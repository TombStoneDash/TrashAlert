# TrashAlert - Residential Address Collection

This project collects residential addresses from OpenStreetMap for trash collection routing and management.

## Features

- **OSM Address Extraction**: Fetches residential addresses via Overpass API
- **Multi-City Support**: Currently configured for 6 major US cities
- **Rate Limiting**: Respects Overpass API limits (1 request per 10 seconds)
- **Retry Logic**: Automatic retry with exponential backoff (up to 3 attempts)
- **Multiple Endpoints**: Tries alternative Overpass API servers if primary fails
- **Subdivision Assignment**: Point-in-polygon matching for subdivision IDs
- **Demo Mode**: Generate synthetic data when Overpass API is not accessible

## Setup

### Requirements

```bash
pip install -r requirements.txt
```

### Dependencies

- `requests` - HTTP client for Overpass API
- `shapely` - Geospatial operations for point-in-polygon

## Usage

### Fetch Addresses from OpenStreetMap

```bash
python3 scripts/fetch_addresses_osm.py
```

This will:
1. Query Overpass API for residential addresses in all configured cities
2. Filter for buildings tagged as residential (house, residential, apartments, etc.)
3. Extract house numbers, street names, and coordinates
4. Assign subdivision IDs via point-in-polygon matching
5. Write results to `data/addresses_osm_raw.csv`

### Demo Mode (Synthetic Data)

If the Overpass API is blocked or unavailable:

```bash
DEMO_MODE=1 python3 scripts/fetch_addresses_osm.py
```

This generates realistic synthetic address data for testing and development.

## Output Format

The script generates `data/addresses_osm_raw.csv` with the following fields:

| Field | Description |
|-------|-------------|
| `city_name` | City name (e.g., "Pittsburgh") |
| `subdivision_id` | Subdivision ID from point-in-polygon match (empty if no subdivision data) |
| `house_number` | Street number from `addr:housenumber` tag |
| `street` | Street name from `addr:street` tag |
| `lat` | Latitude (WGS84) |
| `lon` | Longitude (WGS84) |
| `source` | Data source ("OSM") |

## Configuration

### Cities

Edit `CITIES` in `scripts/fetch_addresses_osm.py` to configure which cities to query:

```python
CITIES = [
    {"name": "Pittsburgh", "area_id": 3600178723},
    {"name": "Philadelphia", "area_id": 3600188022},
    # ... add more cities
]
```

To find area IDs:
1. Search for the city on [Nominatim](https://nominatim.openstreetmap.org/)
2. Find the relation ID
3. Add 3600000000 to get the Overpass area ID

### Subdivision Data

To enable subdivision assignment, create `data/subdivisions.geojson` with:
- GeoJSON feature collection
- Each feature representing a subdivision boundary polygon
- Properties must include an `id` field for the subdivision ID

Example:
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": "SUB001",
      "properties": {"id": "SUB001", "name": "Downtown"},
      "geometry": {"type": "Polygon", "coordinates": [...]}
    }
  ]
}
```

## API Constraints

- **Rate Limiting**: 1 request per 10 seconds (configurable via `RATE_LIMIT_SECONDS`)
- **Retries**: Up to 3 attempts with exponential backoff (1s, 2s, 4s)
- **Timeout**: 300 seconds per request
- **Endpoints**: Tries multiple Overpass servers if one fails

## Troubleshooting

### 403 Forbidden Errors

If you encounter 403 errors from Overpass API:
- The API may be blocking requests from your IP range
- Try running from a different network/environment
- Use demo mode for development: `DEMO_MODE=1 python3 scripts/fetch_addresses_osm.py`

### No Subdivision IDs

If all `subdivision_id` fields are empty:
- Create `data/subdivisions.geojson` with subdivision boundary polygons
- Ensure each feature has an `id` property

## Project Structure

```
TrashAlert/
├── data/
│   ├── addresses_osm_raw.csv      # Output: extracted addresses
│   └── subdivisions.geojson       # Input: subdivision boundaries (optional)
├── scripts/
│   └── fetch_addresses_osm.py     # Main address fetcher script
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## Contributing

When adding new cities:
1. Find the city's area ID on Nominatim
2. Add to the `CITIES` list
3. Ensure rate limiting is configured appropriately
4. Test with demo mode first

## License

[License information to be added]
