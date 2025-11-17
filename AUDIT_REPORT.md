# TrashAlert Repository Code Audit Report

**Date**: 2025-11-17
**Auditor**: Claude (Automated Code Audit)
**Scope**: Full repository audit before scaling features

---

## Executive Summary

This audit identified **17 critical issues** across database schema inconsistencies, API duplication, missing error handling, broken imports, and performance risks. The repository has **3 separate API implementations** with conflicting database schemas that will cause runtime failures.

**Critical Findings**:
- ❌ **3 conflicting database schemas** (SQLite vs SQLAlchemy ORM)
- ❌ **3 different API entry points** with incompatible models
- ❌ **Multiple normalization implementations** with different logic
- ❌ Missing validation, error handling, and exception management
- ❌ Broken paths and import inconsistencies
- ⚠️ Performance risks: unindexed queries, large OSM fetches without pagination

---

## 1. CRITICAL: Multiple Conflicting Database Schemas

### Issue
The repository has **3 different database schema definitions** that are incompatible:

#### Schema 1: `scripts/init_database.py` (Lines 32-107)
```sql
- cities (city_id, city_name, state)
- subdivisions (subdivision_id, city_id, subdivision_name)
- addresses (address_id, city_id, subdivision_id, house_number, street, lat, lon, osm_id)
- address_pickup_info (id, address_id, city_id, pickup_zone_id, trash_day_of_week, recycling_day_of_week, green_waste_day_of_week, source)
```

#### Schema 2: `scripts/init_database.py` (Lines 179-223)
```sql
- addresses_normalized (id, city_name, house_number, street, normalized_address, lat, lon, osm_id, subdivision_id)
- address_pickup_info (id, address_id, trash_day_of_week, recycling_day_of_week, green_waste_day_of_week)
```

#### Schema 3: `app/models.py` (Lines 7-78)
```python
- addresses (id, normalized_address, house_number, street, city, state, zip_code, lat, lon, official_trash_day, official_recycling_day, official_green_day)
- crowd_reports (id, address_id, trash_day, recycling_day, green_day, user_hash, ip_address)
- crowd_consensus (id, address_id, consensus_trash_day, consensus_recycling_day, consensus_green_day, ...)
```

#### Schema 4: `src/models.py` (Lines 14-33)
```python
- addresses (id, house_number, street, city, subdivision_id, lat, lon, normalized_address, trash_day_of_week, osm_id)
```

### Impact
- **RUNTIME FAILURES**: Scripts expecting one schema will fail with another
- **DATA LOSS**: Incompatible column names prevent data migration
- **API FAILURES**: APIs query non-existent tables/columns

### Affected Files
- `scripts/init_database.py` (has TWO schemas in one file!)
- `app/models.py`
- `src/models.py`
- `init_db.py`
- All scripts querying database

---

## 2. CRITICAL: Three Separate API Implementations

### Issue
The repository contains **3 complete API implementations** with conflicting routes and models:

#### API 1: `src/api.py`
- Entry point: `uvicorn src.api:app`
- Database: `src/models.py` (SQLAlchemy ORM)
- Routes: `POST /lookup`, `GET /lookup/{id}`, `GET /health`
- Uses: SQLAlchemy sessions with `src.models.Address`

#### API 2: `app/main.py`
- Entry point: `uvicorn app.main:app`
- Database: `app/models.py` (SQLAlchemy ORM with crowdsourcing)
- Routes: `POST /report`, `GET /lookup`, `GET /stats`
- Uses: SQLAlchemy sessions with `app.models.Address`, `CrowdReport`, `CrowdConsensus`

#### API 3: `api/main.py`
- Entry point: `uvicorn api.main:app`
- Database: `api/database.py` (raw SQLite3)
- Routes: `GET /lookup`, `GET /health`
- Uses: Raw SQL queries against `addresses_normalized` table

### Impact
- **CONFUSION**: Unclear which API is the "production" version
- **DEPLOYMENT FAILURES**: Different APIs expect different schemas
- **MAINTENANCE BURDEN**: Bug fixes must be applied to 3 separate codebases
- **TESTING FAILURES**: `test_api.py` and tests expect different endpoints

### Affected Files
- `src/api.py`
- `app/main.py`
- `api/main.py`
- `test_api.py` (expects `app.main`)
- `tests/test_api_lookup.py` (expects `src.api`)

---

