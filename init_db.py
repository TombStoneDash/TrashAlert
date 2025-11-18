"""Initialize database with migrations and sample data."""
import subprocess
import sys
from app.database import SessionLocal, DATABASE_URL
from app.models import Address


def run_migrations():
    """Run Alembic migrations to create/update database schema."""
    print("Running database migrations...")
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        print("✓ Migrations completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Migration failed: {e.stderr}")
        return False


def init_sample_data():
    """Add sample addresses to the database."""
    db = SessionLocal()

    # Check if data already exists
    if db.query(Address).count() > 0:
        print("Database already has data. Skipping sample data initialization.")
        db.close()
        return

    sample_addresses = [
        {
            "normalized_address": "1122 PALMVIEW AVE, EL CENTRO, CA",
            "house_number": "1122",
            "street": "PALMVIEW AVE",
            "city_name": "EL CENTRO",
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
            "city_name": "SAN DIEGO",
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
            "city_name": "CALEXICO",
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
    print(f"✓ Added {len(sample_addresses)} sample addresses to the database.")
    db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("TrashAlert Database Initialization")
    print("=" * 60)
    print(f"Database URL: {DATABASE_URL}")
    print()

    # Run migrations first
    if not run_migrations():
        print("\n✗ Database initialization failed!")
        sys.exit(1)

    # Then add sample data
    print()
    init_sample_data()

    print()
    print("=" * 60)
    print("✓ Database initialization complete!")
    print("=" * 60)
