# BLOCKER.md — Analysis as of 2026-04-26

**Source file:** `C:/TombstoneDash/factory/trashalert/BLOCKER.md` (FastAPI repo)
**Status of this analysis:** Read-only. No migrations executed. No code changed. No DB writes.

---

## TL;DR

The blocker that BLOCKER.md flags as "MANUAL APPLICATION REQUIRED" — the `collection_zones` migration — **has already been applied to production Supabase**. The table exists, the `lookup_zone` RPC is callable. The actual remaining work is:

1. **Importing zone polygons** for Chicago, Houston, Indianapolis, Miami-Dade, Kansas City, Jacksonville (table is currently empty).
2. **Resolving Phase-1 city blockers** that are still flagged as ongoing (St. Louis County, Mesa AZ, Louisville KY endpoint refresh, Pittsburgh PA fallback).
3. **BLOCKER.md needs an update commit** — the readiness-sprint section is now misleading.

---

## What BLOCKER.md says

The file (112 lines, last touched 2026-04-20) contains two sections:

### 1. Readiness Sprint (2026-04-20) — Phase B

Claims `trashalert-web/supabase/migrations/20260420000000_collection_zones.sql` requires **manual application via Supabase Studio → SQL Editor** because:

- "no Supabase CLI linked locally"
- "service role key cannot execute DDL via PostgREST"

States that until applied, the `/api/schedule` `db_zone` tier "will fail open (caught and logged, falls through to remaining tiers) — safe but ineffective."

Also lists three zone-polygon imports to run *after* the migration:
- `chicago-wards`
- `houston-swm`
- `indianapolis-dpw`

…plus three more (Miami-Dade, Kansas City, Jacksonville) that "still need field mapping; pending source-URL verification."

### 2. Phase 1 history (2026-04-19)

Records city imports from a week earlier:
- **RESOLVED:** Raleigh NC (121,923 rows), Louisville KY (21 rows), Pittsburgh PA (178 rows)
- **BLOCKED:** St. Louis County MO (159,819 address points but no `collection_day` field; would need ~160K hauler-website scrapes), Mesa AZ (no public data source), Louisville KY (endpoint dead — duplicate entry, contradicts the RESOLVED line above), Pittsburgh PA (primary endpoint dead — duplicate entry, contradicts RESOLVED)

The Louisville/Pittsburgh duplication suggests the file accumulated entries across multiple runs without dedup.

---

## What the migration actually does

`20260420000000_collection_zones.sql`:

- Enables `postgis` extension
- Creates `collection_zones` table with columns: `id`, `city`, `zone_id`, `zone_name`, `geom (MultiPolygon, 4326)`, `collection_day`, `recycling_week`, `source`, `fetched_at`. Unique on `(city, zone_id)`. GIST index on `geom`.
- Creates `lookup_zone(p_lat, p_lng, p_city)` SQL function that does point-in-polygon via `ST_Contains`, returns first matching zone
- Grants `EXECUTE` on the RPC and `SELECT` on the table to `anon` and `authenticated` roles

This is the schema/RPC backbone for the `db_zone` tier in `/api/schedule` (Step 2.73, see PR #10's resolver). When a user types an address, the resolver geocodes to lat/lng, then calls `lookup_zone` to find which polygon contains that point and returns the day for that zone.

**Risk profile of the migration itself:** low. Creates one new table and one new function. No modifications to existing tables or data. Idempotent (`IF NOT EXISTS`). Fully reversible by `DROP TABLE collection_zones CASCADE; DROP FUNCTION lookup_zone(double precision, double precision, text);`.

**Sacred Rule #1** (from overnight directive): "No Prisma `--accept-data-loss` or destructive Supabase migrations. Feb 20 data loss is the reason." This migration is non-destructive and would not have triggered the rule. Manual application caution was warranted only because we lacked the CLI.

---

## Current production state (verified 2026-04-26 19:30 UTC, read-only)

| Probe | Result | Interpretation |
|---|---|---|
| `GET /rest/v1/collection_zones?select=id` (count=estimated) | HTTP 200, `Content-Range: */0` | Table exists. Zero rows. |
| `POST /rest/v1/rpc/lookup_zone` with sample Chicago lat/lng | HTTP 200, body `[]` | RPC exists, callable, returns empty (no zones to match). |

**Conclusion:** The migration has been applied to production at some point between 2026-04-20 and now. The Supabase-Studio manual step BLOCKER.md describes is no longer outstanding.

The remaining work is **importing the zone polygons** that the migration was created for. None of the six target cities (Chicago, Houston, Indianapolis, Miami-Dade, Kansas City, Jacksonville) have any rows in `collection_zones`. The `db_zone` tier in `/api/schedule` is therefore still "safe but ineffective" — but the cause is empty data, not a missing migration.

---

## Recommended next steps (for HT, post-overnight)

1. **Update or delete BLOCKER.md** — the "MANUAL APPLICATION REQUIRED" section is misleading and will trick a future agent into trying to re-apply the migration. Either rewrite the section to "applied 2026-04-XX, awaiting imports" or remove it.

2. **Decide on zone-polygon imports** — there are three "ready" cities (`chicago-wards`, `houston-swm`, `indianapolis-dpw`) that have importer scripts already written. Estimated yield: tens of thousands of zone rows mapping to millions of addressable lookups via point-in-polygon. This is genuinely high-leverage work.

3. **Field-mapping research for the other three** (Miami-Dade, Kansas City, Jacksonville) — BLOCKER.md notes the canonical `SERVICE_DAY` field name varies. ~30-60 min per city with their ArcGIS endpoint open in a browser.

4. **Resolve the Phase-1 contradictions** in BLOCKER.md (Louisville/Pittsburgh listed as both RESOLVED and BLOCKED in different sections). Probably the second mention is the live state; the RESOLVED note was overwritten by a later run that found the endpoint dead again.

5. **St. Louis County MO** — deferred per BLOCKER.md as a "separate per-address enrichment job, run outside this campaign." Still valid; not overnight work.

6. **Mesa AZ** — needs human contact to Mesa Solid Waste / GIS staff. Not agent-doable.

---

## What this analysis explicitly does NOT do

- Does not execute the migration (already applied, no need)
- Does not run the zone-polygon imports (Sacred Rule: no DB writes during overnight without explicit per-task authorization)
- Does not modify BLOCKER.md (recommended above; HT decides)
- Does not modify any code
- Does not revisit the Louisville/Pittsburgh/St. Louis import scripts

---

## Methodology

- Read `BLOCKER.md` end-to-end
- Read `20260420000000_collection_zones.sql` migration source from `origin/main` of trashalert-web
- Probed Supabase REST: `select=id` on `collection_zones` (table exists check), `rpc/lookup_zone` POST (RPC callable check). Both read-only.
- Cross-referenced with PR #10's resolver code (Step 2.73 zone tier wiring)
