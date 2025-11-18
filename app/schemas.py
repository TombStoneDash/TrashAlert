"""Pydantic schemas for API request/response validation."""
from typing import Optional, Literal, List, Dict, Any
from datetime import datetime
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


class ConsensusDetails(BaseModel):
    """Consensus details for crowdsourced data."""
    reports_count: int
    agreement_ratio: float


class LookupRequest(BaseModel):
    """Request schema for GET /lookup endpoint - supports multiple input formats."""
    # Option 1: Full address string
    address: Optional[str] = Field(None, min_length=5, max_length=500, description="Full address string")

    # Option 2: Coordinates
    lat: Optional[float] = Field(None, ge=-90, le=90, description="Latitude")
    lon: Optional[float] = Field(None, ge=-180, le=180, description="Longitude")

    # Option 3: Address + city_id (for more precise matching)
    city_id: Optional[str] = Field(None, description="City identifier from cities.yaml")

    @model_validator(mode='after')
    def validate_input_format(self):
        """Ensure at least one valid input format is provided."""
        has_address = bool(self.address and self.address.strip())
        has_coords = self.lat is not None and self.lon is not None

        if not has_address and not has_coords:
            raise ValueError("Must provide either 'address' or both 'lat' and 'lon'")

        return self


class LookupResponse(BaseModel):
    """Response schema for GET /lookup endpoint."""
    matched_address: str = Field(..., description="The matched address from database")
    city_id: Optional[str] = Field(None, description="City identifier")
    city_name: Optional[str] = Field(None, description="City name")

    # Coordinates
    lat: Optional[float] = Field(None, description="Latitude of matched address")
    lon: Optional[float] = Field(None, description="Longitude of matched address")

    # Pickup schedule (using full day names: Monday, Tuesday, etc.)
    trash_day_of_week: Optional[str] = Field(None, description="Trash pickup day")
    recycling_day_of_week: Optional[str] = Field(None, description="Recycling pickup day")
    green_waste_day_of_week: Optional[str] = Field(None, description="Green waste pickup day")

    # Source information
    data_source: Literal["CROWD_VERIFIED", "CROWD_UNVERIFIED", "OFFICIAL", "UNKNOWN"] = Field(
        ..., description="Data source: CROWD_VERIFIED > OFFICIAL > CROWD_UNVERIFIED > UNKNOWN"
    )

    # Consensus metrics (exposed at top level for convenience)
    consensus_reports_count: Optional[int] = Field(None, description="Number of crowdsourced reports")
    consensus_agreement_ratio: Optional[float] = Field(None, description="Overall consensus agreement ratio (0-1)")

    # Detailed consensus info (backward compatibility)
    consensus_details: Optional[ConsensusDetails] = Field(
        None, description="Detailed consensus metrics if data is crowdsourced"
    )


# Admin API Key Schemas

class CreateAPIKeyRequest(BaseModel):
    """Request schema for creating a new API key."""
    company_name: str = Field(..., min_length=1, max_length=200, description="Company name")
    contact_email: Optional[str] = Field(None, description="Contact email")
    rate_limit_per_minute: Optional[int] = Field(60, ge=1, le=1000, description="Requests per minute")
    rate_limit_per_hour: Optional[int] = Field(1000, ge=1, le=100000, description="Requests per hour")
    rate_limit_per_day: Optional[int] = Field(10000, ge=1, le=1000000, description="Requests per day")
    expires_at: Optional[datetime] = Field(None, description="Expiration date (optional)")
    notes: Optional[str] = Field(None, description="Admin notes")


class APIKeyResponse(BaseModel):
    """Response schema for API key details."""
    id: int
    key_prefix: str
    company_name: str
    contact_email: Optional[str]
    is_active: bool
    rate_limit_per_minute: int
    rate_limit_per_hour: int
    rate_limit_per_day: int
    total_requests: int
    last_used_at: Optional[datetime]
    created_at: datetime
    expires_at: Optional[datetime]
    notes: Optional[str]

    class Config:
        from_attributes = True


class CreateAPIKeyResponse(BaseModel):
    """Response schema for newly created API key (includes full key)."""
    success: bool
    message: str
    api_key: str = Field(..., description="Full API key - SAVE THIS! It won't be shown again.")
    key_details: APIKeyResponse


class UpdateAPIKeyRequest(BaseModel):
    """Request schema for updating an API key."""
    is_active: Optional[bool] = None
    rate_limit_per_minute: Optional[int] = Field(None, ge=1, le=1000)
    rate_limit_per_hour: Optional[int] = Field(None, ge=1, le=100000)
    rate_limit_per_day: Optional[int] = Field(None, ge=1, le=1000000)
    expires_at: Optional[datetime] = None
    notes: Optional[str] = None


class APIUsageStats(BaseModel):
    """API usage statistics."""
    total_requests: int
    requests_by_endpoint: Dict[str, int]
    requests_by_status: Dict[str, int]
    avg_response_time_ms: float
    error_rate: float


class APIKeyUsageResponse(BaseModel):
    """Response schema for API key usage details."""
    api_key: APIKeyResponse
    stats_today: APIUsageStats
    stats_7days: APIUsageStats
    stats_30days: APIUsageStats
    recent_requests: List[Dict[str, Any]]


class UsageDashboardResponse(BaseModel):
    """Response schema for admin usage dashboard."""
    total_api_keys: int
    active_api_keys: int
    total_requests_today: int
    total_requests_7days: int
    total_requests_30days: int
    top_keys_by_usage: List[Dict[str, Any]]
    requests_by_endpoint: Dict[str, int]
    error_rate: float
    avg_response_time_ms: float
