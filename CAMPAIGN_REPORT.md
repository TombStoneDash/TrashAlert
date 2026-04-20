# Full Campaign — Rolling Report

Run date: 2026-04-19
Repo: `C:\TombstoneDash\factory\trashalert`
Sprint: `factory/queue/SPRINT_IMPORT_FULL_CAMPAIGN.md`
PR: https://github.com/TombStoneDash/TrashAlert/pull/70 (Phase 1 results,
will be amended with full campaign output)

This document is updated after every phase so a mid-run crash doesn't
lose progress. Naming note: the repo already has a local-only
`REPORT.md` (gitignored) and a per-phase `IMPORT_PHASE1_REPORT.md`,
hence this separate file for the campaign rollup.

---

## Phase 1A (prior session) — 9/13 cities, 20,049 rows
Verified in `IMPORT_PHASE1_REPORT.md`.

## Phase 1B/discovery context
Per `REPORT.md`, `schedule_reports` already holds **~6.28M rows from
44+ distinct cities** from earlier prior work. The numbers below are
*deltas* this campaign added on top.

---

## Phase 1C — schedule_reports indexes

**Status: migration written, manual application required.**

- Migration: `supabase/migrations/20260419_schedule_reports_indexes.sql`
- Indexes: `(city)`, `(city,address)`, `(reporter_hash)`, gin trgm on `address`
- Application: needs human run via Supabase Studio SQL Editor — this
  environment has no `psql`, no Supabase CLI, no DB password, and no
  `exec_sql` RPC on the project.

Empirical workaround discovered during 1D: `city=eq.X` queries DO
succeed when paired with `order=address.asc` (server can use the
implicit btree on the upsert conflict-target). So verification could
proceed without indexes; index migration still recommended for general-
purpose lookups.

---

## Phase 1D — trashalert.io verification

**All 9 Phase 1A cities verified end-to-end.** Each address below was
constructed from upstream OBJECTID/route values, then probed against
`https://trashalert.io/api/schedule`. All returned
`found:true match:"exact"` from `db_schedule_reports` (source `city_api`).

| city | sample address | day |
|---|---|---|
| albuquerque | `albuquerque zone 1` | friday |
| baltimore | `1  allen court` | wednesday |
| baltimore | `1  blossom lane` | tuesday |
| tucson | `tucson recycling route 1152` | monday |
| milwaukee | `milwaukee monday route 1` | monday |
| kansas-city | `kansas-city zone 3201` | friday |
| jacksonville | `jacksonville garbage district city` | tuesday |
| indianapolis | `indianapolis garbage route 1370 mon` | monday |
| miami-dade | `miami-dade garbage route 4117` | monday |
| la-county | `la-county area e. charter oak / foothill / ramona / spadra` | tuesday |

No city slug normalization issues found; no city imported but failed
to resolve.

---

## Phase 1E — fix the 4 failed cities

| city | status | source | rows |
|---|---|---|---|
| louisville-ky | ✅ resolved | LOJIC OpenDataSociety MapServer/12 | 21 |
| pittsburgh-pa | ✅ resolved | PGH DPW Refuse_Routes FeatureServer/2 | 178 |
| raleigh-nc    | ✅ resolved | RALEIGH_SWS_COLLECTION FeatureServer/0 | **121,923** |
| mesa-az       | ❌ blocked  | (no public source found) | 0 |

Total Phase 1E delta: **122,122 rows**.

Mesa research log:
- ArcGIS Online `owner:MesaAz` → 80+ items, none waste-related
- ReCollect `/r/area/{mesa,mesa-az,MesaAZ,CityOfMesa}` → all 404
- mesaaz.gov solid-waste paths → 404 on attempted deep links
- data.mesaaz.gov → analytics dashboards only (no per-route schedule)
- Logged in `BLOCKER.md` per sprint's "log and keep going" rule.

---

## Phase 2 — ReCollect API integration

`scripts/import-recollect.mjs` — single importer, hard-coded
PLACE_ID/SERVICE_ID list curated from the home-assistant
`hacs_waste_collection_schedule` canonical doc.

Discovery: ReCollect has no city-slug API. Each address resolves through
opaque UUID `place_id` + integer `service_id`. We pull events for the
next 28 days, group by trash/recycle flag (case-insensitive regex —
flag names are inconsistent across municipalities: `Trash`/`garbage`/
`Davenport_Garbage`/`garbagecart`/`Cart_Recycling`), pick the dominant
day-of-week, write one row per area.

Imported (16/16):
- Ottawa ON, Denver CO, Austin TX, San Francisco CA, Cambridge MA,
  Vancouver BC, Halton ON, Saanich BC, Richmond BC, Davenport IA,
  Georgetown TX, Peterborough ON, Sherwood Park AB, Morris MB,
  Hardin Sanitation ID, Recology CleanScapes (King County WA).

Total Phase 2 delta: **16 rows** (zone-level fallback signal per area).

---

## Phase 3 — state/county open data discovery

Research agent surfaced 15 ArcGIS endpoints; 12 imported successfully.

### 3a — Top-20 cities with existing scripts (re-runs against current DB)

