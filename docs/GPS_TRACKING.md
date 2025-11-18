# GPS Truck Tracking System

This document describes the GPS tracking system added to TrashAlert for real-time truck location monitoring.

## Overview

The GPS tracking system enables real-time monitoring of trash collection trucks through:
- GPS location ingestion from trucks in the field
- Historical trail storage for route analysis
- Live map visualization in the admin dashboard
- Simulated GPS feed for testing

## Architecture

### Backend Components

#### 1. Database Models (`app/models.py`)

Three new models were added:

- **Truck**: Fleet information (truck number, license plate, city, status, vehicle type)
- **TruckLocation**: GPS location trails (coordinates, speed, heading, timestamp)
- **TruckRoute**: Daily route planning (route date, zone, status, stops)

#### 2. GPS Ingestor (`app/gps_ingestor.py`)

FastAPI router with endpoints:

- `POST /gps/truck-location` - Ingest GPS data from trucks
- `GET /gps/trucks` - Get all trucks with latest locations
- `GET /gps/trucks/{truck_id}/trail` - Get location history for a truck
- `GET /gps/trucks/{truck_id}/latest` - Get latest location for a truck

#### 3. Database Migration

Migration file: `alembic/versions/add_truck_tracking_tables.py`

Creates tables for trucks, truck_locations, and truck_routes with proper indexes for performance.

### Frontend Components

#### 1. TruckTracking Page (`frontend/admin-dashboard/src/pages/TruckTracking.jsx`)

Features:
- **Live Map**: Real-time visualization of truck positions using Leaflet
- **Fleet Status Panel**: List of all trucks with their current status
- **Auto-refresh**: Automatic updates every 10 seconds
- **Trail Visualization**: Show path history when truck is selected
- **Truck Details**: Speed, heading, last update time in popups

#### 2. Navigation Integration

- Added "Truck Tracking" menu item in sidebar
- Added route `/trucks` to router

## API Reference

### Ingest Truck Location

```http
POST /gps/truck-location
Content-Type: application/json

{
  "truck_id": 1,
  "lat": 37.7749,
  "lon": -122.4194,
  "speed_mph": 25.5,
  "heading_degrees": 180.0,
  "altitude_meters": 50.0,
  "accuracy_meters": 10.0,
  "timestamp": "2025-11-18T20:00:00Z"
}
```

### Get All Trucks with Locations

```http
GET /gps/trucks

Response:
[
  {
    "id": 1,
    "truck_number": "TEST-001",
    "license_plate": "CA-1234",
    "status": "active",
    "vehicle_type": "trash",
    "latest_location": {
      "id": 123,
      "truck_id": 1,
      "lat": 37.7749,
      "lon": -122.4194,
      "speed_mph": 25.5,
      "heading_degrees": 180.0,
      "timestamp": "2025-11-18T20:00:00Z",
      "created_at": "2025-11-18T20:00:01Z"
    }
  }
]
```

### Get Truck Trail

```http
GET /gps/trucks/{truck_id}/trail?limit=100

Response: Array of TruckLocation objects (most recent first)
```

## GPS Simulator

### Purpose

The GPS simulator (`scripts/gps_simulator.py`) generates realistic truck movement data for testing without real GPS hardware.

### Features

- Simulates multiple trucks (default: 3)
- Realistic movement patterns (speed variation, turning)
- Configurable update interval (default: 5 seconds)
- Creates test trucks automatically in database
- Sends data to API via HTTP

### Usage

```bash
# Ensure backend is running first
cd /home/user/TrashAlert

# Run the simulator
python scripts/gps_simulator.py
```

The simulator will:
1. Create test trucks in the database if they don't exist
2. Start simulating truck movements in San Francisco
3. Send GPS updates to the API every 5 seconds
4. Display progress in the console

Press `Ctrl+C` to stop the simulation.

### Configuration

Edit `scripts/gps_simulator.py` to customize:

```python
API_BASE_URL = "http://localhost:8000"  # API endpoint
UPDATE_INTERVAL = 5  # seconds between updates
NUM_TRUCKS = 3  # number of simulated trucks
```

## Testing the System

