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

from strawberry.fastapi import GraphQLRouter

from app.database import get_db, engine, Base
from app.models import (
    Address, CrowdReport, CrowdConsensus, RequestMetrics,
    User, Badge, ApiKey, AddressSubscription, NotificationLog,
    PipelineRun, PipelineCityStatus
)
from app.schemas import (
    ReportRequest, ReportResponse, LookupResponse, ConsensusInfo, ConsensusDetails, ZoneResponse,
    MobileLookupRequest, MobileLookupResponse, MobileReportRequest, MobileReportResponse,
    InterpretAddressRequest, InterpretAddressResponse, PredictRequest, PredictResponse,
    DelayPrediction, SeasonalPredictionResponse, SeasonalPrediction,
    TrainModelRequest, TrainModelResponse, HeatmapResponse, HeatmapPoint,
    UserCreate, UserResponse, SubscriptionCreate, SubscriptionUpdate, SubscriptionResponse,
    TestNotificationRequest, TestNotificationResponse,
    LeaderboardResponse, UserStatsResponse
)
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
from app.gps_ingestor import router as gps_router
from app.gamification import GamificationService
from app.graphql_schema import schema
from app.redis_cache import redis_cache
from app.routing_optimizer import RouteOptimizer
from app.routing_optimizer.schemas import (
    OptimizeRouteRequest,
    OptimizeRouteResponse,
    RouteStop,
    RouteStatistics,
    Coordinate
)
from app.ai_classifier import (
    AIClassifierRequest,
    AIClassifierResponse,
    classify_schedule_text,
    get_classifier
)
from app.ai_cache import get_cache_manager
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
from app.prediction_service import PredictionService
from app.security import add_security_headers, validate_request_security
from app.mobile import router as mobile_router
from app.admin_routes import router as admin_router
from app.auth import get_optional_current_user, require_authenticated
from app.routers import auth, admin
from app.routers.zones import router as zones_router
from app.routers.map_pages import router as map_pages_router
from app.routers.narpm_pages import router as narpm_pages_router
from app.routers.lookup_api import router as lookup_api_router
from app.routers.schedule_api import router as schedule_api_router
from app.routers.notifications import router as notifications_router
from app.routers.portfolio_api import router as portfolio_api_router
from app.routers.city_pages import router as city_pages_router
from app.routers.sitemap import router as sitemap_router
from app.routers.robots import router as robots_router

# Create database tables
Base.metadata.create_all(bind=engine)

# Initialize FastAPI
app = FastAPI(
    title="TrashAlert API",
    description="API for trash pickup schedules with crowdsourced data and RBAC",
    version="2.0.0"
)

# Include mobile router
app.include_router(mobile_router)

# ============================================================================
# GraphQL Setup
# ============================================================================

async def get_context(request: Request):
    """Context dependency for GraphQL - provides database session."""
    db = next(get_db())
    try:
        return {"db": db, "request": request}
    finally:
        # Don't close here, will be handled by GraphQL router
        pass


