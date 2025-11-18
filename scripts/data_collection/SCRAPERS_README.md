# Automated Schedule Scraper Framework

This document describes the automated schedule scraper framework for Imperial Valley cities and how to use, maintain, and extend it.

## Overview

The scraper framework automatically fetches trash collection schedules from city websites and imports them into the TrashAlert database. It supports multiple Imperial Valley cities with a unified architecture.

## Supported Cities

All 5 Imperial Valley cities now have scrapers:

1. **El Centro** - Zone-based (4 zones) - CR&R Waste Services
2. **Imperial** - Citywide schedule - Republic Services
3. **Holtville** - Citywide schedule - CR&R Environmental Services
4. **Brawley** - Zone-based (4 zones) - Republic Services
5. **Calexico** - Zone-based (6 zones) - Allied Waste Services (Republic Services)

## Architecture

### Components

1. **Base Parser** (`base_parser.py`) - Abstract base class that all scrapers inherit from
2. **City Parsers** - Individual parser for each city
3. **Schedule Runner** (`schedule_runner.py`) - Orchestrates all parsers
4. **Schedules Importer** (`schedules_importer.py`) - Handles data import with duplicate detection
5. **Tests** - Comprehensive test suite with mocked HTML

### Data Flow

```
City Website → Parser.fetch_raw_data() → HTML/JSON
                                             ↓
                            Parser.parse_raw_data() → ParseResult
                                             ↓
                            SchedulesImporter → Database
```

## Usage

### Running All Scrapers

```bash
# Dry run (no database writes)
python scripts/data_collection/schedule_runner.py --all --dry-run

# Import all schedules
python scripts/data_collection/schedule_runner.py --all

# Verbose output
python scripts/data_collection/schedule_runner.py --all --verbose
```

### Running a Single City

```bash
# Dry run for specific city
python scripts/data_collection/schedule_runner.py --city "El Centro" --dry-run

# Import for specific city
python scripts/data_collection/schedule_runner.py --city "Holtville"
```

### Using the Importer

```bash
# Import with duplicate detection (default)
python scripts/data_collection/schedules_importer.py --all

# Allow duplicates
python scripts/data_collection/schedules_importer.py --all --allow-duplicates

# Import specific city
python scripts/data_collection/schedules_importer.py --city "Brawley"
```

## Parser Implementation

### Creating a New Parser

To add a new city parser:

1. **Create parser file** in `schedule_parsers/`:

```python
from .base_parser import BaseScheduleParser, ScheduleData, ParseResult

class NewCityParser(BaseScheduleParser):
    def __init__(self):
        super().__init__(
            city="New City",
            source_url="https://city.gov/trash"
        )

    def fetch_raw_data(self):
        """Fetch from city website or use fallback."""
        try:
            response = requests.get(self.source_url)
            return {"html": response.text}
        except:
            return self._get_fallback_html()

    def parse_raw_data(self, raw_data):
        """Parse HTML and return ParseResult."""
        result = ParseResult()
        # Parse schedules and exceptions
        return result
```

2. **Register in schedule_runner.py**:

```python
from .new_city_parser import NewCityParser

self.parsers = {
    # ...
    "New City": NewCityParser,
}
```

3. **Add tests** in `tests/test_schedule_scrapers.py`

### Parser Methods

**Required:**
- `fetch_raw_data()` - Fetch data from source (HTML, PDF, API)
- `parse_raw_data(raw_data)` - Parse data into ScheduleData and ExceptionData

**Inherited from BaseScheduleParser:**
- `normalize_day(day)` - Convert day names to codes (MON, TUE, etc.)
- `normalize_collection_type(type)` - Normalize collection types
- `calculate_next_pickup(day)` - Calculate next pickup date
- `run()` - Execute full pipeline (fetch + parse)

## Data Models

### ScheduleData

```python
ScheduleData(
    address="City, Zone",
    day_of_week="MON",  # MON, TUE, WED, THU, FRI, SAT, SUN
    collection_type="trash",  # trash, recycling, green_waste
    zone="ZONE_A",  # Optional zone identifier
    recurrence="weekly",  # weekly, biweekly, monthly
    confidence=0.95,  # 0.0-1.0
    effective_date=datetime(2025, 1, 1),
    next_pickup_date=datetime(2025, 1, 6)
)
```

### ExceptionData

```python
ExceptionData(
    exception_date=datetime(2025, 12, 25),
    rescheduled_date=datetime(2025, 12, 26),
    is_cancelled=False,
    reason="Christmas",
    notes="Holiday schedule change"
)
```

### ParseResult

```python
ParseResult(
    schedules=[ScheduleData, ...],
    exceptions=[ExceptionData, ...],
    metadata={
        "total_schedules": 12,
        "source_format": "html",
        "parser_version": "1.0.0"
    },
    errors=[],
    warnings=[]
)
```

## Features

### 1. Automatic Fallback

All parsers attempt to fetch live data but gracefully fall back to hardcoded schedules if:
- Website is down (connection error)
- Website blocks scraper (403 Forbidden)
- HTML structure has changed

### 2. Duplicate Detection

The `SchedulesImporter` prevents duplicate schedules:
- Checks for existing schedules by city, zone, collection type, and day
- Updates if new data has higher confidence
- Skips if schedule already exists
- Can be disabled with `--allow-duplicates` flag

### 3. Re-import Safety

Re-running imports is safe:
- First import: Creates schedules
- Subsequent imports: Skips duplicates or updates with better data
- No need to clean database between runs

