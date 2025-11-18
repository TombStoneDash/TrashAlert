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
from app.models import Base, Schedule, ScheduleException, SourceMetadata, Address
from scripts.data_collection.schedule_parsers.el_centro_parser import ElCentroParser
from scripts.data_collection.schedule_parsers.imperial_parser import ImperialParser
from scripts.data_collection.schedule_parsers.san_diego_parser import SanDiegoParser
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
        Store parse results in database.

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
            "errors": len(result.errors)
        }

        if self.dry_run:
            logger.info("[DRY RUN] Would store to database:")
            logger.info(f"  - {len(result.schedules)} schedules")
            logger.info(f"  - {len(result.exceptions)} exceptions")
            return stats

        try:
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

            # Store schedules
            # Note: For pilot, we're not linking to specific addresses yet
            # In production, we'd match schedules to addresses from the addresses table
            for schedule_data in result.schedules:
                schedule = Schedule(
                    address_id=None,  # TODO: Link to actual address
                    day_of_week=schedule_data.day_of_week,
                    collection_type=schedule_data.collection_type,
                    zone=schedule_data.zone,
                    recurrence=schedule_data.recurrence,
                    source_id=source.id,
                    confidence=schedule_data.confidence,
                    effective_date=schedule_data.effective_date
                )
                self.db.add(schedule)
                stats["schedules"] += 1

            # Store exceptions
            # Note: Exceptions are linked to schedules, but for pilot we'll store them separately
            for exception_data in result.exceptions:
                exception = ScheduleException(
                    schedule_id=None,  # TODO: Link to specific schedule
                    exception_date=exception_data.exception_date,
                    rescheduled_date=exception_data.rescheduled_date,
                    is_cancelled=exception_data.is_cancelled,
                    reason=exception_data.reason,
                    notes=exception_data.notes
                )
                self.db.add(exception)
                stats["exceptions"] += 1

            self.db.commit()
            logger.info(f"✓ Stored {stats['schedules']} schedules and {stats['exceptions']} exceptions")

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to store results: {e}")
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
