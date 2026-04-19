# Phase 1 Import — Blockers

Run date: 2026-04-19
Repo: `C:\TombstoneDash\factory\trashalert`
Sprint: `factory/queue/SPRINT_IMPORT_PHASE1.md`

## Cities not imported

### Raleigh NC — PLACEHOLDER
- Script: `scripts/import-raleigh.mjs`
- Status: `process.exit(2)` — script is a stub with no data source identified.
- Root cause: Initial research (2026-04-16) did not surface a Raleigh
  Solid Waste Services FeatureServer URL on data-ral.opendata.arcgis.com.
- Next steps (from script header): search the open-data hub for "Collection",
  "Solid Waste", "Sanitation", "Yard Waste", "Recycling Route"; if no hit,
  email gisadmin@raleighnc.gov; alternative: scrape
  raleighnc.gov/services/solid-waste per-address.

### Mesa AZ — PLACEHOLDER
- Script: `scripts/import-mesa.mjs`
- Status: `process.exit(2)` — script is a stub with no data source identified.
- Root cause: same pattern as Raleigh — no public ArcGIS endpoint located
  during initial research.
- Next steps: see script header.

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
