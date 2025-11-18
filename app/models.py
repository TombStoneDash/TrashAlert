"""Database models for TrashAlert."""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Index
from sqlalchemy.sql import func
from app.database import Base


class Address(Base):
    """Address table - stores normalized addresses with pickup information."""
    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True, index=True)

    # Address fields
    normalized_address = Column(String, index=True, nullable=False)
    house_number = Column(String)
    street = Column(String, index=True)
    city = Column(String, index=True)
    state = Column(String, index=True)  # Added index for filtering by state
    zip_code = Column(String, index=True)  # Added index for filtering by zip

    # Coordinates
    lat = Column(Float)
    lon = Column(Float)

    # Official pickup schedule (from GIS/rules)
    official_trash_day = Column(String)  # MON, TUE, WED, THU, FRI
    official_recycling_day = Column(String)
    official_green_day = Column(String)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CrowdReport(Base):
    """Individual crowdsourced reports from users."""
    __tablename__ = "crowd_reports"

    id = Column(Integer, primary_key=True, index=True)
    address_id = Column(Integer, ForeignKey("addresses.id"), nullable=False, index=True)

    # Reported pickup days
    trash_day = Column(String)
    recycling_day = Column(String)
    green_day = Column(String)

    # User tracking (optional, for preventing spam)
    user_hash = Column(String, index=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    ip_address = Column(String, index=True)  # Index for spam prevention queries

    # Composite indexes for common query patterns
    __table_args__ = (
        Index('idx_address_created', 'address_id', 'created_at'),
    )


class CrowdConsensus(Base):
    """Aggregated consensus from crowdsourced reports."""
    __tablename__ = "crowd_consensus"

    id = Column(Integer, primary_key=True, index=True)
    address_id = Column(Integer, ForeignKey("addresses.id"), nullable=False, unique=True, index=True)

    # Consensus pickup days
    consensus_trash_day = Column(String)
    consensus_recycling_day = Column(String)
    consensus_green_day = Column(String)

    # Consensus metrics
    total_reports = Column(Integer, default=0)
    trash_agreement_ratio = Column(Float, default=0.0)
    recycling_agreement_ratio = Column(Float, default=0.0)
    green_agreement_ratio = Column(Float, default=0.0)

    # Verification status
    is_verified = Column(Boolean, default=False, index=True)  # True if meets threshold

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Composite indexes for common query patterns
    __table_args__ = (
        Index('idx_address_verified', 'address_id', 'is_verified'),
    )

class RequestMetrics(Base):
    """Track API request metrics for observability."""
    __tablename__ = "request_metrics"

    id = Column(Integer, primary_key=True, index=True)

    # Request details
    endpoint = Column(String, index=True, nullable=False)  # /lookup, /report
    method = Column(String)  # GET, POST
    status_code = Column(Integer, index=True)

    # Performance metrics
    response_time_ms = Column(Float)  # Response time in milliseconds

    # Geographic tracking
    city = Column(String, index=True)  # City from the request (if applicable)

    # Additional context
    error_message = Column(String)  # If request failed
    user_agent = Column(String)
    ip_address = Column(String)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
