"""Initialize database with sample data."""
from app.database import SessionLocal, engine, Base
from app.models import Address

# Create all tables
Base.metadata.create_all(bind=engine)

# Add some sample addresses with official data
def init_sample_data():
    """Add sample addresses to the database."""
    db = SessionLocal()

    # Check if data already exists
    if db.query(Address).count() > 0:
        print("Database already has data. Skipping initialization.")
        db.close()
        return

    sample_addresses = [
        {
            "normalized_address": "1122 PALMVIEW AVE, EL CENTRO, CA",
            "house_number": "1122",
            "street": "PALMVIEW AVE",
            "city": "EL CENTRO",
            "state": "CA",
            "lat": 32.7920,
            "lon": -115.5630,
            "official_trash_day": "MON",
            "official_recycling_day": "WED",
            "official_green_day": None
        },
        {
            "normalized_address": "456 MAIN ST, SAN DIEGO, CA",
            "house_number": "456",
            "street": "MAIN ST",
            "city": "SAN DIEGO",
            "state": "CA",
            "lat": 32.7157,
            "lon": -117.1611,
            "official_trash_day": "TUE",
            "official_recycling_day": "TUE",
            "official_green_day": "FRI"
        },
        {
            "normalized_address": "789 OAK AVE, CALEXICO, CA",
            "house_number": "789",
            "street": "OAK AVE",
            "city": "CALEXICO",
            "state": "CA",
            "lat": 32.6789,
            "lon": -115.4989,
            "official_trash_day": None,  # No official data
            "official_recycling_day": None,
            "official_green_day": None
        }
    ]

    for addr_data in sample_addresses:
        address = Address(**addr_data)
        db.add(address)

    db.commit()
    print(f"Added {len(sample_addresses)} sample addresses to the database.")
    db.close()


if __name__ == "__main__":
    print("Initializing database...")
    init_sample_data()
    print("Database initialization complete!")
