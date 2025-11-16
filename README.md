# TrashAlert

A database system for managing city, subdivision, and address data for trash collection routing.

## Project Structure

```
TrashAlert/
├── data/
│   ├── trashpilot.db                          # SQLite database
│   ├── city_boundaries.geojson                # City boundary polygons
│   ├── *_subdivisions.geojson                 # Subdivision/neighborhood boundaries
│   └── addresses_sampled_50_per_city.csv      # Address point data
└── scripts/
    └── load_to_sqlite.py                      # Database loader script
```

## Database Schema

### Tables

**cities**
- `city_id` (INTEGER PRIMARY KEY) - Unique city identifier
- `name` (TEXT) - City name
- `state` (TEXT) - State/province
- `country` (TEXT) - Country

**subdivisions**
- `subdivision_id` (TEXT PRIMARY KEY) - Unique subdivision identifier
- `city_id` (INTEGER) - Foreign key to cities table
- `name` (TEXT) - Subdivision/neighborhood name
- `geom_wkt` (TEXT) - Geometry in Well-Known Text format

**addresses**
- `id` (INTEGER PRIMARY KEY AUTOINCREMENT) - Unique address identifier
- `city_id` (INTEGER) - Foreign key to cities table
- `subdivision_id` (TEXT) - Foreign key to subdivisions table
- `house_number` (TEXT) - House/building number
- `street` (TEXT) - Street name
- `lat` (REAL) - Latitude
- `lon` (REAL) - Longitude
- `source` (TEXT) - Data source (e.g., "OSM")

## Usage

### Loading Data into SQLite

Run the loader script to populate the database:

```bash
python3 scripts/load_to_sqlite.py
```

This script will:
1. Create the SQLite database at `data/trashpilot.db`
2. Read city boundaries from `city_boundaries.geojson`
3. Read subdivision data from `*_subdivisions.geojson` files
4. Read address data from `addresses_sampled_50_per_city.csv`
5. Populate all three tables with proper foreign key relationships
6. Run sample queries to verify the data

### Sample Queries

The script automatically runs these queries to verify the data:

```sql
-- Count addresses by city
SELECT city_id, COUNT(*) FROM addresses GROUP BY city_id;

-- View sample addresses
SELECT * FROM addresses LIMIT 5;
```

### Querying the Database

You can query the database using Python:

```python
import sqlite3

conn = sqlite3.connect('data/trashpilot.db')
cursor = conn.cursor()

# Get all cities
cursor.execute("SELECT * FROM cities")
for row in cursor.fetchall():
    print(row)

conn.close()
```

Or using the sqlite3 command-line tool:

```bash
sqlite3 data/trashpilot.db "SELECT * FROM cities;"
```

## Sample Data

The repository includes sample data for three cities:
- **Austin, Texas** - 10 addresses across 2 subdivisions
- **Portland, Oregon** - 10 addresses across 2 subdivisions
- **Denver, Colorado** - 10 addresses (no subdivisions)

## Requirements

- Python 3.x
- Standard library modules: `sqlite3`, `json`, `csv`, `pathlib`

No external dependencies required!

## Future Enhancements

- **PostGIS Support**: Migrate to PostgreSQL/PostGIS for advanced spatial operations
- **Spatial Indexing**: Add R-tree indexes for faster spatial queries
- **Data Validation**: Add constraints and validation rules
- **API Layer**: Build REST API for data access
- **Route Optimization**: Integrate routing algorithms for trash collection
