"""Pydantic schemas for API request/response validation."""
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class ReportRequest(BaseModel):
    """Request schema for POST /report endpoint."""
    address: str = Field(..., min_length=5, max_length=500, description="Full address string")
    trash_day: Optional[str] = Field(None, max_length=20, description="Trash pickup day (MON, TUE, WED, THU, FRI)")
    recycling_day: Optional[str] = Field(None, max_length=20, description="Recycling pickup day")
    green_day: Optional[str] = Field(None, max_length=20, description="Green waste pickup day")
    user_hash: Optional[str] = Field(None, max_length=64, description="Optional stable user identifier")

    @field_validator('address')
    @classmethod
    def validate_address_not_empty(cls, v: str) -> str:
        """Ensure address is not just whitespace."""
        if not v or not v.strip():
            raise ValueError("Address cannot be empty or whitespace only")
        # Remove excessive whitespace
        return ' '.join(v.split())

    @field_validator('trash_day', 'recycling_day', 'green_day')
    @classmethod
    def validate_day_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate day is in expected format if provided."""
        if v is None:
            return v
        # Remove whitespace and uppercase
        v = v.strip().upper()
        if not v:
            return None

        # Valid day abbreviations and full names
        valid_days = {
            'MON', 'MONDAY', 'TUE', 'TUESDAY', 'WED', 'WEDNESDAY',
            'THU', 'THURSDAY', 'FRI', 'FRIDAY', 'SAT', 'SATURDAY',
            'SUN', 'SUNDAY'
        }

        if v not in valid_days:
            raise ValueError(f"Invalid day '{v}'. Must be MON-SUN or MONDAY-SUNDAY")

        return v

    @model_validator(mode='after')
    def validate_at_least_one_day(self):
        """Ensure at least one pickup day is provided."""
        if not any([self.trash_day, self.recycling_day, self.green_day]):
            raise ValueError("At least one pickup day (trash_day, recycling_day, or green_day) must be provided")
        return self


class ConsensusInfo(BaseModel):
    """Consensus information for a response."""
    trash_day: Optional[str]
    recycling_day: Optional[str]
    green_day: Optional[str]
    reports_count: int
    trash_agreement_ratio: float
    recycling_agreement_ratio: float
    green_agreement_ratio: float
    is_verified: bool


class ReportResponse(BaseModel):
    """Response schema for POST /report endpoint."""
    success: bool
    message: str
    address_id: int
    normalized_address: str
    consensus: Optional[ConsensusInfo] = None


class LookupResponse(BaseModel):
    """Response schema for GET /lookup endpoint."""
    address: str
    normalized_address: str

    # Pickup schedule
    trash_day: Optional[str]
    recycling_day: Optional[str]
    green_day: Optional[str]

    # Source information
    source: Literal["CROWD_VERIFIED", "CROWD_UNVERIFIED", "OFFICIAL", "UNKNOWN"]

    # Consensus metrics (if crowdsourced)
    consensus_reports_count: Optional[int] = None
    consensus_agreement_ratio: Optional[float] = None

    # Coordinates
    lat: Optional[float] = None
    lon: Optional[float] = None
