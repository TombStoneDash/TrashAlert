# San Diego CA — Coverage Probe BLOCKED
**Date:** 2026-05-30  
**Batch:** batch-3-may30  
**City:** San Diego, CA  
**State:** BLOCKED — data auth-gated, no public GIS polygons available

---

## Sources Probed

### 1. data.sandiego.gov (City Open Data Portal)
- 110 datasets catalogued — **no trash/recycling collection zone GIS dataset** present
- Searched for: trash, collection, refuse, collection-routes, collection-zones, collection-schedules
- All returned 404 — dataset slug does not exist on the portal

### 2. webmaps.sandiego.gov ArcGIS REST Server
- Server exists and responds (ArcGIS 11.5)
- Folders identified: `GetItDone`, `GetItDone311`, `ESD`, `SEPS`, `TSD`, `DSD`, `Planning`
- **ALL folders in GetItDone/ESD namespaces return HTTP 499 "Token Required"**
- Specifically probed (all 499):
  - `GetItDone/` folder root
  - `GetItDone311/` folder root
  - `ESD/CollectionZones/MapServer`
  - `GetItDone/GarbageRoutes/MapServer`
- No public unauthenticated access to collection zone polygons

### 3. SanGIS (sangis.org / arcgis.sangis.org)
- `arcgis.sangis.org` — DNS does not resolve (ENOTFOUND)
- `sangis.org/SanGIS-Open-Data.html` — pure JavaScript SPA, no extractable data via static fetch
- No collection zone data accessible

### 4. ArcGIS Online (arcgis.com)
- Searched for `city_of_san_diego` owner + "collection trash" — 0 results
- Searched for "san diego collection zones trash recycling" — 0 results
- No public layers published to ArcGIS Online

### 5. GetItDone / Collection Map Lookup (public app)
- URL: https://getitdone.sandiego.gov/CollectionMapLookup
- **Address-based lookup only** — enter an address, get next pickup date
- No bulk zone polygon download available
- Underlying ArcGIS service is auth-gated
- Private hauler areas (HOAs, multi-unit) explicitly excluded from city service

### 6. sdgis-sandag.opendata.arcgis.com
- SANDAG open data hub — no trash/garbage collection zone datasets found

---

## What IS Available (for future reference)
- **Address-level lookup**: https://getitdone.sandiego.gov/CollectionMapLookup (public, address-by-address only)
- **Service phone**: 858-694-7000 (Environmental Services Dept)
- **Collection schedule**: Mon–Fri, trash + organics weekly, recycling biweekly
- **City collects for**: residential addresses within city limits that don't have private hauler (HOAs excluded)
- **No publicly downloadable zone polygon data confirmed as of 2026-05-30**

---

## Recommended Next Steps
1. **File a public records / open data request** with SD Environmental Services at 858-694-7000 or via sandiego.gov/environmental-services
2. **FOIA/PRA request** for the collection route shapefile (Public Records Act §6250)
3. **Browser automation** of the GetItDone address lookup to enumerate zones by sampling grid points across the city (labor-intensive, rate-limited, no guarantee of polygon boundaries)
4. **Contact SanGIS directly**: info@sangis.org — they may have an authenticated data sharing agreement option

---

## Conclusion
San Diego's garbage/recycling collection zone polygons exist (they power the GetItDone map) but are locked behind ArcGIS authentication. No open data equivalent is published. This city requires a data partnership or PRA request to extract zone boundaries.
