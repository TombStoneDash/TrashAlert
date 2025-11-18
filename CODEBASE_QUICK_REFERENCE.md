# TrashAlert Codebase Quick Reference Guide

## Key Files for Prediction Module Development

### Core Application Files
| File | Purpose | Key Classes/Functions |
|------|---------|---------------------|
| `app/main.py` | FastAPI application & endpoints | `/report`, `/lookup`, `/interpret-address` |
| `app/models.py` | Database models | Address, CrowdReport, CrowdConsensus |
| `app/services.py` | Business logic | ConsensusService, LookupService, ReportService |
| `app/metrics.py` | Metrics collection | MetricsManager (for analytics) |
| `app/utils.py` | Utilities | normalize_address(), geocode_address() |
| `app/ai_service.py` | AI integration | AIAddressInterpreter (OpenAI/Anthropic) |

### Database & Data Access
| File | Purpose |
|------|---------|
| `app/database.py` | SQLAlchemy session management |
| `app/repositories.py` | Data access layer |
| `alembic/` | Database migrations |

### Configuration
| File | Purpose |
|------|---------|
| `config/cities.yaml` | Supported cities configuration |
| `.env` | Environment variables |
| `requirements.txt` | Python dependencies |

---

## Database Query Patterns for Prediction

### Get All Reports for an Address (for time series analysis)
```python
from sqlalchemy.orm import Session
from app.models import CrowdReport

def get_address_reports(db: Session, address_id: int):
    reports = db.query(CrowdReport)\
        .filter(CrowdReport.address_id == address_id)\
        .order_by(CrowdReport.created_at)\
        .all()
    return reports
```

### Get Consensus History (using updated_at)
```python
from app.models import CrowdConsensus
from datetime import timedelta

def get_recent_consensus_changes(db: Session, days: int = 30):
    cutoff = datetime.now() - timedelta(days=days)
    changes = db.query(CrowdConsensus)\
        .filter(CrowdConsensus.updated_at > cutoff)\
        .all()
    return changes
```

### Get City-Level Statistics
```python
from app.models import Address, CrowdReport, CrowdConsensus
from sqlalchemy import func

def get_city_stats(db: Session, city_name: str):
    addresses = db.query(Address).filter(Address.city_name == city_name).all()
    reports = db.query(CrowdReport).filter(
        CrowdReport.address_id.in_([a.id for a in addresses])
    ).count()
    consensus = db.query(CrowdConsensus).filter(
        CrowdConsensus.address_id.in_([a.id for a in addresses])
    ).count()
    return {
        "city": city_name,
        "addresses": len(addresses),
        "reports": reports,
        "consensus_entries": consensus
    }
```

### Get Agreement Ratio Trends
```python
def get_agreement_trends(db: Session, address_id: int, days: int = 90):
    cutoff = datetime.now() - timedelta(days=days)
    trends = db.query(
        CrowdConsensus.updated_at,
        CrowdConsensus.trash_agreement_ratio,
        CrowdConsensus.recycling_agreement_ratio,
        CrowdConsensus.green_agreement_ratio,
        CrowdConsensus.total_reports
    ).filter(
        CrowdConsensus.address_id == address_id,
        CrowdConsensus.updated_at > cutoff
    ).order_by(CrowdConsensus.updated_at).all()
    return trends
```

### Find Spam/Outliers
```python
from sqlalchemy import func

def get_reports_by_ip(db: Session, ip_address: str):
    # Find all reports from an IP address
    reports = db.query(CrowdReport)\
        .filter(CrowdReport.ip_address == ip_address)\
        .all()
    return len(reports)

def find_suspicious_users(db: Session, min_reports: int = 20):
    # Find IP addresses with excessive reports
    suspicious = db.query(
        CrowdReport.ip_address,
        func.count(CrowdReport.id).label('count')
    ).group_by(CrowdReport.ip_address)\
    .having(func.count(CrowdReport.id) > min_reports)\
    .all()
    return suspicious
```

---

## Data Available for Prediction Models

### Time Series Data
```python
# For each address:
- created_at timestamps on CrowdReport
- updated_at timestamps on CrowdConsensus
- agreement_ratio evolution
- total_reports progression
- is_verified status changes
```

### Categorical Data
```python
# Address features:
- city_name
- subdivision (implicit in coordinates)
- state
- zip_code

# Report features:
- collection type (trash/recycling/green)
- day of week (MON-SUN)
- user patterns (user_hash frequency)
```

### Aggregated Metrics
```python
# From request_metrics table:
- lookup frequency per address
- lookup patterns by city
- API usage trends
- response times

# From consensus:
- agreement ratios per collection type
- verification rate
- convergence speed (how fast consensus stabilizes)
```

---

## API Response Structure Reference

### /lookup Response
```python
{
    "matched_address": str,
    "city_id": str,  # e.g., "ca_san_diego"
    "city_name": str,
    "lat": float,
    "lon": float,
    "trash_day_of_week": str,  # "Monday", "Tuesday", etc.
    "recycling_day_of_week": str,
    "green_waste_day_of_week": str,
    "data_source": Literal["CROWD_VERIFIED", "OFFICIAL", "CROWD_UNVERIFIED", "UNKNOWN"],
    "consensus_reports_count": int,
    "consensus_agreement_ratio": float,  # 0.0-1.0
    "consensus_details": {
        "reports_count": int,
        "agreement_ratio": float
    }
}
```

### /report Response
```python
{
    "success": bool,
    "message": str,
    "address_id": int,
    "normalized_address": str,
    "consensus": {
        "trash_day": str,
        "recycling_day": str,
        "green_day": str,
        "reports_count": int,
        "trash_agreement_ratio": float,
        "recycling_agreement_ratio": float,
        "green_agreement_ratio": float,
        "is_verified": bool
    }
}
```

