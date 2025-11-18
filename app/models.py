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

# Import AI cache model to ensure it's registered with Base metadata
from app.ai_cache import AIClassificationCache  # noqa: F401


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
    addresses = relationship("Address", back_populates="city_relation")
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

    __table_args__ = (
        Index('idx_pickup_zone_city_ref', 'city_id', 'external_ref'),
    )


class Address(Base):
    """Address table - stores normalized addresses with pickup information."""
    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True, index=True)

    # City relationship (integer FK to cities table)
    city_table_id = Column(Integer, ForeignKey("cities.id"), nullable=True, index=True)

    # Address fields
    normalized_address = Column(String, index=True, nullable=False)
    house_number = Column(String)
    street = Column(String, index=True)
    city = Column(String, index=True)  # City name (denormalized)
    city_id = Column(String, index=True)  # Links to cities.yaml (e.g., 'san_diego', 'fresno')
    city = Column(String, index=True)
    city_slug = Column(String, index=True)  # Links to cities.yaml (e.g., 'san_diego', 'fresno')
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
    city_relation = relationship("City", back_populates="addresses", foreign_keys=[city_table_id])


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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)  # For gamification

    # Verification status
    is_verified = Column(Boolean, default=False, index=True)
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


class PredictionModel(Base):
    """Store trained prediction models and their metadata."""
    __tablename__ = "prediction_models"

    id = Column(Integer, primary_key=True, index=True)

    # Model identification
    model_type = Column(String, nullable=False, index=True)  # 'delay', 'seasonal'
    version = Column(String, nullable=False)  # Semantic version

    # Model storage
    model_data = Column(Text, nullable=False)  # Base64-encoded model pickle

    # Training metadata
    training_samples = Column(Integer, default=0)
    training_accuracy = Column(Float)
    training_features = Column(JSON)  # List of features used

    # Model status
    is_active = Column(Boolean, default=False, index=True)  # Only one active model per type

    # Timestamps
