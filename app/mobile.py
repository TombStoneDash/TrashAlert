"""Mobile-optimized endpoints with minimal payloads (<1kb)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import time

from app.database import get_db
from app.models import Address, CrowdReport, CrowdConsensus
from app.mobile_schemas import (
    MobileLookupResponse,
    MobileDailyScheduleResponse,
    MobileReportRequest,
    MobileReportResponse,
    MobileErrorResponse
)
from app.mobile_utils import (
    day_to_mobile_code,
    mobile_code_to_day,
    source_to_mobile_code,
    get_next_weekday,
    is_pickup_today
)
from app.utils import (
    normalize_address,
    find_or_create_address,
    find_address_by_coordinates,
    update_crowd_consensus,
    validate_day,
    get_city_id_from_name
)
from app.metrics import MetricsManager
from app.logging_config import app_logger, error_logger

# Create mobile router
router = APIRouter(prefix="/mobile", tags=["mobile"])


@router.get("/lookup", response_model=MobileLookupResponse)
async def mobile_lookup(
    address: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    city_id: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Mobile-optimized lookup endpoint with minimal payload.

    Payload size: <500 bytes typical

    Uses abbreviated field names and single-letter codes:
    - Day codes: M/T/W/R/F/S/U (Mon/Tue/Wed/Thu/Fri/Sat/Sun)
    - Source codes: V/O/U/X (Verified/Official/Unverified/Unknown)

    Args:
        address: Full address string (optional)
        lat: Latitude (optional, requires lon)
        lon: Longitude (optional, requires lat)
        city_id: City identifier (optional)
        request: Request object
        db: Database session

    Returns:
        MobileLookupResponse with minimal fields
    """
    start_time = time.time()
    city_name = None
    status_code = 200

    try:
        # Validate input
        has_address = bool(address and address.strip())
        has_coords = lat is not None and lon is not None

        if not has_address and not has_coords:
            raise HTTPException(
                status_code=400,
                detail="Must provide 'address' or both 'lat' and 'lon'"
            )

        # Find address record
        addr_record = None

        if has_coords:
            app_logger.info(f"Mobile lookup by coords: ({lat}, {lon})")
            addr_record = find_address_by_coordinates(
                db=db,
                lat=lat,
                lon=lon,
                max_distance_meters=50,
                city_id=city_id
            )
        elif has_address:
            parts = normalize_address(address)
            normalized = parts['normalized_address']
            city_name = parts.get('city')

            if not city_id and city_name:
                city_id = get_city_id_from_name(city_name)

            app_logger.info(f"Mobile lookup by address: {normalized}")

            query = db.query(Address).filter(
                Address.normalized_address == normalized
            )
            if city_id:
                query = query.filter(Address.city_id == city_id)

            addr_record = query.first()

        # Return unknown if not found
        if not addr_record:
            return MobileLookupResponse(
                addr=address or f"({lat}, {lon})",
                c=city_id,
                lat=lat,
                lon=lon,
                t=None,
                r=None,
                g=None,
                src='X'
            )

        # Get consensus data
        consensus = db.query(CrowdConsensus).filter(
            CrowdConsensus.address_id == addr_record.id
        ).first()

        # Apply source priority
        data_source = "UNKNOWN"
        trash_day = None
        recycling_day = None
        green_day = None
        consensus_reports_count = None
        consensus_agreement_ratio = None

        # Priority 1: CROWD_VERIFIED
        if consensus and consensus.is_verified:
            data_source = "CROWD_VERIFIED"
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

        # Convert to mobile codes
        response = MobileLookupResponse(
            addr=addr_record.normalized_address,
            c=addr_record.city_id,
            lat=addr_record.lat,
            lon=addr_record.lon,
            t=day_to_mobile_code(trash_day),
            r=day_to_mobile_code(recycling_day),
            g=day_to_mobile_code(green_day),
            src=source_to_mobile_code(data_source),
            cnt=consensus_reports_count,
            agr=consensus_agreement_ratio
        )

        # Record metrics
        response_time_ms = (time.time() - start_time) * 1000
        MetricsManager.record_request(
            db=db,
            endpoint='/mobile/lookup',
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
        error_logger.error(f"Mobile lookup error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Server error")


@router.get("/daily-schedule", response_model=MobileDailyScheduleResponse)
async def mobile_daily_schedule(
    address: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    city_id: Optional[str] = None,
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Ultra-minimal today's schedule endpoint.

    Returns only what's being picked up TODAY plus next pickup dates.
    Payload size: <200 bytes typical

    Args:
        address: Full address string (optional)
        lat: Latitude (optional)
        lon: Longitude (optional)
        city_id: City identifier (optional)
        request: Request object
        db: Database session

    Returns:
        MobileDailyScheduleResponse with today's flags
    """
    start_time = time.time()
    city_name = None

    try:
        # Validate input
        has_address = bool(address and address.strip())
        has_coords = lat is not None and lon is not None

        if not has_address and not has_coords:
            raise HTTPException(
                status_code=400,
                detail="Must provide 'address' or both 'lat' and 'lon'"
            )

        # Find address record
        addr_record = None

        if has_coords:
            addr_record = find_address_by_coordinates(
                db=db,
                lat=lat,
                lon=lon,
                max_distance_meters=50,
                city_id=city_id
            )
        elif has_address:
            parts = normalize_address(address)
            normalized = parts['normalized_address']
            city_name = parts.get('city')

            if not city_id and city_name:
                city_id = get_city_id_from_name(city_name)

            query = db.query(Address).filter(
                Address.normalized_address == normalized
            )
            if city_id:
                query = query.filter(Address.city_id == city_id)

            addr_record = query.first()

        # Get today's date
        today = datetime.now()
        today_str = today.strftime('%Y%m%d')

        # Return empty schedule if not found
        if not addr_record:
            return MobileDailyScheduleResponse(
                d=today_str,
                t=False,
                r=False,
                g=False
            )

        # Get schedule (same priority as lookup)
        consensus = db.query(CrowdConsensus).filter(
            CrowdConsensus.address_id == addr_record.id
        ).first()

        trash_day = None
        recycling_day = None
        green_day = None

        if consensus and consensus.is_verified:
            trash_day = consensus.consensus_trash_day
            recycling_day = consensus.consensus_recycling_day
            green_day = consensus.consensus_green_day
        elif any([addr_record.official_trash_day,
                  addr_record.official_recycling_day,
                  addr_record.official_green_day]):
            trash_day = addr_record.official_trash_day
            recycling_day = addr_record.official_recycling_day
            green_day = addr_record.official_green_day
        elif consensus:
            trash_day = consensus.consensus_trash_day
            recycling_day = consensus.consensus_recycling_day
            green_day = consensus.consensus_green_day

        # Check if today
        trash_today = is_pickup_today(trash_day, today)
        recycling_today = is_pickup_today(recycling_day, today)
        green_today = is_pickup_today(green_day, today)

        # Get next pickup dates
        next_trash = get_next_weekday(today, trash_day) if trash_day else None
        next_recycling = get_next_weekday(today, recycling_day) if recycling_day else None
        next_green = get_next_weekday(today, green_day) if green_day else None

        response = MobileDailyScheduleResponse(
            d=today_str,
            t=trash_today,
            r=recycling_today,
            g=green_today,
            nt=next_trash,
            nr=next_recycling,
            ng=next_green
        )

        # Record metrics
        response_time_ms = (time.time() - start_time) * 1000
        MetricsManager.record_request(
            db=db,
            endpoint='/mobile/daily-schedule',
            method='GET',
            status_code=200,
            response_time_ms=response_time_ms,
            city=addr_record.city if addr_record else city_name,
            user_agent=request.headers.get('user-agent') if request else None,
            ip_address=request.client.host if request and request.client else None
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        error_logger.error(f"Mobile daily-schedule error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Server error")


@router.post("/report", response_model=MobileReportResponse)
async def mobile_report(
    report: MobileReportRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Mobile-optimized report submission.

    Minimal request/response payloads.
    Payload size: <300 bytes typical

    Args:
        report: Mobile report request
        request: Request object
        db: Database session

    Returns:
        MobileReportResponse with minimal fields
    """
    start_time = time.time()
    city = None

    try:
        # Convert mobile codes to standard abbreviations
        trash_day = mobile_code_to_day(report.t) if report.t else None
        recycling_day = mobile_code_to_day(report.r) if report.r else None
        green_day = mobile_code_to_day(report.g) if report.g else None

        # Validate days
        trash_day = validate_day(trash_day)
        recycling_day = validate_day(recycling_day)
        green_day = validate_day(green_day)

        # At least one day must be provided
        if not any([trash_day, recycling_day, green_day]):
            raise HTTPException(
                status_code=400,
                detail="At least one pickup day required"
            )

        # Find or create address
        address = find_or_create_address(db, report.addr)
        city = address.city

        app_logger.info(
            f"Mobile report: {address.normalized_address} - "
            f"T:{trash_day} R:{recycling_day} G:{green_day}"
        )

        # Create crowd report
        new_report = CrowdReport(
            address_id=address.id,
            trash_day=trash_day,
            recycling_day=recycling_day,
            green_day=green_day,
            user_hash=report.u,
            ip_address=request.client.host if request.client else None
        )
        db.add(new_report)
        db.commit()

        # Update consensus
        consensus = update_crowd_consensus(db, address.id)

        # Build minimal response
        response = MobileReportResponse(
            ok=True,
            msg="Submitted",
            addr=address.normalized_address,
            cnt=consensus.total_reports if consensus else 1,
            ver=consensus.is_verified if consensus else False
        )

        # Record metrics
        response_time_ms = (time.time() - start_time) * 1000
        MetricsManager.record_request(
            db=db,
            endpoint='/mobile/report',
            method='POST',
            status_code=200,
            response_time_ms=response_time_ms,
            city=city,
            user_agent=request.headers.get('user-agent'),
            ip_address=request.client.host if request.client else None
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        error_logger.error(f"Mobile report error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Server error")
