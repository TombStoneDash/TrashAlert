# TrashAlert API

A minimal HTTP API for looking up trash, recycling, and green waste pickup schedules by address.

## Overview

The TrashAlert API provides a simple interface to query trash pickup schedules for addresses in supported cities. It uses address normalization and fuzzy matching to find the closest match for a given address.

## Features

- **Address Normalization**: Handles variations in address format (St vs Street, Ave vs Avenue, etc.)
- **Fuzzy Matching**: Finds closest matches even with minor typos or variations
- **Confidence Scores**: Returns a confidence score (0-1) for each match
- **Multiple Cities**: Supports San Diego, El Centro, Calexico, Brawley, Imperial, and Holtville
- **Three Pickup Types**: Trash, recycling, and green waste schedules

## Quick Start

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Initialize the database (if not already done):
```bash
python scripts/init_database.py
```

### Running the API

Start the server:
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Or run directly:
```bash
python -m api.main
```

The API will be available at `http://localhost:8000`

## API Endpoints

### GET /health

Health check endpoint to verify the API and database are operational.

**Response:**
```json
{
  "status": "ok",
  "database": "connected",
  "total_addresses": 248,
  "total_cities": 6
}
```

### GET /lookup

Look up trash pickup schedule for an address.

**Query Parameters:**
- `address` (required): Full address string (e.g., "1245 Main St, El Centro, CA")

**Example Request:**
```bash
curl "http://localhost:8000/lookup?address=1245%20Main%20St,%20El%20Centro,%20CA"
```

**Success Response (200):**
```json
{
  "matched_address": "1245 Main St",
  "city": "El Centro",
  "trash_day_of_week": "Wednesday",
  "recycling_day_of_week": "Saturday",
  "green_waste_day_of_week": null,
  "confidence": 1.0
}
```

**Error Response (404):**
```json
{
  "detail": {
    "error": "Address not found",
    "detail": "No matching address found for '...' in .... Please verify the address and city name."
  }
}
```

## API Documentation

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Examples

### Exact Match
```bash
curl "http://localhost:8000/lookup?address=1245%20Main%20St,%20El%20Centro,%20CA"
```
Returns confidence: 1.0

### Fuzzy Match (Different Suffix)
```bash
curl "http://localhost:8000/lookup?address=1245%20Main%20Street,%20El%20Centro"
```
Returns confidence: 1.0 (normalized to "main st")

### Partial Match
```bash
curl "http://localhost:8000/lookup?address=1620%20Broadway,%20San%20Diego,%20CA"
```
May return a similar address with confidence < 1.0

### Health Check
```bash
curl "http://localhost:8000/health"
```

## Project Structure

```
api/
├── __init__.py          # Package initialization
├── main.py              # FastAPI application and endpoints
├── models.py            # Pydantic models for request/response
├── database.py          # Database query functions
├── normalization.py     # Address normalization utilities
└── README.md           # This file
```

## Database Schema

### addresses_normalized
Stores normalized address data from OSM.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| city_name | TEXT | City name |
| house_number | TEXT | House/building number |
| street | TEXT | Street name |
| normalized_address | TEXT | Normalized full address |
| lat | REAL | Latitude |
| lon | REAL | Longitude |
| osm_id | TEXT | OpenStreetMap ID |
| subdivision_id | TEXT | Subdivision/neighborhood |

### address_pickup_info
Stores pickup schedule information.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| address_id | INTEGER | Foreign key to addresses_normalized |
| trash_day_of_week | TEXT | Day for trash pickup |
| recycling_day_of_week | TEXT | Day for recycling pickup |
| green_waste_day_of_week | TEXT | Day for green waste pickup |

## Development

### Running Tests
```bash
pytest
```

### Adding New Cities

1. Add sample data to `data/addresses_sampled_50_per_city.csv`
2. Define pickup schedules in `scripts/init_database.py`
3. Re-run database initialization:
```bash
python scripts/init_database.py
```

## Future Enhancements

- [ ] Add geocoding support for better address parsing
- [ ] Implement caching for frequent lookups
- [ ] Add bulk lookup endpoint
- [ ] Support for more cities and counties
- [ ] Add holiday schedule adjustments
- [ ] User feedback mechanism for incorrect schedules
- [ ] Rate limiting and API keys

## License

MIT
