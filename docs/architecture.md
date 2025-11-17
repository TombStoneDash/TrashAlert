# TrashAlert Architecture

## Overview

TrashAlert is a trash day lookup system designed as a pilot project for San Diego and Imperial Valley cities. The system helps residents find their trash collection day through a crowdsourced, consensus-based approach.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         TRASHALERT SYSTEM                            │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│   City       │         │  OpenStreetMap│         │  City        │
│   Boundaries │────────▶│  (OSM)        │────────▶│  Subdivisions│
│   Data       │         │  API Query    │         │  Detection   │
└──────────────┘         └──────────────┘         └──────────────┘
                                                           │
                                                           ▼
                                                  ┌──────────────┐
                                                  │  Address     │
                                                  │  Extraction  │
                                                  └──────────────┘
                                                           │
                                                           ▼
                                                  ┌──────────────┐
                                                  │  Sampling    │
                                                  │  (50/city)   │
                                                  └──────────────┘
                                                           │
                                                           ▼
┌────────────────────────────────────────────────────────────────────┐
│                         DATABASE LAYER                              │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ Cities   │  │Addresses │  │ Reports  │  │ Schedules│          │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘          │
└────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────┐
│                           API LAYER                                 │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │  Address     │  │  Report      │  │  Schedule    │            │
│  │  Lookup      │  │  Submission  │  │  Query       │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
└────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────┐
│                    CROWDSOURCING ENGINE                             │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │  Consensus Logic:                                         │     │
│  │  - Collect multiple reports per address                  │     │
│  │  - Calculate consensus based on agreement                │     │
│  │  - Weight reports by recency and consistency             │     │
│  │  - Flag conflicting reports for review                   │     │
│  └──────────────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────┐
│                      CLIENT INTERFACE                               │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │  Web App     │  │  Mobile App  │  │  API Clients │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
└────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Data Collection Layer

#### City Boundaries
- Source: City boundary GeoJSON files
- Purpose: Define geographic scope for each city
- Format: GeoJSON with polygon coordinates

#### OSM Address Extraction
- Source: OpenStreetMap Overpass API
- Query: All addresses within city boundaries
- Extracts: house_number, street, city, subdivision, coordinates
- Output: Raw address dataset

#### Subdivision Detection
- Detects neighborhoods/subdivisions when available
- Used for stratified sampling to ensure geographic coverage
- Optional: cities without subdivisions still supported

### 2. Address Sampling

**Purpose**: Limit initial dataset to manageable size while maintaining geographic diversity

**Algorithm**:
- **Target**: Up to 50 addresses per city
- **Strategy**: Stratified sampling across subdivisions
- **Distribution**:
  - If city has subdivisions: distribute samples evenly across them
  - If city has no subdivisions: random sampling
  - If city has <50 addresses: include all

**Benefits**:
- Reduces database size for pilot
- Maintains geographic representation
- Balances coverage across neighborhoods

### 3. Database Layer

**Primary Tables**:
- `cities`: City metadata and boundaries
- `addresses`: Sampled addresses with coordinates
- `trash_schedules`: Known/verified trash collection schedules
- `user_reports`: Crowdsourced trash day reports
- `consensus_schedules`: Computed consensus from reports

**Relationships**:
- Cities → Addresses (one-to-many)
- Addresses → User Reports (one-to-many)
- Addresses → Consensus Schedules (one-to-one)

### 4. API Layer

**Endpoints** (planned):

```
GET  /api/cities
     List all supported cities

GET  /api/addresses/:id
     Get address details and current trash schedule

POST /api/reports
     Submit a new trash day report
     Body: { address_id, collection_day, collection_type, user_token }

GET  /api/schedules/:address_id
     Get consensus schedule for an address
     Returns: { collection_day, confidence_score, report_count }

GET  /api/addresses/search
     Query: ?street=Main+St&city=San+Diego
     Returns: Matching addresses with schedules
```

### 5. Crowdsourcing Engine

**Consensus Algorithm**:

1. **Report Collection**
   - Users submit observed trash collection days
   - Each report includes: day of week, collection type (trash/recycling/green)
   - Reports timestamped and optionally tied to user tokens

