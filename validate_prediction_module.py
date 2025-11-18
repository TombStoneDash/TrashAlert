#!/usr/bin/env python3
"""Validation script for prediction module."""
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Address, CrowdReport, CrowdConsensus
from app.prediction_service import PredictionService


def setup_test_database():
    """Create in-memory test database with sample data."""
    engine = create_engine('sqlite:///:memory:', echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    return db, engine


def create_sample_data(db):
    """Create sample data for testing."""
    print("Creating sample data...")

    # Create addresses
    addresses = []
    for i in range(20):
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

    # Create reports
    base_date = datetime.now() - timedelta(days=90)
    for i, address in enumerate(addresses):
        num_reports = 5 + (i % 3)
        for j in range(num_reports):
            # Most agree on Monday, some on Tuesday
            trash_day = 'MON' if j < num_reports - 1 else 'TUE'
            report = CrowdReport(
                address_id=address.id,
                trash_day=trash_day,
                recycling_day='THU',
                green_day='WED',
                created_at=base_date + timedelta(days=j * 10)
            )
            db.add(report)
    db.commit()

    # Create consensus
    for i, address in enumerate(addresses):
        agreement_ratio = 0.6 + (i * 0.02)
        consensus = CrowdConsensus(
            address_id=address.id,
            consensus_trash_day='MON',
            consensus_recycling_day='THU',
            consensus_green_day='WED',
            total_reports=5 + (i % 3),
            trash_agreement_ratio=min(agreement_ratio, 0.95),
            recycling_agreement_ratio=0.85,
            green_agreement_ratio=0.80,
            is_verified=agreement_ratio >= 0.67
        )
        db.add(consensus)
    db.commit()

    print(f"Created {len(addresses)} addresses with reports and consensus")
    return addresses


def test_delay_model(db, addresses):
    """Test delay prediction model."""
    print("\n" + "="*60)
    print("TESTING DELAY PREDICTION MODEL")
    print("="*60)

    service = PredictionService(db)

    # Train model
    print("\nTraining delay model...")
    result = service.train_delay_model()

    if not result['success']:
        print(f"❌ Training failed: {result.get('message', 'Unknown error')}")
        return False

    print(f"✓ Model trained successfully")
    print(f"  - Samples: {result['samples']}")
    print(f"  - Accuracy: {result['accuracy']:.3f}")
    print(f"  - Features: {len(result['features'])}")

    # Test predictions
    print("\nTesting predictions...")
    test_addresses = addresses[:5]

    predictions = []
    for addr in test_addresses:
        pred = service.predict_delay(addr.id)
        predictions.append(pred)

        if not pred['success']:
            print(f"❌ Prediction failed for address {addr.id}")
            return False

        print(f"  Address {addr.id}:")
        print(f"    Delay likely: {pred['delay_likely']}")
        print(f"    Probability: {pred['delay_probability']:.3f}")
        print(f"    Confidence: {pred['confidence']:.3f}")

    # Test stability
    print("\nTesting prediction stability...")
    addr = addresses[0]
    pred1 = service.predict_delay(addr.id)
    pred2 = service.predict_delay(addr.id)
    pred3 = service.predict_delay(addr.id)

    if pred1['delay_probability'] == pred2['delay_probability'] == pred3['delay_probability']:
        print("✓ Predictions are stable (deterministic)")
    else:
        print("❌ Predictions are not stable!")
        return False

    # Test confidence bounds
    print("\nTesting confidence bounds...")
    all_valid = True
    for pred in predictions:
        if not (0 <= pred['confidence'] <= 1):
            print(f"❌ Invalid confidence: {pred['confidence']}")
            all_valid = False
        if not (0 <= pred['delay_probability'] <= 1):
            print(f"❌ Invalid probability: {pred['delay_probability']}")
            all_valid = False

    if all_valid:
        print("✓ All confidence values within valid bounds [0, 1]")

    return all_valid


def test_seasonal_model(db):
    """Test seasonal prediction model."""
    print("\n" + "="*60)
    print("TESTING SEASONAL PREDICTION MODEL")
    print("="*60)

    service = PredictionService(db)

    # Train model
    print("\nTraining seasonal model...")
    result = service.train_seasonal_model()

    if not result['success']:
        print(f"❌ Training failed: {result.get('message', 'Unknown error')}")
        return False

    print(f"✓ Model trained successfully")
    print(f"  - Samples: {result['samples']}")
    print(f"  - R² score: {result['r2_score']:.3f}")

    # Test predictions
    print("\nTesting seasonal predictions...")
    pred_result = service.predict_seasonal_volume(weeks_ahead=4)

    if not pred_result['success']:
        print("❌ Prediction failed")
        return False

    predictions = pred_result['predictions']
    print(f"✓ Generated {len(predictions)} weekly predictions")

    for i, pred in enumerate(predictions):
        print(f"  Week {i+1}: {pred['date']}")
        print(f"    Predicted reports: {pred['predicted_reports']}")
        print(f"    Week of year: {pred['week']}, Month: {pred['month']}")

    # Test stability
    print("\nTesting prediction stability...")
    pred1 = service.predict_seasonal_volume(weeks_ahead=4)
    pred2 = service.predict_seasonal_volume(weeks_ahead=4)

    stable = all(
        pred1['predictions'][i]['predicted_reports'] == pred2['predictions'][i]['predicted_reports']
        for i in range(len(pred1['predictions']))
    )

    if stable:
        print("✓ Predictions are stable (deterministic)")
    else:
        print("❌ Predictions are not stable!")
        return False

    # Test chronological order
    print("\nTesting chronological order...")
    dates = [datetime.strptime(p['date'], '%Y-%m-%d') for p in predictions]
    chronological = all(dates[i] < dates[i+1] for i in range(len(dates)-1))

    if chronological:
        print("✓ Predictions are in chronological order")
    else:
        print("❌ Predictions are not in chronological order!")
        return False

    return True


def test_model_persistence(db, addresses):
    """Test model loading from database."""
    print("\n" + "="*60)
    print("TESTING MODEL PERSISTENCE")
    print("="*60)

    # Train models with first service
    print("\nTraining models with first service...")
    service1 = PredictionService(db)
    service1.train_delay_model()
    service1.train_seasonal_model()

    # Create new service and load models
    print("Loading models with second service...")
    service2 = PredictionService(db)
    service2.load_models()

    if service2.delay_model is None:
        print("❌ Failed to load delay model")
        return False

    if service2.seasonal_model is None:
        print("❌ Failed to load seasonal model")
        return False

    print("✓ Models loaded successfully")

    # Test that loaded model works
    print("\nTesting loaded model predictions...")
    addr = addresses[0]
    pred = service2.predict_delay(addr.id)

    if pred['success']:
        print("✓ Loaded model produces predictions")
        return True
    else:
        print("❌ Loaded model failed to predict")
        return False


def test_model_info(db):
    """Test model information retrieval."""
    print("\n" + "="*60)
    print("TESTING MODEL INFO RETRIEVAL")
    print("="*60)

    service = PredictionService(db)
    service.train_delay_model()
    service.train_seasonal_model()

    info = service.get_model_info()

    print(f"\nActive models: {info['total_models']}")

    for model in info['active_models']:
        print(f"\nModel: {model['model_type']}")
        print(f"  Version: {model['version']}")
        print(f"  Samples: {model['training_samples']}")
        print(f"  Accuracy: {model['training_accuracy']:.3f}")
        print(f"  Features: {', '.join(model['features'][:3])}...")

    if info['total_models'] == 2:
        print("\n✓ Model info retrieved successfully")
        return True
    else:
        print(f"\n❌ Expected 2 models, found {info['total_models']}")
        return False


def main():
    """Run all validation tests."""
    print("="*60)
    print("PREDICTION MODULE VALIDATION")
    print("="*60)

    try:
        # Setup
        db, engine = setup_test_database()
        addresses = create_sample_data(db)

        # Run tests
        tests = [
            ("Delay Model", lambda: test_delay_model(db, addresses)),
            ("Seasonal Model", lambda: test_seasonal_model(db)),
            ("Model Persistence", lambda: test_model_persistence(db, addresses)),
            ("Model Info", lambda: test_model_info(db))
        ]

        results = {}
        for test_name, test_func in tests:
            try:
                results[test_name] = test_func()
            except Exception as e:
                print(f"\n❌ {test_name} raised exception: {e}")
                import traceback
                traceback.print_exc()
                results[test_name] = False

        # Summary
        print("\n" + "="*60)
        print("VALIDATION SUMMARY")
        print("="*60)

        for test_name, passed in results.items():
            status = "✓ PASSED" if passed else "❌ FAILED"
            print(f"{test_name:.<40} {status}")

        all_passed = all(results.values())
        print("="*60)

        if all_passed:
            print("✓ ALL TESTS PASSED - Prediction module is stable!")
            return 0
        else:
            print("❌ SOME TESTS FAILED - Please review errors above")
            return 1

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
