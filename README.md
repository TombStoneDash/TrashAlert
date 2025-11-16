# TrashAlert

A city-level trash and waste management alert system.

## Project Structure

```
TrashAlert/
├── data/                    # Data storage
│   └── city_boundaries.geojson  # City boundary polygons
├── notebooks/               # Jupyter notebooks for analysis
├── scripts/                 # Python scripts
│   ├── cities_config.py     # Configuration for pilot cities
│   ├── fetch_city_boundaries.py      # Fetch real boundaries from OSM
│   └── generate_sample_boundaries.py # Generate sample boundaries
└── config/                  # Configuration files
```

## Pilot Cities

The project currently includes 6 pilot cities:

1. **San Francisco**, California, USA
2. **Seattle**, Washington, USA
3. **Austin**, Texas, USA
4. **Portland**, Oregon, USA
5. **Denver**, Colorado, USA
6. **Boston**, Massachusetts, USA

## Setup

### Requirements

```bash
pip install osmnx geopandas pandas shapely
```

### Fetching City Boundaries

There are two scripts available for obtaining city boundaries:

#### 1. From OpenStreetMap (Production)

```bash
python scripts/fetch_city_boundaries.py
```

This script uses OSMnx to fetch real city boundaries from OpenStreetMap's Nominatim API. Requires internet access and compliance with OSM's usage policy.

#### 2. Sample Boundaries (Development/Testing)

```bash
python scripts/generate_sample_boundaries.py
```

This script generates approximate city boundaries for development and testing purposes. Use this when OSM API access is not available or for quick testing.

## Data Files

### city_boundaries.geojson

GeoJSON file containing polygon boundaries for all pilot cities. Each feature includes:

- `city_name`: Name of the city
- `state`: State/province
- `country`: Country
- `display_name`: Full display name
- `geometry`: Polygon geometry in WGS84 (EPSG:4326)
- Additional metadata (varies by source)

## Usage

### Loading City Boundaries

```python
import geopandas as gpd

# Load city boundaries
cities = gpd.read_file('data/city_boundaries.geojson')

# Get a specific city
sf = cities[cities['city_name'] == 'San Francisco']
```

### Using City Configuration

```python
from scripts.cities_config import PILOT_CITIES, get_city_by_name

# Get all pilot cities
all_cities = PILOT_CITIES

# Get a specific city
austin = get_city_by_name('Austin')
print(f"{austin['name']}, {austin['state']}")
```

## Next Steps

- Add trash collection zones within each city
- Integrate with city waste management APIs
- Set up alert notification system
- Create web interface for visualization

## License

TBD
