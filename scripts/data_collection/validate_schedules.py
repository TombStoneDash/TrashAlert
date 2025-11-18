#!/usr/bin/env python3
"""
Validation script for schedule extraction.

Demonstrates:
1. Schedule lookup by city/zone
2. Next pickup date calculation
3. Exception handling (holidays)
4. Data quality validation

Usage:
    python scripts/data_collection/validate_schedules.py
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import SessionLocal
from app.models import Schedule, ScheduleException, SourceMetadata
from scripts.data_collection.schedule_parsers.el_centro_parser import ElCentroParser
from scripts.data_collection.schedule_parsers.imperial_parser import ImperialParser
from scripts.data_collection.schedule_parsers.san_diego_parser import SanDiegoParser


def validate_next_pickup_dates():
    """Validate next pickup date calculation."""
    print("\n" + "="*60)
    print("NEXT PICKUP DATE VALIDATION")
    print("="*60)

    test_dates = [
        (datetime(2025, 11, 17), "MON", datetime(2025, 11, 24)),  # Sunday -> next Monday
        (datetime(2025, 11, 18), "TUE", datetime(2025, 11, 25)),  # Monday -> next Tuesday
        (datetime(2025, 11, 19), "FRI", datetime(2025, 11, 21)),  # Tuesday -> next Friday
    ]

    parser = ElCentroParser()

    for ref_date, day, expected in test_dates:
        calculated = parser.calculate_next_pickup(day, ref_date)
        status = "✓" if calculated.date() == expected.date() else "✗"
        print(f"{status} From {ref_date.strftime('%Y-%m-%d (%a)')}, next {day}: "
              f"{calculated.strftime('%Y-%m-%d (%a)')} (expected: {expected.strftime('%Y-%m-%d (%a)')})")


def demonstrate_address_lookup():
    """Demonstrate address-to-schedule lookup."""
    print("\n" + "="*60)
    print("ADDRESS LOOKUP DEMONSTRATION")
    print("="*60)

    # Test addresses
    test_addresses = [
        ("123 Main St, El Centro, CA", ElCentroParser),
        ("456 Oak Ave, Imperial, CA", ImperialParser),
        ("789 Broadway, San Diego, CA", SanDiegoParser),
    ]

    for address, parser_class in test_addresses:
        parser = parser_class()
        schedules = parser.get_schedule_for_address(address)

        print(f"\n{address}:")
        for schedule in schedules:
            print(f"  - {schedule.collection_type.title()}: "
                  f"{schedule.day_of_week} (next pickup: {schedule.next_pickup_date.strftime('%Y-%m-%d')})")


def validate_database_consistency():
    """Validate database data consistency."""
    print("\n" + "="*60)
    print("DATABASE CONSISTENCY VALIDATION")
    print("="*60)

    db = SessionLocal()

    try:
        # Check for required fields
        invalid_schedules = db.query(Schedule).filter(
            (Schedule.day_of_week == None) | (Schedule.collection_type == None)
        ).count()

        print(f"\nSchedules with missing required fields: {invalid_schedules}")

        # Check day_of_week values
        valid_days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
        invalid_days = db.query(Schedule).filter(
            ~Schedule.day_of_week.in_(valid_days)
        ).count()

        print(f"Schedules with invalid day_of_week: {invalid_days}")

        # Check collection_type values
        valid_types = ['trash', 'recycling', 'green_waste', 'bulk']
        invalid_types = db.query(Schedule).filter(
            ~Schedule.collection_type.in_(valid_types)
        ).count()

        print(f"Schedules with invalid collection_type: {invalid_types}")

        # Check confidence values
        invalid_confidence = db.query(Schedule).filter(
            (Schedule.confidence < 0) | (Schedule.confidence > 1)
        ).count()

        print(f"Schedules with invalid confidence: {invalid_confidence}")

        # Summary by city
        print("\n=== Schedules by City ===")
        sources = db.query(SourceMetadata).all()
        for source in sources:
            count = db.query(Schedule).filter(Schedule.source_id == source.id).count()
            print(f"{source.city}: {count} schedules")

        # Exception validation
        print("\n=== Exception Validation ===")
        total_exceptions = db.query(ScheduleException).count()
        cancelled = db.query(ScheduleException).filter(
            ScheduleException.is_cancelled == True
        ).count()
        rescheduled = db.query(ScheduleException).filter(
            ScheduleException.rescheduled_date != None
        ).count()

        print(f"Total exceptions: {total_exceptions}")
        print(f"Cancelled pickups: {cancelled}")
        print(f"Rescheduled pickups: {rescheduled}")

        # Overall validation status
        print("\n" + "-"*60)
        if invalid_schedules == 0 and invalid_days == 0 and invalid_types == 0 and invalid_confidence == 0:
            print("✓ ALL VALIDATION CHECKS PASSED")
        else:
            print("✗ VALIDATION FAILED - See errors above")

    finally:
        db.close()


def demonstrate_real_world_example():
    """Show a real-world example of schedule lookup."""
    print("\n" + "="*60)
    print("REAL-WORLD EXAMPLE: Trash Day Lookup")
    print("="*60)

    # Simulate user query: "When is my next trash pickup?"
    user_address = "1234 State St, El Centro, CA"
    today = datetime.now()

    parser = ElCentroParser()
    zone = parser.match_address_to_zone(user_address)
    schedules = parser.get_schedule_for_address(user_address)

    print(f"\nAddress: {user_address}")
    print(f"Zone: {zone}")
    print(f"Today: {today.strftime('%A, %B %d, %Y')}")
    print("\nPickup Schedule:")

    for schedule in schedules:
        next_pickup = schedule.next_pickup_date
        days_until = (next_pickup - today).days

        print(f"\n  {schedule.collection_type.upper().replace('_', ' ')}:")
        print(f"    Regular day: {schedule.day_of_week}")
        print(f"    Next pickup: {next_pickup.strftime('%A, %B %d, %Y')}")
        print(f"    Days until pickup: {days_until}")


def main():
    """Run all validation and demonstration functions."""
    print("\n" + "="*60)
    print("TRASH SCHEDULE EXTRACTION - VALIDATION & DEMO")
    print("="*60)

    # Run validations
    validate_next_pickup_dates()
    validate_database_consistency()

    # Run demonstrations
    demonstrate_address_lookup()
    demonstrate_real_world_example()

    print("\n" + "="*60)
    print("VALIDATION COMPLETE")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
