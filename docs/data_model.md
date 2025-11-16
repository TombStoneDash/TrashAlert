# TrashAlert Data Model

## Overview

This document describes the database schema for the TrashAlert system, including all tables, their relationships, and key constraints.

## Database Technology

- **DBMS**: PostgreSQL 14+
- **Extensions**: PostGIS (for geospatial queries)
- **ORM**: SQLAlchemy (Python)

## Entity Relationship Diagram

```
┌─────────────────┐
│     cities      │
│─────────────────│
│ id (PK)         │
│ name            │
│ state           │
│ boundary_geom   │──┐
│ created_at      │  │
│ updated_at      │  │
└─────────────────┘  │
                     │ 1:N
                     │
                     ▼
              ┌─────────────────┐
              │   addresses     │
              │─────────────────│
              │ id (PK)         │
              │ city_id (FK)    │
              │ house_number    │
              │ street          │
              │ subdivision     │──┐
              │ latitude        │  │
              │ longitude       │  │
              │ osm_id          │  │
              │ created_at      │  │
              │ updated_at      │  │
              └─────────────────┘  │
                     │              │ 1:N
                     │              │
          ┌──────────┴──────────┐  │
          │ 1:N                 │  │
          ▼                     ▼  │
┌─────────────────┐   ┌─────────────────┐
│  user_reports   │   │trash_schedules  │
│─────────────────│   │─────────────────│
│ id (PK)         │   │ id (PK)         │
│ address_id (FK) │   │ address_id (FK) │
│ user_token      │   │ collection_type │
│ collection_day  │   │ collection_day  │
│ collection_type │   │ recurrence      │
│ reported_at     │   │ confidence      │
│ is_verified     │   │ report_count    │
│ created_at      │   │ last_updated    │
└─────────────────┘   │ created_at      │
          │           └─────────────────┘
          │                     ▲
          └─────────┬───────────┘
                    │
                    │ N:1 (consensus calculation)
                    │
          ┌─────────▼───────────┐
          │ schedule_conflicts  │
          │─────────────────────│
          │ id (PK)             │
          │ address_id (FK)     │
          │ collection_type     │
          │ conflict_details    │
          │ detected_at         │
          │ resolved            │
          │ created_at          │
          └─────────────────────┘
```

## Table Definitions

### 1. cities

Stores information about supported cities and their geographic boundaries.

```sql
CREATE TABLE cities (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    state VARCHAR(2) NOT NULL,
    county VARCHAR(100),
    boundary_geom GEOMETRY(POLYGON, 4326),
    population INTEGER,
    area_sq_km DECIMAL(10, 2),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT cities_name_state_unique UNIQUE (name, state)
);

CREATE INDEX idx_cities_boundary ON cities USING GIST (boundary_geom);
CREATE INDEX idx_cities_name ON cities (name);
```

**Columns**:
- `id`: Primary key
- `name`: City name (e.g., "San Diego", "El Centro")
- `state`: Two-letter state code (e.g., "CA")
- `county`: County name (e.g., "San Diego County", "Imperial County")
- `boundary_geom`: PostGIS polygon representing city boundaries
- `population`: Estimated population (optional)
- `area_sq_km`: City area in square kilometers
- `metadata`: Additional city information as JSON (e.g., timezone, official website)
- `created_at`: Record creation timestamp
- `updated_at`: Last update timestamp

**Indexes**:
- Spatial index on `boundary_geom` for efficient geospatial queries
- Index on `name` for quick city lookups

---

### 2. addresses

Stores individual addresses sampled from OpenStreetMap.

