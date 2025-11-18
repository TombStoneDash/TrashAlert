---
sidebar_position: 2
title: Database Schema
slug: /architecture/database
---

# Database Schema

Complete reference for the TrashAlert database design.

This documentation is based on `/home/user/TrashAlert/docs/data_model.md`. For full details, see that file.

## Core Tables

### cities
Stores information about supported cities.

```sql
CREATE TABLE cities (
  id INTEGER PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  state VARCHAR(2) NOT NULL,
  county VARCHAR(100),
  timezone VARCHAR(50),
  enabled BOOLEAN DEFAULT TRUE,
  extra_metadata JSONB,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  UNIQUE (name, state)
);
```

**Fields**:
- `id`: Primary key
- `name`: City name (e.g., "El Centro")
- `state`: State code (e.g., "CA")
- `county`: County name
- `timezone`: Timezone (e.g., "America/Los_Angeles")
- `enabled`: Whether city is active
- `extra_metadata`: Additional data as JSON

### addresses
Stores individual addresses with pickup information.

```sql
CREATE TABLE addresses (
  id INTEGER PRIMARY KEY,
  normalized_address VARCHAR(500) NOT NULL,
  house_number VARCHAR(20),
  street VARCHAR(200),
  city_slug VARCHAR(50) NOT NULL,
  city_name VARCHAR(100) NOT NULL,
  state VARCHAR(2),
  zip_code VARCHAR(10),
  lat FLOAT,
  lon FLOAT,

  -- Official schedule (from GIS)
  official_trash_day VARCHAR(20),
  official_recycling_day VARCHAR(20),
  official_green_day VARCHAR(20),

  created_at TIMESTAMP,
  updated_at TIMESTAMP,

  INDEX idx_normalized_address (normalized_address),
  INDEX idx_city_slug (city_slug),
  INDEX idx_lat_lon (lat, lon)
);
```

**Fields**:
- `normalized_address`: Standardized address string
- `house_number`: Street number
- `street`: Street name
- `city_slug`: City identifier (links to cities table)
- `lat`, `lon`: Geographic coordinates
- `official_*_day`: Official pickup days from municipal data

### crowd_reports
Individual user-submitted observations.

```sql
CREATE TABLE crowd_reports (
  id INTEGER PRIMARY KEY,
  address_id INTEGER NOT NULL,
  trash_day VARCHAR(20),
  recycling_day VARCHAR(20),
  green_day VARCHAR(20),
  user_hash VARCHAR(64),
  ip_address VARCHAR(45),
  created_at TIMESTAMP,

  FOREIGN KEY (address_id) REFERENCES addresses(id),
  INDEX idx_address_created (address_id, created_at),
  INDEX idx_user_hash (user_hash)
);
```

**Fields**:
- `address_id`: Which address this report is for
- `trash_day`, etc.: Observed pickup days
- `user_hash`: Anonymous user identifier
- `ip_address`: For rate limiting

### crowd_consensus
Aggregated consensus from reports.

```sql
CREATE TABLE crowd_consensus (
  id INTEGER PRIMARY KEY,
  address_id INTEGER NOT NULL UNIQUE,

  -- Consensus days
  consensus_trash_day VARCHAR(20),
  consensus_recycling_day VARCHAR(20),
  consensus_green_day VARCHAR(20),

  -- Metrics
  total_reports INTEGER DEFAULT 0,
  trash_agreement_ratio FLOAT DEFAULT 0,
  recycling_agreement_ratio FLOAT DEFAULT 0,
  green_agreement_ratio FLOAT DEFAULT 0,

  -- Verification
  is_verified BOOLEAN DEFAULT FALSE,

  created_at TIMESTAMP,
  updated_at TIMESTAMP,

  FOREIGN KEY (address_id) REFERENCES addresses(id),
  INDEX idx_verified (is_verified)
);
```

**Fields**:
- `address_id`: Associated address
- `consensus_*_day`: Most common pickup day
- `*_agreement_ratio`: Agreement percentage (0.0-1.0)
- `is_verified`: Meets verification threshold (≥3 reports, ≥67%)

### pickup_zones
Geographic zones within cities with distinct schedules.

```sql
CREATE TABLE pickup_zones (
  id INTEGER PRIMARY KEY,
  city_id INTEGER NOT NULL,
  name VARCHAR(200) NOT NULL,
  external_ref VARCHAR(100),
  extra_metadata JSONB,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,

  FOREIGN KEY (city_id) REFERENCES cities(id),
  INDEX idx_city_id (city_id),
  INDEX idx_external_ref (city_id, external_ref)
);
```

### schedules
Official pickup schedules for zones or cities.

```sql
CREATE TABLE schedules (
  id INTEGER PRIMARY KEY,
  city_id INTEGER NOT NULL,
  pickup_zone_id INTEGER,

  trash_day_of_week VARCHAR(20),
  recycling_day_of_week VARCHAR(20),
  green_waste_day_of_week VARCHAR(20),

  source VARCHAR(50),
  effective_date DATE,
  expiration_date DATE,

  FOREIGN KEY (city_id) REFERENCES cities(id),
  FOREIGN KEY (pickup_zone_id) REFERENCES pickup_zones(id),
  INDEX idx_city_id (city_id),
  INDEX idx_zone_id (pickup_zone_id)
);
```

### schedule_exceptions
Holidays and special schedule changes.

