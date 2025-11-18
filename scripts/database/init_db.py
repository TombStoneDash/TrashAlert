#!/usr/bin/env python3
"""
Initialize the TrashAlert database with necessary tables and seed data.
This is the main database initialization script for the TrashAlert system.
"""

import sys
import logging
import yaml
from pathlib import Path
from sqlalchemy import inspect

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import engine, Base
from app.models import (
    City, PickupZone, Schedule, AddressPickupInfo, Address,
    CrowdReport, CrowdConsensus, APIKey, APIUsage
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_tables():
    """Create all tables using SQLAlchemy models."""
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully")

    # Print created tables
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    logger.info(f"Created tables: {', '.join(sorted(tables))}")


def seed_cities():
    """Seed cities from config/cities.yaml."""
    from sqlalchemy.orm import Session

    logger.info("Seeding cities from config/cities.yaml...")

    # Load cities.yaml
    base_dir = Path(__file__).parent.parent.parent
    cities_yaml_path = base_dir / 'config' / 'cities.yaml'

    if not cities_yaml_path.exists():
        logger.warning(f"cities.yaml not found at {cities_yaml_path}, skipping city seeding")
        return

    with open(cities_yaml_path, 'r') as f:
        data = yaml.safe_load(f)

    cities_data = data.get('cities', [])

    if not cities_data:
        logger.warning("No cities found in cities.yaml")
        return

    # Create session
    session = Session(engine)

    try:
        cities_created = 0
        cities_skipped = 0

        for city_config in cities_data:
            # Create slug from name (lowercase, replace spaces with hyphens)
            slug = city_config['name'].lower().replace(' ', '-')

            # Check if city already exists
            existing = session.query(City).filter_by(slug=slug).first()
            if existing:
                logger.debug(f"City {city_config['name']} already exists, skipping")
                cities_skipped += 1
                continue

            # Create new city
            city = City(
                slug=slug,
                name=city_config['name'],
                state=city_config.get('state'),
                county=city_config.get('county'),
                enabled=True,
                extra_metadata={
                    'state_abbr': city_config.get('state_abbr'),
                    'country': city_config.get('country'),
                    'has_official_pickup_zones': city_config.get('has_official_pickup_zones', False),
                    'pickup_zone_data_source': city_config.get('pickup_zone_data_source'),
                    'notes': city_config.get('notes'),
                }
            )

            session.add(city)
            cities_created += 1
            logger.info(f"Added city: {city.name}, {city.state} (slug: {slug})")

        session.commit()
        logger.info(f"City seeding complete: {cities_created} created, {cities_skipped} skipped")

    except Exception as e:
        logger.error(f"Error seeding cities: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def main():
    """Main entry point."""
    logger.info("Initializing TrashAlert database...")

    # Create tables
    create_tables()

    # Seed cities
    seed_cities()

    logger.info("Database initialization complete!")
    return 0


if __name__ == '__main__':
    exit(main())