```sql
CREATE TABLE addresses (
    id SERIAL PRIMARY KEY,
    city_id INTEGER NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    house_number VARCHAR(20) NOT NULL,
    street VARCHAR(200) NOT NULL,
    subdivision VARCHAR(100),
    latitude DECIMAL(10, 7) NOT NULL,
    longitude DECIMAL(11, 7) NOT NULL,
    location GEOMETRY(POINT, 4326),
    osm_id VARCHAR(50),
    osm_type VARCHAR(20),
    full_address TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT addresses_unique UNIQUE (city_id, house_number, street),
    CONSTRAINT addresses_lat_check CHECK (latitude BETWEEN -90 AND 90),
    CONSTRAINT addresses_lon_check CHECK (longitude BETWEEN -180 AND 180)
);

CREATE INDEX idx_addresses_city ON addresses (city_id);
CREATE INDEX idx_addresses_location ON addresses USING GIST (location);
CREATE INDEX idx_addresses_street ON addresses (street);
CREATE INDEX idx_addresses_subdivision ON addresses (subdivision);
CREATE INDEX idx_addresses_osm ON addresses (osm_id);

-- Trigger to auto-populate location from lat/lon
CREATE OR REPLACE FUNCTION update_address_location()
RETURNS TRIGGER AS $$
BEGIN
    NEW.location = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_address_location
    BEFORE INSERT OR UPDATE ON addresses
    FOR EACH ROW
    EXECUTE FUNCTION update_address_location();
```

**Columns**:
- `id`: Primary key
- `city_id`: Foreign key to cities table
- `house_number`: Street number (e.g., "1234", "1234A")
- `street`: Street name (e.g., "Main St", "Broadway Ave")
- `subdivision`: Neighborhood/subdivision name (optional)
- `latitude`: GPS latitude (WGS84)
- `longitude`: GPS longitude (WGS84)
- `location`: PostGIS point geometry (auto-populated from lat/lon)
- `osm_id`: OpenStreetMap node/way ID
- `osm_type`: OSM element type (e.g., "node", "way")
- `full_address`: Complete formatted address
- `metadata`: Additional address data as JSON
- `created_at`: Record creation timestamp
- `updated_at`: Last update timestamp

**Constraints**:
- Unique constraint on (city_id, house_number, street) to prevent duplicates
- Check constraints on latitude/longitude ranges

**Indexes**:
- Index on `city_id` for filtering by city
- Spatial index on `location` for proximity queries
- Indexes on `street` and `subdivision` for search

---

### 3. user_reports

Stores individual trash day reports submitted by users (crowdsourced data).

```sql
CREATE TABLE user_reports (
    id SERIAL PRIMARY KEY,
    address_id INTEGER NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    user_token VARCHAR(64),
    collection_day VARCHAR(20) NOT NULL,
    collection_type VARCHAR(20) NOT NULL,
    notes TEXT,
    is_verified BOOLEAN DEFAULT FALSE,
    verified_by VARCHAR(64),
    verified_at TIMESTAMP,
    reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT reports_collection_day_check
        CHECK (collection_day IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday',
                                   'Friday', 'Saturday', 'Sunday')),
    CONSTRAINT reports_collection_type_check
        CHECK (collection_type IN ('trash', 'recycling', 'green_waste', 'bulk'))
);

CREATE INDEX idx_reports_address ON user_reports (address_id);
CREATE INDEX idx_reports_user ON user_reports (user_token);
CREATE INDEX idx_reports_reported_at ON user_reports (reported_at);
CREATE INDEX idx_reports_collection ON user_reports (address_id, collection_type);
```

**Columns**:
- `id`: Primary key
- `address_id`: Foreign key to addresses table
- `user_token`: Anonymous user identifier (hashed, for rate limiting)
- `collection_day`: Day of week for collection
- `collection_type`: Type of collection (trash, recycling, etc.)
- `notes`: Optional user comments
- `is_verified`: Whether report has been manually verified
- `verified_by`: Admin/moderator who verified
- `verified_at`: Verification timestamp
- `reported_at`: When user observed the collection
- `created_at`: Record creation timestamp

**Constraints**:
- Check constraint ensuring valid days of week
- Check constraint ensuring valid collection types

**Indexes**:
- Index on `address_id` for aggregating reports per address
- Index on `user_token` for user activity tracking
- Index on `reported_at` for recency-based queries
- Composite index on (address_id, collection_type) for consensus calculation

---

### 4. trash_schedules

Stores the consensus trash collection schedule for each address, computed from user reports.