# Create GraphQL router with GraphiQL console enabled
graphql_app = GraphQLRouter(
    schema,
    context_getter=get_context,
    graphiql=True  # Enable GraphiQL console
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
# Mount GraphQL endpoint
app.include_router(graphql_app, prefix="/graphql")
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
# Add security middleware
app.middleware("http")(add_security_headers)
app.middleware("http")(validate_request_security)

# Add request logging middleware

# Initialize API key rate limiter
api_key_rate_limiter = APIKeyRateLimiter()

# Add middleware in reverse order (last added = first executed)
# Order: Analytics -> Request logging -> Usage tracking -> API key auth -> Application
from app.analytics import PlausibleMiddleware
app.add_middleware(PlausibleMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(APIUsageTrackingMiddleware)
app.add_middleware(APIKeyAuthMiddleware, rate_limiter=api_key_rate_limiter)

# Include admin routes
app.include_router(admin_router)

# Include GPS tracking router
app.include_router(gps_router)

# Include zone map router
app.include_router(zones_router)

# Include map page routes (/map, /map/embed)
app.include_router(map_pages_router)

# Include NARPM landing pages (/narpm, /narpm/print)
app.include_router(narpm_pages_router)

# Include public lookup API (/api/lookup)
app.include_router(lookup_api_router)

# Include v1 schedule & bulk API (/api/v1/schedule, /api/v1/bulk)
app.include_router(schedule_api_router)

# Include notification signup API (/api/notifications/signup)
app.include_router(notifications_router)

# Include portfolio dashboard API (/api/portfolio/*)
app.include_router(portfolio_api_router)

# Sitemap and robots.txt
app.include_router(sitemap_router)
app.include_router(robots_router)

# Dynamic city pages (/{city_slug}) — must be last (catch-all pattern)
app.include_router(city_pages_router)

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

    # Get client IP (respecting X-Forwarded-For header)
    from app.security import get_client_ip
    client_ip = get_client_ip(request)

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
        "endpoints": {
            "rest": [
                "/lookup", "/report", "/interpret-address", "/stats",
                "/predict", "/predict/train", "/analytics/heatmap",
                "/leaderboard", "/badges", "/users/{user_id}/stats"
            ],
            "mobile": ["/mobile/lookup", "/mobile/daily-schedule", "/mobile/report"],
            "graphql": "/graphql",
            "graphiql": "/graphql (interactive GraphQL console)",
            "optimization": ["/optimize-route"],
            "zones": ["/zone"]
        }
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

        # Create crowd report
        from app.security import get_client_ip
        # Create crowd report (link to authenticated user if available)
        new_report = CrowdReport(
            address_id=address.id,
            trash_day=trash_day,
            recycling_day=recycling_day,
            green_day=green_day,
            user_hash=report.user_hash,  # Keep for backward compatibility
            user_id=current_user.id if current_user else None,  # Link to authenticated user
            ip_address=get_client_ip(request)
        )
        db.add(new_report)
        db.commit()

        # Update consensus
        consensus = update_crowd_consensus(db, address.id)

        # Invalidate caches for this address
        redis_cache.invalidate_lookup_cache(address_id=address.id)
        redis_cache.invalidate_stats_cache()

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
        from app.security import get_client_ip
        MetricsManager.record_request(
            db=db,
            endpoint='/report',
            method='POST',
            status_code=status_code,
            response_time_ms=response_time_ms,
            city=city,
            user_agent=request.headers.get('user-agent'),
            ip_address=get_client_ip(request)
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
        from app.security import get_client_ip
        MetricsManager.record_request(
            db=db,
            endpoint='/report',
            method='POST',
            status_code=status_code,
            response_time_ms=response_time_ms,
            city=city,
            error_message=error_msg,
            user_agent=request.headers.get('user-agent'),
            ip_address=get_client_ip(request)
        )
        raise
    except Exception as e:
        # Log unexpected errors
        error_logger.error(f"Report submission error: {str(e)}", exc_info=True)
        response_time_ms = (time.time() - start_time) * 1000
        from app.security import get_client_ip
        MetricsManager.record_request(
            db=db,
            endpoint='/report',
            method='POST',
            status_code=500,
            response_time_ms=response_time_ms,
            city=city,
            error_message=str(e),
            user_agent=request.headers.get('user-agent'),
            ip_address=get_client_ip(request)
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

        # Check Redis cache first
        cache_key = redis_cache._generate_key(
            "lookup",
            address=address,
            lat=lat,
            lon=lon,
            city_id=city_id
        )
        cached_response = redis_cache.get(cache_key)
        if cached_response:
            app_logger.info(f"Cache hit for lookup: {address or f'({lat},{lon})'}")
            return LookupResponse(**cached_response)

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

        # Step 7: Cache the response
        redis_cache.set(cache_key, response.model_dump(), ttl=300)  # 5 minutes

        # Step 8: Record metrics
        response_time_ms = (time.time() - start_time) * 1000
        from app.security import get_client_ip
        MetricsManager.record_request(
            db=db,
            endpoint='/lookup',
            method='GET',
            status_code=status_code,
            response_time_ms=response_time_ms,
            city=addr_record.city if addr_record else city_name,
            user_agent=request.headers.get('user-agent') if request else None,
            ip_address=get_client_ip(request) if request else None
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        error_logger.error(f"Lookup error: {str(e)}", exc_info=True)
        response_time_ms = (time.time() - start_time) * 1000
        from app.security import get_client_ip
        MetricsManager.record_request(
            db=db,
            endpoint='/lookup',
            method='GET',
            status_code=500,
            response_time_ms=response_time_ms,
            city=city_name,
            error_message=str(e),
            user_agent=request.headers.get('user-agent') if request else None,
            ip_address=get_client_ip(request) if request else None
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
    """Get statistics about the database and cache performance."""
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
            from app.security import get_client_ip
            MetricsManager.record_request(
                db=db,
                endpoint='/interpret-address',
                method='POST',
                status_code=status_code,
                response_time_ms=response_time_ms,
                city=city_name,
                error_message=error_msg,
                user_agent=request.headers.get('user-agent'),
                ip_address=get_client_ip(request)
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
        from app.security import get_client_ip
        MetricsManager.record_request(
            db=db,
            endpoint='/interpret-address',
            method='POST',
            status_code=status_code,
            response_time_ms=response_time_ms,
            city=city,
            user_agent=request.headers.get('user-agent'),
            ip_address=get_client_ip(request)
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
        from app.security import get_client_ip
        MetricsManager.record_request(
            db=db,
            endpoint='/interpret-address',
            method='POST',
            status_code=500,
            response_time_ms=response_time_ms,
            city=city_name,
            error_message=str(e),
            user_agent=request.headers.get('user-agent'),
            ip_address=get_client_ip(request)
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

    # Get cache statistics
    cache_manager = get_cache_manager()
    cache_stats = cache_manager.get_stats()

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
        ],
        "cache_stats": redis_cache.get_stats(),
        "ai_cache_stats": cache_stats
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
@app.get("/analytics/heatmap", response_model=HeatmapResponse)
async def get_heatmap_data(
    metric: str = "report_density",
    city: Optional[str] = None,
    limit: int = 1000,
    db: Session = Depends(get_db)
):
    """
    Get heatmap data for visualization in admin dashboard.

    Supported metrics:
    - report_density: Shows areas with high concentration of crowdsourced reports
    - low_confidence: Shows areas with low consensus agreement (potential issues)
    - high_activity: Shows addresses with most recent reporting activity

    Args:
        metric: Type of heatmap to generate
        city: Optional city filter
        limit: Maximum number of points to return (default 1000)
        db: Database session

    Returns:
        HeatmapResponse with coordinate points and intensity values
    """
    from sqlalchemy import func

    app_logger.info(f"Generating heatmap: metric={metric}, city={city}, limit={limit}")

    points = []
    max_intensity = 0.0
    min_intensity = 1.0

    try:
        if metric == "report_density":
            # Count reports per address location
            query = db.query(
                Address.lat,
                Address.lon,
                Address.normalized_address,
                Address.city_name,
                func.count(CrowdReport.id).label('report_count')
            ).join(
                CrowdReport, Address.id == CrowdReport.address_id
            ).filter(
                Address.lat.isnot(None),
                Address.lon.isnot(None)
            )

            if city:
                query = query.filter(Address.city_name.ilike(f"%{city}%"))

            query = query.group_by(
                Address.id,
                Address.lat,
                Address.lon,
                Address.normalized_address,
                Address.city_name
            ).order_by(
                func.count(CrowdReport.id).desc()
            ).limit(limit)

            results = query.all()

            # Normalize intensities
            if results:
                max_count = max(r.report_count for r in results)
                min_count = min(r.report_count for r in results)
                count_range = max_count - min_count if max_count > min_count else 1

                for row in results:
                    intensity = (row.report_count - min_count) / count_range if count_range > 0 else 0.5
                    points.append(HeatmapPoint(
                        lat=row.lat,
                        lon=row.lon,
                        intensity=intensity,
                        count=row.report_count,
                        details={
                            "address": row.normalized_address,
                            "city": row.city_name,
                            "metric_type": "report_count"
                        }
                    ))
                    max_intensity = max(max_intensity, intensity)
                    min_intensity = min(min_intensity, intensity)

        elif metric == "low_confidence":
            # Show areas with low agreement ratios (potential problems)
            query = db.query(
                Address.lat,
                Address.lon,
                Address.normalized_address,
                Address.city_name,
                CrowdConsensus.trash_agreement_ratio,
                CrowdConsensus.recycling_agreement_ratio,
                CrowdConsensus.total_reports
            ).join(
                CrowdConsensus, Address.id == CrowdConsensus.address_id
            ).filter(
                Address.lat.isnot(None),
                Address.lon.isnot(None),
                CrowdConsensus.total_reports >= 2  # Only show where there are multiple reports
            )

            if city:
                query = query.filter(Address.city_name.ilike(f"%{city}%"))

            query = query.limit(limit)
            results = query.all()

            for row in results:
                # Calculate average disagreement (inverse of agreement)
                ratios = [r for r in [row.trash_agreement_ratio, row.recycling_agreement_ratio] if r > 0]
                avg_agreement = sum(ratios) / len(ratios) if ratios else 0.5
                disagreement = 1.0 - avg_agreement  # Higher disagreement = higher intensity

                points.append(HeatmapPoint(
                    lat=row.lat,
                    lon=row.lon,
                    intensity=disagreement,
                    count=row.total_reports,
                    details={
                        "address": row.normalized_address,
                        "city": row.city_name,
                        "agreement_ratio": round(avg_agreement, 2),
                        "metric_type": "disagreement"
                    }
                ))
                max_intensity = max(max_intensity, disagreement)
                min_intensity = min(min_intensity, disagreement)

        elif metric == "high_activity":
            # Show addresses with most recent activity
            query = db.query(
                Address.lat,
                Address.lon,
                Address.normalized_address,
                Address.city_name,
                func.count(CrowdReport.id).label('report_count'),
                func.max(CrowdReport.created_at).label('latest_report')
            ).join(
                CrowdReport, Address.id == CrowdReport.address_id
            ).filter(
                Address.lat.isnot(None),
                Address.lon.isnot(None)
            )

            if city:
                query = query.filter(Address.city_name.ilike(f"%{city}%"))

            # Filter to last 30 days
            thirty_days_ago = datetime.now() - timedelta(days=30)
            query = query.filter(CrowdReport.created_at >= thirty_days_ago)

            query = query.group_by(
                Address.id,
                Address.lat,
                Address.lon,
                Address.normalized_address,
                Address.city_name
            ).order_by(
                func.count(CrowdReport.id).desc()
            ).limit(limit)

            results = query.all()

            if results:
                max_count = max(r.report_count for r in results)
                min_count = min(r.report_count for r in results)
                count_range = max_count - min_count if max_count > min_count else 1

                for row in results:
                    intensity = (row.report_count - min_count) / count_range if count_range > 0 else 0.5
                    points.append(HeatmapPoint(
                        lat=row.lat,
                        lon=row.lon,
                        intensity=intensity,
                        count=row.report_count,
                        details={
                            "address": row.normalized_address,
                            "city": row.city_name,
                            "latest_report": row.latest_report.isoformat() if row.latest_report else None,
                            "metric_type": "recent_activity"
                        }
                    ))
                    max_intensity = max(max_intensity, intensity)
                    min_intensity = min(min_intensity, intensity)

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid metric '{metric}'. Supported: report_density, low_confidence, high_activity"
            )

        app_logger.info(f"Heatmap generated: {len(points)} points")

        return HeatmapResponse(
            metric=metric,
            city=city,
            points=points,
            total_points=len(points),
            max_intensity=max_intensity if points else 0.0,
            min_intensity=min_intensity if points else 0.0,
            generated_at=datetime.now().isoformat()
        )

    except HTTPException:
        raise
    except Exception as e:
        error_logger.error(f"Heatmap generation error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate heatmap data")
# ============================================================================
# GAMIFICATION ENDPOINTS
# ============================================================================


@app.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    limit: int = 100,
    offset: int = 0,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Get the leaderboard showing top users by points.

    Args:
        limit: Maximum number of entries to return (default: 100)
        offset: Offset for pagination (default: 0)
        user_id: Optional user ID to include current user's rank
        db: Database session

    Returns:
        LeaderboardResponse with ranked users
    """
    try:
        leaderboard, total_users = GamificationService.get_leaderboard(
            db=db,
            limit=limit,
            offset=offset
        )

        current_user_rank = None
        if user_id:
            current_user_rank = GamificationService.get_user_rank(db, user_id)

        return LeaderboardResponse(
            leaderboard=leaderboard,
            total_users=total_users,
            current_user_rank=current_user_rank
        )
    except Exception as e:
        error_logger.error(f"Leaderboard error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/users/{user_id}/stats", response_model=UserStatsResponse)
async def get_user_stats(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Get detailed statistics for a specific user.

    Args:
        user_id: User ID
        db: Database session

    Returns:
        UserStatsResponse with user stats and badges
    """
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        badges = GamificationService.get_user_badges(db, user_id)
        recent_points = GamificationService.get_recent_point_history(db, user_id)
        rank = GamificationService.get_user_rank(db, user_id)

        return UserStatsResponse(
            user_id=user.id,
            username=user.username,
            email=user.email,
            total_points=user.total_points or 0,
            total_reports=user.total_reports or 0,
            verified_reports=user.verified_reports or 0,
            is_verified_reporter=user.is_verified_reporter or False,
            badges=badges,
            recent_points=recent_points,
            rank=rank
        )
    except HTTPException:
        raise
    except Exception as e:
        error_logger.error(f"User stats error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/badges")
async def get_all_badges(db: Session = Depends(get_db)):
    """
    Get all available badges.

    Returns:
        List of all badge definitions
    """
    try:
        badges = db.query(Badge).all()
        return {
            "badges": [
                {
                    "id": badge.id,
                    "slug": badge.slug,
                    "name": badge.name,
                    "description": badge.description,
                    "icon": badge.icon,
                    "color": badge.color,
                    "tier": badge.tier,
                    "requirement_type": badge.requirement_type,
                    "requirement_value": badge.requirement_value
                }
                for badge in badges
            ]
        }
    except Exception as e:
        error_logger.error(f"Get badges error: {str(e)}", exc_info=True)
    # Cache the stats for 60 seconds (shorter TTL since stats change frequently)
    redis_cache.set(cache_key, stats, ttl=60)

    return stats


@app.post("/predict", response_model=PredictResponse)
async def predict(
    request_data: PredictRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Make predictions about pickup patterns.

    Supports two prediction types:
    1. 'delay' - Predict likelihood of pickup delays for a specific address
    2. 'seasonal' - Predict report volume patterns for upcoming weeks

    Args:
        request_data: Prediction request with type and parameters
    """
    prediction_service = PredictionService(db)

    if request_data.prediction_type == "delay":
        if request_data.address_id is None:
            return PredictResponse(
                prediction_type="delay",
                delay=DelayPrediction(
                    success=False,
                    message="address_id is required for delay predictions"
                )
            )

        result = prediction_service.predict_delay(request_data.address_id)
        return PredictResponse(
            prediction_type="delay",
            delay=DelayPrediction(
                success=result.get('success', False),
                address_id=result.get('address_id'),
                delay_likely=result.get('delay_likely'),
                delay_probability=result.get('delay_probability'),
                confidence=result.get('confidence'),
                message=result.get('message')
            )
        )

    elif request_data.prediction_type == "seasonal":
        weeks = request_data.weeks_ahead or 4
        result = prediction_service.predict_seasonal_volume(weeks_ahead=weeks)

        seasonal_predictions = None
        if result.get('success') and result.get('predictions'):
            seasonal_predictions = [
                SeasonalPrediction(
                    week=p['week'],
                    month=p['month'],
                    date=p['date'],
                    predicted_reports=p['predicted_reports']
                )
                for p in result['predictions']
            ]

        return PredictResponse(
            prediction_type="seasonal",
            seasonal=SeasonalPredictionResponse(
                success=result.get('success', False),
                predictions=seasonal_predictions,
                message=result.get('message')
            )
        )

    return PredictResponse(
        prediction_type=request_data.prediction_type,
        delay=None,
        seasonal=None
    )


# ============================================================================
# PIPELINE STATUS ENDPOINTS
# ============================================================================

@app.get("/pipeline/runs")
async def get_pipeline_runs(
    status: Optional[str] = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    Get list of pipeline runs with optional status filter.

    Args:
        status: Filter by status (pending, running, completed, failed, paused)
        limit: Maximum number of runs to return
        db: Database session

    Returns:
        List of pipeline runs with summary information
    """
    query = db.query(PipelineRun)

    if status:
        query = query.filter(PipelineRun.status == status)

    runs = query.order_by(PipelineRun.started_at.desc()).limit(limit).all()

    results = []
    for run in runs:
        # Calculate progress
        progress_pct = 0
        if run.total_cities > 0:
            progress_pct = round((run.completed_cities / run.total_cities) * 100, 1)

        # Calculate duration
        duration_seconds = None
        if run.completed_at and run.started_at:
            duration_seconds = (run.completed_at - run.started_at).total_seconds()
        elif run.started_at:
            duration_seconds = (datetime.utcnow() - run.started_at).total_seconds()

        results.append({
            "id": run.id,
            "run_type": run.run_type,
            "status": run.status,
            "city_filter": run.city_filter,
            "total_cities": run.total_cities,
            "completed_cities": run.completed_cities,
            "failed_cities": run.failed_cities,
            "progress_percent": progress_pct,
            "total_addresses_fetched": run.total_addresses_fetched,
            "total_addresses_processed": run.total_addresses_processed,
            "error_count": run.error_count,
            "last_error": run.last_error,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "duration_seconds": duration_seconds
        })

    return {
        "runs": results,
        "count": len(results)
    }


@app.get("/pipeline/runs/{run_id}")
async def get_pipeline_run_detail(
    run_id: int,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific pipeline run.

    Args:
        run_id: Pipeline run ID
        db: Database session

    Returns:
        Detailed run information including per-city status
    """
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()

    if not run:
        raise HTTPException(status_code=404, detail=f"Pipeline run {run_id} not found")

    # Get all city statuses
    city_statuses = db.query(PipelineCityStatus).filter(
        PipelineCityStatus.pipeline_run_id == run_id
    ).order_by(PipelineCityStatus.city_name).all()

    # Calculate progress
    progress_pct = 0
    if run.total_cities > 0:
        progress_pct = round((run.completed_cities / run.total_cities) * 100, 1)

    # Calculate duration
    duration_seconds = None
    if run.completed_at and run.started_at:
        duration_seconds = (run.completed_at - run.started_at).total_seconds()
    elif run.started_at:
        duration_seconds = (datetime.utcnow() - run.started_at).total_seconds()

    # Build city status list
    cities = []
    for city_status in city_statuses:
        city_duration = None
        if city_status.completed_at and city_status.started_at:
            city_duration = (city_status.completed_at - city_status.started_at).total_seconds()

        cities.append({
            "city_id": city_status.city_id,
            "city_name": city_status.city_name,
            "status": city_status.status,
            "current_step": city_status.current_step,
            "steps_completed": city_status.steps_completed or [],
            "addresses_fetched": city_status.addresses_fetched,
            "addresses_sampled": city_status.addresses_sampled,
            "addresses_normalized": city_status.addresses_normalized,
            "error_message": city_status.error_message,
            "retry_count": city_status.retry_count,
            "started_at": city_status.started_at.isoformat() if city_status.started_at else None,
            "completed_at": city_status.completed_at.isoformat() if city_status.completed_at else None,
            "duration_seconds": city_duration
        })

    return {
        "run": {
            "id": run.id,
            "run_type": run.run_type,
            "status": run.status,
            "city_filter": run.city_filter,
            "total_cities": run.total_cities,
            "completed_cities": run.completed_cities,
            "failed_cities": run.failed_cities,
            "progress_percent": progress_pct,
            "total_addresses_fetched": run.total_addresses_fetched,
            "total_addresses_processed": run.total_addresses_processed,
            "error_count": run.error_count,
            "last_error": run.last_error,
            "last_processed_city_id": run.last_processed_city_id,
            "checkpoint_data": run.checkpoint_data,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "duration_seconds": duration_seconds
        },
        "cities": cities
    }


@app.get("/pipeline/status")
async def get_current_pipeline_status(db: Session = Depends(get_db)):
    """
    Get status of currently running or most recent pipeline runs.

    Returns:
        Summary of active and recent pipeline runs
    """
    # Get currently running pipeline
    active_run = db.query(PipelineRun).filter(
        PipelineRun.status == "running"
    ).order_by(PipelineRun.started_at.desc()).first()

    # Get most recent completed run
    recent_run = db.query(PipelineRun).filter(
        PipelineRun.status.in_(["completed", "failed"])
    ).order_by(PipelineRun.completed_at.desc()).first()

    result = {
        "has_active_run": active_run is not None,
        "active_run": None,
        "recent_run": None
    }

    if active_run:
        progress_pct = 0
        if active_run.total_cities > 0:
            progress_pct = round((active_run.completed_cities / active_run.total_cities) * 100, 1)

        duration_seconds = None
        if active_run.started_at:
            duration_seconds = (datetime.utcnow() - active_run.started_at).total_seconds()

        result["active_run"] = {
            "id": active_run.id,
            "run_type": active_run.run_type,
            "status": active_run.status,
            "city_filter": active_run.city_filter,
            "total_cities": active_run.total_cities,
            "completed_cities": active_run.completed_cities,
            "failed_cities": active_run.failed_cities,
            "progress_percent": progress_pct,
            "total_addresses_fetched": active_run.total_addresses_fetched,
            "started_at": active_run.started_at.isoformat() if active_run.started_at else None,
            "duration_seconds": duration_seconds
        }

    if recent_run:
        progress_pct = 0
        if recent_run.total_cities > 0:
            progress_pct = round((recent_run.completed_cities / recent_run.total_cities) * 100, 1)

        duration_seconds = None
        if recent_run.completed_at and recent_run.started_at:
            duration_seconds = (recent_run.completed_at - recent_run.started_at).total_seconds()

        result["recent_run"] = {
            "id": recent_run.id,
            "run_type": recent_run.run_type,
            "status": recent_run.status,
            "city_filter": recent_run.city_filter,
            "total_cities": recent_run.total_cities,
            "completed_cities": recent_run.completed_cities,
            "failed_cities": recent_run.failed_cities,
            "progress_percent": progress_pct,
            "total_addresses_fetched": recent_run.total_addresses_fetched,
            "started_at": recent_run.started_at.isoformat() if recent_run.started_at else None,
            "completed_at": recent_run.completed_at.isoformat() if recent_run.completed_at else None,
            "duration_seconds": duration_seconds
        }

    return result

@app.get("/optimize-route", response_model=OptimizeRouteResponse)
async def optimize_route(
    city_id: str,
    max_stops: Optional[int] = None,
    use_time_windows: bool = False,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Optimize trash collection route for a city.

    This endpoint:
    1. Retrieves all addresses for the specified city
    2. Uses OR-Tools to optimize the collection route
    3. Returns the optimized route order with statistics

    Args:
        city_id: City identifier (e.g., 'san_diego', 'el_centro')
        max_stops: Maximum number of stops to include (optional)
        use_time_windows: Enable time window constraints (optional, experimental)
        request: FastAPI request object
        db: Database session

    Returns:
        PredictResponse with prediction results
    """
    start_time = time.time()
    status_code = 200
    error_msg = None

    try:
        prediction_service = PredictionService(db)

        if request_data.prediction_type == 'delay':
            # Delay prediction for specific address
            app_logger.info(f"Predicting delays for address_id={request_data.address_id}")
            result = prediction_service.predict_delay(request_data.address_id)

            delay_prediction = DelayPrediction(**result)

            response_time_ms = (time.time() - start_time) * 1000
            MetricsManager.record_request(
                db=db,
                endpoint='/predict',
                method='POST',
                status_code=status_code,
                response_time_ms=response_time_ms,
                user_agent=request.headers.get('user-agent'),
                ip_address=request.client.host if request.client else None
            )

            return PredictResponse(
                prediction_type='delay',
                delay=delay_prediction
            )

        elif request_data.prediction_type == 'seasonal':
            # Seasonal pattern prediction
            app_logger.info(f"Predicting seasonal patterns for {request_data.weeks_ahead} weeks")
            result = prediction_service.predict_seasonal_volume(request_data.weeks_ahead)

            if result['success']:
                predictions = [
                    SeasonalPrediction(**pred) for pred in result['predictions']
                ]
                seasonal_response = SeasonalPredictionResponse(
                    success=True,
                    predictions=predictions
                )
            else:
                seasonal_response = SeasonalPredictionResponse(
                    success=False,
                    message=result.get('message', 'Seasonal prediction failed')
                )

            response_time_ms = (time.time() - start_time) * 1000
            MetricsManager.record_request(
                db=db,
                endpoint='/predict',
                method='POST',
                status_code=status_code,
                response_time_ms=response_time_ms,
                user_agent=request.headers.get('user-agent'),
                ip_address=request.client.host if request.client else None
            )

            return PredictResponse(
                prediction_type='seasonal',
                seasonal=seasonal_response
            )

    except HTTPException:
        raise
    except Exception as e:
        error_logger.error(f"Prediction error: {str(e)}", exc_info=True)
        response_time_ms = (time.time() - start_time) * 1000
        MetricsManager.record_request(
            db=db,
            endpoint='/predict',
            method='POST',
            status_code=500,
            response_time_ms=response_time_ms,
            error_message=str(e),
            user_agent=request.headers.get('user-agent'),
            ip_address=request.client.host if request.client else None
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/predict/train", response_model=TrainModelResponse)
async def train_models(
    request_data: TrainModelRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Train prediction models on crowdsourced data.

    This endpoint trains ML models using historical crowd reports.
    Models are stored in the database and can be used for predictions.

    Args:
        request_data: Training request specifying which models to train
        request: FastAPI request object
        db: Database session

    Returns:
        TrainModelResponse with training results
    """
    start_time = time.time()
    status_code = 200

    try:
        prediction_service = PredictionService(db)
        results = []

        if request_data.model_type in ['delay', 'both']:
            app_logger.info("Training delay prediction model")
            delay_result = prediction_service.train_delay_model()
            results.append(delay_result)

        if request_data.model_type in ['seasonal', 'both']:
            app_logger.info("Training seasonal prediction model")
            seasonal_result = prediction_service.train_seasonal_model()
            results.append(seasonal_result)

        success = all(r.get('success', False) for r in results)
        message = "Models trained successfully" if success else "Some models failed to train"

        response_time_ms = (time.time() - start_time) * 1000
        MetricsManager.record_request(
            db=db,
            endpoint='/predict/train',
            method='POST',
            status_code=status_code,
            response_time_ms=response_time_ms,
            user_agent=request.headers.get('user-agent'),
            ip_address=request.client.host if request.client else None
        )

        return TrainModelResponse(
            success=success,
            results=results,
            message=message
        )

    except HTTPException:
        raise
    except Exception as e:
        error_logger.error(f"Model training error: {str(e)}", exc_info=True)
        response_time_ms = (time.time() - start_time) * 1000
        MetricsManager.record_request(
            db=db,
            endpoint='/predict/train',
            method='POST',
            status_code=500,
            response_time_ms=response_time_ms,
            error_message=str(e),
            user_agent=request.headers.get('user-agent'),
            ip_address=request.client.host if request.client else None
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/routing/optimize", response_model=OptimizeRouteResponse)
async def optimize_route(
    city_id: str,
    max_stops: Optional[int] = None,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Optimize collection route for a city using OR-Tools.

    Args:
        city_id: City identifier
        max_stops: Maximum number of stops to include (optional)
        request: FastAPI request object
        db: Database session

    Returns:
        OptimizeRouteResponse with optimized route and statistics
    """
    start_time = time.time()
    status_code = 200

    try:
        # Validate city_id
        city_id_normalized = city_id.strip().lower()

        app_logger.info(f"Optimizing route for city: {city_id_normalized}, max_stops: {max_stops}")

        # Query addresses for the city
        query = db.query(Address).filter(
            Address.city_id == city_id_normalized,
            Address.lat.isnot(None),
            Address.lon.isnot(None)
        )

        # Apply max_stops limit if specified
        if max_stops and max_stops > 0:
            query = query.limit(max_stops)

        addresses = query.all()

        if not addresses:
            app_logger.warning(f"No addresses found for city: {city_id_normalized}")
            raise HTTPException(
                status_code=404,
                detail=f"No addresses found for city '{city_id_normalized}'"
            )

        if len(addresses) < 2:
            app_logger.warning(f"Need at least 2 addresses for optimization, found {len(addresses)}")
            raise HTTPException(
                status_code=400,
                detail=f"Need at least 2 addresses to optimize route, found {len(addresses)}"
            )

        # Extract coordinates and metadata
        coordinates = [(addr.lat, addr.lon) for addr in addresses]
        address_ids = [addr.id for addr in addresses]
        address_strings = [addr.normalized_address for addr in addresses]

        app_logger.info(f"Optimizing route for {len(coordinates)} addresses")

        # Initialize optimizer and run optimization
        optimizer = RouteOptimizer()
        result = optimizer.optimize(
            coordinates=coordinates,
            depot_index=0,
            use_time_windows=use_time_windows,
            time_limit_seconds=30
        )

        if not result["success"]:
            app_logger.error(f"Optimization failed: {result['message']}")
            raise HTTPException(
                status_code=500,
                detail=f"Optimization failed: {result['message']}"
            )

        # Create route stops
        route_stops = optimizer.create_route_stops(
            coordinates=coordinates,
            optimized_order=result["optimized_order"],
            address_ids=address_ids,
            addresses=address_strings
        )

        # Calculate distance reduction
        distance_reduction = optimizer.calculate_distance_reduction(
            coordinates=coordinates,
            optimized_distance_km=result["total_distance_km"]
        )

        # Build statistics
        statistics = RouteStatistics(
            total_distance_km=result["total_distance_km"],
            total_distance_miles=result["total_distance_miles"],
            total_stops=len(route_stops),
            distance_reduction_percent=distance_reduction
        )

        # Prepare heatmap data (just the coordinates in optimized order)
        heatmap_data = [
            (stop.lat, stop.lon) for stop in route_stops
        ]

        app_logger.info(
            f"Route optimized: {len(route_stops)} stops, "
            f"{result['total_distance_km']:.2f} km, "
            f"{distance_reduction:.1f}% reduction"
        )

        # Record metrics
        response_time_ms = (time.time() - start_time) * 1000
        MetricsManager.record_request(
            db=db,
            endpoint='/optimize-route',
            method='POST',
            status_code=status_code,
            response_time_ms=response_time_ms,
            city=city_id_normalized
        )

        return OptimizeRouteResponse(
            success=True,
            route=route_stops,
            statistics=result
        )

    except HTTPException:
        raise
    except Exception as e:
        error_logger.error(f"Route optimization error: {str(e)}", exc_info=True)
        response_time_ms = (time.time() - start_time) * 1000
        MetricsManager.record_request(
            db=db,
            endpoint='/optimize-route',
            method='POST',
            status_code=500,
            response_time_ms=response_time_ms,
            error_message=str(e),
            city=city_id_normalized
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/ai-classify", response_model=AIClassifierResponse)
async def ai_classify(
    request_data: AIClassifierRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    AI-powered natural language schedule classifier.

    Converts messy natural language text describing trash pickup schedules
    into structured schedule objects with normalized data.

    Features:
    - Extracts pickup_day (MON, TUE, WED, etc.)
    - Extracts frequency (weekly, biweekly, monthly)
    - Extracts exceptions (holidays, special dates)
    - Integrates with existing normalization
    - Caches results for common phrases

    Example input texts:
    - "Trash pickup is every Monday"
    - "Recycling on Wednesdays every other week"
    - "Garbage collection Thursday mornings, no pickup on Christmas"
    - "I think it's Tuesday or maybe Wednesday for trash"

    Returns:
        AIClassifierResponse with structured schedule data
    """
    start_time = time.time()

    try:
        # Check rate limit
        client_ip = request.client.host if request.client else "unknown"
        if not rate_limiter.check_rate_limit(client_ip, "ai-classify"):
            app_logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later."
            )

        # Get cache manager
        cache_manager = get_cache_manager()

        # Check cache first
        cached_result = cache_manager.get(request_data.text, db)
        if cached_result:
            response_time_ms = (time.time() - start_time) * 1000
            app_logger.info(
                f"AI classify cache hit: '{request_data.text[:50]}...' "
                f"({response_time_ms:.2f}ms)"
            )

            # Record metrics
            MetricsManager.record_request(
                db=db,
                endpoint='/ai-classify',
                method='POST',
                status_code=200,
                response_time_ms=response_time_ms,
                user_agent=request.headers.get('user-agent') if request else None,
                ip_address=client_ip
            )

            return AIClassifierResponse(
                schedules=cached_result,
                success=True,
                cached=True
            )

        # Classify using AI
        app_logger.info(f"AI classify request: '{request_data.text[:100]}...'")

        classified_schedules = classify_schedule_text(
            text=request_data.text,
            context=request_data.context
        )

        # Convert to dict format
        schedules_dict = [schedule.to_dict() for schedule in classified_schedules]

        # Store in cache
        cache_manager.set(request_data.text, schedules_dict, db)

        response_time_ms = (time.time() - start_time) * 1000
        app_logger.info(
            f"AI classify success: '{request_data.text[:50]}...' "
            f"-> {len(schedules_dict)} schedule(s) ({response_time_ms:.2f}ms)"
        )

        # Record metrics
        MetricsManager.record_request(
            db=db,
            endpoint='/ai-classify',
            method='POST',
            status_code=200,
            response_time_ms=response_time_ms,
            user_agent=request.headers.get('user-agent') if request else None,
            ip_address=client_ip
        )

        return AIClassifierResponse(
            schedules=schedules_dict,
            success=True,
            cached=False
        )

    except ValueError as e:
        # API key not configured
        error_msg = str(e)
        error_logger.error(f"AI classify configuration error: {error_msg}")
        response_time_ms = (time.time() - start_time) * 1000

        MetricsManager.record_request(
            db=db,
            endpoint='/ai-classify',
            method='POST',
            status_code=503,
            response_time_ms=response_time_ms,
            error_message=error_msg,
            user_agent=request.headers.get('user-agent') if request else None,
            ip_address=request.client.host if request and request.client else None
        )

        return OptimizeRouteResponse(
            success=True,
            message=f"Route optimized successfully for {city_id_normalized}",
            city_id=city_id_normalized,
            optimized_route=route_stops,
            statistics=statistics,
            heatmap_data=heatmap_data
        )

    except HTTPException:
        raise
    except Exception as e:
        error_logger.error(f"Route optimization error: {str(e)}", exc_info=True)
        response_time_ms = (time.time() - start_time) * 1000
        MetricsManager.record_request(
            db=db,
            endpoint='/optimize-route',
            method='GET',
            status_code=500,
            response_time_ms=response_time_ms,
            city=city_id,
            error_message=str(e),
            user_agent=request.headers.get('user-agent') if request else None,
            ip_address=request.client.host if request and request.client else None
        )
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="AI classification service not configured. Please set OPENAI_API_KEY."
        )

    except Exception as e:
        # Other errors
        error_msg = str(e)
        error_logger.error(f"AI classify error: {error_msg}", exc_info=True)
        response_time_ms = (time.time() - start_time) * 1000

        MetricsManager.record_request(
            db=db,
            endpoint='/ai-classify',
            method='POST',
            status_code=500,
            response_time_ms=response_time_ms,
            error_message=error_msg,
            user_agent=request.headers.get('user-agent') if request else None,
            ip_address=request.client.host if request and request.client else None
        )

        return AIClassifierResponse(
            schedules=[],
            success=False,
            error=f"Classification failed: {error_msg}",
            cached=False
        )


@app.get("/ai-classify/popular")
async def get_popular_phrases(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """
    Get most popular cached phrases.

    Returns the most frequently classified schedule phrases,
    useful for understanding common user inputs.

    Args:
        limit: Maximum number of phrases to return (default: 10)

    Returns:
        List of popular phrases with statistics
    """
    try:
        cache_manager = get_cache_manager()
        popular = cache_manager.get_popular_phrases(db, limit=limit)

        return {
            "popular_phrases": popular,
            "total_returned": len(popular)
        }
    except Exception as e:
        error_logger.error(f"Error getting popular phrases: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/ai-classify/cache/clear")
async def clear_ai_cache(
    cache_type: str = "memory",  # "memory", "db", or "all"
    db: Session = Depends(get_db)
):
    """
    Clear AI classification cache.

    Args:
        cache_type: Type of cache to clear ("memory", "db", or "all")

    Returns:
        Success message
    """
    try:
        cache_manager = get_cache_manager()

        if cache_type in ("memory", "all"):
            cache_manager.clear_memory_cache()

        if cache_type in ("db", "all"):
            cache_manager.clear_db_cache(db)

        app_logger.info(f"AI cache cleared: {cache_type}")

        return {
            "success": True,
            "message": f"Cache cleared: {cache_type}"
        }
    except Exception as e:
        error_logger.error(f"Error clearing cache: {e}")
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


@app.get("/predict/models")
async def get_model_info(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get information about currently active prediction models."""
    try:
        prediction_service = PredictionService(db)
        return prediction_service.get_model_info()
    except Exception as e:
        error_logger.error(f"Error fetching model info: {str(e)}", exc_info=True)
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
