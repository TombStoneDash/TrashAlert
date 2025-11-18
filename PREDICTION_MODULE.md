# Prediction Module

This module provides machine learning capabilities for predicting pickup delays and seasonal patterns based on crowdsourced data.

## Features

### 1. Pickup Delay Prediction
Predicts the likelihood of pickup schedule delays or inconsistencies for a specific address based on:
- Report patterns (number of reports, velocity)
- Agreement ratios from consensus data
- Day variety (conflicting reports)
- Recent activity

**Model**: Random Forest Classifier
**Output**: Binary prediction (delay likely or not) with probability and confidence scores

### 2. Seasonal Pattern Prediction
Predicts report volume patterns for upcoming weeks based on historical temporal trends:
- Week of year
- Month
- Week of month

**Model**: Random Forest Regressor
**Output**: Predicted number of reports for future weeks

## API Endpoints

### POST /predict
Make predictions about pickup patterns.

**Request Body**:
```json
{
  "prediction_type": "delay",  // or "seasonal"
  "address_id": 123,            // required for delay predictions
  "weeks_ahead": 4              // optional for seasonal (default: 4, max: 12)
}
```

**Response** (delay prediction):
```json
{
  "prediction_type": "delay",
  "delay": {
    "success": true,
    "address_id": 123,
    "delay_likely": false,
    "delay_probability": 0.25,
    "confidence": 0.75
  }
}
```

**Response** (seasonal prediction):
```json
{
  "prediction_type": "seasonal",
  "seasonal": {
    "success": true,
    "predictions": [
      {
        "week": 47,
        "month": 11,
        "date": "2025-11-18",
        "predicted_reports": 45
      },
      // ... more weeks
    ]
  }
}
```

### POST /predict/train
Train prediction models on current crowdsourced data.

**Request Body**:
```json
{
  "model_type": "both"  // "delay", "seasonal", or "both"
}
```

**Response**:
```json
{
  "success": true,
  "results": [
    {
      "success": true,
      "model_type": "delay",
      "version": "1.0.0",
      "samples": 150,
      "accuracy": 0.85,
      "features": ["total_reports", "report_velocity", ...]
    },
    {
      "success": true,
      "model_type": "seasonal",
      "version": "1.0.0",
      "samples": 48,
      "r2_score": 0.72,
      "features": ["week_of_year", "month", "week_of_month"]
    }
  ],
  "message": "Models trained successfully"
}
```

### GET /predict/models
Get information about currently active models.

**Response**:
```json
{
  "active_models": [
    {
      "model_type": "delay",
      "version": "1.0.0",
      "training_samples": 150,
      "training_accuracy": 0.85,
      "features": ["total_reports", "report_velocity", ...],
      "created_at": "2025-11-18T10:00:00Z"
    },
    {
      "model_type": "seasonal",
      "version": "1.0.0",
      "training_samples": 48,
      "training_accuracy": 0.72,
      "features": ["week_of_year", "month", "week_of_month"],
      "created_at": "2025-11-18T10:00:00Z"
    }
  ],
  "total_models": 2
}
```

## Database Schema

### prediction_models
Stores trained ML models and their metadata.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| model_type | String | 'delay' or 'seasonal' |
| version | String | Semantic version |
| model_data | Text | Base64-encoded pickled model |
| training_samples | Integer | Number of samples used for training |
| training_accuracy | Float | Model accuracy/R² score |
| training_features | JSON | List of features used |
| is_active | Boolean | Only one active model per type |
| created_at | DateTime | Creation timestamp |
| updated_at | DateTime | Last update timestamp |

### prediction_cache
Caches prediction results to avoid recomputation.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| address_id | Integer | Foreign key to addresses |
| prediction_type | String | 'delay' or 'seasonal' |
| prediction_result | JSON | Cached prediction data |
| confidence | Float | Prediction confidence |
| model_version | String | Version of model used |
| expires_at | DateTime | Cache expiration time |
| created_at | DateTime | Creation timestamp |

## Model Training

### When to Train
- Initial setup: Train models after accumulating sufficient data (recommended: 50+ addresses with reports)
- Regular updates: Retrain weekly or monthly to incorporate new crowdsourced data
- After data quality improvements: Retrain when consensus data is cleaned or improved

### Training Requirements
- **Delay Model**: Requires addresses with multiple reports and consensus data
- **Seasonal Model**: Requires historical report data spanning multiple weeks

### Example Training Workflow
```bash
# Train both models
curl -X POST http://localhost:8000/predict/train \
  -H "Content-Type: application/json" \
  -d '{"model_type": "both"}'

# Check model info
curl http://localhost:8000/predict/models
```

