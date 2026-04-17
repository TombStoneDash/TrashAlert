# TRASHALERT — CLAUDE CODE SETUP DIRECTIVE
## Organize repo, wire audit script, verify pipeline — April 17, 2026

**Purpose:** Move the 8 new files at the repo root into their correct
locations, wire the audit script into `package.json`, install missing deps,
and verify the whole pipeline with `preflight.ps1`. One clean commit.

**Scope:** File organization + scripts wiring only. No feature work. No city
integrations. No directive execution. That's for the test-fire and main runs.

**Expected duration:** 10–20 minutes.

---

## LAUNCH

From the Lenovo, in PowerShell or Windows Terminal:

```powershell
cd C:\TombstoneDash\factory\trashalert
claude -p "$(Get-Content .\SETUP.md -Raw)"
```

Or paste the contents into an interactive `claude` session.

---

## RULES

1. **Investigate before moving.** Read the repo structure before assuming
   where anything goes. In particular, find out whether the Next.js app
   uses `app/` (App Router), `pages/` (Pages Router), or lives in a
   subdirectory like `frontend/` or `web/`.
2. **Ask before deleting.** If a file looks like someone else's work-in-
   progress, flag it — don't delete. (The only file we KNOW is safe to
   delete is `audit-cities.ts` v1, because it's explicitly superseded
   by v2.)
3. **One commit for the whole setup.** Title: `chore(setup): organize
   directive files + wire audit script`.
4. **Stop and report** after the commit lands. Do not keep going into
   other work.

---

## STEP 1 — INVESTIGATE (read, don't touch)

Run these and note the results in your working memory:

```
# Repo structure
ls
cat package.json 2>$null          # does it exist?
ls app 2>$null                    # Next.js App Router
ls pages 2>$null                  # Next.js Pages Router
ls src 2>$null                    # sometimes used
ls scripts 2>$null                # where to put audit script
ls frontend web 2>$null           # subdirectory Next.js?
cat CODEBASE_OVERVIEW.md
cat CODEBASE_QUICK_REFERENCE.md
cat ARCHITECTURE_DIAGRAM.txt
```

Answer these questions before moving anything:

- [ ] Where is the Next.js app? Root, `src/`, `frontend/`, or other?
- [ ] Is it App Router (`app/`) or Pages Router (`pages/`)?
- [ ] Does `package.json` exist? If so, what's in `scripts`?
- [ ] Is there already a `scripts/` folder? If not, can one be created at
      the repo root without conflicting with Python's `worker.py` workflow?
- [ ] Is Python (`worker.py`, `alembic.ini`) the backend API that serves
      `/api/lookup`, or does Next.js serve it? This tells us what the
      audit script is actually hitting.

---

## STEP 2 — MOVE FILES

Based on what Step 1 found, execute the moves below. Exact paths depend on
the Next.js layout — use your judgment, but follow these principles:

### 2A. `property-managers-page.tsx` — Next.js landing page
- If App Router: move to `app/for/property-managers/page.tsx`
  (create the intermediate directories)
- If Pages Router: move to `pages/for/property-managers.tsx`
  (rename from `-page` to fit Pages Router convention)
- If Next.js is in a subdirectory: prefix the path accordingly
- **DO NOT move** if the Next.js app is not in this repo at all. In that
  case, stop and report — you'll need HT's guidance.

### 2B. `audit-cities-v2.ts` → `scripts/audit-cities.ts`
- Create `scripts/` folder if missing
- Move and rename: `mv audit-cities-v2.ts scripts/audit-cities.ts`
- Then delete the stale v1: `rm audit-cities.ts`
  (the one dated 4/17/2026 12:48 PM from the screenshot — it's the v1
  that expects `/api/schedule` and `trash_day`, which is wrong)

### 2C. `preflight.ps1` — stays at repo root
No move needed.

### 2D. Directive files — stay at repo root for now
- `DAISY_DIRECTIVE_ROAD_TO_150M.md`
- `DAISY_DIRECTIVE_TEST_FIRE_4H.md`
- `DAISY_TRASHALERT_STANDDOWN.md`
- `TRASHALERT_PREFLIGHT_ANSWERS.md`

Optionally, create `directives/` and move them all there for cleanliness.
If you do this, update the launch commands in the directives themselves
to reflect the new path, AND update this file's own launch command.

### 2E. `DAISY_TRASHALERT_STANDDOWN.md` — actually belongs on Mac Mini
This directive is addressed to Daisy, who runs on the Mac Mini. It
shouldn't be committed to the TrashAlert repo at all. Two options:
- Leave it in place for now, HT will hand-deliver to Daisy
- Or: move to `directives/external/` to signal it's not repo-scoped
Either is fine. Don't just delete it.

---

## STEP 3 — WIRE `package.json`

If `package.json` exists (i.e., Next.js lives in this repo):

```json
{
  "scripts": {
    "audit:cities": "tsx scripts/audit-cities.ts"
  },
  "devDependencies": {
    "tsx": "^4.0.0"
  }
}
```

Then run:
```powershell
npm i -D tsx
```

If Next.js lives in a subdirectory (e.g., `frontend/`):
- The audit script can stay at the repo root under `scripts/`
- But `package.json` in that subdirectory is where the npm script goes
- Adjust: `"audit:cities": "tsx ../scripts/audit-cities.ts"` to get the
  relative path right

