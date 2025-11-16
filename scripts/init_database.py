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


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent
    db_path = base_dir / 'data' / 'trashalert.db'

    init_database(db_path)
    logger.info(f"✓ Database initialized at {db_path}")
    return 0


if __name__ == '__main__':
    exit(main())
