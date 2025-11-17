"""
FastAPI application for TrashAlert address lookup.

Provides REST API endpoints for looking up trash collection schedules by address.
"""

from typing import Optional
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.models import Address, create_database, get_db_session
from src.normalization import normalize_address


# Pydantic models for request/response
class AddressLookupRequest(BaseModel):
    """Request model for address lookup."""
    address: str
    city: Optional[str] = None


class AddressLookupResponse(BaseModel):
    """Response model for address lookup."""
    normalized_address: str
    trash_day_of_week: Optional[str]
    subdivision_id: Optional[str]
    lat: float
    lon: float

    class Config:
        from_attributes = True


class HealthCheckResponse(BaseModel):
    """Response model for health check."""
    status: str
    message: str


# Create FastAPI app
app = FastAPI(
    title="TrashAlert API",
    description="API for looking up trash collection schedules by address",
    version="1.0.0"
)

# Database setup (will be overridden in tests)
_engine = None
_SessionLocal = None


def get_session_factory():
    """Get the session factory, initializing if needed."""
    global _engine, _SessionLocal
    if _SessionLocal is None:
        _engine, _SessionLocal = create_database()
    return _SessionLocal


def get_db():
    """Dependency for getting database sessions."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", response_model=HealthCheckResponse)
async def root():
    """Health check endpoint."""
    return HealthCheckResponse(
        status="ok",
        message="TrashAlert API is running"
    )


@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """Detailed health check endpoint."""
    return HealthCheckResponse(
        status="healthy",
        message="All systems operational"
    )


@app.post("/lookup", response_model=AddressLookupResponse)
async def lookup_address(
    request: AddressLookupRequest,
    db: Session = Depends(get_db)
):
    """
    Look up trash collection schedule for an address.

    Args:
        request: Address lookup request
        db: Database session

    Returns:
        Address information with trash collection day

    Raises:
        HTTPException: If address not found
    """
    # Normalize the input address
    normalized = normalize_address(request.address)

    # Query the database
    query = db.query(Address).filter(Address.normalized_address == normalized)

    # Optionally filter by city
    if request.city:
        query = query.filter(Address.city == request.city.upper())

    # Get the first matching address
    address = query.first()

    if not address:
        raise HTTPException(
            status_code=404,
            detail=f"Address not found: {normalized}"
        )

    return AddressLookupResponse(
        normalized_address=address.normalized_address,
        trash_day_of_week=address.trash_day_of_week,
        subdivision_id=address.subdivision_id,
        lat=address.lat,
        lon=address.lon
    )


@app.get("/lookup/{address_id}", response_model=AddressLookupResponse)
async def lookup_address_by_id(
    address_id: int,
    db: Session = Depends(get_db)
):
    """
    Look up address information by ID.

    Args:
        address_id: Address ID
        db: Database session

    Returns:
        Address information

    Raises:
        HTTPException: If address not found
    """
    address = db.query(Address).filter(Address.id == address_id).first()

    if not address:
        raise HTTPException(
            status_code=404,
            detail=f"Address ID not found: {address_id}"
        )

    return AddressLookupResponse(
        normalized_address=address.normalized_address,
        trash_day_of_week=address.trash_day_of_week,
        subdivision_id=address.subdivision_id,
        lat=address.lat,
        lon=address.lon
    )


def set_session_factory(session_factory):
    """
    Set the session factory (used for testing).

    Args:
        session_factory: SQLAlchemy session factory
    """
    global _SessionLocal
    _SessionLocal = session_factory