If there's no `package.json` anywhere (i.e., the whole frontend is
hosted elsewhere and this repo is Python-only):
- The audit script still runs — just invoke it with `npx tsx
  scripts/audit-cities.ts` directly
- Stop and report this. The directives assume `npm run audit:cities`
  works. They need a one-line fix if it doesn't.

---

## STEP 4 — VERIFY `.env.local`

The audit script needs `SUPABASE_URL` and `SUPABASE_ANON_KEY` (or
`SUPABASE_SERVICE_ROLE_KEY`). Check:

```powershell
Test-Path .env.local
```

If it exists, check whether the Supabase vars are in it (don't print
them, just confirm presence):

```powershell
Select-String -Path .env.local -Pattern "SUPABASE_URL" -Quiet
Select-String -Path .env.local -Pattern "SUPABASE_(ANON|SERVICE_ROLE)_KEY" -Quiet
```

If `.env.local` is missing, flag it in the final report. Do not invent
values. HT needs to SCP it from the Mac Mini.

---

## STEP 5 — VERIFY `.gitignore`

Make sure these are gitignored (add if missing):

```
.env.local
.env
node_modules/
test-results/
CHECKPOINT.md
REPORT.md
```

`CHECKPOINT.md` and `REPORT.md` are the agent's operational files for the
big runs — they shouldn't pollute git history.

---

## STEP 6 — COMMIT

One commit, clean message:

```
git add .
git commit -m "chore(setup): organize directive files + wire audit script"
git push
```

If pre-commit hooks fail, fix them and try again. If they fail in ways
you can't easily fix, stop and report.

---

## STEP 7 — RUN PREFLIGHT

```powershell
.\preflight.ps1
```

Capture the output. This is the moment of truth — it tests:
- Auth (OAuth vs. leaked API key)
- Repo + push access
- Vercel CLI
- `.env.local` presence
- Node / npm / tsx
- `npm run build` passes
- Power settings

If it exits 0: great, we're green.
If it exits 1 with warnings only: list the warnings, ask if HT wants to
  proceed anyway.
If it exits 1 with failures: list the failures, propose fixes, wait for
  HT's call.

---

## STEP 8 — BASELINE AUDIT (optional but recommended)

If preflight is green AND `.env.local` has Supabase creds:

```powershell
npm run audit:cities
```

Capture the output. This is the first real test of the audit script
against the actual API. Expect one of three outcomes:

**A. Clean pass.** Script queries Supabase, finds live cities, hits
   `/api/lookup` for landmark addresses in each, all sources check out,
   all cities healthy. This is the best case.

**B. API shape mismatch.** The script reports "no collection_day in
   response" for every address. This means the response uses a different
   field name. Capture a raw response (curl
   `https://trashalert.io/api/lookup?address=X&city=Y`) and flag for HT
   to update the script's `validatePayload()` function.

**C. Supabase query failed.** The script falls back to its hardcoded city
   list and warns. The hardcoded list might not match the 26 live cities.
   Capture the exact Supabase error and flag for HT.

Do NOT try to fix the audit script yourself. Report findings, stop.

---

## STEP 9 — FINAL REPORT

Write `SETUP_REPORT.md` with:

```markdown
# Setup Report — [ISO timestamp]

## Files moved
- [list each move, source → destination]

## Files deleted
- [list each deletion with reason]

## Files left in place (intentionally)
- [list with reason]

## package.json changes
- [diff summary]

## .env.local status
- Present / missing, Supabase vars present / missing

## .gitignore changes
- [what was added]

## Commit
- Hash: [sha]
- Pushed: Y/N
- Vercel deploy: [url if auto-deploy fires, N/A otherwise]

## Preflight result
- Exit code: [0/1]
- Summary: X pass / Y warn / Z fail
- Failures: [list or None]
- Warnings: [list or None]

## Audit baseline (if run)
- Outcome: A / B / C (see step 8)
- Details: [...]

## GREEN / YELLOW / RED verdict
- GREEN: safe to fire the 4-hour test directive tonight
- YELLOW: test directive can run but [list caveats]
- RED: do not launch. [list blockers]

## Next actions
1. [ordered]
```

---

## STOP CONDITIONS

Halt and ask HT if:
- The Next.js app is nowhere to be found in this repo
- `package.json` exists but has unexpected pre-commit hooks that fail
- `git push` fails for non-trivial reasons
- `preflight.ps1` flags a leaked `ANTHROPIC_API_KEY` (critical, HT needs
  to know immediately)
- You find `.env.local` already contains an `ANTHROPIC_API_KEY` — this
  would mean the repo itself is carrying the key into git history,
  which is a secret-leak problem

Otherwise, execute clean and report.

---

## DO NOT

- Do not start wiring cities
- Do not start the test-fire or 150M directive
- Do not touch Python files (`worker.py`, `alembic.ini`,
  `requirements.txt`, migration files)
- Do not modify `vercel.json` unless `package.json` wiring makes it
  strictly necessary
- Do not run `vercel --prod` — auto-deploy is fine for a chore commit

---

Read, investigate, move, commit, verify, report. Go.
