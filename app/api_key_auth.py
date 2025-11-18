"""API key authentication and management utilities."""
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session
from fastapi import Header, HTTPException, Depends, status
from app.database import get_db
from app.models import ApiKey, ApiKeyUsage


def generate_api_key() -> Tuple[str, str, str]:
    """Generate a secure API key.

    Returns:
        Tuple of (full_key, hashed_key, prefix)
        - full_key: The complete API key to give to the user (only shown once)
        - hashed_key: SHA256 hash to store in database
        - prefix: First 8 chars for identification (unhashed)
    """
    # Generate a 32-byte random key (256 bits)
    full_key = f"ta_{secrets.token_urlsafe(32)}"

    # Create hash for storage
    hashed_key = hashlib.sha256(full_key.encode()).hexdigest()

    # Extract prefix for identification
    prefix = full_key[:11]  # "ta_" + 8 chars

    return full_key, hashed_key, prefix


def hash_api_key(api_key: str) -> str:
    """Hash an API key for comparison.

    Args:
        api_key: The raw API key

    Returns:
        SHA256 hash of the API key
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def create_api_key(
    db: Session,
    name: str,
    description: Optional[str] = None,
    scopes: Optional[List[str]] = None,
    rate_limit_per_minute: int = 30,
    rate_limit_per_hour: int = 500,
    expires_in_days: Optional[int] = None,
    created_by: Optional[str] = None
) -> Tuple[str, ApiKey]:
    """Create a new API key.

    Args:
        db: Database session
        name: Human-readable name for the key
        description: Optional description
        scopes: List of scopes (e.g., ["mobile:lookup", "mobile:report"])
        rate_limit_per_minute: Requests per minute limit
        rate_limit_per_hour: Requests per hour limit
        expires_in_days: Optional expiration (None = never expires)
        created_by: Who created this key

    Returns:
        Tuple of (full_api_key, api_key_record)
        IMPORTANT: full_api_key is only returned once and should be given to the user
    """
    full_key, hashed_key, prefix = generate_api_key()

    # Calculate expiration
    expires_at = None
    if expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

    # Default scopes
    if scopes is None:
        scopes = ["mobile:lookup", "mobile:report"]

    # Create database record
    api_key_record = ApiKey(
        key=hashed_key,
        key_prefix=prefix,
        name=name,
        description=description,
        scopes=scopes,
        rate_limit_per_minute=rate_limit_per_minute,
        rate_limit_per_hour=rate_limit_per_hour,
        expires_at=expires_at,
        created_by=created_by,
        is_active=True
    )

    db.add(api_key_record)
    db.commit()
    db.refresh(api_key_record)

    return full_key, api_key_record


def validate_api_key(
    db: Session,
    api_key: str,
    required_scope: Optional[str] = None
) -> Optional[ApiKey]:
    """Validate an API key and check if it's active and not expired.

    Args:
        db: Database session
        api_key: The raw API key to validate
        required_scope: Optional scope to check (e.g., "mobile:lookup")

    Returns:
        ApiKey record if valid, None otherwise
    """
    # Hash the provided key
    hashed_key = hash_api_key(api_key)

    # Look up the key
    api_key_record = db.query(ApiKey).filter(
        ApiKey.key == hashed_key,
        ApiKey.is_active == True
    ).first()

    if not api_key_record:
        return None

    # Check expiration
    if api_key_record.expires_at:
        if datetime.utcnow() > api_key_record.expires_at:
            return None

    # Check scope if required
    if required_scope:
        if required_scope not in (api_key_record.scopes or []):
            return None

    return api_key_record


def record_api_key_usage(
    db: Session,
    api_key_id: int,
    endpoint: str,
    method: str,
    status_code: int,
    response_time_ms: float,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> None:
    """Record API key usage for analytics.

    Args:
        db: Database session
        api_key_id: ID of the API key
        endpoint: Endpoint path
        method: HTTP method
        status_code: Response status code
        response_time_ms: Response time in milliseconds
        ip_address: Client IP address
        user_agent: User agent string
    """
    usage = ApiKeyUsage(
        api_key_id=api_key_id,
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        response_time_ms=response_time_ms,
        ip_address=ip_address,
        user_agent=user_agent
    )

    # Update last_used_at and total_requests on the key
    api_key_record = db.query(ApiKey).filter(ApiKey.id == api_key_id).first()
    if api_key_record:
        api_key_record.last_used_at = datetime.utcnow()
        api_key_record.total_requests = (api_key_record.total_requests or 0) + 1

    db.add(usage)
    db.commit()


# FastAPI dependency for API key authentication
async def require_api_key(
    x_api_key: Optional[str] = Header(None, description="API key for authentication"),
    db: Session = Depends(get_db)
) -> ApiKey:
    """FastAPI dependency to require valid API key.

    Usage:
        @app.get("/mobile/lookup")
        async def mobile_lookup(
            api_key: ApiKey = Depends(require_api_key)
        ):
            # api_key is the validated ApiKey record
            ...

    Raises:
        HTTPException: 401 if API key is missing or invalid
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    api_key_record = validate_api_key(db, x_api_key)

    if not api_key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    return api_key_record


# Optional API key dependency (allows requests without key)
async def optional_api_key(
    x_api_key: Optional[str] = Header(None, description="Optional API key"),
    db: Session = Depends(get_db)
) -> Optional[ApiKey]:
    """FastAPI dependency for optional API key.

    Returns:
        ApiKey record if valid key provided, None otherwise
    """
    if not x_api_key:
        return None

    return validate_api_key(db, x_api_key)
