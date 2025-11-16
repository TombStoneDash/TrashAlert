# TrashAlert Pipeline

A scalable data pipeline for collecting and processing trash pickup information across multiple cities.

## Overview

This pipeline collects address data from OpenStreetMap and processes it for use in the TrashAlert system. It's designed to scale from a single city to hundreds of cities across the United States.

## Pipeline Architecture

The pipeline consists of several modular scripts that work together:

1. **fetch_city_boundaries.py** - Fetches city boundaries from OpenStreetMap
2. **build_subdivisions.py** - Builds subdivision/neighborhood data for each city
3. **fetch_addresses_osm.py** - Fetches address data from OpenStreetMap
4. **sample_addresses_per_city.py** - Samples addresses per city (up to configurable limit)
5. **run_full_pipeline.py** - Orchestrates the entire pipeline

## Configuration

Cities are configured in `config/cities.yaml`. Each city entry includes:

```yaml
- name: City Name
  state: State Name
  state_abbr: XX
  country: USA
  has_official_pickup_zones: true/false
  pickup_zone_data_source: "URL or note"
  notes: "Additional context"
```

## Usage

### Running the Full Pipeline

Process all cities:
```bash
python scripts/run_full_pipeline.py --all
```

Process a specific city:
```bash
python scripts/run_full_pipeline.py --city "Brawley, California"
# or
python scripts/run_full_pipeline.py --city "Brawley"
```

Process all cities in a state:
```bash
python scripts/run_full_pipeline.py --state CA
# or
python scripts/run_full_pipeline.py --state California
```

Skip certain pipeline steps:
```bash
python scripts/run_full_pipeline.py --city "Brawley" \
  --skip-boundaries --skip-subdivisions
```

### Running Individual Scripts

Each script can be run independently with the same filtering options:

**Sample addresses:**
```bash
# All cities
python scripts/sample_addresses_per_city.py

# One city
python scripts/sample_addresses_per_city.py --only "Brawley, California"

# One state
python scripts/sample_addresses_per_city.py --state CA

# Custom sample size
python scripts/sample_addresses_per_city.py --only "Brawley" --max-per-city 100
```

**Fetch boundaries:**
```bash
python scripts/fetch_city_boundaries.py --only "San Diego, California"
```

**Build subdivisions:**
```bash
python scripts/build_subdivisions.py --state CA
```

**Fetch addresses:**
```bash
python scripts/fetch_addresses_osm.py --only "Brawley"
```

## Adding New Cities

1. Edit `config/cities.yaml` and add a new city entry
2. Run the pipeline for that city:
   ```bash
   python scripts/run_full_pipeline.py --city "New City, State"
   ```

## Output

The pipeline generates the following data:

- `data/boundaries/*.geojson` - City boundary GeoJSON files
- `data/subdivisions/*.json` - Subdivision/neighborhood data
- `data/addresses_osm_raw.csv` - Raw address data from OpenStreetMap
- `data/addresses_sampled_50_per_city.csv` - Sampled addresses (default: 50 per city)

## Requirements

```bash
pip install pyyaml requests pandas
```

## Example: Pipeline for One City

```bash
# Run the complete pipeline for Brawley
python scripts/run_full_pipeline.py --city "Brawley"

# Output shows:
# - Cities processed: Brawley, CA
# - Steps completed: 4
# - Data statistics per city
# - Summary with timing information
```

## Future Enhancements

- Normalization step for address standardization
- Database loading functionality
- Integration with official city pickup zone data
- Support for international cities (currently US-only)
