"""GPS Ingestor Module - Handles truck location tracking and data ingestion."""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, validator

from app.database import get_db
from app.models import Truck, TruckLocation, TruckRoute


# Pydantic schemas for GPS data
class TruckLocationCreate(BaseModel):
    """Schema for creating a truck location record."""
    truck_id: int
    lat: float = Field(..., ge=-90, le=90, description="Latitude (-90 to 90)")
    lon: float = Field(..., ge=-180, le=180, description="Longitude (-180 to 180)")
    speed_mph: Optional[float] = Field(None, ge=0, description="Speed in mph")
    heading_degrees: Optional[float] = Field(None, ge=0, le=360, description="Heading in degrees")
    altitude_meters: Optional[float] = None
    accuracy_meters: Optional[float] = Field(None, ge=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @validator('timestamp', pre=True)
    def ensure_timezone_aware(cls, v):
        """Ensure timestamp is timezone-aware."""
        if isinstance(v, datetime):
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v
        return v


class TruckLocationResponse(BaseModel):
    """Schema for truck location response."""
    id: int
    truck_id: int
    lat: float
    lon: float
    speed_mph: Optional[float]
    heading_degrees: Optional[float]
    altitude_meters: Optional[float]
    accuracy_meters: Optional[float]
    timestamp: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class TruckResponse(BaseModel):
    """Schema for truck response."""
    id: int
    truck_number: str
    license_plate: Optional[str]
    city_id: Optional[int]
    status: str
    vehicle_type: Optional[str]
    capacity_cubic_yards: Optional[float]

    class Config:
        from_attributes = True


class TruckWithLocation(BaseModel):
    """Schema for truck with latest location."""
    id: int
    truck_number: str
    license_plate: Optional[str]
    status: str
    vehicle_type: Optional[str]
    latest_location: Optional[TruckLocationResponse]

    class Config:
        from_attributes = True


# Create router
router = APIRouter(prefix="/gps", tags=["GPS Tracking"])


@router.post("/truck-location", response_model=TruckLocationResponse, status_code=status.HTTP_201_CREATED)
async def ingest_truck_location(
    location: TruckLocationCreate,
    db: Session = Depends(get_db)
):
    """
    Ingest GPS location data from a truck.

    This endpoint receives GPS coordinates from trucks in the field and stores them
    for tracking, route history, and real-time monitoring.
    """
    # Verify truck exists
    truck = db.query(Truck).filter(Truck.id == location.truck_id).first()
    if not truck:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Truck with ID {location.truck_id} not found"
        )

    # Create location record
    db_location = TruckLocation(
        truck_id=location.truck_id,
        lat=location.lat,
        lon=location.lon,
        speed_mph=location.speed_mph,
        heading_degrees=location.heading_degrees,
        altitude_meters=location.altitude_meters,
        accuracy_meters=location.accuracy_meters,
        timestamp=location.timestamp
    )

    db.add(db_location)
    db.commit()
    db.refresh(db_location)

    return db_location


@router.get("/trucks", response_model=List[TruckWithLocation])
async def get_all_trucks_with_locations(db: Session = Depends(get_db)):
    """
    Get all trucks with their latest GPS location.

    Returns a list of all trucks in the fleet along with their most recent
    location update for real-time tracking on the admin dashboard.
    """
    trucks = db.query(Truck).filter(Truck.status == "active").all()

    result = []
    for truck in trucks:
        # Get latest location for this truck
        latest_location = (
            db.query(TruckLocation)
            .filter(TruckLocation.truck_id == truck.id)
            .order_by(TruckLocation.timestamp.desc())
            .first()
        )

        result.append({
            "id": truck.id,
            "truck_number": truck.truck_number,
            "license_plate": truck.license_plate,
            "status": truck.status,
            "vehicle_type": truck.vehicle_type,
            "latest_location": latest_location
        })

    return result


@router.get("/trucks/{truck_id}/trail", response_model=List[TruckLocationResponse])
async def get_truck_trail(
    truck_id: int,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get GPS trail (location history) for a specific truck.

    Returns the most recent location points for visualization of the truck's
    path. Useful for showing route coverage and movement patterns.
    """
    # Verify truck exists
    truck = db.query(Truck).filter(Truck.id == truck_id).first()
    if not truck:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Truck with ID {truck_id} not found"
        )

    # Get location trail
    locations = (
        db.query(TruckLocation)
        .filter(TruckLocation.truck_id == truck_id)
        .order_by(TruckLocation.timestamp.desc())
        .limit(limit)
        .all()
    )

    return locations


@router.get("/trucks/{truck_id}/latest", response_model=TruckLocationResponse)
async def get_truck_latest_location(
    truck_id: int,
    db: Session = Depends(get_db)
):
    """
    Get the latest GPS location for a specific truck.
    """
    # Verify truck exists
    truck = db.query(Truck).filter(Truck.id == truck_id).first()
    if not truck:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Truck with ID {truck_id} not found"
        )

    # Get latest location
    location = (
        db.query(TruckLocation)
        .filter(TruckLocation.truck_id == truck_id)
        .order_by(TruckLocation.timestamp.desc())
        .first()
    )

    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No location data found for truck {truck_id}"
        )

    return location
