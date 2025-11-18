#!/usr/bin/env python3
"""
Address normalization and deduplication script.

Loads sampled addresses from CSV, normalizes them to a canonical form,
deduplicates based on (city_id, full_address), and writes to SQLite and CSV.
"""

import csv
import sqlite3
import re
from collections import defaultdict
from pathlib import Path


# Street suffix abbreviations mapping
STREET_SUFFIXES = {
    'STREET': 'ST',
    'AVENUE': 'AVE',
    'BOULEVARD': 'BLVD',
    'ROAD': 'RD',
    'DRIVE': 'DR',
    'LANE': 'LN',
    'COURT': 'CT',
    'CIRCLE': 'CIR',
    'PLACE': 'PL',
    'PARKWAY': 'PKWY',
    'TERRACE': 'TER',
    'WAY': 'WAY',
    'HIGHWAY': 'HWY',
    'ALLEY': 'ALY',
    'PLAZA': 'PLZ',
}


def normalize_street_name(street: str) -> str:
    """
    Normalize a street name to canonical form.

    - Uppercase
    - Replace common suffixes with standard abbreviations
    - Remove duplicate spaces
    - Trim whitespace
    """
    if not street:
        return ""

    # Uppercase and clean whitespace
    normalized = street.upper().strip()

    # Remove duplicate spaces
    normalized = re.sub(r'\s+', ' ', normalized)

    # Replace street suffixes with abbreviations
    for full, abbrev in STREET_SUFFIXES.items():
        # Match whole word at end of string
        pattern = r'\b' + full + r'\b$'
        normalized = re.sub(pattern, abbrev, normalized)

    return normalized


def create_full_address(house_number: str, street: str, city_name: str) -> str:
    """
    Create a full address in canonical format.

    Format: "{house_number} {street}, {city_name}, CA, USA"
    """
    normalized_street = normalize_street_name(street)
    house_number = str(house_number).strip()
    city_name = city_name.strip()

    return f"{house_number} {normalized_street}, {city_name}, CA, USA"


def load_addresses_from_csv(csv_path: str) -> list:
    """Load addresses from CSV file."""
    addresses = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            addresses.append({
                'city_name': row['city_name'],
                'subdivision_id': row['subdivision_id'],
                'house_number': row['house_number'],
                'street': row['street'],
                'lat': row['lat'],
                'lon': row['lon'],
                'osm_id': row['osm_id']
            })

    return addresses


def setup_database(db_path: str):
    """Create necessary tables in the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create cities table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)

    # Create addresses table matching src/models.py schema
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            house_number TEXT NOT NULL,
            street TEXT NOT NULL,
            city TEXT NOT NULL,
            subdivision_id TEXT,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            normalized_address TEXT NOT NULL,
            trash_day_of_week TEXT,
            osm_id TEXT,
            source TEXT
        )
    """)

    # Create index on normalized_address for faster lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_addresses_normalized
        ON addresses(normalized_address)
    """)

    # Also create addresses_normalized table for CSV export compatibility
    cursor.execute("""
        DROP TABLE IF EXISTS addresses_normalized
    """)

    cursor.execute("""
        CREATE TABLE addresses_normalized (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city_id INTEGER NOT NULL,
            city_name TEXT NOT NULL,
            house_number TEXT NOT NULL,
            street_normalized TEXT NOT NULL,
            full_address TEXT NOT NULL,
            lat REAL,
            lon REAL,
            osm_id TEXT,
            FOREIGN KEY (city_id) REFERENCES cities(id),
            UNIQUE(city_id, full_address)
        )
    """)

    conn.commit()
    return conn


def get_or_create_city_id(cursor, city_name: str) -> int:
    """Get city ID, creating it if it doesn't exist."""
    cursor.execute("SELECT id FROM cities WHERE name = ?", (city_name,))
    result = cursor.fetchone()

    if result:
        return result[0]

    cursor.execute("INSERT INTO cities (name) VALUES (?)", (city_name,))
    return cursor.lastrowid