```sql
CREATE TABLE trash_schedules (
    id SERIAL PRIMARY KEY,
    address_id INTEGER NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    collection_type VARCHAR(20) NOT NULL,
    collection_day VARCHAR(20) NOT NULL,
    recurrence VARCHAR(20) DEFAULT 'weekly',
    confidence_score DECIMAL(5, 2) NOT NULL,
    report_count INTEGER NOT NULL,
    agreement_percentage DECIMAL(5, 2),
    last_reported_at TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT schedules_address_type_unique UNIQUE (address_id, collection_type),
    CONSTRAINT schedules_confidence_check CHECK (confidence_score BETWEEN 0 AND 100),
    CONSTRAINT schedules_agreement_check CHECK (agreement_percentage BETWEEN 0 AND 100),
    CONSTRAINT schedules_collection_day_check
        CHECK (collection_day IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday',
                                   'Friday', 'Saturday', 'Sunday')),
    CONSTRAINT schedules_collection_type_check
        CHECK (collection_type IN ('trash', 'recycling', 'green_waste', 'bulk'))
);

CREATE INDEX idx_schedules_address ON trash_schedules (address_id);
CREATE INDEX idx_schedules_confidence ON trash_schedules (confidence_score);
CREATE INDEX idx_schedules_type ON trash_schedules (collection_type);
```

**Columns**:
- `id`: Primary key
- `address_id`: Foreign key to addresses table
- `collection_type`: Type of collection
- `collection_day`: Consensus day of week
- `recurrence`: Frequency (weekly, biweekly, monthly)
- `confidence_score`: Overall confidence (0-100)
- `report_count`: Total number of reports used
- `agreement_percentage`: Percentage of reports agreeing on this day
- `last_reported_at`: Most recent report timestamp
- `last_updated`: When consensus was last recalculated
- `created_at`: Record creation timestamp

**Constraints**:
- Unique constraint on (address_id, collection_type) - one schedule per type per address
- Check constraints on confidence_score and agreement_percentage ranges
- Check constraints on valid days and collection types

**Indexes**:
- Index on `address_id` for schedule lookups
- Index on `confidence_score` for quality filtering

---

### 5. schedule_conflicts

Tracks addresses where user reports conflict significantly, requiring manual review.

```sql
CREATE TABLE schedule_conflicts (
    id SERIAL PRIMARY KEY,
    address_id INTEGER NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    collection_type VARCHAR(20) NOT NULL,
    conflict_details JSONB NOT NULL,
    severity VARCHAR(20) DEFAULT 'medium',
    resolved BOOLEAN DEFAULT FALSE,
    resolved_by VARCHAR(64),
    resolved_at TIMESTAMP,
    resolution_notes TEXT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT conflicts_severity_check
        CHECK (severity IN ('low', 'medium', 'high'))
);

CREATE INDEX idx_conflicts_address ON schedule_conflicts (address_id);
CREATE INDEX idx_conflicts_resolved ON schedule_conflicts (resolved);
CREATE INDEX idx_conflicts_severity ON schedule_conflicts (severity);
```

**Columns**:
- `id`: Primary key
- `address_id`: Foreign key to addresses table
- `collection_type`: Type of collection with conflict
- `conflict_details`: JSON object with conflicting report counts
  ```json
  {
    "Monday": 3,
    "Wednesday": 5,
    "Friday": 2
  }
  ```
- `severity`: Conflict severity level
- `resolved`: Whether conflict has been resolved
- `resolved_by`: Admin who resolved the conflict
- `resolved_at`: Resolution timestamp
- `resolution_notes`: Explanation of resolution
- `detected_at`: When conflict was first detected
- `created_at`: Record creation timestamp

**Indexes**:
- Index on `address_id` for address-specific conflicts
- Index on `resolved` to filter unresolved conflicts
- Index on `severity` for prioritization

---

## Common Queries

### 1. Find addresses in a city

```sql
SELECT a.*, c.name as city_name
FROM addresses a
JOIN cities c ON a.city_id = c.id
WHERE c.name = 'San Diego';
```

### 2. Get trash schedule for an address

```sql
SELECT
    a.house_number,
    a.street,
    ts.collection_type,
    ts.collection_day,
    ts.confidence_score,
    ts.report_count
FROM addresses a
LEFT JOIN trash_schedules ts ON a.id = ts.address_id
WHERE a.id = 123;
```

### 3. Calculate consensus for an address