### Step 1: Run Database Migrations

```bash
cd /home/user/TrashAlert
docker-compose exec api alembic upgrade head
```

### Step 2: Start the Backend

```bash
docker-compose up -d
```

### Step 3: Start the Simulator

```bash
python scripts/gps_simulator.py
```

### Step 4: View in Dashboard

1. Open admin dashboard: http://localhost:5173
2. Navigate to "Truck Tracking" in the sidebar
3. Watch trucks move on the map in real-time
4. Click on trucks to see details and trails

## Database Schema

### trucks

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| truck_number | String | Unique truck identifier |
| license_plate | String | Vehicle license plate |
| city_id | Integer | Foreign key to cities |
| status | String | active, inactive, maintenance |
| vehicle_type | String | trash, recycling, green |
| capacity_cubic_yards | Float | Truck capacity |
| extra_metadata | JSON | Additional truck data |

### truck_locations

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| truck_id | Integer | Foreign key to trucks |
| lat | Float | Latitude |
| lon | Float | Longitude |
| speed_mph | Float | Speed in mph |
| heading_degrees | Float | Heading (0-360°) |
| altitude_meters | Float | Altitude |
| accuracy_meters | Float | GPS accuracy |
| timestamp | DateTime | GPS timestamp |

### truck_routes

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| truck_id | Integer | Foreign key to trucks |
| pickup_zone_id | Integer | Foreign key to pickup_zones |
| route_date | Date | Route date |
| route_type | String | trash, recycling, green |
| start_time | DateTime | Route start time |
| end_time | DateTime | Route end time |
| status | String | planned, in_progress, completed |
| total_stops | Integer | Total planned stops |
| completed_stops | Integer | Completed stops |

## Performance Considerations

### Indexes

The following indexes are created for optimal query performance:

- `truck_locations.truck_id` - Fast lookups by truck
- `truck_locations.timestamp` - Time-based queries
- `truck_locations(truck_id, timestamp)` - Combined index for trail queries

### Data Retention

Consider implementing:
- Data archival for old location records (e.g., >30 days)
- Periodic cleanup to maintain performance
- Aggregation of historical data

Example cleanup query:
```sql
DELETE FROM truck_locations
WHERE timestamp < NOW() - INTERVAL '30 days';
```

## Future Enhancements

Potential improvements:

1. **WebSocket Support**: Real-time push updates instead of polling
2. **Geofencing**: Alerts when trucks enter/exit zones
3. **Route Optimization**: Suggest optimal routes based on pickups
4. **Driver Mobile App**: GPS data from driver smartphones
5. **Analytics Dashboard**: Route efficiency, fuel usage, coverage analysis
6. **Historical Playback**: Replay past routes for analysis
7. **ETA Calculations**: Predict arrival times for customers

## Troubleshooting

### Trucks not appearing on map

- Check that trucks have `status = 'active'`
- Verify location data exists in `truck_locations` table
- Check browser console for API errors

### GPS simulator fails

- Ensure API is running on http://localhost:8000
- Check database connection
- Verify Python dependencies are installed

### Map not loading

- Check that Leaflet CSS is imported
- Verify OpenStreetMap tiles are accessible
- Check browser console for JavaScript errors

## API Integration for Real Trucks

To integrate with real GPS hardware:

```python
import requests
from datetime import datetime, timezone

def send_gps_update(truck_id, lat, lon, speed, heading):
    """Send GPS update from truck to TrashAlert API."""
    data = {
        "truck_id": truck_id,
        "lat": lat,
        "lon": lon,
        "speed_mph": speed,
        "heading_degrees": heading,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    response = requests.post(
        "http://api.trashalert.com/gps/truck-location",
        json=data
    )

    return response.status_code == 201
```

## Security Considerations

For production deployment:

1. **Authentication**: Add API key or JWT authentication for GPS endpoints
2. **Rate Limiting**: Prevent abuse of location ingestion
3. **HTTPS**: Use encrypted connections for GPS data
4. **Access Control**: Restrict who can view truck locations
5. **Data Privacy**: Comply with location tracking regulations

## License

This GPS tracking system is part of the TrashAlert project.
