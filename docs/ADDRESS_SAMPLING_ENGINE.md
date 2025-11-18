# Address Sampling Engine

## Overview

The Address Sampling Engine is an automated tool that generates random address samples within city boundaries using OpenStreetMap (OSM) data and reverse geocoding.

## Features

- ✅ **Random Point Generation**: Generates 50 random sample points within city boundary polygons
- ✅ **Reverse Geocoding**: Uses Nominatim API to convert coordinates to valid addresses
- ✅ **Rate Limiting**: Respects Nominatim's 1 request/second limit
- ✅ **Retry Logic**: Exponential backoff (2s, 4s, 8s) for failed requests
- ✅ **Address Normalization**: Converts addresses to USPS standard format
- ✅ **Caching**: Stores geocoding results to avoid duplicate API calls
- ✅ **Error Handling**: Saves failed lookups separately for debugging
- ✅ **Zero Crashes**: Robust error handling prevents script failures

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Address Sampling Engine                      │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
        ┌───────────────────────────────────────────┐
        │   1. Load City Boundary (GeoJSON)         │
        │      - Check cache first                  │
        │      - Fallback to Overpass API           │
        └───────────────────────────────────────────┘
                                │
                                ▼
        ┌───────────────────────────────────────────┐
        │   2. Generate Random Points               │
        │      - Rejection sampling                 │
        │      - Within polygon boundaries          │
        └───────────────────────────────────────────┘
                                │
                                ▼
        ┌───────────────────────────────────────────┐
        │   3. Reverse Geocode (Nominatim)          │
        │      - Rate limited (1 req/sec)           │
        │      - Retry with exponential backoff     │
        │      - Cache results                      │
        └───────────────────────────────────────────┘
                                │
                                ▼
        ┌───────────────────────────────────────────┐
        │   4. Normalize Addresses (USPS)           │
        │      - Uppercase conversion               │
        │      - Street type abbreviation           │
        │      - Directional abbreviation           │
        └───────────────────────────────────────────┘
                                │
                                ▼
        ┌───────────────────────────────────────────┐
        │   5. Save Results                         │
        │      - data/processed/addresses/{city}.json│
        │      - data/processed/addresses/{city}_failed.json│
        └───────────────────────────────────────────┘
```

## Usage

### Basic Usage

Sample all configured cities (50 addresses each):
```bash
python scripts/sample_addresses_engine.py
```

### Sample Specific City

```bash
python scripts/sample_addresses_engine.py --only "Brawley, California"
```

### Sample Cities in Specific State

```bash
python scripts/sample_addresses_engine.py --state CA
```

### Custom Number of Samples

```bash
python scripts/sample_addresses_engine.py --samples 100
```

### Custom Output Directory

```bash
python scripts/sample_addresses_engine.py --output-dir /path/to/output
```

## Output Format

### Successful Addresses: `{city}.json`

```json
{
  "city": "Brawley",
  "state": "California",
  "count": 50,
  "addresses": [
    {
      "lat": 32.9786,
      "lon": -115.5300,
      "house_number": "123",
      "street": "Main Street",
      "city": "Brawley",
      "state": "California",
      "postcode": "92227",
      "country": "United States",
      "display_name": "123 Main Street, Brawley, CA 92227, USA",
      "normalized_address": "123 MAIN ST",
      "osm_type": "node",
      "osm_id": 123456789
    }
  ]
}
```

### Failed Attempts: `{city}_failed.json`

```json
{
  "city": "Brawley",
  "state": "California",
  "count": 3,
  "failed_attempts": [
    {
      "lat": 32.9786,
      "lon": -115.5300,
      "reason": "geocoding_failed"
    },
    {
      "lat": 32.9800,
      "lon": -115.5250,
      "reason": "parse_failed",
      "raw_result": { ... }
    }
  ]
}
```

## Directory Structure

```
TrashAlert/
├── data/
│   ├── cache/                           # City boundaries and geocoding cache
│   │   ├── {city}_boundary.geojson     # Cached city boundaries
│   │   └── reverse_geocoding_cache.json # Geocoding results cache
│   └── processed/
│       └── addresses/                   # Generated address samples
│           ├── {city}.json             # Successful addresses
│           └── {city}_failed.json      # Failed lookups
└── scripts/
    └── sample_addresses_engine.py      # Main engine script
