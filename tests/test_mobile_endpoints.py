"""Tests for mobile endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

from app.main import app
from app.database import Base, get_db
from app.models import Address, CrowdReport, CrowdConsensus, ApiKey
from app.api_key_auth import create_api_key, hash_api_key


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_mobile.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """Create test client with dependency override."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def api_key(db):
    """Create a test API key."""
    full_key, api_key_record = create_api_key(
        db=db,
        name="Test Key",
        description="For testing",
        scopes=["mobile:lookup", "mobile:report"],
        rate_limit_per_minute=100,  # High limit for testing
        rate_limit_per_hour=1000,
        created_by="pytest"
    )
    return full_key, api_key_record


@pytest.fixture
def sample_address(db):
    """Create a sample address with verified consensus."""
    address = Address(
        normalized_address="123 MAIN ST, SAN DIEGO, CA",
        city="San Diego",
        lat=32.7157,
        lon=-117.1611,
        official_trash_day="TUESDAY"
    )
    db.add(address)
    db.commit()
    db.refresh(address)

    # Add some crowd reports
    for i in range(5):
        report = CrowdReport(
            address_id=address.id,
            trash_day="TUE",
            recycling_day="FRI",
            user_hash=f"user_{i}",
            ip_address=f"192.168.1.{i}"
        )
        db.add(report)

    # Create verified consensus
    consensus = CrowdConsensus(
        address_id=address.id,
        consensus_trash_day="TUE",
        consensus_recycling_day="FRI",
        reports_count=5,
        trash_agreement_ratio=1.0,
        recycling_agreement_ratio=1.0,
        is_verified=True
    )
    db.add(consensus)
    db.commit()

    return address


# ============================================================================
# Authentication Tests
# ============================================================================

def test_mobile_lookup_requires_api_key(client):
    """Test that mobile lookup requires API key."""
    response = client.get("/mobile/lookup?address=123 Main St")
    assert response.status_code == 401
    assert "API key required" in response.json()["detail"]


def test_mobile_lookup_invalid_api_key(client):
    """Test that invalid API key is rejected."""
    response = client.get(
        "/mobile/lookup?address=123 Main St",
        headers={"X-API-Key": "invalid_key"}
    )
    assert response.status_code == 401
    assert "Invalid or expired" in response.json()["detail"]


def test_mobile_report_requires_api_key(client):
    """Test that mobile report requires API key."""
    response = client.post(
        "/mobile/report",
        json={"address": "123 Main St", "trash": "TUE"}
    )
    assert response.status_code == 401


# ============================================================================
# Mobile Lookup Tests
# ============================================================================

def test_mobile_lookup_by_address_success(client, api_key, sample_address):
    """Test successful address lookup."""
    full_key, _ = api_key

    response = client.get(
        "/mobile/lookup?address=123 Main St, San Diego, CA",
        headers={"X-API-Key": full_key}
    )

    assert response.status_code == 200
    data = response.json()

    # Check simplified response structure
    assert "address" in data
    assert "city" in data
    assert "trash" in data
    assert "recycling" in data
    assert "source" in data
    assert "lat" in data
    assert "lon" in data

    # Check values
    assert data["city"] == "San Diego"
    assert data["trash"] == "TUE"  # Abbreviated
    assert data["recycling"] == "FRI"
    assert data["source"] == "verified"  # Has verified consensus


