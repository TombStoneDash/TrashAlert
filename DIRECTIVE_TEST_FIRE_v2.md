# TRASHALERT — CLAUDE CODE TEST-FIRE v2
## 4-hour reality-matched sprint — April 17, 2026, 9:00 PM PT

**Purpose:** Figure out why city imports aren't landing in Supabase, fix it,
prove the pipeline by landing two cities cleanly. Then the main run can expand.

**Today's ground truth (from HT + status report):**
- Supabase project `qsuzfemakaaroeakyick` has **2 cities** (Austin, Boston)
- 16 city scripts exist on disk, most have been "run"
- Today's runs: Charlotte 847, Chicago 849, Seattle 195, Philly 28,500 (SIGKILL)
- Audit at 7:55 PM showed 3 cities (Austin, Boston, Phoenix) healthy
- `/api/stats/live` falsely claims 5.19M / 26 cities (cache lying)
- App Store: APPROVED April 4
- FB Ad: $0 spent — kill it
- Google Ads: 455 clicks/20K impressions last week, 1 disapproval

**Ceiling:** 4 hours. Hard stop.
**Success:** Pipeline diagnosed and fixed, 2 new cities cleanly landed and
audit-verified, `/api/stats/live` returning real numbers.

---

## LAUNCH COMMAND

From `C:\TombstoneDash\factory\trashalert\` on the Lenovo:

```powershell
claude --dangerously-skip-permissions `
  --model claude-opus-4-7 `
  --max-turns 200 `
  -p "$(Get-Content .\DIRECTIVE_TEST_FIRE_v2.md -Raw)"
```

Resume after crash:
```powershell
claude --dangerously-skip-permissions --continue
```

---

## EXECUTION RULES (NON-NEGOTIABLE)

1. One commit per fix. Never batch.
2. 20-min cap per diagnostic probe. Stuck → log in `BLOCKED.md` → move on.
3. **Never invent cities in Supabase.** If an import fails, it failed.
4. **Never declare a city "live" without the audit confirming.** `/api/stats/live`
   is lying. `/api/schedule?address=...&city=...` is ground truth.
5. `/api/schedule` is the real endpoint. Not `/api/lookup`. The earlier
   setup had this wrong.
6. Every commit deploys. Verify on Vercel.
7. Visual changes get `NEEDS VISUAL REVIEW` in commit message.
8. Never run Prisma `--accept-data-loss` or Supabase destructive migrations.
9. Checkpoint every 3 commits to `CHECKPOINT.md`.

---

## STEP 0 — READ FIRST

```bash
cat CHECKPOINT.md 2>/dev/null || echo "fresh start"
cat SETUP_REPORT.md | tail -50
cat scripts/audit-cities.ts | head -50
ls scripts/ | grep -v '^$'
git log --oneline -10
```

---

## GATE 1 — DIAGNOSIS (60 min)

Don't fix anything yet. Find the truth.

### G1.1 — Confirm Supabase actual state (10 min)
```bash
# Use SUPABASE_SERVICE_KEY or SUPABASE_SERVICE_ROLE_KEY from .env.local.
# Query distinct cities + count per city.
```

Write a small one-off script `scripts/diag-supabase-cities.ts`:

```typescript
// scripts/diag-supabase-cities.ts
// Reports actual city counts from schedule_reports.
import { createClient } from "@supabase/supabase-js";

const url = process.env.SUPABASE_URL ?? process.env.NEXT_PUBLIC_SUPABASE_URL!;
const key = process.env.SUPABASE_SERVICE_KEY
  ?? process.env.SUPABASE_SERVICE_ROLE_KEY
  ?? process.env.SUPABASE_KEY
  ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

const sb = createClient(url, key);

// Page through all rows in batches of 10000, collect city counts
const counts = new Map<string, number>();
let from = 0;
const batch = 10000;
while (true) {
  const { data, error } = await sb
    .from("schedule_reports")
    .select("city")
    .range(from, from + batch - 1);
  if (error) { console.error(error); break; }
  if (!data || data.length === 0) break;
  for (const row of data) {
    const c = (row.city ?? "(null)").toLowerCase().trim();
    counts.set(c, (counts.get(c) ?? 0) + 1);
  }
  if (data.length < batch) break;
  from += batch;
}

console.log(`Total distinct cities: ${counts.size}`);
console.log(`Total rows: ${[...counts.values()].reduce((a,b)=>a+b, 0)}`);
console.log(`\nPer-city counts (sorted):`);
for (const [city, n] of [...counts.entries()].sort((a,b) => b[1] - a[1])) {
  console.log(`  ${city.padEnd(25)} ${n}`);
}
```

Run:
```powershell
npx tsx --env-file=.env.local scripts/diag-supabase-cities.ts > diag/cities-actual.txt
```

