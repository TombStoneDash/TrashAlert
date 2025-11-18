"""
Comprehensive tests for the upgraded /lookup endpoint.

Tests cover:
1. Exact address match
2. Coordinate-based lookup
3. Address + city_id matching
4. Source priority (CROWD_VERIFIED > OFFICIAL > CROWD_UNVERIFIED > UNKNOWN)
5. Consensus verification threshold
6. No-data "UNKNOWN" responses
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import tempfile
import os

from app.main import app
from app.database import get_db, Base
from app.models import Address, CrowdReport, CrowdConsensus


@pytest.fixture(scope="function")
def test_db():
    """Create a temporary test database for each test."""
    # Create temporary database file
    db_fd, db_path = tempfile.mkstemp(suffix='.db')

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Create session factory
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Override the dependency
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    yield {'factory': TestingSessionLocal, 'engine': engine}

    # Cleanup
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def sample_addresses(test_db):
    """Populate the test database with sample addresses."""
    db = test_db['factory']()

    addresses = [
        Address(
            id=1,
            normalized_address="123 MAIN ST SAN DIEGO CA 92101",
            house_number="123",
            street="MAIN ST",
            city="San Diego",
            city_id="san_diego",
            state="CA",
            zip_code="92101",
            lat=32.7157,
            lon=-117.1611,
            official_trash_day="MON",
            official_recycling_day="WED",
            official_green_day="FRI"
        ),
        Address(
            id=2,
            normalized_address="456 ELM AVE FRESNO CA 93701",
            house_number="456",
            street="ELM AVE",
            city="Fresno",
            city_id="fresno",
            state="CA",
            zip_code="93701",
            lat=36.7378,
            lon=-119.7871,
            official_trash_day="TUE",
            official_recycling_day="THU",
            official_green_day=None
        ),
        Address(
            id=3,
            normalized_address="789 OAK RD EL CENTRO CA 92243",
            house_number="789",
            street="OAK RD",
            city="El Centro",
            city_id="el_centro",
            state="CA",
            zip_code="92243",
            lat=32.7920,
            lon=-115.5631,
            official_trash_day=None,
            official_recycling_day=None,
            official_green_day=None
        ),
        # Address with coordinates nearby for geospatial testing
        Address(
            id=4,
            normalized_address="100 PARK LN SAN DIEGO CA 92101",
            house_number="100",
            street="PARK LN",
            city="San Diego",
            city_id="san_diego",
            state="CA",
            zip_code="92101",
            lat=32.7160,  # ~33 meters from 123 Main St
            lon=-117.1615,
            official_trash_day="WED",
            official_recycling_day="FRI",
            official_green_day=None
        )
    ]

    for addr in addresses:
        db.add(addr)

    db.commit()

    for addr in addresses:
        db.refresh(addr)

    db.close()

    return addresses


@pytest.fixture
def sample_consensus(test_db, sample_addresses):
    """Add consensus data for testing source priority."""
    db = test_db['factory']()

    # Add verified consensus for address 1 (should override official data)
    consensus1 = CrowdConsensus(
        address_id=1,
        consensus_trash_day="TUE",  # Different from official MON
        consensus_recycling_day="THU",
        consensus_green_day="SAT",
        total_reports=5,
        trash_agreement_ratio=0.80,
        recycling_agreement_ratio=0.80,
        green_agreement_ratio=0.80,
        is_verified=True
    )

    # Add unverified consensus for address 3 (no official data)
    consensus3 = CrowdConsensus(
        address_id=3,
        consensus_trash_day="FRI",
        consensus_recycling_day=None,
        consensus_green_day=None,
        total_reports=2,  # Below verification threshold
        trash_agreement_ratio=0.50,
        recycling_agreement_ratio=0.0,
        green_agreement_ratio=0.0,
        is_verified=False
    )

    db.add(consensus1)
    db.add(consensus3)
    db.commit()
    db.close()


class TestLookupExactMatch:
    """Tests for exact address string matching."""

    def test_lookup_with_official_data(self, client, sample_addresses):
        """Test lookup returns official data when no consensus exists."""
        response = client.get("/lookup", params={"address": "456 Elm Ave Fresno CA 93701"})

        assert response.status_code == 200
        data = response.json()

        assert data["matched_address"] == "456 ELM AVE FRESNO CA 93701"
        assert data["city_id"] == "fresno"
        assert data["city_name"] == "Fresno"
        assert data["lat"] == 36.7378
        assert data["lon"] == -119.7871
        assert data["trash_day_of_week"] == "Tuesday"
        assert data["recycling_day_of_week"] == "Thursday"
        assert data["green_waste_day_of_week"] is None
        assert data["data_source"] == "OFFICIAL"
        assert data["consensus_reports_count"] is None
        assert data["consensus_agreement_ratio"] is None

    def test_lookup_with_verified_consensus_override(self, client, sample_addresses, sample_consensus):
        """Test that CROWD_VERIFIED overrides OFFICIAL data."""
        response = client.get("/lookup", params={"address": "123 Main St San Diego CA 92101"})

        assert response.status_code == 200
        data = response.json()

        assert data["matched_address"] == "123 MAIN ST SAN DIEGO CA 92101"
        assert data["city_id"] == "san_diego"
        assert data["trash_day_of_week"] == "Tuesday"  # From consensus, not Monday from official
        assert data["recycling_day_of_week"] == "Thursday"
        assert data["green_waste_day_of_week"] == "Saturday"
        assert data["data_source"] == "CROWD_VERIFIED"
        assert data["consensus_reports_count"] == 5
        assert data["consensus_agreement_ratio"] == 0.80
        assert data["consensus_details"]["reports_count"] == 5
        assert data["consensus_details"]["agreement_ratio"] == 0.80

    def test_lookup_with_unverified_consensus(self, client, sample_addresses, sample_consensus):
        """Test that CROWD_UNVERIFIED is used when no official data exists."""
        response = client.get("/lookup", params={"address": "789 Oak Rd El Centro CA 92243"})

        assert response.status_code == 200
        data = response.json()

        assert data["matched_address"] == "789 OAK RD EL CENTRO CA 92243"
        assert data["city_id"] == "el_centro"
        assert data["trash_day_of_week"] == "Friday"
        assert data["recycling_day_of_week"] is None
        assert data["data_source"] == "CROWD_UNVERIFIED"
        assert data["consensus_reports_count"] == 2
        assert data["consensus_agreement_ratio"] == 0.50

    def test_lookup_unknown_address(self, client, sample_addresses):
        """Test that unknown addresses return UNKNOWN data source."""
        response = client.get("/lookup", params={"address": "999 Nonexistent St"})

        assert response.status_code == 200
        data = response.json()

        assert data["data_source"] == "UNKNOWN"
        assert data["trash_day_of_week"] is None
        assert data["recycling_day_of_week"] is None
        assert data["green_waste_day_of_week"] is None
        assert data["consensus_reports_count"] is None


class TestLookupCoordinates:
    """Tests for coordinate-based lookup."""

    def test_lookup_by_coordinates_exact(self, client, sample_addresses):
        """Test lookup by exact coordinates."""
        response = client.get("/lookup", params={
            "lat": 32.7157,
            "lon": -117.1611
        })

        assert response.status_code == 200
        data = response.json()

        assert data["matched_address"] == "123 MAIN ST SAN DIEGO CA 92101"
        assert data["city_id"] == "san_diego"
        assert data["data_source"] == "OFFICIAL"

    def test_lookup_by_coordinates_nearby(self, client, sample_addresses):
        """Test lookup finds address within 50m radius."""
        # Coordinates ~20m from 100 Park Ln (32.7160, -117.1615)
        # 0.0002 degrees latitude ~= 22 meters
        response = client.get("/lookup", params={
            "lat": 32.7162,
            "lon": -117.1615
        })

        assert response.status_code == 200
        data = response.json()

        assert data["matched_address"] == "100 PARK LN SAN DIEGO CA 92101"
        assert data["city_id"] == "san_diego"
        assert data["trash_day_of_week"] == "Wednesday"

    def test_lookup_by_coordinates_not_found(self, client, sample_addresses):
        """Test lookup returns UNKNOWN when no address within 50m."""
        # Coordinates far from any address
        response = client.get("/lookup", params={
            "lat": 40.7128,  # New York City
            "lon": -74.0060
        })

        assert response.status_code == 200
        data = response.json()

        assert data["data_source"] == "UNKNOWN"
        assert "(40.7128, -74.006)" in data["matched_address"]

    def test_lookup_by_coordinates_with_city_filter(self, client, sample_addresses):
        """Test coordinate lookup with city_id filter."""
        response = client.get("/lookup", params={
            "lat": 32.7157,
            "lon": -117.1611,
            "city_id": "san_diego"
        })

        assert response.status_code == 200
        data = response.json()

        assert data["city_id"] == "san_diego"
        assert data["matched_address"] == "123 MAIN ST SAN DIEGO CA 92101"


class TestLookupWithCityId:
    """Tests for address + city_id lookup."""

    def test_lookup_with_city_id_filter(self, client, sample_addresses):
        """Test that city_id filters results correctly."""
        response = client.get("/lookup", params={
            "address": "456 Elm Ave Fresno CA 93701",
            "city_id": "fresno"
        })

        assert response.status_code == 200
        data = response.json()

        assert data["city_id"] == "fresno"
        assert data["matched_address"] == "456 ELM AVE FRESNO CA 93701"


class TestLookupValidation:
    """Tests for input validation."""

    def test_lookup_missing_params(self, client, sample_addresses):
        """Test that missing both address and coordinates returns 400."""
        response = client.get("/lookup")

        assert response.status_code == 400
        assert "Must provide either" in response.json()["detail"]

    def test_lookup_incomplete_coordinates(self, client, sample_addresses):
        """Test that providing only lat or only lon returns 400."""
        response = client.get("/lookup", params={"lat": 32.7157})
        assert response.status_code == 400

        response = client.get("/lookup", params={"lon": -117.1611})
        assert response.status_code == 400


class TestConsensusThreshold:
    """Tests for consensus verification threshold behavior."""

    def test_consensus_below_report_threshold(self, test_db, client):
        """Test that consensus with <3 reports is not verified."""
        db = test_db['factory']()

        # Create address
        addr = Address(
            normalized_address="999 TEST ST",
            city="San Diego",
            city_id="san_diego",
            lat=32.7,
            lon=-117.1
        )
        db.add(addr)
        db.commit()
        db.refresh(addr)

        # Create reports (only 2, below threshold)
        for i in range(2):
            report = CrowdReport(
                address_id=addr.id,
                trash_day="MON",
                user_hash=f"user{i}"
            )
            db.add(report)

        db.commit()

        # Manually create consensus
        consensus = CrowdConsensus(
            address_id=addr.id,
            consensus_trash_day="MON",
            total_reports=2,
            trash_agreement_ratio=1.0,
            is_verified=False  # Not verified due to low report count
        )
        db.add(consensus)
        db.commit()
        db.close()

        # Lookup should return CROWD_UNVERIFIED, not CROWD_VERIFIED
        response = client.get("/lookup", params={"address": "999 Test St"})

        assert response.status_code == 200
        data = response.json()
        assert data["data_source"] == "CROWD_UNVERIFIED"

    def test_consensus_below_agreement_threshold(self, test_db, client):
        """Test that consensus with <67% agreement is not verified."""
        db = test_db['factory']()

        # Create address
        addr = Address(
            normalized_address="888 TEST AVE",
            city="San Diego",
            city_id="san_diego",
            lat=32.7,
            lon=-117.1
        )
        db.add(addr)
        db.commit()
        db.refresh(addr)

        # Manually create consensus with low agreement
        consensus = CrowdConsensus(
            address_id=addr.id,
            consensus_trash_day="MON",
            total_reports=5,
            trash_agreement_ratio=0.60,  # Below 67% threshold
            is_verified=False
        )
        db.add(consensus)
        db.commit()
        db.close()

        # Lookup should return CROWD_UNVERIFIED
        response = client.get("/lookup", params={"address": "888 Test Ave"})

        assert response.status_code == 200
        data = response.json()
        assert data["data_source"] == "CROWD_UNVERIFIED"


class TestResponseSchema:
    """Tests for response schema completeness."""

    def test_response_has_all_required_fields(self, client, sample_addresses):
        """Test that response includes all required fields."""
        response = client.get("/lookup", params={"address": "123 Main St San Diego CA"})

        assert response.status_code == 200
        data = response.json()

        # Check all required fields exist
        required_fields = [
            "matched_address",
            "city_id",
            "city_name",
            "lat",
            "lon",
            "trash_day_of_week",
            "recycling_day_of_week",
            "green_waste_day_of_week",
            "data_source",
            "consensus_reports_count",
            "consensus_agreement_ratio",
            "consensus_details"
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_consensus_details_structure(self, client, sample_addresses, sample_consensus):
        """Test that consensus_details has correct structure."""
        response = client.get("/lookup", params={"address": "123 Main St San Diego CA 92101"})

        assert response.status_code == 200
        data = response.json()

        consensus_details = data["consensus_details"]
        assert consensus_details is not None
        assert "reports_count" in consensus_details
        assert "agreement_ratio" in consensus_details
        assert isinstance(consensus_details["reports_count"], int)
        assert isinstance(consensus_details["agreement_ratio"], float)


class TestBackwardCompatibility:
    """Tests for backward compatibility with existing clients."""

    def test_lookup_with_only_address_param(self, client, sample_addresses):
        """Test that traditional address-only lookup still works."""
        response = client.get("/lookup?address=456 Elm Ave Fresno CA 93701")

        assert response.status_code == 200
        data = response.json()

        assert data["matched_address"] == "456 ELM AVE FRESNO CA 93701"
        assert data["data_source"] == "OFFICIAL"
