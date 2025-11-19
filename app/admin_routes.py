"""Admin routes for API key management and usage analytics."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import List

from app.database import get_db
from app.models import ApiKey, ApiKeyUsage
from app.schemas import (
    CreateAPIKeyRequest,
    CreateAPIKeyResponse,
    APIKeyResponse,
    UpdateAPIKeyRequest,
    APIKeyUsageResponse,
    UsageDashboardResponse,
    APIUsageStats,
)
from app.api_key_utils import generate_api_key

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/keys", response_model=CreateAPIKeyResponse)
async def create_api_key(
    request: CreateAPIKeyRequest,
    db: Session = Depends(get_db)
):
    """
    Create a new API key.

    WARNING: The full API key is only shown once in this response.
    Store it securely - it cannot be retrieved later.
    """
    # Generate API key
    full_key, key_hash, key_prefix = generate_api_key()

    # Create API key record
    api_key = ApiKey(
        key_hash=key_hash,
        key_prefix=key_prefix,
        company_name=request.company_name,
        contact_email=request.contact_email,
        rate_limit_per_minute=request.rate_limit_per_minute,
        rate_limit_per_hour=request.rate_limit_per_hour,
        rate_limit_per_day=request.rate_limit_per_day,
        expires_at=request.expires_at,
        notes=request.notes,
    )

    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return CreateAPIKeyResponse(
        success=True,
        message="API key created successfully. SAVE THE KEY - it won't be shown again!",
        api_key=full_key,
        key_details=APIKeyResponse.model_validate(api_key)
    )


@router.get("/keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    """List all API keys."""
    query = db.query(ApiKey)

    if active_only:
        query = query.filter(ApiKey.is_active == True)

    keys = query.order_by(desc(ApiKey.created_at)).all()
    return [APIKeyResponse.model_validate(key) for key in keys]


@router.get("/keys/{key_id}", response_model=APIKeyResponse)
async def get_api_key(
    key_id: int,
    db: Session = Depends(get_db)
):
    """Get details of a specific API key."""
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    return APIKeyResponse.model_validate(api_key)


@router.patch("/keys/{key_id}", response_model=APIKeyResponse)
async def update_api_key(
    key_id: int,
    request: UpdateAPIKeyRequest,
    db: Session = Depends(get_db)
):
    """Update an API key's settings."""
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    # Update only provided fields
    if request.is_active is not None:
        api_key.is_active = request.is_active
    if request.rate_limit_per_minute is not None:
        api_key.rate_limit_per_minute = request.rate_limit_per_minute
    if request.rate_limit_per_hour is not None:
        api_key.rate_limit_per_hour = request.rate_limit_per_hour
    if request.rate_limit_per_day is not None:
        api_key.rate_limit_per_day = request.rate_limit_per_day
    if request.expires_at is not None:
        api_key.expires_at = request.expires_at
    if request.notes is not None:
        api_key.notes = request.notes

    db.commit()
    db.refresh(api_key)

    return APIKeyResponse.model_validate(api_key)


@router.delete("/keys/{key_id}")
async def delete_api_key(
    key_id: int,
    db: Session = Depends(get_db)
):
    """Delete an API key (soft delete by deactivating)."""
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    # Soft delete - just deactivate
    api_key.is_active = False
    db.commit()

    return {"success": True, "message": f"API key {api_key.key_prefix}... deactivated"}


def _calculate_usage_stats(usage_logs: list) -> APIUsageStats:
    """Calculate usage statistics from usage logs."""
    if not usage_logs:
        return APIUsageStats(
            total_requests=0,
            requests_by_endpoint={},
            requests_by_status={},
            avg_response_time_ms=0.0,
            error_rate=0.0,
        )

    total_requests = len(usage_logs)

    # Requests by endpoint
    requests_by_endpoint = {}
    for log in usage_logs:
        endpoint = log.endpoint
        requests_by_endpoint[endpoint] = requests_by_endpoint.get(endpoint, 0) + 1

    # Requests by status
    requests_by_status = {}
    for log in usage_logs:
        status = str(log.status_code)
        requests_by_status[status] = requests_by_status.get(status, 0) + 1

    # Average response time
    response_times = [log.response_time_ms for log in usage_logs if log.response_time_ms]
    avg_response_time_ms = sum(response_times) / len(response_times) if response_times else 0.0

    # Error rate (4xx and 5xx)
    error_count = sum(1 for log in usage_logs if log.status_code >= 400)
    error_rate = error_count / total_requests if total_requests > 0 else 0.0

    return APIUsageStats(
        total_requests=total_requests,
        requests_by_endpoint=requests_by_endpoint,
        requests_by_status=requests_by_status,
        avg_response_time_ms=round(avg_response_time_ms, 2),
        error_rate=round(error_rate, 4),
    )