## 3. CRITICAL: Schema Mismatches in Scripts

### Issue: `scripts/init_database.py` defines TWO schemas

**Lines 18-127**: Function `init_database()` creates Schema A:
- Tables: `cities`, `subdivisions`, `addresses`, `address_pickup_info`
- Uses foreign keys: `city_id`

**Lines 174-226**: Function `create_tables()` creates Schema B:
- Tables: `addresses_normalized`, `address_pickup_info`
- NO cities table, uses `city_name` string instead

### Impact
- **SCRIPT FAILURE**: Running `init_database()` then `create_tables()` causes conflicts
- **DATA CORRUPTION**: Two different `address_pickup_info` tables with different schemas

### Fix Required
Remove duplicate schema definitions. Choose ONE canonical schema.

---

## 4. Missing Error Handling and Validation

### 4.1 API Validation Issues

#### `api/main.py:114` - Missing address validation
```python
def parse_address_components(address: str) -> Tuple[str, str, str]:
    # No validation if address is empty or malformed
```
- **Impact**: Empty addresses cause crashes
- **Fix**: Add input validation

#### `app/main.py:199` - Incorrect source labeling
```python
# Line 199: Bug - unverified consensus labeled as "CROWD_VERIFIED"
source = "CROWD_VERIFIED"  # Should be "CROWD_UNVERIFIED"
```
- **Impact**: Users get false confidence in unverified data
- **Fix**: Use correct source label

#### `src/api.py:108` - No validation on normalized address
```python
normalized = normalize_address(request.address)
# If normalization returns empty string, query will fail
query = db.query(Address).filter(Address.normalized_address == normalized)
```

### 4.2 Missing Exception Handling in Scripts

#### `scripts/normalize_addresses.py:206`
```python
float(addr['lat']) if addr['lat'] else None
# No try/except for ValueError if lat is malformed
```

#### `scripts/fetch_addresses_osm.py:71`
```python
response = requests.post(overpass_url, data={'data': query}, timeout=120)
response.raise_for_status()
# No retry logic despite comment in run_full_pipeline.py
```

#### `scripts/link_addresses_to_pickup_zones.py:66`
```python
with open(geojson_path, 'r') as f:
    geojson = json.load(f)
# No handling for malformed JSON
```

---

## 5. Broken Imports and Path Issues

### 5.1 Circular Dependencies Risk
- `src/api.py` imports `src.models`, `src.normalization`
- `api/main.py` imports `api.models`, `api.database`, `api.normalization`
- If scripts try to import from wrong module, silent failures occur

### 5.2 Duplicate Normalization Logic

**Three separate implementations**:
1. `src/normalization.py` (normalize_address) - USPS abbreviations
2. `api/normalization.py` (normalize_address) - Lowercase style
3. `app/utils.py` (normalize_address) - Returns dict
4. `scripts/normalize_addresses.py` (normalize_street_name) - Different logic

**Impact**: Same address normalizes differently depending on which module is used
- Example: "Main Street" → "MAIN ST" (src) vs "main st" (api) vs dict (app)

### 5.3 Missing Requirements

`requirements.txt` has **duplicate entries**:
```
Line 4: fastapi==0.109.0
Line 14: fastapi==0.109.0

Line 5: uvicorn[standard]==0.27.0
Line 15: uvicorn[standard]==0.27.0

Line 6: pydantic==2.5.3
Line 17: pydantic==2.5.3
```

Missing for some scripts:
- `pyyaml` (required by `scripts/config_utils.py:6`)
- `shapely` (required by `scripts/link_addresses_to_pickup_zones.py:19`)
- `geopy` (required by `app/utils.py:6`)

---

## 6. Database Query Issues

### 6.1 Queries Against Non-Existent Tables

#### `api/database.py:59` queries `addresses_normalized`:
```python
cursor.execute("""
    SELECT ... FROM addresses_normalized a
    LEFT JOIN address_pickup_info p ON a.id = p.address_id
""")
```
- **Problem**: `addresses_normalized` only exists if `create_tables()` in `init_database.py:174` was called
- **Problem**: JOIN assumes `address_pickup_info.address_id` exists, but Schema A uses `address_pickup_info.id` as PK

#### `app/main.py:138` queries app schema:
```python
addr_record = db.query(Address).filter(
    Address.normalized_address == normalized
).first()
```
- **Problem**: Assumes `app.models.Address` table exists
- **Problem**: No error handling if table doesn't exist

