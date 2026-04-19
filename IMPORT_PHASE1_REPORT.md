# Phase 1 Import — Report

Run date: 2026-04-19
Repo: `C:\TombstoneDash\factory\trashalert`
Sprint: `factory/queue/SPRINT_IMPORT_PHASE1.md`
Target table: `schedule_reports` in Supabase project `qsuzfemakaaroeakyick`

## Summary

| Metric | Value |
|---|---|
| Cities attempted | 13 |
| Cities succeeded | **9** |
| Cities failed | 4 (2 dead endpoints, 2 placeholders) |
| Total new rows imported | **20,049** |
| Acceptance threshold (8/13) | met |

## Per-city breakdown

| Order | City | Status | Fetched | Imported | Skipped | Errors |
|---|---|---|---:|---:|---:|---:|
| smoke | Albuquerque NM | OK | 9 | **9** | 0 | 0 |
| 1 | Mesa AZ | placeholder script | — | 0 | — | — |
| 2 | Albuquerque NM | (run as smoke) | — | — | — | — |
| 3 | Baltimore MD | OK | 1,000 segments → expanded | **18,500** | 309 | 380 |
| 4 | Tucson AZ | OK after patch | 131 | **131** | 0 | 0 |
| 5 | Louisville KY | FAIL | — | 0 | — | — |
| 6 | Milwaukee WI | OK | 417 | **417** | 0 | 0 |
| 7 | Kansas City MO | OK | 303 | **303** | 0 | 0 |
| 8 | Pittsburgh PA | FAIL | — | 0 | — | — |
| 9 | Jacksonville FL | OK (low yield) | 97 | **8** | 283 | 0 |
| 10 | Indianapolis IN | OK | 485 | **346** | 624 | 0 |
| 11 | Miami-Dade FL | OK after patch | 783 | **306** | 477 | 0 |
| 12 | LA County CA | OK after patch | 239 | **29** | 210 | 0 |
| 13 | Raleigh NC | placeholder script | — | 0 | — | — |

(Mesa was placed first in the sprint order but is a placeholder — see BLOCKER.md.
Albuquerque was used as smoke-test substitute since the sprint's chosen smoke
script, Raleigh, is also a placeholder.)

## Script fixes made during the run

Three of five initial failures turned out to be field-name drift in the
upstream ArcGIS schemas. Patched in place:

- **`scripts/import-la-county.mjs`** — upstream layer's primary key is
  `FID`, not `OBJECTID`. Replaced in `FIELDS`, `orderByFields`, and the
  fallback in `areaName`.
- **`scripts/import-tucson.mjs`** — upstream renamed `ServiceDates` →
  `ServDates` and removed `BBArea`. Updated `FIELDS`, the `normalizeDay`
  fallback chain, and the neighborhood/route-id fallbacks.
- **`scripts/import-miami-dade.mjs`** — `WEEKDAYS` strings are
  space-separated (`"Monday Thursday"`); added `\s` to the split regex
  in `normalizeDay`. Recycling endpoint
  (`RecyclingZone_gdb/FeatureServer/0`) only exposes `ZONEID` with no
  day/route fields, so the recycling layer is now skipped (with an
  explanatory comment) — this fixes the "Invalid query parameters"
  fatal that was crashing the whole script.

The two remaining hard failures (Louisville, Pittsburgh) are dead
endpoints — needs new source URLs, not a code fix. See BLOCKER.md.

## Sample addresses per successful city

Verification via `https://trashalert.io/api/schedule?...` could not be
performed in this run (sandbox denied the external curl — see "Verification
limitation" in BLOCKER.md). Listing the address keys that were upserted
so a human can spot-check:

- **albuquerque** — zone-level: `albuquerque zone <OBJECTID>` (9 zones)
- **baltimore** — street-segment expansion: e.g. `<houseNo> <prefix> <street> <type>` (18,500 individual addresses across ~691 segments with day data)
- **tucson** — `tucson recycling route <PRIMARY_RT or OBJECTID>` (131 zones)
- **milwaukee** — zone-level routes (417 zones across mon-fri layers)
- **kansas-city** — zone-level (303 routes)
- **jacksonville** — zone-level (8 zones — low yield, most input lacked day field)
- **indianapolis** — zone-level (346 collection areas)
- **miami-dade** — `miami-dade garbage route <ROUTE>` (306 routes)
- **la-county** — `la-county area <AREA_NAME>` (29 areas, unincorporated only)

The shape of these addresses matches the existing Dallas / Houston /
Denver / Boston rows that PR #1 confirmed working with the
`/api/schedule` fallback. Baltimore is the only city that imported
real street-level addresses; the rest are zone-level centroids that
depend on `/api/schedule` doing geo lookup vs. exact-match.

## Recommended next priorities

1. **Verify on production.** Once external curls to `trashalert.io` are
   authorized (or run by a human), spot-check one address per city
   against `/api/schedule` and confirm `match:"db_schedule_reports"`
   resolves with the right `collection_day`. Most likely to surprise:
   the zone-level cities, where `/api/schedule` must geo-resolve user
   input → centroid match.
2. **Index `schedule_reports.city` (and probably `reporter_hash`) in
   Supabase.** `SELECT … WHERE city=eq.X` against this table currently
   times out via the REST endpoint, blocking any operational debugging
   or per-city auditing. A simple btree index will fix it.
3. **Fix Louisville and Pittsburgh source URLs** (see BLOCKER.md). Both
   are quick wins — endpoints just moved.
4. **Promote Raleigh / Mesa from placeholder to real imports** (see
   BLOCKER.md script headers for the exact research checklist).
5. **Phase 2 ReCollect discovery** — out of scope for tonight per the
   sprint's NON-GOALS; queue separately.

## Stop-condition compliance

- All 13 cities attempted: ✓ (9 imported, 2 dead endpoints, 2 placeholders)
- 8 hours elapsed: well under
- Supabase access lost: no
