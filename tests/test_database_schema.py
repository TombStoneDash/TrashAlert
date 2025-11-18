"""
Tests for database schema and basic database operations.

Tests ensure that the database schema is correctly defined
and basic CRUD operations work as expected.
"""

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
import tempfile
import os

from src.models import Base, Address, create_database


@pytest.fixture(scope="function")
def temp_db():
    """
    Create a temporary database for testing.

    Yields:
        Tuple of (engine, SessionLocal)
    """
    # Create temporary database file
    db_fd, db_path = tempfile.mkstemp(suffix='.db')

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False}
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session factory
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    yield engine, SessionLocal

    # Cleanup
    engine.dispose()
    os.close(db_fd)
    os.unlink(db_path)


class TestDatabaseSchema:
    """Test database schema definition."""

    def test_addresses_table_exists(self, temp_db):
        """Test that addresses table is created."""
        engine, _ = temp_db
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        assert 'addresses' in tables

    def test_addresses_table_columns(self, temp_db):
        """Test that addresses table has all required columns."""
        engine, _ = temp_db
        inspector = inspect(engine)
        columns = {col['name'] for col in inspector.get_columns('addresses')}

        required_columns = {
            'id', 'house_number', 'street', 'city',
            'subdivision_id', 'lat', 'lon',
            'normalized_address', 'trash_day_of_week', 'osm_id'
        }

        assert required_columns.issubset(columns)

    def test_addresses_primary_key(self, temp_db):
        """Test that addresses table has a primary key on id."""
        engine, _ = temp_db
        inspector = inspect(engine)
        pk = inspector.get_pk_constraint('addresses')

        assert 'id' in pk['constrained_columns']

    def test_addresses_indexes(self, temp_db):
        """Test that appropriate indexes exist."""
        engine, _ = temp_db
        inspector = inspect(engine)
        indexes = inspector.get_indexes('addresses')

        # Check that we have at least one index
        assert len(indexes) > 0

        # Check for normalized_address index
        index_columns = [idx['column_names'] for idx in indexes]
        assert any('normalized_address' in cols for cols in index_columns)


class TestAddressModel:
    """Test the Address model."""

    def test_create_address(self, temp_db):
        """Test creating a new address."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        address = Address(
            house_number="123",
            street="MAIN ST",
            city="SAN DIEGO",
            subdivision_id="downtown",
            lat=32.7157,
            lon=-117.1611,
            normalized_address="123 MAIN ST",
            trash_day_of_week="Monday",
            osm_id="way/123456"
        )

        db.add(address)
        db.commit()
        db.refresh(address)

        assert address.id is not None
        assert address.normalized_address == "123 MAIN ST"

        db.close()

    def test_address_repr(self, temp_db):
        """Test the string representation of Address."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        address = Address(
            house_number="456",
            street="ELM AVE",
            city="SAN DIEGO",
            subdivision_id="la_jolla",
            lat=32.8328,
            lon=-117.2713,
            normalized_address="456 ELM AVE",
            trash_day_of_week="Tuesday"
        )

        db.add(address)
        db.commit()
        db.refresh(address)

        repr_str = repr(address)
        assert "456 ELM AVE" in repr_str
        assert "Tuesday" in repr_str

        db.close()

    def test_nullable_fields(self, temp_db):
        """Test that nullable fields can be None."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        # subdivision_id, trash_day_of_week, and osm_id should be nullable
        address = Address(
            house_number="789",
            street="OAK BLVD",
            city="EL CENTRO",
            subdivision_id=None,
            lat=32.7920,
            lon=-115.5630,
            normalized_address="789 OAK BLVD",
            trash_day_of_week=None,
            osm_id=None
        )

        db.add(address)
        db.commit()
        db.refresh(address)

        assert address.subdivision_id is None
        assert address.trash_day_of_week is None
        assert address.osm_id is None

        db.close()

    def test_required_fields_cannot_be_null(self, temp_db):
        """Test that required fields raise error when None."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        # Missing required field: house_number
        address = Address(
            house_number=None,  # This should fail
            street="MAIN ST",
            city="SAN DIEGO",
            lat=32.7157,
            lon=-117.1611,
            normalized_address="MAIN ST"
        )

        db.add(address)

        # Should raise an exception when committing
        with pytest.raises(Exception):
            db.commit()

        db.rollback()
        db.close()


