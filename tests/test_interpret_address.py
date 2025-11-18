"""
Tests for the /interpret-address endpoint with AI-powered address interpretation.

Tests include:
- Mocked AI responses for consistent testing
- Geocoding fallback scenarios
- Various input formats and edge cases
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app, get_db
from app.models import Base
from app.ai_service import AddressInterpretation


@pytest.fixture(scope="function")
def test_db():
    """Create an in-memory SQLite database for testing."""
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

    # Remove temporary database file
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(test_db):
    """Create a test client for the API."""
    return TestClient(app)


@pytest.fixture
def mock_ai_high_confidence():
    """Mock AI interpreter with high confidence result."""
    mock_result = AddressInterpretation(
        normalized_address="123 Main Street, San Diego, CA 92101",
        confidence=0.95,
        city="San Diego",
        state="CA",
        zip_code="92101",
        house_number="123",
        street="Main Street",
        reasoning="Clear address with all components present"
    )
    return mock_result


@pytest.fixture
def mock_ai_low_confidence():
    """Mock AI interpreter with low confidence result."""
    mock_result = AddressInterpretation(
        normalized_address="456 Elm Avenue, Los Angeles, CA",
        confidence=0.45,
        city="Los Angeles",
        state="CA",
        zip_code=None,
        house_number="456",
        street="Elm Avenue",
        reasoning="Missing ZIP code, uncertain about exact location"
    )
    return mock_result


@pytest.fixture
def mock_geocode_high_quality():
    """Mock geocoding result with high quality."""
    return {
        'lat': 32.7157,
        'lon': -117.1611,
        'display_name': '123 Main Street, San Diego, California 92101, USA',
        'address_components': {
            'house_number': '123',
            'road': 'Main Street',
            'city': 'San Diego',
            'state': 'California',
            'postcode': '92101',
            'country': 'USA'
        },
        'quality': 'high'
    }


@pytest.fixture
def mock_geocode_medium_quality():
    """Mock geocoding result with medium quality."""
    return {
        'lat': 34.0522,
        'lon': -118.2437,
        'display_name': 'Main Street, Los Angeles, California, USA',
        'address_components': {
            'house_number': None,
            'road': 'Main Street',
            'city': 'Los Angeles',
            'state': 'California',
            'postcode': None,
            'country': 'USA'
        },
        'quality': 'medium'
    }


class TestInterpretAddressAI:
    """Test AI-powered address interpretation."""

    @patch('app.main.create_ai_interpreter')
    def test_successful_ai_interpretation_high_confidence(
        self, mock_create_interpreter, client, test_db, mock_ai_high_confidence
    ):
        """Test successful AI interpretation with high confidence."""
        # Setup mock
        mock_interpreter = AsyncMock()
        mock_interpreter.interpret = AsyncMock(return_value=mock_ai_high_confidence)
        mock_create_interpreter.return_value = mock_interpreter

        # Make request
        response = client.post(
            "/interpret-address",
            json={
                "text": "I live at 123 Main Street in San Diego, 92101",
                "use_geocoding": False
            }
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()

        assert data['success'] is True
        assert data['normalized_address'] == "123 Main Street, San Diego, CA 92101"
        assert data['confidence'] == 0.95
        assert data['city'] == "San Diego"
        assert data['city_id'] == "ca_san_diego"
        assert data['state'] == "CA"
        assert data['zip_code'] == "92101"
        assert data['interpretation_method'] == "ai"
        assert data['ai_reasoning'] == "Clear address with all components present"

    @patch('app.main.create_ai_interpreter')
    @patch('app.main.geocode_address')
    def test_ai_with_geocoding_fallback(
        self, mock_geocode, mock_create_interpreter, client, test_db,
        mock_ai_low_confidence, mock_geocode_high_quality
    ):
        """Test AI interpretation with geocoding fallback for low confidence."""
        # Setup mocks
        mock_interpreter = AsyncMock()
        mock_interpreter.interpret = AsyncMock(return_value=mock_ai_low_confidence)
        mock_create_interpreter.return_value = mock_interpreter
        mock_geocode.return_value = mock_geocode_high_quality

        # Make request
        response = client.post(
            "/interpret-address",
            json={
                "text": "456 Elm Ave somewhere in LA",
                "use_geocoding": True
            }
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()

        assert data['success'] is True
        assert data['confidence'] >= 0.8  # Boosted by high-quality geocoding
        assert data['interpretation_method'] == "hybrid"
        assert data['lat'] == 32.7157
        assert data['lon'] == -117.1611
        assert data['geocoding_quality'] == "high"

    @patch('app.main.create_ai_interpreter')
    def test_ai_interpretation_partial_address(
        self, mock_create_interpreter, client, test_db
    ):
        """Test AI interpretation with partial address information."""
        mock_result = AddressInterpretation(
            normalized_address="Main Street, El Centro, CA",
            confidence=0.65,
            city="El Centro",
            state="CA",
            zip_code=None,
            house_number=None,
            street="Main Street",
            reasoning="Partial address - missing house number"
        )

        mock_interpreter = AsyncMock()
        mock_interpreter.interpret = AsyncMock(return_value=mock_result)
        mock_create_interpreter.return_value = mock_interpreter

        response = client.post(
            "/interpret-address",
            json={
                "text": "Main Street in El Centro",
                "use_geocoding": False
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data['success'] is True
        assert data['city'] == "El Centro"
        assert data['city_id'] == "ca_el_centro"
        assert data['confidence'] == 0.65


class TestInterpretAddressGeocodingOnly:
    """Test geocoding-only scenarios (AI unavailable or disabled)."""

    @patch('app.main.create_ai_interpreter')
    @patch('app.main.geocode_address')
    def test_geocoding_fallback_when_ai_fails(
        self, mock_geocode, mock_create_interpreter, client, test_db,
        mock_geocode_high_quality
    ):
        """Test geocoding fallback when AI interpretation fails."""
        # Setup mocks - AI returns None
        mock_interpreter = AsyncMock()
        mock_interpreter.interpret = AsyncMock(return_value=None)
        mock_create_interpreter.return_value = mock_interpreter
        mock_geocode.return_value = mock_geocode_high_quality

        response = client.post(
            "/interpret-address",
            json={
                "text": "123 Main St, San Diego CA",
                "use_geocoding": True
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data['success'] is True
        assert data['interpretation_method'] == "geocoding"
        assert data['confidence'] == 0.85  # High quality geocoding
        assert data['lat'] == 32.7157
        assert data['lon'] == -117.1611

    @patch('app.main.create_ai_interpreter')
    @patch('app.main.geocode_address')
    def test_both_ai_and_geocoding_fail(
        self, mock_geocode, mock_create_interpreter, client, test_db
    ):
        """Test complete failure when both AI and geocoding fail."""
        # Setup mocks - both return None/empty
        mock_interpreter = AsyncMock()
        mock_interpreter.interpret = AsyncMock(return_value=None)
        mock_create_interpreter.return_value = mock_interpreter
        mock_geocode.return_value = None

        response = client.post(
            "/interpret-address",
            json={
                "text": "some random gibberish xyz123",
                "use_geocoding": True
            }
        )

        assert response.status_code == 200  # Still returns 200 but with success=False
        data = response.json()

        assert data['success'] is False
        assert data['confidence'] == 0.0
        assert data['normalized_address'] == ""
        assert 'error' in data
        assert "Failed to interpret" in data['error']


class TestInterpretAddressEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_text_validation(self, client, test_db):
        """Test that empty text is rejected."""
        response = client.post(
            "/interpret-address",
            json={"text": "   ", "use_geocoding": False}
        )

        assert response.status_code == 422  # Validation error

    def test_too_short_text(self, client, test_db):
        """Test that text shorter than 3 characters is rejected."""
        response = client.post(
            "/interpret-address",
            json={"text": "ab", "use_geocoding": False}
        )

        assert response.status_code == 422  # Validation error

    @patch('app.main.create_ai_interpreter')
    def test_missing_use_geocoding_defaults_to_true(
        self, mock_create_interpreter, client, test_db, mock_ai_high_confidence
    ):
        """Test that use_geocoding defaults to True."""
        mock_interpreter = AsyncMock()
        mock_interpreter.interpret = AsyncMock(return_value=mock_ai_high_confidence)
        mock_create_interpreter.return_value = mock_interpreter

        # Request without use_geocoding field
        response = client.post(
            "/interpret-address",
            json={"text": "123 Main Street, San Diego"}
        )

        assert response.status_code == 200
        assert response.json()['success'] is True

    def test_invalid_json(self, client, test_db):
        """Test that invalid JSON is handled."""
        response = client.post(
            "/interpret-address",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_missing_text_field(self, client, test_db):
        """Test that missing text field is rejected."""
        response = client.post(
            "/interpret-address",
            json={"use_geocoding": True}  # Missing 'text'
        )

        assert response.status_code == 422


class TestInterpretAddressCityMatching:
    """Test city matching and city_id inference."""

    @patch('app.main.create_ai_interpreter')
    def test_city_id_inference_from_supported_cities(
        self, mock_create_interpreter, client, test_db
    ):
        """Test that city_id is correctly inferred for supported cities."""
        test_cases = [
            ("San Diego", "ca_san_diego"),
            ("El Centro", "ca_el_centro"),
            ("Fresno", "ca_fresno"),
            ("Bakersfield", "ca_bakersfield"),
        ]

        for city_name, expected_city_id in test_cases:
            mock_result = AddressInterpretation(
                normalized_address=f"123 Main St, {city_name}, CA 92101",
                confidence=0.9,
                city=city_name,
                state="CA",
                zip_code="92101",
                house_number="123",
                street="Main St",
                reasoning="Test case"
            )

            mock_interpreter = AsyncMock()
            mock_interpreter.interpret = AsyncMock(return_value=mock_result)
            mock_create_interpreter.return_value = mock_interpreter

            response = client.post(
                "/interpret-address",
                json={"text": f"123 Main St {city_name}", "use_geocoding": False}
            )

            assert response.status_code == 200
            data = response.json()
            assert data['city'] == city_name
            assert data['city_id'] == expected_city_id

    @patch('app.main.create_ai_interpreter')
    def test_unsupported_city_no_city_id(
        self, mock_create_interpreter, client, test_db
    ):
        """Test that unsupported cities don't get a city_id."""
        mock_result = AddressInterpretation(
            normalized_address="123 Main St, Unknown City, CA 90001",
            confidence=0.8,
            city="Unknown City",
            state="CA",
            zip_code="90001",
            house_number="123",
            street="Main St",
            reasoning="Unknown city"
        )

        mock_interpreter = AsyncMock()
        mock_interpreter.interpret = AsyncMock(return_value=mock_result)
        mock_create_interpreter.return_value = mock_interpreter

        response = client.post(
            "/interpret-address",
            json={"text": "123 Main St Unknown City CA", "use_geocoding": False}
        )

        assert response.status_code == 200
        data = response.json()
        assert data['city'] == "Unknown City"
        assert data['city_id'] is None  # Not in supported cities


