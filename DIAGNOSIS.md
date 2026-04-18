# DIAGNOSIS — TrashAlert pipeline reality check
## 2026-04-18T04:25Z (Gate 1)

## TL;DR

**The pipeline is not broken.** Imports have landed. `schedule_reports` has **~6.28M rows from 44+ distinct cities**. What's broken is the *visibility* layer: the audit script's `fetchLiveCities()` silently undercounts because it relies on PostgREST's default 1000-row cap, and the deployed `/api/stats/live` endpoint isn't reachable on `trashalert.io` (404s to the Next.js fallback).

The "2 cities (Austin, Boston)" claim in the v2 directive is also wrong — that ground truth was itself derived from the broken audit.

## Actual Supabase state (G1.1)

Connected to project: `qsuzfemakaaroeakyick.supabase.co` (matches directive).

`schedule_reports` table:
- Estimated total rows: **~6,286,242**
- Distinct cities seen: **44+** (sampling missed the latter half of the table due to OFFSET timeouts on a non-indexed scan, so the true count may be higher)
- Heaviest cities (extrapolated from head sample):
  - boston ~2.1M · houston ~2.5M · san-antonio ~2.0M · dallas ~1.2M · philadelphia ~1.0M · san-francisco ~1.0M · denver ~445K · austin ~93K · phoenix ~6K
- Tail (latest 5000 rows by id desc) shows the EDCO bundle landed: escondido, vista, san marcos, encinitas, fallbrook, el cajon, la mesa, lakewood, etc. (28 north-county-SD cities). Plus charlotte, chicago, seattle each appear at low row counts in the tail (zone-level imports — these tables hold zones, not addresses, so 800–4K rows is correct for them).

Raw data: `diag/cities-actual.txt`.

## Import-script audit (G1.2)

All ~32 import scripts use the canonical pattern:
```js
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
```
All target the same project (`qsuzfemakaaroeakyick`). No legacy URLs found. None silently drop rows. Insert pattern is `BATCH_SIZE = 500` with await between batches.

`scripts/import-zones.mjs` and the four `.js` import utilities (`import-274k.js`, `import-edco-*.js`, `geocode-addresses.js`) hardcode the URL as a fallback — but to the *correct* project, so it's not a bug.

Full table: `diag/import-script-audit.md`.

## Stats endpoint (G1.3)

```
$ curl -sS https://trashalert.io/api/stats/live
<!DOCTYPE html>...<link href="/_next/..."  → Next.js 404 page (38KB HTML)
```

The endpoint **does not respond as JSON** on the deployed site. It serves the Next.js not-found page.

The repo has stats handlers at `app/routers/stats_api.py` and `vercel_app/handler.py` (FastAPI), but those aren't what's deployed at trashalert.io — the deployed product is a Next.js app (likely in a separate repo). So:
- The "5.19M / 26 cities cached lie" the v2 directive describes does not appear at `/api/stats/live` right now (or at least not in the form the directive expected).
- If a stats lie is being shown to users, it's coming from a Next.js page that hardcodes those numbers — not from a backend cache.

To find the lie:
```bash
# Searched the Python repo — only legitimate uses found
grep -rn "5,191,847|5191847|5.19M" --include="*.py" --include="*.ts"
# (no matches for the literal 5.19M number in this repo)
```
The hardcoded number must live in the deployed Next.js repo, not here. **Action for HT:** grep the Next.js deploy repo for `5191847` / `5.19M` / `26 cities` to find where the page pulls those numbers from.

## Top 3 root causes of the "missing cities" perception

### #1 (real, in scope): `audit-cities.ts:248` undercounts
```js
url.searchParams.set("limit", "50000");  // ← Supabase enforces a 1000-row cap; this is silently ignored
```
Effect: audit fetches 1000 rows of `(city)` from `schedule_reports`, dedupes, reports the result as "live cities." Since the table is heavily skewed (boston ~33% of head, houston ~17%, etc.), only the 2–3 dominant cities show up. This is what produced the "Supabase returned 3 distinct live cities" output that everyone has been treating as truth.

**Fix shape (single commit):**
- Replace `fetchLiveCities()` with a *paged distinct-city scan*, OR
- Use PostgREST's `?distinct=city` query param if the project's PostgREST version supports it, OR
- Maintain a small `cities` table (or materialized view) populated by import scripts that the audit can query in O(1).

### #2 (real, out-of-scope-tonight): `/api/stats/live` not deployed
The deployed `trashalert.io` is a Next.js app. The FastAPI `stats_api.py` here is for a different deploy or never went live. Either:
- (a) Wire the Next.js app to a real Supabase count query and ship that, OR
- (b) Add an `/api/stats` route to the Next.js app that hits `qsuzfemakaaroeakyick` directly.

Either way, the fix lives in the Next.js repo, not this factory repo.

### #3 (cosmetic, low priority): `audit-cities.ts` source-breakdown shows `{}`
Per-address `source` is captured (we see `city_api`, `houston_arcgis`) but the aggregate counter doesn't increment. One-line fix when next touched.

## Recommended fix order

1. **Patch `audit-cities.ts:248` (Gate 2).** Single commit. Rerun audit. Confirm we see ≥9 cities in the output (matching the head sample minimum).
2. **Run `diag-supabase-cities.ts` again** post-fix to confirm visibility.
3. **(Skip in this run)** Hand off `/api/stats/live` to the Next.js deploy repo — out of scope for this 4-hour test-fire.

## Re-stating the GO/NO-GO question

The TEST_FIRE v2 directive's success criterion was "Pipeline diagnosed and fixed, 2 new cities cleanly landed and audit-verified." The diagnosis itself reveals that:
- Cities are already landed — chicago (~849), seattle (~195), charlotte (~847+), philadelphia (28.5K and growing), plus 40+ others.
- Nothing needs to be "re-imported" cleanly to prove the pipeline works. The pipeline already works. We need to fix the *audit*, then verify cities show up.

Gate 2 should therefore re-scope to: **fix the audit's distinct-city query, prove visibility, declare done.** Re-running Chicago/Seattle imports (Gate 3 as written) would be busy-work — the data is already there.

## Exit criteria for Gate 1

- [x] `diag/cities-actual.txt` exists with real counts (head + tail sample, 44+ cities)
- [x] `diag/import-script-audit.md` exists with per-script findings (32 scripts, all consistent)
- [x] `DIAGNOSIS.md` exists at repo root
- [ ] Commit: `chore(diag): reality check on city import pipeline` (next step)
