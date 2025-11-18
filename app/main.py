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
from app.models import Address, CrowdReport, CrowdConsensus, RequestMetrics
from app.schemas import ReportRequest, ReportResponse, LookupResponse, ConsensusInfo, ZoneResponse
from app.models import Address, CrowdReport, CrowdConsensus, RequestMetrics, ApiKey
from app.schemas import (
    ReportRequest, ReportResponse, LookupResponse, ConsensusInfo, ConsensusDetails,
    MobileLookupRequest, MobileLookupResponse, MobileReportRequest, MobileReportResponse
)
from app.models import Address, CrowdReport, CrowdConsensus, RequestMetrics, User
from app.schemas import ReportRequest, ReportResponse, LookupResponse, ConsensusInfo, ConsensusDetails
from app.models import Address, CrowdReport, CrowdConsensus
from app.schemas import (
    ReportRequest, ReportResponse, LookupResponse, ConsensusInfo, ConsensusDetails,
    InterpretAddressRequest, InterpretAddressResponse
)
from app.models import Address, CrowdReport, CrowdConsensus, RequestMetrics
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
from app.zone_locator import (
    find_zone,
    find_city,
    validate_coordinates,
    get_zone_statistics
)
from app.api_key_auth import require_api_key, record_api_key_usage
from app.mobile_rate_limiter import mobile_rate_limiter

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
from app.middleware import (
    RequestLoggingMiddleware,
    APIKeyAuthMiddleware,
    APIKeyRateLimiter,
    APIUsageTrackingMiddleware
)
from app.metrics import MetricsManager
from app.logging_config import app_logger, error_logger
from app.admin_routes import router as admin_router
from app.auth import get_optional_current_user, require_authenticated
from app.routers import auth, admin

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI
app = FastAPI(
    title="TrashAlert API",
    description="API for trash pickup schedules with crowdsourced data and RBAC",
    version="2.0.0"
)

# Include routers
app.include_router(auth.router)
app.include_router(admin.router)

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

# Initialize API key rate limiter
api_key_rate_limiter = APIKeyRateLimiter()

# Add middleware in reverse order (last added = first executed)
# Order: Request logging -> Usage tracking -> API key auth -> Application
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(APIUsageTrackingMiddleware)
app.add_middleware(APIKeyAuthMiddleware, rate_limiter=api_key_rate_limiter)

# Include admin routes
app.include_router(admin_router)

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
        "endpoints": ["/lookup", "/report", "/stats", "/zone"]
        "endpoints": ["/lookup", "/report", "/interpret-address", "/stats"]
    }


@app.post("/report", response_model=ReportResponse, dependencies=[Depends(require_authenticated)])
async def submit_report(
    report: ReportRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_optional_current_user)
):
    """
    Submit a crowdsourced report for trash pickup schedule.

    **Authentication Required:** This endpoint requires authentication with any role
    (user, reporter, city_partner, admin).

    This endpoint:
    1. Normalizes the provided address
    2. Finds or creates an address record
    3. Stores the report in crowd_reports table (linked to authenticated user)
    4. Updates consensus calculations
    5. Returns the updated consensus

    Args:
        report: Report data including address and pickup days
        request: FastAPI request (for IP tracking and metrics)
        db: Database session
        current_user: Current authenticated user (optional for backward compatibility)

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

        # Create crowd report (link to authenticated user if available)
        new_report = CrowdReport(
            address_id=address.id,
            trash_day=trash_day,
            recycling_day=recycling_day,
            green_day=green_day,
            user_hash=report.user_hash,  # Keep for backward compatibility
            user_id=current_user.id if current_user else None,  # Link to authenticated user
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


@app.get("/zone", response_model=ZoneResponse)
async def get_zone(
    lat: float,
    lon: float,
    city: Optional[str] = None
):
    """
    Find the service zone for a given geographic coordinate.

    This endpoint uses geofencing with point-in-polygon operations to determine
    which pickup zone contains the specified location.

    Args:
        lat: Latitude (decimal degrees, -90 to 90)
        lon: Longitude (decimal degrees, -180 to 180)
        city: Optional city name or slug to narrow search (e.g., "brawley", "San Diego")

    Returns:
        ZoneResponse with zone information if found, or found=False if no zone matches

    Example:
        GET /zone?lat=32.9786&lon=-115.5303
        GET /zone?lat=32.9786&lon=-115.5303&city=brawley
    """
    # Validate coordinates
    is_valid, error_msg = validate_coordinates(lat, lon)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # Convert city name to slug if provided
    city_slug = None
    if city:
        # Normalize city input (handle "San Diego", "san_diego", "san diego", etc.)
        city_slug = city.lower().strip().replace(' ', '_').replace('-', '_')

    # Find zone
    try:
        zone_info = find_zone(lat, lon, city_slug=city_slug)

        if zone_info:
            # Get full city name from slug
            city_name = None
            if zone_info.get('city_slug'):
                # Try to get display name from cities.yaml
                from app.utils import load_cities_config
                config = load_cities_config()
                for city_config in config.get('cities', []):
                    # Match by city_id or name
                    city_id = city_config.get('city_id', '')
                    if city_id.endswith(zone_info['city_slug']):
                        city_name = city_config.get('name')
                        break

                # Fallback: convert slug to title case
                if not city_name:
                    city_name = zone_info['city_slug'].replace('_', ' ').title()

            return ZoneResponse(
                found=True,
                lat=lat,
                lon=lon,
                zone_id=zone_info.get('zone_id'),
                zone_name=zone_info.get('zone_name'),
                city_slug=zone_info.get('city_slug'),
                city_name=city_name,
                trash_day=zone_info.get('trash_day'),
                recycling_day=zone_info.get('recycling_day'),
                green_waste_day=zone_info.get('green_waste_day'),
                properties=zone_info.get('properties')
            )
        else:
            # No zone found - check if at least in a city boundary
            city_info = find_city(lat, lon)

            city_name = None
            city_slug_found = None
            if city_info:
                city_slug_found = city_info.get('city_slug')
                city_name = city_info.get('properties', {}).get('name')

            return ZoneResponse(
                found=False,
                lat=lat,
                lon=lon,
                zone_id=None,
                zone_name=None,
                city_slug=city_slug_found,
                city_name=city_name,
                trash_day=None,
                recycling_day=None,
                green_waste_day=None,
                properties=city_info.get('properties') if city_info else None
            )

    except Exception as e:
        logger.error(f"Error in /zone endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing zone lookup: {str(e)}"
        )


@app.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get statistics about the database."""
    from sqlalchemy import func, distinct
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
# MOBILE ENDPOINTS - Simplified & Optimized for Mobile Apps
# ============================================================================

