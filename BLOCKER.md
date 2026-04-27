# Import Blockers

Run date: 2026-04-19 (Phase 1), 2026-04-20 (Readiness sprint)
Repo: `C:\TombstoneDash\factory\trashalert`
Sprint: `factory/queue/SPRINT_IMPORT_PHASE1.md`, `SPRINT_PM_READINESS.md`

---

## Readiness Sprint (2026-04-20) — Phase B

### collection_zones migration — APPLIED 2026-04-XX
- File: `trashalert-web/supabase/migrations/20260420000000_collection_zones.sql`
- Verified live in production 2026-04-26: `collection_zones` table exists
  (currently empty), `lookup_zone(p_lat, p_lng, p_city)` RPC is callable
  and returns `[]` for points with no matching polygon.
- The earlier "MANUAL APPLICATION REQUIRED" note no longer applies. The
  migration was applied via Supabase Studio at some point between
  2026-04-20 and 2026-04-26.
- The /api/schedule `db_zone` tier (Step 2.73) is wired but currently
  fails open because the table has zero rows — same user-visible effect
  as before, different root cause.

### Zone imports — STILL OUTSTANDING (the actual remaining work)
- `node --env-file=.env.local scripts/import-zone-polygons.mjs chicago-wards`
- `node --env-file=.env.local scripts/import-zone-polygons.mjs houston-swm`
- `node --env-file=.env.local scripts/import-zone-polygons.mjs indianapolis-dpw`
- `long-beach` — see Long Beach PoC writeup in factory_overnight_apr27_phaseB.md.
  19-zone polygon dataset confirmed at
  `services6.arcgis.com/yCArG7wGXGyWLqav/.../Refuse_Collection_Days/FeatureServer/0`.
- Miami-Dade / Kansas City / Jacksonville sources still need field mapping;
  pending source-URL verification (ArcGIS endpoints for those cities have
  rotated and the canonical SERVICE_DAY field name varies).

---

## Phase 1 history (2026-04-19)

## Cities not imported

> **Note (2026-04-27 cleanup):** the original Phase-1 history listed
> Louisville KY and Pittsburgh PA as both RESOLVED *and* DEAD ENDPOINT
> in different sections of the same file. The "DEAD ENDPOINT" entries
> further down are the live state — the RESOLVED notes were written
> before the endpoints rotated and were never reconciled. See those
> sections below.

### Raleigh NC — RESOLVED 2026-04-19 (Phase 1E)
- Script: `scripts/import-raleigh.mjs` (rewritten)
- New source: `services.arcgis.com/v400IkDOw1ad7Yad/.../RALEIGH_SWS_COLLECTION/FeatureServer/0`
- Result: 121,923 rows imported (per-address points).

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
