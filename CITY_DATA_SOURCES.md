# City Data Sources — 14-City Import Batch

Documents every data source researched for the sprint's 14-city import batch.
Each script lives at `scripts/import-<city>.mjs` and follows the pattern of
`scripts/import-charlotte.mjs` (ArcGIS pagination → zone polygon centroid →
Supabase upsert into `schedule_reports`).

## Summary

| # | City | State | Status | Data source |
|---|------|-------|--------|-------------|
| 1 | Indianapolis     | IN | ✅ ready | ArcGIS MapServer |
| 2 | Baltimore        | MD | ✅ ready | ArcGIS FeatureServer (street segments) |
| 3 | Albuquerque      | NM | ✅ ready | ABQ GIS MapServer |
| 4 | Tucson           | AZ | ✅ ready | Tucson ArcGIS MapServer |
| 5 | Kansas City      | MO | ✅ ready | KCMO PublicWorks MapServer |
| 6 | Jacksonville     | FL | ✅ ready | ArcGIS FeatureServer |
| 7 | Columbus         | OH | ✅ existing | See `import-columbus.mjs` (already imported) |
| 8 | Louisville       | KY | ✅ ready | Louisville Open Data FeatureServer |
| 9 | Milwaukee        | WI | ✅ ready | Milwaukee DPW MapServer (layers 3–7) |
| 10 | Pittsburgh      | PA | ⚠️ non-ArcGIS | pgh.st REST API (WPRDC-backed) |
| 11 | LA County       | CA | ✅ ready | LA County FeatureServer (unincorporated only) |
| 12 | Miami-Dade      | FL | ✅ ready | ArcGIS FeatureServer (garbage + recycling) |
| 13 | Mesa            | AZ | ❌ placeholder | No public FeatureServer found |
| 14 | Raleigh         | NC | ❌ placeholder | Hub exists; specific URL not surfaced |

## Details

### 1. Indianapolis, IN — `import-indianapolis.mjs`
- **Endpoint:** `https://gis.indy.gov/server/rest/services/InforPS/InforPS/MapServer/29`
- **Fields:** `HAULER, ROUTE_NO, DISTRICT, DAY, HVYTRASHDA, RC_HAULER, RC_DAY`
- **Records:** ~485 collection zones
- **Approach:** Import one row per zone per service type (GARB via `DAY`, RECY via `RC_DAY`).

### 2. Baltimore, MD — `import-baltimore.mjs`
- **Endpoint:** `https://services3.arcgis.com/bpeS3swje8g57sok/arcgis/rest/services/Trash/FeatureServer/0`
- **Fields:** `TRASH_RT, TRASH_DAY, RECYCL_DAY, BIN_COLOR, STR_NAME, STR_TYPE, PREFIX_DIR, LEFT_FROM, LEFT_TO, RIGHT_FROM, RIGHT_TO`
- **Records:** 1,940 street segments with address ranges
- **Approach:** Expand `LEFT_FROM..LEFT_TO` (even) and `RIGHT_FROM..RIGHT_TO` (odd) into individual houses; cap 100 houses/segment to prevent runaway.

### 3. Albuquerque, NM — `import-albuquerque.mjs`
- **Endpoint:** `https://abqgis01.cabq.gov/arcgis/rest/services/ABQData/SolidWaste/MapServer/0`
- **Fields:** `Pickup_Day`
- **Records:** 9 collection-day zones
- **Approach:** Centroid per polygon; one row per zone.

### 4. Tucson, AZ — `import-tucson.mjs`
- **Endpoint:** `https://mapdata.tucsonaz.gov/arcgis/rest/services/IT/ZoomTucson/MapServer/56`
- **Fields:** `BBArea, ServiceDates, CollWeek (A/B), DOS, PRIMARY_RT`
- **Records:** 238 brush/bulky + 131 recycling
- **Approach:** Use `DOS`/`ServiceDates` for weekday, `CollWeek` for A/B recycling cycle.

### 5. Kansas City, MO — `import-kansas-city.mjs`
- **Endpoint:** `https://mapd.kcmo.org/kcgis/rest/services/PublicWorks/TrashDay/MapServer/0`
- **Fields:** `TRASHDAY`
- **Records:** 303 zones
- **Approach:** Single service type, one row per zone.

### 6. Jacksonville, FL — `import-jacksonville.mjs`
- **Endpoint:** `https://services1.arcgis.com/NXfNVaFp7QMxnE3j/arcgis/rest/services/All_WP_Changes_2022/FeatureServer/23`
- **Fields:** `COMPANY (CITY/WP/MW), DISTRICT, GarbDay, RecyDay, YardDay, BulkDay`
- **Records:** 97 zones
- **Approach:** Import one row per service type (garbage / recycling / yard) per district, with correct hauler name (City / Waste Pro / Meridian Waste).

