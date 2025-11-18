"""Tests for prediction module."""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models import Address, CrowdReport, CrowdConsensus, PredictionModel, PredictionCache
from app.prediction_service import PredictionService


@pytest.fixture
def sample_addresses(db: Session):
    """Create sample addresses for testing."""
    addresses = []
    for i in range(10):
        addr = Address(
            normalized_address=f"123{i} Test St, San Diego, CA 92101",
            house_number=f"123{i}",
            street="Test St",
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
    return addresses


@pytest.fixture
def sample_reports(db: Session, sample_addresses):
    """Create sample crowd reports for testing."""
    reports = []
    base_date = datetime.now() - timedelta(days=90)

    for i, address in enumerate(sample_addresses):
        # Create varying numbers of reports per address
        num_reports = 3 + (i % 5)  # 3-7 reports per address

        for j in range(num_reports):
            # Most reports agree on Monday for trash
            trash_day = 'MON' if j < num_reports - 1 else 'TUE'

            report = CrowdReport(
                address_id=address.id,
                trash_day=trash_day,
                recycling_day='THU',
                green_day='WED',
                created_at=base_date + timedelta(days=j * 7)
            )
            db.add(report)
            reports.append(report)

    db.commit()
    return reports


@pytest.fixture
def sample_consensus(db: Session, sample_addresses):
    """Create sample consensus records."""
    consensus_records = []
    for i, address in enumerate(sample_addresses):
        # Vary agreement ratios
        agreement_ratio = 0.5 + (i * 0.05)  # 0.5 to 0.95

        consensus = CrowdConsensus(
            address_id=address.id,
            consensus_trash_day='MON',
            consensus_recycling_day='THU',
            consensus_green_day='WED',
            total_reports=3 + (i % 5),
            trash_agreement_ratio=agreement_ratio,
            recycling_agreement_ratio=0.8,
            green_agreement_ratio=0.75,
            is_verified=agreement_ratio >= 0.67
        )
        db.add(consensus)
        consensus_records.append(consensus)

    db.commit()
    return consensus_records


class TestPredictionService:
    """Test suite for PredictionService."""

    def test_initialization(self, db: Session):
        """Test service initialization."""
        service = PredictionService(db)
        assert service.db == db
        assert service.delay_model is None
        assert service.seasonal_model is None

    def test_extract_features(self, db: Session, sample_addresses, sample_reports, sample_consensus):
        """Test feature extraction from address data."""
        service = PredictionService(db)
        address = sample_addresses[0]
        reports = [r for r in sample_reports if r.address_id == address.id]

        features = service._extract_features_from_address(address, reports)

        assert 'total_reports' in features
        assert 'report_velocity' in features
        assert 'trash_day_variety' in features
        assert 'recent_reports' in features
        assert 'trash_agreement_ratio' in features
        assert 'is_verified' in features
        assert 'week_of_year' in features
        assert 'month' in features
        assert 'day_of_week' in features

        assert features['total_reports'] > 0
        assert features['report_velocity'] >= 0
        assert features['trash_agreement_ratio'] >= 0

    def test_train_delay_model(self, db: Session, sample_addresses, sample_reports, sample_consensus):
        """Test delay model training."""
        service = PredictionService(db)
        result = service.train_delay_model()

        assert result['success'] is True
        assert result['model_type'] == 'delay'
        assert result['samples'] > 0
        assert 'accuracy' in result
        assert result['accuracy'] >= 0

        # Verify model was saved to database
        saved_model = db.query(PredictionModel).filter(
            PredictionModel.model_type == 'delay',
            PredictionModel.is_active == True
        ).first()

        assert saved_model is not None
        assert saved_model.version == '1.0.0'
        assert saved_model.training_samples > 0
        assert saved_model.model_data is not None

    def test_train_seasonal_model(self, db: Session, sample_addresses, sample_reports):
        """Test seasonal model training."""
        service = PredictionService(db)
        result = service.train_seasonal_model()

        assert result['success'] is True
        assert result['model_type'] == 'seasonal'
        assert result['samples'] > 0
        assert 'r2_score' in result

        # Verify model was saved to database
        saved_model = db.query(PredictionModel).filter(
            PredictionModel.model_type == 'seasonal',
            PredictionModel.is_active == True
        ).first()

        assert saved_model is not None
        assert saved_model.version == '1.0.0'
        assert saved_model.training_samples > 0

    def test_load_models(self, db: Session, sample_addresses, sample_reports, sample_consensus):
        """Test loading models from database."""
        # First train models
        service1 = PredictionService(db)
        service1.train_delay_model()
        service1.train_seasonal_model()

        # Create new service instance and load models
        service2 = PredictionService(db)
        service2.load_models()

        assert service2.delay_model is not None
        assert service2.seasonal_model is not None

    def test_predict_delay(self, db: Session, sample_addresses, sample_reports, sample_consensus):
        """Test delay prediction for an address."""
        # Train model first
        service = PredictionService(db)
        service.train_delay_model()

        # Make prediction
        address = sample_addresses[0]
        result = service.predict_delay(address.id)

        assert result['success'] is True
        assert result['address_id'] == address.id
        assert 'delay_likely' in result
        assert 'delay_probability' in result
        assert 'confidence' in result
        assert isinstance(result['delay_likely'], bool)
        assert 0 <= result['delay_probability'] <= 1
        assert 0 <= result['confidence'] <= 1

    def test_predict_delay_stability(self, db: Session, sample_addresses, sample_reports, sample_consensus):
        """Test that delay predictions are stable across multiple calls."""
        service = PredictionService(db)
        service.train_delay_model()

        address = sample_addresses[0]

        # Make multiple predictions
        predictions = []
        for _ in range(5):
            result = service.predict_delay(address.id)
            predictions.append(result['delay_probability'])

        # All predictions should be identical (deterministic)
        assert all(p == predictions[0] for p in predictions)

    def test_predict_seasonal_volume(self, db: Session, sample_addresses, sample_reports):
        """Test seasonal volume prediction."""
        service = PredictionService(db)
        service.train_seasonal_model()

        result = service.predict_seasonal_volume(weeks_ahead=4)

        assert result['success'] is True
        assert 'predictions' in result
        assert len(result['predictions']) == 4

        for pred in result['predictions']:
            assert 'week' in pred
            assert 'month' in pred
            assert 'date' in pred
            assert 'predicted_reports' in pred
            assert pred['predicted_reports'] >= 0

    def test_predict_seasonal_stability(self, db: Session, sample_addresses, sample_reports):
        """Test that seasonal predictions are stable across multiple calls."""
        service = PredictionService(db)
        service.train_seasonal_model()

        # Make multiple predictions
        predictions = []
        for _ in range(3):
            result = service.predict_seasonal_volume(weeks_ahead=4)
            predictions.append(result['predictions'])

        # All predictions should be identical
        for i in range(len(predictions[0])):
            first_pred = predictions[0][i]['predicted_reports']
            assert all(
                p[i]['predicted_reports'] == first_pred
                for p in predictions
            )

    def test_prediction_caching(self, db: Session, sample_addresses, sample_reports, sample_consensus):
        """Test that predictions are cached properly."""
        service = PredictionService(db)
        service.train_delay_model()

        address = sample_addresses[0]

        # First prediction should create cache entry
        result1 = service.predict_delay(address.id)

        # Check cache was created
        cache_entry = db.query(PredictionCache).filter(
            PredictionCache.address_id == address.id,
            PredictionCache.prediction_type == 'delay'
        ).first()

        assert cache_entry is not None
        assert cache_entry.confidence == result1['confidence']

        # Second prediction should use cache
        result2 = service.predict_delay(address.id)
        assert result2 == result1

    def test_get_model_info(self, db: Session, sample_addresses, sample_reports, sample_consensus):
        """Test getting model information."""
        service = PredictionService(db)
        service.train_delay_model()
        service.train_seasonal_model()

        info = service.get_model_info()

        assert 'active_models' in info
        assert 'total_models' in info
        assert info['total_models'] == 2

        model_types = [m['model_type'] for m in info['active_models']]
        assert 'delay' in model_types
        assert 'seasonal' in model_types

    def test_insufficient_data_handling(self, db: Session):
        """Test model training with insufficient data."""
        # Create minimal data
        address = Address(
            normalized_address="123 Empty St, San Diego, CA 92101",
            city_slug="san_diego",
            city_name="San Diego",
            state="CA"
        )
        db.add(address)
        db.commit()

        service = PredictionService(db)

        # Should handle gracefully
        result = service.train_delay_model()
        assert result['success'] is False
        assert 'message' in result

    def test_prediction_without_trained_model(self, db: Session, sample_addresses):
        """Test prediction when no model is trained."""
        service = PredictionService(db)
        address = sample_addresses[0]

        result = service.predict_delay(address.id)
        assert result['success'] is False
        assert 'message' in result

    def test_model_version_management(self, db: Session, sample_addresses, sample_reports, sample_consensus):
        """Test that training new model deactivates old one."""
        service = PredictionService(db)

        # Train first model
        service.train_delay_model()

        first_model = db.query(PredictionModel).filter(
            PredictionModel.model_type == 'delay',
            PredictionModel.is_active == True
        ).first()
        first_model_id = first_model.id

        # Train second model
        service.train_delay_model()

        # Old model should be inactive
        old_model = db.query(PredictionModel).filter(
            PredictionModel.id == first_model_id
        ).first()
        assert old_model.is_active is False

        # New model should be active
        active_models = db.query(PredictionModel).filter(
            PredictionModel.model_type == 'delay',
            PredictionModel.is_active == True
        ).all()
        assert len(active_models) == 1

    def test_prediction_confidence_bounds(self, db: Session, sample_addresses, sample_reports, sample_consensus):
        """Test that prediction confidence values are within valid bounds."""
        service = PredictionService(db)
        service.train_delay_model()

        for address in sample_addresses:
            result = service.predict_delay(address.id)
            if result['success']:
                assert 0 <= result['confidence'] <= 1
                assert 0 <= result['delay_probability'] <= 1

    def test_seasonal_predictions_chronological(self, db: Session, sample_addresses, sample_reports):
        """Test that seasonal predictions are in chronological order."""
        service = PredictionService(db)
        service.train_seasonal_model()

        result = service.predict_seasonal_volume(weeks_ahead=4)

        predictions = result['predictions']
        dates = [datetime.strptime(p['date'], '%Y-%m-%d') for p in predictions]

        # Dates should be in ascending order
        for i in range(len(dates) - 1):
            assert dates[i] < dates[i + 1]
