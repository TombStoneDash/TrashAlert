# TrashAlert Database Scripts

This directory contains scripts for managing the TrashAlert database.

## Scripts

### init_db.py

Initializes the TrashAlert database with all necessary tables and indexes.

**Usage:**
```bash
python scripts/database/init_db.py
```

**What it does:**
- Creates all database tables (cities, addresses, pickup_zones, schedules, etc.)
- Sets up foreign key relationships
- Creates indexes for optimal query performance
- Can be run multiple times safely (uses CREATE TABLE IF NOT EXISTS)

**Tables created:**
- `cities` - City metadata
- `addresses` - Address information from OSM
- `subdivisions` - Neighborhood/subdivision data
- `pickup_zones` - Zones within cities for pickup scheduling
- `schedules` - Official trash pickup schedules
- `schedule_exceptions` - Holiday and special event exceptions
- `crowd_reports` - User-submitted pickup day reports
- `crowd_consensus` - Computed consensus from crowdsourced data
- `address_pickup_info` - Legacy backward compatibility table

### inspect_schema.py

Displays detailed information about the database schema.

**Usage:**
```bash
# Inspect default database (trashalert.db in project root)
python scripts/database/inspect_schema.py

# Inspect a specific database file
python scripts/database/inspect_schema.py --db-path /path/to/database.db

# Skip row counts for faster inspection of large databases
python scripts/database/inspect_schema.py --no-counts
```

**What it shows:**
- List of all tables
- Column names, types, and constraints for each table
- Foreign key relationships
- Indexes
- Row counts per table
- Database file size

**Example output:**
```
================================================================================
DATABASE SCHEMA INSPECTION
================================================================================

Database: /home/user/TrashAlert/trashalert.db
Total Tables: 10

Table List: address_pickup_info, addresses, cities, crowd_consensus, ...

================================================================================
TABLE: schedules
================================================================================

COLUMNS:
  Name                      Type            NotNull    Default         PK
  ------------------------- --------------- ---------- --------------- -----
  schedule_id               INTEGER         NO                         YES
  city_id                   INTEGER         YES
  pickup_zone_id            INTEGER         NO
  trash_day_of_week         TEXT            NO
  ...

FOREIGN KEYS:
  pickup_zone_id -> pickup_zones(zone_id)
  city_id -> cities(city_id)

INDEXES:
  - idx_schedules_zone
  - idx_schedules_city

ROW COUNT: 0
```

## Database Schema Overview

### Core Entity Tables
- **cities**: Cities supported by the system
- **addresses**: Individual addresses from OpenStreetMap
- **subdivisions**: Neighborhoods or subdivisions within cities

### Schedule Management
- **pickup_zones**: Geographic zones with distinct pickup schedules
- **schedules**: Official pickup schedules (trash, recycling, green waste)
- **schedule_exceptions**: Holidays and special events affecting pickup

### Crowdsourcing
- **crowd_reports**: Individual user reports about pickup days
- **crowd_consensus**: Computed consensus from multiple reports

### Backward Compatibility
- **address_pickup_info**: Legacy table for direct address-to-schedule mapping

## Database Location

By default, the database is created at:
```
/home/user/TrashAlert/trashalert.db
```

## Common Tasks

### Initialize a fresh database
```bash
# Remove old database if it exists
rm trashalert.db

# Create new database with schema
python scripts/database/init_db.py
```

### Check database structure
```bash
python scripts/database/inspect_schema.py
```

### Backup database
```bash
# Simple file copy
cp trashalert.db trashalert.db.backup

# Or use SQLite's backup command
sqlite3 trashalert.db ".backup trashalert.db.backup"
```

### Query database directly
```bash
# Open SQLite shell
sqlite3 trashalert.db

# Run some queries
sqlite> SELECT * FROM cities;
sqlite> SELECT COUNT(*) FROM addresses;
sqlite> .schema schedules
sqlite> .quit
```

## Foreign Key Relationships

```
cities (1) ─────> (N) addresses
  │                     │
  │                     └──> (N) crowd_reports
  │                     │
  │                     └──> (1) crowd_consensus
  │
  ├────> (N) subdivisions
  │
  ├────> (N) pickup_zones ──> (N) schedules
  │
  └────> (N) schedule_exceptions
```

## Indexes

All foreign keys have indexes for efficient joins. Additional indexes include:
- Address coordinates (lat, lon) for geospatial queries
- Exception dates for date-based lookups
- City IDs on all related tables for city-specific queries

## Development Notes

### Adding a New Table
1. Edit `init_db.py` and add CREATE TABLE statement
2. Add appropriate indexes
3. Run `python scripts/database/init_db.py` to create the table
4. Verify with `python scripts/database/inspect_schema.py`
5. Update this README with new table information

### Modifying an Existing Table
Since we're using SQLite without a migration framework:
1. For adding columns: Use ALTER TABLE statements
2. For complex changes: Create new table, copy data, drop old table, rename new table
3. Always backup database before schema modifications

### Testing
Before deploying schema changes:
1. Test with a separate test database
2. Verify all foreign key relationships work
3. Check that indexes are created properly
4. Ensure backward compatibility with existing code
