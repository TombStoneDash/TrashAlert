"""
Tests for the expanded database schema (cities, pickup_zones, schedules, address_pickup_info).

Tests ensure that the new tables work correctly and relationships are properly defined.
"""

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
import tempfile
import os

from app.database import Base
from app.models import City, PickupZone, Schedule, AddressPickupInfo, Address


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


class TestNewTableStructure:
    """Test that new tables are created correctly."""

    def test_cities_table_exists(self, temp_db):
        """Test that cities table is created."""
        engine, _ = temp_db
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        assert 'cities' in tables

    def test_pickup_zones_table_exists(self, temp_db):
        """Test that pickup_zones table is created."""
        engine, _ = temp_db
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        assert 'pickup_zones' in tables

    def test_schedules_table_exists(self, temp_db):
        """Test that schedules table is created."""
        engine, _ = temp_db
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        assert 'schedules' in tables

    def test_address_pickup_info_table_exists(self, temp_db):
        """Test that address_pickup_info table is created."""
        engine, _ = temp_db
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        assert 'address_pickup_info' in tables


class TestCityModel:
    """Test the City model."""

    def test_create_city(self, temp_db):
        """Test creating a new city."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        city = City(
            slug="san-diego",
            name="San Diego",
            state="California",
            county="San Diego County",
            timezone="America/Los_Angeles",
            enabled=True,
            extra_metadata={"population": 1400000}
        )

        db.add(city)
        db.commit()
        db.refresh(city)

        assert city.id is not None
        assert city.slug == "san-diego"
        assert city.name == "San Diego"
        assert city.enabled is True

        db.close()

    def test_city_slug_unique(self, temp_db):
        """Test that city slugs must be unique."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        # Create first city
        city1 = City(slug="san-diego", name="San Diego", state="California")
        db.add(city1)
        db.commit()

        # Try to create second city with same slug
        city2 = City(slug="san-diego", name="San Diego 2", state="California")
        db.add(city2)

        with pytest.raises(Exception):  # SQLite will raise IntegrityError
            db.commit()

        db.close()


class TestPickupZoneModel:
    """Test the PickupZone model."""

    def test_create_pickup_zone(self, temp_db):
        """Test creating a new pickup zone."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        # Create city first
        city = City(slug="san-diego", name="San Diego", state="California")
        db.add(city)
        db.commit()
        db.refresh(city)

        # Create pickup zone
        zone = PickupZone(
            city_id=city.id,
            name="Zone A",
            external_ref="SD-ZONE-A",
            extra_metadata={"color": "blue"}
        )

        db.add(zone)
        db.commit()
        db.refresh(zone)

        assert zone.id is not None
        assert zone.city_id == city.id
        assert zone.name == "Zone A"

        db.close()

    def test_pickup_zone_city_relationship(self, temp_db):
        """Test the relationship between pickup zones and cities."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        # Create city
        city = City(slug="el-centro", name="El Centro", state="California")
        db.add(city)
        db.commit()
        db.refresh(city)

        # Create multiple zones
        zone1 = PickupZone(city_id=city.id, name="Zone 1", external_ref="EC-1")
        zone2 = PickupZone(city_id=city.id, name="Zone 2", external_ref="EC-2")

        db.add_all([zone1, zone2])
        db.commit()

        # Test relationship
        city_zones = db.query(PickupZone).filter_by(city_id=city.id).all()
        assert len(city_zones) == 2

        db.close()


