# CLAUDE CODE — COMPLETE TRASHALERT SETUP
## Single directive, no ping-pong with HT

**Assume:** `.env.local` is now present in this repo (Daisy just
SCP'd it from the Mac Mini). If it's NOT present, halt at Step 1
and report.

**You are continuing the SETUP.md run.** Steps 1-6 already completed
in commit a9cd889. Now finish Steps 7-11 and deliver the final verdict.

---

## STEP 1 — VERIFY .env.local

```bash
ls -la .env.local
```

If missing, STOP and report. Do not proceed.

If present, confirm required Supabase keys without printing values:

```bash
grep -l "SUPABASE_URL" .env.local && echo "SUPABASE_URL: present"
grep -lE "SUPABASE_(ANON|SERVICE_ROLE)_KEY" .env.local && echo "SUPABASE key: present"
grep -l "ANTHROPIC_API_KEY" .env.local && echo "⚠ ANTHROPIC_API_KEY present — REMOVING"
```

If `ANTHROPIC_API_KEY` is in the file, strip it:
```bash
grep -v "^ANTHROPIC_API_KEY" .env.local > .env.local.tmp && mv .env.local.tmp .env.local
```

That key would override OAuth and bill to API usage. It does not belong
in `.env.local` on any machine.

---

## STEP 2 — RUN PREFLIGHT

```powershell
.\preflight.ps1
```

Capture the full output to `preflight-output.txt`. Note exit code.

- Exit 0 = green
- Exit 1 = failures present
- Exit 2 = warnings only

---

## STEP 3 — RUN BASELINE AUDIT

Only if preflight exits 0 or 2 (not on exit 1):

```powershell
npm run audit:cities
```

Capture the full output to `audit-baseline-output.txt`.

Three outcomes possible — handle each:

### Outcome A: Clean pass
All live cities healthy. The audit script's assumptions match reality.
Proceed to Step 4 with a green verdict on the audit.

### Outcome B: API shape mismatch
Script reports "no collection_day in response" for most/all addresses.
This means my assumed response shape doesn't match the real
`/api/lookup` output. Capture a raw response sample:

```bash
curl -s "https://trashalert.io/api/lookup?address=200+W+Washington+St&city=Phoenix" > sample-response.json
cat sample-response.json
```

Note the actual field names in `SETUP_REPORT.md`. The audit script's
`validatePayload()` function needs to be updated to match — but do NOT
fix it yourself in this run. Report the finding and let HT adjust.

### Outcome C: Supabase query failed
Script warns "falling back to hardcoded city list." Capture the exact
Supabase error. The hardcoded list may miss cities. Note in report.

---

## STEP 4 — UPDATE SETUP_REPORT.md

Overwrite the existing `SETUP_REPORT.md` with a complete, final version:

```markdown
# Setup Report — TrashAlert
## {{ISO timestamp}} (updated)

## Commit from first pass
- SHA: a9cd889
- Message: chore(setup): organize directive files + wire audit script
- Files moved: 2 (audit-cities-v2.ts, property-managers-page.tsx)
- Files deleted: 1 (audit-cities.ts v1)
- Files installed: tsx@4.21.0

## .env.local verification
- Present: [Y/N]
- SUPABASE_URL: [present/missing]
- SUPABASE key: [present/missing]
- ANTHROPIC_API_KEY: [absent/stripped — should always be absent]

## Preflight
- Exit code: [0/1/2]
- Pass count: [N]
- Warn count: [N]
- Fail count: [N]
- Failures (if any):
  - [list]
- Warnings (if any):
  - [list]

## Baseline audit
- Outcome: [A clean / B shape mismatch / C supabase failed]
- Cities in DB: [N]
- Cities tested: [N]
- Addresses tested: [N]
- Pass rate: [N%]
- Source breakdown: [e.g., supabase: 45, republic: 8, recollect: 2]
- Cities healthy: [N]
- Cities degraded: [N]
- Cities broken: [N]
- If shape mismatch: raw sample response saved to sample-response.json

## Known issues carried forward
- factory_template.zip cleanup: [done by Daisy / still present]
- Remote URL capitalization: [fixed / not fixed]
- Node PATH propagation (cmd.exe child): [patch applied / not applied]

## Final verdict

**[GREEN | YELLOW | RED]**

- GREEN: fire DIRECTIVE_TEST_FIRE_4H.md tonight
- YELLOW: test-fire can run with these caveats: [list]
- RED: do not launch. Blockers: [list]

## Reasoning
[one paragraph explaining the verdict]

## Recommended next command
[the exact claude command to run next, if GREEN or YELLOW]
```

---

## STEP 5 — COMMIT THE REPORT

```bash
# SETUP_REPORT.md is gitignored per the first pass. Leave it local.
# But commit any incidental changes from this step (e.g., scripts folder
# adjustments) if any.
git status
# If there are unstaged changes related to this pass only, commit them:
git add -A
git commit -m "chore(setup): complete preflight + baseline audit" || echo "nothing to commit"
git push || echo "nothing to push"
```

---

## STEP 6 — STOP

Your job ends here. Do not fire the test directive. Do not start
feature work. HT reads SETUP_REPORT.md and decides.

Do not suggest wrapping up. Do not suggest what to do tomorrow. Just
finish the report and stop.

---

## HALT CONDITIONS

Stop and report to HT via SETUP_REPORT.md if:
- `.env.local` is still missing after Step 1
- Preflight exits 1 with failures
- Baseline audit crashes with an unhandled error
- You find an `ANTHROPIC_API_KEY` in `.env.local` (strip, then continue)
- Any repo file appears to have been modified by an external process
  since commit a9cd889

---

Execute.
