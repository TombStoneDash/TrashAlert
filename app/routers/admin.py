"""Admin and city partner endpoints router."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

from app.database import get_db
from app.models import User, CrowdReport, Address
from app.schemas import ReportDetailResponse, VerifyReportRequest
from app.auth import get_current_user, require_city_partner_or_admin
from app.logging_config import app_logger

router = APIRouter(prefix="/admin", tags=["Admin & City Partners"])


@router.get("/reports/{address_id}", response_model=List[ReportDetailResponse])
async def get_reports_for_address(
    address_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_city_partner_or_admin)
):
    """
    Get all reports for a specific address (city partners and admins only).

    Args:
        address_id: Address ID to get reports for
        db: Database session
        current_user: Current authenticated user with city_partner or admin role

    Returns:
        List of detailed report information

    Raises:
        HTTPException: If address not found
    """
    # Check if address exists
    address = db.query(Address).filter(Address.id == address_id).first()
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )

    # Get all reports for this address
    reports = db.query(CrowdReport).filter(
        CrowdReport.address_id == address_id
    ).order_by(CrowdReport.created_at.desc()).all()

    # Build response with user information
    report_details = []
    for report in reports:
        # Get user information if available
        username = None
        if report.user_id:
            user = db.query(User).filter(User.id == report.user_id).first()
            username = user.username if user else None

        # Get verified by user information if available
        verified_by_username = None
        if report.verified_by_user_id:
            verified_by = db.query(User).filter(User.id == report.verified_by_user_id).first()
            verified_by_username = verified_by.username if verified_by else None

        report_details.append(ReportDetailResponse(
            id=report.id,
            address_id=report.address_id,
            normalized_address=address.normalized_address,
            trash_day=report.trash_day,
            recycling_day=report.recycling_day,
            green_day=report.green_day,
            user_id=report.user_id,
            username=username,
            is_verified=report.is_verified,
            verified_by_username=verified_by_username,
            verified_at=report.verified_at,
            created_at=report.created_at,
            ip_address=report.ip_address if current_user.role.value == "admin" else None
        ))

    app_logger.info(
        f"User {current_user.username} viewed {len(report_details)} reports for address {address_id}"
    )

    return report_details


@router.patch("/reports/{report_id}/verify", response_model=ReportDetailResponse)
async def verify_report(
    report_id: int,
    verify_data: VerifyReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_city_partner_or_admin)
):
    """
    Verify or unverify a crowdsourced report (city partners and admins only).

    Args:
        report_id: Report ID to verify/unverify
        verify_data: Verification data
        db: Database session
        current_user: Current authenticated user with city_partner or admin role

    Returns:
        Updated report information

    Raises:
        HTTPException: If report not found
    """
    # Get report
    report = db.query(CrowdReport).filter(CrowdReport.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )

    # Get address for response
    address = db.query(Address).filter(Address.id == report.address_id).first()

    # Update verification status
    old_status = report.is_verified
    report.is_verified = verify_data.is_verified

    if verify_data.is_verified:
        report.verified_by_user_id = current_user.id
        report.verified_at = datetime.utcnow()
    else:
        report.verified_by_user_id = None
        report.verified_at = None

    db.commit()
    db.refresh(report)

    # Get user information for response
    username = None
    if report.user_id:
        user = db.query(User).filter(User.id == report.user_id).first()
        username = user.username if user else None

    verified_by_username = None
    if report.verified_by_user_id:
        verified_by = db.query(User).filter(User.id == report.verified_by_user_id).first()
        verified_by_username = verified_by.username if verified_by else None

    app_logger.info(
        f"User {current_user.username} {'verified' if verify_data.is_verified else 'unverified'} "
        f"report {report_id} (was {'verified' if old_status else 'unverified'})"
    )

    return ReportDetailResponse(
        id=report.id,
        address_id=report.address_id,
        normalized_address=address.normalized_address,
        trash_day=report.trash_day,
        recycling_day=report.recycling_day,
        green_day=report.green_day,
        user_id=report.user_id,
        username=username,
        is_verified=report.is_verified,
        verified_by_username=verified_by_username,
        verified_at=report.verified_at,
        created_at=report.created_at,
        ip_address=report.ip_address if current_user.role.value == "admin" else None
    )


@router.get("/reports", response_model=List[ReportDetailResponse])
async def list_all_reports(
    skip: int = 0,
    limit: int = 100,
    verified_only: bool = False,
    unverified_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_city_partner_or_admin)
):
    """
    List all reports with filtering options (city partners and admins only).

    Args:
        skip: Number of reports to skip (pagination)
        limit: Maximum number of reports to return
        verified_only: Only return verified reports
        unverified_only: Only return unverified reports
        db: Database session
        current_user: Current authenticated user with city_partner or admin role

    Returns:
        List of detailed report information
    """
    query = db.query(CrowdReport)

    # Apply filters
    if verified_only:
        query = query.filter(CrowdReport.is_verified == True)
    elif unverified_only:
        query = query.filter(CrowdReport.is_verified == False)

    # Get reports
    reports = query.order_by(
        CrowdReport.created_at.desc()
    ).offset(skip).limit(limit).all()

    # Build response with user information
    report_details = []
    for report in reports:
        # Get address
        address = db.query(Address).filter(Address.id == report.address_id).first()

        # Get user information if available
        username = None
        if report.user_id:
            user = db.query(User).filter(User.id == report.user_id).first()
            username = user.username if user else None

        # Get verified by user information if available
        verified_by_username = None
        if report.verified_by_user_id:
            verified_by = db.query(User).filter(User.id == report.verified_by_user_id).first()
            verified_by_username = verified_by.username if verified_by else None

        report_details.append(ReportDetailResponse(
            id=report.id,
            address_id=report.address_id,
            normalized_address=address.normalized_address if address else "Unknown",
            trash_day=report.trash_day,
            recycling_day=report.recycling_day,
            green_day=report.green_day,
            user_id=report.user_id,
            username=username,
            is_verified=report.is_verified,
            verified_by_username=verified_by_username,
            verified_at=report.verified_at,
            created_at=report.created_at,
            ip_address=report.ip_address if current_user.role.value == "admin" else None
        ))

    app_logger.info(
        f"User {current_user.username} listed {len(report_details)} reports "
        f"(verified_only={verified_only}, unverified_only={unverified_only})"
    )

    return report_details