```sql
WITH report_counts AS (
    SELECT
        collection_day,
        COUNT(*) as count,
        MAX(reported_at) as last_report
    FROM user_reports
    WHERE address_id = 123
      AND collection_type = 'trash'
      AND reported_at > NOW() - INTERVAL '6 months'
    GROUP BY collection_day
),
total_reports AS (
    SELECT SUM(count) as total
    FROM report_counts
)
SELECT
    rc.collection_day,
    rc.count,
    ROUND((rc.count::DECIMAL / tr.total * 100), 2) as agreement_percentage,
    rc.last_report
FROM report_counts rc
CROSS JOIN total_reports tr
ORDER BY rc.count DESC;
```

### 4. Find addresses near a location

```sql
SELECT
    a.id,
    a.house_number,
    a.street,
    ST_Distance(
        a.location::geography,
        ST_SetSRID(ST_MakePoint(-117.1611, 32.7157), 4326)::geography
    ) as distance_meters
FROM addresses a
WHERE ST_DWithin(
    a.location::geography,
    ST_SetSRID(ST_MakePoint(-117.1611, 32.7157), 4326)::geography,
    1000  -- 1km radius
)
ORDER BY distance_meters;
```

### 5. Detect schedule conflicts

```sql
WITH day_counts AS (
    SELECT
        address_id,
        collection_type,
        collection_day,
        COUNT(*) as report_count,
        COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY address_id, collection_type) as percentage
    FROM user_reports
    WHERE reported_at > NOW() - INTERVAL '6 months'
    GROUP BY address_id, collection_type, collection_day
),
conflicts AS (
    SELECT
        address_id,
        collection_type,
        COUNT(*) as days_reported,
        MAX(percentage) as max_agreement
    FROM day_counts
    GROUP BY address_id, collection_type
    HAVING COUNT(*) > 1 AND MAX(percentage) < 75
)
SELECT
    a.house_number,
    a.street,
    c.collection_type,
    c.days_reported,
    c.max_agreement
FROM conflicts c
JOIN addresses a ON c.address_id = a.id
ORDER BY c.max_agreement;
```

## Data Relationships

### One-to-Many Relationships

1. **cities → addresses**: One city contains many addresses
2. **addresses → user_reports**: One address can have many user reports
3. **addresses → trash_schedules**: One address can have multiple schedules (one per collection type)
4. **addresses → schedule_conflicts**: One address can have multiple conflicts

### Derived Relationships

1. **user_reports → trash_schedules**: Many reports are aggregated to compute one consensus schedule
2. **user_reports → schedule_conflicts**: Conflicting reports trigger conflict records

## Data Integrity Rules

### Referential Integrity
- All foreign keys use `ON DELETE CASCADE` to maintain consistency
- Deleting a city removes all its addresses and related data
- Deleting an address removes all reports, schedules, and conflicts

### Data Validation
- Latitude must be between -90 and 90
- Longitude must be between -180 and 180
- Collection days must be valid day names
- Collection types must be from predefined list
- Confidence scores must be 0-100
- Agreement percentages must be 0-100

### Uniqueness Constraints
- Cities are unique by (name, state)
- Addresses are unique by (city_id, house_number, street)
- Schedules are unique by (address_id, collection_type)

## Performance Considerations

### Indexes
- All foreign keys are indexed for join performance
- Geospatial indexes (GIST) on geometry columns
- Composite indexes on frequently queried combinations
- Indexes on timestamp columns for date range queries

### Partitioning (Future)
For scale, consider partitioning:
- `user_reports` by `reported_at` (monthly partitions)
- `addresses` by `city_id` (if supporting many cities)

### Materialized Views (Future)
Pre-compute expensive aggregations:
- Current consensus schedules with confidence
- Address coverage statistics per city
- Daily report submission counts

## Schema Migration

Use a migration tool like Alembic for version control:

```python
# Example Alembic migration
def upgrade():
    op.create_table(
        'cities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('state', sa.String(2), nullable=False),
        # ... more columns
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('cities')
```

## Backup and Maintenance

### Recommended Practices
- Daily automated backups
- Point-in-time recovery enabled
- Regular VACUUM and ANALYZE for performance
- Monitor table bloat and index health
- Archive old user_reports (>1 year) to separate table

### Data Retention
- `user_reports`: Keep last 2 years, archive older
- `schedule_conflicts`: Keep only unresolved + last 1 year resolved
- `trash_schedules`: Keep all (current consensus)
- `addresses`: Keep all (core data)
- `cities`: Keep all (reference data)
