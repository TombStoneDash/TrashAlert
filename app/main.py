"""TrashAlert FastAPI application."""
from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Optional
import time

from app.database import get_db, engine, Base
from app.models import Address, CrowdReport, CrowdConsensus, RequestMetrics
from app.schemas import ReportRequest, ReportResponse, LookupResponse, ConsensusInfo
from app.utils import (
    normalize_address,
    find_or_create_address,
    update_crowd_consensus,
    validate_day
)
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
