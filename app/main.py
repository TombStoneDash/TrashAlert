"""TrashAlert FastAPI application."""
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime, timedelta
from collections import defaultdict
import logging
import time

from app.database import get_db, engine, Base
from app.models import Address, CrowdReport, CrowdConsensus
from app.schemas import (
    ReportRequest, ReportResponse, LookupResponse, ConsensusInfo, ConsensusDetails,
    InterpretAddressRequest, InterpretAddressResponse,
    UserCreate, UserResponse, SubscriptionCreate, SubscriptionUpdate, SubscriptionResponse,
    TestNotificationRequest, TestNotificationResponse
)
from app.models import Address, CrowdReport, CrowdConsensus, RequestMetrics, User, AddressSubscription, NotificationLog
from app.utils import (
    normalize_address,
    find_or_create_address,
    find_address_by_coordinates,
    update_crowd_consensus,
    validate_day,
    day_abbrev_to_full,
    get_city_id_from_name,
    get_city_name_from_id,
    geocode_address,
    get_supported_cities
)
from app.ai_service import create_ai_interpreter
from app.rate_limiter import rate_limiter
from app.cache import lookup_cache

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
from app.middleware import RequestLoggingMiddleware
from app.metrics import MetricsManager
from app.logging_config import app_logger, error_logger

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI
app = FastAPI(
    title="TrashAlert API",
    description="API for trash pickup schedules with crowdsourced data",
    version="1.0.0"
)

# Initialize notification scheduler
scheduler = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    global scheduler
    from app.scheduler_service import get_scheduler

    # Start the notification scheduler
    try:
        scheduler = get_scheduler()
        scheduler.start()
        logger.info("Notification scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start notification scheduler: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    global scheduler

    # Stop the notification scheduler
    if scheduler:
        try:
            scheduler.stop()
            logger.info("Notification scheduler stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping notification scheduler: {e}")

# Simple in-memory rate limiter
# In production, use Redis or similar distributed cache
# Format: {ip_address: [(timestamp1, address1), (timestamp2, address2), ...]}
rate_limit_store = defaultdict(list)
RATE_LIMIT_WINDOW = timedelta(minutes=15)  # 15-minute window
MAX_REPORTS_PER_WINDOW = 10  # Max 10 reports per IP per 15 minutes
MAX_REPORTS_PER_ADDRESS = 3  # Max 3 reports per IP per address per window


def check_rate_limit(ip_address: str, normalized_address: str) -> bool:
    """
    Check if request should be rate limited.

    Rules:
    - Max 10 reports per IP per 15 minutes (global)
    - Max 3 reports per IP per address per 15 minutes (prevents spam on single address)

    Returns:
        True if allowed, False if rate limited
    """
    now = datetime.now()
    cutoff = now - RATE_LIMIT_WINDOW

    # Clean old entries
    rate_limit_store[ip_address] = [
        (ts, addr) for ts, addr in rate_limit_store[ip_address]
        if ts > cutoff
    ]

    recent_reports = rate_limit_store[ip_address]

    # Check global limit
    if len(recent_reports) >= MAX_REPORTS_PER_WINDOW:
        return False

    # Check per-address limit
    address_reports = [addr for ts, addr in recent_reports if addr == normalized_address]
    if len(address_reports) >= MAX_REPORTS_PER_ADDRESS:
        return False

    return True


def record_report(ip_address: str, normalized_address: str):
    """Record a report for rate limiting."""
    rate_limit_store[ip_address].append((datetime.now(), normalized_address))
# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

app_logger.info("TrashAlert API started")


# ============================================================================
# GLOBAL EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 Not Found errors with structured response."""
    logger.warning(f"404 Not Found: {request.method} {request.url.path}")
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": f"The requested endpoint '{request.url.path}' does not exist",
            "path": request.url.path,
            "method": request.method
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle 422 Validation errors with detailed structured response."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": " -> ".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })

    logger.warning(f"422 Validation Error: {request.method} {request.url.path} - {errors}")

    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "message": "Request validation failed",
            "details": errors,
            "path": request.url.path
        }
    )


