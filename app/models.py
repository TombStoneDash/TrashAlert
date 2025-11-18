"""Database models for TrashAlert."""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, JSON
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


class Schedule(Base):
    """Official trash collection schedules extracted from city sources."""
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    address_id = Column(Integer, ForeignKey("addresses.id"), nullable=True, index=True)  # Nullable for pilot

    # Schedule information
    day_of_week = Column(String, nullable=False)  # MON, TUE, WED, THU, FRI, SAT, SUN
    collection_type = Column(String, nullable=False)  # trash, recycling, green_waste
    zone = Column(String)  # Pickup zone identifier (if city uses zones)
    recurrence = Column(String, default="weekly")  # weekly, biweekly, monthly

    # Metadata
    source_id = Column(Integer, ForeignKey("source_metadata.id"))
    confidence = Column(Float, default=1.0)  # 0.0 - 1.0

    # Timestamps
    effective_date = Column(DateTime(timezone=True))  # When this schedule becomes effective
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ScheduleException(Base):
    """Holiday exceptions and special pickup date changes."""
    __tablename__ = "schedule_exceptions"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(Integer, ForeignKey("schedules.id"), nullable=True, index=True)  # Nullable for pilot

    # Exception details
    exception_date = Column(DateTime(timezone=True), nullable=False, index=True)  # The holiday/exception date
    rescheduled_date = Column(DateTime(timezone=True))  # New pickup date (if rescheduled)
    is_cancelled = Column(Boolean, default=False)  # True if pickup is cancelled, not rescheduled

    # Description
    reason = Column(String)  # e.g., "Christmas", "Thanksgiving", "City Holiday"
    notes = Column(Text)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SourceMetadata(Base):
    """Metadata about schedule data sources (PDFs, websites, etc.)."""
    __tablename__ = "source_metadata"

    id = Column(Integer, primary_key=True, index=True)

    # Source identification
    city = Column(String, nullable=False, index=True)
    source_type = Column(String, nullable=False)  # pdf, html, api, manual
    source_url = Column(String)  # URL where data was obtained
    source_name = Column(String)  # Descriptive name (e.g., "2024 Trash Calendar PDF")

    # Parsing information
    parser_version = Column(String)  # Version of parser used
    parser_name = Column(String)  # Name of parser module

    # Data quality
    total_records_extracted = Column(Integer, default=0)
    successful_records = Column(Integer, default=0)
    failed_records = Column(Integer, default=0)

    # Additional metadata
    extra_data = Column(JSON)  # Flexible JSON field for parser-specific data

    # Timestamps
    last_fetched_at = Column(DateTime(timezone=True))
    last_parsed_at = Column(DateTime(timezone=True))
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
