#!/usr/bin/env python3
"""
Load TrashAlert data into SQLite database.

This script reads:
- city_boundaries.geojson
- subdivision GeoJSONs
- addresses_sampled_50_per_city.csv

And populates a SQLite database with cities, subdivisions, and addresses tables.
"""

import sqlite3
import json
import csv
import os
from pathlib import Path
from typing import Dict, List, Tuple


def create_database(db_path: str) -> sqlite3.Connection:
    """
    Create SQLite database with the required schema.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        Database connection
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create cities table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cities (
            city_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            state TEXT,
            country TEXT
        )
    """)

    # Create subdivisions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subdivisions (
            subdivision_id TEXT PRIMARY KEY,
            city_id INTEGER NOT NULL,
            name TEXT,
            geom_wkt TEXT,
            FOREIGN KEY (city_id) REFERENCES cities(city_id)
        )
    """)

    # Create addresses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city_id INTEGER,
            subdivision_id TEXT,
            house_number TEXT,
            street TEXT,
            lat REAL,
            lon REAL,
            source TEXT,
            FOREIGN KEY (city_id) REFERENCES cities(city_id),
            FOREIGN KEY (subdivision_id) REFERENCES subdivisions(subdivision_id)
        )
    """)

    # Create indexes for better query performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_addresses_city ON addresses(city_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_addresses_subdivision ON addresses(subdivision_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_subdivisions_city ON subdivisions(city_id)")

    conn.commit()
    print("✓ Database schema created")
    return conn


def geojson_to_wkt(geometry: Dict) -> str:
    """
    Convert GeoJSON geometry to WKT (Well-Known Text) format.

    Args:
        geometry: GeoJSON geometry object

    Returns:
        WKT string representation
    """
    geom_type = geometry.get('type')
    coords = geometry.get('coordinates', [])

    if geom_type == 'Point':
        return f"POINT({coords[0]} {coords[1]})"
    elif geom_type == 'Polygon':
        rings = []
        for ring in coords:
            points = ', '.join([f"{pt[0]} {pt[1]}" for pt in ring])
            rings.append(f"({points})")
        return f"POLYGON({', '.join(rings)})"
    elif geom_type == 'MultiPolygon':
        polygons = []
        for polygon in coords:
            rings = []
            for ring in polygon:
                points = ', '.join([f"{pt[0]} {pt[1]}" for pt in ring])
                rings.append(f"({points})")
            polygons.append(f"({', '.join(rings)})")
        return f"MULTIPOLYGON({', '.join(polygons)})"
    else:
        return f"{geom_type.upper()}(...)"


