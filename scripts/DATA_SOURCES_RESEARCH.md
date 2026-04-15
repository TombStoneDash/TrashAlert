# ArcGIS Data Sources Research — Top 20 US Cities

Researched: 2026-04-15

## Overview

Survey of the top 20 US cities by population for publicly accessible ArcGIS REST
endpoints that expose trash/garbage collection route or schedule data.

**Result:** 4 new cities identified with usable ArcGIS endpoints (in addition to
10 cities already covered by existing import scripts).

---

## Cities with existing import scripts

| # | City | Pop Rank | Script | Endpoint type |
|---|------|----------|--------|---------------|
| 1 | New York City, NY | 1 | `import-nyc.mjs` | Socrata / City API |
| 2 | Chicago, IL | 3 | `import-chicago.mjs` | ArcGIS |
| 3 | Houston, TX | 4 | `import-houston.mjs` | ArcGIS (address-level) |
| 4 | Phoenix, AZ | 5 | `import-phoenix.mjs` | ArcGIS |
| 5 | Philadelphia, PA | 6 | `import-philadelphia.mjs` | ArcGIS |
| 6 | San Antonio, TX | 7 | `import-san-antonio.mjs` | ArcGIS |
| 7 | Dallas, TX | 9 | `import-dallas.mjs` | ArcGIS (zone+address spatial join) |
| 8 | Austin, TX | 11 | `import-austin.mjs` | ArcGIS |
| 9 | San Francisco, CA | 17 | `import-san-francisco.mjs` | ArcGIS |
| 10 | Denver, CO | 19 | `import-denver.mjs` | ArcGIS |

Also covered (outside top 20): Boston, Portland.

---

## NEW: Cities with confirmed ArcGIS endpoints

### Columbus, OH (Pop rank #14)

- **Endpoint:** `https://maps2.columbus.gov/arcgis/rest/services/Applications/Neighborhood/MapServer/24`
- **Layer name:** Refuse Colordays
- **Geometry:** Polygon (zone boundaries)
- **Key fields:**
  - `UNIT_NAME` (String) — collection day/color code: MON, TUE, WED, THU, FRI, GOLD, GRAY, NAVY, PINK, RUBY, DAILY
- **Notes:** Columbus uses a "color day" system. Day-of-week values (MON–FRI) map
  directly. Color values (GOLD, GRAY, NAVY, PINK, RUBY) represent day rotations
  assigned to neighborhoods. DAILY = daily collection areas.
- **Hauler:** City of Columbus, Division of Refuse Collection
- **Data type:** Zone polygons (no address-level data in this layer)
- **Import approach:** Query zone polygons, extract centroid + collection day

### Fort Worth, TX (Pop rank #13)

- **Endpoint:** `https://mapitwest.fortworthtexas.gov/ags/rest/services/CodeComp/SolidWaste/MapServer`
- **Key layers:**
  - Layer 3: Garbage Route — `Route` (Double), `Contractor` (String), `Weekday` (String)
  - Layer 40: Garbage Route Zones — `Route`, `Zone`, `Weekday`
  - Layer 0: Solid Waste View — `StreetAddress`, `CFWLAND_ID` (no collection day)
- **Geometry:** Polygon (route/zone boundaries)
- **Key fields:**
  - `Weekday` — MON, TUE, WED, THU, FRI
  - `Contractor` — WM (Waste Management)
  - `Route` — route number (101, 102, etc.)
- **Hauler:** Waste Management (contractor for City of Fort Worth)
- **Data type:** Route zone polygons with weekday assignment
- **Import approach:** Query route zones from layer 3, extract centroid + weekday

### Charlotte, NC (Pop rank #15)

- **Endpoint:** `https://services.arcgis.com/9Nl857LBlQVyzq54/arcgis/rest/services/Solid_Waste_Collection/FeatureServer/0`
- **Layer name:** Solid Waste Collection
- **Geometry:** Polygon (route boundaries)
- **Key fields:**
  - `WORK_DAY` (String) — MON, TUE, WED, THU, FRI
  - `ROUTE_TYPE` (String) — GARB (garbage), RECY (recycling), YARD (yard waste)
  - `SERVED_BY` (String) — hauler name (e.g., "WASTE MANAGEMENT")
  - `ROUTE_NAME` (String) — route identifier
  - `ROUTE_NOTE` (String) — e.g., "THU Collection for Recycling on ORANGE week"
  - `UNIT_COUNT` (SmallInteger) — units served by route
  - `WORK_ZONE` (String) — zone category (RECYCLING, GARBAGE, etc.)
- **Hauler:** Waste Management (contracted)
- **Data type:** Route polygons by service type with day assignment
- **Import approach:** Filter ROUTE_TYPE=GARB for garbage collection zones,
  extract centroid + work_day. Recycling week derivable from ROUTE_NOTE.

### Seattle, WA (Pop rank #18)

