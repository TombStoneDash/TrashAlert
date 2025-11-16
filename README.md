# TrashAlert

A scalable, config-driven system for mapping trash collection routes and schedules using OpenStreetMap and municipal open data.

## Overview

TrashAlert aggregates geographic and address data from multiple sources to support trash collection routing and scheduling. The system is designed to easily scale across multiple cities and states through a simple YAML configuration file.

## Project Structure

```
TrashAlert/
├── config/
│   └── cities.yaml              # City configurations and metadata
├── data/
│   ├── raw/                     # Raw OSM JSON downloads
│   └── processed/               # Processed address data (CSV, JSON, GeoJSON)
├── logs/                        # Application logs (auto-created)
├── scripts/
│   ├── fetch_osm_data.py        # Download OSM data via Overpass API
│   └── process_addresses.py    # Extract and normalize address data
├── utils/
│   ├── __init__.py
│   ├── config_loader.py         # YAML configuration loader
│   └── logging_setup.py         # Centralized logging setup
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## Data Sources

### OpenStreetMap (OSM)
- **Source**: [Overpass API](https://overpass-api.de/)
- **Data**: Street networks, building footprints, addresses, administrative boundaries
- **Format**: JSON (raw), GeoJSON (processed)
- **Coverage**: All configured cities

### City Open Data
- **Source**: Municipal open data portals (city-specific)
- **Data**: Trash collection schedules, service zones, special pickup information
- **Format**: Varies by city (CSV, JSON, API)
- **Integration**: Manual/API-based (city-dependent)

## Data Files

### Raw Data (`data/raw/`)
- `{city_id}_osm.json` - Raw OSM data from Overpass API
  - Contains nodes, ways, and relations within city boundaries
  - Includes roads, buildings, and address points
  - Downloaded by `fetch_osm_data.py`

### Processed Data (`data/processed/`)
- `{city_id}_addresses.csv` - Address data in tabular format
  - Columns: osm_id, housenumber, street, unit, city, state, postcode, lat, lon
  - Suitable for database import or spreadsheet analysis

- `{city_id}_addresses.json` - Address data in JSON format
  - Structured address objects
  - Includes OSM metadata

- `{city_id}_addresses.geojson` - Address data as GeoJSON FeatureCollection
  - Point geometries for each address
  - Compatible with GIS tools (QGIS, ArcGIS, Leaflet, Mapbox)
  - Includes full address formatting

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd TrashAlert
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create data directories (auto-created by scripts):
```bash
mkdir -p data/raw data/processed logs
```

## Configuration

### Adding New Cities

Edit `config/cities.yaml` to add new cities:

```yaml
cities:
  - id: "my_city_name"              # Unique identifier
    name: "My City"                 # Display name
    state: "CA"                     # State abbreviation
    county: "My County"             # County name
    region: "My Region"             # Regional grouping
    bbox:                           # Bounding box coordinates
      south: 32.534
      west: -117.280
      north: 33.114
      east: -116.908
    osm:
      use_overpass: true
      query_type: "city_bounds"
    data_sources:
      - name: "OSM"
        type: "overpass"
        url: "https://overpass-api.de/api/interpreter"
      - name: "City Open Data"
        type: "api"
        url: "https://data.mycity.gov"
    population: 100000
    timezone: "America/Los_Angeles"
    enabled: true                   # Set to false to skip processing
```

**Finding Bounding Box Coordinates:**
1. Visit [OpenStreetMap](https://www.openstreetmap.org/)
2. Navigate to your city
3. Click "Export" in the top menu
4. Use the displayed coordinates (min lat/lon, max lat/lon)

## Usage

### 1. Fetch OSM Data

Download OpenStreetMap data for cities using the Overpass API.

```bash
# Fetch all enabled cities
python scripts/fetch_osm_data.py

# Fetch a specific city
python scripts/fetch_osm_data.py --city imperial_brawley

# Fetch all cities in a region
python scripts/fetch_osm_data.py --region "Imperial Valley"

# Fetch all cities in a county
python scripts/fetch_osm_data.py --county "San Diego"

# Custom output directory
python scripts/fetch_osm_data.py --output-dir data/raw --log-level DEBUG
```

**Options:**
- `--city CITY_ID` - Process specific city (e.g., `imperial_brawley`)
- `--region REGION` - Process all cities in region (e.g., `Imperial Valley`)
- `--county COUNTY` - Process all cities in county (e.g., `Imperial`)
- `--output-dir DIR` - Output directory (default: `data/raw`)
- `--config FILE` - Config file path (default: `config/cities.yaml`)
- `--log-level LEVEL` - Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL

**Output:**
- Creates `{city_id}_osm.json` in the output directory
- Logs saved to `logs/fetch_osm_data.log`

### 2. Process Address Data

Extract and normalize address information from raw OSM data.

```bash
# Process all cities
python scripts/process_addresses.py

# Process a specific city
python scripts/process_addresses.py --city imperial_brawley

# Output only CSV format
python scripts/process_addresses.py --format csv