def load_cities(conn: sqlite3.Connection, city_boundaries_path: str) -> Dict[str, int]:
    """
    Load cities from city_boundaries.geojson.

    Args:
        conn: Database connection
        city_boundaries_path: Path to city_boundaries.geojson

    Returns:
        Dictionary mapping city names to city_ids
    """
    cursor = conn.cursor()
    city_name_to_id = {}

    if not os.path.exists(city_boundaries_path):
        print(f"⚠ Warning: {city_boundaries_path} not found, skipping cities")
        return city_name_to_id

    with open(city_boundaries_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    features = data.get('features', [])

    for idx, feature in enumerate(features, start=1):
        props = feature.get('properties', {})
        city_name = props.get('name') or props.get('city') or f"City_{idx}"
        state = props.get('state') or props.get('admin_level_4')
        country = props.get('country') or 'USA'

        cursor.execute("""
            INSERT INTO cities (city_id, name, state, country)
            VALUES (?, ?, ?, ?)
        """, (idx, city_name, state, country))

        city_name_to_id[city_name] = idx

    conn.commit()
    print(f"✓ Loaded {len(features)} cities")
    return city_name_to_id


def load_subdivisions(conn: sqlite3.Connection, data_dir: str, city_name_to_id: Dict[str, int]) -> None:
    """
    Load subdivisions from GeoJSON files in data directory.

    Args:
        conn: Database connection
        data_dir: Path to data directory
        city_name_to_id: Mapping of city names to IDs
    """
    cursor = conn.cursor()
    subdivision_count = 0

    # Look for subdivision GeoJSON files
    data_path = Path(data_dir)
    subdivision_files = list(data_path.glob('*_subdivisions.geojson')) + \
                       list(data_path.glob('subdivisions_*.geojson'))

    if not subdivision_files:
        print("⚠ Warning: No subdivision GeoJSON files found")
        return

    for geojson_file in subdivision_files:
        with open(geojson_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        features = data.get('features', [])

        for feature in features:
            props = feature.get('properties', {})
            geometry = feature.get('geometry', {})

            # Extract subdivision information
            subdivision_id = props.get('id') or props.get('subdivision_id') or \
                           props.get('osm_id') or f"subdiv_{subdivision_count}"
            subdivision_name = props.get('name') or props.get('neighbourhood')

            # Try to determine city
            city_name = props.get('city') or props.get('parent_city')
            city_id = city_name_to_id.get(city_name, 1) if city_name else 1

            # Convert geometry to WKT
            geom_wkt = geojson_to_wkt(geometry) if geometry else None

            cursor.execute("""
                INSERT OR REPLACE INTO subdivisions (subdivision_id, city_id, name, geom_wkt)
                VALUES (?, ?, ?, ?)
            """, (str(subdivision_id), city_id, subdivision_name, geom_wkt))

            subdivision_count += 1

    conn.commit()
    print(f"✓ Loaded {subdivision_count} subdivisions")


def load_addresses(conn: sqlite3.Connection, addresses_csv_path: str, city_name_to_id: Dict[str, int]) -> None:
    """
    Load addresses from CSV file.

    Args:
        conn: Database connection
        addresses_csv_path: Path to addresses CSV file
        city_name_to_id: Mapping of city names to IDs
    """
    cursor = conn.cursor()

    if not os.path.exists(addresses_csv_path):
        print(f"⚠ Warning: {addresses_csv_path} not found, skipping addresses")
        return

    address_count = 0

    with open(addresses_csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            city_name = row.get('city')
            city_id = city_name_to_id.get(city_name) if city_name else None

            subdivision_id = row.get('subdivision_id') or row.get('neighbourhood_id')
            house_number = row.get('house_number') or row.get('housenumber')
            street = row.get('street') or row.get('street_name')

            # Parse lat/lon
            try:
                lat = float(row.get('lat') or row.get('latitude') or 0)
                lon = float(row.get('lon') or row.get('longitude') or 0)
            except (ValueError, TypeError):
                lat, lon = None, None

            source = row.get('source') or 'OSM'

            cursor.execute("""
                INSERT INTO addresses (city_id, subdivision_id, house_number, street, lat, lon, source)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (city_id, subdivision_id, house_number, street, lat, lon, source))

            address_count += 1

    conn.commit()
    print(f"✓ Loaded {address_count} addresses")


def run_sample_queries(conn: sqlite3.Connection) -> None:
    """
    Run sample SQL queries to verify data.

    Args:
        conn: Database connection
    """
    cursor = conn.cursor()

    print("\n" + "="*60)
    print("SAMPLE QUERIES")
    print("="*60)

    # Query 1: Count addresses by city
    print("\nQuery 1: SELECT city_id, COUNT(*) FROM addresses GROUP BY city_id;")
    print("-" * 60)
    cursor.execute("SELECT city_id, COUNT(*) as count FROM addresses GROUP BY city_id")
    results = cursor.fetchall()

    if results:
        print(f"{'City ID':<10} {'Count':<10}")
        print("-" * 20)
        for row in results:
            print(f"{row[0]:<10} {row[1]:<10}")
    else:
        print("No results found")

    # Query 2: Sample addresses
    print("\n\nQuery 2: SELECT * FROM addresses LIMIT 5;")
    print("-" * 60)
    cursor.execute("SELECT * FROM addresses LIMIT 5")
    results = cursor.fetchall()

    if results:
        print(f"{'ID':<6} {'City':<6} {'Subdiv':<15} {'House#':<8} {'Street':<20} {'Lat':<10} {'Lon':<10}")
        print("-" * 80)
        for row in results:
            id_val, city_id, subdiv_id, house_num, street, lat, lon, source = row
            subdiv_short = (subdiv_id[:12] + '...') if subdiv_id and len(subdiv_id) > 15 else (subdiv_id or '')
            street_short = (street[:17] + '...') if street and len(street) > 20 else (street or '')
            print(f"{id_val:<6} {city_id or '':<6} {subdiv_short:<15} {house_num or '':<8} {street_short:<20} {lat or '':<10.6f} {lon or '':<10.6f}")
    else:
        print("No results found")

    # Summary statistics
    print("\n\nDatabase Summary:")
    print("-" * 60)
    cursor.execute("SELECT COUNT(*) FROM cities")
    city_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM subdivisions")
    subdiv_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM addresses")
    addr_count = cursor.fetchone()[0]

    print(f"Cities:       {city_count}")
    print(f"Subdivisions: {subdiv_count}")
    print(f"Addresses:    {addr_count}")
    print("="*60 + "\n")


def main():
    """Main function to orchestrate the data loading."""
    # Define paths
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / 'data'
    db_path = data_dir / 'trashpilot.db'
    city_boundaries_path = data_dir / 'city_boundaries.geojson'
    addresses_csv_path = data_dir / 'addresses_sampled_50_per_city.csv'

    print("="*60)
    print("TrashAlert - SQLite Database Loader")
    print("="*60)
    print(f"\nDatabase: {db_path}")
    print(f"Data directory: {data_dir}\n")

    # Ensure data directory exists
    data_dir.mkdir(exist_ok=True)

    # Create database and schema
    conn = create_database(str(db_path))

    try:
        # Load data
        print("\nLoading data...")
        city_name_to_id = load_cities(conn, str(city_boundaries_path))
        load_subdivisions(conn, str(data_dir), city_name_to_id)
        load_addresses(conn, str(addresses_csv_path), city_name_to_id)

        # Run sample queries
        run_sample_queries(conn)

        print(f"✓ Database successfully created at: {db_path}")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == '__main__':
    main()