- **Garbage Routes:** `https://services.arcgis.com/ZOyb2t4B0UYuYNYH/arcgis/rest/services/Residential_Garbage_Routes/FeatureServer/0`
- **Recycle Routes:** `https://services.arcgis.com/ZOyb2t4B0UYuYNYH/arcgis/rest/services/Residential_Recycle_Routes/FeatureServer/0`
- **Yard Waste Routes:** `https://services.arcgis.com/ZOyb2t4B0UYuYNYH/arcgis/rest/services/Residential_Food_and_Yard_Waste_Routes/FeatureServer/3`
- **Layer name:** Residential Garbage Routes
- **Geometry:** Polygon (route boundaries)
- **Key fields:**
  - `PCKUP_DAY` (String) — pickup day: MON, TUE, WED, THU, FRI
  - `CONTRACTOR` (String) — RECOLOGY, WM
  - `CNTR_DESC` (String) — full contractor name (e.g., "RECOLOGY CLEANSCAPES")
  - `ZONE` (String) — zone code (G1, G2, etc.)
  - `ROUTE_ID` (String) — route identifier
- **Haulers:** Recology Cleanscapes, Waste Management
- **Data type:** Route zone polygons with pickup day and contractor
- **Import approach:** Query garbage routes, extract centroid + pickup day

---

## Cities with NO public ArcGIS REST endpoint for collection schedules

### Los Angeles, CA (Pop rank #2)

- **Status:** No public ArcGIS REST API for collection schedules
- **What exists:** LASAN (LA Sanitation) provides a Collection Day Finder web tool
  and sanitation maintenance district boundaries on GeoHub (geohub.lacity.org).
  However, these are district boundaries only — no collection day/schedule data
  is exposed via a queryable REST endpoint.
- **Alternative:** LASAN web lookup tool at sanitation.lacity.gov

### San Diego, CA (Pop rank #8)

- **Status:** No public ArcGIS REST API for collection schedules
- **What exists:** City operates ArcGIS services at webmaps.sandiego.gov but no
  waste collection layers. Residential Waste Collection Services Portal
  (wasteportal.sandiego.gov) and Collection Schedule Lookup
  (getitdone.sandiego.gov/CollectionMapLookup) are proprietary web apps.
- **Alternative:** Web scraping of getitdone.sandiego.gov lookup tool

### San Jose, CA (Pop rank #10)

- **Status:** No public ArcGIS REST API for collection schedules
- **What exists:** Waste collection handled by private franchised haulers
  (Republic Services, GreenTeam). City provides a Utility Services Lookup tool
  but no public GIS data for collection routes.
- **Alternative:** Per-hauler scraping or Republic Services API

### Jacksonville, FL (Pop rank #12)

- **Status:** No public ArcGIS REST API for collection schedules
- **What exists:** Three private haulers (Advanced Disposal, Meridian Waste,
  Waste Pro) serve different districts. JaxGIS My Neighborhood app shows pickup
  days but behind a proprietary web interface. Solid Waste Issue Search at
  maps.coj.net/careswsearch is CRM-focused.
- **Alternative:** Scraping coj.net/swschedule lookup tool

### Indianapolis, IN (Pop rank #16)

- **Status:** No public ArcGIS REST API for collection schedules
- **What exists:** GIS infrastructure at gis.indy.gov and xmaps.indy.gov with
  InforPS, IMPD, and Accela services — none contain waste collection data.
  Solid Waste Districts page on indy.gov provides static district info.
- **Alternative:** Contact DPW for data access

### Nashville, TN (Pop rank #20)

- **Status:** No public ArcGIS REST API for collection schedules
- **What exists:** ArcGIS server at maps.nashville.gov with 31 folders covering
  cadastral, planning, boundaries, etc. — no waste/refuse folder or service.
  Open data portal (datanashvillegov-nashville.hub.arcgis.com) has convenience
  center locations but no collection zones.
- **Alternative:** Scraping Nashville Waste & Recycling App address lookup

---

## Summary table

| # | City | Pop Rank | ArcGIS endpoint? | Status |
|---|------|----------|-------------------|--------|
| 1 | New York City | 1 | Yes (existing) | `import-nyc.mjs` |
| 2 | Los Angeles | 2 | **No** | LASAN web app only |
| 3 | Chicago | 3 | Yes (existing) | `import-chicago.mjs` |
| 4 | Houston | 4 | Yes (existing) | `import-houston.mjs` |
| 5 | Phoenix | 5 | Yes (existing) | `import-phoenix.mjs` |
| 6 | Philadelphia | 6 | Yes (existing) | `import-philadelphia.mjs` |
| 7 | San Antonio | 7 | Yes (existing) | `import-san-antonio.mjs` |
| 8 | San Diego | 8 | **No** | Proprietary portal |
| 9 | Dallas | 9 | Yes (existing) | `import-dallas.mjs` |
| 10 | San Jose | 10 | **No** | Private haulers |
| 11 | Austin | 11 | Yes (existing) | `import-austin.mjs` |
| 12 | Jacksonville | 12 | **No** | Private haulers / web lookup |
| 13 | Fort Worth | 13 | **Yes (NEW)** | `import-fort-worth.mjs` |
| 14 | Columbus | 14 | **Yes (NEW)** | `import-columbus.mjs` |
| 15 | Charlotte | 15 | **Yes (NEW)** | `import-charlotte.mjs` |
| 16 | Indianapolis | 16 | **No** | No GIS waste data |
| 17 | San Francisco | 17 | Yes (existing) | `import-san-francisco.mjs` |
| 18 | Seattle | 18 | **Yes (NEW)** | `import-seattle.mjs` |
| 19 | Denver | 19 | Yes (existing) | `import-denver.mjs` |
| 20 | Nashville | 20 | **No** | No ArcGIS waste services |

**Coverage: 14 / 20 cities** (10 existing + 4 new)
