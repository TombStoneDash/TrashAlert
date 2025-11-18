# Nationwide Mode - Quick City Onboarding Guide

TrashAlert's Nationwide Mode enables you to onboard a new city in **under 10 minutes**.

## Quick Start

### Basic City Onboarding (Minimal)

```bash
# Add a city with auto-fetched boundaries
python scripts/city_importer.py \
  --city "Los Angeles" \
  --state "California"
```

### With Pickup Rule Template

```bash
# Use a standard pickup schedule template
python scripts/city_importer.py \
  --city "Los Angeles" \
  --state "California" \
  --template "alternating_week"
```

### With GIS Shapefile

```bash
# Import pickup zones from GeoJSON/Shapefile
python scripts/city_importer.py \
  --city "Los Angeles" \
  --state "California" \
  --shapefile "data/gis/los_angeles/pickup_zones.geojson" \
  --template "zone_based"
```

### Full Configuration

```bash
# Complete onboarding with all options
python scripts/city_importer.py \
  --city "Los Angeles" \
  --state "California" \
  --state-abbr "CA" \
  --bbox "-118.668,33.704,-118.155,34.337" \
  --shapefile "data/gis/los_angeles/pickup_zones.geojson" \
  --template "zone_based" \
  --population 3898747 \
  --region "Southern California" \
  --timezone "America/Los_Angeles" \
  --notes "Major city with official GIS data"
```

## Features

### 1. Extended cities.yaml Format

The `config/cities.yaml` file now supports additional fields for Nationwide Mode:

```yaml
cities:
  - city_id: ca_los_angeles
    name: Los Angeles
    state: California
    state_abbr: CA
    country: USA
    has_official_pickup_zones: true
    pickup_zone_data_source: "https://example.com/gis"
    notes: "Major city"

    # Nationwide Mode fields
    bounding_box: [-118.668, 33.704, -118.155, 34.337]  # [min_lon, min_lat, max_lon, max_lat]
    shapefile_path: "data/gis/los_angeles/pickup_zones.geojson"
    pickup_rule_template: "zone_based"
    population: 3898747
    region: "Southern California"
    timezone: "America/Los_Angeles"
    onboarding_status: "COMPLETE"  # PENDING, IN_PROGRESS, COMPLETE, VERIFIED
```

### 2. Automatic Bounding Box Fetching

If you don't provide a `--bbox` parameter, the importer will automatically fetch the city's bounding box from OpenStreetMap's Nominatim API.

```python
# Auto-fetches bounding box
python scripts/city_importer.py --city "Austin" --state "Texas"
```

### 3. Pickup Rule Templates

The importer includes several pre-defined pickup schedule templates:

#### **alternating_week**
- Trash weekly, recycling alternating weeks
- Creates 5 zones (Mon-Fri)
- Each zone has trash, recycling, and green waste days

```yaml
zones:
  - Zone A: Trash Mon, Recycling Mon, Green Thu
  - Zone B: Trash Tue, Recycling Tue, Green Fri
  - Zone C: Trash Wed, Recycling Wed, Green Mon
  - Zone D: Trash Thu, Recycling Thu, Green Tue
  - Zone E: Trash Fri, Recycling Fri, Green Wed
```

#### **weekly_same_day**
- All pickups (trash, recycling, green) on the same day
- Creates 5 zones (Mon-Fri)

```yaml
zones:
  - Monday Zone: All pickups Monday
  - Tuesday Zone: All pickups Tuesday
  - Wednesday Zone: All pickups Wednesday
  - Thursday Zone: All pickups Thursday
  - Friday Zone: All pickups Friday
```

#### **zone_based**
- Uses zones from imported shapefile
- Schedules must be configured manually per zone

#### **manual**
- No automatic zones or schedules
- Complete manual configuration required

### 4. GIS Shapefile Import

Import pickup zones from GeoJSON or Shapefile formats:

```bash
python scripts/city_importer.py \
  --city "Portland" \
  --state "Oregon" \
  --shapefile "data/gis/portland/zones.geojson"
```

