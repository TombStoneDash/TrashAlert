# TrashAlert Codebase: Comprehensive Overview

## Table of Contents
1. [Project Summary](#project-summary)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Database Architecture](#database-architecture)
5. [API Endpoints](#api-endpoints)
6. [Data Flow](#data-flow)
7. [Data Models & Relationships](#data-models--relationships)
8. [Existing Analytics & Metrics](#existing-analytics--metrics)
9. [Data Collection Pipeline](#data-collection-pipeline)
10. [Key Features for Prediction Module](#key-features-for-prediction-module)

---

## Project Summary

TrashAlert is a **crowdsourced trash pickup schedule lookup system** for California cities. It combines:
- **Official municipal data** from city GIS systems and websites
- **Crowdsourced community reports** from users who observe actual pickups
- **Smart consensus algorithms** to verify accuracy through community agreement

### Current Scope
- **Pilot cities**: San Diego, El Centro, Calexico, Brawley, Imperial, Holtville
- **Data types**: Trash, Recycling, and Green Waste collection days
- **Verification method**: Consensus algorithm requiring ≥3 reports with ≥75% agreement

### Project Phase
Currently in **Phase 5: Advanced Features and Expansion**, with recent additions including:
- Address interpretation using AI (OpenAI/Anthropic)
- Enhanced metrics collection
- Admin dashboard (React)
- Comprehensive logging and observability

---

## Technology Stack

### Backend
| Component | Technology | Version |
|-----------|-----------|---------|
| **Framework** | FastAPI | 0.109.0 |
| **Server** | Uvicorn | 0.27.0 |
| **Database** | PostgreSQL (primary) / SQLite (dev) | 14+ |
| **ORM** | SQLAlchemy | 2.0.25 |
| **Migrations** | Alembic | 1.13.1 |
| **Data Validation** | Pydantic | 2.5.3 |

### Data Processing & Geospatial
- **Pandas**: Data manipulation (2.0.0+)
- **GeoPandas**: Geospatial analysis (0.14.0+)
- **Shapely**: Geometric operations (2.0.0+)
- **GeoPy**: Geocoding (2.4.1)
- **Nominatim**: Address geocoding fallback

### AI/LLM Integration
- **Anthropic**: Claude API (0.39.0+)
- **OpenAI**: GPT API (1.54.0+)

### Document Processing
- **PyPDF2**: PDF extraction
- **PDFPlumber**: Advanced PDF parsing
- **Tesseract**: OCR for scanned documents
- **BeautifulSoup4**: Web scraping

### Frontend
- **React**: 19.2.0
- **React Router**: 7.9.6
- **Leaflet**: Interactive maps (via react-leaflet)
- **Recharts**: Data visualization
- **Tailwind CSS**: Styling

### Infrastructure
- **Docker**: Containerization
- **Nginx**: Reverse proxy
- **Python 3.11+**: Runtime

---

## Project Structure

```
TrashAlert/
├── README.md                          # Main project documentation
├── PROGRESS_REPORT.md                 # Development progress tracking
├── requirements.txt                   # Python dependencies
├── pytest.ini                         # Test configuration
├── docker-compose.yml                 # Docker services definition
├── Dockerfile                         # Container image definition
│
├── app/                               # FastAPI application (MAIN APPLICATION)
│   ├── main.py                        # FastAPI app definition, endpoints
│   ├── models.py                      # SQLAlchemy database models
│   ├── schemas.py                     # Pydantic request/response schemas
│   ├── services.py                    # Business logic services
│   ├── repositories.py                # Data access layer
│   ├── database.py                    # Database configuration
│   ├── utils.py                       # Utility functions
│   ├── ai_service.py                  # AI/LLM integration
│   ├── metrics.py                     # Request metrics tracking
│   ├── cache.py                       # Caching layer
│   ├── rate_limiter.py                # Rate limiting
│   ├── middleware.py                  # Request middleware
│   ├── logging_config.py              # Logging configuration
│   └── __init__.py
│
├── config/                            # Configuration files
│   └── cities.yaml                    # Supported cities configuration
│
├── scripts/                           # Data processing scripts
│   ├── run_full_pipeline.py           # Main pipeline orchestrator
│   ├── fetch_city_boundaries.py       # Get city boundaries from OSM
│   ├── build_subdivisions.py          # Detect neighborhoods
│   ├── fetch_addresses_osm.py         # Extract addresses from OSM
│   ├── sample_addresses_per_city.py   # Sample addresses (50/city)
│   ├── create_database.py             # Initialize database schema
│   ├── load_addresses.py              # Load addresses to DB
│   ├── add_test_crowd_reports.py      # Generate test data
│   ├── normalize_addresses.py         # Address normalization
│   │
│   ├── data_collection/               # Schedule data collection
│   │   ├── schedule_runner.py         # Schedule fetching orchestrator
│   │   ├── schedule_parsers/          # City-specific schedule parsers
│   │   │   ├── base_parser.py         # Parser base class
│   │   │   ├── san_diego_parser.py    # San Diego parser
│   │   │   ├── el_centro_parser.py    # El Centro parser
│   │   │   └── imperial_parser.py     # Imperial parser
│   │   └── validate_schedules.py      # Schedule validation
│   │
│   ├── processing/                    # Post-processing scripts
│   │   ├── generate_subdivisions.py   # Subdivision generation
│   │   ├── assign_zones_and_schedules.py # Zone assignment
│   │   └── update_crowd_consensus.py  # Consensus calculation
│   │
│   ├── schedules/                     # Schedule fetching
│   │   ├── fetch_san_diego_schedule.py
│   │   └── fetch_el_centro_schedule.py
│   │
│   └── database/                      # Database utilities
│       ├── init_db.py                 # Database initialization
│       └── inspect_schema.py          # Schema inspection
│
├── alembic/                           # Database migrations
│   ├── alembic.ini                    # Alembic configuration
│   └── versions/
│       └── cf3d5b32a1e3_initial_...py # Initial schema migration
│
├── frontend/                          # Frontend applications
│   ├── index.html                     # Main landing page
│   ├── README.md                      # Frontend documentation
│   └── admin-dashboard/               # React admin dashboard
│       ├── src/
│       ├── package.json               # Node dependencies
│       └── vite.config.js             # Build configuration
│
├── tests/                             # Test suite
│   ├── test_api.py                    # API endpoint tests
│   ├── test_api_lookup.py             # Lookup endpoint tests
│   ├── test_database_schema.py        # Database schema tests
│   ├── test_crowdsourcing.py          # Consensus algorithm tests
│   ├── test_hardening.py              # Security tests
│   ├── test_observability.py          # Metrics tests
│   └── test_expanded_schema.py        # Extended schema tests
│
├── docs/                              # Documentation
│   ├── architecture.md                # System architecture
│   ├── data_model.md                  # Database schema documentation
│   ├── crowdsourcing.md               # Consensus algorithm
│   ├── OSM_PIPELINE.md                # OSM data pipeline
│   ├── ADDRESS_SAMPLING_ENGINE.md     # Address sampling strategy
│   ├── TRASH_RULES_SUMMARY.md         # City trash rules
│   └── trash_rules_*.md               # City-specific rules
│
├── data/                              # Data storage
│   ├── boundaries/                    # City boundary GeoJSON files
│   ├── subdivisions/                  # Subdivision data
│   ├── raw/                           # Raw OSM/source data
│   ├── processed/                     # Processed address data
│   ├── cache/                         # Geocoding cache
│   └── *.csv, *.db                    # Address and database files
│
├── nginx/                             # Nginx configuration
└── logs/                              # Application logs (runtime)
```

---

## Database Architecture

### Technology
- **Primary**: PostgreSQL 14+ with PostGIS extension
- **Development**: SQLite
- **ORM**: SQLAlchemy 2.0

### Core Tables

#### 1. **cities** - Supported cities
```python
Fields:
  - id (PK)
  - slug (unique) - URL-friendly ID (e.g., 'ca_san_diego')
  - name - City name
  - state - State abbreviation
  - county - County name
  - region - Geographic region
  - timezone - Time zone (default: America/Los_Angeles)
  - enabled - Is city active
  - extra_metadata - JSON for flexible data
  - created_at, updated_at

Relationships:
  - 1:N pickup_zones (city can have multiple zones)
```

#### 2. **addresses** - Individual addresses
```python
Fields:
  - id (PK)
  - normalized_address (indexed)
  - house_number
  - street (indexed)
  - city_slug (indexed) - Links to cities.yaml
  - city_name (indexed) - Human readable city
  - state (indexed)
  - zip_code (indexed)
  - lat, lon - GPS coordinates
  - official_trash_day - MON, TUE, WED, etc.
  - official_recycling_day
  - official_green_day
  - created_at, updated_at

Indexes:
  - normalized_address
  - street, city_slug, state, zip_code
  - (All foreign keys indexed)

Relationships:
  - 1:N crowd_reports
  - 1:1 crowd_consensus
  - 1:1 address_pickup_info
```

#### 3. **crowd_reports** - Individual user submissions
```python
Fields:
  - id (PK)
  - address_id (FK, indexed)
  - trash_day - Reported pickup day
  - recycling_day
  - green_day
  - user_hash (indexed) - Anonymous user ID
  - ip_address (indexed) - For spam prevention
  - created_at (indexed) - Report timestamp

Composite Indexes:
  - (address_id, created_at) - For consensus queries
  - (address_id, ip_address) - For spam checking
```

#### 4. **crowd_consensus** - Aggregated consensus
```python
Fields:
  - id (PK)
  - address_id (FK, unique, indexed)
  - consensus_trash_day - Consensus pickup day
  - consensus_recycling_day
  - consensus_green_day
  - total_reports - Count of reports used
  - trash_agreement_ratio - 0.0 to 1.0
  - recycling_agreement_ratio
  - green_agreement_ratio
  - is_verified (indexed) - Met verification threshold
  - created_at, updated_at

Relationships:
  - 1:1 with addresses
```

#### 5. **schedules** - Official pickup schedules
```python
Fields:
  - id (PK)
  - city_id (FK, indexed)
  - pickup_zone_id (FK, nullable)
  - trash_day_of_week - MON, TUE, WED, etc.
  - recycling_day_of_week
  - green_day_of_week
  - source - OFFICIAL, GIS, MANUAL
  - extra_metadata - JSON for schedule details
  - created_at, updated_at
```

#### 6. **pickup_zones** - Geographic zones within cities
```python
Fields:
  - id (PK)
  - city_id (FK, indexed)
  - name - Zone name (e.g., "North Zone")
  - external_ref - City GIS reference ID
  - extra_metadata - JSON (geometry, etc.)
  - created_at, updated_at

Indexes:
  - (city_id, external_ref) - For zone lookup
```

#### 7. **address_pickup_info** - Consolidated pickup info
```python
Fields:
  - id (PK)
  - address_id (FK, unique, indexed)
  - pickup_zone_id (FK, nullable, indexed)
  - trash_day_of_week
  - recycling_day_of_week
  - green_day_of_week
  - source - OFFICIAL, CROWD, HYBRID
  - created_at, updated_at

Purpose: Provides a single consolidated view merging official
and crowdsourced data for each address.
```

#### 8. **schedule_exceptions** - Holiday and special pickups
```python
Fields:
  - id (PK)
  - schedule_id (FK, indexed)
  - exception_date (indexed) - Date of exception
  - rescheduled_date - New pickup date
  - is_cancelled (bool) - Pickup cancelled?
  - reason - Holiday name (e.g., "Christmas")
  - notes - Description
  - created_at, updated_at
```

#### 9. **source_metadata** - Track data source provenance
```python
Fields:
  - id (PK)
  - city (indexed)
  - source_type - pdf, html, api, manual
  - source_url - Where data came from
  - source_name - Descriptive name
  - parser_version - Parser used
  - parser_name
  - total_records_extracted
  - successful_records
  - failed_records
  - extra_data (JSON)
  - last_fetched_at
  - last_parsed_at
  - created_at, updated_at

Purpose: Maintain audit trail of how schedules were sourced
and parsed for quality tracking.
```

#### 10. **request_metrics** - API observability
```python
Fields:
  - id (PK)
  - endpoint (indexed) - /lookup, /report
  - method - GET, POST
  - status_code (indexed)
  - response_time_ms - Performance metric
  - city (indexed) - City from request
  - error_message - If failed
  - user_agent
  - ip_address
  - created_at (indexed)

Purpose: Track API usage, performance, and errors for
monitoring and analytics.
```

### Data Relationships Diagram
```
cities
  ├─ 1:N ─→ addresses
  │          ├─ 1:N ─→ crowd_reports
  │          ├─ 1:1 ─→ crowd_consensus
  │          ├─ 1:1 ─→ address_pickup_info
  │          │         └─ N:1 ─→ pickup_zones
  │          │
  │          └─ (official schedule fields)
  │
  ├─ 1:N ─→ schedules
  │         └─ 1:N ─→ schedule_exceptions
  │
  └─ 1:N ─→ pickup_zones
           └─ 1:N ─→ addresses
```

---

## API Endpoints

### Health & Status
```http
GET /
Returns: {"status": "healthy", "service": "TrashAlert API", "version": "1.0.0", "endpoints": [...]}
```

### Core Endpoints

#### 1. POST /report - Submit Crowdsourced Report
**Purpose**: Submit observations of trash pickup days

**Request**:
```json
{
  "address": "1122 Palmview Ave, El Centro, CA",
  "trash_day": "WED",
  "recycling_day": "FRI",
  "green_day": null,
  "user_hash": "optional-stable-id"
}
```

**Response** (200 OK):
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

**Features**:
- Automatic address normalization and geocoding
- Creates address if not in database
- Updates consensus calculation
- Rate limiting: 10 reports per IP/15min, 3 per address
- Metrics tracking
- Real-time consensus updates

---

#### 2. GET /lookup - Retrieve Pickup Schedule
**Purpose**: Look up trash schedule for an address

**Query Parameters**:
- `address` (string, optional) - Full address
- `lat` (float, optional) - Latitude (requires lon)
- `lon` (float, optional) - Longitude (requires lat)
- `city_id` (string, optional) - City filter (e.g., 'ca_san_diego')

**Response** (200 OK):
```json
{
  "matched_address": "1122 PALMVIEW AVE, EL CENTRO, CA",
  "city_id": "ca_el_centro",
  "city_name": "El Centro",
  "lat": 32.7924,
  "lon": -115.5633,
  "trash_day_of_week": "Wednesday",
  "recycling_day_of_week": "Friday",
  "green_waste_day_of_week": null,
  "data_source": "CROWD_VERIFIED",
  "consensus_reports_count": 3,
  "consensus_agreement_ratio": 1.0,
  "consensus_details": {
    "reports_count": 3,
    "agreement_ratio": 1.0
  }
}
```

**Data Source Priority**:
1. `CROWD_VERIFIED` - Verified consensus (≥3 reports, ≥75% agreement)
2. `OFFICIAL` - Official city data
3. `CROWD_UNVERIFIED` - Crowdsourced but unverified
4. `UNKNOWN` - No data available

**Features**:
- Multiple input formats (address or coordinates)
- Automatic city detection
- Coordinate-based lookup (50m radius)
- 5-minute cache
- Source attribution
- Agreement metrics

---

#### 3. POST /interpret-address - AI Address Interpretation
**Purpose**: Parse and normalize freeform address text

**Request**:
```json
{
  "text": "my trash goes out on Wednesdays at 1122 Palmview, El Centro",
  "use_geocoding": true
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "normalized_address": "1122 Palmview Avenue, El Centro, California",
  "confidence": 0.92,
  "city": "El Centro",
  "city_id": "ca_el_centro",
  "state": "CA",
  "zip_code": "92243",
  "lat": 32.7924,
  "lon": -115.5633,
  "interpretation_method": "ai",
  "ai_reasoning": "Extracted house number 1122 from street reference...",
  "geocoding_quality": null
}
```

**Features**:
- AI-powered text parsing (OpenAI/Anthropic)
- Hybrid interpretation (AI + geocoding fallback)
- Confidence scoring
- Geolocation support
- City matching from config
- Structured reasoning from AI

---

#### 4. GET /stats - Database & API Statistics
**Purpose**: Get overview of system data and usage

**Response**:
```json
{
  "total_addresses": 2150,
  "total_reports": 3421,
  "total_consensus": 1850,
  "verified_consensus": 1200,
  "cities": [
    {"city": "San Diego", "address_count": 800},
    {"city": "El Centro", "address_count": 450},
    ...
  ],
  "pilot_cities": ["El Centro", "Imperial", "Brawley", ...]
}
```

**Features**:
- Address coverage by city
- Consensus verification rate
- Report submission statistics
- Pilot city list

---

## Data Flow

### Report Submission Flow
```
User submits report
    ↓
/report endpoint validates input
    ↓
Normalize address (extract components, geocode)
    ↓
Find or create Address record (if not exists)
    ↓
Create CrowdReport record
    ↓
Calculate consensus:
  1. Aggregate all reports for address
  2. Find most common day (mode) for each type
  3. Calculate agreement ratio (agreement / total reports)
  4. Check verification threshold (≥3 reports, ≥75% agreement)
    ↓
Update CrowdConsensus record (is_verified true/false)
    ↓
Record metrics (endpoint, response time, city, status)
    ↓
Return response with updated consensus
```

### Lookup Flow
```
User queries /lookup with address or coordinates
    ↓
Validate input format
    ↓
Find Address record:
  - By normalized address (if address provided)
  - By coordinates within 50m (if lat/lon provided)
    ↓
Return UNKNOWN if not found
    ↓
Retrieve CrowdConsensus (if exists)
    ↓
Apply data source priority:
  1. Is consensus verified? → CROWD_VERIFIED
  2. Has official data? → OFFICIAL
  3. Has unverified consensus? → CROWD_UNVERIFIED
  4. Nothing? → UNKNOWN
    ↓
Convert day abbreviations to full names
    ↓
Build response with source attribution
    ↓
Record metrics
    ↓
Return response (may be cached)
```

### Address Interpretation Flow
```
User submits freeform text
    ↓
AI interpreter (Anthropic/OpenAI):
  - Parse text into components
  - Extract address parts
  - Infer city from context
  - Generate confidence score
    ↓
If confidence < 0.7 and geocoding enabled:
  - Use Nominatim to geocode address
  - Extract address components from result
  - Boost confidence if match quality high
    ↓
If AI failed and geocoding enabled:
  - Attempt geocoding directly on input text
  - Extract components from geocoding result
    ↓
Return structured interpretation with method used
```

---

## Data Models & Relationships

### SQLAlchemy Model Definitions

#### Address Model
```python
class Address(Base):
    __tablename__ = "addresses"
    
    id = Column(Integer, primary_key=True)
    normalized_address = Column(String, index=True)
    house_number = Column(String)
    street = Column(String, index=True)
    city_slug = Column(String, index=True)
    city_name = Column(String, index=True)
    state = Column(String, index=True)
    zip_code = Column(String, index=True)
    lat = Column(Float)
    lon = Column(Float)
    
    # Official schedule fields
    official_trash_day = Column(String)
    official_recycling_day = Column(String)
    official_green_day = Column(String)
```

#### CrowdReport Model
```python
class CrowdReport(Base):
    __tablename__ = "crowd_reports"
    
    id = Column(Integer, primary_key=True)
    address_id = Column(Integer, FK, indexed)
    trash_day = Column(String)
    recycling_day = Column(String)
    green_day = Column(String)
    user_hash = Column(String, indexed)
    ip_address = Column(String, indexed)
    created_at = Column(DateTime, indexed)
```

#### CrowdConsensus Model
```python
class CrowdConsensus(Base):
    __tablename__ = "crowd_consensus"
    
    id = Column(Integer, primary_key=True)
    address_id = Column(Integer, FK, unique, indexed)
    
    # Consensus values
    consensus_trash_day = Column(String)
    consensus_recycling_day = Column(String)
    consensus_green_day = Column(String)
    
    # Metrics
    total_reports = Column(Integer, default=0)
    trash_agreement_ratio = Column(Float, default=0.0)
    recycling_agreement_ratio = Column(Float, default=0.0)
    green_agreement_ratio = Column(Float, default=0.0)
    
    # Verification
    is_verified = Column(Boolean, default=False, indexed)
```

---

## Existing Analytics & Metrics

### Metrics Collection (app/metrics.py)

#### MetricsManager Class
Provides methods for tracking API usage and performance:

```python
MetricsManager.record_request(
    endpoint="/lookup",
    method="GET",
    status_code=200,
    response_time_ms=45.23,
    city="San Diego",
    user_agent="Mozilla/5.0..."
)
```

#### Available Metrics
1. **Overall Statistics**
   - Total lookups / reports
   - Average response times
   - Error counts and rates
   - Per-city breakdowns

2. **Endpoint-Specific Stats**
   - Total requests per endpoint
   - Min/max/average response times
   - Error count and success rate

3. **Database Statistics**
   - Total addresses
   - Total crowd reports
   - Consensus count (verified/unverified)

4. **Usage Patterns**
   - Lookups per city
   - Reports per city
   - Peak usage times (timestamp indexed)

### Request Metrics Table
```python
class RequestMetrics(Base):
    __tablename__ = "request_metrics"
    
    id = Column(Integer, primary_key=True)
    endpoint = Column(String, indexed)
    method = Column(String)
    status_code = Column(Integer, indexed)
    response_time_ms = Column(Float)
    city = Column(String, indexed)
    error_message = Column(String)
    user_agent = Column(String)
    ip_address = Column(String)
    created_at = Column(DateTime, indexed)
```

### Metrics Query Methods
- `get_lookup_stats_by_city()` - Lookups per city
- `get_report_stats_by_city()` - Reports per city
- `get_overall_stats()` - Complete statistics
- `get_endpoint_stats(endpoint)` - Detailed endpoint stats

---

## Data Collection Pipeline

### Components

#### 1. City Boundaries (fetch_city_boundaries.py)
- Queries OpenStreetMap Overpass API
- Extracts boundary polygons for cities
- Stores as GeoJSON files

#### 2. Address Extraction (fetch_addresses_osm.py)
- Queries OSM for all addresses within city boundary
- Extracts: house_number, street, subdivision, coordinates
- Outputs to addresses_osm_raw.csv

#### 3. Subdivision Detection (build_subdivisions.py)
- Analyzes address distribution within cities
- Identifies neighborhoods and subdivisions
- Used for stratified sampling

#### 4. Address Sampling (sample_addresses_per_city.py)
- Stratified sampling across subdivisions
- Targets 50 addresses per city
- Ensures geographic diversity
- Removes duplicates and invalid coordinates

#### 5. Database Loading (load_addresses.py)
- Loads sampled addresses into database
- Normalizes address strings
- Geocodes if needed
- Links to city records

#### 6. Schedule Parsers (scripts/data_collection/schedule_parsers/)
- City-specific parsers for official schedules
- Extracts from PDFs, HTML, APIs
- Supports San Diego, El Centro, Imperial
- Extensible base parser class

#### 7. Consensus Update (scripts/processing/update_crowd_consensus.py)
- Batch updates consensus for all addresses
- Recalculates agreement ratios
- Verifies threshold compliance

### Pipeline Execution
```bash
# Run full pipeline for one city
python scripts/run_full_pipeline.py --city "El Centro"

# Process all cities
python scripts/run_full_pipeline.py --all

# Run individual steps
python scripts/fetch_city_boundaries.py --only "San Diego"
python scripts/fetch_addresses_osm.py --only "San Diego"
python scripts/sample_addresses_per_city.py --only "San Diego"
```

---

## Key Features for Prediction Module

### 1. Rich Historical Data Available
- **Crowd reports** with timestamps (created_at)
- **Consensus changes** tracked over time (updated_at)
- **Report agreement patterns** per day of week
- **User patterns** (anonymous via user_hash)

### 2. Address-Level Context
- Geographic coordinates (lat/lon)
- Subdivisions/neighborhoods
- City information
- Multiple collection types (trash, recycling, green)

### 3. Consensus Metrics
- Agreement ratios (0.0-1.0) for each type
- Total reports per address
- Verification status (proved reliable threshold)
- Breakdown by pickup type

### 4. City-Level Data
- Per-city report and lookup counts
- Geographic distribution of reports
- City-specific patterns
- Coverage statistics

### 5. Temporal Features Available
- Timestamp on every report (created_at)
- Timestamp on every lookup (request_metrics)
- Can analyze seasonal patterns
- Can identify trending changes

### 6. Schedule Exception Handling
- Holiday exceptions tracked separately
- Schedule change audit trail via source_metadata
- City-level special pickup dates
- Can predict impact of exceptions

### 7. Data Quality Indicators
- Report count (more = higher confidence)
- Agreement ratio (consistency)
- Verification status (passed threshold)
- Source attribution (official vs crowdsourced)

---

## Suggested Prediction Module Architecture

Based on available data, a prediction module should:

### Input Features (from historical data)
1. **Address features**
   - City, subdivision
   - Coordinates (for geographic patterns)
   - Collection type (trash/recycling/green)

2. **Historical consensus**
   - Current agreement ratio
   - Number of reports
   - Report timing distribution
   - Previous consensus values

3. **Temporal features**
   - Week number
   - Month
   - Holiday proximity
   - Seasonal patterns

4. **User patterns**
   - Report frequency per address
   - Consistency (std dev of agreement)
   - Report timing patterns

### Outputs (what to predict)
1. **Schedule changes**
   - Probability of change in next 30/60/90 days
   - Likely new day (if change occurs)
   - Confidence in prediction

2. **Report reliability**
   - Quality score for next report
   - Expected agreement ratio trend
   - Spam probability

3. **City-level patterns**
   - Growth in report submissions
   - Coverage expansion
   - Data quality trends

### ML Approaches
1. **Time series forecasting** (ARIMA, Prophet)
   - Predict report submission rates
   - Forecast consensus changes

2. **Classification models** (Logistic Regression, Random Forest)
   - Predict schedule changes (binary or multi-class)
   - Identify spam reports

3. **Clustering** (K-means, DBSCAN)
   - Group addresses with similar patterns
   - Identify neighborhoods with consistent reports

4. **Anomaly detection** (Isolation Forest, Local Outlier Factor)
   - Find unusual agreement patterns
   - Detect data quality issues

---

## Testing & Development

### Test Files
- `test_api.py` - API endpoint integration tests
- `test_api_lookup.py` - Lookup functionality tests
- `test_database_schema.py` - Database model tests
- `test_crowdsourcing.py` - Consensus algorithm tests
- `test_hardening.py` - Security tests
- `test_observability.py` - Metrics tests

### Development Environment
```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Start API (development)
uvicorn app.main:app --reload

# Docker deployment
docker-compose up --build
```

### Configuration Files
- `config/cities.yaml` - Supported cities and metadata
- `.env` - Environment variables (API keys, DB credentials)
- `alembic.ini` - Database migration settings
- `docker-compose.yml` - Service definitions

---

## Summary

TrashAlert is a well-architected system with:
- **Solid database foundation** with proper indexing and relationships
- **RESTful API** with multiple endpoints and input formats
- **Consensus algorithm** for data quality verification
- **Metrics tracking** for observability and analytics
- **AI integration** for address interpretation
- **Extensive data collection pipeline** from multiple sources
- **Rich historical data** ready for prediction models

The prediction module should leverage:
- Address-level consensus metrics and history
- Temporal patterns in reports and lookups
- City-level aggregations
- Schedule exception tracking
- Multi-type collection data (trash/recycling/green)