class TestScheduleModel:
    """Test the Schedule model."""

    def test_create_schedule(self, temp_db):
        """Test creating a schedule."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        # Create city and zone
        city = City(slug="san-diego", name="San Diego", state="California")
        db.add(city)
        db.commit()
        db.refresh(city)

        zone = PickupZone(city_id=city.id, name="Zone A", external_ref="SD-A")
        db.add(zone)
        db.commit()
        db.refresh(zone)

        # Create schedule
        schedule = Schedule(
            city_id=city.id,
            pickup_zone_id=zone.id,
            trash_day_of_week="MON",
            recycling_day_of_week="TUE",
            green_day_of_week="WED",
            source="OFFICIAL"
        )

        db.add(schedule)
        db.commit()
        db.refresh(schedule)

        assert schedule.id is not None
        assert schedule.trash_day_of_week == "MON"
        assert schedule.recycling_day_of_week == "TUE"
        assert schedule.source == "OFFICIAL"

        db.close()


class TestAddressPickupInfoModel:
    """Test the AddressPickupInfo model."""

    def test_create_address_pickup_info(self, temp_db):
        """Test creating address pickup info."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        # Create city
        city = City(slug="san-diego", name="San Diego", state="California")
        db.add(city)
        db.commit()
        db.refresh(city)

        # Create address
        address = Address(
            city_id=city.id,
            normalized_address="123 MAIN ST",
            house_number="123",
            street="MAIN ST",
            city_name="San Diego",
            state="CA",
            lat=32.7157,
            lon=-117.1611
        )
        db.add(address)
        db.commit()
        db.refresh(address)

        # Create pickup zone
        zone = PickupZone(city_id=city.id, name="Zone A", external_ref="SD-A")
        db.add(zone)
        db.commit()
        db.refresh(zone)

        # Create address pickup info
        pickup_info = AddressPickupInfo(
            address_id=address.id,
            pickup_zone_id=zone.id,
            trash_day_of_week="MON",
            recycling_day_of_week="TUE",
            green_day_of_week="WED",
            source="OFFICIAL"
        )

        db.add(pickup_info)
        db.commit()
        db.refresh(pickup_info)

        assert pickup_info.id is not None
        assert pickup_info.address_id == address.id
        assert pickup_info.trash_day_of_week == "MON"

        db.close()

    def test_address_pickup_info_unique_per_address(self, temp_db):
        """Test that each address can only have one pickup info record."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        # Create city and address
        city = City(slug="san-diego", name="San Diego", state="California")
        db.add(city)
        db.commit()
        db.refresh(city)

        address = Address(
            city_id=city.id,
            normalized_address="456 ELM ST",
            house_number="456",
            street="ELM ST",
            city_name="San Diego",
            lat=32.7157,
            lon=-117.1611
        )
        db.add(address)
        db.commit()
        db.refresh(address)

        # Create first pickup info
        pickup_info1 = AddressPickupInfo(
            address_id=address.id,
            trash_day_of_week="MON",
            source="OFFICIAL"
        )
        db.add(pickup_info1)
        db.commit()

        # Try to create second pickup info for same address
        pickup_info2 = AddressPickupInfo(
            address_id=address.id,
            trash_day_of_week="TUE",
            source="CROWD"
        )
        db.add(pickup_info2)

        with pytest.raises(Exception):  # Should raise IntegrityError due to unique constraint
            db.commit()

        db.close()


class TestRelationships:
    """Test relationships between models."""

    def test_city_to_addresses_relationship(self, temp_db):
        """Test the relationship from City to Addresses."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        # Create city
        city = City(slug="fresno", name="Fresno", state="California")
        db.add(city)
        db.commit()
        db.refresh(city)

        # Create addresses
        addr1 = Address(
            city_id=city.id,
            normalized_address="100 MAIN ST",
            house_number="100",
            street="MAIN ST",
            city_name="Fresno",
            lat=36.7378,
            lon=-119.7871
        )
        addr2 = Address(
            city_id=city.id,
            normalized_address="200 MAIN ST",
            house_number="200",
            street="MAIN ST",
            city_name="Fresno",
            lat=36.7379,
            lon=-119.7871
        )

        db.add_all([addr1, addr2])
        db.commit()

        # Test relationship
        assert len(city.addresses) == 2

        db.close()

    def test_city_to_pickup_zones_relationship(self, temp_db):
        """Test the relationship from City to PickupZones."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        # Create city
        city = City(slug="riverside", name="Riverside", state="California")
        db.add(city)
        db.commit()
        db.refresh(city)

        # Create zones
        zone1 = PickupZone(city_id=city.id, name="North", external_ref="RV-N")
        zone2 = PickupZone(city_id=city.id, name="South", external_ref="RV-S")
        zone3 = PickupZone(city_id=city.id, name="East", external_ref="RV-E")

        db.add_all([zone1, zone2, zone3])
        db.commit()

        # Test relationship
        assert len(city.pickup_zones) == 3

        db.close()


class TestCompleteWorkflow:
    """Test a complete workflow with all new tables."""

    def test_full_address_workflow(self, temp_db):
        """Test creating a complete address with city, zone, schedule, and pickup info."""
        _, SessionLocal = temp_db
        db = SessionLocal()

        # 1. Create city
        city = City(
            slug="bakersfield",
            name="Bakersfield",
            state="California",
            county="Kern County"
        )
        db.add(city)
        db.commit()
        db.refresh(city)

        # 2. Create pickup zone
        zone = PickupZone(
            city_id=city.id,
            name="Downtown",
            external_ref="BK-DT"
        )
        db.add(zone)
        db.commit()
        db.refresh(zone)

        # 3. Create schedule for zone
        schedule = Schedule(
            city_id=city.id,
            pickup_zone_id=zone.id,
            trash_day_of_week="WED",
            recycling_day_of_week="THU",
            green_day_of_week="FRI",
            source="OFFICIAL"
        )
        db.add(schedule)
        db.commit()
        db.refresh(schedule)

        # 4. Create address
        address = Address(
            city_id=city.id,
            normalized_address="789 OAK AVE",
            house_number="789",
            street="OAK AVE",
            city_name="Bakersfield",
            state="CA",
            lat=35.3733,
            lon=-119.0187
        )
        db.add(address)
        db.commit()
        db.refresh(address)

        # 5. Create address pickup info linking it all together
        pickup_info = AddressPickupInfo(
            address_id=address.id,
            pickup_zone_id=zone.id,
            trash_day_of_week=schedule.trash_day_of_week,
            recycling_day_of_week=schedule.recycling_day_of_week,
            green_day_of_week=schedule.green_day_of_week,
            source="OFFICIAL"
        )
        db.add(pickup_info)
        db.commit()
        db.refresh(pickup_info)

        # Verify everything is linked correctly
        assert address.city_id == city.id
        assert pickup_info.address_id == address.id
        assert pickup_info.pickup_zone_id == zone.id
        assert schedule.city_id == city.id
        assert schedule.pickup_zone_id == zone.id

        # Verify schedule data
        assert pickup_info.trash_day_of_week == "WED"
        assert pickup_info.recycling_day_of_week == "THU"
        assert pickup_info.green_day_of_week == "FRI"

        db.close()
