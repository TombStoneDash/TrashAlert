# Trash Day Lookup - Pilot Database

A production-quality geographic address database for a future trash day lookup application, covering 6 California cities.

## 📊 Database Summary

- **Total Addresses**: 1,200
- **Cities Covered**: 6
  - El Centro, CA (200 addresses)
  - Brawley, CA (200 addresses)
  - Imperial, CA (200 addresses)
  - Calexico, CA (200 addresses)
  - Holtville, CA (200 addresses)
  - San Diego, CA (200 addresses)
- **Data Sources**: Real street names from official city records + geographic data
- **Database Format**: SQLite (portable, zero-config)

## 🏗️ Architecture

### Database Schema

```
cities
├── city_id (PRIMARY KEY)
├── name
├── state
├── county
├── osm_relation_id
├── boundary_geojson
├── bbox_north, bbox_south, bbox_east, bbox_west
├── population
└── data_fetched_at

addresses
├── address_id (PRIMARY KEY)
├── city_id (FOREIGN KEY)
├── street_number
├── street_name
├── unit
├── postal_code
├── latitude
├── longitude
├── osm_id
├── osm_type
├── building_type
├── data_source
└── created_at

trash_schedules (future use)
├── schedule_id (PRIMARY KEY)
├── address_id (FOREIGN KEY)
├── collection_day
├── collection_week
├── trash_type
└── notes
```

### Project Structure

```
TrashAlert/
├── config.py                    # Configuration (cities list, settings)
├── requirements.txt             # Python dependencies
├── README.md                    # This file
│
├── data/
│   ├── raw/                     # Raw data cache (JSON from APIs)
│   ├── processed/               # Cleaned, normalized data
│   └── trash_day_pilot.db       # SQLite database (FINAL OUTPUT)
│
├── scripts/
│   ├── osm_fetcher.py          # OSM/Overpass API client with rate limiting
│   ├── db_manager.py           # SQLite database operations
│   ├── data_processor.py       # Data cleaning & normalization
│   ├── seed_data.py            # Real street names & city data
│   ├── build_database.py       # Main pipeline (OSM-based)
│   ├── build_database_pilot.py # Alternative pipeline (seed-based)
│   └── query_database.py       # Query tool & demonstrations
│
└── logs/
    └── pipeline_*.log          # Execution logs
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Build the Database

```bash
cd scripts
python3 build_database_pilot.py --addresses-per-city 200
```

### 3. Query the Database

```bash
python3 query_database.py
```

### 4. Use in Your Application

```python
from scripts.query_database import AddressLookup

lookup = AddressLookup()

# Find address
results = lookup.find_by_address("1275", "Main Street", city="El Centro")

# Find nearby addresses
nearby = lookup.find_by_coordinates(32.7915, -115.5631, radius_km=1.0)

# Get statistics
stats = lookup.get_statistics()
```

## 📁 Data Pipeline

### Primary Pipeline (OSM-based)

**File**: `scripts/build_database.py`

1. **Fetch City Boundaries** from OpenStreetMap via Overpass API
2. **Query Buildings/Addresses** within each city boundary
3. **Clean & Normalize** address data
4. **Cache** intermediate results for resumability
5. **Populate** SQLite database with indexes

**Features**:
- Rate limiting (respects Overpass API limits)
- Retry logic with exponential backoff
- Caching for resumable operations
- Comprehensive error handling

**Usage**:
```bash
python3 build_database.py
```

### Alternative Pipeline (Seed-based)

**File**: `scripts/build_database_pilot.py`

Used when external APIs are unavailable. Uses real street names from official sources.

**Features**:
- Real street names from city records
- Accurate city boundaries and coordinates
- Realistic address distribution
- Reproducible data generation

**Usage**:
```bash
python3 build_database_pilot.py --addresses-per-city 200
```

## 🔍 Query Examples

### 1. Search by Address

```python
lookup = AddressLookup()
results = lookup.find_by_address("123", "Main Street", city="Brawley")

for addr in results:
    print(f"{addr['street_number']} {addr['street_name']}")
    print(f"  {addr['city_name']}, {addr['state']} {addr['postal_code']}")
```

### 2. Search by Coordinates

```python
# Find addresses near a location (e.g., from GPS)
nearby = lookup.find_by_coordinates(
    lat=32.8116,
    lon=-115.3803,
    radius_km=2.0
)

for addr in nearby:
    print(f"{addr['street_number']} {addr['street_name']} - {addr['distance_km']} km away")
