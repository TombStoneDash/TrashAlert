# TrashAlert Pipeline

A scalable data pipeline for collecting and processing trash pickup information across multiple cities.

## Overview

This pipeline collects address data from OpenStreetMap and processes it for use in the TrashAlert system. It's designed to scale from a single city to hundreds of cities across the United States.

## Pipeline Architecture

The pipeline consists of several modular scripts that work together:

1. **fetch_city_boundaries.py** - Fetches city boundaries from OpenStreetMap
2. **build_subdivisions.py** - Builds subdivision/neighborhood data for each city
3. **fetch_addresses_osm.py** - Fetches address data from OpenStreetMap
4. **sample_addresses_per_city.py** - Samples addresses per city (up to configurable limit)
5. **run_full_pipeline.py** - Orchestrates the entire pipeline

## Configuration

Cities are configured in `config/cities.yaml`. Each city entry includes:

```yaml
- name: City Name
  state: State Name
  state_abbr: XX
  country: USA
  has_official_pickup_zones: true/false
  pickup_zone_data_source: "URL or note"
  notes: "Additional context"
```

## Usage

### Running the Full Pipeline

Process all cities:
```bash
python scripts/run_full_pipeline.py --all
```

Process a specific city:
```bash
python scripts/run_full_pipeline.py --city "Brawley, California"
# or
python scripts/run_full_pipeline.py --city "Brawley"
```

Process all cities in a state:
```bash
python scripts/run_full_pipeline.py --state CA
# or
python scripts/run_full_pipeline.py --state California
```

Skip certain pipeline steps:
```bash
python scripts/run_full_pipeline.py --city "Brawley" \
  --skip-boundaries --skip-subdivisions
```

### Running Individual Scripts

Each script can be run independently with the same filtering options:

**Sample addresses:**
```bash
# All cities
python scripts/sample_addresses_per_city.py

# One city
python scripts/sample_addresses_per_city.py --only "Brawley, California"

# One state
python scripts/sample_addresses_per_city.py --state CA

# Custom sample size
python scripts/sample_addresses_per_city.py --only "Brawley" --max-per-city 100
```

**Fetch boundaries:**
```bash
python scripts/fetch_city_boundaries.py --only "San Diego, California"
```

**Build subdivisions:**
```bash
python scripts/build_subdivisions.py --state CA
```

**Fetch addresses:**
```bash
python scripts/fetch_addresses_osm.py --only "Brawley"
```

## Adding New Cities

1. Edit `config/cities.yaml` and add a new city entry
2. Run the pipeline for that city:
   ```bash
   python scripts/run_full_pipeline.py --city "New City, State"
   ```

## Output

The pipeline generates the following data:

- `data/boundaries/*.geojson` - City boundary GeoJSON files
- `data/subdivisions/*.json` - Subdivision/neighborhood data
- `data/addresses_osm_raw.csv` - Raw address data from OpenStreetMap
- `data/addresses_sampled_50_per_city.csv` - Sampled addresses (default: 50 per city)

## Requirements

```bash
pip install pyyaml requests pandas
```

## Example: Pipeline for One City

```bash
# Run the complete pipeline for Brawley
python scripts/run_full_pipeline.py --city "Brawley"

# Output shows:
# - Cities processed: Brawley, CA
# - Steps completed: 4
# - Data statistics per city
# - Summary with timing information
```

## Future Enhancements

- Normalization step for address standardization
- Database loading functionality
- Integration with official city pickup zone data
- Support for international cities (currently US-only)
# TrashAlert

> **Crowdsourced trash collection day lookup for California cities**

TrashAlert is a pilot project to help residents quickly find their trash collection day through community-driven data. Instead of navigating complex city websites or calling municipal offices, users can look up their address and see when trash is collected based on real observations from their neighbors.

## 🎯 Project Goal

Build a reliable, crowdsourced trash schedule database for San Diego and Imperial Valley cities, demonstrating that community data can be more accurate and up-to-date than official sources.

## 🏗️ Project Status

**Current Phase**: Data Pipeline Development (Phase 1)