class TestInterpretAddressResponseStructure:
    """Test response structure and field validation."""

    @patch('app.main.create_ai_interpreter')
    def test_response_has_all_required_fields(
        self, mock_create_interpreter, client, test_db, mock_ai_high_confidence
    ):
        """Test that response contains all expected fields."""
        mock_interpreter = AsyncMock()
        mock_interpreter.interpret = AsyncMock(return_value=mock_ai_high_confidence)
        mock_create_interpreter.return_value = mock_interpreter

        response = client.post(
            "/interpret-address",
            json={"text": "123 Main Street", "use_geocoding": False}
        )

        assert response.status_code == 200
        data = response.json()

        # Check required fields
        required_fields = [
            'success',
            'normalized_address',
            'confidence',
            'interpretation_method'
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Check optional fields exist (even if None)
        optional_fields = [
            'city', 'city_id', 'state', 'zip_code',
            'lat', 'lon', 'ai_reasoning', 'geocoding_quality', 'error'
        ]

        for field in optional_fields:
            assert field in data, f"Missing optional field: {field}"

    @patch('app.main.create_ai_interpreter')
    def test_confidence_within_valid_range(
        self, mock_create_interpreter, client, test_db
    ):
        """Test that confidence is always between 0.0 and 1.0."""
        test_confidences = [0.0, 0.5, 0.99, 1.0]

        for conf in test_confidences:
            mock_result = AddressInterpretation(
                normalized_address="Test Address",
                confidence=conf,
                city="San Diego",
                state="CA",
                reasoning="Test"
            )

            mock_interpreter = AsyncMock()
            mock_interpreter.interpret = AsyncMock(return_value=mock_result)
            mock_create_interpreter.return_value = mock_interpreter

            response = client.post(
                "/interpret-address",
                json={"text": "test address", "use_geocoding": False}
            )

            assert response.status_code == 200
            data = response.json()
            assert 0.0 <= data['confidence'] <= 1.0
