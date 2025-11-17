"""Pydantic schemas for API request/response validation."""
from typing import Optional, Literal
from pydantic import BaseModel, Field


class ReportRequest(BaseModel):
    """Request schema for POST /report endpoint."""
    address: str = Field(..., description="Full address string")
    trash_day: Optional[str] = Field(None, description="Trash pickup day (MON, TUE, WED, THU, FRI)")
    recycling_day: Optional[str] = Field(None, description="Recycling pickup day")
    green_day: Optional[str] = Field(None, description="Green waste pickup day")
    user_hash: Optional[str] = Field(None, description="Optional stable user identifier")


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


class LookupResponse(BaseModel):
    """Response schema for GET /lookup endpoint."""
    matched_address: str = Field(..., description="The matched address from database")
    city_name: Optional[str] = Field(None, description="City name")

    # Pickup schedule (using full day names: Monday, Tuesday, etc.)
    trash_day_of_week: Optional[str] = Field(None, description="Trash pickup day")
    recycling_day_of_week: Optional[str] = Field(None, description="Recycling pickup day")
    green_waste_day_of_week: Optional[str] = Field(None, description="Green waste pickup day")

    # Source information
    data_source: Literal["CROWD_VERIFIED", "CROWD_UNVERIFIED", "OFFICIAL", "UNKNOWN"] = Field(
        ..., description="Data source: CROWD_VERIFIED > OFFICIAL > CROWD_UNVERIFIED > UNKNOWN"
    )

    # Consensus metrics (if crowdsourced)
    consensus_details: Optional[ConsensusDetails] = Field(
        None, description="Consensus details if data is crowdsourced"
    )
