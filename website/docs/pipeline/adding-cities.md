---
sidebar_position: 4
title: Adding New Cities
slug: /pipeline/adding-cities
---

# Adding New Cities to TrashAlert

Complete guide to expand TrashAlert coverage to new cities.

Based on `/home/user/TrashAlert/CITY_EXPANSION.md`.

## Overview

Adding a new city involves:
1. Configuring city metadata
2. Obtaining city boundaries
3. Running data collection pipeline
4. Setting up official schedules (optional)
5. Testing and validation
6. Deployment

**Timeline**: 2-4 hours per city

## Step 1: Configure City in cities.yaml

Edit `/config/cities.yaml`:

```yaml
cities:
  - city_id: ca_fresno
    name: Fresno
    state: CA
    country: USA
    county: Fresno County
    timezone: America/Los_Angeles
    enabled: true

    # Geographic bounds (from Google Maps or GIS data)
    bounds:
      north: 37.0000  # Northern latitude
      south: 36.6500  # Southern latitude
      east: -119.7200  # Eastern longitude
      west: -119.9500  # Western longitude

    # Optional: subdivisions for stratified sampling
    subdivisions:
      - Downtown
      - East Fresno
      - West Fresno
      - North Fresno
      - South Fresno

    # Optional: official schedule info
    official_schedule:
      source: "Fresno City GIS"
      url: "https://fresno.gov/trash-schedule"
      contact: "trash@fresnogovt.com"

    # Optional: special rules
    metadata:
      holiday_delays: true
      bulk_pickup: true
      hazmat_available: true
```

### Finding City Bounds

**Google Maps**:
1. Search for city
2. Open in Google Maps
3. Read coordinates from URL: `@37.0,-119.85,10z`
4. Estimate bounds from map view

**GIS Data**:
- Use QGIS to view shapefiles
- City/county GIS websites
- Census data

**Overpass API**:
```
https://overpass-turbo.eu/
# Query:
[name="Fresno"];
out;
# View boundaries
```

## Step 2: Obtain City Boundary Data

### Option 1: Download GeoJSON

Many cities publish GIS data:

1. Visit city GIS portal
2. Search for "city boundary" or "municipal boundary"
3. Download GeoJSON format
4. Save to `/data/boundaries/fresno.geojson`

### Option 2: Draw Boundaries

Use Overpass Turbo or QGIS:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[
          [-119.9500, 36.6500],
          [-119.7200, 36.6500],
          [-119.7200, 37.0000],
          [-119.9500, 37.0000],
          [-119.9500, 36.6500]
        ]]
      }
    }
  ]
}
```

Save as `/data/boundaries/fresno.geojson`

### Option 3: Use Lat/Lon Bounds

Simplest approach - just use bounds in config.yaml:

```yaml
bounds:
  north: 37.0000
  south: 36.6500
  east: -119.7200
  west: -119.9500
```

## Step 3: Run Data Collection Pipeline

### Test with Single City

```bash
# Verify configuration
python scripts/validate_config.py --city-id ca_fresno

# Fetch addresses from OSM
python scripts/fetch_addresses_osm.py --city-id ca_fresno

# Monitor progress
tail -f logs/osm_collection.log
```

### Full Pipeline

```bash
# Run complete pipeline for new city
python scripts/run_full_pipeline.py --city-id ca_fresno

# Output
# ✓ OSM collection: 1,245 addresses
# ✓ Sampling: 50 addresses selected
# ✓ Normalization: All addresses standardized
# ✓ Geocoding: 49/50 successful
# ✓ Database: 50 records inserted
# ✓ Validation: All checks passed
```

### Handle Issues

**Too few addresses (&lt;20)**
```bash
# Likely issue: bounds too small or no data in OSM
# Solution: Expand bounds or check OSM coverage
python scripts/fetch_addresses_osm.py --city-id ca_fresno --debug
```

**Geocoding failures**
```bash
# Manual geocoding for failed addresses
python scripts/geocode_addresses.py --city-id ca_fresno --retry
```

## Step 4: Set Up Official Schedules (Optional)

If city publishes official schedules:

### Option 1: Manual Entry

```sql
INSERT INTO schedules (city_id, trash_day_of_week,
                       recycling_day_of_week, source)
VALUES (
  (SELECT id FROM cities WHERE city_id = 'ca_fresno'),
  'Monday',
  'Thursday',
  'City of Fresno GIS'
);
```

### Option 2: Import from CSV

Create `schedules_fresno.csv`:

```csv
address_id,trash_day,recycling_day,green_day
1,MON,THU,
2,MON,THU,
3,TUE,FRI,
4,WED,SAT,
...
```

Load:
```bash
python scripts/import_official_schedules.py --file schedules_fresno.csv
```

### Option 3: City API Integration

If city has API:

```python
# scripts/import_fresno_api.py
import requests

