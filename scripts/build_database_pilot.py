"""
Alternative pipeline for building the pilot database using seed data
Uses real street names and city boundaries when external APIs are unavailable
"""
import sys
import logging
from pathlib import Path
from datetime import datetime

sys.path.append('..')

from config import CITIES, LOG_DIR
from db_manager import DatabaseManager
from seed_data import DataSeeder, CITY_DATA


def setup_logging():
    """Configure logging for the pipeline"""
    log_dir = Path(LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"pilot_pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

    return logging.getLogger(__name__)


def build_pilot_database(addresses_per_city: int = 150):
    """
    Build pilot database using real street names and city data

    Args:
        addresses_per_city: Number of addresses to generate per city
    """
    logger = setup_logging()
    logger.info("=" * 70)
    logger.info("STARTING TRASH DAY LOOKUP PILOT DATABASE BUILD")
    logger.info("=" * 70)
    logger.info(f"Generating {addresses_per_city} addresses per city")
    logger.info(f"Target cities: {len(CITIES)}")

    # Initialize components
    db = DatabaseManager()
    seeder = DataSeeder()

    # Connect to database and create schema
    db.connect()
    db.create_schema()
    logger.info("Database schema created successfully")

    total_addresses = 0

    # Process each city
    for i, city_config in enumerate(CITIES, 1):
        city_name = city_config['name']

        logger.info("")
        logger.info("=" * 70)
        logger.info(f"Processing {i}/{len(CITIES)}: {city_name}, {city_config['state']}")
        logger.info("=" * 70)

        try:
            # Get city boundary info
            boundary_info = seeder.get_city_boundary_info(city_name)

            if not boundary_info:
                logger.warning(f"No seed data available for {city_name}, skipping")
                continue

            # Insert city record
            city_id = db.insert_city(boundary_info)
            logger.info(f"Inserted city record (ID: {city_id})")

            # Generate addresses using real street names
            logger.info(f"Generating {addresses_per_city} addresses with real street names...")
            addresses = seeder.generate_addresses_for_city(city_name, count=addresses_per_city)

            # Add city_id to each address
            for addr in addresses:
                addr['city_id'] = city_id

            # Insert addresses into database
            inserted = db.insert_addresses_batch(addresses)
            total_addresses += inserted

            logger.info(f"Inserted {inserted} addresses for {city_name}")

            # Show sample addresses
            if addresses:
                logger.info(f"Sample addresses:")
                for sample in addresses[:3]:
                    addr_str = f"  {sample['street_number']} {sample['street_name']}"
                    if sample['unit']:
                        addr_str += f" {sample['unit']}"
                    addr_str += f", {sample['postal_code']}"
                    logger.info(addr_str)

        except Exception as e:
            logger.error(f"Error processing {city_name}: {e}", exc_info=True)
            continue

    # Generate summary report
    logger.info("")
    logger.info("=" * 70)
    logger.info("PILOT DATABASE BUILD COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Total addresses inserted: {total_addresses:,}")

    generate_summary_report(db, logger)

    # Close database
    db.close()
    logger.info("\nDatabase build completed successfully!")


def generate_summary_report(db: DatabaseManager, logger: logging.Logger):
    """Generate detailed summary report"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("DATABASE SUMMARY REPORT")
    logger.info("=" * 70)

    stats = db.get_city_stats()

    for city_stat in stats:
        logger.info(f"\n{'─' * 70}")
        logger.info(f"City: {city_stat['name']}, {city_stat['state']}")
        logger.info(f"{'─' * 70}")
        logger.info(f"  County: {city_stat['county']}")
        logger.info(f"  Total Addresses: {city_stat['address_count']:,}")
        logger.info(f"  Bounding Box:")
        logger.info(f"    North: {city_stat['bbox_north']:.4f}")
        logger.info(f"    South: {city_stat['bbox_south']:.4f}")
        logger.info(f"    East:  {city_stat['bbox_east']:.4f}")
        logger.info(f"    West:  {city_stat['bbox_west']:.4f}")
        logger.info(f"  Data Fetched: {city_stat['data_fetched_at']}")

        # Show sample addresses (privacy-conscious - only 3 samples)
        if city_stat['address_count'] > 0:
            samples = db.get_sample_addresses(city_stat['city_id'], limit=3)
            logger.info(f"\n  Sample Addresses:")
            for sample in samples:
                addr_str = f"    • {sample['street_number']} {sample['street_name']}"
                if sample['unit']:
                    addr_str += f" {sample['unit']}"
                addr_str += f", {sample['postal_code']}"
                logger.info(addr_str)
                logger.info(f"      Location: ({sample['latitude']:.6f}, {sample['longitude']:.6f})")
                if sample['building_type']:
                    logger.info(f"      Type: {sample['building_type']}")

    # Overall statistics
    total = db.get_total_addresses()
    logger.info(f"\n{'=' * 70}")
    logger.info(f"TOTAL ADDRESSES IN DATABASE: {total:,}")
    logger.info(f"DATABASE FILE: {db.db_path}")
    logger.info(f"{'=' * 70}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build pilot trash day lookup database")
    parser.add_argument(
        "--addresses-per-city",
        type=int,
        default=150,
        help="Number of addresses to generate per city (default: 150)"
    )

    args = parser.parse_args()

    build_pilot_database(addresses_per_city=args.addresses_per_city)
