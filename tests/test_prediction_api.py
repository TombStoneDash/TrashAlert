"""Integration tests for prediction API endpoints."""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Address, CrowdReport, CrowdConsensus
from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def setup_test_data(db: Session):
    """Setup test data for API tests."""
    # Create addresses
    addresses = []
    for i in range(5):
        addr = Address(
            normalized_address=f"456{i} API Test St, San Diego, CA 92101",
            house_number=f"456{i}",
            street="API Test St",
            city_slug="san_diego",
            city_name="San Diego",
            state="CA",
            zip_code="92101",
            lat=32.7157 + (i * 0.001),
            lon=-117.1611 + (i * 0.001)
        )
        db.add(addr)
        addresses.append(addr)
    db.commit()

    # Create reports
    base_date = datetime.now() - timedelta(days=60)
    for i, address in enumerate(addresses):
        for j in range(5):
            report = CrowdReport(
                address_id=address.id,
                trash_day='MON' if j < 4 else 'TUE',
                recycling_day='THU',
                green_day='WED',
                created_at=base_date + timedelta(days=j * 10)
            )
            db.add(report)

    db.commit()

    # Create consensus
    for i, address in enumerate(addresses):
        consensus = CrowdConsensus(
            address_id=address.id,
            consensus_trash_day='MON',
            consensus_recycling_day='THU',
            consensus_green_day='WED',
            total_reports=5,
            trash_agreement_ratio=0.8,
            recycling_agreement_ratio=0.9,
            green_agreement_ratio=0.85,
            is_verified=True
        )
        db.add(consensus)

    db.commit()
    return addresses


