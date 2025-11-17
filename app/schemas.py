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


class LookupResponse(BaseModel):
    """Response schema for GET /lookup endpoint."""
    address: str
    normalized_address: str

    # Pickup schedule
    trash_day: Optional[str]
    recycling_day: Optional[str]
    green_day: Optional[str]

    # Source information
    source: Literal["CROWD_VERIFIED", "OFFICIAL", "UNKNOWN"]

    # Consensus metrics (if crowdsourced)
    consensus_reports_count: Optional[int] = None
    consensus_agreement_ratio: Optional[float] = None

    # Coordinates
    lat: Optional[float] = None
    lon: Optional[float] = None
