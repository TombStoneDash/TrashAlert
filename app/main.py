"""TrashAlert FastAPI application."""
from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db, engine, Base
from app.models import Address, CrowdReport, CrowdConsensus
from app.schemas import ReportRequest, ReportResponse, LookupResponse, ConsensusInfo, ConsensusDetails
from app.utils import (
    normalize_address,
    find_or_create_address,
    update_crowd_consensus,
    validate_day,
    day_abbrev_to_full
)

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="TrashAlert API",
    description="API for trash pickup schedules with crowdsourced data",
    version="1.0.0"
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "TrashAlert API",
        "endpoints": ["/lookup", "/report"]
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
        request: FastAPI request (for IP tracking)
        db: Database session

    Returns:
        Report response with consensus information
    """
    # Validate days
    trash_day = validate_day(report.trash_day)
    recycling_day = validate_day(report.recycling_day)
    green_day = validate_day(report.green_day)

    # At least one day must be provided
    if not any([trash_day, recycling_day, green_day]):
        raise HTTPException(
            status_code=400,
            detail="At least one pickup day (trash_day, recycling_day, or green_day) must be provided"
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

    return ReportResponse(
        success=True,
        message="Report submitted successfully",
        address_id=address.id,
        normalized_address=address.normalized_address,
        consensus=consensus_info
    )


@app.get("/lookup", response_model=LookupResponse)
async def lookup_address(
    address: str,
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
        db: Database session

    Returns:
        Pickup schedule with source information
    """
    # Validate input
    if not address or not address.strip():
        raise HTTPException(
            status_code=400,
            detail="Address parameter is required and cannot be empty"
        )

    # Normalize address to find it
    parts = normalize_address(address)
    normalized = parts['normalized_address']

    # Check if normalization produced valid result
    if not normalized or len(normalized) < 3:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid address format: '{address}'"
        )

    # Try to find address
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

    # Get consensus data if available
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


@app.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get statistics about the database."""
    total_addresses = db.query(Address).count()
    total_reports = db.query(CrowdReport).count()
    total_consensus = db.query(CrowdConsensus).count()
    verified_consensus = db.query(CrowdConsensus).filter(
        CrowdConsensus.is_verified == True
    ).count()

    return {
        "total_addresses": total_addresses,
        "total_reports": total_reports,
        "total_consensus": total_consensus,
        "verified_consensus": verified_consensus
    }
