#!/usr/bin/env python3
"""
Load addresses from CSV into the trashpilot.db database.
"""

import sqlite3
import pandas as pd
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_addresses(db_path: Path, csv_path: Path):
    """Load addresses from CSV into database."""
    logger.info(f"Loading addresses from {csv_path}")

    # Read CSV
    df = pd.read_csv(csv_path)
    logger.info(f"Loaded {len(df)} addresses from CSV")

    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Insert addresses
    inserted = 0
    skipped = 0

    for _, row in df.iterrows():
        try:
            cursor.execute("""
                INSERT INTO addresses (city_name, subdivision_id, house_number, street, lat, lon, osm_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                row['city_name'],
                row.get('subdivision_id'),
                row['house_number'],
                row['street'],
                row['lat'],
                row['lon'],
                row.get('osm_id')
            ))
            inserted += 1
        except sqlite3.IntegrityError:
            # Duplicate address
            skipped += 1

    conn.commit()
    conn.close()

    logger.info(f"✓ Inserted {inserted} addresses")
    if skipped > 0:
        logger.info(f"  Skipped {skipped} duplicates")

    return inserted


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent
    db_path = base_dir / 'trashpilot.db'
    csv_path = base_dir / 'data' / 'addresses_sampled_50_per_city.csv'

    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        logger.error("Please run create_database.py first")
        return 1

    if not csv_path.exists():
        logger.error(f"CSV file not found at {csv_path}")
        return 1

    load_addresses(db_path, csv_path)
    return 0


if __name__ == '__main__':
    exit(main())