### 4. Zone Matching

Parsers support two models:

**Citywide** (Imperial, Holtville):
- Single schedule applies to all addresses

**Zone-based** (El Centro, Brawley, Calexico):
- Different schedules per zone
- `match_address_to_zone()` method assigns zones
- Currently uses heuristics (street names)
- TODO: Implement GIS polygon matching

## Testing

### Run All Tests

```bash
# Run all scraper tests
pytest tests/test_schedule_scrapers.py -v

# Run importer tests
pytest tests/test_schedules_importer.py -v

# Run specific test
pytest tests/test_schedule_scrapers.py::TestElCentroParser::test_parse_raw_data -v
```

### Test Structure

Tests use mocked HTML responses:
- No live network requests
- Fast and reliable
- Tests all parsers comprehensively

## Schedule Information by City

### El Centro
- **Service Provider:** CR&R Waste Services
- **Schedule Type:** Zone-based (4 zones)
- **URL:** https://crrwasteservices.com/cities/california/imperial-county/city-of-el-centro/residents/
- **Notes:** Zones ABCD with different collection days

### Imperial
- **Service Provider:** Republic Services
- **Schedule Type:** Citywide
- **URL:** https://www.cityofimperial.org/trash-recycling
- **Schedule:**
  - Trash: Tuesday (Weekly)
  - Recycling: Friday (Biweekly)
  - Green Waste: Tuesday (Weekly)

### Holtville
- **Service Provider:** CR&R Environmental Services
- **Schedule Type:** Citywide
- **URL:** https://crrwasteservices.com/cities/california/imperial-county/holtville/
- **Schedule:**
  - Trash: Tuesday (Weekly)
  - Recycling: Friday (Biweekly)
  - Green Waste: Tuesday (Weekly)

### Brawley
- **Service Provider:** Republic Services (760-355-0004)
- **Schedule Type:** Zone-based (4 zones)
- **URL:** https://www.republicservices.com/municipality/brawley-ca
- **Notes:** Zones 1-4 covering North, East, South, West areas

### Calexico
- **Service Provider:** Allied Waste Services (Republic Services) (760-768-2100)
- **Schedule Type:** Zone-based (6 zones)
- **URL:** https://www.calexico.ca.gov/trash-recycling
- **Features:** Three-can system (trash, recycling, green waste)
- **Hours:** Collections 5:00 AM - 8:00 PM, Monday-Saturday
- **Notes:** 6 zones covering different areas of the city

## Success Criteria ✓

All success criteria have been met:

- ✅ All 5 Imperial Valley cities have scrapers
- ✅ Scrapers use requests and beautifulsoup4
- ✅ Individual scraper files per city
- ✅ Standardized output via schedules_importer.py
- ✅ Data stored in schedules table
- ✅ Comprehensive tests with mocked HTML
- ✅ Re-import works without creating duplicates

## Future Enhancements

1. **GIS Zone Matching**
   - Replace heuristic zone matching with GIS polygon lookups
   - Integrate with pickup_zones table geometry

2. **Playwright Integration**
   - For cities with JavaScript-rendered content
   - Add playwright to requirements.txt
   - Implement in parser.fetch_raw_data()

3. **Scheduled Updates**
   - Cron job or scheduled task
   - Automatic weekly/monthly re-scraping
   - Email notifications on changes

4. **OCR Support**
   - For PDF schedules with images
   - Already have pytesseract in requirements

5. **API Integration**
   - Direct API calls where available
   - More reliable than HTML scraping

## Troubleshooting

### Parser Returns No Schedules

Check:
1. Website URL is correct
2. HTML structure hasn't changed
3. Fallback data is properly formatted
4. Run with `--verbose` to see detailed logs

### Import Fails

Check:
1. Database connection is working
2. Required tables exist (run migrations)
3. City model has required fields (name, slug)
4. Run with `--dry-run` first to test

### Tests Fail

Check:
1. All dependencies installed (`pip install -r requirements.txt`)
2. Mock HTML fixtures are valid
3. Models match test expectations

## Maintenance

### Regular Tasks

1. **Verify Schedules** (Monthly)
   - Check city websites for schedule changes
   - Update fallback data if needed

2. **Update Holidays** (Annually)
   - Add new year's holidays
   - Update exception dates in parsers

3. **Monitor Errors** (Weekly)
   - Check logs for parsing errors
   - Update HTML selectors if sites change

## Contact & Support

For issues or questions about the scraper framework:
1. Check this README
2. Review test files for usage examples
3. Check parser source code for implementation details
4. Review base_parser.py for available methods

## File Structure

```
scripts/data_collection/
├── schedule_parsers/
│   ├── __init__.py
│   ├── base_parser.py           # Base class
│   ├── el_centro_parser.py      # El Centro scraper
│   ├── imperial_parser.py       # Imperial scraper
│   ├── holtville_parser.py      # Holtville scraper (NEW)
│   ├── brawley_parser.py        # Brawley scraper (NEW)
│   ├── calexico_parser.py       # Calexico scraper (NEW)
│   └── san_diego_parser.py      # San Diego scraper
├── schedule_runner.py           # Orchestrator
├── schedules_importer.py        # Importer with duplicate detection (NEW)
├── validate_schedules.py        # Validation utilities
└── SCRAPERS_README.md           # This file

tests/
├── test_schedule_scrapers.py    # Parser tests (NEW)
└── test_schedules_importer.py   # Importer tests (NEW)
```
