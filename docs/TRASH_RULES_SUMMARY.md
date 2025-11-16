# Trash Pickup Rules Research Summary

## Overview
This document summarizes the trash pickup rules, zones, and GIS data availability for all six pilot cities in the TrashAlert project.

**Research Date**: January 2025
**Pilot Cities**: El Centro, Brawley, Imperial, Calexico, Holtville, San Diego

---

## Quick Reference Table

| City | Provider | Zone System | GIS Data | Interactive Map | Priority for Data Acquisition |
|------|----------|-------------|----------|-----------------|-------------------------------|
| **El Centro** | CR&R | Zone-based (day lookup) | Potentially available | ✅ Yes | High - map exists, request shapefile |
| **Brawley** | Republic Services | Unknown zones | Unknown | ❌ No | Medium - contact city/provider |
| **Imperial** | Republic Services | **NONE** - Citywide Wednesday | Not needed | ❌ No | **Low - uniform schedule** |
| **Calexico** | Republic Services | Mon-Sat (6 zones likely) | Unknown | ❌ No | Medium - contact city/provider |
| **Holtville** | CR&R | Zone-based (contact for day) | Unknown | ❌ No | Medium - contact CR&R |
| **San Diego** | City ESD | Zone-based (Mon-Fri) | Potentially available | ✅ Yes | High - map exists, SanGIS access |

---

## Implementation Recommendations by City

### 🟢 Imperial (Easiest)
**Status**: Ready to implement
**Pickup Schedule**:
- All services: **Wednesday** (citywide)
- Trash, recycling, green waste all collected together

**Implementation**:
```python
if city == "Imperial":
    trash_day = "Wednesday"
    recycling_day = "Wednesday"
    green_waste_day = "Wednesday"
```

**Action Required**: Verify schedule hasn't changed for 2025 (call city to confirm)

---

### 🟡 El Centro (Interactive Map Available)
**Status**: Map exists, need zone data
**Service Provider**: CR&R Environmental Services
**Interactive Map**: https://www.cityofelcentro.org/1316/Street-Sweeping

**Implementation Options**:
1. **Request GIS shapefile**: Contact City Environmental Compliance (760-337-4538)
2. **API/Web scraping**: Reverse-engineer interactive map if it has public API
3. **Manual mapping**: Query map with sample addresses to build zone database

**Next Steps**:
- [ ] Contact city to request zone shapefile
- [ ] Investigate if interactive map has queryable API
- [ ] Test map with sample addresses from our dataset

---

### 🟡 San Diego (Complex but Data Available)
**Status**: Lookup tool exists, GIS data potentially available
**Service Provider**: City Environmental Services Department
**Interactive Lookup**: https://getitdone.sandiego.gov/CollectionMapLookup

**Collection Schedule**:
- Trash: Weekly (Mon-Fri)
- Recycling: Bi-weekly (Mon-Fri)
- Organic waste: Weekly (Mon-Fri)
- Zone assignment determines specific day

**Data Sources**:
1. **SanGIS Regional Data Warehouse** (requires free registration)
   - URL: https://rdw.sandag.org/
   - 419+ layers of regional GIS data
   - Free shapefiles after registration
   - Contact: GISTeam@sandag.org

2. **City Open Data Portal**
   - URL: https://data.sandiego.gov/
   - Has street sweeping schedule dataset
   - Trash zones not confirmed in public catalog

3. **Direct Request**
   - Contact: trash@sandiego.gov or (858) 694-7000
   - Request collection zone shapefile

**Implementation Options**:
1. **Register for SanGIS**: Browse data warehouse for collection zones
2. **Request from city**: Email/call Environmental Services for zone data
3. **Reverse-engineer**: Query lookup tool with sample addresses
4. **Public records request**: Formal request if data exists but not published

**Next Steps**:
- [ ] Register for SanGIS Regional Data Warehouse
- [ ] Browse available layers for waste collection zones
- [ ] Contact Environmental Services to request zone data
- [ ] Test lookup tool with sample addresses

---

### 🟡 Brawley, Calexico, Holtville (Contact Required)
**Status**: No public zone data found, must contact providers

#### Brawley
- **Provider**: Republic Services (877-732-9253)
- **City Contact**: Public Works (760-344-5800)
- **Next Steps**: Request zone map and schedule

#### Calexico
- **Provider**: Republic Services
- **City Contact**: Public Works (760-768-2160)
- **Schedule**: Mon-Sat collection window (likely 6 zones)
- **Next Steps**: Request zone boundaries and day assignments

#### Holtville
- **Provider**: CR&R (877-482-5656)
- **City Contact**: Utilities department
- **Next Steps**: Request zone map from CR&R or city

---

## GIS Data Resources

### Imperial County GIS Data Portal
- **URL**: https://gis-imperialcounty.opendata.arcgis.com/datasets
- **Coverage**: El Centro, Brawley, Imperial, Calexico, Holtville
- **Access**: Free, public
- **Status**: Portal exists, specific trash zone data not confirmed
- **Action**: Browse portal for any municipal service zones

### SanGIS Regional Data Warehouse (San Diego)
- **URL**: https://rdw.sandag.org/
- **URL**: https://www.sangis.org/download/
- **Coverage**: San Diego city and county
- **Data**: 419+ layers, compressed shapefiles
- **Access**: Free with registration
- **Contact**: GISTeam@sandag.org (technical), webmaster@sangis.org (data questions)
- **Action**: Register and search for waste collection zones

