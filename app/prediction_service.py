"""Prediction service for pickup delays and seasonal patterns."""
import base64
import pickle
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import (
    CrowdReport, Address, CrowdConsensus, PredictionModel, PredictionCache
)

logger = logging.getLogger(__name__)


class PredictionService:
    """Service for training and using ML models to predict pickup patterns."""

    def __init__(self, db: Session):
        """Initialize prediction service with database session."""
        self.db = db
        self.delay_model: Optional[RandomForestClassifier] = None
        self.seasonal_model: Optional[RandomForestRegressor] = None
        self.day_encoder = LabelEncoder()
        self.day_encoder.fit(['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'])

    def _extract_features_from_address(self, address: Address, report_history: List[CrowdReport]) -> Dict[str, Any]:
        """
        Extract features from address and its report history.

        Features include:
        - Number of reports
        - Report velocity (reports per day)
        - Agreement ratios
        - Time-based features (day of week, week of year)
        - Geographic features (if available)
        """
        features = {}

        # Report count features
        features['total_reports'] = len(report_history)

        if report_history:
            # Time-based features
            oldest_report = min(report_history, key=lambda r: r.created_at)
            newest_report = max(report_history, key=lambda r: r.created_at)
            time_span_days = (newest_report.created_at - oldest_report.created_at).total_seconds() / 86400
            features['report_velocity'] = len(report_history) / max(time_span_days, 1)

            # Day distribution (how many reports per day of week)
            trash_days = [r.trash_day for r in report_history if r.trash_day]
            features['trash_day_variety'] = len(set(trash_days))

            # Recent activity (reports in last 30 days)
            thirty_days_ago = datetime.now() - timedelta(days=30)
            recent_reports = [r for r in report_history if r.created_at > thirty_days_ago]
            features['recent_reports'] = len(recent_reports)
        else:
            features['report_velocity'] = 0
            features['trash_day_variety'] = 0
            features['recent_reports'] = 0

        # Consensus features
        consensus = self.db.query(CrowdConsensus).filter(
            CrowdConsensus.address_id == address.id
        ).first()

        if consensus:
            features['trash_agreement_ratio'] = consensus.trash_agreement_ratio
            features['recycling_agreement_ratio'] = consensus.recycling_agreement_ratio
            features['green_agreement_ratio'] = consensus.green_agreement_ratio
            features['is_verified'] = 1 if consensus.is_verified else 0
        else:
            features['trash_agreement_ratio'] = 0
            features['recycling_agreement_ratio'] = 0
            features['green_agreement_ratio'] = 0
            features['is_verified'] = 0

        # Temporal features (current)
        now = datetime.now()
        features['week_of_year'] = now.isocalendar()[1]
        features['month'] = now.month
        features['day_of_week'] = now.weekday()

        return features

    def _prepare_delay_training_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare training data for delay prediction model.

        The delay model predicts likelihood of schedule delays based on:
        - Report patterns (conflicting reports = potential delays)
        - Agreement ratios
        - Report velocity
        """
        addresses = self.db.query(Address).all()
        features_list = []
        labels = []

        for address in addresses:
            # Get report history
            reports = self.db.query(CrowdReport).filter(
                CrowdReport.address_id == address.id
            ).order_by(CrowdReport.created_at).all()

            if len(reports) < 2:
                continue

            features = self._extract_features_from_address(address, reports)

            # Label: delay likelihood based on agreement ratios
            # Low agreement = high likelihood of delays/inconsistencies
            consensus = self.db.query(CrowdConsensus).filter(
                CrowdConsensus.address_id == address.id
            ).first()

            if consensus:
                avg_agreement = np.mean([
                    consensus.trash_agreement_ratio,
                    consensus.recycling_agreement_ratio,
                    consensus.green_agreement_ratio
                ])
                # Classify as "delay likely" if agreement < 0.7
                delay_label = 1 if avg_agreement < 0.7 else 0
            else:
                # No consensus = uncertain, skip
                continue

            features_list.append([
                features['total_reports'],
                features['report_velocity'],
                features['trash_day_variety'],
                features['recent_reports'],
                features['trash_agreement_ratio'],
                features['recycling_agreement_ratio'],
                features['green_agreement_ratio'],
                features['is_verified'],
                features['week_of_year'],
                features['month'],
                features['day_of_week']
            ])
            labels.append(delay_label)

        if not features_list:
            logger.warning("No training data available for delay model")
            return np.array([]), np.array([])

        return np.array(features_list), np.array(labels)

    def _prepare_seasonal_training_data(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare training data for seasonal pattern prediction.

        The seasonal model predicts report volume based on time of year.
        """
        # Get report counts by week
        weekly_data = self.db.query(
            func.extract('week', CrowdReport.created_at).label('week'),
            func.extract('month', CrowdReport.created_at).label('month'),
            func.count(CrowdReport.id).label('report_count')
        ).group_by('week', 'month').all()

        if not weekly_data:
            logger.warning("No training data available for seasonal model")
            return np.array([]), np.array([])

        features_list = []
        labels = []

        for week, month, count in weekly_data:
            features_list.append([
                int(week),
                int(month),
                int(week) % 4,  # Week of month (approximate)
            ])
            labels.append(count)

        return np.array(features_list), np.array(labels)

    def train_delay_model(self) -> Dict[str, Any]:
        """
        Train the pickup delay prediction model.

        Returns:
            Dict with training results and model metadata
        """
        logger.info("Training delay prediction model")

        X, y = self._prepare_delay_training_data()

        if len(X) == 0:
            logger.warning("Insufficient data to train delay model")
            return {
                'success': False,
                'message': 'Insufficient training data',
                'samples': 0
            }

        # Train Random Forest Classifier
        self.delay_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            min_samples_split=5,
            min_samples_leaf=2
        )
        self.delay_model.fit(X, y)

        # Calculate training accuracy
        accuracy = self.delay_model.score(X, y)

        # Save model to database
        model_data = pickle.dumps(self.delay_model)
        encoded_model = base64.b64encode(model_data).decode('utf-8')

        # Deactivate old models
        self.db.query(PredictionModel).filter(
            PredictionModel.model_type == 'delay',
            PredictionModel.is_active == True
        ).update({'is_active': False})

        # Save new model
        new_model = PredictionModel(
            model_type='delay',
            version='1.0.0',
            model_data=encoded_model,
            training_samples=len(X),
            training_accuracy=accuracy,
            training_features=[
                'total_reports', 'report_velocity', 'trash_day_variety',
                'recent_reports', 'trash_agreement_ratio', 'recycling_agreement_ratio',
                'green_agreement_ratio', 'is_verified', 'week_of_year', 'month', 'day_of_week'
            ],
            is_active=True
        )
        self.db.add(new_model)
        self.db.commit()

        logger.info(f"Delay model trained: {len(X)} samples, accuracy={accuracy:.3f}")

        return {
            'success': True,
            'model_type': 'delay',
            'version': '1.0.0',
            'samples': len(X),
            'accuracy': accuracy,
            'features': new_model.training_features
        }

    def train_seasonal_model(self) -> Dict[str, Any]:
        """
        Train the seasonal pattern prediction model.

        Returns:
            Dict with training results and model metadata
        """
        logger.info("Training seasonal pattern model")

        X, y = self._prepare_seasonal_training_data()

        if len(X) == 0:
            logger.warning("Insufficient data to train seasonal model")
            return {
                'success': False,
                'message': 'Insufficient training data',
                'samples': 0
            }

        # Train Random Forest Regressor
        self.seasonal_model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            min_samples_split=5,
            min_samples_leaf=2
        )
        self.seasonal_model.fit(X, y)

        # Calculate R² score
        r2_score = self.seasonal_model.score(X, y)

        # Save model to database
        model_data = pickle.dumps(self.seasonal_model)
        encoded_model = base64.b64encode(model_data).decode('utf-8')

        # Deactivate old models
        self.db.query(PredictionModel).filter(
            PredictionModel.model_type == 'seasonal',
            PredictionModel.is_active == True
        ).update({'is_active': False})

        # Save new model
        new_model = PredictionModel(
            model_type='seasonal',
            version='1.0.0',
            model_data=encoded_model,
            training_samples=len(X),
            training_accuracy=r2_score,
            training_features=['week_of_year', 'month', 'week_of_month'],
            is_active=True
        )
        self.db.add(new_model)
        self.db.commit()

        logger.info(f"Seasonal model trained: {len(X)} samples, R²={r2_score:.3f}")

        return {
            'success': True,
            'model_type': 'seasonal',
            'version': '1.0.0',
            'samples': len(X),
            'r2_score': r2_score,
            'features': new_model.training_features
        }

    def load_models(self) -> None:
        """Load active models from database."""
        # Load delay model
        delay_model_record = self.db.query(PredictionModel).filter(
            PredictionModel.model_type == 'delay',
            PredictionModel.is_active == True
        ).first()

        if delay_model_record:
            model_bytes = base64.b64decode(delay_model_record.model_data)
            self.delay_model = pickle.loads(model_bytes)
            logger.info(f"Loaded delay model v{delay_model_record.version}")

        # Load seasonal model
        seasonal_model_record = self.db.query(PredictionModel).filter(
            PredictionModel.model_type == 'seasonal',
            PredictionModel.is_active == True
        ).first()

        if seasonal_model_record:
            model_bytes = base64.b64decode(seasonal_model_record.model_data)
            self.seasonal_model = pickle.loads(model_bytes)
            logger.info(f"Loaded seasonal model v{seasonal_model_record.version}")

    def predict_delay(self, address_id: int) -> Dict[str, Any]:
        """
        Predict likelihood of pickup delays for an address.

        Args:
            address_id: Address ID to predict for

        Returns:
            Dict with prediction results
        """
        # Check cache first
        cache_entry = self.db.query(PredictionCache).filter(
            PredictionCache.address_id == address_id,
            PredictionCache.prediction_type == 'delay',
            PredictionCache.expires_at > datetime.now()
        ).first()

        if cache_entry:
            logger.info(f"Using cached delay prediction for address {address_id}")
            return cache_entry.prediction_result

        # Load model if not loaded
        if self.delay_model is None:
            self.load_models()

        if self.delay_model is None:
            return {
                'success': False,
                'message': 'Delay prediction model not trained yet'
            }

        # Get address and reports
        address = self.db.query(Address).filter(Address.id == address_id).first()
        if not address:
            return {
                'success': False,
                'message': 'Address not found'
            }

        reports = self.db.query(CrowdReport).filter(
            CrowdReport.address_id == address_id
        ).all()

        # Extract features
        features = self._extract_features_from_address(address, reports)
        feature_vector = np.array([[
            features['total_reports'],
            features['report_velocity'],
            features['trash_day_variety'],
            features['recent_reports'],
            features['trash_agreement_ratio'],
            features['recycling_agreement_ratio'],
            features['green_agreement_ratio'],
            features['is_verified'],
            features['week_of_year'],
            features['month'],
            features['day_of_week']
        ]])

        # Make prediction
        delay_probability = self.delay_model.predict_proba(feature_vector)[0]
        delay_likely = self.delay_model.predict(feature_vector)[0]

        # Handle case where model only learned one class
        if len(delay_probability) == 1:
            # Only one class in training data
            delay_prob = delay_probability[0] if delay_likely else 1 - delay_probability[0]
            confidence = delay_probability[0]
        else:
            # Normal case with both classes
            delay_prob = delay_probability[1]  # Probability of class 1 (delay)
            confidence = max(delay_probability)

        result = {
            'success': True,
            'address_id': address_id,
            'delay_likely': bool(delay_likely),
            'delay_probability': float(delay_prob),
            'confidence': float(confidence),
            'features_used': features
        }

        # Cache result for 24 hours
        cache_entry = PredictionCache(
            address_id=address_id,
            prediction_type='delay',
            prediction_result=result,
            confidence=result['confidence'],
            expires_at=datetime.now() + timedelta(hours=24)
        )
        self.db.add(cache_entry)
        self.db.commit()

        return result

    def predict_seasonal_volume(self, weeks_ahead: int = 4) -> Dict[str, Any]:
        """
        Predict report volume for upcoming weeks.

        Args:
            weeks_ahead: Number of weeks to predict ahead

        Returns:
            Dict with seasonal predictions
        """
        # Load model if not loaded
        if self.seasonal_model is None:
            self.load_models()

        if self.seasonal_model is None:
            return {
                'success': False,
                'message': 'Seasonal prediction model not trained yet'
            }

        predictions = []
        now = datetime.now()

        for week_offset in range(weeks_ahead):
            future_date = now + timedelta(weeks=week_offset)
            week_of_year = future_date.isocalendar()[1]
            month = future_date.month
            week_of_month = (future_date.day - 1) // 7 + 1

            feature_vector = np.array([[week_of_year, month, week_of_month]])
            predicted_volume = self.seasonal_model.predict(feature_vector)[0]

            predictions.append({
                'week': week_of_year,
                'month': month,
                'date': future_date.strftime('%Y-%m-%d'),
                'predicted_reports': int(max(0, predicted_volume))
            })

        return {
            'success': True,
            'predictions': predictions
        }

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about currently active models."""
        models = self.db.query(PredictionModel).filter(
            PredictionModel.is_active == True
        ).all()

        model_info = []
        for model in models:
            model_info.append({
                'model_type': model.model_type,
                'version': model.version,
                'training_samples': model.training_samples,
                'training_accuracy': model.training_accuracy,
                'features': model.training_features,
                'created_at': model.created_at.isoformat()
            })

        return {
            'active_models': model_info,
            'total_models': len(model_info)
        }
