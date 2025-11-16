# TrashAlert API

A FastAPI-based service for managing trash pickup schedules with crowdsourced data.

## Features

- **POST /report**: Submit crowdsourced trash pickup reports
- **GET /lookup**: Look up trash pickup schedules for an address
- **Consensus Algorithm**: Automatically verifies crowdsourced data when ≥3 reports with ≥67% agreement
- **Multi-source Data**: Merges crowdsourced and official data with intelligent prioritization

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Initialize Database

```bash
python init_db.py
```

This creates a SQLite database with sample addresses.

### 3. Start the API Server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### 4. Run Tests

In a new terminal:

```bash
python test_api.py
```

## API Endpoints

### POST /report

Submit a crowdsourced trash pickup report.

**Request:**
```json
{
  "address": "1122 Palmview Ave, El Centro, CA",
  "trash_day": "WED",
  "recycling_day": "FRI",
  "green_day": null,
  "user_hash": "optional-stable-id"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Report submitted successfully",
  "address_id": 1,
  "normalized_address": "1122 PALMVIEW AVE, EL CENTRO, CA",
  "consensus": {
    "trash_day": "WED",
    "recycling_day": "FRI",
    "green_day": null,
    "reports_count": 3,
    "trash_agreement_ratio": 1.0,
    "recycling_agreement_ratio": 1.0,
    "green_agreement_ratio": 0.0,
    "is_verified": true
  }
}
```

### GET /lookup

Look up trash pickup schedule for an address.

**Request:**
```
GET /lookup?address=1122 Palmview Ave, El Centro, CA
```

**Response:**
```json
{
  "address": "1122 Palmview Ave, El Centro, CA",
  "normalized_address": "1122 PALMVIEW AVE, EL CENTRO, CA",
  "trash_day": "WED",
  "recycling_day": "FRI",
  "green_day": null,
  "source": "CROWD_VERIFIED",
  "consensus_reports_count": 3,
  "consensus_agreement_ratio": 1.0,
  "lat": 32.792,
  "lon": -115.563
}
```

**Source Priority:**
1. `CROWD_VERIFIED` - Crowdsourced data with ≥3 reports and ≥67% agreement
2. `OFFICIAL` - Official GIS/government data
3. `UNKNOWN` - No data available

### GET /stats

Get database statistics.

**Response:**
```json
{
  "total_addresses": 3,
  "total_reports": 10,
  "total_consensus": 2,
  "verified_consensus": 2
}
```

## Data Model

### Address
- Stores normalized addresses with coordinates
- Contains official pickup schedules (from GIS/rules)

### CrowdReport
- Individual user-submitted reports
- Tracks user_hash to prevent spam

### CrowdConsensus
- Aggregated consensus from multiple reports
- Automatically calculated and verified
- Verification requires:
  - At least 3 reports
  - At least 67% agreement ratio

## Consensus Algorithm

The consensus algorithm:

1. Aggregates all reports for an address
2. Finds the most common value for each pickup day type
3. Calculates agreement ratios (% of reports agreeing with consensus)
4. Marks as verified if:
   - Total reports ≥ 3
   - Average agreement ratio ≥ 0.67

## Example Usage

### Submit Reports

```bash
# Report 1
curl -X POST http://localhost:8000/report \
  -H "Content-Type: application/json" \
  -d '{
    "address": "1122 Palmview Ave, El Centro, CA",
    "trash_day": "WED",
    "recycling_day": "FRI",
    "user_hash": "user_001"
  }'

# Report 2
curl -X POST http://localhost:8000/report \
  -H "Content-Type: application/json" \
  -d '{
    "address": "1122 Palmview Ave, El Centro, CA",
    "trash_day": "WED",
    "recycling_day": "FRI",
    "user_hash": "user_002"
  }'

# Report 3 (reaches verification threshold)
curl -X POST http://localhost:8000/report \
  -H "Content-Type: application/json" \
  -d '{
    "address": "1122 Palmview Ave, El Centro, CA",
    "trash_day": "WED",
    "recycling_day": "FRI",
    "user_hash": "user_003"
  }'
```

### Lookup Address

```bash
curl "http://localhost:8000/lookup?address=1122%20Palmview%20Ave,%20El%20Centro,%20CA"
```

## Project Structure

```
TrashAlert/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI application
│   ├── models.py        # Database models
│   ├── schemas.py       # Pydantic schemas
│   ├── database.py      # Database connection
│   └── utils.py         # Utility functions
├── init_db.py           # Database initialization
├── test_api.py          # Test/demo script
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

## Development

### Interactive API Documentation

FastAPI provides automatic interactive documentation:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Database

The application uses SQLite by default (`trashalert.db`). To use PostgreSQL or another database, modify `app/database.py`.

## License

MIT