**Supported formats:**
- GeoJSON (`.geojson`, `.json`)
- Shapefile (`.shp` with supporting files)
- Any format supported by GeoPandas

**Expected GeoJSON structure:**

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [...]
      },
      "properties": {
        "zone_name": "North Zone",
        "zone_id": "ZONE_1",
        "trash_day": "Monday",
        "recycling_day": "Thursday"
      }
    }
  ]
}
```

## Workflow

### Step 1: Add City Configuration

The `city_importer.py` script performs the following:

1. **Generate city_id** from city name and state abbreviation
2. **Fetch bounding box** from Nominatim (if not provided)
3. **Add entry to cities.yaml** with all metadata
4. **Create database record** in the `cities` table
5. **Import shapefile** (if provided) into `pickup_zones` table
6. **Apply template** (if provided) to create schedules
7. **Update onboarding status** to "COMPLETE"

### Step 2: Run Address Pipeline

After onboarding, fetch and process addresses:

```bash
python scripts/run_full_pipeline.py --city "Los Angeles"
```

This will:
- Fetch city boundaries from OSM
- Query addresses from Overpass API
- Normalize address data
- Link addresses to pickup zones
- Load into database

### Step 3: Verify Data Integrity

```bash
python scripts/verify_city_integrity.py --city "ca_los_angeles"
```

### Step 4: Test API

```bash
curl "http://localhost:8000/lookup?address=123%20Main%20St&city=Los%20Angeles&state=CA"
```

## Command Reference

### city_importer.py Options

| Option | Required | Description | Example |
|--------|----------|-------------|---------|
| `--city` | Yes | City name | `"Los Angeles"` |
| `--state` | Yes | Full state name | `"California"` |
| `--state-abbr` | No | State abbreviation (auto-derived if not provided) | `"CA"` |
| `--bbox` | No | Bounding box as `min_lon,min_lat,max_lon,max_lat` | `"-118.668,33.704,-118.155,34.337"` |
| `--shapefile` | No | Path to shapefile/GeoJSON | `"data/gis/la/zones.geojson"` |
| `--template` | No | Pickup rule template | `"alternating_week"` |
| `--population` | No | City population | `3898747` |
| `--region` | No | Regional grouping | `"Southern California"` |
| `--timezone` | No | IANA timezone | `"America/Los_Angeles"` |
| `--notes` | No | Additional notes | `"Major city"` |

### Template Options

- `alternating_week` - Trash weekly, recycling alternating weeks (5 zones)
- `weekly_same_day` - All pickups same day (5 zones)
- `zone_based` - Uses shapefile zones, manual schedule config
- `manual` - No automatic zones/schedules

## Examples

### Example 1: Small Town (No GIS Data)

```bash
# Quick onboarding with template
python scripts/city_importer.py \
  --city "Holtville" \
  --state "California" \
  --template "weekly_same_day" \
  --population 6200 \
  --region "Imperial County"

# Run pipeline
python scripts/run_full_pipeline.py --city "Holtville"
```

### Example 2: Major City (With GIS Data)

```bash
# Download GIS data first (manual step)
# Place in data/gis/austin/pickup_zones.geojson

# Import city with shapefile
python scripts/city_importer.py \
  --city "Austin" \
  --state "Texas" \
  --shapefile "data/gis/austin/pickup_zones.geojson" \
  --template "zone_based" \
  --population 964254 \
  --region "Central Texas" \
  --timezone "America/Chicago"

# Run pipeline
python scripts/run_full_pipeline.py --city "Austin"
```

### Example 3: Manual Configuration

```bash
# Add city without zones/schedules
python scripts/city_importer.py \
  --city "Portland" \
  --state "Maine" \
  --template "manual" \
  --population 68408

