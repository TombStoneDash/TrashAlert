#!/usr/bin/env python3
"""
Schedules importer - standardizes schedule data import across all sources.

This module provides a unified interface for importing trash collection schedules
from various sources (scrapers, APIs, manual uploads) into the database.

Key features:
- Duplicate detection and prevention
- Data validation and normalization
- Batch import with transaction support
- Rollback on errors
- Import statistics and logging

Usage:
    from schedules_importer import SchedulesImporter

    importer = SchedulesImporter(db_session)
    result = importer.import_from_parser(city_name, parser_result)
    print(f"Imported {result['schedules_created']} schedules")
"""
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models import (
    Schedule, ScheduleException, SourceMetadata,
    City, PickupZone, Address
)
from scripts.data_collection.schedule_parsers.base_parser import (
    ParseResult, ScheduleData, ExceptionData
)

logger = logging.getLogger(__name__)


class SchedulesImporter:
    """
    Unified importer for trash collection schedules.

    Handles importing schedules from various sources while preventing
    duplicates and ensuring data consistency.
    """

    def __init__(self, db: Session, allow_duplicates: bool = False):
        """
        Initialize importer.

        Args:
            db: Database session
            allow_duplicates: If True, allow duplicate schedules (default: False)
        """
        self.db = db
        self.allow_duplicates = allow_duplicates

    def import_from_parser(
        self,
        city_name: str,
        parse_result: ParseResult,
        source_url: str = ""
    ) -> Dict[str, Any]:
        """
        Import schedules from a parser result.

        Args:
            city_name: Name of the city
            parse_result: ParseResult from a schedule parser
            source_url: URL of the data source

        Returns:
            Dict with import statistics:
            {
                'source_metadata_id': int,
                'schedules_created': int,
                'schedules_updated': int,
                'schedules_skipped': int,
                'exceptions_created': int,
                'errors': List[str],
                'warnings': List[str]
            }
        """
        stats = {
            'source_metadata_id': None,
            'schedules_created': 0,
            'schedules_updated': 0,
            'schedules_skipped': 0,
            'exceptions_created': 0,
            'errors': list(parse_result.errors),
            'warnings': list(parse_result.warnings)
        }

        try:
            # Get or create city
            city = self._get_or_create_city(city_name)

            # Create source metadata record
            source = self._create_source_metadata(
                city=city_name,
                parse_result=parse_result,
                source_url=source_url
            )
            stats['source_metadata_id'] = source.id

            # Import schedules
            for schedule_data in parse_result.schedules:
                try:
                    result = self._import_schedule(
                        city=city,
                        source=source,
                        schedule_data=schedule_data
                    )
                    if result == 'created':
                        stats['schedules_created'] += 1
                    elif result == 'updated':
                        stats['schedules_updated'] += 1
                    elif result == 'skipped':
                        stats['schedules_skipped'] += 1
                except Exception as e:
                    error_msg = f"Failed to import schedule {schedule_data.address}: {e}"
                    stats['errors'].append(error_msg)
                    logger.error(error_msg)

            # Import exceptions
            for exception_data in parse_result.exceptions:
                try:
                    self._import_exception(
                        source=source,
                        exception_data=exception_data
                    )
                    stats['exceptions_created'] += 1
                except Exception as e:
                    error_msg = f"Failed to import exception {exception_data.reason}: {e}"
                    stats['errors'].append(error_msg)
                    logger.error(error_msg)

            # Commit transaction
            self.db.commit()
            logger.info(f"Successfully imported schedules for {city_name}: "
                       f"{stats['schedules_created']} created, "
                       f"{stats['schedules_updated']} updated, "
                       f"{stats['schedules_skipped']} skipped")

        except Exception as e:
            self.db.rollback()
            error_msg = f"Failed to import schedules for {city_name}: {e}"
            stats['errors'].append(error_msg)
            logger.error(error_msg)
            raise

        return stats

    def _get_or_create_city(self, city_name: str) -> City:
        """Get existing city or create new one."""
        city = self.db.query(City).filter(City.name == city_name).first()
        if not city:
            # Create slug from city name
            slug = city_name.lower().replace(" ", "_")
            city = City(
                name=city_name,
                slug=slug,
                state="CA"
            )
            self.db.add(city)
            self.db.flush()
            logger.info(f"Created new city: {city_name}")
        return city

    def _create_source_metadata(
        self,
        city: str,
        parse_result: ParseResult,
        source_url: str
    ) -> SourceMetadata:
        """Create source metadata record."""
        source = SourceMetadata(
            city=city,
            source_type=parse_result.metadata.get("source_format", "scraper"),
            source_url=source_url or parse_result.metadata.get("source_url", ""),
            source_name=f"{city} Schedule {datetime.now().year}",
            parser_version=parse_result.metadata.get("parser_version", "1.0.0"),
            parser_name=parse_result.metadata.get("parser_name", f"{city}Parser"),
            total_records_extracted=len(parse_result.schedules),
            successful_records=len(parse_result.schedules) - len(parse_result.errors),
            failed_records=len(parse_result.errors),
            extra_data=parse_result.metadata,
            last_fetched_at=datetime.now(),
            last_parsed_at=datetime.now()
        )
        self.db.add(source)
        self.db.flush()
        return source

    def _import_schedule(
        self,
        city: City,
        source: SourceMetadata,
        schedule_data: ScheduleData
    ) -> str:
        """
        Import a single schedule.

        Returns:
            'created', 'updated', or 'skipped'
        """
        # Get or create pickup zone if specified
        pickup_zone = None
        if schedule_data.zone:
            pickup_zone = self._get_or_create_zone(city, schedule_data.zone)

        # Check for existing schedule (duplicate detection)
        if not self.allow_duplicates:
            existing = self._find_existing_schedule(
                city=city,
                zone=pickup_zone,
                collection_type=schedule_data.collection_type,
                day_of_week=schedule_data.day_of_week
            )

            if existing:
                # Update if data has changed
                if self._should_update_schedule(existing, schedule_data):
                    self._update_schedule(existing, schedule_data, source)
                    return 'updated'
                else:
                    return 'skipped'

        # Create new schedule
        schedule = Schedule(
            city_id=city.id,
            pickup_zone_id=pickup_zone.id if pickup_zone else None,
            trash_day_of_week=schedule_data.day_of_week if schedule_data.collection_type == "trash" else None,
            recycling_day_of_week=schedule_data.day_of_week if schedule_data.collection_type == "recycling" else None,
            green_day_of_week=schedule_data.day_of_week if schedule_data.collection_type == "green_waste" else None,
            source="OFFICIAL",
            extra_metadata={
                "collection_type": schedule_data.collection_type,
                "recurrence": schedule_data.recurrence,
                "confidence": schedule_data.confidence,
                "effective_date": schedule_data.effective_date.isoformat() if schedule_data.effective_date else None,
                "next_pickup_date": schedule_data.next_pickup_date.isoformat() if schedule_data.next_pickup_date else None,
                "source_id": source.id,
                "imported_at": datetime.now().isoformat()
            }
        )
        self.db.add(schedule)
        self.db.flush()
        return 'created'

    def _import_exception(
        self,
        source: SourceMetadata,
        exception_data: ExceptionData
    ) -> ScheduleException:
        """Import a schedule exception (holiday, etc.)."""
        # Check for existing exception
        existing = self.db.query(ScheduleException).filter(
            and_(
                ScheduleException.exception_date == exception_data.exception_date,
                ScheduleException.reason == exception_data.reason
            )
        ).first()

        if existing:
            logger.debug(f"Exception already exists: {exception_data.reason} on {exception_data.exception_date}")
            return existing

        exception = ScheduleException(
            schedule_id=None,  # Applied to all schedules
            exception_date=exception_data.exception_date,
            rescheduled_date=exception_data.rescheduled_date,
            is_cancelled=exception_data.is_cancelled,
            reason=exception_data.reason,
            notes=exception_data.notes
        )
        self.db.add(exception)
        self.db.flush()
        return exception

    def _get_or_create_zone(self, city: City, zone_name: str) -> PickupZone:
        """Get existing zone or create new one."""
        zone = self.db.query(PickupZone).filter(
            and_(
                PickupZone.city_id == city.id,
                PickupZone.name == zone_name
            )
        ).first()

        if not zone:
            zone = PickupZone(
                city_id=city.id,
                name=zone_name,
                extra_metadata={"created_by": "importer", "zone_type": "administrative"}
            )
            self.db.add(zone)
            self.db.flush()
            logger.info(f"Created new zone: {zone_name} for {city.name}")

        return zone

    def _find_existing_schedule(
        self,
        city: City,
        zone: Optional[PickupZone],
        collection_type: str,
        day_of_week: str
    ) -> Optional[Schedule]:
        """Find existing schedule matching the criteria."""
        query = self.db.query(Schedule).filter(
            Schedule.city_id == city.id
        )

        if zone:
            query = query.filter(Schedule.pickup_zone_id == zone.id)
        else:
            query = query.filter(Schedule.pickup_zone_id.is_(None))

        # Check the appropriate day field based on collection type
        if collection_type == "trash":
            query = query.filter(Schedule.trash_day_of_week == day_of_week)
        elif collection_type == "recycling":
            query = query.filter(Schedule.recycling_day_of_week == day_of_week)
        elif collection_type == "green_waste":
            query = query.filter(Schedule.green_day_of_week == day_of_week)

        return query.first()

    def _should_update_schedule(
        self,
        existing: Schedule,
        new_data: ScheduleData
    ) -> bool:
        """
        Determine if an existing schedule should be updated.

        Returns True if the new data has higher confidence or newer information.
        """
        # Check if new data has higher confidence
        old_confidence = existing.extra_metadata.get("confidence", 0) if existing.extra_metadata else 0
        new_confidence = new_data.confidence

        if new_confidence > old_confidence:
            return True

        # Check if new data is more recent
        old_date = existing.updated_at or existing.created_at
        # Consider updating if old data is more than 30 days old
        age_days = (datetime.now() - old_date).days
        if age_days > 30:
            return True

        return False

    def _update_schedule(
        self,
        schedule: Schedule,
        new_data: ScheduleData,
        source: SourceMetadata
    ):
        """Update an existing schedule with new data."""
        # Update the appropriate day field
        if new_data.collection_type == "trash":
            schedule.trash_day_of_week = new_data.day_of_week
        elif new_data.collection_type == "recycling":
            schedule.recycling_day_of_week = new_data.day_of_week
        elif new_data.collection_type == "green_waste":
            schedule.green_day_of_week = new_data.day_of_week

        # Update metadata
        if not schedule.extra_metadata:
            schedule.extra_metadata = {}

        schedule.extra_metadata.update({
            "collection_type": new_data.collection_type,
            "recurrence": new_data.recurrence,
            "confidence": new_data.confidence,
            "updated_by_source_id": source.id,
            "last_updated": datetime.now().isoformat()
        })

        schedule.updated_at = datetime.now()
        self.db.flush()


