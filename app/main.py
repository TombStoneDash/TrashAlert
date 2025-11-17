"""TrashAlert FastAPI application."""
from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db, engine, Base
from app.models import Address, CrowdReport, CrowdConsensus
from app.schemas import ReportRequest, ReportResponse, LookupResponse, ConsensusInfo
from app.utils import (
    normalize_address,
    find_or_create_address,
    update_crowd_consensus,
    validate_day
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
    # Normalize address to find it
    parts = normalize_address(address)
    normalized = parts['normalized_address']

    # Try to find address
    addr_record = db.query(Address).filter(
        Address.normalized_address == normalized
    ).first()

    if not addr_record:
        # Address not found - return UNKNOWN
        return LookupResponse(
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
        source = "CROWD_VERIFIED"  # Still show as crowd, but not fully verified
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

    return LookupResponse(
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