| city | source | rows added this run |
|---|---|---|
| charlotte-nc   | `services.arcgis.com/9Nl857LBlQVyzq54/.../Solid_Waste_Collection/FeatureServer/0` | 847 |
| fort-worth-tx  | `mapitwest.fortworthtexas.gov/.../SolidWaste/MapServer/3` | 697 |
| seattle-wa     | `services.arcgis.com/ZOyb2t4B0UYuYNYH/.../Residential_Garbage_Routes/FeatureServer/0` | 195 (after per-row fallback fix) |
| columbus-oh    | `maps2.columbus.gov/.../Neighborhood/MapServer/24` | 0 (15,604 dupes — already loaded) |

### 3b — New ArcGIS sources via `scripts/import-phase3-zones.mjs`

| city/county | source | rows |
|---|---|---|
| nyc           | DSNY_FREQUENCIES FeatureServer/0 | 610 |
| houston       | COH_Solid_Waste_Automated_Trash_Pickup_Areas_view/FeatureServer/18 | 360 |
| san-antonio   | RECYCLEROUTES_WEBMAP FeatureServer/0 | 271 |
| dekalb-ga     | Dekalb_County_Sanitation_layer_Garbage_Route FeatureServer/0 | 291 |
| nashville     | Trash_Collection_Routes_5_Day_Public_View FeatureServer/0 | 189 |
| boston        | gisportal.boston.gov/.../Infrastructure/OpenData/MapServer/10 | 51 |
| boston-fix    | added single-letter day codes (M/T/W/TH/F) | (subset of 51) |
| phoenix-az    | Trash_Routes FeatureServer/0 | 3 |
| orlando       | OrlandoSWGarbage FeatureServer/0 | 30 |
| philadelphia  | Service_Areas FeatureServer/2 | 5 |
| arlington-tx  | OD_Community/MapServer/4 | 5 |

Subtotal Phase 3b: **1,815 rows**.

### 3c — DC DPW (per-address goldmine)

Standalone `scripts/import-dc.mjs`. Source: ~105,894 per-address points
with `ADDRESS` + `DAY` directly populated. Layer maxRecordCount=1000
required PAGE_SIZE adjustment plus retry/timeout wrapper after a
mid-run connection drop.

**Result: 99,513 rows imported** (105,894 fetched, 6,381 skipped — final
batch had a cluster of points with empty DAY field, likely commercial
or special-collection addresses; 0 errors).

### 3d — St. Louis County MO — BLOCKED

160K per-address points but no district→day mapping. Documented in
`BLOCKER.md`; would require per-address scraping of Republic Services
+ Waste Connections lookup endpoints (~160K calls) — out of scope for
this campaign session.

---

## Phase 4 — long-tail discovery via ArcGIS Online search

After Phase 3, direct URL guesses for "next 10 likely cities"
(Greensboro / Durham / Cary / Knoxville / Richmond VA / Norfolk /
Va Beach / Anchorage / Lincoln NE / KC-MO areas) all returned 404
or "Invalid URL". Pivoted to ArcGIS Online's `/sharing/rest/search`
endpoint, ranked candidates by `numViews`, then probed each layer's
geometry type, count, and field schema for per-address goldmines.

Six new per-address sources turned up:

| city | source | rows |
|---|---|---|
| stevens-point (WI) | Garbage_Address_Points (Q3XmNaYun…) FeatureServer/0 | 7,231 |
| bay-city (MI)      | Address_Recycling (qEGIvpJUx…) FeatureServer/0   | 14,893 |
| novi-mi            | Trash_and_Recycling_Collection L1 (jwbgoAzqz…)   | 16,433 |
| wauwatosa-wi       | RefuseRecyclingCustomers L0 (gyXZ0hXCx…)         | 15,638 |
| south-fulton-ga    | Solid_Waste_by_Day_WFL1 L2 (y2BJK2GUf…)          | 38,002 |
| cocoa-fl           | WM_All_Pickup_Types L3 (Tex1uhbqn…)              | 5,573 |

Skipped:
- **herndon-va** — Addresses_In_Refuse_Recycle_Routes L0 (5,219
  points) — `Current_Refuse_Collection_Day` is empty for every row;
  the only populated day fields are the `Proposed_*` columns from a
  2019 reroute survey that never went live.
- Hoover AL — 93,432 address points but only 2 polygons carry
  `Trashday`; would need server-side spatial join (point-in-polygon)
  to attribute days to addresses. Out of scope this run.

New importers:
- `scripts/import-stevens-point.mjs`
- `scripts/import-bay-city.mjs`
- `scripts/import-phase4-points.mjs` — combined importer covering
  novi-mi, wauwatosa-wi, south-fulton-ga, herndon-va, cocoa-fl
  (config-driven `SOURCES` map; pass `all` or a single slug as argv).

---

## Running totals (this campaign delta only)

| phase | rows added |
|---|---|
| Phase 1A (prior session) | 20,049 |
| Phase 1E (Raleigh+Pittsburgh+Louisville) | 122,122 |
| Phase 2 (ReCollect) | 16 |
| Phase 3a (re-runs of existing scripts) | 1,739 |
| Phase 3b (new zone sources) | 1,815 |
| Phase 3c (DC) | 99,513 |
| Phase 4 (Stevens Point + Bay City + Novi + Wauwatosa + South Fulton + Cocoa) | 97,770 |
| **Total** | **343,024** rows added across the campaign |
