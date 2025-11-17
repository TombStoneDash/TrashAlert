#!/usr/bin/env python3
"""
Create the trashpilot.db database schema.
This creates tables for addresses, crowd reports, and crowd consensus.
"""

import sqlite3
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_database(db_path: Path):
    """Create the database schema."""
    logger.info(f"Creating database at {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create addresses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            city_name TEXT NOT NULL,
            subdivision_id TEXT,
            house_number TEXT NOT NULL,
            street TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            osm_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(city_name, house_number, street)
        )
    """)
    logger.info("✓ Created addresses table")

    # Create crowd_reports table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crowd_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            address_id INTEGER NOT NULL,
            reported_trash_day TEXT NOT NULL,
            reported_recycling_day TEXT,
            reported_green_day TEXT,
            reported_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            report_source TEXT,
            user_hash TEXT,
            FOREIGN KEY (address_id) REFERENCES addresses(id),
            CHECK (reported_trash_day IN ('MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'))
        )
    """)
    logger.info("✓ Created crowd_reports table")

    # Create crowd_consensus table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crowd_consensus (
            address_id INTEGER PRIMARY KEY,
            trash_day TEXT,
            recycling_day TEXT,
            green_day TEXT,
            reports_count INTEGER NOT NULL DEFAULT 0,
            agreement_ratio REAL,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (address_id) REFERENCES addresses(id)
        )
    """)
    logger.info("✓ Created crowd_consensus table")

    # Create indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_crowd_reports_address ON crowd_reports(address_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_addresses_city ON addresses(city_name)")
    logger.info("✓ Created indexes")

    conn.commit()
    conn.close()

    logger.info(f"✓ Database created successfully at {db_path}")


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent
    db_path = base_dir / 'trashpilot.db'

    if db_path.exists():
        logger.warning(f"Database already exists at {db_path}")
        response = input("Do you want to recreate it? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Aborted")
            return 1
        db_path.unlink()
        logger.info("Deleted existing database")

    create_database(db_path)
    return 0


if __name__ == '__main__':
    exit(main())
