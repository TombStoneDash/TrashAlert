# Phase 1 Import — Blockers

Run date: 2026-04-19
Repo: `C:\TombstoneDash\factory\trashalert`
Sprint: `factory/queue/SPRINT_IMPORT_PHASE1.md`

## Cities not imported

### Raleigh NC — RESOLVED 2026-04-19 (Phase 1E)
- Script: `scripts/import-raleigh.mjs` (rewritten)
- New source: `services.arcgis.com/v400IkDOw1ad7Yad/.../RALEIGH_SWS_COLLECTION/FeatureServer/0`
- Result: 121,923 rows imported (per-address points).

### Louisville KY — RESOLVED 2026-04-19 (Phase 1E)
- Script: `scripts/import-louisville.mjs` (re-pointed)
- New source: `gis.lojic.org/maps/rest/services/LojicSolutions/OpenDataSociety/MapServer/12`
- Result: 21 rows imported (zone-level/centroid).

### Pittsburgh PA — RESOLVED 2026-04-19 (Phase 1E)
- Script: `scripts/import-pittsburgh.mjs` (rewritten)
- New source: `services1.arcgis.com/YZCmUqbcsUpOKfj7/.../Refuse_Routes/FeatureServer/2`
- Result: 178 rows imported (zone-level/centroid).

### St. Louis County MO — BLOCKED (Phase 3, 2026-04-19)
- Source: `services2.arcgis.com/w657bnjzrjguNyOy/.../Address_Points_in_Trash_Collection_Districts/FeatureServer/39`
- Has 159,819 per-address points but only `TRASH_DISTRICT` (1-8), no day field.
- The `Trash_Collection_Districts_Updated_March_2026/FeatureServer/45`
  layer maps district → hauler (Republic Services or Waste Connections)
  but **not** district → day-of-week. Day is per-route per-hauler.
- `schedule_reports.collection_day` is check-constrained to a valid
  weekday, so cannot insert without per-address hauler-lookup
  scraping (~160K calls against `republicservices.com/schedule` and
  `wasteconnections.com/st-louis`).
- Recommended next step: separate per-address enrichment job, run
  outside this campaign as a long-running background task.

### Mesa AZ — STILL BLOCKED
- Script: `scripts/import-mesa.mjs` (still a placeholder)
- Sources checked 2026-04-19:
  - ArcGIS Online owner search `owner:MesaAz` → 80+ items, none waste-related.
  - ReCollect API: `mesa`, `mesa-az`, `MesaAZ`, `CityOfMesa` all 404 on `/r/area/<slug>`.
  - `mesaaz.gov` solid-waste pages: 404 on the deep-link paths attempted.
  - `data.mesaaz.gov` carries Solid Waste analytics (Route Demographics,
    Barrels Collected) but no per-address or per-route schedule layer.
- Recommended next step: human contact to Mesa Solid Waste / GIS staff
  to request either a route-day shapefile or a public ArcGIS layer.
  Skipping for the campaign per sprint's "log and keep going" rule.

### Louisville KY — DEAD ENDPOINT
- Script: `scripts/import-louisville.mjs`
- Status: `Fatal: ArcGIS error: Invalid URL`
- Root cause: source URL
  `https://services1.arcgis.com/79kfd2K6fskCAkyg/ArcGIS/rest/services/OpenDataJeflib/FeatureServer/21`
  returns `{"error":{"code":400,"message":"Invalid URL"}}` even at the
  metadata path (no `/query`). The OpenDataJeflib service path or layer
  index `21` no longer resolves.
- Next steps: browse `https://data.louisvilleky.gov/` for the current
  Sanitation Routes / Garbage Collection layer URL; refresh the script
  with the new endpoint.

### Pittsburgh PA — PRIMARY DEAD, FALLBACK NOT CONFIGURED
- Script: `scripts/import-pittsburgh.mjs`
- Status: Primary endpoint `http://www.pgh.st/api/data/location` returned
  `fetch failed`. Script printed its own warning pointing to fallback
  research targets but did not attempt a fallback URL.
- Next steps (from script's own warning):
  1. Browse `https://pghgishub-pittsburghpa.opendata.arcgis.com/` for the
     current Public Works trash-pickup FeatureServer.
  2. Or use the WPRDC package: `https://data.wprdc.org/dataset/?q=trash+collection`.

## Verification limitation

The sprint specifies post-import verification via
`https://trashalert.io/api/schedule?address=<X>&city=<Y>`. The sandbox
denied that external curl (treated as a guessed/untrusted endpoint).
Verification fell back to:
- The import scripts' own row counts, which use the Supabase JS SDK
  (`upsert`/`insert` errors would surface as `errors > 0`).
- A direct Supabase REST query on `select=address&limit=1` (the only
  query shape that did not hit the `schedule_reports` statement timeout —
  filtered queries by `city`, `reporter_hash`, or `address LIKE` all
  exceeded the configured statement timeout, suggesting missing indexes).

A follow-up by a human (or with the trashalert.io endpoint authorized in
settings) is recommended to confirm rows resolve via the production
`/api/schedule` fallback.