### 6.2 Missing Indexes

#### `scripts/init_database.py` creates indexes, but not all needed
Missing indexes on:
- `addresses.osm_id` (used in lookups)
- `addresses_normalized.lat, lon` (used in fuzzy matching)
- `crowd_reports.created_at` (for time-based queries)

---

## 7. Performance Risks

### 7.1 Unindexed Full Table Scans

#### `api/database.py:79-111` - Fuzzy matching on entire table
```python
cursor.execute("""
    SELECT ... FROM addresses_normalized a
    WHERE a.city_name LIKE ?
""")
rows = cursor.fetchall()

for row in rows:
    score = calculate_similarity(normalized_address, row['normalized_address'])
```
- **Impact**: O(n) string comparison for every address in city
- **Fix**: Use spatial index or pre-filter by street name

### 7.2 Large OSM Fetches Without Pagination

#### `scripts/fetch_addresses_osm.py:59-67`
```python
query = f"""
    [out:json][timeout:90];
    area[name="{city_name}"]["admin_level"~"^(8|9)$"]->.city;
    (
      node["addr:housenumber"](area.city);
      way["addr:housenumber"](area.city);
    );
    out center;
    """
```
- **Problem**: No limit on result size
- **Problem**: 90-second timeout may not be enough for large cities
- **Impact**: San Diego could have 100k+ addresses, causing OOM or timeout
- **Fix**: Add pagination or spatial chunking

### 7.3 No Connection Pooling

All database access uses single connections, no pooling configured for concurrent requests.

---

## 8. Dead Code and Unused Files

### Unused/Orphaned Files
- `init_db.py` - Seems to be old version of initialization (uses `app.models`)
- `api/__init__.py` - Empty, possibly leftover
- `app/__init__.py` - Empty
- `src/__init__.py` - Empty

### Unreachable Code
- `src/models.py:35-51` - `create_database()` function never called in main API
- `scripts/normalize_addresses.py:274-293` - `show_schema()` defined but only called in main

---

## 9. Security Issues

### 9.1 SQL Injection Risk (Low - Using Parameterized Queries)
All SQL uses parameterized queries (✓), but:

#### `scripts/fetch_addresses_osm.py:59`
```python
query = f"""
    area[name="{city_name}"]
```
- **Risk**: If city_name from untrusted source, could inject Overpass QL
- **Current**: city_name comes from YAML config (safe)

### 9.2 No Rate Limiting
- `app/main.py:/report` endpoint has no rate limiting
- **Impact**: Spam/abuse of crowdsourced reporting
- **Fix**: Add rate limiting (tracks IP via `request.client.host`)

---

## 10. Test Coverage Gaps

### 10.1 Test Files Incompatible with APIs

- `tests/test_api_lookup.py` imports `src.api` but uses `src.models` schema
- `test_api.py` expects `app.main` with crowdsourcing schema
- **Result**: Can't run both test files against same database

### 10.2 Missing Tests
- No tests for `api/main.py` (the SQLite version)
- No tests for normalization edge cases
- No tests for error conditions (500 errors, DB connection failures)
- No tests for crowdsourcing consensus calculation

---

## 11. Missing Functionality

### 11.1 No Migration Scripts
- No Alembic or migration tool configured
- Schema changes require manual SQL or DB recreation
- **Risk**: Production data loss during schema updates

### 11.2 No Health Checks for DB
- APIs have `/health` endpoints but don't verify DB connectivity
- **Example** `api/main.py:47-71` - tries to query DB but catches exception generically

---

## 12. Configuration Issues

### 12.1 Hardcoded Paths

#### `scripts/normalize_addresses.py:298-300`
```python
csv_input = 'data/addresses_sampled_50_per_city.csv'
csv_output = 'data/addresses_normalized.csv'
db_path = 'data/trashpilot.db'
```
- **Problem**: Hardcoded relative paths
- **Impact**: Scripts fail if run from different directory

#### `api/database.py:11`
```python
DB_PATH = Path(__file__).parent.parent / 'data' / 'trashalert.db'
```

#### `app/database.py:7`
```python
SQLALCHEMY_DATABASE_URL = "sqlite:///./trashalert.db"
```
- **Inconsistency**: Different DB filenames (`trashpilot.db` vs `trashalert.db`)

---

## 13. Documentation Gaps

