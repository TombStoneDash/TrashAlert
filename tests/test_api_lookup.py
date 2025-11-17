"""
Tests for the TrashAlert API endpoints.

Tests ensure that the API correctly handles address lookups,
returns appropriate status codes, and provides expected data.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api import app, get_db, set_session_factory
from src.models import Base, Address
from src.normalization import normalize_address


@pytest.fixture(scope="function")
def test_db():
    """
    Create an in-memory SQLite database for testing.

    This fixture creates a fresh database for each test and tears it down afterward.
    """
    # Create file-based database for testing (more reliable than in-memory for multiple connections)
    import tempfile
    import os

    # Create a temporary database file
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

    # Override the app's session factory
    set_session_factory(TestingSessionLocal)

    # Override the dependency
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Return both the factory and engine
    yield {'factory': TestingSessionLocal, 'engine': engine}

    # Cleanup
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

    # Remove temporary database file
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def sample_addresses(test_db):
    """
    Populate the test database with sample addresses.

    Returns:
        List of created Address objects
    """
    db = test_db['factory']()

    addresses = [
        Address(
            house_number="123",
            street="MAIN ST",
            city="SAN DIEGO",
            subdivision_id="downtown",
            lat=32.7157,
            lon=-117.1611,
            normalized_address="123 MAIN ST",
            trash_day_of_week="Monday",
            osm_id="way/123456"
        ),
        Address(
            house_number="456",
            street="ELM AVE",
            city="SAN DIEGO",
            subdivision_id="la_jolla",
            lat=32.8328,
            lon=-117.2713,
            normalized_address="456 ELM AVE",
            trash_day_of_week="Tuesday",
            osm_id="way/123457"
        ),
        Address(
            house_number="789",
            street="OAK BLVD",
            city="SAN DIEGO",
            subdivision_id="pacific_beach",
            lat=32.7941,
            lon=-117.2363,
            normalized_address="789 OAK BLVD",
            trash_day_of_week="Wednesday",
            osm_id="way/123458"
        ),
        Address(
            house_number="100",
            street="N PARK DR",
            city="EL CENTRO",
            subdivision_id=None,
            lat=32.7920,
            lon=-115.5630,
            normalized_address="100 N PARK DR",
            trash_day_of_week="Thursday",
            osm_id="way/123459"
        ),
    ]

    for addr in addresses:
        db.add(addr)

    db.commit()

    for addr in addresses:
        db.refresh(addr)

    db.close()

    return addresses


@pytest.fixture
def client():
    """Create a test client for the API."""
    return TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_root_endpoint(self, client, test_db):
        """Test the root endpoint returns 200."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "message" in data

    def test_health_check_endpoint(self, client, test_db):
        """Test the health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestLookupEndpoint:
    """Test the /lookup endpoint."""

    def test_lookup_existing_address(self, client, sample_addresses):
        """Test looking up an existing address."""
        response = client.post(
            "/lookup",
            json={"address": "123 main street"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["normalized_address"] == "123 MAIN ST"
        assert data["trash_day_of_week"] == "Monday"
        assert data["subdivision_id"] == "downtown"
        assert data["lat"] == 32.7157
        assert data["lon"] == -117.1611

    def test_lookup_with_normalization(self, client, sample_addresses):
        """Test that address normalization works in lookup."""
        # Query with unnormalized address
        response = client.post(
            "/lookup",
            json={"address": "456  elm   avenue"}  # Extra spaces
        )

        assert response.status_code == 200
        data = response.json()

        assert data["normalized_address"] == "456 ELM AVE"
        assert data["trash_day_of_week"] == "Tuesday"

    def test_lookup_nonexistent_address(self, client, sample_addresses):
        """Test looking up a non-existent address returns 404."""
        response = client.post(
            "/lookup",
            json={"address": "999 fake street"}
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_lookup_with_city_filter(self, client, sample_addresses):
        """Test looking up address with city filter."""
        response = client.post(
            "/lookup",
            json={"address": "100 north park drive", "city": "El Centro"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["normalized_address"] == "100 N PARK DR"
        assert data["trash_day_of_week"] == "Thursday"

    def test_lookup_returns_expected_trash_day(self, client, sample_addresses):
        """Test that lookup returns the expected trash day."""
        # Test multiple addresses to ensure correct mapping
        test_cases = [
            ("123 main street", "Monday"),
            ("456 elm avenue", "Tuesday"),
            ("789 oak boulevard", "Wednesday"),
            ("100 north park drive", "Thursday"),
        ]

        for address, expected_day in test_cases:
            response = client.post(
                "/lookup",
                json={"address": address}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["trash_day_of_week"] == expected_day

    def test_lookup_empty_address(self, client, sample_addresses):
        """Test looking up an empty address."""
        response = client.post(
            "/lookup",
            json={"address": ""}
        )

        assert response.status_code == 404

    def test_lookup_response_structure(self, client, sample_addresses):
        """Test that lookup response has the correct structure."""
        response = client.post(
            "/lookup",
            json={"address": "123 main street"}
        )

        assert response.status_code == 200
        data = response.json()

        # Check all required fields are present
        required_fields = [
            "normalized_address",
            "trash_day_of_week",
            "subdivision_id",
            "lat",
            "lon"
        ]

        for field in required_fields:
            assert field in data, f"Missing field: {field}"


class TestLookupByIdEndpoint:
    """Test the /lookup/{address_id} endpoint."""

    def test_lookup_by_id_existing(self, client, sample_addresses):
        """Test looking up an address by ID."""
        # Get the first address ID
        address_id = sample_addresses[0].id

        response = client.get(f"/lookup/{address_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["normalized_address"] == "123 MAIN ST"
        assert data["trash_day_of_week"] == "Monday"

    def test_lookup_by_id_nonexistent(self, client, sample_addresses):
        """Test looking up a non-existent ID returns 404."""
        response = client.get("/lookup/999999")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_lookup_by_id_invalid(self, client, sample_addresses):
        """Test looking up with invalid ID format."""
        response = client.get("/lookup/invalid")

        # FastAPI should return 422 for validation error
        assert response.status_code == 422


class TestDatabaseIntegration:
    """Test database integration and data persistence."""

    def test_multiple_lookups_same_address(self, client, sample_addresses):
        """Test that multiple lookups of the same address are consistent."""
        responses = []

        for _ in range(3):
            response = client.post(
                "/lookup",
                json={"address": "123 main street"}
            )
            responses.append(response.json())

        # All responses should be identical
        assert all(r == responses[0] for r in responses)

    def test_subdivision_id_nullable(self, client, sample_addresses):
        """Test that addresses without subdivision_id work correctly."""
        # The El Centro address has no subdivision_id
        response = client.post(
            "/lookup",
            json={"address": "100 north park drive"}
        )

        assert response.status_code == 200
        data = response.json()

        # subdivision_id can be None
        assert data["subdivision_id"] is None
        assert data["trash_day_of_week"] == "Thursday"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_invalid_json_payload(self, client, sample_addresses):
        """Test that invalid JSON payload is handled."""
        response = client.post(
            "/lookup",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_missing_address_field(self, client, sample_addresses):
        """Test that missing address field is handled."""
        response = client.post(
            "/lookup",
            json={"city": "San Diego"}  # Missing 'address' field
        )

        assert response.status_code == 422

    def test_case_insensitive_city_match(self, client, sample_addresses):
        """Test that city matching is case-insensitive."""
        # Database has "SAN DIEGO", test with different cases
        test_cases = ["san diego", "San Diego", "SAN DIEGO"]

        for city_variant in test_cases:
            response = client.post(
                "/lookup",
                json={"address": "123 main street", "city": city_variant}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["normalized_address"] == "123 MAIN ST"
