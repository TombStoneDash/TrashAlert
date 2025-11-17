"""
Pydantic models for API request/response schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional


class LookupResponse(BaseModel):
    """Response model for address lookup."""

    matched_address: str = Field(
        ...,
        description="The matched address from the database"
    )
    city: str = Field(
        ...,
        description="City name"
    )
    trash_day_of_week: Optional[str] = Field(
        None,
        description="Day of week for trash pickup (e.g., 'Monday')"
    )
    recycling_day_of_week: Optional[str] = Field(
        None,
        description="Day of week for recycling pickup"
    )
    green_waste_day_of_week: Optional[str] = Field(
        None,
        description="Day of week for green waste pickup"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score of the match (0-1)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "matched_address": "1122 Palmview Ave",
                "city": "El Centro",
                "trash_day_of_week": "Tuesday",
                "recycling_day_of_week": "Friday",
                "green_waste_day_of_week": None,
                "confidence": 0.95
            }
        }


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    database: str = Field(..., description="Database status")
    total_addresses: int = Field(..., description="Total addresses in database")
    total_cities: int = Field(..., description="Total cities in database")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok",
                "database": "connected",
                "total_addresses": 248,
                "total_cities": 6
            }
        }
