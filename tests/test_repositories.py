"""
Comprehensive tests for repository layer.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Address, CrowdReport, CrowdConsensus, RequestMetrics
from app.repositories import (
    AddressRepository,
    CrowdReportRepository,
    CrowdConsensusRepository,
    MetricsRepository,
)


@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


class TestAddressRepository:
    """Test suite for AddressRepository."""

    def test_get_by_id(self, db_session):
        """Test getting address by ID."""
        repo = AddressRepository(db_session)

        # Create test address
        addr = Address(
            normalized_address="123 MAIN ST, SAN DIEGO, CA",
            house_number="123",
            street="MAIN ST",
            city="SAN DIEGO",
            city_id="san_diego",
            state="CA",
            lat=32.7157,
            lon=-117.1611,
        )
        db_session.add(addr)
        db_session.commit()

        # Test retrieval
        result = repo.get_by_id(addr.id)
        assert result is not None
        assert result.id == addr.id
        assert result.normalized_address == "123 MAIN ST, SAN DIEGO, CA"

    def test_get_by_id_not_found(self, db_session):
        """Test getting non-existent address."""
        repo = AddressRepository(db_session)
        result = repo.get_by_id(999)
        assert result is None

    def test_get_by_normalized_address(self, db_session):
        """Test getting address by normalized string."""
        repo = AddressRepository(db_session)

        # Create test address
        addr = Address(
            normalized_address="456 ELM AVE, FRESNO, CA",
            house_number="456",
            street="ELM AVE",
            city="FRESNO",
            city_id="fresno",
            state="CA",
            lat=36.7378,
            lon=-119.7871,
        )
        db_session.add(addr)
        db_session.commit()

        # Test retrieval
        result = repo.get_by_normalized_address("456 ELM AVE, FRESNO, CA")
        assert result is not None
        assert result.house_number == "456"
        assert result.city_id == "fresno"

    def test_get_by_normalized_address_with_city_filter(self, db_session):
        """Test getting address with city filter."""
        repo = AddressRepository(db_session)

        # Create addresses in different cities
        addr1 = Address(
            normalized_address="100 OAK ST, SAN DIEGO, CA",
            city="SAN DIEGO",
            city_id="san_diego",
            lat=32.7157,
            lon=-117.1611,
        )
        addr2 = Address(
            normalized_address="100 OAK ST, FRESNO, CA",
            city="FRESNO",
            city_id="fresno",
            lat=36.7378,
            lon=-119.7871,
        )
        db_session.add_all([addr1, addr2])
        db_session.commit()

        # Test with city filter
        result = repo.get_by_normalized_address("100 OAK ST, FRESNO, CA", city_id="fresno")
        assert result is not None
        assert result.city_id == "fresno"

    def test_find_by_coordinates(self, db_session):
        """Test finding address by coordinates."""
        repo = AddressRepository(db_session)

        # Create test address
        addr = Address(
            normalized_address="789 PINE RD, SAN DIEGO, CA",
            city="SAN DIEGO",
            city_id="san_diego",
            lat=32.7157,
            lon=-117.1611,
        )
        db_session.add(addr)
        db_session.commit()

        # Test finding nearby address (within 50m)
        result = repo.find_by_coordinates(lat=32.7158, lon=-117.1612, max_distance_meters=50)
        assert result is not None
        assert result.id == addr.id

    def test_find_by_coordinates_not_found(self, db_session):
        """Test coordinates too far away."""
        repo = AddressRepository(db_session)

        # Create test address
        addr = Address(
            normalized_address="789 PINE RD, SAN DIEGO, CA",
            lat=32.7157,
            lon=-117.1611,
        )
        db_session.add(addr)
        db_session.commit()

        # Test finding far away location
        result = repo.find_by_coordinates(lat=36.7378, lon=-119.7871, max_distance_meters=50)
        assert result is None

    def test_find_or_create_existing(self, db_session):
        """Test find_or_create with existing address."""
        repo = AddressRepository(db_session)

        # Create initial address
        addr = Address(
            normalized_address="321 MAPLE DR, EL CENTRO, CA",
            city="EL CENTRO",
            city_id="el_centro",
            lat=32.792,
            lon=-115.563,
        )
        db_session.add(addr)
        db_session.commit()
        initial_id = addr.id

        # Try to create duplicate
        result = repo.find_or_create("321 Maple Dr, El Centro, CA")
        assert result.id == initial_id  # Should return existing

    def test_find_or_create_new(self, db_session):
        """Test find_or_create creates new address."""
        repo = AddressRepository(db_session)

        # Create new address
        result = repo.find_or_create("999 NEW ST, CALEXICO, CA", lat=32.679, lon=-115.499)
        assert result is not None
        assert result.id is not None
        assert "999 NEW ST" in result.normalized_address
        assert result.lat == 32.679
        assert result.lon == -115.499

    def test_count(self, db_session):
        """Test counting addresses."""
        repo = AddressRepository(db_session)

        # Add multiple addresses
        addresses = [
            Address(normalized_address=f"ADDR{i}", city="TEST", lat=32.0, lon=-117.0)
            for i in range(5)
        ]
        db_session.add_all(addresses)
        db_session.commit()

        assert repo.count() == 5

    def test_get_stats_by_city(self, db_session):
        """Test getting statistics by city."""
        repo = AddressRepository(db_session)

        # Add addresses in different cities
        addresses = [
            Address(normalized_address="ADDR1", city="SAN DIEGO", lat=32.7, lon=-117.1),
            Address(normalized_address="ADDR2", city="SAN DIEGO", lat=32.7, lon=-117.1),
            Address(normalized_address="ADDR3", city="FRESNO", lat=36.7, lon=-119.7),
        ]
        db_session.add_all(addresses)
        db_session.commit()

        stats = repo.get_stats_by_city()
        assert len(stats) == 2
        assert any(s["city"] == "SAN DIEGO" and s["address_count"] == 2 for s in stats)
        assert any(s["city"] == "FRESNO" and s["address_count"] == 1 for s in stats)


class TestCrowdReportRepository:
    """Test suite for CrowdReportRepository."""

    def test_create(self, db_session):
        """Test creating a crowd report."""
        # Create address first
        addr = Address(
            normalized_address="TEST ADDR",
            city="TEST",
            lat=32.0,
            lon=-117.0,
        )
        db_session.add(addr)
        db_session.commit()

        # Create report
        repo = CrowdReportRepository(db_session)
        report = repo.create(
            address_id=addr.id,
            trash_day="MON",
            recycling_day="WED",
            green_day="FRI",
            user_hash="test_user",
            ip_address="192.168.1.1",
        )

        assert report.id is not None
        assert report.address_id == addr.id
        assert report.trash_day == "MON"
        assert report.recycling_day == "WED"
        assert report.green_day == "FRI"

    def test_get_by_address_id(self, db_session):
        """Test getting reports for an address."""
        # Create address
        addr = Address(normalized_address="TEST", city="TEST", lat=32.0, lon=-117.0)
        db_session.add(addr)
        db_session.commit()

        # Create multiple reports
        repo = CrowdReportRepository(db_session)
        repo.create(addr.id, trash_day="MON")
        repo.create(addr.id, trash_day="MON")
        repo.create(addr.id, trash_day="TUE")

        reports = repo.get_by_address_id(addr.id)
        assert len(reports) == 3

    def test_count(self, db_session):
        """Test counting reports."""
        # Create address
        addr = Address(normalized_address="TEST", city="TEST", lat=32.0, lon=-117.0)
        db_session.add(addr)
        db_session.commit()

        # Create reports
        repo = CrowdReportRepository(db_session)
        repo.create(addr.id, trash_day="MON")
        repo.create(addr.id, trash_day="TUE")

        assert repo.count() == 2


class TestCrowdConsensusRepository:
    """Test suite for CrowdConsensusRepository."""

    def test_update_or_create_new(self, db_session):
        """Test creating new consensus."""
        # Create address
        addr = Address(normalized_address="TEST", city="TEST", lat=32.0, lon=-117.0)
        db_session.add(addr)
        db_session.commit()

        # Create consensus
        repo = CrowdConsensusRepository(db_session)
        consensus = repo.update_or_create(
            address_id=addr.id,
            consensus_trash_day="MON",
            consensus_recycling_day="WED",
            consensus_green_day="FRI",
            total_reports=5,
            trash_agreement_ratio=0.8,
            recycling_agreement_ratio=0.9,
            green_agreement_ratio=0.85,
            is_verified=True,
        )

        assert consensus.id is not None
        assert consensus.address_id == addr.id
        assert consensus.consensus_trash_day == "MON"
        assert consensus.is_verified is True
        assert consensus.total_reports == 5

    def test_update_or_create_update_existing(self, db_session):
        """Test updating existing consensus."""
        # Create address and initial consensus
        addr = Address(normalized_address="TEST", city="TEST", lat=32.0, lon=-117.0)
        db_session.add(addr)
        db_session.commit()

        repo = CrowdConsensusRepository(db_session)
        consensus1 = repo.update_or_create(
            address_id=addr.id,
            consensus_trash_day="MON",
            consensus_recycling_day=None,
            consensus_green_day=None,
            total_reports=2,
            trash_agreement_ratio=0.5,
            recycling_agreement_ratio=0.0,
            green_agreement_ratio=0.0,
            is_verified=False,
        )
        initial_id = consensus1.id

        # Update with more reports
        consensus2 = repo.update_or_create(
            address_id=addr.id,
            consensus_trash_day="MON",
            consensus_recycling_day="WED",
            consensus_green_day="FRI",
            total_reports=5,
            trash_agreement_ratio=0.9,
            recycling_agreement_ratio=0.8,
            green_agreement_ratio=0.85,
            is_verified=True,
        )

        assert consensus2.id == initial_id  # Same record
        assert consensus2.total_reports == 5
        assert consensus2.is_verified is True

    def test_get_by_address_id(self, db_session):
        """Test getting consensus by address."""
        # Create address and consensus
        addr = Address(normalized_address="TEST", city="TEST", lat=32.0, lon=-117.0)
        db_session.add(addr)
        db_session.commit()

        repo = CrowdConsensusRepository(db_session)
        repo.update_or_create(
            address_id=addr.id,
            consensus_trash_day="MON",
            consensus_recycling_day=None,
            consensus_green_day=None,
            total_reports=3,
            trash_agreement_ratio=0.8,
            recycling_agreement_ratio=0.0,
            green_agreement_ratio=0.0,
            is_verified=True,
        )

        consensus = repo.get_by_address_id(addr.id)
        assert consensus is not None
        assert consensus.address_id == addr.id

    def test_delete_by_address_id(self, db_session):
        """Test deleting consensus."""
        # Create address and consensus
        addr = Address(normalized_address="TEST", city="TEST", lat=32.0, lon=-117.0)
        db_session.add(addr)
        db_session.commit()

        repo = CrowdConsensusRepository(db_session)
        repo.update_or_create(
            address_id=addr.id,
            consensus_trash_day="MON",
            consensus_recycling_day=None,
            consensus_green_day=None,
            total_reports=1,
            trash_agreement_ratio=1.0,
            recycling_agreement_ratio=0.0,
            green_agreement_ratio=0.0,
            is_verified=False,
        )

        # Delete
        result = repo.delete_by_address_id(addr.id)
        assert result is True

        # Verify deleted
        consensus = repo.get_by_address_id(addr.id)
        assert consensus is None

    def test_count_and_count_verified(self, db_session):
        """Test counting consensus records."""
        # Create addresses and consensus
        addrs = [
            Address(normalized_address=f"TEST{i}", city="TEST", lat=32.0, lon=-117.0)
            for i in range(3)
        ]
        db_session.add_all(addrs)
        db_session.commit()

        repo = CrowdConsensusRepository(db_session)

        # Create 2 verified, 1 unverified
        repo.update_or_create(
            addrs[0].id, "MON", None, None, 5, 0.9, 0.0, 0.0, True
        )
        repo.update_or_create(
            addrs[1].id, "TUE", None, None, 4, 0.85, 0.0, 0.0, True
        )
        repo.update_or_create(
            addrs[2].id, "WED", None, None, 2, 0.6, 0.0, 0.0, False
        )

        assert repo.count() == 3
        assert repo.count_verified() == 2


class TestMetricsRepository:
    """Test suite for MetricsRepository."""

    def test_create(self, db_session):
        """Test creating a metrics record."""
        repo = MetricsRepository(db_session)

        metric = repo.create(
            endpoint="/lookup",
            method="GET",
            status_code=200,
            response_time_ms=45.2,
            city="SAN DIEGO",
            user_agent="TestClient/1.0",
            ip_address="192.168.1.1",
        )

        assert metric.id is not None
        assert metric.endpoint == "/lookup"
        assert metric.status_code == 200
        assert metric.response_time_ms == 45.2
        assert metric.city == "SAN DIEGO"