---

## Consensus Algorithm Reference

### Verification Thresholds (from app/services.py)
```python
MIN_REPORTS_FOR_VERIFICATION = 3
MIN_AGREEMENT_RATIO = 0.75  # 75%
```

### Consensus Calculation
```
1. For each day type (trash/recycling/green):
   a. Collect all reports for that type
   b. Find most common day (mode)
   c. Calculate agreement ratio = (count of most common) / (total reports)

2. Overall verification:
   - total_reports >= 3
   - average(agreement_ratios) >= 0.75
```

---

## City Configuration (config/cities.yaml)

### Supported Cities
- San Diego (ca_san_diego) - Has official pickup zones
- El Centro (ca_el_centro)
- Calexico (ca_calexico)
- Brawley (ca_brawley)
- Imperial (ca_imperial)
- Holtville (ca_holtville)
- Fresno (ca_fresno)
- Riverside (ca_riverside)
- Sacramento (ca_sacramento)
- Bakersfield (ca_bakersfield)

---

## Testing Utilities

### Add Test Data
```bash
python scripts/add_test_crowd_reports.py
```

### Run Tests
```bash
pytest tests/ -v
pytest tests/test_crowdsourcing.py -v  # Consensus tests
pytest tests/test_observability.py -v  # Metrics tests
```

### Inspect Database
```python
python scripts/database/inspect_schema.py
```

---

## Performance Considerations

### Indexes
```sql
-- Frequently queried columns are indexed:
- addresses.normalized_address
- crowd_reports.address_id
- crowd_reports.created_at
- crowd_consensus.address_id
- crowd_consensus.is_verified
- request_metrics.created_at
- request_metrics.endpoint
```

### Query Optimization Tips
1. Always filter by `address_id` when working with crowd_reports
2. Use composite indexes for (address_id, created_at) queries
3. Consider caching consensus queries (5-minute TTL in place)
4. Batch operations for historical analysis

---

## Common Development Tasks

### Add a New API Endpoint
1. Define schema in `app/schemas.py`
2. Add model if needed in `app/models.py`
3. Create service method in `app/services.py`
4. Add endpoint in `app/main.py`
5. Add metrics recording to endpoint
6. Add tests in `tests/`

### Add a Database Table
1. Create model in `app/models.py`
2. Create Alembic migration: `alembic revision -m "description"`
3. Write upgrade() and downgrade() functions
4. Run migration: `alembic upgrade head`

### Deploy Changes
```bash
docker-compose down
docker-compose up --build
```

---

## Prediction Module Integration Points

### Recommended Location
Create `app/prediction_service.py` with:
```python
class PredictionService:
    def __init__(self, db: Session):
        self.db = db
        self.report_repo = CrowdReportRepository(db)
        self.consensus_repo = CrowdConsensusRepository(db)
    
    def predict_schedule_change(self, address_id: int) -> ScheduleChangePrediction:
        # Use historical data to predict
        pass
    
    def predict_report_quality(self, report: CrowdReport) -> float:
        # Estimate reliability of report
        pass
    
    def predict_city_growth(self, city_name: str) -> CityGrowthPrediction:
        # Forecast report submission trends
        pass
```

### Add Prediction Endpoint
```python
@app.post("/predict-schedule-change")
async def predict_schedule_change(
    address_id: int,
    prediction_service: PredictionService = Depends()
) -> ScheduleChangePrediction:
    return prediction_service.predict_schedule_change(address_id)
```

### Export Data for External Analysis
```python
def export_for_analysis(db: Session, city_name: str):
    # Export crowd_reports + consensus for ML analysis
    addresses = db.query(Address).filter(Address.city_name == city_name).all()
    # Export to CSV or DataFrame
```

---

## Useful SQL Queries for Analysis

### Reports Per Address (sorted by count)
```sql
SELECT address_id, COUNT(*) as report_count
FROM crowd_reports
GROUP BY address_id
ORDER BY report_count DESC
LIMIT 20;
```

### Verification Rate by City
```sql
SELECT 
    a.city_name,
    COUNT(DISTINCT a.id) as total_addresses,
    COUNT(DISTINCT CASE WHEN cc.is_verified THEN cc.address_id END) as verified,
    ROUND(COUNT(DISTINCT CASE WHEN cc.is_verified THEN cc.address_id END) * 100.0 / 
        COUNT(DISTINCT a.id), 2) as verification_rate
FROM addresses a
LEFT JOIN crowd_consensus cc ON a.id = cc.address_id
GROUP BY a.city_name
ORDER BY verification_rate DESC;
```

### Agreement Ratio Distribution
```sql
SELECT 
    ROUND(AVG(trash_agreement_ratio), 2) as avg_trash_agreement,
    ROUND(AVG(recycling_agreement_ratio), 2) as avg_recycling_agreement,
    ROUND(AVG(green_agreement_ratio), 2) as avg_green_agreement
FROM crowd_consensus
WHERE is_verified = true;
```

### Most Active Users
```sql
SELECT user_hash, COUNT(*) as report_count
FROM crowd_reports
WHERE user_hash IS NOT NULL
GROUP BY user_hash
ORDER BY report_count DESC
LIMIT 20;
```

---

## Documentation Files to Review

1. **`docs/architecture.md`** - System design overview
2. **`docs/data_model.md`** - Detailed schema documentation
3. **`docs/crowdsourcing.md`** - Consensus algorithm details
4. **`PROGRESS_REPORT.md`** - Phase-by-phase development summary
5. **`README.md`** - User-facing documentation

