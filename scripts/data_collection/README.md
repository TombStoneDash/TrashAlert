# Trash Schedule Extraction Engine

This module provides a modular, extensible system for extracting trash collection schedules from various city sources (PDFs, HTML, APIs) and storing them in a normalized database format.

## Overview

The schedule extraction engine implements a complete pipeline:

```
City Source → Fetch → Parse → Normalize → Store in DB
```

### Key Features

- **Modular parsers**: One parser per city, easily extensible
- **Multiple source types**: PDF, HTML, API support
- **Normalized output**: Consistent data format across all cities
- **Holiday exceptions**: Handles rescheduled and cancelled pickups
- **Next pickup calculation**: Automatic calculation of upcoming pickup dates
- **Data validation**: Built-in validation and quality checks

## Architecture

### Directory Structure

```
scripts/data_collection/
├── schedule_parsers/
│   ├── __init__.py
│   ├── base_parser.py          # Base class and data models
│   ├── el_centro_parser.py     # El Centro parser
│   ├── imperial_parser.py      # Imperial parser
│   └── san_diego_parser.py     # San Diego parser
├── schedule_runner.py           # Unified runner script
├── validate_schedules.py        # Validation and demo
└── README.md                    # This file
```

### Database Schema

**schedules** table:
- `id`: Primary key
- `address_id`: Link to addresses table (nullable for pilot)
- `day_of_week`: MON, TUE, WED, THU, FRI, SAT, SUN
- `collection_type`: trash, recycling, green_waste, bulk
- `zone`: Pickup zone identifier (if city uses zones)
- `recurrence`: weekly, biweekly, monthly
- `source_id`: Link to source_metadata
- `confidence`: 0.0 - 1.0 confidence score
- `effective_date`: When schedule becomes effective

**schedule_exceptions** table:
- `id`: Primary key
- `schedule_id`: Link to schedules table
- `exception_date`: Holiday/exception date
- `rescheduled_date`: New pickup date (if rescheduled)
- `is_cancelled`: True if cancelled, not rescheduled
- `reason`: e.g., "Christmas", "Thanksgiving"

**source_metadata** table:
- `id`: Primary key
- `city`: City name
- `source_type`: pdf, html, api, manual
- `source_url`: URL where data was obtained
- `parser_name`: Name of parser used
- `total_records_extracted`: Count of records
- `extra_data`: JSON metadata

## Usage

### Running All Parsers

Extract schedules from all supported cities:

```bash
python scripts/data_collection/schedule_runner.py --all
```

### Running a Specific Parser

Extract schedules for one city:

```bash
python scripts/data_collection/schedule_runner.py --city "El Centro"
```

### Dry Run (Testing)

Test parsers without writing to database:

```bash
python scripts/data_collection/schedule_runner.py --all --dry-run
```

### Validation

Validate extracted data and see examples:

```bash
python scripts/data_collection/validate_schedules.py
```

## Creating a New Parser

To add a parser for a new city:

### 1. Create Parser File

Create `scripts/data_collection/schedule_parsers/your_city_parser.py`:

```python
from .base_parser import (
    BaseScheduleParser,
    ScheduleData,
    ExceptionData,
    ParseResult
)

class YourCityParser(BaseScheduleParser):
    def __init__(self):
        super().__init__(
            city="Your City",
            source_url="https://yourcity.gov/trash"
        )

    def fetch_raw_data(self):
        # Fetch data from source (PDF, HTML, API, etc.)
        return raw_data

    def parse_raw_data(self, raw_data):
        # Parse and return ParseResult
        result = ParseResult()

        # Create schedules
        schedule = ScheduleData(
            address="Your City, Zone A",
            day_of_week="MON",
            collection_type="trash",
            zone="ZONE_A",
            recurrence="weekly",
            confidence=0.95
        )
        result.schedules.append(schedule)

        return result
```

### 2. Register Parser

Add to `schedule_runner.py`:

```python
from scripts.data_collection.schedule_parsers.your_city_parser import YourCityParser

# In ScheduleRunner.__init__:
self.parsers = {
    "El Centro": ElCentroParser,
    "Imperial": ImperialParser,
    "San Diego": SanDiegoParser,
    "Your City": YourCityParser,  # Add here
}
```

### 3. Test Parser

```bash
python scripts/data_collection/schedule_runner.py --city "Your City" --dry-run
```

## Parser Implementation Examples

### El Centro (Zone-Based)

El Centro uses zones with different schedules for different areas:

```python
# Zone A: Monday trash, Wednesday recycling
# Zone B: Tuesday trash, Thursday recycling
# etc.
```

The parser includes a `match_address_to_zone()` method that uses street names or GIS data to determine the zone.

### Imperial (Citywide)

Imperial uses a simple citywide schedule - all addresses have the same pickup days:

```python
# All addresses: Tuesday trash, Friday recycling
```