This is the single source of truth for what's actually in the DB.

### G1.2 — Audit each city import script (30 min)
For each of the 16 scripts in `scripts/` that match `<city>.ts` / `<city>.py` /
similar pattern:

```bash
# For every city script, check:
# 1. Does it exit 0 when run?
# 2. Does it actually insert into Supabase or just fetch and print?
# 3. Is it writing to the RIGHT Supabase project?
# 4. Does it have a table write that's silently swallowing errors?
```

Don't RUN all 16 — just READ them. Look for the failure pattern. Document
in `diag/import-script-audit.md` with one row per script:

| Script | Has Supabase write? | Error handling? | Target project? | Last run? |
|---|---|---|---|---|

The likely findings based on the status report:
- Some scripts write to a different Supabase project (historical `SUPABASE_URL`)
- Some scripts "succeed" but silently skip all rows (upsert conflict, RLS)
- Some scripts have memory issues (Philly SIGKILL) — need batching

### G1.3 — Verify the cache/stats issue (10 min)
```bash
curl -s https://trashalert.io/api/stats/live | head -100
curl -s "https://trashalert.io/api/schedule?address=100+Military+Plaza&city=San+Antonio"
```

Confirm: `/api/stats/live` returns stale 5.19M/26 numbers.
Find where that endpoint lives in the codebase:
```bash
grep -rn "5,191,847\|5191847\|5.19M\|/api/stats/live" --include="*.py" --include="*.ts" --include="*.js"
```

Document what's generating the fake numbers — is it hardcoded? Cached
Redis/KV? Computed from a stale materialized view?

### G1.4 — Write DIAGNOSIS.md (10 min)
One file at repo root summarizing:
- Actual Supabase state (from G1.1)
- Import script audit findings (from G1.2)
- Stats endpoint truth (from G1.3)
- Top 3 root causes of missing cities
- Recommended fix order

**Exit criteria:**
- [ ] `diag/cities-actual.txt` exists with real counts
- [ ] `diag/import-script-audit.md` exists with per-script findings
- [ ] `DIAGNOSIS.md` exists at repo root
- [ ] Commit: `chore(diag): reality check on city import pipeline`

---

## GATE 2 — FIX THE #1 ROOT CAUSE (90 min)

Whichever root cause from Gate 1 is blocking the most cities — fix it.

### Likely scenarios and approach per each:

**Scenario A: Scripts writing to wrong Supabase project**
- Find the legacy `SUPABASE_URL` still hardcoded somewhere
- Update scripts to read from `process.env.SUPABASE_URL` consistently
- Ship fix as single commit
- Re-run ONE already-exists script (say Chicago — 849 records, known size) to verify it now lands in `qsuzfemakaaroeakyick`
- Re-run `diag-supabase-cities.ts` to confirm Chicago now present

**Scenario B: Scripts succeeding but silently dropping rows**
- Identify the specific conflict (duplicate primary key? RLS policy? CHECK constraint?)
- Run one script with verbose logging, log every insert + response
- Fix root cause (might need an upsert rather than insert, or RLS bypass
  via service-role key)
- Re-run and verify

**Scenario C: Memory issues (Philly SIGKILL)**
- Add batching: insert in chunks of 1000 with await between batches
- Re-run Philadelphia specifically — it was killed at 28,500 records, likely
  needs ~100K+ total
- Verify via `diag-supabase-cities.ts`

Whichever scenario — produce:
- One or two commits with the actual fix
- Re-run ONE specific city script to prove it works now
- Updated `diag/cities-actual.txt` showing the new row counts

**Exit criteria:**
- [ ] Root cause fixed, commit pushed, deploy verified
- [ ] One specific city went from "script ran" → "actually in DB" state
- [ ] `diag/cities-actual.txt` shows at least one new city appeared

---

## GATE 3 — LAND TWO CITIES CLEANLY (60 min)

Now that the pipeline is fixed, land two cities properly.

### G3.1 — Re-run Chicago (15 min)
```bash
# Whatever the actual invocation is — check scripts/chicago.ts for how it runs
npx tsx --env-file=.env.local scripts/chicago.ts
```

After:
```bash
npx tsx --env-file=.env.local scripts/diag-supabase-cities.ts | grep chicago
```

