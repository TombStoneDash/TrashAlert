#!/usr/bin/env python3
"""
Seed the cities table with the 6 pilot cities.
"""

import sqlite3
import logging
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.cities_config import get_pilot_cities, get_city_display_name

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def seed_cities(db_path: Path):
    """
    Seed the cities table with pilot cities from config.

    Args:
        db_path: Path to the database
    """
    logger.info(f"Seeding cities in database: {db_path}")

    if not db_path.exists():
        logger.error(f"Database does not exist: {db_path}")
        logger.error("Run scripts/init_database.py first to create the database")
        return 1

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get pilot cities from config
    pilot_cities = get_pilot_cities()

    logger.info(f"Loading {len(pilot_cities)} pilot cities...")

    inserted = 0
    updated = 0
    skipped = 0

    for city in pilot_cities:
        city_name = city['name']
        state = city.get('state_abbr', city['state'])

        try:
            # Try to insert
            cursor.execute("""
                INSERT INTO cities (city_name, state)
                VALUES (?, ?)
            """, (city_name, state))

            inserted += 1
            logger.info(f"  ✓ Inserted: {get_city_display_name(city)}")

        except sqlite3.IntegrityError:
            # City already exists, update state if needed
            cursor.execute("""
                UPDATE cities
                SET state = ?
                WHERE city_name = ?
            """, (state, city_name))

            if cursor.rowcount > 0:
                updated += 1
                logger.info(f"  ↻ Updated: {get_city_display_name(city)}")
            else:
                skipped += 1
                logger.info(f"  - Skipped: {get_city_display_name(city)} (unchanged)")

    conn.commit()

    # Verify
    cursor.execute("SELECT city_id, city_name, state FROM cities ORDER BY city_name")
    all_cities = cursor.fetchall()

    logger.info("\n" + "=" * 80)
    logger.info("CITIES IN DATABASE")
    logger.info("=" * 80)

    for city_id, name, state in all_cities:
        logger.info(f"  [{city_id}] {name}, {state}")

    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Inserted: {inserted}")
    logger.info(f"Updated: {updated}")
    logger.info(f"Skipped: {skipped}")
    logger.info(f"Total cities in database: {len(all_cities)}")
    logger.info("=" * 80)

    conn.close()

    return 0


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent
    db_path = base_dir / 'data' / 'trashalert.db'

    return seed_cities(db_path)


if __name__ == '__main__':
    exit(main())
