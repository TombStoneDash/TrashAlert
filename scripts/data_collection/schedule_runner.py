#!/usr/bin/env python3
"""
Unified runner for all trash schedule parsers.

This script orchestrates the schedule extraction pipeline:
1. Fetch raw data from city sources
2. Parse and normalize schedules
3. Store results in database
4. Generate reports

Usage:
    # Run all parsers
    python scripts/data_collection/schedule_runner.py --all

    # Run specific city
    python scripts/data_collection/schedule_runner.py --city "El Centro"

    # Dry run (don't write to database)
    python scripts/data_collection/schedule_runner.py --all --dry-run

    # Verbose output
    python scripts/data_collection/schedule_runner.py --all --verbose
"""
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import SessionLocal, engine
from app.models import Base, Schedule, ScheduleException, SourceMetadata, Address, City, PickupZone
from scripts.data_collection.schedule_parsers.el_centro_parser import ElCentroParser
from scripts.data_collection.schedule_parsers.imperial_parser import ImperialParser
from scripts.data_collection.schedule_parsers.san_diego_parser import SanDiegoParser
from scripts.data_collection.schedule_parsers.holtville_parser import HoltvilleParser
from scripts.data_collection.schedule_parsers.brawley_parser import BrawleyParser
from scripts.data_collection.schedule_parsers.calexico_parser import CalexicoParser
from scripts.data_collection.schedule_parsers.brawley_parser import BrawleyParser
from scripts.data_collection.schedule_parsers.calexico_parser import CalexicoParser
from scripts.data_collection.schedule_parsers.holtville_parser import HoltvilleParser
from scripts.data_collection.schedule_parsers.chula_vista_parser import ChulaVistaParser
from scripts.data_collection.schedule_parsers.oceanside_parser import OceansideParser
from scripts.data_collection.schedule_parsers.base_parser import ParseResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ScheduleRunner:
    """Unified runner for schedule parsers."""

    def __init__(self, db: Session, dry_run: bool = False):
        """
        Initialize runner.

        Args:
            db: Database session
            dry_run: If True, don't write to database
        """
        self.db = db
        self.dry_run = dry_run

        # Registry of available parsers
        self.parsers = {
            "El Centro": ElCentroParser,
            "Imperial": ImperialParser,
            "San Diego": SanDiegoParser,
            "Holtville": HoltvilleParser,
            "Brawley": BrawleyParser,
            "Calexico": CalexicoParser,
            "Brawley": BrawleyParser,
            "Calexico": CalexicoParser,
            "Holtville": HoltvilleParser,
            "Chula Vista": ChulaVistaParser,
            "Oceanside": OceansideParser,
        }

    def run_parser(self, city: str) -> ParseResult:
        """
        Run parser for a specific city.

        Args:
            city: City name

        Returns:
            ParseResult from parser

        Raises:
            ValueError: If city parser not found
        """
        parser_class = self.parsers.get(city)
        if not parser_class:
            raise ValueError(f"No parser found for city: {city}")

        logger.info(f"Running parser for {city}...")
        parser = parser_class()
        result = parser.run()

        return result

    def store_results(self, city: str, result: ParseResult) -> Dict[str, int]:
        """
        Store parse results in database and update Address.official_*_day fields.

        Args:
            city: City name
            result: ParseResult from parser

        Returns:
            Dict with counts of stored records
        """
        stats = {
            "source_metadata": 0,
            "schedules": 0,
            "exceptions": 0,
            "pickup_zones": 0,
            "addresses_updated": 0,
            "errors": len(result.errors)
        }

        if self.dry_run:
            logger.info("[DRY RUN] Would store to database:")
            logger.info(f"  - {len(result.schedules)} schedules")
            logger.info(f"  - {len(result.exceptions)} exceptions")
            return stats

        try:
            # Get city record
            city_record = self.db.query(City).filter(City.name == city).first()
            if not city_record:
                logger.warning(f"City '{city}' not found in database. Creating it...")
                # Generate slug from city name (lowercase, replace spaces with underscores)
                slug = city.lower().replace(" ", "_")
                city_record = City(name=city, slug=slug, state="CA")
                self.db.add(city_record)
                self.db.flush()

            # Create source metadata record
            source = SourceMetadata(
                city=city,
                source_type=result.metadata.get("source_format", "unknown"),
                source_url=result.metadata.get("source_url", ""),
                source_name=f"{city} Schedule {datetime.now().year}",
                parser_version=result.metadata.get("parser_version", "1.0.0"),
                parser_name=result.metadata.get("parser_name", "unknown"),
                total_records_extracted=len(result.schedules),
                successful_records=len(result.schedules) - len(result.errors),
                failed_records=len(result.errors),
                extra_data=result.metadata,
                last_fetched_at=datetime.now(),
                last_parsed_at=datetime.now()
            )
            self.db.add(source)
            self.db.flush()  # Get source.id
            stats["source_metadata"] = 1

            # Group schedules by zone to create pickup_zones and schedules
            zone_schedule_map = {}  # zone -> {trash_day, recycling_day, green_day}

            for schedule_data in result.schedules:
                zone_key = schedule_data.zone or "citywide"

                if zone_key not in zone_schedule_map:
                    zone_schedule_map[zone_key] = {
                        "trash_day_of_week": None,
                        "recycling_day_of_week": None,
                        "green_day_of_week": None,
                    }

                # Map collection_type to field name
                if schedule_data.collection_type == "trash":
                    zone_schedule_map[zone_key]["trash_day_of_week"] = schedule_data.day_of_week
                elif schedule_data.collection_type == "recycling":
                    zone_schedule_map[zone_key]["recycling_day_of_week"] = schedule_data.day_of_week
                elif schedule_data.collection_type == "green_waste":
                    zone_schedule_map[zone_key]["green_day_of_week"] = schedule_data.day_of_week

            # Create or update pickup zones and schedules
            zone_id_map = {}  # zone_key -> pickup_zone.id

            for zone_key, schedule_info in zone_schedule_map.items():
                # Create or get pickup zone
                pickup_zone = self.db.query(PickupZone).filter(
                    PickupZone.city_id == city_record.id,
                    PickupZone.name == zone_key
                ).first()

                if not pickup_zone:
                    pickup_zone = PickupZone(
                        city_id=city_record.id,
                        name=zone_key,
                        external_ref=zone_key,
                        extra_metadata={"type": "ADMINISTRATIVE"}  # or "GIS" if using GIS boundaries
                    )
                    self.db.add(pickup_zone)
                    self.db.flush()
                    stats["pickup_zones"] += 1

                zone_id_map[zone_key] = pickup_zone.id

                # Create schedule record for this zone
                schedule = Schedule(
                    city_id=city_record.id,
                    pickup_zone_id=pickup_zone.id,
                    trash_day_of_week=schedule_info["trash_day_of_week"],
                    recycling_day_of_week=schedule_info["recycling_day_of_week"],
                    green_day_of_week=schedule_info["green_day_of_week"],
                    source="OFFICIAL",
                    extra_metadata={
                        "source_id": source.id,
                        "parser_name": result.metadata.get("parser_name", "unknown"),
                        "effective_date": result.metadata.get("effective_date", "2025-01-01")
                    }
                )
                self.db.add(schedule)
                stats["schedules"] += 1

            # Store exceptions (linked to city, not specific schedules for now)
            for exception_data in result.exceptions:
                exception = ScheduleException(
                    schedule_id=None,  # Could link to specific schedule if needed
                    exception_date=exception_data.exception_date,
                    rescheduled_date=exception_data.rescheduled_date,
                    is_cancelled=exception_data.is_cancelled,
                    reason=exception_data.reason,
                    notes=exception_data.notes
                )
                self.db.add(exception)
                stats["exceptions"] += 1

            self.db.flush()

            # NOW THE CRITICAL PART: Update Address.official_*_day fields
            # This makes the schedules visible to the /lookup endpoint
            logger.info(f"Updating addresses with official schedules for {city}...")

            # Get the parser instance to use its zone matching logic
            parser_class = self.parsers.get(city)
            if parser_class:
                parser = parser_class()

                # Get all addresses for this city
                addresses = self.db.query(Address).filter(
                    Address.city_name == city
                ).all()

                logger.info(f"Found {len(addresses)} addresses in {city}")

                for addr in addresses:
                    # Use parser's zone matching logic
                    zone = None
                    if hasattr(parser, 'match_address_to_zone'):
                        zone = parser.match_address_to_zone(addr.normalized_address)
                    elif hasattr(parser, 'match_address_to_neighborhood'):
                        zone = parser.match_address_to_neighborhood(addr.normalized_address)
                    else:
                        # For citywide schedules (like Imperial), use "citywide"
                        zone = "citywide"

                    # Get schedule for this zone
                    if zone in zone_schedule_map:
                        schedule_info = zone_schedule_map[zone]

                        # Update Address record with official schedule
                        addr.official_trash_day = schedule_info["trash_day_of_week"]
                        addr.official_recycling_day = schedule_info["recycling_day_of_week"]
                        addr.official_green_day = schedule_info["green_day_of_week"]

                        stats["addresses_updated"] += 1

                logger.info(f"✓ Updated {stats['addresses_updated']} addresses with official schedules")

            self.db.commit()
            logger.info(f"✓ Stored {stats['schedules']} schedules and {stats['exceptions']} exceptions")

            # Invalidate caches after successful schedule import
            try:
                from app.redis_cache import redis_cache
                redis_cache.invalidate_lookup_cache()
                redis_cache.invalidate_stats_cache()
                logger.info("✓ Invalidated lookup and stats caches after schedule import")
            except ImportError:
                logger.debug("Redis cache not available for invalidation")

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to store results: {e}")
            import traceback
            traceback.print_exc()
            stats["errors"] += 1

        return stats

    def run_all(self) -> Dict[str, Any]:
        """
        Run all available parsers.

        Returns:
            Dict with results for each city
        """
        results = {}

        for city in self.parsers.keys():
            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing: {city}")
                logger.info(f"{'='*60}")

                parse_result = self.run_parser(city)
                stats = self.store_results(city, parse_result)

                results[city] = {
                    "success": len(parse_result.errors) == 0,
                    "schedules": len(parse_result.schedules),
                    "exceptions": len(parse_result.exceptions),
                    "errors": parse_result.errors,
                    "warnings": parse_result.warnings,
                    "stats": stats
                }

                # Log summary
                if parse_result.errors:
                    logger.error(f"Errors: {len(parse_result.errors)}")
                    for error in parse_result.errors:
                        logger.error(f"  - {error}")

                if parse_result.warnings:
                    logger.warning(f"Warnings: {len(parse_result.warnings)}")
                    for warning in parse_result.warnings:
                        logger.warning(f"  - {warning}")

            except Exception as e:
                logger.error(f"Failed to process {city}: {e}")
                results[city] = {
                    "success": False,
                    "error": str(e)
                }

        return results

    def print_summary(self, results: Dict[str, Any]):
        """
        Print summary of all parser results.

        Args:
            results: Results dict from run_all()
        """
        print("\n" + "="*60)
        print("SCHEDULE EXTRACTION SUMMARY")
        print("="*60)

        total_schedules = 0
        total_exceptions = 0
        total_errors = 0
        successful_cities = 0

        for city, result in results.items():
            print(f"\n{city}:")
            if result.get("success"):
                print(f"  ✓ Success")
                print(f"  - Schedules: {result.get('schedules', 0)}")
                print(f"  - Exceptions: {result.get('exceptions', 0)}")
                if result.get('stats'):
                    print(f"  - Pickup Zones: {result['stats'].get('pickup_zones', 0)}")
                    print(f"  - Addresses Updated: {result['stats'].get('addresses_updated', 0)}")
                total_schedules += result.get('schedules', 0)
                total_exceptions += result.get('exceptions', 0)
                successful_cities += 1
            else:
                print(f"  ✗ Failed")
                print(f"  - Error: {result.get('error', 'Unknown')}")
                total_errors += 1

            if result.get('warnings'):
                print(f"  - Warnings: {len(result.get('warnings', []))}")

        print("\n" + "-"*60)
        print(f"Total Cities Processed: {len(results)}")
        print(f"Successful: {successful_cities}")
        print(f"Failed: {total_errors}")
        print(f"Total Schedules Extracted: {total_schedules}")
        print(f"Total Exceptions Extracted: {total_exceptions}")
        print("="*60 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run trash schedule parsers and store results"
    )
    parser.add_argument(
        "--city",
        type=str,
        help="Run parser for specific city (e.g., 'El Centro')"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all available parsers"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't write to database (testing only)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validate arguments
    if not args.all and not args.city:
        parser.error("Must specify --all or --city")

    # Create database session
    db = SessionLocal()

    try:
        # Create runner
        runner = ScheduleRunner(db, dry_run=args.dry_run)

        # Run parsers
        if args.all:
            results = runner.run_all()
            runner.print_summary(results)
        elif args.city:
            result = runner.run_parser(args.city)
            stats = runner.store_results(args.city, result)

            print(f"\n{args.city} Results:")
            print(f"  Schedules: {len(result.schedules)}")
            print(f"  Exceptions: {len(result.exceptions)}")
            print(f"  Errors: {len(result.errors)}")
            print(f"  Warnings: {len(result.warnings)}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