### Missing Documentation
- No API documentation (beyond OpenAPI auto-generated)
- No schema documentation
- No data model ER diagrams
- `docs/data_model.md` exists but may be outdated

---

## Recommended Fixes (Priority Order)

### P0 - Critical (Blocking Issues)

1. **Consolidate Database Schema**
   - Choose ONE schema (recommend `app/models.py` as most complete)
   - Remove duplicate schema definitions in `scripts/init_database.py`
   - Create migration script from old schemas

2. **Choose ONE API**
   - Deprecate `src/api.py` and `api/main.py`
   - Standardize on `app/main.py` (has crowdsourcing features)
   - Update documentation and tests

3. **Fix Schema Mismatches**
   - Update all scripts to use chosen schema
   - Add validation to ensure DB schema matches expected version

4. **Fix requirements.txt**
   - Remove duplicates
   - Add missing dependencies (`pyyaml`, `shapely`)
   - Pin all versions

### P1 - High (Data Integrity)

5. **Add Input Validation**
   - Validate all API inputs (address not empty, days are valid)
   - Add try/except for type conversions (lat/lon floats)
   - Return proper HTTP error codes (400 for validation, 500 for server errors)

6. **Fix Bug in app/main.py:199**
   - Change source label for unverified consensus

7. **Consolidate Normalization**
   - Choose ONE normalization implementation
   - Move to shared module (e.g., `src/normalization.py`)
   - Update all imports

### P2 - Medium (Performance & Maintenance)

8. **Add Database Indexes**
   - Index on `addresses.normalized_address`
   - Index on `crowd_reports.address_id`
   - Index on `addresses.lat, lon` for spatial queries

9. **Add Pagination to OSM Fetches**
   - Chunk large cities by bounding boxes
   - Add retry logic with exponential backoff

10. **Remove Dead Code**
    - Delete unused initialization files
    - Remove unreachable functions

### P3 - Low (Quality of Life)

11. **Add Migration Tool**
    - Set up Alembic for schema migrations
    - Create initial migration from current schemas

12. **Improve Health Checks**
    - Verify DB connectivity in `/health` endpoints
    - Return DB statistics

13. **Fix Hardcoded Paths**
    - Use environment variables or config file
    - Make all paths relative to project root

---

## Files Requiring Immediate Attention

| File | Issues | Priority |
|------|--------|----------|
| `scripts/init_database.py` | Duplicate schemas | P0 |
| `app/main.py` | Bug at line 199 | P1 |
| `requirements.txt` | Duplicates, missing deps | P0 |
| `api/database.py` | Wrong table names | P0 |
| `src/api.py` | Deprecated API | P0 |
| `api/main.py` | Deprecated API | P0 |
| `scripts/fetch_addresses_osm.py` | No pagination | P2 |
| `api/database.py` | Unindexed fuzzy search | P2 |
| All normalization files | Inconsistent logic | P1 |

---

## Conclusion

The repository is **NOT PRODUCTION READY** in its current state. Critical schema inconsistencies and multiple conflicting API implementations will cause runtime failures. Before scaling:

1. ✅ Consolidate to single database schema
2. ✅ Choose one API implementation
3. ✅ Fix all P0 and P1 issues
4. ✅ Add comprehensive error handling
5. ✅ Update tests to match chosen architecture

**Estimated effort**: 2-3 days for P0 fixes, 5-7 days for full stabilization.

---

## Appendix: File Inventory

### API Files (3 implementations)
- `src/api.py` - SQLAlchemy API
- `app/main.py` - Crowdsourcing API
- `api/main.py` - SQLite API

### Model Files (4 implementations)
- `src/models.py`
- `app/models.py`
- `api/models.py`
- `scripts/init_database.py` (inline schema)

### Database Files
- `app/database.py`
- `api/database.py`
- `init_db.py`
- `scripts/init_database.py`
- `scripts/init_sample_database.py`
- `scripts/create_database.py`

### Normalization Files (4 implementations)
- `src/normalization.py`
- `api/normalization.py`
- `app/utils.py`
- `scripts/normalize_addresses.py`

### Test Files
- `test_api.py` - Integration tests for `app.main`
- `tests/test_api_lookup.py` - Unit tests for `src.api`
- `tests/test_normalization.py`
- `tests/test_spatial_joins.py`

### Scripts (19 files)
All in `scripts/` directory - see file listing above.

---

**End of Audit Report**