# Manually configure zones and schedules in database
# Then run pipeline
python scripts/run_full_pipeline.py --city "Portland" --state "ME"
```

## Database Schema

### City Record

```python
City(
    slug="ca_los_angeles",
    name="Los Angeles",
    state="California",
    region="Southern California",
    timezone="America/Los_Angeles",
    enabled=True,
    extra_metadata={
        "state_abbr": "CA",
        "country": "USA",
        "bounding_box": [-118.668, 33.704, -118.155, 34.337],
        "population": 3898747,
        "onboarding_status": "COMPLETE"
    }
)
```

### PickupZone Records (from template)

```python
PickupZone(
    city_id=1,
    name="Zone A",
    external_ref="ZONE_A",
    extra_metadata={"template": "alternating_week"}
)
```

### Schedule Records (from template)

```python
Schedule(
    city_id=1,
    pickup_zone_id=1,
    trash_day_of_week="MON",
    recycling_day_of_week="MON",
    green_day_of_week="THU",
    source="TEMPLATE",
    extra_metadata={"template": "alternating_week"}
)
```

## Testing

Run the automated tests:

```bash
# Run all city importer tests
pytest tests/test_city_importer.py -v

# Run specific test
pytest tests/test_city_importer.py::TestCityImporter::test_full_onboarding_with_template -v

# Run with coverage
pytest tests/test_city_importer.py --cov=scripts.city_importer --cov-report=html
```

## Troubleshooting

### Bounding Box Fetch Fails

If Nominatim can't find your city, provide the bbox manually:

```bash
# Find bbox on https://boundingbox.klokantech.com/
python scripts/city_importer.py \
  --city "Small Town" \
  --state "Wyoming" \
  --bbox "-110.5,41.0,-110.0,41.5"
```

### Shapefile Import Fails

Check your GeoJSON structure:

```bash
# Validate GeoJSON
python -c "import json; json.load(open('data/gis/city/zones.geojson'))"

# Check with geopandas
python -c "import geopandas as gpd; print(gpd.read_file('data/gis/city/zones.geojson'))"
```

### City Already Exists

The importer will skip duplicate cities:

```bash
# This is safe - won't create duplicates
python scripts/city_importer.py --city "San Diego" --state "California"
# Output: "City ca_san_diego already exists in YAML"
```

## Performance

Target: **Onboard a new city in under 10 minutes**

Typical breakdown:
- Add to YAML: 5-10 seconds (with Nominatim fetch)
- Create DB record: <1 second
- Import shapefile: 1-5 seconds (depends on zone count)
- Apply template: 1-2 seconds
- **Total: ~15-30 seconds** for the importer script

Address pipeline (separate step):
- Fetch boundaries: 5-10 seconds
- Query addresses: 1-5 minutes (depends on city size)
- Process addresses: 1-3 minutes
- **Total: 2-8 minutes** for full pipeline

**Grand total: ~2-9 minutes** from start to finish

## Roadmap

Future enhancements:

- [ ] Bulk import from CSV (add 100+ cities at once)
- [ ] Web UI for city onboarding
- [ ] Automated GIS data discovery from official sources
- [ ] Schedule conflict detection and validation
- [ ] Progress dashboard showing onboarding status
- [ ] Integration with state/county databases
- [ ] Template customization UI
- [ ] Quality metrics per city (coverage %, accuracy %)

## Contributing

To add a new pickup rule template:

1. Edit `scripts/city_importer.py`
2. Add to `CityImporter.TEMPLATES` dict
3. Add tests in `tests/test_city_importer.py`
4. Update this documentation

Example:

```python
"biweekly_trash": {
    "name": "Bi-Weekly Trash Schedule",
    "description": "Trash every other week, recycling opposite weeks",
    "zones": [
        {"name": "Week A Zone", "trash": "MON", "recycling": "MON", "green": "THU"},
        {"name": "Week B Zone", "trash": "MON", "recycling": "MON", "green": "THU"},
    ]
}
```

## Support

For questions or issues:

1. Check the [main README](../README.md)
2. Review [troubleshooting](#troubleshooting) section
3. Run tests: `pytest tests/test_city_importer.py -v`
4. Open an issue on GitHub

---

**Happy onboarding!** 🚀