```sql
CREATE TABLE schedule_exceptions (
  id INTEGER PRIMARY KEY,
  city_id INTEGER NOT NULL,
  holiday_name VARCHAR(100),
  exception_date DATE NOT NULL,
  rule_description TEXT,
  affected_service_types VARCHAR(100),
  makeup_date DATE,
  source VARCHAR(50),

  FOREIGN KEY (city_id) REFERENCES cities(id),
  INDEX idx_exception_date (exception_date)
);
```

## Relationships

```
cities (1) ──── (N) addresses
            ├── (N) pickup_zones
            ├── (N) schedules
            └── (N) schedule_exceptions

addresses (1) ──── (N) crowd_reports
          ├── (1) crowd_consensus
          └── (1) address_pickup_info

pickup_zones (1) ──── (N) schedules
```

## Data Types

| Type | Purpose | Examples |
|------|---------|----------|
| INTEGER | IDs, counts | id, total_reports |
| VARCHAR(n) | Text fields | name, address, day |
| FLOAT | Decimal numbers | lat, lon, ratio |
| DATE | Dates | effective_date, exception_date |
| TIMESTAMP | Dates with time | created_at, updated_at |
| JSONB | Flexible data | extra_metadata |
| BOOLEAN | Yes/No | is_verified, enabled |

## Indexes

Indexes improve query performance:

```sql
-- Address lookup
CREATE INDEX idx_normalized_address ON addresses(normalized_address);
CREATE INDEX idx_city_slug ON addresses(city_slug);

-- Geospatial queries (PostGIS)
CREATE INDEX idx_location ON addresses USING GIST(location);

-- Report queries
CREATE INDEX idx_address_created ON crowd_reports(address_id, created_at);
CREATE INDEX idx_user_hash ON crowd_reports(user_hash);

-- Consensus queries
CREATE INDEX idx_consensus_verified ON crowd_consensus(is_verified);

-- Date-based queries
CREATE INDEX idx_exception_date ON schedule_exceptions(exception_date);
```

## Query Examples

### Find addresses in a city

```sql
SELECT * FROM addresses
WHERE city_slug = 'CA_EL_CENTRO'
ORDER BY street;
```

### Get consensus for an address

```sql
SELECT
  a.normalized_address,
  c.consensus_trash_day,
  c.total_reports,
  c.trash_agreement_ratio,
  c.is_verified
FROM addresses a
LEFT JOIN crowd_consensus c ON a.id = c.address_id
WHERE a.id = 123;
```

### Find addresses with verified consensus

```sql
SELECT COUNT(*) as verified_count
FROM crowd_consensus
WHERE is_verified = TRUE;
```

### Calculate consensus from reports

```sql
SELECT
  collection_day,
  COUNT(*) as report_count,
  COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as percentage
FROM crowd_reports
WHERE address_id = 123
  AND collection_type = 'trash'
  AND created_at > NOW() - INTERVAL '6 months'
GROUP BY collection_day
ORDER BY report_count DESC;
```

### Find nearby addresses

```sql
SELECT
  id,
  normalized_address,
  ST_Distance(location::geography,
              ST_SetSRID(ST_MakePoint(-115.2645, 32.7971), 4326)::geography)
    as distance_meters
FROM addresses
WHERE ST_DWithin(location::geography,
                 ST_SetSRID(ST_MakePoint(-115.2645, 32.7971), 4326)::geography,
                 1000)  -- 1km radius
ORDER BY distance_meters
LIMIT 10;
```

## Constraints

### Unique Constraints

```sql
-- One city per name/state
UNIQUE (cities.name, cities.state)

-- One consensus per address
UNIQUE (crowd_consensus.address_id)

-- One pickup info per address
UNIQUE (address_pickup_info.address_id)
```

### Check Constraints

```sql
-- Valid latitude
CHECK (lat BETWEEN -90 AND 90)

-- Valid longitude
CHECK (lon BETWEEN -180 AND 180)

-- Valid agreement ratio
CHECK (trash_agreement_ratio BETWEEN 0 AND 1)
```

### Foreign Keys

All foreign keys use `ON DELETE CASCADE` for data consistency:

```sql
FOREIGN KEY (address_id) REFERENCES addresses(id) ON DELETE CASCADE
```

Deleting a city cascades to delete all related addresses, reports, etc.

## Database Migrations

Use Alembic for schema changes:

```bash
# Generate migration
alembic revision --autogenerate -m "Add column"

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1
```

Example migration:

```python
# alembic/versions/001_initial.py
def upgrade():
    op.create_table(
        'addresses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('normalized_address', sa.String(500), nullable=False),
        # ...
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_normalized_address', 'addresses', ['normalized_address'])

def downgrade():
    op.drop_index('idx_normalized_address', 'addresses')
    op.drop_table('addresses')
```

## Performance Considerations

### Query Optimization

1. **Use indexes** on commonly queried columns
2. **Denormalize** when necessary (e.g., city_name on addresses)
3. **Cache** frequent queries
4. **Limit result sets** with pagination

### Scaling Strategy

- **Vertical**: More CPU/RAM/disk
- **Horizontal**: Read replicas for queries
- **Partitioning**: Split by city or date
- **Archiving**: Move old reports to archive table

### Monitoring

```sql
-- Check index usage
SELECT * FROM pg_stat_user_indexes;

-- Check table sizes
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables;

-- Check slow queries
EXPLAIN ANALYZE SELECT ...;
```

## Related Documentation

- **[System Architecture](/docs/architecture/overview)** - High-level design
- **[Crowdsourcing Logic](/docs/architecture/crowdsourcing)** - Consensus algorithm
- **[Data Pipeline](/docs/pipeline/overview)** - How data is collected