- ✅ OpenStreetMap address extraction
- ✅ Address sampling script (50 per city)
- ✅ Sample data generation for testing
- ⏳ Database schema design
- ⏳ API development
- ⏳ Web interface

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Data Flow](#data-flow)
- [Setup Instructions](#setup-instructions)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## 🌟 Overview

### The Problem

Finding your trash collection day is harder than it should be:
- City websites are confusing or outdated
- Schedules vary by neighborhood/subdivision
- Route changes aren't communicated well
- New residents don't know where to look

### The Solution

TrashAlert uses crowdsourcing to build a reliable schedule database:
1. Users report when they observe trash collection
2. System calculates consensus from multiple reports
3. Confidence scores indicate reliability
4. Self-correcting as more data comes in

### Key Features

- 📍 **Address-based lookup**: Enter your address, get your schedule
- 👥 **Crowdsourced data**: Community observations, not outdated records
- 🎯 **Confidence scores**: Know how reliable each schedule is
- 🔄 **Self-updating**: Automatically adapts to schedule changes
- 🗺️ **Geographic sampling**: Ensures coverage across subdivisions

## 🏛️ Architecture

### High-Level Data Flow

```
City Config → City Boundaries → OSM Query → Address Extraction
                                                    ↓
                                            Subdivision Detection
                                                    ↓
                                          Sampling (50 per city)
                                                    ↓
                                              Database
                                                    ↓
                                           API Endpoints
                                                    ↓
                                          Web Interface
                                                    ↓
                                        User Reports
                                                    ↓
                                      Consensus Calculation
                                                    ↓
                                      Updated Schedules
```

### System Components

1. **Data Collection Layer**
   - City boundary definitions
   - OpenStreetMap address queries
   - Subdivision detection
   - Geographic sampling

2. **Database Layer**
   - PostgreSQL with PostGIS
   - Cities, addresses, reports, schedules
   - Spatial indexing for location queries

3. **API Layer** (planned)
   - RESTful API with FastAPI/Flask
   - Address lookup endpoints
   - Report submission
   - Schedule queries

4. **Crowdsourcing Engine** (planned)
   - Consensus algorithm
   - Confidence scoring
   - Conflict detection
   - Quality metrics

5. **Client Interface** (planned)
   - Web application
   - Mobile app (future)

For detailed architecture, see [docs/architecture.md](docs/architecture.md).

## 🔄 Data Flow

### Initial Setup Flow

```
1. City Configuration
   ├─ Define city name and boundaries
   └─ Load boundary GeoJSON

2. OSM Address Extraction
   ├─ Query Overpass API with city boundary
   ├─ Extract: house_number, street, subdivision, lat, lon
   └─ Save to addresses_osm_raw.csv

3. Address Sampling
   ├─ Load raw addresses
   ├─ Remove null coordinates and duplicates
   ├─ Sample up to 50 per city (stratified by subdivision)
   └─ Save to addresses_sampled_50_per_city.csv

4. Database Ingestion (planned)
   ├─ Load sampled addresses
   ├─ Geocode and validate
   └─ Insert into addresses table
```

### User Interaction Flow (Planned)

```
1. User Lookup
   User enters address → Search API → Return consensus schedule + confidence

2. User Report
   User observes collection → Submit report → Store in database →
   Recalculate consensus → Update schedule

3. Consensus Calculation
   Collect all reports for address → Filter by recency →
   Calculate weighted scores → Determine consensus day →
   Compute confidence score → Update trash_schedules table
```

For detailed data flow, see [docs/architecture.md](docs/architecture.md).

## 🚀 Setup Instructions

### Prerequisites

- **Python**: 3.11 or higher
- **Git**: For version control
- **PostgreSQL**: 14+ with PostGIS extension (for production)
- **pip**: Python package manager

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/TrashAlert.git
   cd TrashAlert
   ```

2. **Create a virtual environment**

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies** (when requirements.txt is created)

   ```bash
   pip install -r requirements.txt
   ```

   Current dependencies (to be added to requirements.txt):
   - `pandas` - Data manipulation
   - `geopandas` - Geospatial data processing
   - `shapely` - Geometric operations
   - `requests` - HTTP requests for OSM API
   - `sqlalchemy` - Database ORM (future)
   - `psycopg2-binary` - PostgreSQL adapter (future)
   - `fastapi` - API framework (future)
   - `uvicorn` - ASGI server (future)

4. **Set up environment variables** (future)

   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Initialize the database** (future)

   ```bash
   # Create database
   createdb trashalert

   # Run migrations
   alembic upgrade head
   ```

### Configuration

Configuration files will be in `config/`:
- `cities.json` - City definitions and boundaries
- `database.yml` - Database connection settings
- `api.yml` - API configuration

## 📖 Usage

### Current Scripts

#### 1. Generate Sample Raw Data

Creates realistic test data for development:

```bash
python scripts/create_sample_raw_data.py
```

**Output**: `data/addresses_osm_raw.csv`
- Generates 445 sample addresses across 6 cities
- Includes subdivisions for San Diego
- Adds test cases: duplicates, null coordinates

#### 2. Sample Addresses Per City

Samples up to 50 addresses per city with geographic distribution:

```bash
python scripts/sample_addresses_per_city.py
```

**Input**: `data/addresses_osm_raw.csv`
**Output**: `data/addresses_sampled_50_per_city.csv`

**Features**:
- Stratified sampling across subdivisions
- Removes duplicates and null coordinates
- Ensures geographic diversity
- Logs sampling statistics

**Example Output**:
```
2025-11-16 10:00:00 - INFO - Loading raw addresses from data/addresses_osm_raw.csv
2025-11-16 10:00:00 - INFO - Loaded 445 addresses from 6 cities
2025-11-16 10:00:00 - INFO - San Diego: sampled 50 from 200 addresses across 8 subdivisions
2025-11-16 10:00:00 - INFO - El Centro: sampled 50 from 80 addresses across 5 subdivisions
2025-11-16 10:00:00 - INFO - Calexico: sampled 50 from 65 addresses (no subdivisions)
2025-11-16 10:00:00 - INFO - ✓ Done! Sampled dataset saved to data/addresses_sampled_50_per_city.csv
```

### Full Pipeline (Future)

#### 1. Setup a New City

```bash
# Add city to config/cities.json
python scripts/add_city.py --name "Carlsbad" --state "CA"

# Fetch addresses from OSM
python scripts/fetch_osm_addresses.py --city "Carlsbad"

# Sample addresses
python scripts/sample_addresses.py --city "Carlsbad"

# Load into database
python scripts/load_to_db.py --city "Carlsbad"
```

#### 2. Run the API Server

```bash
# Development server
uvicorn app.main:app --reload --port 8000

# Production server
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

API will be available at: `http://localhost:8000`
API documentation: `http://localhost:8000/docs`

#### 3. Run Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_consensus.py
```

## 📁 Project Structure

```
TrashAlert/
├── README.md                 # This file
├── .gitignore               # Git ignore rules
├── requirements.txt         # Python dependencies (to be created)
├── setup.py                 # Package setup (to be created)
│
├── data/                    # Data files
│   ├── addresses_osm_raw.csv                # Raw OSM address data
│   └── addresses_sampled_50_per_city.csv    # Sampled addresses
│
├── scripts/                 # Data processing scripts
│   ├── create_sample_raw_data.py       # Generate test data
│   ├── sample_addresses_per_city.py    # Sample addresses
│   ├── fetch_osm_addresses.py          # Fetch from OSM (future)
│   ├── load_to_db.py                   # Load to database (future)
│   └── add_city.py                     # Add new city (future)
│
├── app/                     # Application code (future)
│   ├── __init__.py
│   ├── main.py             # FastAPI app entry point
│   ├── config.py           # Configuration management
│   ├── database.py         # Database connection
│   │
│   ├── models/             # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── city.py
│   │   ├── address.py
│   │   ├── report.py
│   │   └── schedule.py
│   │
│   ├── api/                # API routes
│   │   ├── __init__.py
│   │   ├── addresses.py
│   │   ├── reports.py
│   │   └── schedules.py
│   │
│   ├── services/           # Business logic
│   │   ├── __init__.py
│   │   ├── consensus.py    # Consensus algorithm
│   │   ├── geocoding.py    # Address geocoding
│   │   └── validation.py   # Data validation
│   │
│   └── utils/              # Utility functions
│       ├── __init__.py
│       └── geo.py          # Geospatial helpers
│
├── tests/                   # Test suite (future)
│   ├── __init__.py
│   ├── test_consensus.py
│   ├── test_api.py
│   └── test_models.py
│
├── docs/                    # Documentation
│   ├── architecture.md      # System architecture
│   ├── data_model.md        # Database schema
│   ├── crowdsourcing.md     # Consensus algorithm
│   └── api.md              # API documentation (future)
│
├── config/                  # Configuration files (future)
│   ├── cities.json         # City definitions
│   ├── database.yml        # Database config
│   └── api.yml             # API config
│
├── migrations/              # Database migrations (future)
│   └── alembic/            # Alembic migration files
│
└── web/                     # Frontend (future)
    ├── public/
    ├── src/
    └── package.json
```

## 📚 Documentation

### Available Documentation

- **[Architecture Overview](docs/architecture.md)**: System design and component details
- **[Data Model](docs/data_model.md)**: Database schema, tables, and relationships
- **[Crowdsourcing Logic](docs/crowdsourcing.md)**: Consensus algorithm and quality metrics

### Future Documentation

- **API Reference**: Endpoint documentation with examples
- **Deployment Guide**: Production deployment instructions
- **Contributing Guide**: How to contribute to the project
- **User Guide**: How to use the web interface

## 🧪 Testing

### Current Testing

Manual testing with sample data:

```bash
# Generate sample data
python scripts/create_sample_raw_data.py

# Run sampling script
python scripts/sample_addresses_per_city.py

# Verify output
head -20 data/addresses_sampled_50_per_city.csv
```

### Future Testing

Automated test suite:

```bash
# Unit tests
pytest tests/test_consensus.py
pytest tests/test_models.py

# Integration tests
pytest tests/test_api.py

# End-to-end tests
pytest tests/test_e2e.py
```

## 🔍 Data Sources

### Current Data

- **Sample Data**: Generated test data for development
  - 6 cities: San Diego, El Centro, Calexico, Brawley, Imperial, Holtville
  - 445 addresses total (200 in San Diego, varying amounts in others)
  - Includes subdivisions where applicable

### Future Data Sources

- **OpenStreetMap**: Real address data via Overpass API
- **City Boundaries**: GeoJSON from OpenStreetMap or city open data portals
- **Official Schedules**: Where available from city websites
- **User Reports**: Crowdsourced observations

## 🛠️ Technology Stack

### Current

- **Python 3.11+**: Core language
- **Pandas**: Data processing
- **Standard Library**: CSV handling, logging

### Planned

**Backend**:
- **FastAPI**: Modern Python web framework
- **SQLAlchemy**: ORM for database operations
- **PostgreSQL**: Database with PostGIS extension
- **Alembic**: Database migrations
- **Pydantic**: Data validation

**Data Processing**:
- **GeoPandas**: Geospatial data analysis
- **Shapely**: Geometric operations
- **Requests**: HTTP client for OSM API

**Frontend** (future):
- **React**: UI framework
- **Leaflet**: Interactive maps
- **Tailwind CSS**: Styling

**Infrastructure**:
- **Docker**: Containerization
- **Nginx**: Reverse proxy
- **GitHub Actions**: CI/CD

## 🗺️ Roadmap

### Phase 1: Data Pipeline ✅ (In Progress)
- [x] Sample data generation
- [x] Address sampling script
- [ ] Database schema implementation
- [ ] OSM data fetching script
- [ ] Data ingestion pipeline

### Phase 2: Core API (Q1 2026)
- [ ] FastAPI project setup
- [ ] Database models (SQLAlchemy)
- [ ] CRUD operations
- [ ] Consensus algorithm implementation
- [ ] API endpoints

### Phase 3: Web Interface (Q2 2026)
- [ ] React app setup
- [ ] Address search UI
- [ ] Schedule display
- [ ] Report submission form
- [ ] Confidence indicators

### Phase 4: Beta Launch (Q3 2026)
- [ ] Deploy to cloud platform
- [ ] Load real OSM data for pilot cities
- [ ] User testing
- [ ] Bug fixes and refinements
- [ ] Documentation updates

### Phase 5: Expansion (Q4 2026)
- [ ] Add more California cities
- [ ] Mobile app (React Native)
- [ ] Advanced features (reminders, etc.)
- [ ] Integration with official city APIs

## 🤝 Contributing

Contributions are welcome! This is an early-stage project with lots of opportunities to help.

### How to Contribute

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/your-feature`
3. **Make your changes**
4. **Add tests** (when test suite is set up)
5. **Commit**: `git commit -m "Add your feature"`
6. **Push**: `git push origin feature/your-feature`
7. **Open a Pull Request**

### Areas Needing Help

- Database schema refinement
- API development
- Frontend development
- Testing and quality assurance
- Documentation improvements
- Data collection for new cities

## 📄 License

[To be determined - recommend MIT or Apache 2.0]

## 💬 Contact

- **Project Lead**: [Your Name]
- **Email**: [your-email@example.com]
- **GitHub Issues**: [https://github.com/yourusername/TrashAlert/issues](https://github.com/yourusername/TrashAlert/issues)

## 🙏 Acknowledgments

- **OpenStreetMap**: For providing free, open address data
- **PostGIS**: For powerful geospatial database capabilities
- **FastAPI**: For the excellent Python web framework
- **Community Contributors**: Everyone who reports trash days!

---

**Note**: This is a pilot project. Schedules may not be 100% accurate. Always verify with your local waste management provider for official information.