def main():
    """CLI interface for schedules importer."""
    import argparse
    from app.database import SessionLocal
    from scripts.data_collection.schedule_runner import ScheduleRunner

    parser = argparse.ArgumentParser(description="Import trash collection schedules")
    parser.add_argument("--city", help="City name to import")
    parser.add_argument("--all", action="store_true", help="Import all cities")
    parser.add_argument("--allow-duplicates", action="store_true",
                       help="Allow duplicate schedules")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    db = SessionLocal()
    try:
        runner = ScheduleRunner(db, dry_run=False)
        importer = SchedulesImporter(db, allow_duplicates=args.allow_duplicates)

        cities = []
        if args.all:
            cities = list(runner.parsers.keys())
        elif args.city:
            cities = [args.city]
        else:
            print("Error: Specify --city or --all")
            return

        for city in cities:
            print(f"\n{'='*60}")
            print(f"Importing schedules for {city}...")
            print(f"{'='*60}")

            # Run parser
            parse_result = runner.run_parser(city)

            # Import results
            stats = importer.import_from_parser(city, parse_result)

            # Print results
            print(f"\nImport Results for {city}:")
            print(f"  Schedules created: {stats['schedules_created']}")
            print(f"  Schedules updated: {stats['schedules_updated']}")
            print(f"  Schedules skipped: {stats['schedules_skipped']}")
            print(f"  Exceptions created: {stats['exceptions_created']}")
            if stats['errors']:
                print(f"  Errors: {len(stats['errors'])}")
                for error in stats['errors']:
                    print(f"    - {error}")
            if stats['warnings']:
                print(f"  Warnings: {len(stats['warnings'])}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