### California State Resources
- **State Geoportal**: https://gis.data.ca.gov/
- **SCAG (Southern California)**: Covers Imperial and San Diego counties
- **CNRA**: https://gis.data.cnra.ca.gov/

---

## Holiday Schedules

### CR&R Cities (El Centro, Holtville)
Observed holidays: New Year's, Memorial Day, July 4th, Labor Day, Thanksgiving, Christmas
- Weekend holiday → no delay
- Weekday holiday → rest of week delayed by 1 day

### Republic Services Cities (Brawley, Imperial, Calexico)
Likely similar policy, confirm with provider

### San Diego (City ESD)
2025 Holidays:
- January 1 (Wed) - New Year's
- May 26 (Mon) - Memorial Day
- July 4 (Fri) - Independence Day
- September 1 (Mon) - Labor Day
- November 27 (Thu) - Thanksgiving
- December 25 (Thu) - Christmas

Holiday policy: Collection delayed 1 day for rest of week

---

## Implementation Priority

### Phase 1: Quick Win ✅
**City**: Imperial
**Why**: Uniform citywide schedule (Wednesday), no zone mapping needed
**Effort**: Minimal - just city name matching
**Action**: Verify schedule, implement simple rule

### Phase 2: Interactive Maps 🗺️
**Cities**: El Centro, San Diego
**Why**: Interactive lookup tools exist, underlying data likely available
**Effort**: Medium - request GIS data or reverse-engineer maps
**Action**:
1. Request shapefiles from cities
2. Register for SanGIS (San Diego)
3. Investigate map APIs

### Phase 3: Provider Contact 📞
**Cities**: Brawley, Calexico, Holtville
**Why**: No public zone data, must contact providers
**Effort**: Medium-High - depends on provider cooperation
**Action**:
1. Call/email each provider
2. Request zone maps and schedules
3. Manually digitize if necessary

---

## Data Gaps & Next Actions

### Immediate Actions
- [ ] **Imperial**: Call city to verify Wednesday schedule for 2025
- [ ] **El Centro**: Request zone shapefile from Environmental Compliance
- [ ] **San Diego**: Register for SanGIS data warehouse
- [ ] **San Diego**: Email Environmental Services for zone data
- [ ] **Imperial County GIS**: Browse portal for municipal service zones

### Follow-up Actions
- [ ] **Brawley**: Contact Public Works for zone map
- [ ] **Calexico**: Contact Public Works for zone map
- [ ] **Holtville**: Contact CR&R for zone map
- [ ] Test interactive maps with sample addresses
- [ ] If no GIS data available, consider manual zone mapping

### Fallback Strategy
If GIS data unavailable for a city:
1. Use address lookup tools to build database
2. Query with all addresses in our sample dataset
3. Extract zone/day mappings
4. Build custom zone database from results

---

## Technical Notes

### Zone Data Requirements
For each city, we need to map addresses to:
- `trash_zone` (identifier)
- `trash_day_of_week`
- `recycling_day_of_week` (if different)
- `green_waste_day_of_week` (if different)

### Data Format Preferences
1. **Shapefile** (.shp) - polygons defining geographic zones
2. **GeoJSON** - same as shapefile but web-friendly
3. **CSV/Table** - address-to-zone lookup table
4. **API** - interactive lookup service

### Integration Approach
1. **GIS polygons**: Point-in-polygon matching (address → lat/lon → zone)
2. **Lookup tables**: Direct address matching
3. **API services**: Real-time queries (may have rate limits)

---

## Contact Information Summary

| Entity | Contact | Purpose |
|--------|---------|---------|
| El Centro Environmental Compliance | (760) 337-4538 | Zone shapefile request |
| CR&R (El Centro/Holtville) | (877) 482-5656 | Schedule and zone info |
| Brawley Public Works | (760) 344-5800 | Zone map request |
| Imperial City | Contact via website | Verify Wednesday schedule |
| Calexico Public Works | (760) 768-2160 | Zone map request |
| Republic Services | (877) 732-9253 | Zone info for Brawley/Calexico/Imperial |
| San Diego Environmental Services | (858) 694-7000<br>trash@sandiego.gov | Zone data request |
| SanGIS GIS Team | GISTeam@sandag.org | Data warehouse technical support |
| SanGIS Data Questions | webmaster@sangis.org | Dataset questions |
| Imperial County Planning GIS | (442) 265-1736<br>planninginfo@co.imperial.ca.us | County GIS data |

---

## Conclusion

**Data Availability Status**:
- ✅ **1 city** (Imperial) ready to implement immediately
- 🟡 **2 cities** (El Centro, San Diego) have interactive maps - good chance of obtaining GIS data
- ⚠️ **3 cities** (Brawley, Calexico, Holtville) require direct provider contact

**Recommended Approach**:
1. Start with Imperial (uniform schedule)
2. Obtain GIS data for El Centro and San Diego (maps exist)
3. Contact providers for remaining cities
4. Use fallback address-lookup approach if GIS data unavailable

**Estimated Timeline**:
- Imperial: 1 day (verify schedule)
- El Centro/San Diego: 1-2 weeks (data requests)
- Brawley/Calexico/Holtville: 2-4 weeks (provider coordination)

All six cities are feasible for pilot implementation, though some will require more effort to obtain zone data than others.
