#!/usr/bin/env python3
"""
Add sample addresses for testing schedule lookup.
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models import Address, City

# Sample addresses for each city
SAMPLE_ADDRESSES = {
    "El Centro": [
        {"street": "Main St", "house_number": "100", "zip_code": "92243"},
        {"street": "Imperial Ave", "house_number": "250", "zip_code": "92243"},
        {"street": "Broadway", "house_number": "500", "zip_code": "92243"},
        {"street": "State St", "house_number": "750", "zip_code": "92243"},
    ],
    "Imperial": [
        {"street": "Main St", "house_number": "100", "zip_code": "92251"},
        {"street": "Barioni Blvd", "house_number": "250", "zip_code": "92251"},
        {"street": "Imperial Ave", "house_number": "500", "zip_code": "92251"},
    ],
    "San Diego": [
        {"street": "Broadway", "house_number": "100", "zip_code": "92101"},  # Downtown
        {"street": "Torrey Pines Rd", "house_number": "250", "zip_code": "92037"},  # La Jolla
        {"street": "Garnet Ave", "house_number": "500", "zip_code": "92109"},  # Pacific Beach
        {"street": "University Ave", "house_number": "750", "zip_code": "92104"},  # North Park
    ],
    "Brawley": [
        {"street": "Main St", "house_number": "100", "zip_code": "92227"},
        {"street": "A St", "house_number": "250", "zip_code": "92227"},
        {"street": "C St", "house_number": "500", "zip_code": "92227"},
    ],
    "Calexico": [
        {"street": "Imperial Ave", "house_number": "100", "zip_code": "92231"},
        {"street": "1st St", "house_number": "250", "zip_code": "92231"},
        {"street": "4th St", "house_number": "500", "zip_code": "92231"},
    ],
    "Holtville": [
        {"street": "Holt Ave", "house_number": "100", "zip_code": "92250"},
        {"street": "5th St", "house_number": "250", "zip_code": "92250"},
        {"street": "Olive Ave", "house_number": "500", "zip_code": "92250"},
    ],
    "Chula Vista": [
        {"street": "Broadway", "house_number": "100", "zip_code": "91910"},
        {"street": "Third Ave", "house_number": "250", "zip_code": "91910"},
        {"street": "Olympic Pkwy", "house_number": "500", "zip_code": "91913"},
    ],
    "Oceanside": [
        {"street": "Pacific St", "house_number": "100", "zip_code": "92054"},
        {"street": "Coast Hwy", "house_number": "250", "zip_code": "92054"},
        {"street": "Mission Ave", "house_number": "500", "zip_code": "92057"},
    ],
}


def main():
    db = SessionLocal()

    try:
        # Get all cities
        cities = {city.name: city for city in db.query(City).all()}

        total_added = 0

        for city_name, addresses in SAMPLE_ADDRESSES.items():
            city = cities.get(city_name)
            if not city:
                print(f"Warning: City '{city_name}' not found in database")
                continue

            for addr_data in addresses:
                normalized = f"{addr_data['house_number']} {addr_data['street']}, {city_name}, CA {addr_data['zip_code']}"

                # Check if address already exists
                existing = db.query(Address).filter(
                    Address.normalized_address == normalized
                ).first()

                if existing:
                    print(f"Skipping existing address: {normalized}")
                    continue

                address = Address(
                    normalized_address=normalized,
                    house_number=addr_data['house_number'],
                    street=addr_data['street'],
                    city_slug=city.slug,
                    city_name=city_name,
                    state="CA",
                    zip_code=addr_data['zip_code']
                )
                # Set the city_id foreign key
                address.city_id = city.id
                db.add(address)
                total_added += 1
                print(f"Added: {normalized}")

        db.commit()
        print(f"\n✓ Successfully added {total_added} sample addresses")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    exit(main())