Should show ~849 rows (matching today's earlier run number).

### G3.2 — Re-run Seattle (15 min)
Same pattern. Expect ~195 rows.

### G3.3 — Audit both (15 min)
Add Chicago and Seattle landmark addresses to `scripts/audit-cities.ts`
(the `LANDMARK_ADDRESSES` map). Examples:

```typescript
chicago: [
  "121 N LaSalle St, Chicago, IL 60602",         // City Hall
  "400 S State St, Chicago, IL 60605",           // Harold Washington Library
  "111 S Michigan Ave, Chicago, IL 60603",       // Art Institute
],
seattle: [
  "600 4th Ave, Seattle, WA 98104",              // City Hall
  "1000 4th Ave, Seattle, WA 98104",             // Central Library
  "325 5th Ave N, Seattle, WA 98109",            // Space Needle
],
```

Then:
```powershell
$env:AUDIT_LOOKUP_PATH='/api/schedule'
npx tsx --env-file=.env.local scripts/audit-cities.ts
```

Expected: austin, boston, chicago, seattle all healthy. Phoenix may or
may not show (it was there at 7:55 PM; diagnose if it disappeared).
Houston's ward-based gap is NOT in scope — it's a known data problem.

### G3.4 — Verify in prod (10 min)
Hit `https://trashalert.io/api/schedule?address=121+N+LaSalle+St&city=Chicago`
directly. Real schedule should come back.

### G3.5 — Kill the stats cache (5 min)
If `/api/stats/live` is still lying, either:
- Bust the cache (Vercel → Redeploy from dashboard, or `vercel --prod --force`)
- If it's hardcoded, fix it with a real Supabase count query

Commit either way.

**Exit criteria:**
- [ ] Chicago and Seattle both in Supabase
- [ ] Both pass audit with ≥3 landmark addresses each
- [ ] Both work in production via `/api/schedule`
- [ ] `/api/stats/live` reflects reality (or is acknowledged stale in `BLOCKED.md`)

---

## GATE 4 — REPORT (30 min)

### G4.1 — Final audit
```powershell
$env:AUDIT_LOOKUP_PATH='/api/schedule'
npx tsx --env-file=.env.local scripts/audit-cities.ts > test-results/final-audit.txt
```

### G4.2 — Update CHECKPOINT.md
- Live cities in DB (from `diag-supabase-cities.ts` output)
- Pipeline status: fixed / partially fixed / still broken
- Next actions for the main run

### G4.3 — Write REPORT.md

```markdown
# Test-Fire Report v2 — TrashAlert
## {{ISO}} · {{duration}}

## DIAGNOSIS FINDINGS
[Summary from DIAGNOSIS.md]

## PIPELINE FIX
- Root cause: [specific]
- Commit(s): [sha, sha]
- Verification: [one city that went from not-in-DB to in-DB]

## CITIES LANDED THIS RUN
| City | Rows before | Rows after | Audit pass? |
|---|---|---|---|
| Chicago | 0 | 849 | ✅ |
| Seattle | 0 | 195 | ✅ |

## STATS ENDPOINT
- Was: 5.19M / 26 cities (cached lie)
- Now: [real number] / [real count]
- Fix: [cache bust / code fix]

## KNOWN GAPS (not fixed here)
- Houston ward-based collection unmapped
- Philadelphia incomplete import (28.5K of ~1M)
- 14 cities from roadmap have no scripts yet

## GO / NO-GO FOR MAIN RUN

**[GO | NO-GO]**

Reasoning: [paragraph]

Recommended main-run scope (if GO):
1. Complete Philadelphia import (memory-safe batching)
2. Wire the remaining 13 Tier-1 cities that have confirmed endpoints
3. Investigate ReCollect API (hauler multiplier — Waste Connections uses it)
4. Fix Google Ads disapproval
5. Kill FB ad at $0 spend
```

---

## OUT OF SCOPE

- ReCollect API integration (main run, not test-fire)
- New city scripts for cities with no existing code (main run)
- FB ad kill / Google Ads fix (HT manual, not agent work)
- Property manager tier / Portfolio monetization (separate run)
- Houston ward-based collection mapping (real research needed, not 4 hrs)

---

## EMERGENCY STOP

Halt if:
- Can't connect to Supabase at all (different problem than this run solves)
- Diagnosis Gate 1 takes more than 90 min (scope cut: skip Gate 2, write
  DIAGNOSIS.md as the deliverable, verdict NO-GO)
- Any Supabase write operation fails in a way that could corrupt existing
  Austin/Boston data
- Destructive migration would be required to fix the pipeline
- Auth flips from OAuth to API
- Rate limit blocks work for 2+ hours

---

## TIMELINE

| Gate | Duration | Cumulative |
|---|---|---|
| Gate 1: diagnosis | 60 min | 1:00 |
| Gate 2: fix root cause | 90 min | 2:30 |
| Gate 3: land 2 cities | 60 min | 3:30 |
| Gate 4: report | 30 min | 4:00 |

If overtime: cut Gate 3 item #2 (Seattle). Land one city clean > two rushed.

---

## GO

Read `_CONFIG.md` (if present), `SETUP_REPORT.md`, `CHECKPOINT.md`. Start Gate 1.

No ceremony. No celebration. No "wrapping up" language.

Ship.
