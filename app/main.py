"""TrashAlert FastAPI application."""
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from typing import Optional
import logging
import time

from app.database import get_db, engine, Base
from app.models import Address, CrowdReport, CrowdConsensus
from app.schemas import ReportRequest, ReportResponse, LookupResponse, ConsensusInfo, ConsensusDetails
from app.models import Address, CrowdReport, CrowdConsensus, RequestMetrics
from app.schemas import ReportRequest, ReportResponse, LookupResponse, ConsensusInfo
from app.utils import (
    normalize_address,
    find_or_create_address,
    update_crowd_consensus,
    validate_day,
    day_abbrev_to_full
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

        response = ReportResponse(
            success=True,
            message="Report submitted successfully",
            address_id=address.id,
            normalized_address=address.normalized_address,
            consensus=consensus_info
        )

    # Find or create address
    address = find_or_create_address(db, report.address)

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

    # Invalidate cache for this address since data changed
    cache_key = f"lookup:{address.normalized_address}"
    lookup_cache.delete(cache_key)
    logger.debug(f"Cache invalidated for address: {address.normalized_address}")

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

        return response

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
    address: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Look up trash pickup schedule for an address.

    This endpoint merges data from multiple sources with priority:
    1. Verified crowdsourced consensus (if available and verified)
    2. Official GIS/rules data
    3. Unverified crowdsourced data (if no official data)

    Includes caching for improved performance (5-minute TTL).

    Args:
        address: Address to look up
        request: FastAPI request (for metrics)
        db: Database session

    Returns:
        Pickup schedule with source information
    """
    start_time = time.time()
    city = None
    status_code = 200
    error_msg = None

    try:
        # Validate input
        if not address or not address.strip():
            status_code = 400
            error_msg = "Address parameter is required and cannot be empty"
            raise HTTPException(status_code=status_code, detail=error_msg)

        # Normalize address to find it
        parts = normalize_address(address)
        normalized = parts['normalized_address']
        city = parts.get('city', None)

        app_logger.info(f"Lookup request: {address} -> Normalized: {normalized}, City: {city}")

        # Check if normalization produced valid result
        if not normalized or len(normalized) < 3:
            status_code = 400
            error_msg = f"Invalid address format: '{address}'"
            raise HTTPException(status_code=status_code, detail=error_msg)

        # Try to find address
        addr_record = db.query(Address).filter(
            Address.normalized_address == normalized
        ).first()

        if not addr_record:
            # Address not found - return UNKNOWN
            app_logger.warning(f"Address not found: {normalized}")
            response = LookupResponse(
                address=address,
                normalized_address=normalized,
                trash_day=None,
                recycling_day=None,
                green_day=None,
                source="UNKNOWN",
                consensus_reports_count=None,
                consensus_agreement_ratio=None,
                lat=None,
                lon=None
            )

            # Record metric
            response_time_ms = (time.time() - start_time) * 1000
            MetricsManager.record_request(
                db=db,
                endpoint='/lookup',
                method='GET',
                status_code=status_code,
                response_time_ms=response_time_ms,
                city=city,
                user_agent=request.headers.get('user-agent'),
                ip_address=request.client.host if request.client else None
            )

            return response

        # Get consensus data if available
        consensus = db.query(CrowdConsensus).filter(
            CrowdConsensus.address_id == addr_record.id
        ).first()

        # Determine source and data to return
        source = "UNKNOWN"
        trash_day = None
        recycling_day = None
        green_day = None
        reports_count = None
        agreement_ratio = None

        # Priority 1: Verified crowdsourced consensus
        if consensus and consensus.is_verified:
            source = "CROWD_VERIFIED"
            trash_day = consensus.consensus_trash_day
            recycling_day = consensus.consensus_recycling_day
            green_day = consensus.consensus_green_day
            reports_count = consensus.total_reports

            # Calculate overall agreement ratio
            ratios = [
                r for r in [
                    consensus.trash_agreement_ratio,
                    consensus.recycling_agreement_ratio,
                    consensus.green_agreement_ratio
                ] if r > 0
            ]
            agreement_ratio = sum(ratios) / len(ratios) if ratios else 0.0

        # Priority 2: Official data
        elif any([addr_record.official_trash_day,
                  addr_record.official_recycling_day,
                  addr_record.official_green_day]):
            source = "OFFICIAL"
            trash_day = addr_record.official_trash_day
            recycling_day = addr_record.official_recycling_day
            green_day = addr_record.official_green_day

        # Priority 3: Unverified crowdsourced (if exists)
        elif consensus:
            source = "CROWD_UNVERIFIED"
            trash_day = consensus.consensus_trash_day
            recycling_day = consensus.consensus_recycling_day
            green_day = consensus.consensus_green_day
            reports_count = consensus.total_reports

            ratios = [
                r for r in [
                    consensus.trash_agreement_ratio,
                    consensus.recycling_agreement_ratio,
                    consensus.green_agreement_ratio
                ] if r > 0
            ]
            agreement_ratio = sum(ratios) / len(ratios) if ratios else 0.0

        app_logger.info(f"Lookup result: {normalized} -> Source: {source}")

        response = LookupResponse(
            address=address,
            normalized_address=addr_record.normalized_address,
            trash_day=trash_day,
            recycling_day=recycling_day,
            green_day=green_day,
            source=source,
            consensus_reports_count=reports_count,
            consensus_agreement_ratio=agreement_ratio,
            lat=addr_record.lat,
            lon=addr_record.lon
        )

        # Record successful metric
        response_time_ms = (time.time() - start_time) * 1000
        MetricsManager.record_request(
            db=db,
            endpoint='/lookup',
            method='GET',
            status_code=status_code,
            response_time_ms=response_time_ms,
            city=city,
            user_agent=request.headers.get('user-agent'),
            ip_address=request.client.host if request.client else None
        )

    # Check cache first
    cache_key = f"lookup:{normalized}"
    cached_result = lookup_cache.get(cache_key)

    if cached_result:
        logger.debug(f"Cache hit for address: {normalized}")
        return LookupResponse(**cached_result)

    # Optimized query: Use LEFT JOIN to get address and consensus in one query
    from sqlalchemy.orm import joinedload

    addr_record = db.query(Address).filter(
        Address.normalized_address == normalized
    ).first()

    if not addr_record:
        # Address not found - return UNKNOWN
        return LookupResponse(
            matched_address=normalized,
            city_name=parts.get('city'),
            trash_day_of_week=None,
            recycling_day_of_week=None,
            green_waste_day_of_week=None,
            data_source="UNKNOWN",
            consensus_details=None
        )

    # Get consensus data if available (single query)
    consensus = db.query(CrowdConsensus).filter(
        CrowdConsensus.address_id == addr_record.id
    ).first()

    # Determine source and data to return
    data_source = "UNKNOWN"
    trash_day = None
    recycling_day = None
    green_day = None
    consensus_details = None

    # Priority 1: Verified crowdsourced consensus
    if consensus and consensus.is_verified:
        data_source = "CROWD_VERIFIED"
        trash_day = consensus.consensus_trash_day
        recycling_day = consensus.consensus_recycling_day
        green_day = consensus.consensus_green_day

        # Calculate overall agreement ratio
        ratios = [
            r for r in [
                consensus.trash_agreement_ratio,
                consensus.recycling_agreement_ratio,
                consensus.green_agreement_ratio
            ] if r > 0
        ]
        agreement_ratio = sum(ratios) / len(ratios) if ratios else 0.0

        consensus_details = ConsensusDetails(
            reports_count=consensus.total_reports,
            agreement_ratio=round(agreement_ratio, 2)
        )

    # Priority 2: Official data
    elif any([addr_record.official_trash_day,
              addr_record.official_recycling_day,
              addr_record.official_green_day]):
        data_source = "OFFICIAL"
        trash_day = addr_record.official_trash_day
        recycling_day = addr_record.official_recycling_day
        green_day = addr_record.official_green_day

    # Priority 3: Unverified crowdsourced (if exists)
    elif consensus:
        data_source = "CROWD_UNVERIFIED"
        trash_day = consensus.consensus_trash_day
        recycling_day = consensus.consensus_recycling_day
        green_day = consensus.consensus_green_day

        ratios = [
            r for r in [
                consensus.trash_agreement_ratio,
                consensus.recycling_agreement_ratio,
                consensus.green_agreement_ratio
            ] if r > 0
        ]
        agreement_ratio = sum(ratios) / len(ratios) if ratios else 0.0

        consensus_details = ConsensusDetails(
            reports_count=consensus.total_reports,
            agreement_ratio=round(agreement_ratio, 2)
        )

    # Convert day abbreviations to full names
    trash_day_full = day_abbrev_to_full(trash_day)
    recycling_day_full = day_abbrev_to_full(recycling_day)
    green_day_full = day_abbrev_to_full(green_day)

    return LookupResponse(
        matched_address=addr_record.normalized_address,
        city_name=addr_record.city,
        trash_day_of_week=trash_day_full,
        recycling_day_of_week=recycling_day_full,
        green_waste_day_of_week=green_day_full,
        data_source=data_source,
        consensus_details=consensus_details
    )
    # Build response
    response_data = {
        "address": address,
        "normalized_address": addr_record.normalized_address,
        "trash_day": trash_day,
        "recycling_day": recycling_day,
        "green_day": green_day,
        "source": source,
        "consensus_reports_count": reports_count,
        "consensus_agreement_ratio": agreement_ratio,
        "lat": addr_record.lat,
        "lon": addr_record.lon
    }

    # Cache the result for 5 minutes (300 seconds)
    lookup_cache.set(cache_key, response_data, ttl=300)

    return LookupResponse(**response_data)
        return response

    except HTTPException:
        # Re-raise HTTP exceptions (already logged)
        response_time_ms = (time.time() - start_time) * 1000
        MetricsManager.record_request(
            db=db,
            endpoint='/lookup',
            method='GET',
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
        error_logger.error(f"Lookup error for '{address}': {str(e)}", exc_info=True)
        response_time_ms = (time.time() - start_time) * 1000
        MetricsManager.record_request(
            db=db,
            endpoint='/lookup',
            method='GET',
            status_code=500,
            response_time_ms=response_time_ms,
            city=city,
            error_message=str(e),
            user_agent=request.headers.get('user-agent'),
            ip_address=request.client.host if request.client else None
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
    # Get cache statistics
    cache_stats = lookup_cache.get_stats()

    return {
        "database": {
            "total_addresses": total_addresses,
            "total_reports": total_reports,
            "total_consensus": total_consensus,
            "verified_consensus": verified_consensus
        },
        "cache": cache_stats
    """
    Get comprehensive statistics about the API and database.

    Returns:
        JSON object with:
        - api_metrics: Request counts, response times, error rates
        - lookup_by_city: Number of /lookup calls per city
        - report_by_city: Number of /report submissions per city
        - database_stats: Address, report, and consensus counts
        - endpoint_details: Detailed stats for each endpoint
    """
    app_logger.info("Stats endpoint requested")

    # Get comprehensive metrics from MetricsManager
    stats = MetricsManager.get_overall_stats(db)

    # Get detailed endpoint statistics
    lookup_details = MetricsManager.get_endpoint_stats(db, '/lookup')
    report_details = MetricsManager.get_endpoint_stats(db, '/report')

    stats['endpoint_details'] = {
        'lookup': lookup_details,
        'report': report_details
    }

    return stats