def normalize_and_dedupe(addresses: list, conn: sqlite3.Connection):
    """
    Normalize addresses, deduplicate, and insert into database.

    Returns stats about the process.
    """
    cursor = conn.cursor()

    # Track stats
    stats = {
        'raw_count_by_city': defaultdict(int),
        'normalized_count_by_city': defaultdict(int),
        'duplicates_removed': 0,
        'total_raw': 0,
        'total_normalized': 0
    }

    # Track unique addresses per city to count duplicates
    seen_addresses = set()

    print("Processing addresses...")

    for addr in addresses:
        city_name = addr['city_name']
        stats['raw_count_by_city'][city_name] += 1
        stats['total_raw'] += 1

        # Get or create city ID
        city_id = get_or_create_city_id(cursor, city_name)

        # Create normalized full address
        full_address = create_full_address(
            addr['house_number'],
            addr['street'],
            city_name
        )

        # Check for duplicates
        dedupe_key = (city_id, full_address)
        if dedupe_key in seen_addresses:
            stats['duplicates_removed'] += 1
            continue

        seen_addresses.add(dedupe_key)

        # Normalize street name
        street_normalized = normalize_street_name(addr['street'])

        # Insert into addresses_normalized table (for CSV export)
        try:
            cursor.execute("""
                INSERT INTO addresses_normalized
                (city_id, city_name, house_number, street_normalized, full_address, lat, lon, osm_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                city_id,
                city_name,
                addr['house_number'],
                street_normalized,
                full_address,
                float(addr['lat']) if addr['lat'] else None,
                float(addr['lon']) if addr['lon'] else None,
                addr['osm_id']
            ))

            stats['normalized_count_by_city'][city_name] += 1
            stats['total_normalized'] += 1

        except sqlite3.IntegrityError:
            # Duplicate found (shouldn't happen with our deduplication above)
            stats['duplicates_removed'] += 1
            continue

        # Insert into addresses table (main table matching src/models.py)
        try:
            cursor.execute("""
                INSERT INTO addresses
                (house_number, street, city, subdivision_id, lat, lon,
                 normalized_address, trash_day_of_week, osm_id, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                addr['house_number'],
                street_normalized,
                city_name,
                addr.get('subdivision_id'),
                float(addr['lat']) if addr['lat'] else None,
                float(addr['lon']) if addr['lon'] else None,
                full_address,
                None,  # trash_day_of_week will be populated later
                addr.get('osm_id'),
                'osm'  # source is OSM data
            ))

        except sqlite3.IntegrityError:
            # Duplicate in addresses table - this is okay, skip silently
            pass

    conn.commit()
    return stats


def export_to_csv(db_path: str, csv_path: str):
    """Export normalized addresses to CSV."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT city_id, city_name, house_number, street_normalized,
               full_address, lat, lon, osm_id
        FROM addresses_normalized
        ORDER BY city_name, full_address
    """)

    rows = cursor.fetchall()

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'city_id', 'city_name', 'house_number', 'street_normalized',
            'full_address', 'lat', 'lon', 'osm_id'
        ])
        writer.writerows(rows)

    conn.close()
    print(f"\nExported {len(rows)} normalized addresses to {csv_path}")


def print_stats_report(stats: dict):
    """Print statistics about the normalization process."""
    print("\n" + "=" * 80)
    print("ADDRESS NORMALIZATION REPORT")
    print("=" * 80)

    print(f"\nTotal raw addresses: {stats['total_raw']}")
    print(f"Total normalized addresses: {stats['total_normalized']}")
    print(f"Duplicates removed: {stats['duplicates_removed']}")

    print("\nPer-city breakdown:")
    print(f"{'City':<30} {'Raw Count':<15} {'Normalized Count':<20} {'Removed':<10}")
    print("-" * 80)

    all_cities = sorted(set(list(stats['raw_count_by_city'].keys()) +
                            list(stats['normalized_count_by_city'].keys())))

    for city in all_cities:
        raw = stats['raw_count_by_city'][city]
        normalized = stats['normalized_count_by_city'][city]
        removed = raw - normalized
        print(f"{city:<30} {raw:<15} {normalized:<20} {removed:<10}")

    print("=" * 80)


def show_schema(db_path: str):
    """Display the schema of the addresses_normalized table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT sql FROM sqlite_master
        WHERE type='table' AND name='addresses_normalized'
    """)

    schema = cursor.fetchone()
    if schema:
        print("\n" + "=" * 80)
        print("ADDRESSES_NORMALIZED TABLE SCHEMA")
        print("=" * 80)
        print(schema[0])
        print("=" * 80)

    conn.close()


def main():
    """Main execution function."""
    # Paths - updated to use addresses_osm_raw.csv and trashalert.db
    csv_input = 'data/addresses_osm_raw.csv'
    csv_output = 'data/addresses_normalized.csv'
    db_path = 'data/trashalert.db'

    print("Starting address normalization and deduplication...")

    # Load addresses from CSV
    print(f"\nLoading addresses from {csv_input}...")
    addresses = load_addresses_from_csv(csv_input)
    print(f"Loaded {len(addresses)} addresses")

    # Setup database
    print(f"\nSetting up database at {db_path}...")
    conn = setup_database(db_path)

    # Normalize and deduplicate
    stats = normalize_and_dedupe(addresses, conn)

    # Export to CSV
    export_to_csv(db_path, csv_output)

    # Print stats report
    print_stats_report(stats)

    # Show schema
    show_schema(db_path)

    # Show sample data from addresses table
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM addresses LIMIT 5")
    rows = cursor.fetchall()

    if rows:
        print("\n" + "=" * 80)
        print("SAMPLE ADDRESSES IN 'addresses' TABLE")
        print("=" * 80)
        cursor.execute("PRAGMA table_info(addresses)")
        columns = [col[1] for col in cursor.fetchall()]

        for row in rows:
            for col, val in zip(columns, row):
                print(f"  {col}: {val}")
            print("-" * 80)

    # Show counts
    cursor.execute("SELECT COUNT(*) FROM addresses")
    addresses_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM addresses_normalized")
    addresses_normalized_count = cursor.fetchone()[0]

    print(f"\nTotal rows in 'addresses' table: {addresses_count}")
    print(f"Total rows in 'addresses_normalized' table: {addresses_normalized_count}")

    conn.close()
    print("\nNormalization complete!")


if __name__ == '__main__':
    main()
