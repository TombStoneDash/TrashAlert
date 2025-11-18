"""Database models for TrashAlert."""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, JSON, Index, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    """User role enum."""
    USER = "user"
    REPORTER = "reporter"
    ADMIN = "admin"
    CITY_PARTNER = "city_partner"


class User(Base):
    """User table - stores user accounts for authentication."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False, index=True)

    # User status
    is_active = Column(Boolean, default=True, index=True)
    is_verified = Column(Boolean, default=False)

    # Metadata
    full_name = Column(String)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=True)  # For city_partner role

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True))

    # Relationships
    city = relationship("City")
    crowd_reports = relationship("CrowdReport", back_populates="user")


class City(Base):
    """City table - stores cities supported by TrashAlert."""
    __tablename__ = "cities"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True, nullable=False)  # URL-friendly identifier
    name = Column(String, nullable=False)
    state = Column(String, index=True)
    county = Column(String)
    region = Column(String)
    timezone = Column(String, default="America/Los_Angeles")
    enabled = Column(Boolean, default=True, index=True)
    extra_metadata = Column(JSON)  # Flexible JSON for additional city-specific data

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    addresses = relationship("Address", back_populates="city")
    pickup_zones = relationship("PickupZone", back_populates="city")


class PickupZone(Base):
    """Pickup zones - GIS or rule-based groupings for trash collection."""
    __tablename__ = "pickup_zones"

    id = Column(Integer, primary_key=True, index=True)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    external_ref = Column(String)  # External identifier from city GIS system
    extra_metadata = Column(JSON)  # Flexible JSON for zone-specific data (geometry, etc.)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    city = relationship("City", back_populates="pickup_zones")

    __table_args__ = (
        Index('idx_pickup_zone_city_ref', 'city_id', 'external_ref'),
    )


class Address(Base):
    """Address table - stores normalized addresses with pickup information."""
    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True, index=True)

    # City relationship
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=True, index=True)

    # Address fields
    normalized_address = Column(String, index=True, nullable=False)
    house_number = Column(String)
    street = Column(String, index=True)
    city = Column(String, index=True)
    city_id = Column(String, index=True)  # Links to cities.yaml (e.g., 'san_diego', 'fresno')
    city_name = Column(String, index=True)  # Denormalized for backward compatibility
    state = Column(String, index=True)  # Added index for filtering by state
    zip_code = Column(String, index=True)  # Added index for filtering by zip

    # Coordinates
    lat = Column(Float)
    lon = Column(Float)

    # Official pickup schedule (from GIS/rules) - keeping for backward compatibility
    official_trash_day = Column(String)  # MON, TUE, WED, THU, FRI
    official_recycling_day = Column(String)
    official_green_day = Column(String)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    city = relationship("City", back_populates="addresses")


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
    user_hash = Column(String, index=True)  # Keep for backward compatibility
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # New authenticated user reference

    # Verification
    is_verified = Column(Boolean, default=False, index=True)
    verified_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime(timezone=True))

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    ip_address = Column(String, index=True)  # Index for spam prevention queries

    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="crowd_reports")
    verified_by = relationship("User", foreign_keys=[verified_by_user_id])

    # Composite indexes for common query patterns
    __table_args__ = (
        Index('idx_address_created', 'address_id', 'created_at'),
        Index('idx_user_created', 'user_id', 'created_at'),
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


class AddressPickupInfo(Base):
    """Per-address view merging official schedule + crowdsourced data."""
    __tablename__ = "address_pickup_info"

    id = Column(Integer, primary_key=True, index=True)
    address_id = Column(Integer, ForeignKey("addresses.id"), nullable=False, unique=True, index=True)
    pickup_zone_id = Column(Integer, ForeignKey("pickup_zones.id"), nullable=True, index=True)

    # Consolidated pickup schedule (from official or crowd consensus)
    trash_day_of_week = Column(String)
    recycling_day_of_week = Column(String)
    green_day_of_week = Column(String)

    # Source tracking
    source = Column(String, default="OFFICIAL")  # OFFICIAL, CROWD, HYBRID

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('idx_address_pickup_zone', 'address_id', 'pickup_zone_id'),
    )


class Schedule(Base):
    """Official trash collection schedules per zone or address."""
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=False, index=True)
    pickup_zone_id = Column(Integer, ForeignKey("pickup_zones.id"), nullable=True, index=True)

    # Schedule information - consolidated for simplicity
    trash_day_of_week = Column(String)  # MON, TUE, WED, THU, FRI, SAT, SUN
    recycling_day_of_week = Column(String)
    green_day_of_week = Column(String)

    # Source and metadata
    source = Column(String, default="OFFICIAL")  # OFFICIAL, GIS, MANUAL, etc.
    extra_metadata = Column(JSON)  # Flexible JSON for additional schedule data

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('idx_schedule_city_zone', 'city_id', 'pickup_zone_id'),
    )


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