class TestPredictionEndpoints:
    """Test suite for prediction API endpoints."""

    def test_train_delay_model(self, client, setup_test_data):
        """Test training delay model via API."""
        response = client.post(
            "/predict/train",
            json={"model_type": "delay"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data['success'] is True
        assert 'results' in data
        assert len(data['results']) == 1
        assert data['results'][0]['model_type'] == 'delay'
        assert data['results'][0]['samples'] > 0

    def test_train_seasonal_model(self, client, setup_test_data):
        """Test training seasonal model via API."""
        response = client.post(
            "/predict/train",
            json={"model_type": "seasonal"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data['success'] is True
        assert 'results' in data
        assert len(data['results']) == 1
        assert data['results'][0]['model_type'] == 'seasonal'

    def test_train_both_models(self, client, setup_test_data):
        """Test training both models via API."""
        response = client.post(
            "/predict/train",
            json={"model_type": "both"}
        )

        assert response.status_code == 200
        data = response.json()

        assert data['success'] is True
        assert len(data['results']) == 2

        model_types = [r['model_type'] for r in data['results']]
        assert 'delay' in model_types
        assert 'seasonal' in model_types

    def test_predict_delay(self, client, setup_test_data):
        """Test delay prediction via API."""
        # First train the model
        client.post("/predict/train", json={"model_type": "delay"})

        # Get address ID
        address = setup_test_data[0]

        # Make prediction
        response = client.post(
            "/predict",
            json={
                "prediction_type": "delay",
                "address_id": address.id
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data['prediction_type'] == 'delay'
        assert 'delay' in data
        assert data['delay']['success'] is True
        assert data['delay']['address_id'] == address.id
        assert 'delay_likely' in data['delay']
        assert 'delay_probability' in data['delay']
        assert 'confidence' in data['delay']

    def test_predict_seasonal(self, client, setup_test_data):
        """Test seasonal prediction via API."""
        # First train the model
        client.post("/predict/train", json={"model_type": "seasonal"})

        # Make prediction
        response = client.post(
            "/predict",
            json={
                "prediction_type": "seasonal",
                "weeks_ahead": 4
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data['prediction_type'] == 'seasonal'
        assert 'seasonal' in data
        assert data['seasonal']['success'] is True
        assert len(data['seasonal']['predictions']) == 4

        for pred in data['seasonal']['predictions']:
            assert 'week' in pred
            assert 'month' in pred
            assert 'date' in pred
            assert 'predicted_reports' in pred

    def test_predict_seasonal_custom_weeks(self, client, setup_test_data):
        """Test seasonal prediction with custom weeks ahead."""
        client.post("/predict/train", json={"model_type": "seasonal"})

        response = client.post(
            "/predict",
            json={
                "prediction_type": "seasonal",
                "weeks_ahead": 8
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data['seasonal']['predictions']) == 8

    def test_predict_delay_missing_address_id(self, client, setup_test_data):
        """Test delay prediction without address_id fails validation."""
        response = client.post(
            "/predict",
            json={
                "prediction_type": "delay"
            }
        )

        assert response.status_code == 422  # Validation error

    def test_predict_without_trained_model(self, client, setup_test_data):
        """Test prediction fails gracefully without trained model."""
        address = setup_test_data[0]

        response = client.post(
            "/predict",
            json={
                "prediction_type": "delay",
                "address_id": address.id
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data['delay']['success'] is False
        assert 'message' in data['delay']

    def test_get_model_info_empty(self, client):
        """Test getting model info when no models trained."""
        response = client.get("/predict/models")

        assert response.status_code == 200
        data = response.json()

        assert 'active_models' in data
        assert 'total_models' in data
        assert data['total_models'] == 0

    def test_get_model_info_with_models(self, client, setup_test_data):
        """Test getting model info after training."""
        # Train both models
        client.post("/predict/train", json={"model_type": "both"})

        response = client.get("/predict/models")

        assert response.status_code == 200
        data = response.json()

        assert data['total_models'] == 2
        assert len(data['active_models']) == 2

        for model in data['active_models']:
            assert 'model_type' in model
            assert 'version' in model
            assert 'training_samples' in model
            assert 'training_accuracy' in model
            assert 'features' in model
            assert 'created_at' in model

    def test_prediction_endpoint_in_health_check(self, client):
        """Test that prediction endpoints are listed in health check."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()

        assert "/predict" in data['endpoints']
        assert "/predict/train" in data['endpoints']

    def test_prediction_stability_across_requests(self, client, setup_test_data):
        """Test that predictions are stable across multiple requests."""
        # Train model
        client.post("/predict/train", json={"model_type": "delay"})

        address = setup_test_data[0]

        # Make multiple predictions
        predictions = []
        for _ in range(3):
            response = client.post(
                "/predict",
                json={
                    "prediction_type": "delay",
                    "address_id": address.id
                }
            )
            data = response.json()
            predictions.append(data['delay']['delay_probability'])

        # All predictions should be identical
        assert all(p == predictions[0] for p in predictions)

    def test_seasonal_prediction_bounds(self, client, setup_test_data):
        """Test seasonal predictions with boundary values."""
        client.post("/predict/train", json={"model_type": "seasonal"})

        # Test minimum weeks ahead
        response = client.post(
            "/predict",
            json={
                "prediction_type": "seasonal",
                "weeks_ahead": 1
            }
        )
        assert response.status_code == 200
        assert len(response.json()['seasonal']['predictions']) == 1

        # Test maximum weeks ahead
        response = client.post(
            "/predict",
            json={
                "prediction_type": "seasonal",
                "weeks_ahead": 12
            }
        )
        assert response.status_code == 200
        assert len(response.json()['seasonal']['predictions']) == 12

        # Test invalid value (too high)
        response = client.post(
            "/predict",
            json={
                "prediction_type": "seasonal",
                "weeks_ahead": 13
            }
        )
        assert response.status_code == 422  # Validation error

    def test_invalid_prediction_type(self, client):
        """Test that invalid prediction type is rejected."""
        response = client.post(
            "/predict",
            json={
                "prediction_type": "invalid_type",
                "address_id": 1
            }
        )

        assert response.status_code == 422  # Validation error

    def test_invalid_model_type_for_training(self, client):
        """Test that invalid model type for training is rejected."""
        response = client.post(
            "/predict/train",
            json={
                "model_type": "invalid_model"
            }
        )

        assert response.status_code == 422  # Validation error

    def test_prediction_response_time(self, client, setup_test_data):
        """Test that predictions complete in reasonable time."""
        import time

        # Train model
        client.post("/predict/train", json={"model_type": "delay"})

        address = setup_test_data[0]

        # Measure prediction time
        start = time.time()
        response = client.post(
            "/predict",
            json={
                "prediction_type": "delay",
                "address_id": address.id
            }
        )
        duration = time.time() - start

        assert response.status_code == 200
        # Prediction should complete within 2 seconds
        assert duration < 2.0

    def test_concurrent_predictions(self, client, setup_test_data):
        """Test that multiple concurrent predictions work correctly."""
        import concurrent.futures

        # Train model
        client.post("/predict/train", json={"model_type": "delay"})

        def make_prediction(address_id):
            response = client.post(
                "/predict",
                json={
                    "prediction_type": "delay",
                    "address_id": address_id
                }
            )
            return response.json()

        # Make concurrent predictions
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(make_prediction, addr.id)
                for addr in setup_test_data[:3]
            ]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed
        assert len(results) == 3
        for result in results:
            assert result['delay']['success'] is True
