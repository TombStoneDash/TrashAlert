"""Pydantic schemas for API request/response validation."""
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator, EmailStr
from datetime import datetime


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


# ============================================================================
# MOBILE ENDPOINTS - Simplified Schemas
# ============================================================================

class MobileLookupRequest(BaseModel):
    """Simplified request schema for mobile /mobile/lookup endpoint."""
    # Option 1: Address
    address: Optional[str] = Field(None, min_length=5, max_length=500)

    # Option 2: Coordinates (more common for mobile)
    lat: Optional[float] = Field(None, ge=-90, le=90)
    lon: Optional[float] = Field(None, ge=-180, le=180)

    @model_validator(mode='after')
    def validate_input(self):
        """Ensure at least one valid input format is provided."""
        has_address = bool(self.address and self.address.strip())
        has_coords = self.lat is not None and self.lon is not None

        if not has_address and not has_coords:
            raise ValueError("Provide 'address' or both 'lat' and 'lon'")

        return self


class MobileLookupResponse(BaseModel):
    """Simplified response schema for mobile /mobile/lookup endpoint.

    Designed for mobile apps with focus on:
    - Minimal data transfer
    - Essential information only
    - Abbreviations to save bandwidth
    """
    # Core data
    address: str = Field(..., description="Matched address")
    city: Optional[str] = Field(None, description="City name")

    # Pickup days (abbreviated: MON, TUE, WED, etc.)
    trash: Optional[str] = Field(None, description="Trash day (MON-SUN)")
    recycling: Optional[str] = Field(None, description="Recycling day (MON-SUN)")
    green: Optional[str] = Field(None, description="Green waste day (MON-SUN)")

    # Data quality indicator
    source: Literal["verified", "official", "unverified", "unknown"] = Field(
        ..., description="Data source quality"
    )

    # Coordinates (optional, for map display)
    lat: Optional[float] = None
    lon: Optional[float] = None


class MobileReportRequest(BaseModel):
    """Simplified request schema for mobile /mobile/report endpoint."""
    address: str = Field(..., min_length=5, max_length=500)

    # At least one required
    trash: Optional[str] = Field(None, max_length=20, description="Trash day (MON-SUN)")
    recycling: Optional[str] = Field(None, max_length=20, description="Recycling day (MON-SUN)")
    green: Optional[str] = Field(None, max_length=20, description="Green waste day (MON-SUN)")

    # Optional user identifier
    user_id: Optional[str] = Field(None, max_length=64, description="User identifier")

    @field_validator('address')
    @classmethod
    def validate_address(cls, v: str) -> str:
        """Clean address."""
        if not v or not v.strip():
            raise ValueError("Address required")
        return ' '.join(v.split())

    @field_validator('trash', 'recycling', 'green')
    @classmethod
    def validate_day(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize day."""
        if v is None:
            return v
        v = v.strip().upper()
        if not v:
            return None

        # Abbreviations only for mobile
        valid_days = {'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'}

        # Also accept full names and convert
        day_map = {
            'MONDAY': 'MON', 'TUESDAY': 'TUE', 'WEDNESDAY': 'WED',
            'THURSDAY': 'THU', 'FRIDAY': 'FRI', 'SATURDAY': 'SAT', 'SUNDAY': 'SUN'
        }

        if v in day_map:
            return day_map[v]

        if v not in valid_days:
            raise ValueError(f"Invalid day '{v}'. Use MON-SUN")

        return v

    @model_validator(mode='after')
    def validate_at_least_one_day(self):
        """Ensure at least one pickup day provided."""
        if not any([self.trash, self.recycling, self.green]):
            raise ValueError("Provide at least one pickup day")
        return self


class MobileReportResponse(BaseModel):
    """Simplified response schema for mobile /mobile/report endpoint."""
    success: bool
    message: str
    address: str  # Normalized address

    # Simplified consensus info (only if verified)
    verified: bool = Field(False, description="True if consensus is verified (≥3 reports, ≥67% agreement)")
    reports: Optional[int] = Field(None, description="Number of reports if verified")
# AUTHENTICATION SCHEMAS
# ============================================================================

class UserRegisterRequest(BaseModel):
    """Request schema for user registration."""
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(..., min_length=8, max_length=100, description="Password (min 8 characters)")
    full_name: Optional[str] = Field(None, max_length=200, description="User's full name")

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format."""
        if not v.isalnum() and '_' not in v and '-' not in v:
            raise ValueError("Username can only contain letters, numbers, underscores, and hyphens")
        return v.lower()

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLoginRequest(BaseModel):
    """Request schema for user login."""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    """Response schema for token endpoints."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token expiration in seconds")


class TokenRefreshRequest(BaseModel):
    """Request schema for token refresh."""
    refresh_token: str = Field(..., description="Valid refresh token")


class UserResponse(BaseModel):
    """Response schema for user information."""
    id: int
    username: str
    email: str
    role: str
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime]

    class Config:
        from_attributes = True


class UserUpdateRoleRequest(BaseModel):
    """Request schema for updating user role (admin only)."""
    role: Literal["user", "reporter", "admin", "city_partner"] = Field(..., description="New role for user")


class ReportDetailResponse(BaseModel):
    """Detailed report information for city partners and admins."""
    id: int
    address_id: int
    normalized_address: str
    trash_day: Optional[str]
    recycling_day: Optional[str]
    green_day: Optional[str]
    user_id: Optional[int]
    username: Optional[str]
    is_verified: bool
    verified_by_username: Optional[str]
    verified_at: Optional[datetime]
    created_at: datetime
    ip_address: Optional[str]

    class Config:
        from_attributes = True


class VerifyReportRequest(BaseModel):
    """Request schema for verifying a report."""
    is_verified: bool = Field(..., description="Whether to mark report as verified")
class InterpretAddressRequest(BaseModel):
    """Request schema for POST /interpret-address endpoint."""
    text: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Freeform text containing an address to interpret"
    )
    use_geocoding: bool = Field(
        default=True,
        description="Whether to use geocoding fallback if AI interpretation has low confidence"
    )

    @field_validator('text')
    @classmethod
    def validate_text_not_empty(cls, v: str) -> str:
        """Ensure text is not just whitespace."""
        if not v or not v.strip():
            raise ValueError("Text cannot be empty or whitespace only")
        return v.strip()


class InterpretAddressResponse(BaseModel):
    """Response schema for POST /interpret-address endpoint."""
    success: bool = Field(..., description="Whether interpretation was successful")
    normalized_address: str = Field(..., description="Normalized address string")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0 to 1.0)")

    # Address components
    city: Optional[str] = Field(None, description="Extracted city name")
    city_id: Optional[str] = Field(None, description="Matched city ID from config")
    state: Optional[str] = Field(None, description="State abbreviation")
    zip_code: Optional[str] = Field(None, description="ZIP code")

    # Coordinates (from geocoding fallback)
    lat: Optional[float] = Field(None, description="Latitude (from geocoding)")
    lon: Optional[float] = Field(None, description="Longitude (from geocoding)")

    # Interpretation details
    interpretation_method: Literal["ai", "geocoding", "hybrid"] = Field(
        ..., description="Method used for interpretation"
    )
    ai_reasoning: Optional[str] = Field(None, description="AI's explanation of interpretation")
    geocoding_quality: Optional[str] = Field(None, description="Geocoding match quality if used")

    # Error information
    error: Optional[str] = Field(None, description="Error message if interpretation failed")
