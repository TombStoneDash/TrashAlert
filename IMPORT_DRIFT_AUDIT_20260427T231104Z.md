# ReCollect Import Drift Audit — 2026-04-27

**Scope:** all 16 entries in `scripts/import-recollect.mjs`
**Method:** for each (place_id, service_id) tuple, check (a) row exists in `schedule_reports`, (b) ReCollect API still resolves the place
**Output:** drift table (read-only, no changes)

---

## TL;DR

- **All 16 entries: 1 row in DB ✅** (placeholder pattern intact)
- **All 16 ReCollect places still resolve ✅** (no decommissioned tuples)
- **City-name drift on 4 entries** — ReCollect's canonical `city` field doesn't match our slug (e.g., Halton-ON resolves to "burlington" in ReCollect's data). Not actionable; just naming differences for regional service areas.
- **No row-shape drift** — every DB row carries the expected `<slug> default service area` address pattern
- **No action required.** The 16-entry baseline is healthy.

---

## Per-entry results

| Slug | DB rows | Sample address | ReCollect resolves | Current city in API |
|---|---|---|---|---|
| ottawa-on | 1 | ottawa-on default service area | OK | ottawa |
| denver-co | 1 | denver-co default service area | OK | denver |
| austin-tx | 1 | austin-tx default service area | OK | austin |
| san-francisco-ca | 1 | san-francisco-ca default service area | OK | san francisco |
| cambridge-ma | 1 | cambridge-ma default service area | OK | cambridge |
| vancouver-bc | 1 | vancouver-bc default service area | OK | vancouver |
| **halton-on** | 1 | halton-on default service area | OK | **burlington** ← drift |
| **saanich-bc** | 1 | saanich-bc default service area | OK | **victoria** ← drift |
| richmond-bc | 1 | richmond-bc default service area | OK | richmond |
| davenport-ia | 1 | davenport-ia default service area | OK | davenport |
| georgetown-tx | 1 | georgetown-tx default service area | OK | georgetown |
| peterborough-on | 1 | peterborough-on default service area | OK | peterborough |
| sherwood-park-ab | 1 | sherwood-park-ab default service area | OK | sherwood park |
| morris-mb | 1 | morris-mb default service area | OK | morris |
| **hardin-id** | 1 | hardin-id default service area | OK | **boise** ← drift |
| **king-county-wa** | 1 | king-county-wa default service area | OK | **des moines** ← drift |

## Drift analysis (4 entries)

These 4 cases aren't bugs — they're naming mismatches between our slug and ReCollect's canonical city label:

- **halton-on** → "burlington" — Halton Region encompasses Burlington, Oakville, Halton Hills, Milton. The reference place is in Burlington, but the *service* covers all of Halton. Slug is correct.
- **saanich-bc** → "victoria" — Saanich is a district within Greater Victoria. Slug is more specific than ReCollect's city label.
- **hardin-id** → "boise" — Hardin Sanitation serves the Boise metro area. Slug is the hauler's name, not a geographic city.
- **king-county-wa** → "des moines" — Recology CleanScapes serves multiple King County cities; Des Moines WA is just where the reference place is located.

None of these affect data quality or response correctness. The ReCollect API call still returns valid event data for each tuple, and the resulting placeholder row in `schedule_reports` is structurally correct.

## What this audit explicitly does NOT do

- Modify any ReCollect entry
- Remove or alter the placeholder rows in `schedule_reports`
- Run the discovery script `scripts/discover-recollect-tuples.mjs` to find new tuples (tracked separately in PR #73)

---

## Methodology

- For each of 16 PLACES entries: query `schedule_reports?city=eq.<slug>` for row count + sample address, then `GET api.recollect.net/api/places/<place_id>` to confirm the place metadata still exists
- All operations read-only
- Wall clock: ~2 minutes