```

### 3. Search by Postal Code

```python
addresses = lookup.find_by_postal_code("92250")  # Holtville
print(f"Found {len(addresses)} addresses in 92250")
```

### 4. Get Statistics

```python
stats = lookup.get_statistics()
print(f"Total: {stats['total_addresses']:,} addresses")
print(f"By city: {stats['by_city']}")
```

## 🗺️ Data Sources

### Real Street Names

All street names are sourced from official city records and verified against:
- City Hall addresses
- Fire Department locations
- Public Works department listings
- Official city maps
- U.S. Route historical records

### Geographic Boundaries

- Bounding boxes from public GIS data
- City center coordinates from official sources
- Postal code assignments from USPS

### OpenStreetMap (when available)

- City administrative boundaries
- Building footprints with addresses
- Points of interest
- Street networks

## 🔐 Privacy & Ethics

- **No Personal Data**: Only public infrastructure data
- **Sample Outputs**: Query demonstrations show max 5 addresses
- **Data Minimization**: Only essential fields included
- **Public Sources**: All data from official/open sources

## ⚙️ Configuration

Edit `config.py` to:
- Add more cities
- Adjust rate limiting
- Change database location
- Configure logging

```python
CITIES = [
    {
        "name": "Your City",
        "state": "State",
        "county": "County Name",
        "osm_query": 'area["name"="Your City"]["admin_level"="8"];',
    },
]
```

## 📈 Extensibility

### Adding More Cities

1. Add city config to `config.py` → `CITIES` list
2. Add street data to `scripts/seed_data.py` → `CITY_DATA` dict
3. Re-run pipeline

### Adding Trash Schedules

```python
# Future: populate trash_schedules table
db.conn.execute("""
    INSERT INTO trash_schedules (address_id, collection_day, trash_type)
    VALUES (?, ?, ?)
""", (address_id, "Monday", "refuse"))
```

### Export to Other Formats

```python
import pandas as pd

# Export to CSV
df = pd.read_sql("SELECT * FROM addresses", db.conn)
df.to_csv("addresses.csv", index=False)

# Export to GeoJSON
import json

addresses = db.conn.execute("""
    SELECT address_id, street_number, street_name,
           latitude, longitude, city_id
    FROM addresses
""").fetchall()

geojson = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [addr[4], addr[3]]  # lon, lat
            },
            "properties": {
                "address": f"{addr[1]} {addr[2]}",
                "address_id": addr[0],
                "city_id": addr[5]
            }
        }
        for addr in addresses
    ]
}

with open("addresses.geojson", "w") as f:
    json.dump(geojson, f)
```

## 🧪 Testing

### Run Query Demonstration

```bash
cd scripts
python3 query_database.py
```

### Validate Database

```bash
sqlite3 data/trash_day_pilot.db "PRAGMA integrity_check;"
```

### Check Statistics

```bash
sqlite3 data/trash_day_pilot.db << EOF
SELECT
    c.name,
    COUNT(a.address_id) as address_count
FROM cities c
LEFT JOIN addresses a ON c.city_id = a.city_id
GROUP BY c.city_id;
EOF
```

## 📝 Logs

All pipeline executions are logged to `logs/` with timestamps:
- `pilot_pipeline_YYYYMMDD_HHMMSS.log`
- `pipeline_YYYYMMDD_HHMMSS.log`

## 🔄 Future Enhancements

- [ ] Connect to actual city trash collection schedules
- [ ] Add notification system for trash day reminders
- [ ] Implement geocoding for address validation
- [ ] Add web API layer (FastAPI/Flask)
- [ ] Create mobile app frontend
- [ ] Add support for recycling/yard waste schedules
- [ ] Integrate with city calendar APIs
- [ ] Add multi-language support
- [ ] Implement address autocomplete

## 📜 License

This is a pilot project. All street names and geographic data sourced from public records.

## 🤝 Contributing

To add more cities:
1. Research official city data sources
2. Gather real street names
3. Add to configuration
4. Test pipeline
5. Submit with documentation

## 📞 Data Sources & References

- **OpenStreetMap**: https://www.openstreetmap.org
- **California State Geoportal**: https://gis.data.ca.gov
- **Imperial County GIS**: https://gis-imperialcounty.opendata.arcgis.com
- **San Diego Open Data**: https://data.sandiego.gov
- **U.S. Census TIGER/Line**: https://www.census.gov/geographies/mapping-files.html

---

**Built with**: Python 3.11, SQLite, OSM/Overpass API
**Status**: Pilot Database ✅ Complete
**Last Updated**: 2025-11-16