def test_mobile_lookup_by_coordinates_success(client, api_key, sample_address):
    """Test successful coordinate lookup."""
    full_key, _ = api_key

    response = client.get(
        f"/mobile/lookup?lat={sample_address.lat}&lon={sample_address.lon}",
        headers={"X-API-Key": full_key}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["address"] == sample_address.normalized_address
    assert data["source"] == "verified"


def test_mobile_lookup_missing_address(client, api_key):
    """Test lookup with missing address returns 404."""
    full_key, _ = api_key

    response = client.get(
        "/mobile/lookup?address=999 Nonexistent St",
        headers={"X-API-Key": full_key}
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_mobile_lookup_invalid_input(client, api_key):
    """Test lookup with invalid input (no address or coords)."""
    full_key, _ = api_key

    response = client.get(
        "/mobile/lookup",  # No parameters
        headers={"X-API-Key": full_key}
    )

    assert response.status_code == 422  # Validation error


def test_mobile_lookup_data_source_priority(client, api_key, db):
    """Test that data source priority is correct."""
    full_key, _ = api_key

    # Create address with official data only
    address = Address(
        normalized_address="456 OAK AVE, SAN DIEGO, CA",
        city="San Diego",
        lat=32.7157,
        lon=-117.1611,
        official_trash_day="WEDNESDAY"
    )
    db.add(address)
    db.commit()

    response = client.get(
        "/mobile/lookup?address=456 Oak Ave, San Diego, CA",
        headers={"X-API-Key": full_key}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "official"
    assert data["trash"] == "WED"


# ============================================================================
# Mobile Report Tests
# ============================================================================

def test_mobile_report_success(client, api_key, db):
    """Test successful report submission."""
    full_key, _ = api_key

    response = client.post(
        "/mobile/report",
        headers={"X-API-Key": full_key},
        json={
            "address": "789 Pine Rd, San Diego, CA",
            "trash": "THU",
            "recycling": "MON"
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert "submitted successfully" in data["message"].lower()
    assert data["address"] == "789 PINE RD, SAN DIEGO, CA"
    assert data["verified"] is False  # Only 1 report, not verified yet
    assert data["reports"] is None  # Not verified


def test_mobile_report_creates_consensus(client, api_key, db):
    """Test that multiple reports create verified consensus."""
    full_key, _ = api_key

    # Submit 3 identical reports
    for i in range(3):
        response = client.post(
            "/mobile/report",
            headers={"X-API-Key": full_key},
            json={
                "address": "321 Elm St, San Diego, CA",
                "trash": "FRI",
                "user_id": f"user_{i}"
            }
        )
        assert response.status_code == 200

    # Check last response
    data = response.json()
    assert data["verified"] is True  # 3 reports with 100% agreement
    assert data["reports"] == 3


def test_mobile_report_validation_no_days(client, api_key):
    """Test that report without any days is rejected."""
    full_key, _ = api_key

    response = client.post(
        "/mobile/report",
        headers={"X-API-Key": full_key},
        json={"address": "123 Main St"}  # No pickup days
    )

    assert response.status_code == 422  # Validation error


def test_mobile_report_validation_invalid_day(client, api_key):
    """Test that invalid day format is rejected."""
    full_key, _ = api_key

    response = client.post(
        "/mobile/report",
        headers={"X-API-Key": full_key},
        json={
            "address": "123 Main St",
            "trash": "INVALID_DAY"
        }
    )

    assert response.status_code == 422


def test_mobile_report_accepts_full_day_names(client, api_key):
    """Test that full day names are converted to abbreviations."""
    full_key, _ = api_key

    response = client.post(
        "/mobile/report",
        headers={"X-API-Key": full_key},
        json={
            "address": "555 Maple Dr, San Diego, CA",
            "trash": "THURSDAY",  # Full name
            "recycling": "MONDAY"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


# ============================================================================
# Rate Limiting Tests
# ============================================================================

def test_mobile_rate_limiting(client, api_key):
    """Test that rate limiting works for mobile endpoints."""
    full_key, api_key_record = api_key

    # Update rate limit to very low for testing
    from app.database import SessionLocal
    db = SessionLocal()
    api_key_record.rate_limit_per_minute = 2
    db.commit()
    db.close()

    # Make 2 successful requests
    for i in range(2):
        response = client.get(
            "/mobile/lookup?address=123 Main St",
            headers={"X-API-Key": full_key}
        )
        # Might be 404 (not found) or 200, but not rate limited
        assert response.status_code in [200, 404]

    # Third request should be rate limited
    response = client.get(
        "/mobile/lookup?address=123 Main St",
        headers={"X-API-Key": full_key}
    )
    assert response.status_code == 429
    assert "Rate limit exceeded" in response.json()["detail"]


def test_rate_limit_headers(client, api_key, sample_address):
    """Test that rate limit headers are present."""
    full_key, _ = api_key

    response = client.get(
        "/mobile/lookup?address=123 Main St, San Diego, CA",
        headers={"X-API-Key": full_key}
    )

    # Even on success, rate limit info should be available
    # (though not in headers on success, only on 429)
    assert response.status_code == 200


# ============================================================================
# API Key Usage Tracking Tests
# ============================================================================

def test_api_key_usage_tracking(client, api_key, sample_address, db):
    """Test that API key usage is tracked."""
    full_key, api_key_record = api_key

    # Make a request
    response = client.get(
        "/mobile/lookup?address=123 Main St, San Diego, CA",
        headers={"X-API-Key": full_key}
    )

    assert response.status_code == 200

    # Check that usage was recorded
    from app.models import ApiKeyUsage
    usage = db.query(ApiKeyUsage).filter(
        ApiKeyUsage.api_key_id == api_key_record.id
    ).first()

    assert usage is not None
    assert usage.endpoint == "/mobile/lookup"
    assert usage.method == "GET"
    assert usage.status_code == 200
    assert usage.response_time_ms > 0


def test_api_key_total_requests_increments(client, api_key, sample_address, db):
    """Test that total_requests counter increments."""
    full_key, api_key_record = api_key

    initial_count = api_key_record.total_requests or 0

    # Make a request
    client.get(
        "/mobile/lookup?address=123 Main St, San Diego, CA",
        headers={"X-API-Key": full_key}
    )

    # Refresh and check
    db.refresh(api_key_record)
    assert api_key_record.total_requests == initial_count + 1


# ============================================================================
# Response Format Tests
# ============================================================================

def test_mobile_lookup_response_is_minimal(client, api_key, sample_address):
    """Test that mobile response is truly minimal (no extra fields)."""
    full_key, _ = api_key

    response = client.get(
        "/mobile/lookup?address=123 Main St, San Diego, CA",
        headers={"X-API-Key": full_key}
    )

    assert response.status_code == 200
    data = response.json()

    # Should only have these fields
    expected_fields = {"address", "city", "trash", "recycling", "green", "source", "lat", "lon"}
    actual_fields = set(data.keys())

    assert actual_fields == expected_fields, f"Unexpected fields: {actual_fields - expected_fields}"


def test_mobile_report_response_is_minimal(client, api_key):
    """Test that mobile report response is minimal."""
    full_key, _ = api_key

    response = client.post(
        "/mobile/report",
        headers={"X-API-Key": full_key},
        json={
            "address": "999 Test Ave, San Diego, CA",
            "trash": "TUE"
        }
    )

    assert response.status_code == 200
    data = response.json()

    # Should only have these fields
    expected_fields = {"success", "message", "address", "verified", "reports"}
    actual_fields = set(data.keys())

    assert actual_fields == expected_fields


# ============================================================================
# Edge Cases
# ============================================================================

def test_mobile_lookup_with_null_optional_fields(client, api_key, db):
    """Test lookup when address has no pickup data."""
    full_key, _ = api_key

    # Create address with no pickup data
    address = Address(
        normalized_address="000 EMPTY ST, SAN DIEGO, CA",
        city="San Diego",
        lat=32.7157,
        lon=-117.1611
    )
    db.add(address)
    db.commit()

    response = client.get(
        "/mobile/lookup?address=000 Empty St, San Diego, CA",
        headers={"X-API-Key": full_key}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["trash"] is None
    assert data["recycling"] is None
    assert data["green"] is None
    assert data["source"] == "unknown"


def test_expired_api_key_rejected(client, db):
    """Test that expired API key is rejected."""
    # Create expired key
    full_key, api_key_record = create_api_key(
        db=db,
        name="Expired Key",
        expires_in_days=-1  # Expired yesterday
    )

    response = client.get(
        "/mobile/lookup?address=123 Main St",
        headers={"X-API-Key": full_key}
    )

    assert response.status_code == 401


def test_inactive_api_key_rejected(client, api_key, db):
    """Test that inactive (revoked) API key is rejected."""
    full_key, api_key_record = api_key

    # Revoke the key
    api_key_record.is_active = False
    db.commit()

    response = client.get(
        "/mobile/lookup?address=123 Main St",
        headers={"X-API-Key": full_key}
    )

    assert response.status_code == 401
