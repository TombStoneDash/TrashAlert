# City Gap Research — Phase C (2026-04-20)

Priority metros not yet imported. Sourced from Phase C research sweep;
each entry lists the authoritative data source (when one exists) and
the coverage approach. Ranked from "easiest to import now" to "needs
investigation".

## Tier 1 — ready to import (direct ArcGIS endpoints confirmed)

### Durham, NC ✅ (importer added — see `import-zone-polygons.mjs` → `durham-sw`)
- **Source:** ArcGIS MapServer, Layer 6
- **URL:** `https://webgis2.durhamnc.gov/server/rest/services/PublicServices/Administrative/MapServer/6`
- **Shape:** polygon zones (weekly trash; recycling biweekly same day)
- **Run:** `node --env-file=.env.local scripts/import-zone-polygons.mjs durham-sw`

### Anaheim, CA
- **Source:** ArcGIS Hub — "Trash Collection Days"
- **Dataset:** `https://data-anaheim.opendata.arcgis.com/datasets/e175b466cf1e477aac6a68c637ac642a_15`
- **Shape:** polygon zones (Mon/Tue/Fri)
- **Next step:** Click "View API" on the dataset page to extract the
  FeatureServer URL, then add a SOURCES entry analogous to durham-sw.
- **Provider note:** Republic Services contract (city-managed data).

### Detroit, MI
- **Source:** City data hub — "Trash, Recycling, Bulk Pick Up Zones"
- **Dataset:** `https://data.detroitmi.gov/datasets/trash-recycling-bulk-pick-up-zones`
- **Shape:** polygon zones (weekly since June 2024)
- **Next step:** Follow the GeoService link on the dataset page to get
  the FeatureServer query URL; small feature count.
- **Provider note:** Priority Waste (east/SW) + Advance & GFL (others).

### Orlando, FL
- **Source:** `services3.arcgis.com/bpeS3swje8g57sok/arcgis/rest/services/Trash/FeatureServer`
- **Shape:** **per-street polylines** (address-range matching) + zone polygons for recycling
- **Fields:** `TRASH_RT`, `TRASH_DAY`, `RECYCL_DAY`, `LEFT_FROM/TO`, `RIGHT_FROM/TO`, `STR_NAME`, `PREFIX_DIR`
- **Complexity:** higher — polyline geometry with from/to address ranges means per-address expansion. Warrants its own importer.

## Tier 2 — ArcGIS-backed but endpoint needs network trace

| City | App / portal | Notes |
|---|---|---|
| Rochester, NY | `arcgis.com/apps/InformationLookup/?appid=f1053106ec0b4e6d8b4b4dd326de7d33` | Polygon zones, Red/Blue week recycling. Inspect network tab to extract FeatureServer URL. |
| Long Beach, CA | `experience.arcgis.com/experience/846a17aadb6e40d79f4da0470d106bcf` | "Refuse Collection Days" polygon layer. Datasets downloadable as CSV/GeoJSON. |
| El Paso, TX | `experience.arcgis.com/experience/533d0f50c98c43ff81930d681bf3362c` | Zone polygons. Biweekly recycling same day as garbage. |
| Scottsdale, AZ | `scottsdaleaz.gov/solid-waste/my-services` | Strong GIS shop; REST URL likely under `data-cos-gis.opendata.arcgis.com`. |
| Greensboro, NC | `gisimages.greensboro-nc.gov/servicedayfinder/` | Finder app. Red/Blue week recycling. REST at `gis.greensboro-nc.gov/arcgis/rest/services` (solid-waste folder not public). |
| Fresno, CA | `gis4u.fresno.gov/arcgis/rest/services` | Polyline routes (256). Same day for gray/blue/green carts. |
| Arlington, TX | `data-arlingtontx.opendata.arcgis.com` | Likely has hidden polygon layer. Contractor: Republic Services. |
| San Jose, CA | `gis.sanjoseca.gov/maps/serviceslookuptool/` | Multi-hauler (GreenTeam west, Republic commercial). |

## Tier 3 — no open data source surfaced (investigation needed)

- **Atlanta, GA** — internal lookup tool only; ~100K single-family households. May require FOIA or scraping.
- **Tampa, FL** — app/web lookup only. Needs deeper network trace.
- **Sacramento, CA** — portal exists but no FeatureServer found; A/B week recycling complicates.
- **Buffalo, NY** — `gis.buffalony.gov` exists, waste layer not public.
- **Tempe, AZ** — data portal exists, no waste layer. Alley collection (unusual).
- **Oakland, CA** — third-party (`oaklandrecycles.com`) only; WM + CalWaste Solutions.
- **Cleveland, OH** — PDF calendar only. Would require manual zone extraction.

## Delivery plan

1. ✅ Durham (this PR)
2. Anaheim, Detroit, Rochester — small polygon sets; each ~30 min once FeatureServer URL is confirmed
3. Orlando — dedicated polyline importer (street segments)
4. Long Beach, El Paso, Scottsdale, Greensboro, Fresno — once network-trace confirms REST URLs
5. Tier 3 — queued; may require vendor outreach or third-party scraping

Each zone-based city, once imported, will be resolvable via the Phase B
`collection_zones` + `lookup_zone` RPC tier in `/api/schedule`.
