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
