# OSM Address Pipeline Documentation

## Overview

The OSM Address Pipeline is a standardized, city-aware pipeline for collecting and processing address data from OpenStreetMap. It's designed to work seamlessly with the TrashAlert city configuration system.

## Architecture

### Configuration Files

1. **`config/cities.yaml`** - Single source of truth for all cities
   - Each city has a unique `city_id` (e.g., `ca_el_centro`)
   - Contains city metadata (name, state, pickup zones, etc.)

2. **`config/config.yaml`** - Pipeline settings
   - Overpass API configuration (URL, timeouts, retry logic)
   - Data directory paths
   - Processing settings (sampling limits, etc.)
   - Logging configuration

3. **`utils/config_loader.py`** - Unified configuration loader
   - Single entry point for all config access
   - City filtering by ID, name, or state
   - Path management
   - Logging setup

## Pipeline Scripts

All pipeline scripts use a consistent CLI interface:

### Common CLI Arguments

```bash
# City selection (mutually exclusive)
--all                    # Process all cities
--city-id <id>          # Process by city ID (e.g., "ca_el_centro")
--city <name>           # Process by name (e.g., "El Centro, CA")
--state <state>         # Process all cities in state (e.g., "CA")
```

### Pipeline Steps

#### 1. Fetch Addresses from OSM

```bash
python scripts/fetch_addresses_osm.py --city-id ca_el_centro
```

**Features:**
- Queries Overpass API for address data
- Automatic retry logic with exponential backoff
- Rate limiting (configurable in config.yaml)
- Respects Overpass API timeout settings
- Outputs to `data/raw/addresses_osm_raw.csv`

**Configuration:**
- `overpass_api.timeout_seconds` - Request timeout
- `overpass_api.rate_limit_delay_seconds` - Delay between cities
- `overpass_api.retry.max_attempts` - Number of retry attempts
- `overpass_api.retry.backoff_multiplier` - Exponential backoff multiplier

#### 2. Sample Addresses Per City

```bash
python scripts/sample_addresses_per_city.py --city-id ca_el_centro
```

**Features:**
- Samples up to N addresses per city (configurable)
- Spreads samples across subdivisions when available
- Removes duplicates and null coordinates
- Outputs to `data/processed/addresses_sampled_50_per_city.csv`

**Configuration:**
- `processing.max_addresses_per_city` - Maximum addresses to sample per city

#### 3. Normalize Addresses

```bash
python scripts/normalize_addresses.py --city-id ca_el_centro
```

**Features:**
- Normalizes street names (uppercase, abbreviations)
- Creates canonical full addresses
- Deduplicates based on (city_id, full_address)
- Writes to both SQLite database and CSV
- Outputs to `data/processed/addresses_normalized.csv` and `data/trashalert.db`

### Full Pipeline Orchestration

Run the complete pipeline with a single command:

```bash
# Run full pipeline for one city
python scripts/run_full_pipeline.py --city-id ca_el_centro

# Run for all cities
python scripts/run_full_pipeline.py --all

# Run for all California cities
python scripts/run_full_pipeline.py --state CA

# Skip certain steps
python scripts/run_full_pipeline.py --city-id ca_brawley --skip-boundaries --skip-subdivisions
```

**Available Options:**
- `--skip-boundaries` - Skip city boundary fetching
- `--skip-subdivisions` - Skip subdivision building
- `--skip-addresses` - Skip address fetching from OSM
- `--skip-sampling` - Skip address sampling
- `--skip-normalization` - Skip address normalization

## Data Flow

```
OpenStreetMap (Overpass API)
         ↓
  fetch_addresses_osm.py
         ↓
  data/raw/addresses_osm_raw.csv
         ↓
  sample_addresses_per_city.py
         ↓
  data/processed/addresses_sampled_50_per_city.csv
         ↓
  normalize_addresses.py
         ↓
  ├─ data/processed/addresses_normalized.csv
  └─ data/trashalert.db
```

## Directory Structure

```
TrashAlert/
├── config/
│   ├── cities.yaml              # City definitions with city_id
│   └── config.yaml              # Pipeline configuration
├── utils/
│   └── config_loader.py         # Unified config loader
├── scripts/
│   ├── fetch_addresses_osm.py   # OSM address fetching
│   ├── sample_addresses_per_city.py  # Address sampling
│   ├── normalize_addresses.py   # Address normalization
│   └── run_full_pipeline.py     # Pipeline orchestration
└── data/
    ├── raw/                     # Raw data from OSM
    ├── processed/               # Processed/normalized data
    ├── boundaries/              # City boundaries (GeoJSON)
    └── subdivisions/            # Subdivision data (JSON)
```

## Error Handling and Resilience

### Overpass API Retry Logic

The pipeline implements robust retry logic for Overpass API calls:

1. **Timeout Handling**: Retries with exponential backoff (2s, 4s, 8s, 16s)
2. **Rate Limiting**: Automatic delays between requests
3. **HTTP 429 (Too Many Requests)**: Extended backoff delay
4. **Network Errors**: Automatic retry with configurable max attempts

### Configuration Example

```yaml
overpass_api:
  retry:
    max_attempts: 4
    initial_delay_seconds: 2
    backoff_multiplier: 2.0
    max_delay_seconds: 30
```

## Adding a New City

1. Add city to `config/cities.yaml`:
   ```yaml
   - city_id: ca_example_city    # Format: {state_abbr}_{city_name_snake_case}
     name: Example City
     state: California
     state_abbr: CA
     country: USA
     has_official_pickup_zones: false
     pickup_zone_data_source: "Not available"
     notes: "Example city"
   ```

2. Run the pipeline:
   ```bash
   python scripts/run_full_pipeline.py --city-id ca_example_city
   ```

## Testing

To test the pipeline with a single city without hitting the network:

```bash
# Test with mock data (if available)
python scripts/run_full_pipeline.py --city-id ca_el_centro --skip-addresses
```

## Best Practices

1. **Always use city_id for automation** - More stable than city names
2. **Use --all carefully** - Respects rate limits but takes time
3. **Check logs** - All scripts log to consistent format
4. **Monitor Overpass API** - Be respectful of rate limits
5. **Incremental processing** - Process cities one at a time first

## Troubleshooting

### Common Issues

**Q: "No cities match the specified filters"**
- Check city_id spelling in `config/cities.yaml`
- Verify city name format (include state if ambiguous)

**Q: "Overpass API timeout"**
- Increase `overpass_api.timeout_seconds` in config.yaml
- City might have too much data; query might need refinement

**Q: "Rate limited by Overpass API"**
- Increase `overpass_api.rate_limit_delay_seconds`
- Wait longer between pipeline runs

**Q: "Input file not found"**
- Ensure previous pipeline step completed successfully
- Check `data/raw/` and `data/processed/` directories exist

## Future Enhancements

- [ ] Dry-run mode for testing without network calls
- [ ] Progress indicators for long-running operations
- [ ] Parallel city processing (with rate limit coordination)
- [ ] Incremental updates (only fetch new/changed addresses)
- [ ] Validation tests for address data quality

## Support

For issues or questions:
1. Check logs in console output
2. Verify configuration in `config/config.yaml`
3. Review city definitions in `config/cities.yaml`
4. Check GitHub issues for known problems
