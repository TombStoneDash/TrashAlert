#!/usr/bin/env python3
"""
Script to create test data with various inconsistencies for validation testing.

This script creates sample data with intentional issues to test the
validation pipeline's ability to detect and correct problems.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import SessionLocal
from app.models import City, Address, Schedule, PickupZone, ScheduleException
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_city(db) -> City:
    """Create a test city."""
    city = City(
        name="Test City",
        slug="test-city",
        state="CA",
        timezone="America/Los_Angeles"
    )
    db.add(city)
    db.flush()
    logger.info(f"Created test city: {city.name} (ID: {city.id})")
    return city


def create_test_zones(db, city: City) -> list:
    """Create test pickup zones with issues."""
    zones = []

    # Zone 1: Valid zone
    zone1 = PickupZone(
        city_id=city.id,
        zone_name="Zone A",
        external_zone_id="ZONE_A"
    )
    zones.append(zone1)

    # Zone 2: Missing zone_name (issue)
    zone2 = PickupZone(
        city_id=city.id,
        zone_name=None,  # ISSUE: Missing zone name
        external_zone_id="ZONE_B"
    )
    zones.append(zone2)

    # Zone 3: Duplicate zone_name (issue)
    zone3 = PickupZone(
        city_id=city.id,
        zone_name="Zone A",  # ISSUE: Duplicate name
        external_zone_id="ZONE_C"
    )
    zones.append(zone3)

    # Zone 4: Missing city_id (issue)
    zone4 = PickupZone(
        city_id=None,  # ISSUE: Missing city reference
        zone_name="Orphan Zone",
        external_zone_id="ZONE_ORPHAN"
    )
    zones.append(zone4)

    for zone in zones:
        db.add(zone)

    db.flush()
    logger.info(f"Created {len(zones)} test pickup zones")
    return zones


def create_test_schedules(db, city: City, zones: list) -> list:
    """Create test schedules with issues."""
    schedules = []

    # Schedule 1: Valid schedule
    schedule1 = Schedule(
        city_id=city.id,
        pickup_zone_id=zones[0].id,
        trash_day_of_week=2,  # Wednesday
        recycling_day_of_week=4,  # Friday
        source="test"
    )
    schedules.append(schedule1)

    # Schedule 2: Invalid day of week (issue)
    schedule2 = Schedule(
        city_id=city.id,
        pickup_zone_id=zones[0].id,
        trash_day_of_week=9,  # ISSUE: Invalid day (must be 0-6)
        recycling_day_of_week=1,
        source="test"
    )
    schedules.append(schedule2)

    # Schedule 3: Day as string instead of number (issue)
    schedule3 = Schedule(
        city_id=city.id,
        pickup_zone_id=zones[2].id,
        trash_day_of_week="Monday",  # ISSUE: String instead of int
        recycling_day_of_week=3,
        source="test"
    )
    schedules.append(schedule3)

    # Schedule 4: Trash and recycling on same day (inconsistency)
    schedule4 = Schedule(
        city_id=city.id,
        pickup_zone_id=zones[0].id,
        trash_day_of_week=2,  # ISSUE: Same day as recycling
        recycling_day_of_week=2,  # ISSUE: Same day as trash
        source="test"
    )
    schedules.append(schedule4)

    # Schedule 5: No pickup days defined (issue)
    schedule5 = Schedule(
        city_id=city.id,
        pickup_zone_id=zones[0].id,
        trash_day_of_week=None,  # ISSUE: No days defined
        recycling_day_of_week=None,
        green_day_of_week=None,
        source="test"
    )
    schedules.append(schedule5)

    # Schedule 6: Missing city reference (issue)
    schedule6 = Schedule(
        city_id=None,  # ISSUE: Missing city
        pickup_zone_id=zones[0].id,
        trash_day_of_week=1,
        source="test"
    )
    schedules.append(schedule6)

    for schedule in schedules:
        db.add(schedule)

    db.flush()
    logger.info(f"Created {len(schedules)} test schedules with issues")
    return schedules


def create_test_addresses(db, city: City, zones: list) -> list:
    """Create test addresses with issues."""
    addresses = []

    # Address 1: Valid address
    address1 = Address(
        street_number="123",
        street_name="Main Street",
        city_id=city.id,
        zipcode="90001",
        latitude=34.0522,
        longitude=-118.2437,
        official_trash_day=2,
        official_recycling_day=4
    )
    addresses.append(address1)

    # Address 2: Missing street_number (issue)
    address2 = Address(
        street_number=None,  # ISSUE: Missing street number
        street_name="Oak Avenue",
        city_id=city.id,
        zipcode="90002"
    )
    addresses.append(address2)

    # Address 3: Missing street_name (issue)
    address3 = Address(
        street_number="456",
        street_name=None,  # ISSUE: Missing street name
        city_id=city.id,
        zipcode="90003"
    )
    addresses.append(address3)

    # Address 4: Missing city_id (critical issue)
    address4 = Address(
        street_number="789",
        street_name="Pine Street",
        city_id=None,  # ISSUE: Missing city reference
        zipcode="90004"
    )
    addresses.append(address4)

    # Address 5: Invalid coordinates (issue)
    address5 = Address(
        street_number="321",
        street_name="Elm Street",
        city_id=city.id,
        zipcode="90005",
        latitude=999.0,  # ISSUE: Invalid latitude
        longitude=-118.2437
    )
    addresses.append(address5)

    # Address 6: Incomplete coordinates (issue)
    address6 = Address(
        street_number="654",
        street_name="Maple Drive",
        city_id=city.id,
        zipcode="90006",
        latitude=34.0522,
        longitude=None  # ISSUE: Missing longitude
    )
    addresses.append(address6)

    # Address 7: Invalid longitude (issue)
    address7 = Address(
        street_number="987",
        street_name="Cedar Lane",
        city_id=city.id,
        zipcode="90007",
        latitude=34.0522,
        longitude=-200.0  # ISSUE: Invalid longitude
    )
    addresses.append(address7)

    for address in addresses:
        db.add(address)

    db.flush()
    logger.info(f"Created {len(addresses)} test addresses with issues")
    return addresses


def create_test_exceptions(db, city: City) -> list:
    """Create test schedule exceptions with issues."""
    exceptions = []

    today = datetime.now().date()

    # Exception 1: Valid future exception
    exception1 = ScheduleException(
        city_id=city.id,
        exception_date=today + timedelta(days=7),
        rescheduled_date=today + timedelta(days=8),
        reason="Holiday",
        applies_to_trash=True,
        applies_to_recycling=True
    )
    exceptions.append(exception1)

    # Exception 2: Old exception (cleanup candidate)
    exception2 = ScheduleException(
        city_id=city.id,
        exception_date=today - timedelta(days=60),  # ISSUE: Old date
        rescheduled_date=today - timedelta(days=59),
        reason="Past Holiday"
    )
    exceptions.append(exception2)

    # Exception 3: Rescheduled date before exception date (issue)
    exception3 = ScheduleException(
        city_id=city.id,
        exception_date=today + timedelta(days=14),
        rescheduled_date=today + timedelta(days=10),  # ISSUE: Before exception date
        reason="Invalid Reschedule"
    )
    exceptions.append(exception3)

    # Exception 4: Missing exception_date (critical issue)
    exception4 = ScheduleException(
        city_id=city.id,
        exception_date=None,  # ISSUE: Missing date
        reason="No Date Holiday"
    )
    exceptions.append(exception4)

    # Exception 5: Missing city_id (issue)
    exception5 = ScheduleException(
        city_id=None,  # ISSUE: Missing city reference
        exception_date=today + timedelta(days=21),
        reason="Orphan Exception"
    )
    exceptions.append(exception5)

    for exception in exceptions:
        db.add(exception)

    db.flush()
    logger.info(f"Created {len(exceptions)} test schedule exceptions with issues")
    return exceptions


def main():
    """Create test data with various issues."""
    logger.info("Creating test data with intentional issues...")

    db = SessionLocal()

    try:
        # Check if test city already exists
        existing_city = db.query(City).filter(City.slug == "test-city").first()
        if existing_city:
            logger.warning("Test city already exists. Deleting old test data...")
            # Delete old test data
            db.query(ScheduleException).filter(
                ScheduleException.city_id == existing_city.id
            ).delete()
            db.query(Schedule).filter(Schedule.city_id == existing_city.id).delete()
            db.query(Address).filter(Address.city_id == existing_city.id).delete()
            db.query(PickupZone).filter(PickupZone.city_id == existing_city.id).delete()
            db.query(City).filter(City.id == existing_city.id).delete()
            db.commit()

        # Create test city
        city = create_test_city(db)

        # Create test data with issues
        zones = create_test_zones(db, city)
        schedules = create_test_schedules(db, city, zones)
        addresses = create_test_addresses(db, city, zones)
        exceptions = create_test_exceptions(db, city)

        # Commit all changes
        db.commit()

        logger.info("\n" + "=" * 80)
        logger.info("TEST DATA CREATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Created:")
        logger.info(f"  - 1 test city")
        logger.info(f"  - {len(zones)} pickup zones (with issues)")
        logger.info(f"  - {len(schedules)} schedules (with issues)")
        logger.info(f"  - {len(addresses)} addresses (with issues)")
        logger.info(f"  - {len(exceptions)} schedule exceptions (with issues)")
        logger.info("\nYou can now run the validation pipeline to detect and fix these issues:")
        logger.info(f"  python scripts/validation/run_pipeline.py --city-id {city.id}")

    except Exception as e:
        logger.error(f"Failed to create test data: {str(e)}", exc_info=True)
        db.rollback()
        sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    main()
