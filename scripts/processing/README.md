# Processing Scripts

This directory contains data processing scripts for TrashAlert.

## assign_zones_and_schedules.py

Assigns pickup zones and schedules to addresses using GIS data.

### Purpose

For any city with zone data:
1. Loads city boundaries, subdivisions, pickup zones, and addresses from the database
2. For each address, determines the associated pickup_zone_id using point-in-polygon matching
3. Looks up trash_day_of_week, recycling_day_of_week, and green_waste_day_of_week from zone data
4. Inserts or updates the address_pickup_info table

### Usage

```bash
python3 scripts/processing/assign_zones_and_schedules.py
```

### Requirements

- Database must be initialized (run `scripts/init_database.py` first)
- GIS data must be available in `data/gis/` directory
- Expected file format: `data/gis/{city_name}/pickup_zones_{city_name}.geojson`

### GeoJSON Format

The pickup zones GeoJSON file should follow this structure:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "zone_id": "CITY_ZONE_1",
        "zone_name": "North Zone",
        "trash_day": "Monday",
        "recycling_day": "Monday",
        "green_waste_day": "Thursday"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": [[...]]
      }
    }
  ]
}
```

### Output

The script will:
- Process all cities with available GIS zone data
- Display detailed statistics for each city:
  - Total addresses processed
  - Addresses matched to zones
  - Distribution by zone and trash day
- Print overall statistics:
  - Total addresses matched
  - Success rate
  - Coverage percentage

### Error Handling

- Handles cases where no zone is found → leaves pickup_zone_id NULL but doesn't crash
- Efficient geometry operations using cached prepared geometries
- Logs warnings for unmatched addresses (debug level)
- Continues processing other cities if one fails

### Database Tables

**Input:**
- `cities` - City information
- `addresses` - Address coordinates and details
- `pickup_zones` (GeoJSON files) - Zone boundaries and schedules

**Output:**
- `address_pickup_info` - Assigned zones and schedules for each address
  - `address_id` - Foreign key to addresses
  - `city_id` - Foreign key to cities
  - `pickup_zone_id` - Assigned zone ID
  - `trash_day_of_week` - Trash pickup day
  - `recycling_day_of_week` - Recycling pickup day
  - `green_waste_day_of_week` - Green waste pickup day
  - `source` - Data source (default: 'CITY_GIS')

### Example Output

```
================================================================================
Processing city: Brawley
================================================================================
Loading pickup zones from data/gis/brawley/pickup_zones_brawley.geojson
Loaded 4 pickup zones for Brawley
Retrieved 10 addresses for Brawley
Assigning zones to 10 addresses using 4 zones
✓ Matched 10 addresses, 0 unmatched

📊 Statistics for Brawley:
   Total addresses: 10
   With pickup info: 10
   By zone:
      BRAWLEY_ZONE_2: 5 addresses
      BRAWLEY_ZONE_4: 2 addresses
      BRAWLEY_ZONE_1: 2 addresses
      BRAWLEY_ZONE_3: 1 addresses
   By trash day:
      Tuesday: 5 addresses
      Thursday: 2 addresses
      Monday: 2 addresses
      Wednesday: 1 addresses

📋 Sample assignments:
   100 Main St → Zone BRAWLEY_ZONE_2, Trash: Tuesday
   200 Main St → Zone BRAWLEY_ZONE_2, Trash: Tuesday
   300 Main St → Zone BRAWLEY_ZONE_1, Trash: Monday
```

### Dependencies

- Python 3.7+
- shapely >= 2.0.0
- geopandas >= 0.14.0 (optional, for advanced spatial operations)
- sqlite3 (built-in)