@app.get(
    "/mobile/lookup",
    response_model=MobileLookupResponse,
    tags=["Mobile"],
    summary="Mobile-optimized lookup endpoint",
    description="Simplified lookup endpoint for mobile apps. Requires API key authentication. "
                "Returns minimal payload to reduce bandwidth usage."
)
async def mobile_lookup(
    request: Request,
    address: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    api_key: ApiKey = Depends(require_api_key),
    db: Session = Depends(get_db)
):
    """Mobile-optimized address lookup endpoint.

    Features:
    - API key authentication required
    - Per-API-key rate limiting (30/min, 500/hour by default)
    - Simplified response payload (minimal JSON)
    - Abbreviated day names (MON-SUN vs MONDAY-SUNDAY)
    - Essential fields only

    Query Parameters:
        - address: Full address string OR
        - lat + lon: Coordinates

    Returns:
        MobileLookupResponse with simplified data structure
    """
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")

    # Validate input
    lookup_req = MobileLookupRequest(address=address, lat=lat, lon=lon)

    # Check mobile rate limiter (API key-based)
    allowed, error_msg, rate_stats = mobile_rate_limiter.is_allowed(
        api_key=api_key,
        ip_address=client_ip
    )

    if not allowed:
        # Record blocked request
        response_time = (time.time() - start_time) * 1000
        record_api_key_usage(
            db=db,
            api_key_id=api_key.id,
            endpoint="/mobile/lookup",
            method="GET",
            status_code=429,
            response_time_ms=response_time,
            ip_address=client_ip,
            user_agent=user_agent
        )

        raise HTTPException(
            status_code=429,
            detail=error_msg,
            headers={
                "X-RateLimit-Limit-Minute": str(rate_stats["limit_per_minute"]),
                "X-RateLimit-Limit-Hour": str(rate_stats["limit_per_hour"]),
                "X-RateLimit-Remaining-Minute": str(rate_stats["remaining_minute"]),
                "X-RateLimit-Remaining-Hour": str(rate_stats["remaining_hour"])
            }
        )

    try:
        # Determine lookup method
        if lookup_req.lat is not None and lookup_req.lon is not None:
            # Coordinate-based lookup
            address_record = find_address_by_coordinates(db, lookup_req.lat, lookup_req.lon)
            if not address_record:
                raise HTTPException(
                    status_code=404,
                    detail="No address found near coordinates"
                )
        else:
            # Address-based lookup
            normalized = normalize_address(lookup_req.address)
            address_record = db.query(Address).filter(
                Address.normalized_address == normalized
            ).first()

            if not address_record:
                raise HTTPException(
                    status_code=404,
                    detail="Address not found"
                )

        # Determine data source priority
        consensus = db.query(CrowdConsensus).filter(
            CrowdConsensus.address_id == address_record.id
        ).first()

        # Determine source and days
        if consensus and consensus.is_verified:
            source = "verified"
            trash_day = consensus.consensus_trash_day
            recycling_day = consensus.consensus_recycling_day
            green_day = consensus.consensus_green_day
        elif address_record.official_trash_day:
            source = "official"
            trash_day = address_record.official_trash_day
            recycling_day = address_record.official_recycling_day
            green_day = address_record.official_green_day
        elif consensus:
            source = "unverified"
            trash_day = consensus.consensus_trash_day
            recycling_day = consensus.consensus_recycling_day
            green_day = consensus.consensus_green_day
        else:
            source = "unknown"
            trash_day = None
            recycling_day = None
            green_day = None

        # Helper to convert to abbreviation
        def to_abbrev(day: Optional[str]) -> Optional[str]:
            if not day:
                return None
            day_map = {
                'MONDAY': 'MON', 'TUESDAY': 'TUE', 'WEDNESDAY': 'WED',
                'THURSDAY': 'THU', 'FRIDAY': 'FRI', 'SATURDAY': 'SAT', 'SUNDAY': 'SUN'
            }
            return day_map.get(day.upper(), day[:3].upper())

        # Build response
        response = MobileLookupResponse(
            address=address_record.normalized_address,
            city=address_record.city,
            trash=to_abbrev(trash_day),
            recycling=to_abbrev(recycling_day),
            green=to_abbrev(green_day),
            source=source,
            lat=address_record.lat,
            lon=address_record.lon
        )

        # Record successful usage
        response_time = (time.time() - start_time) * 1000
        record_api_key_usage(
            db=db,
            api_key_id=api_key.id,
            endpoint="/mobile/lookup",
            method="GET",
            status_code=200,
            response_time_ms=response_time,
            ip_address=client_ip,
            user_agent=user_agent
        )

        app_logger.info(
            f"Mobile lookup success: {address_record.normalized_address} "
            f"(API key: {api_key.key_prefix})"
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        error_logger.error(f"Mobile lookup error: {str(e)}", exc_info=True)
        response_time = (time.time() - start_time) * 1000
        record_api_key_usage(
            db=db,
            api_key_id=api_key.id,
            endpoint="/mobile/lookup",
            method="GET",
            status_code=500,
            response_time_ms=response_time,
            ip_address=client_ip,
            user_agent=user_agent
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post(
    "/mobile/report",
    response_model=MobileReportResponse,
    tags=["Mobile"],
    summary="Mobile-optimized report endpoint",
    description="Simplified report submission for mobile apps. Requires API key authentication."
)
async def mobile_report(
    request: Request,
    report_data: MobileReportRequest,
    api_key: ApiKey = Depends(require_api_key),
    db: Session = Depends(get_db)
):
    """Mobile-optimized report submission endpoint.

    Features:
    - API key authentication required
    - Per-API-key rate limiting
    - Simplified request/response payloads
    - Abbreviated day names

    Request Body:
        MobileReportRequest with address and at least one pickup day

    Returns:
        MobileReportResponse with success status and simplified consensus info
    """
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "")

    # Check mobile rate limiter
    allowed, error_msg, rate_stats = mobile_rate_limiter.is_allowed(
        api_key=api_key,
        ip_address=client_ip
    )

    if not allowed:
        response_time = (time.time() - start_time) * 1000
        record_api_key_usage(
            db=db,
            api_key_id=api_key.id,
            endpoint="/mobile/report",
            method="POST",
            status_code=429,
            response_time_ms=response_time,
            ip_address=client_ip,
            user_agent=user_agent
        )

        raise HTTPException(
            status_code=429,
            detail=error_msg,
            headers={
                "X-RateLimit-Limit-Minute": str(rate_stats["limit_per_minute"]),
                "X-RateLimit-Limit-Hour": str(rate_stats["limit_per_hour"]),
                "X-RateLimit-Remaining-Minute": str(rate_stats["remaining_minute"]),
                "X-RateLimit-Remaining-Hour": str(rate_stats["remaining_hour"])
            }
        )

    try:
        # Normalize address
        normalized_address = normalize_address(report_data.address)

        # Find or create address
        address_record = find_or_create_address(db, normalized_address)

        # Create crowd report
        crowd_report = CrowdReport(
            address_id=address_record.id,
            trash_day=report_data.trash,
            recycling_day=report_data.recycling,
            green_day=report_data.green,
            user_hash=report_data.user_id,
            ip_address=client_ip,
            user_agent=user_agent
        )

        db.add(crowd_report)
        db.commit()

        # Update consensus
        consensus = update_crowd_consensus(db, address_record.id)

        # Build response
        response = MobileReportResponse(
            success=True,
            message="Report submitted successfully",
            address=normalized_address,
            verified=consensus.is_verified if consensus else False,
            reports=consensus.reports_count if (consensus and consensus.is_verified) else None
        )

        # Record successful usage
        response_time = (time.time() - start_time) * 1000
        record_api_key_usage(
            db=db,
            api_key_id=api_key.id,
            endpoint="/mobile/report",
            method="POST",
            status_code=200,
            response_time_ms=response_time,
            ip_address=client_ip,
            user_agent=user_agent
        )

        app_logger.info(
            f"Mobile report success: {normalized_address} "
            f"(API key: {api_key.key_prefix})"
        )

        return response

    except Exception as e:
        error_logger.error(f"Mobile report error: {str(e)}", exc_info=True)
        response_time = (time.time() - start_time) * 1000
        record_api_key_usage(
            db=db,
            api_key_id=api_key.id,
            endpoint="/mobile/report",
            method="POST",
            status_code=500,
            response_time_ms=response_time,
            ip_address=client_ip,
            user_agent=user_agent
        )
        raise HTTPException(status_code=500, detail="Internal server error")
