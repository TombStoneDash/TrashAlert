#!/usr/bin/env python3
"""
Initialize the TrashAlert database with necessary tables.
"""

import sqlite3
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_database(db_path: Path) -> None:
    """
    Initialize the database with all necessary tables.

    Args:
        db_path: Path to the SQLite database file
    """
    logger.info(f"Initializing database at {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Create cities table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cities (
                city_id INTEGER PRIMARY KEY AUTOINCREMENT,
                city_name TEXT NOT NULL UNIQUE,
                state TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create subdivisions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subdivisions (
                subdivision_id INTEGER PRIMARY KEY AUTOINCREMENT,
                city_id INTEGER NOT NULL,
                subdivision_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (city_id) REFERENCES cities(city_id)
            )
        """)

        # Create addresses table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS addresses (
                address_id INTEGER PRIMARY KEY AUTOINCREMENT,
                city_id INTEGER NOT NULL,
                subdivision_id INTEGER,
                house_number TEXT,
                street TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                osm_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (city_id) REFERENCES cities(city_id),
                FOREIGN KEY (subdivision_id) REFERENCES subdivisions(subdivision_id)
            )
        """)

        # Create address_pickup_info table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS address_pickup_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address_id INTEGER NOT NULL,
                city_id INTEGER NOT NULL,
                pickup_zone_id TEXT NOT NULL,
                trash_day_of_week TEXT,
                recycling_day_of_week TEXT,
                green_waste_day_of_week TEXT,
                source TEXT DEFAULT 'CITY_GIS',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (address_id) REFERENCES addresses(address_id),
                FOREIGN KEY (city_id) REFERENCES cities(city_id),
                UNIQUE(address_id)
            )
        """)

        # Create pickup_zones table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pickup_zones (
                zone_id INTEGER PRIMARY KEY AUTOINCREMENT,
                city_id INTEGER NOT NULL,
                zone_name TEXT NOT NULL,
                zone_identifier TEXT,
                geometry_reference TEXT,
                metadata TEXT,
                source TEXT DEFAULT 'CITY_GIS',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (city_id) REFERENCES cities(city_id),
                UNIQUE(city_id, zone_identifier)
            )
        """)

        # Create schedules table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedules (
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                city_id INTEGER NOT NULL,
                pickup_zone_id INTEGER,
                trash_day_of_week TEXT,
                recycling_day_of_week TEXT,
                green_waste_day_of_week TEXT,
                bulk_pickup_schedule TEXT,
                source TEXT DEFAULT 'CITY_GIS',
                effective_date DATE,
                expiration_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (city_id) REFERENCES cities(city_id),
                FOREIGN KEY (pickup_zone_id) REFERENCES pickup_zones(zone_id)
            )
        """)

        # Create schedule_exceptions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedule_exceptions (
                exception_id INTEGER PRIMARY KEY AUTOINCREMENT,
                city_id INTEGER NOT NULL,
                holiday_name TEXT NOT NULL,
                exception_date DATE NOT NULL,
                rule_description TEXT,
                affected_service_types TEXT,
                makeup_date DATE,
                source TEXT DEFAULT 'CITY_GIS',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (city_id) REFERENCES cities(city_id),
                UNIQUE(city_id, exception_date, holiday_name)
            )
        """)

        # Create crowd_reports table for crowdsourced data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crowd_reports (
                report_id INTEGER PRIMARY KEY AUTOINCREMENT,
                address_id INTEGER NOT NULL,
                reported_trash_day TEXT,
                reported_recycling_day TEXT,
                reported_green_day TEXT,
                reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                report_source TEXT DEFAULT 'USER',
                user_hash TEXT,
                FOREIGN KEY (address_id) REFERENCES addresses(address_id)
            )
        """)

        # Create crowd_consensus table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crowd_consensus (
                consensus_id INTEGER PRIMARY KEY AUTOINCREMENT,
                address_id INTEGER NOT NULL,
                trash_day TEXT,
                recycling_day TEXT,
                green_day TEXT,
                reports_count INTEGER DEFAULT 0,
                agreement_ratio REAL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (address_id) REFERENCES addresses(address_id),
                UNIQUE(address_id)
            )
        """)

        # Create indexes for better query performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_addresses_city
            ON addresses(city_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_addresses_coords
            ON addresses(lat, lon)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pickup_info_address
            ON address_pickup_info(address_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pickup_info_city
            ON address_pickup_info(city_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pickup_zones_city
            ON pickup_zones(city_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_schedules_city
            ON schedules(city_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_schedules_zone
            ON schedules(pickup_zone_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_exceptions_city
            ON schedule_exceptions(city_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_exceptions_date
            ON schedule_exceptions(exception_date)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_crowd_reports_address
            ON crowd_reports(address_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_crowd_consensus_address
            ON crowd_consensus(address_id)
        """)

        conn.commit()
        logger.info("Database schema created successfully")

        # Print table info
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            ORDER BY name
        """)
        tables = cursor.fetchall()
        logger.info(f"Created tables: {', '.join([t[0] for t in tables])}")

    except Exception as e:
        logger.error(f"Error creating database schema: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
Initialize the TrashAlert database with sample data.
Creates tables and loads address data with mock pickup schedules.
"""

import sqlite3
import pandas as pd
import random
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set seed for reproducible mock data
random.seed(42)

def normalize_address(house_number: str, street: str, city: str) -> str:
    """
    Simple address normalization function.
    Converts to lowercase, removes extra spaces, standardizes abbreviations.
    """
    # Standardize street suffixes
    suffix_map = {
        'avenue': 'ave',
        'street': 'st',
        'boulevard': 'blvd',
        'road': 'rd',
        'drive': 'dr',
        'court': 'ct',
        'lane': 'ln',
        'way': 'way',
    }

    # Normalize
    parts = [house_number.strip(), street.strip(), city.strip()]
    normalized = ' '.join(parts).lower()

    # Replace common suffixes
    for long_form, short_form in suffix_map.items():
        normalized = normalized.replace(f' {long_form}', f' {short_form}')

    # Remove extra whitespace
    normalized = ' '.join(normalized.split())

    return normalized


def create_tables(conn: sqlite3.Connection):
    """Create database tables."""
    cursor = conn.cursor()

    # Table for normalized addresses
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS addresses_normalized (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city_name TEXT NOT NULL,
            house_number TEXT NOT NULL,
            street TEXT NOT NULL,
            normalized_address TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            osm_id TEXT,
            subdivision_id TEXT,
            UNIQUE(city_name, house_number, street)
        )
    """)

    # Index on normalized_address for faster lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_normalized_address
        ON addresses_normalized(normalized_address)
    """)

    # Index on city_name for city-specific queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_city_name
        ON addresses_normalized(city_name)
    """)

    # Table for pickup schedules
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS address_pickup_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address_id INTEGER NOT NULL,
            trash_day_of_week TEXT,
            recycling_day_of_week TEXT,
            green_waste_day_of_week TEXT,
            FOREIGN KEY (address_id) REFERENCES addresses_normalized(id)
        )
    """)

    # Index for joining
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_address_id
        ON address_pickup_info(address_id)
    """)

    conn.commit()
    logger.info("✓ Database tables created")


def assign_pickup_schedule(city_name: str, subdivision_id: str = None) -> dict:
    """
    Assign a mock pickup schedule based on city.
    In a real system, this would come from city/county data.
    """
    # Mock schedules for different cities
    city_schedules = {
        'San Diego': [
            {'trash': 'Monday', 'recycling': 'Monday', 'green_waste': 'Monday'},
            {'trash': 'Tuesday', 'recycling': 'Tuesday', 'green_waste': None},
            {'trash': 'Wednesday', 'recycling': 'Wednesday', 'green_waste': 'Wednesday'},
            {'trash': 'Thursday', 'recycling': 'Thursday', 'green_waste': None},
            {'trash': 'Friday', 'recycling': 'Friday', 'green_waste': 'Friday'},
        ],
        'El Centro': [
            {'trash': 'Tuesday', 'recycling': 'Friday', 'green_waste': None},
            {'trash': 'Wednesday', 'recycling': 'Saturday', 'green_waste': None},
            {'trash': 'Thursday', 'recycling': 'Monday', 'green_waste': None},
        ],
        'Calexico': [
            {'trash': 'Monday', 'recycling': 'Thursday', 'green_waste': None},
            {'trash': 'Wednesday', 'recycling': 'Friday', 'green_waste': None},
        ],
        'Brawley': [
            {'trash': 'Tuesday', 'recycling': 'Tuesday', 'green_waste': None},
            {'trash': 'Friday', 'recycling': 'Friday', 'green_waste': None},
        ],
        'Imperial': [
            {'trash': 'Wednesday', 'recycling': None, 'green_waste': None},
        ],
        'Holtville': [
            {'trash': 'Thursday', 'recycling': 'Thursday', 'green_waste': None},
        ],
    }

    # Get schedules for this city, or default
    schedules = city_schedules.get(city_name, [
        {'trash': 'Monday', 'recycling': None, 'green_waste': None}
    ])

    # Pick a random schedule
    schedule = random.choice(schedules)

    return {
        'trash_day_of_week': schedule['trash'],
        'recycling_day_of_week': schedule['recycling'],
        'green_waste_day_of_week': schedule['green_waste'],
    }


def load_address_data(conn: sqlite3.Connection, csv_path: Path):
    """Load address data from CSV into database."""
    logger.info(f"Loading addresses from {csv_path}")

    # Read CSV
    df = pd.read_csv(csv_path)
    logger.info(f"Loaded {len(df)} addresses from {df['city_name'].nunique()} cities")

    cursor = conn.cursor()

    addresses_inserted = 0
    schedules_inserted = 0

    for _, row in df.iterrows():
        # Normalize address
        normalized = normalize_address(
            str(row['house_number']),
            str(row['street']),
            str(row['city_name'])
        )

        # Insert address
        try:
            cursor.execute("""
                INSERT INTO addresses_normalized
                (city_name, house_number, street, normalized_address, lat, lon, osm_id, subdivision_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row['city_name'],
                str(row['house_number']),
                row['street'],
                normalized,
                row['lat'],
                row['lon'],
                row['osm_id'],
                row['subdivision_id'] if pd.notna(row['subdivision_id']) else None
            ))

            address_id = cursor.lastrowid
            addresses_inserted += 1

            # Assign and insert pickup schedule
            schedule = assign_pickup_schedule(row['city_name'], row.get('subdivision_id'))

            cursor.execute("""
                INSERT INTO address_pickup_info
                (address_id, trash_day_of_week, recycling_day_of_week, green_waste_day_of_week)
                VALUES (?, ?, ?, ?)
            """, (
                address_id,
                schedule['trash_day_of_week'],
                schedule['recycling_day_of_week'],
                schedule['green_waste_day_of_week']
            ))

            schedules_inserted += 1

        except sqlite3.IntegrityError:
            # Skip duplicates
            continue

    conn.commit()

    logger.info(f"✓ Inserted {addresses_inserted} addresses")
    logger.info(f"✓ Inserted {schedules_inserted} pickup schedules")


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent
    db_path = base_dir / 'data' / 'trashalert.db'

    init_database(db_path)
    logger.info(f"✓ Database initialized at {db_path}")
    csv_path = base_dir / 'data' / 'addresses_sampled_50_per_city.csv'

    # Check if CSV exists
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        logger.error("Please run sample_addresses_per_city.py first")
        return 1

    # Remove old database if it exists
    if db_path.exists():
        logger.info(f"Removing existing database: {db_path}")
        db_path.unlink()

    # Create database
    logger.info(f"Creating database: {db_path}")
    conn = sqlite3.connect(db_path)

    try:
        # Create schema
        create_tables(conn)

        # Load data
        load_address_data(conn, csv_path)

        # Print summary
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM addresses_normalized")
        address_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM address_pickup_info")
        schedule_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT city_name) FROM addresses_normalized")
        city_count = cursor.fetchone()[0]

        logger.info("\n" + "=" * 60)
        logger.info("DATABASE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total addresses: {address_count}")
        logger.info(f"Total schedules: {schedule_count}")
        logger.info(f"Cities: {city_count}")
        logger.info("=" * 60)

        # Show sample data
        logger.info("\nSample addresses with pickup schedules:")
        cursor.execute("""
            SELECT
                a.city_name,
                a.house_number,
                a.street,
                p.trash_day_of_week,
                p.recycling_day_of_week,
                p.green_waste_day_of_week
            FROM addresses_normalized a
            JOIN address_pickup_info p ON a.id = p.address_id
            LIMIT 5
        """)

        for row in cursor.fetchall():
            logger.info(f"  {row[1]} {row[2]}, {row[0]} -> Trash: {row[3]}, Recycling: {row[4]}, Green: {row[5]}")

        logger.info(f"\n✓ Database initialized successfully: {db_path}")

    finally:
        conn.close()

    return 0


if __name__ == '__main__':
    exit(main())