# Custom directories
python scripts/process_addresses.py --input-dir data/raw --output-dir data/processed
```

**Options:**
- `--input-dir DIR` - Input directory with OSM JSON (default: `data/raw`)
- `--output-dir DIR` - Output directory (default: `data/processed`)
- `--city CITY_ID` - Process specific city
- `--format FORMAT` - Output format: `csv`, `json`, `geojson`, `all` (default: `all`)
- `--config FILE` - Config file path (default: `config/cities.yaml`)
- `--log-level LEVEL` - Logging level

**Output:**
- CSV: `{city_id}_addresses.csv`
- JSON: `{city_id}_addresses.json`
- GeoJSON: `{city_id}_addresses.geojson`
- Logs saved to `logs/process_addresses.log`

## Workflow Example

Complete workflow for processing Imperial Valley cities:

```bash
# 1. Fetch OSM data for all Imperial Valley cities
python scripts/fetch_osm_data.py --region "Imperial Valley"

# 2. Process the downloaded data
python scripts/process_addresses.py --input-dir data/raw --output-dir data/processed

# 3. Check the results
ls -lh data/processed/
```

For a single city (San Diego):

```bash
# 1. Fetch data
python scripts/fetch_osm_data.py --city san_diego_city

# 2. Process data
python scripts/process_addresses.py --city san_diego_city

# 3. View GeoJSON in a mapping tool
# Open data/processed/san_diego_city_addresses.geojson in QGIS or upload to geojson.io
```

## Logging

All scripts use centralized logging configured in `config/cities.yaml`.

**Log Configuration:**
- Log files are stored in `logs/` directory
- Each script has its own log file (e.g., `fetch_osm_data.log`)
- Logs are rotated when they reach 10MB (keeps 5 backups)
- Console output shows INFO level and above
- File logs capture all levels including DEBUG

**Viewing Logs:**
```bash
# View most recent log entries
tail -f logs/fetch_osm_data.log

# Search for errors
grep ERROR logs/*.log

# View full log
cat logs/process_addresses.log
```

## Scaling to New States

To expand coverage to a new state:

1. **Research cities** - Identify cities to add
2. **Find bounding boxes** - Use OpenStreetMap export feature
3. **Update config** - Add cities to `config/cities.yaml`
4. **Test one city** - Run fetch and process for a single city first
5. **Process all** - Run scripts for all cities in the region/state

Example for adding Nevada cities:

```yaml
cities:
  - id: "nevada_las_vegas"
    name: "Las Vegas"
    state: "NV"
    county: "Clark"
    region: "Southern Nevada"
    bbox:
      south: 36.025
      west: -115.341
      north: 36.275
      east: -114.941
    # ... rest of config
```

## API Rate Limits and Performance

### Overpass API
- **Rate Limit**: 2 requests per second (configurable in `cities.yaml`)
- **Timeout**: 180 seconds per query (configurable)
- **Large Cities**: San Diego and other large cities may take 2-5 minutes per query
- **Small Cities**: Imperial Valley cities typically complete in 10-30 seconds

### Cost Optimization
- Scripts automatically rate-limit to respect API quotas
- Failed requests retry with exponential backoff (up to 3 attempts)
- Use `--city` or `--region` flags to process incrementally
- Process small cities first to validate configuration

## Troubleshooting

### Common Issues

**1. Overpass API Timeout**
```
Error: Timeout on attempt 1/3 for San Diego
```
**Solution**: Increase timeout in `config/cities.yaml`:
```yaml
processing:
  overpass_api:
    timeout_seconds: 300  # Increase to 5 minutes
```

**2. No Addresses Found**
```
Extracted 0 addresses from imperial_brawley_osm.json
```
**Solution**:
- Verify bounding box coordinates are correct
- Check that OSM has address data for the area
- Review raw JSON file to confirm data was downloaded

**3. Import Error**
```
ModuleNotFoundError: No module named 'yaml'
```
**Solution**: Install requirements:
```bash
pip install -r requirements.txt
```

**4. Empty OSM Response**
```
Successfully fetched 0 elements for Brawley
```
**Solution**:
- Verify bounding box coordinates are correct (south < north, west < east)
- Check OpenStreetMap.org to confirm the area has data
- Try a smaller bounding box

## Development

### Adding New Features

1. **New Data Source**: Add parser in `scripts/` directory
2. **New Output Format**: Extend `process_addresses.py` with new save method
3. **New City Attribute**: Update `config/cities.yaml` schema and processors

### Code Style
- Follow PEP 8 guidelines
- Use type hints where appropriate
- Add docstrings to all functions
- Update README when adding new scripts

### Testing
```bash
# Test with a single small city first
python scripts/fetch_osm_data.py --city imperial_imperial --log-level DEBUG
python scripts/process_addresses.py --city imperial_imperial --log-level DEBUG
```

## Contributing

1. Add new cities to `config/cities.yaml`
2. Test thoroughly with `--log-level DEBUG`
3. Document any city-specific quirks in the config
4. Commit with clear messages describing changes

## License

[Add your license here]

## Credits

- **OpenStreetMap**: Data © OpenStreetMap contributors, ODbL 1.0
- **Overpass API**: Query service for OSM data
- **City Open Data**: Various municipal open data portals

## Contact

[Add contact information]

---

**Current Coverage:**
- Imperial Valley, CA: Brawley, Calexico, El Centro, Imperial
- San Diego County, CA: San Diego, Chula Vista, Oceanside

**Last Updated:** 2025-11-16
