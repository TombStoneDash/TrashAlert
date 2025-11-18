"""Pydantic schemas for API request/response validation."""
from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator, EmailStr


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


# Notification system schemas

class UserCreate(BaseModel):
    """Request schema for creating a new user."""
    email: EmailStr = Field(..., description="User's email address")
    phone: Optional[str] = Field(None, description="User's phone number for SMS (E.164 format recommended)")
    display_name: Optional[str] = Field(None, max_length=100, description="User's display name")
    timezone: str = Field(default="America/Los_Angeles", description="User's timezone")


class UserResponse(BaseModel):
    """Response schema for user data."""
    id: int
    email: str
    phone: Optional[str]
    display_name: Optional[str]
    timezone: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SubscriptionCreate(BaseModel):
    """Request schema for creating a subscription."""
    address: str = Field(..., min_length=5, description="Full address to subscribe to")
    notify_trash: bool = Field(default=True, description="Send trash pickup reminders")
    notify_recycling: bool = Field(default=True, description="Send recycling pickup reminders")
    notify_green: bool = Field(default=False, description="Send green waste pickup reminders")
    notify_email: bool = Field(default=True, description="Send notifications via email")
    notify_sms: bool = Field(default=False, description="Send notifications via SMS")
    days_before: int = Field(default=1, ge=0, le=7, description="How many days before pickup to notify (0-7)")
    notification_time: str = Field(default="18:00", description="Time to send notifications (HH:MM format)")

    @field_validator('notification_time')
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """Validate time is in HH:MM format."""
        try:
            hour, minute = map(int, v.split(':'))
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError
            return f"{hour:02d}:{minute:02d}"
        except (ValueError, AttributeError):
            raise ValueError("notification_time must be in HH:MM format (e.g., 18:00)")


class SubscriptionUpdate(BaseModel):
    """Request schema for updating a subscription."""
    notify_trash: Optional[bool] = None
    notify_recycling: Optional[bool] = None
    notify_green: Optional[bool] = None
    notify_email: Optional[bool] = None
    notify_sms: Optional[bool] = None
    days_before: Optional[int] = Field(None, ge=0, le=7)
    notification_time: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator('notification_time')
    @classmethod
    def validate_time_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate time is in HH:MM format."""
        if v is None:
            return v
        try:
            hour, minute = map(int, v.split(':'))
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError
            return f"{hour:02d}:{minute:02d}"
        except (ValueError, AttributeError):
            raise ValueError("notification_time must be in HH:MM format (e.g., 18:00)")


class SubscriptionResponse(BaseModel):
    """Response schema for subscription data."""
    id: int
    user_id: int
    address_id: int
    address: str  # Normalized address from Address table
    notify_trash: bool
    notify_recycling: bool
    notify_green: bool
    notify_email: bool
    notify_sms: bool
    days_before: int
    notification_time: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TestNotificationRequest(BaseModel):
    """Request schema for testing notification delivery."""
    notification_type: Literal["trash", "recycling", "green"] = Field(default="trash", description="Type of notification to test")
    channel: Literal["email", "sms", "both"] = Field(default="email", description="Channel to test")
    address: str = Field(..., description="Address to use in test notification")


class TestNotificationResponse(BaseModel):
    """Response schema for test notification."""
    success: bool
    message: str
    email_result: Optional[dict] = None
    sms_result: Optional[dict] = None