2. **Consensus Calculation**
   - Group reports by address and collection type
   - Calculate mode (most common) collection day
   - Compute confidence score based on:
     - Agreement percentage (e.g., 8/10 reports agree = 80%)
     - Total number of reports
     - Recency of reports (newer weighted higher)

3. **Quality Metrics**
   - **High Confidence**: ≥75% agreement, ≥5 reports
   - **Medium Confidence**: ≥60% agreement, ≥3 reports
   - **Low Confidence**: <60% agreement or <3 reports
   - **Conflicting**: Multiple days with similar report counts

4. **Conflict Resolution**
   - Flag addresses with conflicting reports
   - Prioritize recent reports (last 3 months)
   - Allow manual verification/override

### 6. Client Interface

**Web Application**:
- Address search interface
- Trash day lookup results
- Report submission form
- Confidence indicators

**Mobile Application** (future):
- Location-based lookup
- Push notifications for trash days
- Easy one-tap reporting

## Data Flow

### Initial Setup (One-time per city)

```
1. Load city boundary → 2. Query OSM for addresses →
3. Detect subdivisions → 4. Sample 50 addresses per city →
5. Store in database
```

### User Lookup Flow

```
1. User enters address → 2. Search database →
3. Retrieve consensus schedule → 4. Display result with confidence
```

### Report Submission Flow

```
1. User submits trash day report → 2. Validate and store →
3. Recalculate consensus → 4. Update schedule if needed
```

## Technology Stack (Planned)

### Backend
- **Language**: Python 3.11+
- **Framework**: FastAPI or Flask
- **Database**: PostgreSQL with PostGIS extension
- **ORM**: SQLAlchemy
- **API Documentation**: OpenAPI/Swagger

### Data Processing
- **Geospatial**: GeoPandas, Shapely
- **Data Analysis**: Pandas, NumPy
- **OSM Queries**: Overpass API

### Frontend (Future)
- **Web**: React or Vue.js
- **Mobile**: React Native or Flutter
- **Maps**: Leaflet or Mapbox

### Infrastructure
- **Hosting**: Cloud platform (AWS/GCP/Azure)
- **Database**: Managed PostgreSQL
- **API**: Containerized with Docker

## Scalability Considerations

### Current Scope (Pilot)
- 2 regions: San Diego, Imperial Valley
- ~50 addresses per city
- Estimated total: 500-1000 addresses

### Future Expansion
- Add more California cities
- Increase address coverage (remove 50 limit)
- Support other collection types (bulk pickup, hazardous waste)
- Add schedule prediction based on patterns
- Integration with official city APIs where available

## Security & Privacy

### User Privacy
- Optional anonymous reporting
- No personal information required
- User tokens for rate limiting only

### Data Validation
- Input sanitization on all endpoints
- Rate limiting to prevent abuse
- CAPTCHA for report submission

### API Security
- API key authentication for clients
- HTTPS only
- CORS policies
- SQL injection prevention via ORM

## Monitoring & Maintenance

### Metrics to Track
- Report submission rate
- Consensus confidence distribution
- Address coverage (% with high confidence)
- API response times
- Error rates

### Maintenance Tasks
- Monthly review of conflicting reports
- Quarterly verification of high-traffic addresses
- Annual OSM data refresh
- Database cleanup of outdated reports

## Development Phases

### Phase 1: Data Pipeline (Current)
- ✅ OSM address extraction
- ✅ Address sampling script
- ⏳ Database schema design
- ⏳ Data ingestion pipeline

### Phase 2: API Development
- ⏳ Setup FastAPI/Flask project
- ⏳ Implement CRUD operations
- ⏳ Build consensus algorithm
- ⏳ API documentation

### Phase 3: Client Development
- ⏳ Web interface
- ⏳ Search functionality
- ⏳ Report submission UI
- ⏳ Results visualization

### Phase 4: Testing & Launch
- ⏳ Unit tests
- ⏳ Integration tests
- ⏳ Beta testing with users
- ⏳ Production deployment

### Phase 5: Expansion
- ⏳ Additional cities
- ⏳ Mobile app
- ⏳ Advanced features
- ⏳ Official data integration
