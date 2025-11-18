---
sidebar_position: 1
title: Data Pipeline Overview
slug: /pipeline/overview
---

# Data Pipeline Overview

The TrashAlert data pipeline extracts, processes, and manages address data from multiple sources.

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  DATA COLLECTION SOURCES                     │
├─────────────────────────────────────────────────────────────┤
│  - OpenStreetMap (OSM)                                      │
│  - City GIS Data                                            │
│  - Manual Address Input                                     │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
        ┌────────────────────┐
        │  1. OSM Extraction │
        │  ├─ Overpass API   │
        │  └─ Filter by city │
        └────────┬───────────┘
                 │
                 ▼
        ┌────────────────────┐
        │  2. Normalization  │
        │  ├─ Clean data     │
        │  ├─ Standardize    │
        │  └─ Remove dupes   │
        └────────┬───────────┘
                 │
                 ▼
        ┌────────────────────┐
        │  3. Sampling       │
        │  ├─ Geographic     │
        │  ├─ Stratified     │
        │  └─ 50/city target │
        └────────┬───────────┘
                 │
                 ▼
        ┌────────────────────┐
        │  4. Geocoding      │
        │  ├─ Get coords     │
        │  ├─ Validate       │
        │  └─ Reverse lookup │
        └────────┬───────────┘
                 │
                 ▼
        ┌────────────────────┐
        │  5. Database Ingest│
        │  ├─ Upsert         │
        │  ├─ Validate FK    │
        │  └─ Index          │
        └────────┬───────────┘
                 │
                 ▼
        ┌────────────────────┐
        │  6. QA/Validation  │
        │  ├─ Dedup check    │
        │  ├─ Coverage stats │
        │  └─ Report results │
        └────────┬───────────┘
                 │
                 ▼
        ┌────────────────────┐
        │  READY FOR QUERIES │
        └────────────────────┘
```

## Pipeline Components

### 1. OSM Collection

Extracts address data from OpenStreetMap.

- **Technology**: Overpass API
- **Frequency**: Weekly or on-demand
- **Input**: City boundaries (GeoJSON)
- **Output**: Raw addresses with coordinates

See [OSM Collection](/docs/pipeline/osm-collection) for details.

### 2. Address Sampling

Selects representative sample of addresses.

- **Strategy**: Stratified sampling by subdivision
- **Target**: 50 addresses per city
- **Goal**: Geographic coverage without excessive data
- **Output**: Sampled address list (CSV)

See [Address Sampling](/docs/pipeline/address-sampling) for details.

### 3. Normalization

Standardizes address format.

- **Uppercase conversion**
- **Street type abbreviation** (Street → St)
- **Directional abbreviation** (North → N)
- **Space normalization**
- **Output**: Normalized addresses with full details

### 4. Geocoding

Converts addresses to coordinates.

- **Service**: Nominatim (reverse geocoding)
- **Rate limiting**: 1 request/sec
- **Fallback**: Manual coordinates
- **Output**: Addresses with lat/lon

### 5. Database Ingest

Loads processed data into database.

- **Method**: Batch upsert
- **Validation**: Foreign keys, constraints
- **Indexing**: Create performance indexes
- **Deduplication**: Handle duplicates

### 6. QA/Validation

Verifies data quality.

- **Coverage metrics**: Addresses per city
- **Completeness**: Required fields present
- **Accuracy**: Sample verification
- **Reports**: Email summary to maintainers

## Data Flow

### Typical Pipeline Run

```bash
# Start pipeline for single city
python scripts/run_full_pipeline.py --city-id ca_el_centro

# Or for all cities
python scripts/run_full_pipeline.py --all
```

**Steps executed:**

1. Load city boundaries from config
2. Query OSM for addresses in boundary
3. Apply subdivision-based sampling
4. Normalize addresses
5. Geocode with Nominatim
6. Insert/update in database
7. Generate report

**Time estimate**:
- Per city: 5-15 minutes (depending on OSM load)
- All cities: 30-90 minutes

### Configuration

Pipeline uses `/config/cities.yaml`:

```yaml
cities:
  - city_id: ca_el_centro
    name: El Centro
    state: CA
    country: USA
    timezone: America/Los_Angeles

    # OSM query bounds
    bounds:
      north: 32.8200
      south: 32.7700
      east: -115.2300
      west: -115.3000