```

## Rate Limiting & API Compliance

### Nominatim Usage Policy

The engine follows Nominatim's strict usage requirements:

1. **Rate Limit**: Maximum 1 request per second
2. **User-Agent**: Includes project URL and contact information
3. **Caching**: Results are cached to minimize API calls
4. **No Bulk Downloads**: Samples generated on-demand, not bulk fetched

### Retry Logic

When API calls fail, the engine implements exponential backoff:

- **Attempt 1**: Immediate
- **Attempt 2**: Wait 2 seconds
- **Attempt 3**: Wait 4 seconds
- **Final**: Wait 8 seconds, then mark as failed

## Address Normalization

Addresses are normalized to USPS standard format:

### Street Types
- `Street` → `ST`
- `Avenue` → `AVE`
- `Boulevard` → `BLVD`
- `Drive` → `DR`
- `Lane` → `LN`
- `Road` → `RD`

### Directionals
- `North` → `N`
- `South` → `S`
- `East` → `E`
- `West` → `W`
- `Northeast` → `NE`
- `Southeast` → `SE`

### Examples
```
Input:  "123 main street"
Output: "123 MAIN ST"

Input:  "45 North Park Boulevard"
Output: "45 N PARK BLVD"
```

## Caching System

### Reverse Geocoding Cache

Location: `data/cache/reverse_geocoding_cache.json`

- **Key**: MD5 hash of coordinates (rounded to 6 decimal places)
- **Value**: Raw Nominatim response or `null` for failures
- **Precision**: ~0.11 meter accuracy

### Benefits
- Reduces API calls by ~95% on repeated runs
- Speeds up development/testing
- Respects API provider resources

## Error Handling

### Common Errors

1. **403 Forbidden (Nominatim)**
   - **Cause**: Missing/invalid User-Agent or rate limit exceeded
   - **Solution**: Ensure proper User-Agent header, respect 1 req/sec limit

2. **No Boundary Found**
   - **Cause**: City name not recognized by OSM/Nominatim
   - **Solution**: Manually create boundary file or adjust city name

3. **Parsing Failed**
   - **Cause**: Geocoded location has no valid address components
   - **Solution**: Point may be in unpopulated area, logged in `_failed.json`

### Debug Mode

For verbose logging:
```bash
python scripts/sample_addresses_engine.py --samples 10 2>&1 | tee debug.log
```

## Performance

### Typical Runtime

For 50 samples per city:

- **Boundary Loading**: <1 second (cached)
- **Point Generation**: <1 second
- **Reverse Geocoding**: ~50 seconds (1 req/sec limit)
- **Total per city**: ~52 seconds

### Scaling

For 6 cities × 50 samples = 300 addresses:
- **Total time**: ~5 minutes
- **API calls**: 300 (assuming no cache hits)

## Limitations

1. **API Rate Limits**: Nominatim restricts to 1 req/sec
2. **Geographic Accuracy**: Points may fall in unpopulated areas
3. **Address Quality**: Depends on OSM data completeness
4. **Boundary Precision**: Uses simplified polygons for performance

## Future Enhancements

- [ ] Support for multiple geocoding providers (Google, Mapbox)
- [ ] Weighted sampling (prefer populated areas)
- [ ] Validation against USPS address database
- [ ] Parallel processing with multiple API keys
- [ ] Machine learning for address quality scoring

## Dependencies

```
geopandas>=0.14.0      # Geographic DataFrames
shapely>=2.0.0         # Geometry operations
geopy==2.4.1           # Geocoding utilities
pandas>=2.0.0          # Data manipulation
requests>=2.31.0       # HTTP requests
```

## Contributing

When adding new cities:

1. Add city to `config/cities.yaml`
2. (Optional) Create boundary file: `data/cache/{city}_boundary.geojson`
3. Run engine: `python scripts/sample_addresses_engine.py --only "City, State"`

## License

Part of the TrashAlert project.

## References

- [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/)
- [USPS Address Standards](https://pe.usps.com/text/pub28/welcome.htm)
- [OpenStreetMap Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API)
