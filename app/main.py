"""TrashAlert FastAPI application."""
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
from collections import defaultdict
import logging
import time

from app.database import get_db, engine, Base
from app.models import Address, CrowdReport, CrowdConsensus, RequestMetrics, PipelineRun, PipelineCityStatus
from app.schemas import ReportRequest, ReportResponse, LookupResponse, ConsensusInfo, ConsensusDetails
from app.utils import (
    normalize_address,
    find_or_create_address,
    find_address_by_coordinates,
    update_crowd_consensus,
    validate_day,
    day_abbrev_to_full,
    get_city_id_from_name,
    get_city_name_from_id
)
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
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "TrashAlert API",
        "version": "1.0.0",
        "endpoints": ["/lookup", "/report", "/stats"]
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


@app.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get statistics about the database."""
    from sqlalchemy import func, distinct

    """Get statistics about the database and cache performance."""
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

    return stats


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