```

## Data Sources

### Primary: OpenStreetMap

**Advantages**:
- Free and open
- Global coverage
- Community maintained
- Real-time updates

**Limitations**:
- Completeness varies by region
- Not always up-to-date
- Address formatting inconsistent

**Usage**:
- Initial address collection
- Geographic sampling
- Regular updates

### Secondary: Municipal GIS

**Source**: City GIS systems when available

**Content**:
- Official trash zones
- Pickup schedules
- Service areas

**Integration**: Manual import or API integration

### Tertiary: Community Crowdsourcing

**Source**: User-submitted observations

**Content**:
- Actual pickup observations
- Schedule corrections
- New addresses

**Consensus**: Aggregated into high-confidence data

## Scheduling

### Development

Run manually as needed:

```bash
# Run once
python scripts/run_full_pipeline.py --all

# Run specific city
python scripts/run_full_pipeline.py --city-id ca_el_centro
```

### Production

Automated schedules (using Cron or similar):

```bash
# Weekly refresh (Sunday 2 AM)
0 2 * * 0 /home/trashalert/run_pipeline.sh

# Daily consensus update (1 AM)
0 1 * * * /home/trashalert/update_consensus.sh

# Monthly full reindex (First of month, 3 AM)
0 3 1 * * /home/trashalert/reindex_db.sh
```

## Error Handling

Pipeline includes error recovery:

### Retries

```python
# Exponential backoff for API calls
max_attempts = 3
backoff_multiplier = 2
# 1s, 2s, 4s retry delays
```

### Partial Failures

```python
# Continue processing if single city fails
if city_fails:
    log_error(city)
    continue_next_city()
```

### Logging

Detailed logging for debugging:

```
logs/
├── pipeline_2025-11-18.log      # Full pipeline run
├── osm_collection_errors.log    # OSM-specific errors
├── geocoding_failed.log          # Addresses that failed geocoding
└── qa_report_2025-11-18.txt     # Summary statistics
```

## Output

### Database

Data is stored in PostgreSQL:

```sql
SELECT COUNT(*) FROM addresses;  -- Should be ~250
SELECT * FROM addresses WHERE city_name = 'El Centro';
```

### Reports

Summary report emailed to maintainers:

```
TrashAlert Pipeline Report
Generated: 2025-11-18 03:45:00

Pipeline Status: SUCCESS

Cities Processed: 6
- El Centro: 50 addresses (SUCCESS)
- Imperial: 50 addresses (SUCCESS)
- Brawley: 48 addresses (SUCCESS)
- Holtville: 50 addresses (SUCCESS)
- Calexico: 50 addresses (SUCCESS)
- San Diego: 0 addresses (PENDING)

Total Addresses: 248
New Addresses: 12
Updated Addresses: 5
Duplicates Removed: 2

Geocoding Success Rate: 99.6%
Failed Geocoding: 1 (check logs)

Database Verification:
✓ All constraints valid
✓ Foreign keys intact
✓ Indexes created
✓ No orphaned records

Next Run: 2025-11-25 02:00:00
```

### Metrics

Tracked in database for monitoring:

```sql
SELECT
  city,
  address_count,
  last_updated,
  consensus_count,
  verified_count
FROM address_metrics
ORDER BY city;
```

## Troubleshooting

### Common Issues

**OSM Timeout**
```bash
# Increase timeout in config
OVERPASS_API_TIMEOUT=60  # seconds

# Or retry
python scripts/fetch_addresses_osm.py --city-id ca_el_centro --retry
```

**Geocoding Failures**
```bash
# Check failed addresses
cat logs/geocoding_failed.log

# Manual retry with fallback coordinates
python scripts/geocode_addresses.py --input failed.csv --use-fallback
```

**Database Errors**
```bash
# Verify database connection
psql -h localhost -U trashalert -d trashalert -c "SELECT 1"

# Check constraints
python scripts/validate_database.py --check-constraints
```

## Performance

### Speed Optimizations

- **Batch processing**: Group operations
- **Connection pooling**: Reuse DB connections
- **Parallel processing**: Multi-threaded geocoding
- **Caching**: Cache API responses

### Memory Usage

- **Streaming**: Large result sets
- **Chunking**: Process in batches
- **Cleanup**: Delete temporary data

## Related Documentation

- **[OSM Collection](/docs/pipeline/osm-collection)** - Address extraction
- **[Address Sampling](/docs/pipeline/address-sampling)** - Geographic sampling
- **[Adding Cities](/docs/pipeline/adding-cities)** - Expand coverage
- **[Database Schema](/docs/architecture/database)** - Data storage

