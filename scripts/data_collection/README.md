# OSM Address Harvesting

This directory contains scripts for harvesting address data from OpenStreetMap for pilot cities.

## Script: `fetch_addresses_osm.py`

Fetches addresses from OpenStreetMap using the Overpass API for configured pilot cities.

### Features

- **Multi-source geocoding**: Uses Nominatim API to get city bounding boxes, with fallback to hardcoded coordinates
- **Robust querying**: Queries Overpass API for address nodes and ways within city boundaries
- **Rate limiting**: Respects OSM acceptable use policy with 3-second delays between requests
- **Retry logic**: Exponential backoff (5s, 10s, 20s) for transient network failures
- **Dual output**:
  - Raw JSON files saved to `data/raw/osm/{city}.json`
  - Unified CSV saved to `data/processed/addresses_raw.csv`

### Data Extracted

For each address, the script extracts:
- **Required**: `city_name`, `house_number`, `street`, `lat`, `lon`, `source`
- **Optional**: `postcode`, `unit`, `osm_addr_city`
- **Metadata**: `osm_id`, `osm_type`

### Usage

```bash
# Fetch addresses for all pilot cities
python scripts/data_collection/fetch_addresses_osm.py

# Fetch for a specific city
python scripts/data_collection/fetch_addresses_osm.py --only "Imperial"

# Fetch for all cities in a state
python scripts/data_collection/fetch_addresses_osm.py --state CA

# Custom output paths
python scripts/data_collection/fetch_addresses_osm.py \
  --raw-dir ./custom/raw \
  --csv ./custom/addresses.csv
```

### Output Structure

**Raw JSON** (`data/raw/osm/{city}.json`):
```json
{
  "version": 0.6,
  "generator": "Overpass API",
  "elements": [
    {
      "type": "node",
      "id": 123456789,
      "lat": 32.8484,
      "lon": -115.5698,
      "tags": {
        "addr:housenumber": "100",
        "addr:street": "Main Street",
        "addr:city": "Imperial",
        "addr:postcode": "92251"
      }
    }
  ]
}
```

**Unified CSV** (`data/processed/addresses_raw.csv`):
```csv
city_name,house_number,street,lat,lon,source,osm_addr_city,osm_id,osm_type,postcode
Imperial,100,Main Street,32.8484,-115.5698,OSM,Imperial,node/123456789,node,92251
```

### Pilot Cities

The script includes fallback bounding boxes for all pilot cities:
- Imperial, CA
- El Centro, CA
- Calexico, CA
- Brawley, CA
- San Diego, CA
- Holtville, CA

### OSM Acceptable Use Policy

This script follows the [OSM Overpass API Acceptable Use Policy](https://wiki.openstreetmap.org/wiki/Overpass_API#Acceptable_Use_Policy):

- **Rate limiting**: 3 seconds between requests (minimum 1 second required)
- **Timeout**: 90 seconds per query (well below 180 second limit)
- **User-Agent**: Identifies application as "TrashAlert/1.0"
- **Retry strategy**: Maximum 3 attempts with exponential backoff
- **Fail gracefully**: Logs errors without spamming

### Network Restrictions

**Note**: In some environments, external API access to Nominatim and Overpass may be blocked (HTTP 403 Forbidden). The script includes:

1. **Fallback bounding boxes**: Hardcoded coordinates for pilot cities
2. **Graceful failure**: Clear error messages and logging
3. **Mock data**: Example data in `data/raw/osm/` for testing

If you encounter 403 errors, the script will still function using fallback bounding boxes, but Overpass queries may fail. In production environments with proper network access, the script will work as intended.

### Success Criteria

✅ `data/raw/osm/*.json` files exist for each pilot city
✅ `data/processed/addresses_raw.csv` contains unified address data
✅ Script completes without crashing
✅ Proper rate limiting and retry logic implemented
✅ Concise, informative logging

### Dependencies

```
pandas>=2.0.0
requests>=2.31.0
pyyaml>=6.0.0
```

Install with:
```bash
pip install -r requirements.txt
```