@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc):
    """Handle 500 Internal Server errors with structured response."""
    logger.error(f"500 Internal Server Error: {request.method} {request.url.path}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later.",
            "path": request.url.path
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all handler for any unhandled exceptions."""
    logger.error(f"Unhandled exception: {request.method} {request.url.path} - {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later.",
            "path": request.url.path
        }
    )


# ============================================================================
# MIDDLEWARE
# ============================================================================

@app.middleware("http")
async def rate_limit_and_logging_middleware(request: Request, call_next):
    """Apply rate limiting and log all requests with timing information."""
    start_time = time.time()

    # Get client IP
    client_ip = request.client.host if request.client else "unknown"

    # Log incoming request
    logger.info(f"→ {request.method} {request.url.path} from {client_ip}")

    # Skip rate limiting for health check endpoint
    if request.url.path != "/":
        # Check rate limit
        allowed, reason = rate_limiter.is_allowed(client_ip)

        if not allowed:
            logger.warning(f"Rate limit exceeded for {client_ip}: {reason}")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": reason,
                    "client_ip": client_ip
                }
            )

    try:
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000

        # Log response
        logger.info(f"← {request.method} {request.url.path} - {response.status_code} - {duration_ms:.2f}ms")

        # Add performance header
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        # Add rate limit info to response headers
        if request.url.path != "/":
            stats = rate_limiter.get_stats(client_ip)
            response.headers["X-RateLimit-Limit-Minute"] = str(stats["limit_per_minute"])
            response.headers["X-RateLimit-Limit-Hour"] = str(stats["limit_per_hour"])
            response.headers["X-RateLimit-Remaining-Minute"] = str(
                max(0, stats["limit_per_minute"] - stats["requests_last_minute"])
            )
            response.headers["X-RateLimit-Remaining-Hour"] = str(
                max(0, stats["limit_per_hour"] - stats["requests_last_hour"])
            )

        return response
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"✗ {request.method} {request.url.path} - Error after {duration_ms:.2f}ms: {str(e)}")
        raise


# ============================================================================
# ENDPOINTS
# ============================================================================


@app.get("/")
async def root() -> Dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "TrashAlert API",
        "version": "1.0.0",
        "endpoints": ["/lookup", "/report", "/interpret-address", "/stats"]
    }


@app.post("/report", response_model=ReportResponse)
async def submit_report(
    report: ReportRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Submit a crowdsourced report for trash pickup schedule.

    This endpoint:
    1. Normalizes the provided address
    2. Finds or creates an address record
    3. Stores the report in crowd_reports table
    4. Updates consensus calculations
    5. Returns the updated consensus

    Args:
        report: Report data including address and pickup days
        request: FastAPI request (for IP tracking and metrics)
        db: Database session

    Returns:
        Report response with consensus information
    """
    start_time = time.time()
    city = None
    status_code = 200
    error_msg = None

    try:
        # Validate days
        trash_day = validate_day(report.trash_day)
        recycling_day = validate_day(report.recycling_day)
        green_day = validate_day(report.green_day)

        # At least one day must be provided
        if not any([trash_day, recycling_day, green_day]):
            status_code = 400
            error_msg = "At least one pickup day must be provided"
            raise HTTPException(status_code=status_code, detail=error_msg)

        # Find or create address
        address = find_or_create_address(db, report.address)
        city = address.city

        app_logger.info(
            f"Report submission: {address.normalized_address} - "
            f"City: {city} - Trash: {trash_day}, Recycling: {recycling_day}, Green: {green_day}"
        )

        # Create crowd report
        new_report = CrowdReport(
            address_id=address.id,
            trash_day=trash_day,
            recycling_day=recycling_day,
            green_day=green_day,
            user_hash=report.user_hash,
            ip_address=request.client.host if request.client else None
        )
        db.add(new_report)
        db.commit()

        # Update consensus
        consensus = update_crowd_consensus(db, address.id)

        # Build response
        consensus_info = None
        if consensus:
            consensus_info = ConsensusInfo(
                trash_day=consensus.consensus_trash_day,
                recycling_day=consensus.consensus_recycling_day,
                green_day=consensus.consensus_green_day,
                reports_count=consensus.total_reports,
                trash_agreement_ratio=consensus.trash_agreement_ratio,
                recycling_agreement_ratio=consensus.recycling_agreement_ratio,
                green_agreement_ratio=consensus.green_agreement_ratio,
                is_verified=consensus.is_verified
            )

        app_logger.info(
            f"Report submitted successfully: {address.normalized_address} - "
            f"Total reports: {consensus.total_reports if consensus else 0}"
        )

        # Record successful metric
        response_time_ms = (time.time() - start_time) * 1000
        MetricsManager.record_request(
            db=db,
            endpoint='/report',
            method='POST',
            status_code=status_code,
            response_time_ms=response_time_ms,
            city=city,
            user_agent=request.headers.get('user-agent'),
            ip_address=request.client.host if request.client else None
        )

        return ReportResponse(
            success=True,
            message="Report submitted successfully",
            address_id=address.id,
            normalized_address=address.normalized_address,
            consensus=consensus_info
        )

    except HTTPException:
        # Re-raise HTTP exceptions (already logged)
        response_time_ms = (time.time() - start_time) * 1000
        MetricsManager.record_request(
            db=db,
            endpoint='/report',
            method='POST',
            status_code=status_code,
            response_time_ms=response_time_ms,
            city=city,
            error_message=error_msg,
            user_agent=request.headers.get('user-agent'),
            ip_address=request.client.host if request.client else None
        )
        raise
    except Exception as e:
        # Log unexpected errors
        error_logger.error(f"Report submission error: {str(e)}", exc_info=True)
        response_time_ms = (time.time() - start_time) * 1000
        MetricsManager.record_request(
            db=db,
            endpoint='/report',
            method='POST',
            status_code=500,
            response_time_ms=response_time_ms,
            city=city,
            error_message=str(e),
            user_agent=request.headers.get('user-agent'),
            ip_address=request.client.host if request.client else None
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/lookup", response_model=LookupResponse)
async def lookup_address(
    address: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    city_id: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Look up trash pickup schedule for an address.

    Supports multiple input formats:
    1. Full address string (address)
    2. Coordinates (lat + lon)
    3. Address + city_id for more precise matching

    Data source priority:
    1. CROWD_VERIFIED - Verified crowdsourced consensus (≥3 reports, ≥67% agreement)
    2. OFFICIAL - Official municipal data
    3. CROWD_UNVERIFIED - Unverified crowdsourced data
    4. UNKNOWN - No data available

    Args:
        address: Full address string (optional)
        lat: Latitude (optional, requires lon)
        lon: Longitude (optional, requires lat)
        city_id: City identifier from cities.yaml (optional)
        request: FastAPI request object
        db: Database session

    Returns:
        LookupResponse with schedule and source information
    """
    start_time = time.time()
    city_name = None
    status_code = 200

    try:
        # Validate input format
        has_address = bool(address and address.strip())
        has_coords = lat is not None and lon is not None

        if not has_address and not has_coords:
            raise HTTPException(
                status_code=400,
                detail="Must provide either 'address' or both 'lat' and 'lon'"
            )

        # Step 1: Find address record using appropriate method
        addr_record = None

        if has_coords:
            # Coordinate-based lookup
            app_logger.info(f"Lookup by coordinates: ({lat}, {lon}), city_id={city_id}")
            addr_record = find_address_by_coordinates(
                db=db,
                lat=lat,
                lon=lon,
                max_distance_meters=50,
                city_id=city_id
            )

        elif has_address:
            # Address string lookup
            parts = normalize_address(address)
            normalized = parts['normalized_address']
            city_name = parts.get('city')

            # Get city_id from city name if not provided
            if not city_id and city_name:
                city_id = get_city_id_from_name(city_name)

            app_logger.info(f"Lookup by address: {address} -> {normalized}, city_id={city_id}")

            # Try exact match first
            query = db.query(Address).filter(
                Address.normalized_address == normalized
            )

            # Filter by city_id if provided
            if city_id:
                query = query.filter(Address.city_id == city_id)

            addr_record = query.first()

        # Step 2: Return UNKNOWN if no address found
        if not addr_record:
            app_logger.warning(f"Address not found for lookup")

            return LookupResponse(
                matched_address=address or f"({lat}, {lon})",
                city_id=city_id,
                city_name=city_name or get_city_name_from_id(city_id) if city_id else None,
                lat=lat,
                lon=lon,
                trash_day_of_week=None,
                recycling_day_of_week=None,
                green_waste_day_of_week=None,
                data_source="UNKNOWN",
                consensus_reports_count=None,
                consensus_agreement_ratio=None,
                consensus_details=None
            )

        # Step 3: Get consensus data if available
        consensus = db.query(CrowdConsensus).filter(
            CrowdConsensus.address_id == addr_record.id
        ).first()

        # Step 4: Apply source priority logic
        data_source = "UNKNOWN"
        trash_day = None
        recycling_day = None
        green_day = None
        consensus_reports_count = None
        consensus_agreement_ratio = None
        consensus_details = None

        # Priority 1: CROWD_VERIFIED
        if consensus and consensus.is_verified:
            data_source = "CROWD_VERIFIED"
            trash_day = consensus.consensus_trash_day
            recycling_day = consensus.consensus_recycling_day
            green_day = consensus.consensus_green_day
            consensus_reports_count = consensus.total_reports

            # Calculate overall agreement ratio
            ratios = [
                r for r in [
                    consensus.trash_agreement_ratio,
                    consensus.recycling_agreement_ratio,
                    consensus.green_agreement_ratio
                ] if r > 0
            ]
            consensus_agreement_ratio = round(sum(ratios) / len(ratios), 2) if ratios else 0.0

            consensus_details = ConsensusDetails(
                reports_count=consensus.total_reports,
                agreement_ratio=consensus_agreement_ratio
            )

        # Priority 2: OFFICIAL
        elif any([addr_record.official_trash_day,
                  addr_record.official_recycling_day,
                  addr_record.official_green_day]):
            data_source = "OFFICIAL"
            trash_day = addr_record.official_trash_day
            recycling_day = addr_record.official_recycling_day
            green_day = addr_record.official_green_day

        # Priority 3: CROWD_UNVERIFIED
        elif consensus:
            data_source = "CROWD_UNVERIFIED"
            trash_day = consensus.consensus_trash_day
            recycling_day = consensus.consensus_recycling_day
            green_day = consensus.consensus_green_day
            consensus_reports_count = consensus.total_reports

            ratios = [
                r for r in [
                    consensus.trash_agreement_ratio,
                    consensus.recycling_agreement_ratio,
                    consensus.green_agreement_ratio
                ] if r > 0
            ]
            consensus_agreement_ratio = round(sum(ratios) / len(ratios), 2) if ratios else 0.0

            consensus_details = ConsensusDetails(
                reports_count=consensus.total_reports,
                agreement_ratio=consensus_agreement_ratio
            )

        # Step 5: Convert day abbreviations to full names
        trash_day_full = day_abbrev_to_full(trash_day)
        recycling_day_full = day_abbrev_to_full(recycling_day)
        green_day_full = day_abbrev_to_full(green_day)

        # Step 6: Build response
        app_logger.info(f"Lookup result: {addr_record.normalized_address} -> Source: {data_source}")

        response = LookupResponse(
            matched_address=addr_record.normalized_address,
            city_id=addr_record.city_id,
            city_name=addr_record.city,
            lat=addr_record.lat,
            lon=addr_record.lon,
            trash_day_of_week=trash_day_full,
            recycling_day_of_week=recycling_day_full,
            green_waste_day_of_week=green_day_full,
            data_source=data_source,
            consensus_reports_count=consensus_reports_count,
            consensus_agreement_ratio=consensus_agreement_ratio,
            consensus_details=consensus_details
        )

        # Step 7: Record metrics
        response_time_ms = (time.time() - start_time) * 1000
        MetricsManager.record_request(
            db=db,
            endpoint='/lookup',
            method='GET',
            status_code=status_code,
            response_time_ms=response_time_ms,
            city=addr_record.city if addr_record else city_name,
            user_agent=request.headers.get('user-agent') if request else None,
            ip_address=request.client.host if request and request.client else None
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        error_logger.error(f"Lookup error: {str(e)}", exc_info=True)
        response_time_ms = (time.time() - start_time) * 1000
        MetricsManager.record_request(
            db=db,
            endpoint='/lookup',
            method='GET',
            status_code=500,
            response_time_ms=response_time_ms,
            city=city_name,
            error_message=str(e),
            user_agent=request.headers.get('user-agent') if request else None,
            ip_address=request.client.host if request and request.client else None
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/interpret-address", response_model=InterpretAddressResponse)
async def interpret_address(
    request_data: InterpretAddressRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Interpret and normalize a freeform address using AI with geocoding fallback.

    This endpoint:
    1. Uses AI (OpenAI or Anthropic) to parse and normalize freeform text
    2. Extracts address components and infers likely city from config
    3. Optionally uses Nominatim geocoding as fallback for low-confidence results
    4. Returns normalized address, coordinates, and confidence score

    Args:
        request_data: Request with freeform text to interpret
        request: FastAPI request object
        db: Database session

    Returns:
        InterpretAddressResponse with normalized address and metadata
    """
    start_time = time.time()
    city_name = None
    status_code = 200
    error_msg = None

    try:
        text = request_data.text
        use_geocoding = request_data.use_geocoding

        app_logger.info(f"Interpreting address from text: {text[:100]}")

        # Step 1: Get supported cities for better AI matching
        supported_cities = get_supported_cities()

        # Step 2: Try AI interpretation first
        ai_interpreter = create_ai_interpreter(cities_list=supported_cities)
        ai_result = await ai_interpreter.interpret(text)

        interpretation_method = "ai"
        normalized_address = ""
        confidence = 0.0
        city = None
        city_id = None
        state = None
        zip_code = None
        lat = None
        lon = None
        ai_reasoning = None
        geocoding_quality = None

        if ai_result and ai_result.confidence > 0.0:
            # AI interpretation succeeded
            normalized_address = ai_result.normalized_address
            confidence = ai_result.confidence
            city = ai_result.city
            state = ai_result.state
            zip_code = ai_result.zip_code
            ai_reasoning = ai_result.reasoning

            # Match city to city_id from config
            if city:
                city_id = get_city_id_from_name(city)

            app_logger.info(
                f"AI interpretation: {normalized_address} "
                f"(confidence={confidence}, city={city})"
            )

            # Step 3: If confidence is low and geocoding is enabled, try geocoding fallback
            if use_geocoding and confidence < 0.7:
                app_logger.info("Low confidence, attempting geocoding fallback")
                geocode_result = geocode_address(normalized_address)

                if geocode_result:
                    interpretation_method = "hybrid"
                    lat = geocode_result['lat']
                    lon = geocode_result['lon']
                    geocoding_quality = geocode_result['quality']

                    # Update address components from geocoding if better
                    components = geocode_result['address_components']
                    if not city and components.get('city'):
                        city = components['city']
                        city_id = get_city_id_from_name(city)
                    if not state and components.get('state'):
                        state = components['state']
                    if not zip_code and components.get('postcode'):
                        zip_code = components['postcode']

                    # Boost confidence if geocoding quality is high
                    if geocoding_quality == 'high':
                        confidence = max(confidence, 0.8)
                    elif geocoding_quality == 'medium':
                        confidence = max(confidence, 0.6)

                    app_logger.info(
                        f"Geocoding enhanced result: quality={geocoding_quality}, "
                        f"new confidence={confidence}"
                    )

        elif use_geocoding:
            # AI failed, try geocoding directly on the input text
            app_logger.info("AI interpretation failed, trying geocoding directly")
            geocode_result = geocode_address(text)

            if geocode_result:
                interpretation_method = "geocoding"
                normalized_address = geocode_result['display_name']
                lat = geocode_result['lat']
                lon = geocode_result['lon']
                geocoding_quality = geocode_result['quality']

                # Extract components
                components = geocode_result['address_components']
                city = components.get('city')
                state = components.get('state')
                zip_code = components.get('postcode')

                if city:
                    city_id = get_city_id_from_name(city)

                # Set confidence based on geocoding quality
                if geocoding_quality == 'high':
                    confidence = 0.85
                elif geocoding_quality == 'medium':
                    confidence = 0.65
                else:
                    confidence = 0.4

                app_logger.info(
                    f"Geocoding result: {normalized_address} "
                    f"(quality={geocoding_quality}, confidence={confidence})"
                )

        # Step 4: Build response
        if not normalized_address:
            # Complete failure
            status_code = 400
            error_msg = "Failed to interpret address with both AI and geocoding"
            app_logger.warning(f"Failed to interpret: {text}")

            response_time_ms = (time.time() - start_time) * 1000
            MetricsManager.record_request(
                db=db,
                endpoint='/interpret-address',
                method='POST',
                status_code=status_code,
                response_time_ms=response_time_ms,
                city=city_name,
                error_message=error_msg,
                user_agent=request.headers.get('user-agent'),
                ip_address=request.client.host if request.client else None
            )

            return InterpretAddressResponse(
                success=False,
                normalized_address="",
                confidence=0.0,
                interpretation_method=interpretation_method,
                error=error_msg
            )

        # Success
        app_logger.info(
            f"Successfully interpreted address: {normalized_address} "
            f"(method={interpretation_method}, confidence={confidence})"
        )

        response_time_ms = (time.time() - start_time) * 1000
        MetricsManager.record_request(
            db=db,
            endpoint='/interpret-address',
            method='POST',
            status_code=status_code,
            response_time_ms=response_time_ms,
            city=city,
            user_agent=request.headers.get('user-agent'),
            ip_address=request.client.host if request.client else None
        )

        return InterpretAddressResponse(
            success=True,
            normalized_address=normalized_address,
            confidence=confidence,
            city=city,
            city_id=city_id,
            state=state,
            zip_code=zip_code,
            lat=lat,
            lon=lon,
            interpretation_method=interpretation_method,
            ai_reasoning=ai_reasoning,
            geocoding_quality=geocoding_quality
        )

    except HTTPException:
        raise
    except Exception as e:
        error_logger.error(f"Address interpretation error: {str(e)}", exc_info=True)
        response_time_ms = (time.time() - start_time) * 1000
        MetricsManager.record_request(
            db=db,
            endpoint='/interpret-address',
            method='POST',
            status_code=500,
            response_time_ms=response_time_ms,
            city=city_name,
            error_message=str(e),
            user_agent=request.headers.get('user-agent'),
            ip_address=request.client.host if request.client else None
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/stats")
async def get_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get statistics about the database and cache performance."""
    from sqlalchemy import func, distinct
    total_addresses = db.query(Address).count()
    total_reports = db.query(CrowdReport).count()
    total_consensus = db.query(CrowdConsensus).count()
    verified_consensus = db.query(CrowdConsensus).filter(
        CrowdConsensus.is_verified == True
    ).count()

    # Get city breakdown
    city_stats = db.query(
        Address.city,
        func.count(Address.id).label('address_count')
    ).group_by(Address.city).order_by(Address.city).all()

    cities = [
        {"city": city, "address_count": count}
        for city, count in city_stats
        if city  # Filter out None values
    ]

    return {
        "total_addresses": total_addresses,
        "total_reports": total_reports,
        "total_consensus": total_consensus,
        "verified_consensus": verified_consensus,
        "cities": cities,
        "pilot_cities": [
            "El Centro",
            "Imperial",
            "Brawley",
            "Holtville",
            "Calexico",
            "San Diego"
        ]
    }


# ============================================================================
# NOTIFICATION SYSTEM ENDPOINTS
# ============================================================================

@app.post("/api/users", response_model=UserResponse, status_code=201)
async def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user for notifications.

    - **email**: User's email address (required, unique)
    - **phone**: Optional phone number for SMS notifications
    - **display_name**: Optional display name
    - **timezone**: User's timezone (default: America/Los_Angeles)
    """
    # Check if user with email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    # Create new user
    new_user = User(
        email=user_data.email,
        phone=user_data.phone,
        display_name=user_data.display_name,
        timezone=user_data.timezone
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"Created new user: {new_user.email}")
    return new_user


@app.get("/api/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user by ID."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/api/users", response_model=List[UserResponse])
async def list_users(
    email: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all users with optional filtering."""
    query = db.query(User)

    if email:
        query = query.filter(User.email == email)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    users = query.offset(skip).limit(limit).all()
    return users


@app.post("/api/subscriptions", response_model=SubscriptionResponse, status_code=201)
async def create_subscription(
    user_id: int,
    subscription_data: SubscriptionCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new subscription for a user.

    - **user_id**: ID of the user (query parameter)
    - **address**: Full address to subscribe to
    - **notify_trash/recycling/green**: What to notify about
    - **notify_email/sms**: Notification channels
    - **days_before**: How many days before pickup to notify (0-7)
    - **notification_time**: Time to send notifications (HH:MM)
    """
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Find or create address
    normalized = normalize_address(subscription_data.address)
    address = db.query(Address).filter(Address.normalized_address == normalized).first()

    if not address:
        # Try to create address (simplified - you may want to geocode here)
        address = Address(normalized_address=normalized)
        db.add(address)
        db.flush()

    # Check if subscription already exists
    existing = db.query(AddressSubscription).filter(
        AddressSubscription.user_id == user_id,
        AddressSubscription.address_id == address.id
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Subscription for this address already exists. Use PUT to update."
        )

    # Create subscription
    new_subscription = AddressSubscription(
        user_id=user_id,
        address_id=address.id,
        notify_trash=subscription_data.notify_trash,
        notify_recycling=subscription_data.notify_recycling,
        notify_green=subscription_data.notify_green,
        notify_email=subscription_data.notify_email,
        notify_sms=subscription_data.notify_sms,
        days_before=subscription_data.days_before,
        notification_time=subscription_data.notification_time
    )

    db.add(new_subscription)
    db.commit()
    db.refresh(new_subscription)

    logger.info(f"Created subscription for user {user_id} at address {address.normalized_address}")

    # Return with address details
    response = SubscriptionResponse(
        id=new_subscription.id,
        user_id=new_subscription.user_id,
        address_id=new_subscription.address_id,
        address=address.normalized_address,
        notify_trash=new_subscription.notify_trash,
        notify_recycling=new_subscription.notify_recycling,
        notify_green=new_subscription.notify_green,
        notify_email=new_subscription.notify_email,
        notify_sms=new_subscription.notify_sms,
        days_before=new_subscription.days_before,
        notification_time=new_subscription.notification_time,
        is_active=new_subscription.is_active,
        created_at=new_subscription.created_at
    )
    return response


@app.get("/api/subscriptions", response_model=List[SubscriptionResponse])
async def list_subscriptions(
    user_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List subscriptions with optional filtering."""
    query = db.query(AddressSubscription)

    if user_id is not None:
        query = query.filter(AddressSubscription.user_id == user_id)
    if is_active is not None:
        query = query.filter(AddressSubscription.is_active == is_active)

    subscriptions = query.offset(skip).limit(limit).all()

    # Build response with address details
    results = []
    for sub in subscriptions:
        address = db.query(Address).filter(Address.id == sub.address_id).first()
        results.append(SubscriptionResponse(
            id=sub.id,
            user_id=sub.user_id,
            address_id=sub.address_id,
            address=address.normalized_address if address else "Unknown",
            notify_trash=sub.notify_trash,
            notify_recycling=sub.notify_recycling,
            notify_green=sub.notify_green,
            notify_email=sub.notify_email,
            notify_sms=sub.notify_sms,
            days_before=sub.days_before,
            notification_time=sub.notification_time,
            is_active=sub.is_active,
            created_at=sub.created_at
        ))

    return results


@app.get("/api/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def get_subscription(subscription_id: int, db: Session = Depends(get_db)):
    """Get subscription by ID."""
    subscription = db.query(AddressSubscription).filter(
        AddressSubscription.id == subscription_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    address = db.query(Address).filter(Address.id == subscription.address_id).first()

    return SubscriptionResponse(
        id=subscription.id,
        user_id=subscription.user_id,
        address_id=subscription.address_id,
        address=address.normalized_address if address else "Unknown",
        notify_trash=subscription.notify_trash,
        notify_recycling=subscription.notify_recycling,
        notify_green=subscription.notify_green,
        notify_email=subscription.notify_email,
        notify_sms=subscription.notify_sms,
        days_before=subscription.days_before,
        notification_time=subscription.notification_time,
        is_active=subscription.is_active,
        created_at=subscription.created_at
    )


@app.put("/api/subscriptions/{subscription_id}", response_model=SubscriptionResponse)
async def update_subscription(
    subscription_id: int,
    update_data: SubscriptionUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing subscription."""
    subscription = db.query(AddressSubscription).filter(
        AddressSubscription.id == subscription_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    # Update fields if provided
    if update_data.notify_trash is not None:
        subscription.notify_trash = update_data.notify_trash
    if update_data.notify_recycling is not None:
        subscription.notify_recycling = update_data.notify_recycling
    if update_data.notify_green is not None:
        subscription.notify_green = update_data.notify_green
    if update_data.notify_email is not None:
        subscription.notify_email = update_data.notify_email
    if update_data.notify_sms is not None:
        subscription.notify_sms = update_data.notify_sms
    if update_data.days_before is not None:
        subscription.days_before = update_data.days_before
    if update_data.notification_time is not None:
        subscription.notification_time = update_data.notification_time
    if update_data.is_active is not None:
        subscription.is_active = update_data.is_active

    db.commit()
    db.refresh(subscription)

    address = db.query(Address).filter(Address.id == subscription.address_id).first()

    logger.info(f"Updated subscription {subscription_id}")

    return SubscriptionResponse(
        id=subscription.id,
        user_id=subscription.user_id,
        address_id=subscription.address_id,
        address=address.normalized_address if address else "Unknown",
        notify_trash=subscription.notify_trash,
        notify_recycling=subscription.notify_recycling,
        notify_green=subscription.notify_green,
        notify_email=subscription.notify_email,
        notify_sms=subscription.notify_sms,
        days_before=subscription.days_before,
        notification_time=subscription.notification_time,
        is_active=subscription.is_active,
        created_at=subscription.created_at
    )


@app.delete("/api/subscriptions/{subscription_id}", status_code=204)
async def delete_subscription(subscription_id: int, db: Session = Depends(get_db)):
    """Delete a subscription."""
    subscription = db.query(AddressSubscription).filter(
        AddressSubscription.id == subscription_id
    ).first()

    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    db.delete(subscription)
    db.commit()

    logger.info(f"Deleted subscription {subscription_id}")
    return None


@app.post("/api/notifications/test", response_model=TestNotificationResponse)
async def test_notification(
    user_id: int,
    test_data: TestNotificationRequest,
    db: Session = Depends(get_db)
):
    """
    Send a test notification to verify SMS/Email delivery.

    - **user_id**: ID of the user to send test to (query parameter)
    - **notification_type**: Type of notification (trash/recycling/green)
    - **channel**: Channel to test (email/sms/both)
    - **address**: Address to use in test message
    """
    from app.notification_service import get_notification_service

    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    notification_service = get_notification_service()

    email_result = None
    sms_result = None
    success = True
    messages = []

    # Send email test
    if test_data.channel in ["email", "both"]:
        if not user.email:
            messages.append("User has no email address configured")
            success = False
        else:
            email_result = notification_service.send_trash_reminder_email(
                email=user.email,
                address=test_data.address,
                pickup_type=test_data.notification_type,
                pickup_day="tomorrow (TEST)",
                additional_info="This is a test notification from TrashAlert."
            )
            if email_result.get("status") == "sent":
                messages.append(f"Test email sent to {user.email}")
            else:
                messages.append(f"Failed to send email: {email_result.get('error')}")
                success = False

    # Send SMS test
    if test_data.channel in ["sms", "both"]:
        if not user.phone:
            messages.append("User has no phone number configured")
            success = False
        else:
            sms_result = notification_service.send_trash_reminder_sms(
                phone=user.phone,
                address=test_data.address,
                pickup_type=test_data.notification_type,
                pickup_day="tomorrow (TEST)"
            )
            if sms_result.get("status") == "sent":
                messages.append(f"Test SMS sent to {user.phone}")
            else:
                messages.append(f"Failed to send SMS: {sms_result.get('error')}")
                success = False

    return TestNotificationResponse(
        success=success,
        message="; ".join(messages),
        email_result=email_result,
        sms_result=sms_result
    )