FRESNO_API = "https://fresno.gov/api/trash-schedule"

def fetch_schedule(address):
    """Fetch schedule from city API."""
    response = requests.get(
        f"{FRESNO_API}?address={address}"
    )
    return response.json()

# Integrate with data pipeline
for address in all_addresses():
    schedule = fetch_schedule(address)
    save_to_database(address, schedule)
```

## Step 5: Testing and Validation

### Functional Testing

```bash
# Test API with new city
curl "http://localhost:8000/lookup?address=Main%20St,%20Fresno,%20CA"

# Should return
{
  "matched_address": "...",
  "city_name": "Fresno",
  "data_source": "UNKNOWN"  # No consensus yet
}

# Test report submission
curl -X POST http://localhost:8000/report \
  -H "Content-Type: application/json" \
  -d '{
    "address": "123 Main St, Fresno, CA",
    "trash_day": "MON"
  }'
```

### Data Quality Checks

```python
# Run validation
python scripts/validate_city_data.py --city-id ca_fresno

# Check results:
# ✓ 50 addresses in database
# ✓ All have valid coordinates
# ✓ 48/50 geocoded with high confidence
# ✓ Geographically distributed (5x5 grid: 23/25 cells covered)
# ✓ Subdivisions represented: 5/5 areas covered
```

### Manual Spot Checks

Visit the city and verify:
- Random addresses exist
- Coordinates are accurate
- Neighborhood assignments make sense

## Step 6: Deployment

### Update Production Configuration

```bash
# Update config in production
scp /config/cities.yaml prod-server:/app/config/cities.yaml

# Update database
ssh prod-server
cd /app
python scripts/run_full_pipeline.py --city-id ca_fresno
```

### Announce to Community

```markdown
## New City Added: Fresno, CA

We've just added Fresno to TrashAlert! 🎉

- **Coverage**: 50 addresses
- **Neighborhoods**: 5 areas
- **Data Source**: OpenStreetMap + Community

Help us improve coverage by submitting your actual trash day.
Get started: [https://trashalert.com](https://trashalert.com)
```

### Monitor for Issues

```bash
# Check for errors in logs
docker logs trashalert-api | grep fresno

# Monitor database
SELECT COUNT(*) FROM addresses WHERE city_name = 'Fresno';

# Test API
curl "http://localhost/lookup?address=main%20st,%20fresno,%20ca"
```

## Bulk City Addition

Add multiple cities at once:

```bash
# Add 5 cities in parallel
for city_id in ca_modesto ca_stockton ca_merced ca_visalia ca_tulare; do
  python scripts/run_full_pipeline.py --city-id $city_id &
done
wait

# All cities processed simultaneously
```

## Performance Considerations

### Resource Requirements

- **CPU**: 1 core per city collection (parallel)
- **Memory**: ~500MB per city
- **Disk**: ~10MB per city
- **Network**: Download speed dependent (typically 10-30 min per city)

### Optimization

```bash
# Limit parallel processes to available CPU
# If 4 CPU cores, run 3-4 cities in parallel
for city_id in $CITIES; do
  python scripts/run_full_pipeline.py --city-id $city_id &
  # Keep only 4 background jobs
  while [ $(jobs -r | wc -l) -ge 4 ]; do sleep 1; done
done
wait
```

## Troubleshooting

### No addresses found

```bash
# Check bounds are correct
python scripts/test_bounds.py --city-id ca_fresno

# Try expanding bounds
# Or check if city exists in OSM
# https://www.openstreetmap.org/search?q=Fresno
```

### All addresses marked as duplicates

```bash
# Reduce deduplication distance
# In config.yaml:
processing:
  min_distance_between_samples_meters: 10  # Was 50
```

### Database errors

```bash
# Check database connection
psql -h localhost -U trashalert -d trashalert -c "SELECT 1"

# Verify constraints
python scripts/validate_database.py
```

## Checklist

Before deploying new city:

- [ ] City added to `/config/cities.yaml`
- [ ] City bounds are accurate
- [ ] Data collection successful (≥20 addresses)
- [ ] All addresses geocoded
- [ ] Sample database query works
- [ ] API lookup returns results
- [ ] Report submission works
- [ ] Quality validation passed
- [ ] Documentation updated
- [ ] Announce to users

## Related Documentation

- **[Data Pipeline Overview](/docs/pipeline/overview)** - Full pipeline
- **[OSM Collection](/docs/pipeline/osm-collection)** - Address extraction
- **[Address Sampling](/docs/pipeline/address-sampling)** - Sampling strategy
- **[API Documentation](/docs/api/overview)** - Test new city endpoints

