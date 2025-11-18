# Trash Schedule Import Scripts

This directory contains scripts for fetching and importing official trash collection schedules from various cities.

## Overview

The TrashAlert system prioritizes official schedule data from city sources. This directory contains city-specific scripts that:
1. Fetch schedule data from official sources
2. Parse and normalize the data
3. Import into the `source_metadata` and update `Address` records with official schedules

## Current Cities

### El Centro, CA
- **Script:** `fetch_el_centro_schedule.py`
- **Provider:** CR&R Environmental Services
- **Official Site:** https://www.cityofelcentro.org/1299/Trash-Recycling
- **Contact:** 760-337-4505
- **Status:** Sample data (needs real schedule verification)

**To Run:**
```bash
python scripts/schedules/fetch_el_centro_schedule.py
```

**Data Source Notes:**
- El Centro uses zone-based collection
- Collection starts at 6 AM
- Holiday schedule: If holiday falls on weekday, collection delayed by one day
- Bulky item pickup: 3 free pickups per year (4 items per pickup)

**TODO for Production:**
- Obtain official zone maps from city or CR&R
- Match addresses to zones using GIS data or street boundaries
- Verify zone schedules with CR&R

### San Diego, CA
- **Script:** `fetch_san_diego_schedule.py`
- **Provider:** City of San Diego Environmental Services
- **Official Site:** https://www.sandiego.gov/environmental-services/collection/schedule
- **Lookup Tool:** https://getitdone.sandiego.gov/CollectionMapLookup
- **Contact:** 858-694-7000
- **Status:** Sample data (needs real schedule verification)

**To Run:**
```bash
python scripts/schedules/fetch_san_diego_schedule.py
```

**Data Source Notes:**
- San Diego uses route-based collection
- Serves ~225,000 residential customers
- Collection: Monday-Friday, 6 AM - 5:30 PM
- Automated curbside: trash, recycling, organic waste (all same day)
- Holiday schedule causes one-day delay for remainder of week

**TODO for Production:**
- Request API access to GetItDone lookup system
- Obtain route boundary GIS data
- Batch lookup addresses through official lookup tool
- Import 2025 holiday schedule to `schedule_exceptions` table

## Database Schema

### source_metadata Table
Tracks where schedule data comes from:
- `city`: City identifier (e.g., "imperial_el_centro")
- `source_type`: Type of source (pdf, html, api, manual)
- `source_url`: Official URL
- `parser_name`: Script that processed the data
- `extra_data`: JSON metadata

### Address Model Updates
Official schedule fields in the `addresses` table:
- `official_trash_day`: MON, TUE, WED, THU, FRI, SAT, SUN
- `official_recycling_day`: Same format
- `official_green_day`: Same format

These fields are used by the `/lookup` endpoint with priority:
1. **CROWD_VERIFIED**: Verified crowdsourced consensus
2. **OFFICIAL**: Official schedule data (from these scripts)
3. **CROWD_UNVERIFIED**: Unverified crowdsourced data
4. **UNKNOWN**: No data available

## Adding a New City

To add schedule support for a new city:

1. **Create a new script:** `fetch_<city_name>_schedule.py`
2. **Research data sources:**
   - Official city website
   - Waste service provider
   - GIS data availability
   - API access possibilities

3. **Implement the script:**
   ```python
   def get_or_create_source_metadata(db):
       # Create source_metadata record
       pass

   def import_schedules(db, source_id):
       # Import schedule data
       # Update Address records with official_*_day fields
       pass

   def main():
       # Entry point
       pass
   ```

4. **Update this README** with city details

5. **Test the import:**
   ```bash
   python scripts/schedules/fetch_<city_name>_schedule.py
   ```

## Data Quality

### Sample Data vs. Real Data
Currently, both El Centro and San Diego scripts use **sample data** because:
- Official websites block automated scraping (403 errors)
- No public APIs available yet
- GIS zone/route data not yet obtained

### Verification Checklist
Before marking schedules as production-ready:
- [ ] Verify schedule data with official city source
- [ ] Confirm zone/route boundaries are accurate
- [ ] Test with random address samples
- [ ] Validate holiday exception handling
- [ ] Document data freshness (last updated date)

## Future Improvements

1. **API Integration:**
   - Request official API access from cities
   - Implement automated refresh schedules
   - Add authentication/rate limiting

2. **GIS Integration:**
   - Import zone/route boundary shapefiles
   - Implement spatial matching of addresses to zones
   - Use PostGIS for efficient geo queries

3. **Scraping (with permission):**
   - Implement ethical web scraping with proper headers
   - Respect robots.txt
   - Cache results to minimize requests
   - Add retry logic with exponential backoff

4. **Data Validation:**
   - Cross-reference with crowdsourced data
   - Flag discrepancies for manual review
   - Track confidence scores

5. **Holiday Handling:**
   - Import city holiday calendars
   - Calculate rescheduled pickup dates
   - Update `schedule_exceptions` table
   - Provide next pickup date API

## Maintenance

### Regular Tasks
- **Monthly:** Check for schedule changes on official city websites
- **Quarterly:** Re-run import scripts to refresh data
- **Annually:** Update holiday calendars
- **As Needed:** Add support for new cities

### Monitoring
- Track source metadata update timestamps
- Alert if data becomes stale (>90 days)
- Monitor import success/failure rates
- Log data quality issues

## Contact

For questions about schedule imports or to report data issues:
- Check GitHub issues
- Review city-specific official sources
- Contact city waste management departments directly