class TestDatabaseQueries:
    """Test basic database query operations."""

    def test_insert_and_query(self, temp_db):
        """Test inserting and querying addresses."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        # Insert multiple addresses
        addresses = [
            Address(
                house_number="100",
                street="PARK AVE",
                city="SAN DIEGO",
                lat=32.7157,
                lon=-117.1611,
                normalized_address="100 PARK AVE",
                trash_day_of_week="Monday"
            ),
            Address(
                house_number="200",
                street="PARK AVE",
                city="SAN DIEGO",
                lat=32.7158,
                lon=-117.1612,
                normalized_address="200 PARK AVE",
                trash_day_of_week="Tuesday"
            ),
        ]

        for addr in addresses:
            db.add(addr)

        db.commit()

        # Query all addresses
        all_addresses = db.query(Address).all()
        assert len(all_addresses) == 2

        # Query by normalized_address
        addr = db.query(Address).filter(
            Address.normalized_address == "100 PARK AVE"
        ).first()
        assert addr is not None
        assert addr.trash_day_of_week == "Monday"

        db.close()

    def test_filter_by_city(self, temp_db):
        """Test filtering addresses by city."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        # Insert addresses in different cities
        addresses = [
            Address(
                house_number="100",
                street="MAIN ST",
                city="SAN DIEGO",
                lat=32.7157,
                lon=-117.1611,
                normalized_address="100 MAIN ST",
                trash_day_of_week="Monday"
            ),
            Address(
                house_number="200",
                street="ELM ST",
                city="EL CENTRO",
                lat=32.7920,
                lon=-115.5630,
                normalized_address="200 ELM ST",
                trash_day_of_week="Tuesday"
            ),
        ]

        for addr in addresses:
            db.add(addr)

        db.commit()

        # Filter by city
        sd_addresses = db.query(Address).filter(Address.city == "SAN DIEGO").all()
        assert len(sd_addresses) == 1
        assert sd_addresses[0].house_number == "100"

        ec_addresses = db.query(Address).filter(Address.city == "EL CENTRO").all()
        assert len(ec_addresses) == 1
        assert ec_addresses[0].house_number == "200"

        db.close()

    def test_update_address(self, temp_db):
        """Test updating an address."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        # Insert address
        address = Address(
            house_number="300",
            street="OAK ST",
            city="SAN DIEGO",
            lat=32.7157,
            lon=-117.1611,
            normalized_address="300 OAK ST",
            trash_day_of_week="Monday"
        )

        db.add(address)
        db.commit()
        db.refresh(address)

        # Update trash day
        address.trash_day_of_week = "Wednesday"
        db.commit()

        # Verify update
        updated = db.query(Address).filter(Address.id == address.id).first()
        assert updated.trash_day_of_week == "Wednesday"

        db.close()

    def test_delete_address(self, temp_db):
        """Test deleting an address."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        # Insert address
        address = Address(
            house_number="400",
            street="PINE ST",
            city="SAN DIEGO",
            lat=32.7157,
            lon=-117.1611,
            normalized_address="400 PINE ST",
            trash_day_of_week="Friday"
        )

        db.add(address)
        db.commit()
        db.refresh(address)

        address_id = address.id

        # Delete address
        db.delete(address)
        db.commit()

        # Verify deletion
        deleted = db.query(Address).filter(Address.id == address_id).first()
        assert deleted is None

        db.close()

    def test_count_addresses(self, temp_db):
        """Test counting addresses."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        # Insert multiple addresses
        for i in range(5):
            address = Address(
                house_number=str(100 + i),
                street="TEST ST",
                city="SAN DIEGO",
                lat=32.7157 + i * 0.001,
                lon=-117.1611,
                normalized_address=f"{100 + i} TEST ST",
                trash_day_of_week="Monday"
            )
            db.add(address)

        db.commit()

        # Count addresses
        count = db.query(Address).count()
        assert count == 5

        db.close()


class TestDatabaseFactory:
    """Test database factory function."""

    def test_create_database_default(self):
        """Test creating database with default URL."""
        # Create temporary database
        db_fd, db_path = tempfile.mkstemp(suffix='.db')

        try:
            engine, SessionLocal = create_database(f"sqlite:///{db_path}")

            assert engine is not None
            assert SessionLocal is not None

            # Verify tables were created
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            assert 'addresses' in tables

            engine.dispose()
        finally:
            os.close(db_fd)
            os.unlink(db_path)

    def test_session_factory(self):
        """Test that session factory creates working sessions."""
        db_fd, db_path = tempfile.mkstemp(suffix='.db')

        try:
            engine, SessionLocal = create_database(f"sqlite:///{db_path}")

            # Create a session
            db = SessionLocal()

            # Verify we can query (even if empty)
            count = db.query(Address).count()
            assert count == 0

            db.close()
            engine.dispose()
        finally:
            os.close(db_fd)
            os.unlink(db_path)


class TestCoordinateStorage:
    """Test storage and retrieval of geographic coordinates."""

    def test_coordinate_precision(self, temp_db):
        """Test that coordinates are stored with sufficient precision."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        # Use precise coordinates
        precise_lat = 32.71574567
        precise_lon = -117.16113456

        address = Address(
            house_number="123",
            street="PRECISION ST",
            city="SAN DIEGO",
            lat=precise_lat,
            lon=precise_lon,
            normalized_address="123 PRECISION ST",
            trash_day_of_week="Monday"
        )

        db.add(address)
        db.commit()
        db.refresh(address)

        # Verify precision is maintained (within reasonable floating point error)
        assert abs(address.lat - precise_lat) < 1e-6
        assert abs(address.lon - precise_lon) < 1e-6

        db.close()

    def test_negative_coordinates(self, temp_db):
        """Test that negative coordinates are stored correctly."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        address = Address(
            house_number="456",
            street="NEGATIVE ST",
            city="TEST CITY",
            lat=-33.8688,  # Sydney, Australia
            lon=151.2093,
            normalized_address="456 NEGATIVE ST",
            trash_day_of_week="Tuesday"
        )

        db.add(address)
        db.commit()
        db.refresh(address)

        assert address.lat < 0
        assert address.lon > 0

        db.close()