### 7. Columbus, OH — `import-columbus.mjs` (pre-existing)
- **Endpoint:** `https://maps2.columbus.gov/arcgis/rest/services/Applications/Neighborhood/MapServer/24`
- **Fields:** `UNIT_NAME` (direct day codes MON–FRI + color codes GOLD / GRAY / NAVY / PINK / RUBY)
- **Records:** 15,678 refuse + 13,301 recycling
- **Note:** Script already existed at start of sprint; see `scripts/import-columbus-note.md`.

### 8. Louisville, KY — `import-louisville.mjs`
- **Endpoint:** `https://services1.arcgis.com/79kfd2K6fskCAkyg/ArcGIS/rest/services/OpenDataJeflib/FeatureServer/21`
- **Fields:** `SRA_GARB, SRA_DAY, SRA_ROUTE`
- **Records:** ~50–100 sanitation route areas
- **Approach:** One row per SRA route.

### 9. Milwaukee, WI — `import-milwaukee.mjs`
- **Endpoint:** `https://milwaukeemaps.milwaukee.gov/arcgis/rest/services/DPW/DPW_Sanitation/MapServer`
- **Layer → day mapping:** 3=Mon, 4=Tue, 5=Wed, 6=Thu, 7=Fri
- **Records:** ~442 route polygons across the five day layers
- **Approach:** Iterate each day layer, assign the corresponding weekday to all rows.

### 10. Pittsburgh, PA — `import-pittsburgh.mjs`
- **Primary API:** `http://www.pgh.st/api/data/location` (JSON blocks with `street`, `house_number_from/to`, `collection_day`)
- **Schema:** `http://www.pgh.st/api/data/location/schema`
- **Fallback portal:** `https://pghgishub-pittsburghpa.opendata.arcgis.com/` (WPRDC — likely holds the ArcGIS version but specific FeatureServer URL was not confirmed)
- **Approach:** Fetch block list, expand each block's house-number range (cap 50/block).
- **Caveat:** `pgh.st` is community-maintained — if down, swap in WPRDC endpoint.

### 11. LA County, CA — `import-la-county.mjs`
- **Endpoint:** `https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/Los_Angeles_County_Waste_Service_Collection_Areas_view/FeatureServer/0`
- **Fields:** `AREA_NAME, WASTE_HAUL, PICKUP_DAY`
- **Records:** 239 collection areas
- **Scope:** LA County **unincorporated** areas only. The City of LA (LASAN) has no public API — covered separately.

### 12. Miami-Dade, FL — `import-miami-dade.mjs`
- **Endpoints:**
  - Garbage: `https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/GarbagePickupRoute_gdb/FeatureServer/0`
  - Recycling: `https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/RecyclingZone_gdb/FeatureServer/0`
- **Fields:** `ROUTE, COLLDAY, WEEKDAYS, WCSAREA, TYPE`
- **Records:** 783 garbage routes + recycling zones
- **Approach:** Iterate both endpoints, parse `COLLDAY` / first token of `WEEKDAYS` (e.g., `"MON/THU"` → monday).

### 13. Mesa, AZ — `import-mesa.mjs` (PLACEHOLDER)
- **Searched:**
  - `https://opengis.mesaaz.gov/` — Mesa Open GIS portal (no waste layer)
  - `https://gis.mesaaz.gov/Html5Viewer/` — viewer only, private proxy
  - `https://www.mesaaz.gov/Utilities/Trash-Recycling` — address-lookup tool
  - ArcGIS Hub search for "mesa solid waste" — no match
- **Why it failed:** Mesa runs an internal GIS that powers the Html5Viewer widget but doesn't publish the solid-waste layer publicly.
- **Next step:** Inspect XHR calls on the Html5Viewer to discover the backing URL, or request access from Solid Waste Division (480-644-6789).

### 14. Raleigh, NC — `import-raleigh.mjs` (PLACEHOLDER)
- **Searched:**
  - `https://data-ral.opendata.arcgis.com/` — Open Data Raleigh (no direct match in first page)
  - `https://raleighnc.gov/apps-maps-and-open-data` — portal index
  - NCSU's curated Raleigh GIS list
- **Why it failed:** The hub likely hosts the route layer, but it was not surfaced by a quick keyword search. Further manual search, or a direct ping to `gisadmin@raleighnc.gov`, is needed.
- **Next step:** Grep the ArcGIS Hub for "Collection", "Solid Waste", "Sanitation", "Yard Waste"; model after `import-charlotte.mjs` once the URL is confirmed.

## Running the scripts

```bash
# From the repo root, with .env.local containing:
#   NEXT_PUBLIC_SUPABASE_URL=...
#   SUPABASE_SERVICE_KEY=...
node --env-file=.env.local scripts/import-indianapolis.mjs
node --env-file=.env.local scripts/import-baltimore.mjs
# ...etc
```

Each script is idempotent: it upserts on `(address, city)` so re-running will
not duplicate rows. All records are written to the `schedule_reports` table
with `source='city_api'` and the endpoint URL in `data_source_url`.
