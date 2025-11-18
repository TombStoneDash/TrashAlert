---
sidebar_position: 2
title: OSM Address Extraction
slug: /pipeline/osm-collection
---

# OpenStreetMap Address Collection

How to extract address data from OpenStreetMap for TrashAlert cities.

Based on `/home/user/TrashAlert/docs/OSM_PIPELINE.md`.

## Overview

The OSM collection pipeline automatically extracts address data from OpenStreetMap Overpass API, filtered by city boundaries.

## Architecture

```
┌─────────────────┐
│ City Boundaries │
│ (GeoJSON)       │
└────────┬────────┘
         │
         ▼
┌──────────────────────┐
│ Overpass API Query   │
│ - All addresses      │
│ - Within boundary    │
│ - Rate limited       │
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ Raw Address Data     │
│ - House number       │
│ - Street name        │
│ - City               │
│ - Latitude/Longitude │
│ - OSM ID             │
└────────┬─────────────┘
         │
         ▼
┌──────────────────────┐
│ Output: CSV          │
│ addresses_osm_raw.csv
└──────────────────────┘
```

## Configuration

### City Configuration

Cities are configured in `/config/cities.yaml`:

```yaml
cities:
  - city_id: ca_el_centro
    name: El Centro
    state: CA

    bounds:
      north: 32.8200
      south: 32.7700
      east: -115.2300
      west: -115.3000

    subdivisions:
      - North
      - Central
      - South
```

### Pipeline Configuration

Settings in `/config/config.yaml`:

```yaml
overpass_api:
  url: https://overpass-api.de/api/interpreter
  timeout_seconds: 300
  rate_limit_delay_seconds: 5
  retry:
    max_attempts: 3
    backoff_multiplier: 2.0

processing:
  max_addresses_per_city: 50
  output_directory: data/processed
```

## Overpass API Query

### Query Format

The pipeline builds Overpass QL queries:

```overpass
[bbox:32.77,-115.30,32.82,-115.23];

(
  node["addr:housenumber"]["addr:street"]["addr:city"];
  way["addr:housenumber"]["addr:street"]["addr:city"];
  relation["addr:housenumber"]["addr:street"]["addr:city"];
);

out center;
```

**Explanation**:
- `[bbox:...]` - Restrict to city boundaries
- `node/way/relation` - Find all address nodes/ways/relations
- `["addr:housenumber"]` - Must have house number
- `["addr:street"]` - Must have street name
- `["addr:city"]` - Must have city name
- `out center` - Return representative coordinates

### Extracted Fields

From each OSM feature:

```json
{
  "house_number": "1122",
  "street": "Palmview Avenue",
  "city": "El Centro",
  "state": "California",
  "postcode": "92243",
  "lat": 32.7971,
  "lon": -115.2645,
  "osm_id": "node/1234567",
  "osm_type": "node"
}
```

## Usage

### CLI Interface

```bash
# Process specific city
python scripts/fetch_addresses_osm.py --city-id ca_el_centro

# Process all cities
python scripts/fetch_addresses_osm.py --all

# Process cities in state
python scripts/fetch_addresses_osm.py --state CA

# By city name
python scripts/fetch_addresses_osm.py --city "El Centro, CA"
```

### Command-line Arguments

```
--all                    Process all configured cities
--city-id <id>          Process by city ID
--city <name>           Process by name
--state <state>         Process by state
--output-dir <path>     Custom output directory
--overpass-url <url>    Custom Overpass API URL
```

### Output

Generates CSV file with extracted addresses:

**File**: `data/raw/addresses_osm_raw.csv`

```csv
house_number,street,city,state,postcode,lat,lon,osm_id,osm_type,subdivision
1122,Palmview Avenue,El Centro,California,92243,32.7971,-115.2645,node/1234567,node,
1245,Main Street,El Centro,California,92243,32.8001,-115.2650,node/1234568,node,
...
```

## Features

### Rate Limiting

Respects Overpass API limits:

```python
# Delay between cities
time.sleep(5)  # 5 second delay

# Timeout for requests
timeout = 300  # 5 minutes max
```

### Retry Logic

Exponential backoff for failed requests:

```python
attempts = 0
while attempts < 3:
    try:
        response = query_overpass()
        break
    except Timeout:
        wait_time = 2 ** attempts  # 1s, 2s, 4s
        time.sleep(wait_time)
        attempts += 1
```

### Progress Tracking

```
Processing cities...
[████████░░] 80% - 4/5 cities (ca_el_centro)
```

## Data Quality

### Validation

Addresses are validated:

```python
# Check required fields
assert address.house_number
assert address.street
assert address.city

# Check coordinates
assert -90 <= lat <= 90
assert -180 <= lon <= 180
```

### Filtering

Invalid addresses are rejected:

```python
# No P.O. boxes
if street.startswith("P.O."):
    skip()

# No duplicate coordinate clusters
if too_close_to_previous():
    skip()
```

## Performance

### Time Estimates

| Cities | Typical Time | Max Time |
|--------|--------------|----------|
| 1 city | 1-2 min | 5-10 min (if OSM is slow) |
| 6 cities | 10-15 min | 30-45 min |
| All cities | 30+ min | Can be hours if OSM is busy |

### Optimization

For large regions:

```bash
# Run in parallel (different processes)
python scripts/fetch_addresses_osm.py --city-id ca_el_centro &
python scripts/fetch_addresses_osm.py --city-id ca_imperial &
wait
```

## Troubleshooting

### Overpass API Timeout

```
Error: Overpass API request timeout (>300s)
```

**Solution**:
- Try again later (API may be busy)
- Reduce query size (process smaller regions)
- Increase timeout: `--timeout 600`

### No Addresses Found

```
Warning: 0 addresses found for ca_el_centro
```

**Causes**:
- City boundaries incorrect
- OSM data incomplete for this region
- Query filter too strict

**Solution**:
- Check city boundaries in config
- Verify city exists in OSM
- Review query parameters

### Rate Limit Exceeded

```
Error: Request blocked (rate limited)
```

**Solution**:
- Increase delay between requests
- Use different Overpass API mirror
- Run during off-peak hours

## Integration with Full Pipeline

OSM collection is step 1 of the full pipeline:

```bash
# Full pipeline includes:
python scripts/run_full_pipeline.py --all

# Steps:
1. ✓ fetch_addresses_osm.py (this script)
2. sample_addresses_per_city.py
3. normalize_addresses.py
4. geocode_addresses.py
5. Database ingest + QA
```

## OSM Data Format

### Complete Example

Raw OSM data before processing:

```json
{
  "type": "node",
  "id": 1234567,
  "lat": 32.7971,
  "lon": -115.2645,
  "tags": {
    "addr:housenumber": "1122",
    "addr:street": "Palmview Avenue",
    "addr:city": "El Centro",
    "addr:state": "California",
    "addr:postcode": "92243",
    "building": "yes",
    "name": "Example House"
  }
}
```

Extracted to:

```csv
1122,Palmview Avenue,El Centro,California,92243,32.7971,-115.2645,node/1234567,node
```

## Related Documentation

- **[Data Pipeline Overview](/docs/pipeline/overview)** - Full pipeline
- **[Address Sampling](/docs/pipeline/address-sampling)** - Next step
- **[Adding Cities](/docs/pipeline/adding-cities)** - Expand coverage
- **[Configuration Guide](/docs/guides/setup)** - Setup details