@router.get("/keys/{key_id}/usage", response_model=APIKeyUsageResponse)
async def get_api_key_usage(
    key_id: int,
    db: Session = Depends(get_db)
):
    """Get usage statistics for a specific API key."""
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    now = datetime.utcnow()

    # Get usage logs for different time periods
    usage_today = db.query(ApiKeyUsage).filter(
        ApiKeyUsage.api_key_id == key_id,
        ApiKeyUsage.created_at >= now - timedelta(days=1)
    ).all()

    usage_7days = db.query(ApiKeyUsage).filter(
        ApiKeyUsage.api_key_id == key_id,
        ApiKeyUsage.created_at >= now - timedelta(days=7)
    ).all()

    usage_30days = db.query(ApiKeyUsage).filter(
        ApiKeyUsage.api_key_id == key_id,
        ApiKeyUsage.created_at >= now - timedelta(days=30)
    ).all()

    # Get recent requests (last 100)
    recent_logs = db.query(ApiKeyUsage).filter(
        ApiKeyUsage.api_key_id == key_id
    ).order_by(desc(ApiKeyUsage.created_at)).limit(100).all()

    recent_requests = [
        {
            "endpoint": log.endpoint,
            "method": log.method,
            "status_code": log.status_code,
            "response_time_ms": log.response_time_ms,
            "created_at": log.created_at.isoformat(),
            "error_message": log.error_message,
        }
        for log in recent_logs
    ]

    return APIKeyUsageResponse(
        api_key=APIKeyResponse.model_validate(api_key),
        stats_today=_calculate_usage_stats(usage_today),
        stats_7days=_calculate_usage_stats(usage_7days),
        stats_30days=_calculate_usage_stats(usage_30days),
        recent_requests=recent_requests,
    )


@router.get("/usage", response_model=UsageDashboardResponse)
async def get_usage_dashboard(db: Session = Depends(get_db)):
    """
    Get overall usage dashboard with analytics.

    Returns aggregated metrics across all API keys.
    """
    now = datetime.utcnow()

    # Total API keys
    total_api_keys = db.query(func.count(ApiKey.id)).scalar()
    active_api_keys = db.query(func.count(ApiKey.id)).filter(ApiKey.is_active == True).scalar()

    # Total requests by time period
    total_requests_today = db.query(func.count(ApiKeyUsage.id)).filter(
        ApiKeyUsage.created_at >= now - timedelta(days=1)
    ).scalar()

    total_requests_7days = db.query(func.count(ApiKeyUsage.id)).filter(
        ApiKeyUsage.created_at >= now - timedelta(days=7)
    ).scalar()

    total_requests_30days = db.query(func.count(ApiKeyUsage.id)).filter(
        ApiKeyUsage.created_at >= now - timedelta(days=30)
    ).scalar()

    # Top keys by usage (last 30 days)
    top_keys = db.query(
        ApiKey.id,
        ApiKey.key_prefix,
        ApiKey.company_name,
        func.count(ApiKeyUsage.id).label('request_count')
    ).join(
        APIUsage, ApiKey.id == ApiKeyUsage.api_key_id
    ).filter(
        ApiKeyUsage.created_at >= now - timedelta(days=30)
    ).group_by(
        ApiKey.id
    ).order_by(
        desc('request_count')
    ).limit(10).all()

    top_keys_by_usage = [
        {
            "api_key_id": key.id,
            "key_prefix": key.key_prefix,
            "company_name": key.company_name,
            "request_count": key.request_count,
        }
        for key in top_keys
    ]

    # Requests by endpoint (last 30 days)
    endpoint_stats = db.query(
        ApiKeyUsage.endpoint,
        func.count(ApiKeyUsage.id).label('count')
    ).filter(
        ApiKeyUsage.created_at >= now - timedelta(days=30)
    ).group_by(
        ApiKeyUsage.endpoint
    ).all()

    requests_by_endpoint = {stat.endpoint: stat.count for stat in endpoint_stats}

    # Error rate and avg response time (last 30 days)
    recent_usage = db.query(ApiKeyUsage).filter(
        ApiKeyUsage.created_at >= now - timedelta(days=30)
    ).all()

    stats = _calculate_usage_stats(recent_usage)

    return UsageDashboardResponse(
        total_api_keys=total_api_keys,
        active_api_keys=active_api_keys,
        total_requests_today=total_requests_today or 0,
        total_requests_7days=total_requests_7days or 0,
        total_requests_30days=total_requests_30days or 0,
        top_keys_by_usage=top_keys_by_usage,
        requests_by_endpoint=requests_by_endpoint,
        error_rate=stats.error_rate,
        avg_response_time_ms=stats.avg_response_time_ms,
    )