The parser extracts data from an HTML table on the city website.

### San Diego (Neighborhood-Based)

San Diego uses neighborhood-based schedules with multiple zones:

```python
# Downtown: Monday trash
# La Jolla: Tuesday trash
# Pacific Beach: Wednesday trash
# etc.
```

The parser can extract from PDF calendars (production) or use simulated data (pilot).

## Data Flow

### 1. Fetch Phase
```python
raw_data = parser.fetch_raw_data()
# Returns: PDF content, HTML, JSON, etc.
```

### 2. Parse Phase
```python
result = parser.parse_raw_data(raw_data)
# Returns: ParseResult with schedules, exceptions, metadata
```

### 3. Store Phase
```python
runner.store_results(city, result)
# Writes to database: schedules, schedule_exceptions, source_metadata
```

## Validation

The validation script checks:

- ✓ Required fields populated
- ✓ Valid day_of_week values (MON-SUN)
- ✓ Valid collection_type values
- ✓ Confidence scores in range (0-1)
- ✓ Next pickup date calculations
- ✓ Exception data integrity

## Current Implementation Status

### Pilot Version (v1.0)

**Implemented:**
- ✓ 3 working parsers (El Centro, Imperial, San Diego)
- ✓ Database models and migration scripts
- ✓ Unified runner script
- ✓ Data validation
- ✓ Next pickup date calculation
- ✓ Holiday exception handling

**Limitations (Pilot):**
- Parsers use simulated data (not live fetching)
- Schedules not linked to specific addresses yet
- No OCR for image-based PDFs
- Simple zone matching (not GIS-based)

### Production Roadmap

**Phase 2:**
- Link schedules to actual addresses from database
- Implement live data fetching (HTTP requests)
- Add GIS-based zone matching
- OCR support for image PDFs (pytesseract)

**Phase 3:**
- API integration for schedule lookup
- Automatic schedule updates (scheduled jobs)
- Conflict detection and resolution
- Performance optimization for large cities

## Database Query Examples

### Get schedules for a city

```python
from app.database import SessionLocal
from app.models import Schedule, SourceMetadata

db = SessionLocal()

# Find El Centro schedules
source = db.query(SourceMetadata).filter_by(city="El Centro").first()
schedules = db.query(Schedule).filter_by(source_id=source.id).all()

for schedule in schedules:
    print(f"{schedule.zone}: {schedule.collection_type} on {schedule.day_of_week}")
```

### Get holiday exceptions

```python
from app.models import ScheduleException
from datetime import datetime

# Find Christmas exceptions
christmas = datetime(2025, 12, 25)
exceptions = db.query(ScheduleException).filter_by(
    exception_date=christmas
).all()

for exc in exceptions:
    if exc.rescheduled_date:
        print(f"Rescheduled to: {exc.rescheduled_date}")
    elif exc.is_cancelled:
        print("Cancelled")
```

## Performance Considerations

### Current Performance
- El Centro: 12 schedules, 3 exceptions (~0.1s)
- Imperial: 3 schedules, 2 exceptions (~0.05s)
- San Diego: 24 schedules, 5 exceptions (~0.15s)
- **Total: 39 schedules, 10 exceptions in < 1 second**

### Optimization Tips
- Use database indexes on frequently queried fields
- Batch insert operations for large datasets
- Cache parsed data to avoid re-fetching
- Use connection pooling for concurrent parsers

## Error Handling

Parsers handle errors gracefully:

```python
result = ParseResult()

try:
    # Fetch and parse
    raw_data = self.fetch_raw_data()
    # ... parsing logic ...
except Exception as e:
    result.errors.append(f"Parse failed: {e}")

return result
```

Errors are logged and included in the result object, so partial failures don't crash the entire pipeline.

## Dependencies

Required packages (see `requirements.txt`):

```
# PDF parsing
PyPDF2>=3.0.0
pdfplumber>=0.10.0
pytesseract>=0.3.10
Pillow>=10.0.0

# Web scraping
beautifulsoup4>=4.12.0
lxml>=5.0.0

# Database
sqlalchemy>=2.0.25

# Utilities
requests>=2.31.0
pyyaml>=6.0.0
```

## Testing

Run validation suite:

```bash
# Full validation
python scripts/data_collection/validate_schedules.py

# Run with verbose output
python scripts/data_collection/schedule_runner.py --all --verbose
```

## Contributing

To add a new parser:
1. Create parser file following the examples
2. Inherit from `BaseScheduleParser`
3. Implement `fetch_raw_data()` and `parse_raw_data()`
4. Register in `schedule_runner.py`
5. Test with `--dry-run`
6. Validate with validation script

## Support

For questions or issues:
- Check parser logs for detailed error messages
- Review validation output for data quality issues
- See `base_parser.py` for interface documentation
- Refer to existing parsers for implementation examples
