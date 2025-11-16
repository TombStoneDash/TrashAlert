"""
Database manager for trash day lookup pilot
Handles SQLite database creation, schema management, and data operations
"""
import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import sys
sys.path.append('..')
from config import DB_PATH

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manage SQLite database for trash day lookup"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None

    def connect(self):
        """Connect to database"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        logger.info(f"Connected to database: {self.db_path}")
        return self.conn

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def create_schema(self):
        """Create database schema"""
        if not self.conn:
            self.connect()

        cursor = self.conn.cursor()

        # Cities table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cities (
                city_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                state TEXT NOT NULL,
                county TEXT,
                osm_relation_id INTEGER,
                boundary_geojson TEXT,
                bbox_north REAL,
                bbox_south REAL,
                bbox_east REAL,
                bbox_west REAL,
                population INTEGER,
                data_fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name, state)
            )
        """)

        # Addresses table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS addresses (
                address_id INTEGER PRIMARY KEY AUTOINCREMENT,
                city_id INTEGER NOT NULL,
                street_number TEXT,
                street_name TEXT NOT NULL,
                unit TEXT,
                postal_code TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                osm_id INTEGER,
                osm_type TEXT,
                building_type TEXT,
                data_source TEXT DEFAULT 'osm',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (city_id) REFERENCES cities(city_id),
                UNIQUE(osm_id, osm_type)
            )
        """)

        # Trash schedules table (for future use)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trash_schedules (
                schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                address_id INTEGER NOT NULL,
                collection_day TEXT,
                collection_week TEXT,
                trash_type TEXT NOT NULL,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (address_id) REFERENCES addresses(address_id)
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_addresses_city
            ON addresses(city_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_addresses_location
            ON addresses(latitude, longitude)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_addresses_postal
            ON addresses(postal_code)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_schedules_address
            ON trash_schedules(address_id)
        """)

        self.conn.commit()
        logger.info("Database schema created successfully")

    def insert_city(self, city_data: Dict) -> int:
        """
        Insert or update city record

        Args:
            city_data: Dict containing city information

        Returns:
            city_id of inserted/updated record
        """
        if not self.conn:
            self.connect()

        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO cities (
                name, state, county, osm_relation_id, boundary_geojson,
                bbox_north, bbox_south, bbox_east, bbox_west, population
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name, state) DO UPDATE SET
                county = excluded.county,
                osm_relation_id = excluded.osm_relation_id,
                boundary_geojson = excluded.boundary_geojson,
                bbox_north = excluded.bbox_north,
                bbox_south = excluded.bbox_south,
                bbox_east = excluded.bbox_east,
                bbox_west = excluded.bbox_west,
                population = excluded.population,
                data_fetched_at = CURRENT_TIMESTAMP
        """, (
            city_data.get('name'),
            city_data.get('state'),
            city_data.get('county'),
            city_data.get('osm_relation_id'),
            city_data.get('boundary_geojson'),
            city_data.get('bbox_north'),
            city_data.get('bbox_south'),
            city_data.get('bbox_east'),
            city_data.get('bbox_west'),
            city_data.get('population'),
        ))

        self.conn.commit()

        # Get the city_id
        cursor.execute("""
            SELECT city_id FROM cities WHERE name = ? AND state = ?
        """, (city_data['name'], city_data['state']))

        city_id = cursor.fetchone()[0]
        logger.info(f"Inserted/updated city: {city_data['name']} (ID: {city_id})")

        return city_id

    def insert_addresses_batch(self, addresses: List[Dict]) -> int:
        """
        Insert multiple addresses in batch

        Args:
            addresses: List of address dicts

        Returns:
            Number of addresses inserted
        """
        if not self.conn:
            self.connect()

        cursor = self.conn.cursor()
        inserted = 0

        for addr in addresses:
            try:
                cursor.execute("""
                    INSERT INTO addresses (
                        city_id, street_number, street_name, unit, postal_code,
                        latitude, longitude, osm_id, osm_type, building_type, data_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(osm_id, osm_type) DO NOTHING
                """, (
                    addr.get('city_id'),
                    addr.get('street_number'),
                    addr.get('street_name'),
                    addr.get('unit'),
                    addr.get('postal_code'),
                    addr.get('latitude'),
                    addr.get('longitude'),
                    addr.get('osm_id'),
                    addr.get('osm_type'),
                    addr.get('building_type'),
                    addr.get('data_source', 'osm'),
                ))
                if cursor.rowcount > 0:
                    inserted += 1
            except sqlite3.IntegrityError as e:
                logger.warning(f"Skipping duplicate address: {addr.get('osm_id')} - {e}")
                continue

        self.conn.commit()
        logger.info(f"Inserted {inserted} new addresses")

        return inserted

    def get_city_stats(self) -> List[Dict]:
        """Get statistics for each city"""
        if not self.conn:
            self.connect()

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                c.city_id,
                c.name,
                c.state,
                c.county,
                COUNT(a.address_id) as address_count,
                c.bbox_north,
                c.bbox_south,
                c.bbox_east,
                c.bbox_west,
                c.data_fetched_at
            FROM cities c
            LEFT JOIN addresses a ON c.city_id = a.city_id
            GROUP BY c.city_id
            ORDER BY c.name
        """)

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_sample_addresses(self, city_id: int, limit: int = 5) -> List[Dict]:
        """Get sample addresses for a city"""
        if not self.conn:
            self.connect()

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                street_number,
                street_name,
                unit,
                postal_code,
                latitude,
                longitude,
                building_type
            FROM addresses
            WHERE city_id = ?
            ORDER BY RANDOM()
            LIMIT ?
        """, (city_id, limit))

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_total_addresses(self) -> int:
        """Get total number of addresses in database"""
        if not self.conn:
            self.connect()

        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM addresses")
        return cursor.fetchone()[0]


if __name__ == "__main__":
    # Test database creation
    logging.basicConfig(level=logging.INFO)
    db = DatabaseManager()
    db.connect()
    db.create_schema()

    # Test city insertion
    test_city = {
        'name': 'Test City',
        'state': 'California',
        'county': 'Test County',
        'osm_relation_id': 12345,
        'bbox_north': 33.0,
        'bbox_south': 32.5,
        'bbox_east': -115.0,
        'bbox_west': -116.0,
    }
    city_id = db.insert_city(test_city)
    print(f"Test city ID: {city_id}")

    db.close()
