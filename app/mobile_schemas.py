"""Lightweight mobile-optimized schemas for minimal payloads (<1kb)."""
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator


class MobileLookupResponse(BaseModel):
    """Minimal lookup response optimized for mobile (<1kb).

    Uses single-letter day codes and abbreviated field names.
    """
    # Single letter codes: M=Monday, T=Tuesday, W=Wednesday, R=Thursday, F=Friday, S=Saturday, U=Sunday
    addr: str = Field(..., description="Matched address")
    c: Optional[str] = Field(None, description="City ID")

    # Coordinates (shortened)
    lat: Optional[float] = None
    lon: Optional[float] = None

    # Pickup schedule - single letter day codes or null
    t: Optional[str] = Field(None, description="Trash day (M/T/W/R/F/S/U)")
    r: Optional[str] = Field(None, description="Recycling day (M/T/W/R/F/S/U)")
    g: Optional[str] = Field(None, description="Green waste day (M/T/W/R/F/S/U)")

    # Source: V=verified, O=official, U=unverified, X=unknown
    src: str = Field(..., description="Data source")

    # Consensus metrics (only if crowd-sourced)
    cnt: Optional[int] = Field(None, description="Report count")
    agr: Optional[float] = Field(None, description="Agreement ratio")


class MobileDailyScheduleResponse(BaseModel):
    """Today's pickup schedule - ultra minimal.

    Only returns what's being picked up TODAY.
    """
    # Date in compact format YYYYMMDD
    d: str = Field(..., description="Date (YYYYMMDD)")

    # Boolean flags for today's pickups
    t: bool = Field(False, description="Trash today")
    r: bool = Field(False, description="Recycling today")
    g: bool = Field(False, description="Green waste today")

    # Next pickup dates (compact YYYYMMDD)
    nt: Optional[str] = Field(None, description="Next trash date")
    nr: Optional[str] = Field(None, description="Next recycling date")
    ng: Optional[str] = Field(None, description="Next green waste date")


class MobileReportRequest(BaseModel):
    """Minimal report submission request."""
    addr: str = Field(..., min_length=5, max_length=500)
    t: Optional[str] = Field(None, description="Trash day (M/T/W/R/F/S/U)")
    r: Optional[str] = Field(None, description="Recycling day")
    g: Optional[str] = Field(None, description="Green waste day")
    u: Optional[str] = Field(None, max_length=64, description="User hash")

    @field_validator('addr')
    @classmethod
    def validate_address(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Address required")
        return ' '.join(v.split())

    @field_validator('t', 'r', 'g')
    @classmethod
    def validate_day(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().upper()
        if not v:
            return None
        # Accept single letter codes or full abbreviations
        valid = {'M', 'T', 'W', 'R', 'F', 'S', 'U',
                'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'}
        if v not in valid:
            raise ValueError(f"Invalid day: {v}")
        return v


class MobileReportResponse(BaseModel):
    """Minimal report response."""
    ok: bool = Field(..., description="Success status")
    msg: str = Field(..., description="Message")
    addr: str = Field(..., description="Normalized address")
    # Consensus info (optional)
    cnt: Optional[int] = Field(None, description="Total reports")
    ver: Optional[bool] = Field(None, description="Is verified")


class MobileErrorResponse(BaseModel):
    """Minimal error response for mobile endpoints."""
    err: str = Field(..., description="Error code")
    msg: str = Field(..., description="Error message")
    # Optional retry info
    retry: Optional[bool] = Field(None, description="Can retry")
    wait: Optional[int] = Field(None, description="Wait seconds before retry")
