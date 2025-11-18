#!/usr/bin/env python3
"""
Test the /lookup endpoint with sample addresses from all 8 cities.
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models import Address

# Test addresses
TEST_ADDRESSES = [
    "100 Main St, El Centro, CA 92243",
    "250 Imperial Ave, El Centro, CA 92243",
    "100 Main St, Imperial, CA 92251",
    "100 Broadway, San Diego, CA 92101",
    "100 Main St, Brawley, CA 92227",
    "100 Imperial Ave, Calexico, CA 92231",
    "100 Holt Ave, Holtville, CA 92250",
    "100 Broadway, Chula Vista, CA 91910",
    "100 Pacific St, Oceanside, CA 92054",
]


def main():
    db = SessionLocal()

    try:
        print("="*60)
        print("TESTING SCHEDULE LOOKUP")
        print("="*60)

        for test_address in TEST_ADDRESSES:
            # Query address from database
            addr = db.query(Address).filter(
                Address.normalized_address == test_address
            ).first()

            if not addr:
                print(f"\n✗ Address not found: {test_address}")
                continue

            print(f"\n{test_address}")
            print(f"  City: {addr.city_name}")

            if addr.official_trash_day or addr.official_recycling_day or addr.official_green_day:
                print(f"  ✓ OFFICIAL SCHEDULE:")
                if addr.official_trash_day:
                    print(f"    - Trash: {addr.official_trash_day}")
                if addr.official_recycling_day:
                    print(f"    - Recycling: {addr.official_recycling_day}")
                if addr.official_green_day:
                    print(f"    - Green Waste: {addr.official_green_day}")
            else:
                print(f"  ✗ NO OFFICIAL SCHEDULE")

        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)

        # Count addresses with schedules by city
        all_addresses = db.query(Address).all()

        cities_with_schedules = {}
        for addr in all_addresses:
            city = addr.city_name
            if city not in cities_with_schedules:
                cities_with_schedules[city] = {"total": 0, "with_schedule": 0}

            cities_with_schedules[city]["total"] += 1
            if addr.official_trash_day or addr.official_recycling_day or addr.official_green_day:
                cities_with_schedules[city]["with_schedule"] += 1

        for city, stats in sorted(cities_with_schedules.items()):
            print(f"{city}: {stats['with_schedule']}/{stats['total']} addresses have schedules")

    finally:
        db.close()

    return 0


if __name__ == "__main__":
    exit(main())