## Features Used

### Delay Prediction Features
1. `total_reports` - Total number of reports for address
2. `report_velocity` - Reports per day (activity rate)
3. `trash_day_variety` - Number of unique trash days reported
4. `recent_reports` - Reports in last 30 days
5. `trash_agreement_ratio` - Consensus agreement for trash day
6. `recycling_agreement_ratio` - Consensus agreement for recycling
7. `green_agreement_ratio` - Consensus agreement for green waste
8. `is_verified` - Whether consensus is verified (≥3 reports, ≥67% agreement)
9. `week_of_year` - Current week of year
10. `month` - Current month
11. `day_of_week` - Current day of week

### Seasonal Prediction Features
1. `week_of_year` - Week number (1-52)
2. `month` - Month number (1-12)
3. `week_of_month` - Week within month (1-4)

## Caching

Predictions are automatically cached to improve performance:
- **Delay predictions**: Cached for 24 hours per address
- **Cache invalidation**: Automatic via `expires_at` timestamp
- **Cache hits**: Subsequent requests for same address return cached results

## Model Versioning

- Each training session creates a new model with version 1.0.0
- Previous models are automatically deactivated (`is_active = False`)
- Only one active model per type at a time
- Model history is preserved in database for auditing

## Testing

### Validation Script
Run the validation script to verify model stability:

```bash
python validate_prediction_module.py
```

Tests include:
- Model training with sample data
- Prediction stability (deterministic results)
- Confidence bounds validation (0-1 range)
- Model persistence (save/load)
- Seasonal prediction chronology
- Concurrent prediction handling

### Unit Tests
```bash
pytest tests/test_prediction.py -v
```

### Integration Tests
```bash
pytest tests/test_prediction_api.py -v
```

## Example Usage

### Python Client Example
```python
import requests

# Train models
response = requests.post(
    'http://localhost:8000/predict/train',
    json={'model_type': 'both'}
)
print(response.json())

# Get delay prediction
response = requests.post(
    'http://localhost:8000/predict',
    json={
        'prediction_type': 'delay',
        'address_id': 123
    }
)
result = response.json()
if result['delay']['success']:
    print(f"Delay likely: {result['delay']['delay_likely']}")
    print(f"Probability: {result['delay']['delay_probability']:.2%}")

# Get seasonal predictions
response = requests.post(
    'http://localhost:8000/predict',
    json={
        'prediction_type': 'seasonal',
        'weeks_ahead': 8
    }
)
predictions = response.json()['seasonal']['predictions']
for pred in predictions:
    print(f"{pred['date']}: {pred['predicted_reports']} reports")
```

## Performance

### Model Size
- Delay model: ~50-100 KB (depends on training samples)
- Seasonal model: ~30-50 KB
- Models are compressed with pickle and base64-encoded

### Prediction Time
- Delay prediction: <100ms (first call), <10ms (cached)
- Seasonal prediction: <50ms
- Training time: 1-5 seconds (depends on data size)

### Scalability
- Models stored in database (no memory overhead until loaded)
- Lazy loading: Models loaded on first prediction request
- Cache reduces database queries for repeated predictions

## Dependencies

```
scikit-learn>=1.3.0
numpy>=1.24.0
joblib>=1.3.0
```

## Future Enhancements

Potential improvements for future versions:
1. Multi-class delay severity prediction (minor/moderate/severe)
2. Holiday-aware seasonal predictions
3. City-specific models for better accuracy
4. Feature importance analysis and visualization
5. A/B testing framework for model comparison
6. Automated retraining schedule
7. Model performance monitoring and alerts
8. Additional features (weather, demographics, etc.)

## Troubleshooting

### Model Training Fails
- **Insufficient data**: Ensure you have at least 10-20 addresses with reports
- **No consensus data**: Run consensus calculation before training delay model
- **Database connection**: Verify database is accessible

### Predictions Always Return Same Value
- **Single class in training**: If all training samples have same label, model only learns one class
  - Solution: Ensure training data has diverse examples
- **Not enough features**: Add more addresses with varying characteristics

### Low Model Accuracy
- **Seasonal model**: R² score < 0.5 is common with limited data
  - Solution: Collect more historical data over time
- **Delay model**: Accuracy < 0.6 indicates need for more training data
  - Solution: Encourage more user reports to improve consensus

### Cache Not Working
- Check `prediction_cache` table for entries
- Verify `expires_at` is in the future
- Cache is per-address for delay predictions
