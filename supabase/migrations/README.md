# Supabase migrations

These SQL files are designed for application via the Supabase Studio
SQL Editor (or `supabase db push` if the CLI is set up against this
project). They are NOT auto-applied by any code in this repo.

## Why not auto-applied

The Supabase project does not expose an `exec_sql` / `run_sql` RPC
function and does not have direct DB credentials in `.env.local`
(only `SUPABASE_URL` / `SUPABASE_SERVICE_KEY`, which give PostgREST
access — no DDL). To apply these from the command line we would need
either:
- The DB password and `psql` installed (neither is available here), or
- A `pg`-based Node script with the pooler URL + password, or
- The Supabase Management API personal access token.

## How to apply manually

1. Open Supabase Studio for project `qsuzfemakaaroeakyick`.
2. SQL Editor → New query.
3. Paste the contents of the `.sql` file.
4. Run.

## Files

| File | Purpose |
|---|---|
| `20260419_schedule_reports_indexes.sql` | Add btree indexes on `city`, `(city,address)`, `reporter_hash` and a pg_trgm gin index on `address`. Fixes statement-timeouts seen during Phase 1A verification. |