class User(Base):
    """User table for gamification and authentication."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    # Gamification stats
    total_points = Column(Integer, default=0, index=True)
    total_reports = Column(Integer, default=0)
    verified_reports = Column(Integer, default=0)

    # User status
    is_active = Column(Boolean, default=True)
    is_verified_reporter = Column(Boolean, default=False, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))

    # Relationships
    badges = relationship("UserBadge", back_populates="user")
    point_history = relationship("PointHistory", back_populates="user")


class Badge(Base):
    """Badge definitions for gamification."""
    __tablename__ = "badges"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text)
    icon = Column(String)  # Icon name or URL

    # Badge criteria
    requirement_type = Column(String, nullable=False)  # verified_reports, total_reports, power_user
    requirement_value = Column(Integer)  # Threshold to earn badge

    # Display
    color = Column(String)  # Hex color for badge display
    tier = Column(Integer, default=1)  # Badge tier (1=bronze, 2=silver, 3=gold)
class PipelineRun(Base):
    """Track bulk pipeline execution runs."""
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, index=True)

    # Run metadata
    run_type = Column(String, nullable=False)  # full, incremental, repair
    status = Column(String, nullable=False, index=True)  # pending, running, completed, failed, paused

    # Filters used
    city_filter = Column(String)  # city_id, state, or 'all'

    # Progress tracking
    total_cities = Column(Integer, default=0)
    completed_cities = Column(Integer, default=0)
    failed_cities = Column(Integer, default=0)

    # Statistics
    total_addresses_fetched = Column(Integer, default=0)
    total_addresses_processed = Column(Integer, default=0)

    # Error tracking
    last_error = Column(Text)
    error_count = Column(Integer, default=0)

    # Checkpoint for resumability
    last_processed_city_id = Column(String, index=True)
    checkpoint_data = Column(JSON)  # Flexible JSON for checkpoint state

    # Timestamps
    started_at = Column(DateTime(timezone=True), index=True)
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('idx_model_type_active', 'model_type', 'is_active'),
    )


class PredictionCache(Base):
    """Cache prediction results to avoid recomputation."""
    __tablename__ = "prediction_cache"

    id = Column(Integer, primary_key=True, index=True)

    # Prediction key
    address_id = Column(Integer, ForeignKey("addresses.id"), nullable=False, index=True)
    prediction_type = Column(String, nullable=False, index=True)  # 'delay', 'seasonal'

    # Prediction results
    prediction_result = Column(JSON, nullable=False)  # Stores the prediction data
    confidence = Column(Float)

    # Model tracking
    model_version = Column(String)

    # Cache metadata
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_prediction_cache_lookup', 'address_id', 'prediction_type', 'expires_at'),
        Index('idx_pipeline_run_status_started', 'status', 'started_at'),
    )


class PipelineCityStatus(Base):
    """Track per-city status within a pipeline run."""
    __tablename__ = "pipeline_city_status"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_run_id = Column(Integer, ForeignKey("pipeline_runs.id"), nullable=False, index=True)

    # City information
    city_id = Column(String, nullable=False, index=True)
    city_name = Column(String, nullable=False)

    # Status
    status = Column(String, nullable=False, index=True)  # pending, running, completed, failed, skipped

    # Step tracking
    current_step = Column(String)  # boundaries, subdivisions, addresses, sampling, normalization
    steps_completed = Column(JSON)  # List of completed step names

    # Statistics
    addresses_fetched = Column(Integer, default=0)
    addresses_sampled = Column(Integer, default=0)
    addresses_normalized = Column(Integer, default=0)

    # Error handling
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)

    # Timestamps
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('idx_city_status_run_city', 'pipeline_run_id', 'city_id'),
        Index('idx_city_status_status', 'status'),
class APIKey(Base):
    """B2B API keys for authenticated access."""
class ApiKey(Base):
    """API keys for mobile and third-party access."""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)

    # Key information
    key_hash = Column(String, unique=True, nullable=False, index=True)  # Hashed version of the API key
    key_prefix = Column(String, nullable=False, index=True)  # First 8 chars for identification (e.g., "ta_live_")

    # Owner information
    company_name = Column(String, nullable=False)
    contact_email = Column(String)

    # Status and limits
    is_active = Column(Boolean, default=True, index=True)
    rate_limit_per_minute = Column(Integer, default=60)
    rate_limit_per_hour = Column(Integer, default=1000)
    rate_limit_per_day = Column(Integer, default=10000)

    # Usage metadata
    last_used_at = Column(DateTime(timezone=True))
    total_requests = Column(Integer, default=0)

    # Notes and metadata
    notes = Column(Text)  # Admin notes about this key
    extra_metadata = Column(JSON)  # Flexible JSON for additional data
    # Key details
    key = Column(String, unique=True, index=True, nullable=False)  # The actual API key (hashed)
    key_prefix = Column(String, index=True)  # First 8 chars for identification (unhashed)
    name = Column(String, nullable=False)  # Human-readable name (e.g., "iOS App v1.0")
    description = Column(Text)  # Optional description

    # Authorization
    is_active = Column(Boolean, default=True, index=True)
    scopes = Column(JSON, default=list)  # ["mobile:lookup", "mobile:report"]

    # Rate limiting (per API key, in addition to IP-based)
    rate_limit_per_minute = Column(Integer, default=30)  # More restrictive than IP
    rate_limit_per_hour = Column(Integer, default=500)

    # Usage tracking
    total_requests = Column(Integer, default=0)
    last_used_at = Column(DateTime(timezone=True))

    # Expiration
    expires_at = Column(DateTime(timezone=True))  # Optional expiration

    # Metadata
    created_by = Column(String)  # Who created this key
    extra_metadata = Column(JSON)  # Additional metadata

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class UserBadge(Base):
    """User badge awards - tracks which badges users have earned."""
    __tablename__ = "user_badges"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    badge_id = Column(Integer, ForeignKey("badges.id"), nullable=False, index=True)

    # Award metadata
    earned_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    email_sent = Column(Boolean, default=False)
    email_sent_at = Column(DateTime(timezone=True))

    # Relationships
    user = relationship("User", back_populates="badges")
    badge = relationship("Badge")

    __table_args__ = (
        Index('idx_user_badge_unique', 'user_id', 'badge_id', unique=True),
    )


class PointHistory(Base):
    """Track point awards and changes for transparency."""
    __tablename__ = "point_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Point details
    points = Column(Integer, nullable=False)  # Can be positive or negative
    action = Column(String, nullable=False)  # report_submitted, report_verified, bonus
    description = Column(String)

    # Reference to related entity
    report_id = Column(Integer, ForeignKey("crowd_reports.id"), nullable=True, index=True)
    expires_at = Column(DateTime(timezone=True))  # Optional expiration

    # Relationships
    usage_logs = relationship("APIUsage", back_populates="api_key")

    __table_args__ = (
        Index('idx_apikey_active_hash', 'is_active', 'key_hash'),
    )


class APIUsage(Base):
    """Track per-key API usage for analytics and billing."""
    __tablename__ = "api_usage"

    id = Column(Integer, primary_key=True, index=True)

    # API key reference

    # Relationships
    usage_logs = relationship("ApiKeyUsage", back_populates="api_key")

    __table_args__ = (
        Index('idx_api_key_active', 'is_active', 'expires_at'),
    )


class ApiKeyUsage(Base):
    """Track API key usage for analytics and abuse detection."""
    __tablename__ = "api_key_usage"

    id = Column(Integer, primary_key=True, index=True)

    # Foreign key
    api_key_id = Column(Integer, ForeignKey("api_keys.id"), nullable=False, index=True)

    # Request details
    endpoint = Column(String, index=True, nullable=False)
    method = Column(String)
    status_code = Column(Integer, index=True)

    # Performance metrics
    response_time_ms = Column(Float)

    # Request metadata
    ip_address = Column(String)
    user_agent = Column(String)

    # Error tracking
    error_message = Column(String)

    status_code = Column(Integer)
    response_time_ms = Column(Float)

    # Context
    ip_address = Column(String)
    user_agent = Column(String)

    # Timestamp
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user = relationship("User", back_populates="point_history")

    __table_args__ = (
        Index('idx_user_created', 'user_id', 'created_at'),
    api_key = relationship("APIKey", back_populates="usage_logs")

    __table_args__ = (
        Index('idx_apiusage_key_created', 'api_key_id', 'created_at'),
        Index('idx_apiusage_key_endpoint', 'api_key_id', 'endpoint'),
    api_key = relationship("ApiKey", back_populates="usage_logs")

    __table_args__ = (
        Index('idx_api_key_usage_lookup', 'api_key_id', 'created_at'),
    )
