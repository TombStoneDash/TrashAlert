"""
Main pipeline script to build the trash day lookup database
Orchestrates data fetching, processing, and database population
"""
import sys
import logging
from pathlib import Path
from datetime import datetime
import json

# Add parent directory to path
sys.path.append('..')

from config import CITIES, LOG_DIR, PROCESSED_DATA_DIR
from osm_fetcher import OSMFetcher
from db_manager import DatabaseManager
from data_processor import DataProcessor


def setup_logging():
    """Configure logging for the pipeline"""
    log_dir = Path(LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

    return logging.getLogger(__name__)


def fetch_city_data(fetcher: OSMFetcher, city: dict, logger: logging.Logger) -> dict:
    """
    Fetch boundary and address data for a city

    Args:
        fetcher: OSMFetcher instance
        city: City configuration dict
        logger: Logger instance

    Returns:
        Dict with boundary and address data
    """
    city_name = city['name']
    logger.info(f"=" * 60)
    logger.info(f"Processing city: {city_name}, {city['state']}")
    logger.info(f"=" * 60)

    # Fetch boundary
    logger.info(f"Step 1: Fetching boundary for {city_name}")
    boundary_data = fetcher.fetch_city_boundary(city_name, city['osm_query'])

    if not boundary_data:
        logger.error(f"Failed to fetch boundary for {city_name}")
        return None

    # Get bounding box
    bbox = fetcher.get_bbox_from_boundary(boundary_data)
    logger.info(f"Bounding box: {bbox}")

    # Fetch addresses
    logger.info(f"Step 2: Fetching addresses for {city_name}")
    address_data = fetcher.fetch_addresses_in_area(city_name, city['osm_query'])

    if not address_data:
        logger.warning(f"No addresses found for {city_name}")
        address_data = {'elements': []}

    element_count = len(address_data.get('elements', []))
    logger.info(f"Found {element_count} address elements for {city_name}")

    return {
        'city': city,
        'boundary': boundary_data,
        'bbox': bbox,
        'addresses': address_data,
    }


def process_and_store_city(data: dict, db: DatabaseManager, processor: DataProcessor,
                           logger: logging.Logger) -> int:
    """
    Process city data and store in database

    Args:
        data: City data dict (from fetch_city_data)
        db: DatabaseManager instance
        processor: DataProcessor instance
        logger: Logger instance

    Returns:
        Number of addresses inserted
    """
    city = data['city']
    city_name = city['name']

    logger.info(f"Processing and storing data for {city_name}")

    # Prepare city record
    city_record = {
        'name': city_name,
        'state': city['state'],
        'county': city.get('county'),
        'osm_relation_id': None,  # Will extract from boundary if available
        'boundary_geojson': json.dumps(data['boundary']) if data['boundary'] else None,
        'bbox_north': data['bbox']['north'] if data['bbox'] else None,
        'bbox_south': data['bbox']['south'] if data['bbox'] else None,
        'bbox_east': data['bbox']['east'] if data['bbox'] else None,
        'bbox_west': data['bbox']['west'] if data['bbox'] else None,
    }

    # Extract OSM relation ID from boundary
    if data['boundary'] and 'elements' in data['boundary']:
        for elem in data['boundary']['elements']:
            if elem['type'] == 'relation':
                city_record['osm_relation_id'] = elem['id']
                break

    # Insert city
    city_id = db.insert_city(city_record)

    # Process addresses
    addresses = processor.extract_addresses_from_osm(data['addresses'], city_id)
    addresses = processor.deduplicate_addresses(addresses)

    # Validate
    stats = processor.validate_addresses(addresses)
    logger.info(f"Address validation stats: {stats}")

    # Save processed addresses to file
    processed_file = Path(PROCESSED_DATA_DIR) / f"{city_name.lower().replace(' ', '_')}_processed.json"
    processor.save_processed_data(addresses, processed_file)

    # Insert into database
    inserted = db.insert_addresses_batch(addresses)
    logger.info(f"Inserted {inserted} addresses for {city_name}")

    return inserted


def generate_summary_report(db: DatabaseManager, logger: logging.Logger):
    """Generate and display summary report"""
    logger.info("=" * 60)
    logger.info("DATABASE SUMMARY REPORT")
    logger.info("=" * 60)

    stats = db.get_city_stats()

    total_addresses = 0

    for city_stat in stats:
        logger.info(f"\nCity: {city_stat['name']}, {city_stat['state']}")
        logger.info(f"  County: {city_stat['county']}")
        logger.info(f"  Addresses: {city_stat['address_count']:,}")
        logger.info(f"  Bounding Box: N={city_stat['bbox_north']:.4f}, "
                   f"S={city_stat['bbox_south']:.4f}, "
                   f"E={city_stat['bbox_east']:.4f}, "
                   f"W={city_stat['bbox_west']:.4f}")
        logger.info(f"  Data Fetched: {city_stat['data_fetched_at']}")

        total_addresses += city_stat['address_count']

        # Show sample addresses
        if city_stat['address_count'] > 0:
            samples = db.get_sample_addresses(city_stat['city_id'], limit=3)
            logger.info("  Sample Addresses:")
            for sample in samples:
                addr_str = f"{sample['street_number']} {sample['street_name']}"
                if sample['unit']:
                    addr_str += f" #{sample['unit']}"
                if sample['postal_code']:
                    addr_str += f", {sample['postal_code']}"
                logger.info(f"    - {addr_str} ({sample['latitude']:.6f}, {sample['longitude']:.6f})")

    logger.info(f"\n{'=' * 60}")
    logger.info(f"TOTAL ADDRESSES IN DATABASE: {total_addresses:,}")
    logger.info(f"{'=' * 60}")


def main():
    """Main pipeline execution"""
    logger = setup_logging()
    logger.info("Starting trash day lookup database pipeline")
    logger.info(f"Target cities: {len(CITIES)}")

    # Initialize components
    fetcher = OSMFetcher()
    db = DatabaseManager()
    processor = DataProcessor()

    # Connect to database and create schema
    db.connect()
    db.create_schema()

    # Process each city
    total_inserted = 0

    for i, city in enumerate(CITIES, 1):
        logger.info(f"\nProcessing city {i}/{len(CITIES)}")

        try:
            # Fetch data
            city_data = fetch_city_data(fetcher, city, logger)

            if city_data:
                # Process and store
                inserted = process_and_store_city(city_data, db, processor, logger)
                total_inserted += inserted
            else:
                logger.warning(f"Skipping {city['name']} due to data fetch failure")

        except Exception as e:
            logger.error(f"Error processing {city['name']}: {e}", exc_info=True)
            continue

    # Generate summary
    logger.info("\n" + "=" * 60)
    logger.info(f"Pipeline completed! Total addresses inserted: {total_inserted:,}")
    logger.info("=" * 60)

    generate_summary_report(db, logger)

    # Close database
    db.close()
    logger.info("\nPipeline execution completed successfully")


if __name__ == "__main__":
    main()
