"""Pydantic schemas for routing optimizer API."""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Tuple


class Coordinate(BaseModel):
    """Geographic coordinate."""
    lat: float = Field(..., description="Latitude", ge=-90, le=90)
    lon: float = Field(..., description="Longitude", ge=-180, le=180)


class RouteStop(BaseModel):
    """A stop on the optimized route."""
    address_id: Optional[int] = Field(None, description="Database address ID if available")
    address: Optional[str] = Field(None, description="Address string if available")
    lat: float = Field(..., description="Latitude")
    lon: float = Field(..., description="Longitude")
    sequence: int = Field(..., description="Order in the optimized route (0-based)")
    arrival_time_minutes: Optional[float] = Field(
        None,
        description="Estimated arrival time in minutes from start (if time windows enabled)"
    )


class RouteStatistics(BaseModel):
    """Statistics about the optimized route."""
    total_distance_km: float = Field(..., description="Total route distance in kilometers")
    total_distance_miles: float = Field(..., description="Total route distance in miles")
    total_stops: int = Field(..., description="Total number of stops")
    estimated_time_minutes: Optional[float] = Field(
        None,
        description="Estimated total time in minutes (if time windows enabled)"
    )
    distance_reduction_percent: Optional[float] = Field(
        None,
        description="Percentage reduction vs naive route (if calculated)"
    )


class OptimizeRouteRequest(BaseModel):
    """Request schema for route optimization."""
    city_id: str = Field(..., description="City identifier (e.g., 'san_diego', 'el_centro')")
    coordinates: Optional[List[Coordinate]] = Field(
        None,
        description="List of coordinates to optimize. If not provided, all addresses in city will be used."
    )
    max_stops: Optional[int] = Field(
        None,
        description="Maximum number of stops to include (for large datasets)",
        gt=0
    )
    use_time_windows: bool = Field(
        False,
        description="Enable time window constraints (experimental)"
    )
    depot_lat: Optional[float] = Field(
        None,
        description="Starting/ending depot latitude (if different from first coordinate)"
    )
    depot_lon: Optional[float] = Field(
        None,
        description="Starting/ending depot longitude (if different from first coordinate)"
    )

    @field_validator('city_id')
    @classmethod
    def validate_city_id(cls, v):
        """Validate city_id format."""
        if not v or not v.strip():
            raise ValueError("city_id cannot be empty")
        return v.strip().lower()


class OptimizeRouteResponse(BaseModel):
    """Response schema for route optimization."""
    success: bool = Field(..., description="Whether optimization was successful")
    message: str = Field(..., description="Status message")
    city_id: str = Field(..., description="City identifier")
    optimized_route: List[RouteStop] = Field(
        default_factory=list,
        description="Ordered list of stops in the optimized route"
    )
    statistics: Optional[RouteStatistics] = Field(
        None,
        description="Route statistics"
    )
    heatmap_data: Optional[List[Tuple[float, float]]] = Field(
        None,
        description="Optional heatmap data (list of lat/lon coordinates)"
    )
