# TRASHALERT — CLAUDE CODE TEST-FIRE: 4-HOUR VALIDATION
## Pre-flight for the 150M overnight run — April 17, 2026

**Purpose:** Validate that the agent, directive format, discipline rules, commit
pipeline, and deployment chain all work end-to-end **before** committing 12 hours
of compute. This run does less, but it does it under the exact same constraints
so nothing surprises you overnight.

**Target:** +500K addresses and +3 live cities, cleanly, with full observability.
**Ceiling:** 4 hours. Hard stop.
**Success looks like:** Every commit deployed, every new city passing the audit,
CHECKPOINT.md current, REPORT.md readable, no reverts.

---

## LAUNCH COMMAND

From the TrashAlert repo root:

```bash
claude --dangerously-skip-permissions \
  --model claude-opus-4-7 \
  --max-turns 200 \
  -p "$(cat DAISY_DIRECTIVE_TEST_FIRE_4H.md)"
```

Resume (if it crashes or compacts):

```bash
claude --dangerously-skip-permissions --continue
```

---

## WHAT THIS RUN IS **NOT**

- Not the full 150M sprint. Ignore hauler APIs, county sweep, state datasets,
  pSEO at scale, Portfolio Tier build. Those are Tiers 3–7 of the big
  directive. They do not run here.
- Not a demo. Every commit deploys to production. Data is real.
- Not a free pass on discipline. Every rule in the big directive applies.

---

## GATE 1 (MUST PASS BEFORE ANY EXPANSION — 45 minutes)

If any step in Gate 1 fails, STOP the run, write the failure to
`CHECKPOINT.md`, and exit. Do not proceed to Gate 2.

### G1.1 — Repo sanity (5 min)
```bash
git status                     # must be clean or have only this directive
git log --oneline -5           # note starting commit
node -v && npm -v              # record versions
```

### G1.2 — Build locally (5 min)
```bash
npm ci
npm run build                  # MUST succeed before any new code lands
```
If this fails, FIX IT FIRST. Do not wire any new cities on a broken build.

### G1.3 — Tracking files (2 min)
```bash
touch CHECKPOINT.md CITIES_RESEARCHED.md REPORT.md
mkdir -p test-results source-docs scripts
```

### G1.4 — Supabase performance indexes (5 min)
Run via Supabase SQL editor or migration:
```sql
CREATE INDEX IF NOT EXISTS idx_schedule_reports_city ON schedule_reports(city);
CREATE INDEX IF NOT EXISTS idx_schedule_reports_address ON schedule_reports(address);
CREATE INDEX IF NOT EXISTS idx_schedule_reports_city_zip ON schedule_reports(city, zip);
```
Verify with:
```sql
SELECT indexname FROM pg_indexes WHERE tablename = 'schedule_reports';
```

### G1.5 — Install + run the audit script (20 min)
The audit script lives at `scripts/audit-cities.ts`. If it doesn't exist yet,
this is your first task:

1. Create `scripts/audit-cities.ts` (full source is in the companion file
   `audit-cities.ts` that HT provided — copy it verbatim, then adapt the
   `TEST_ADDRESSES` and the schedule lookup endpoint path to match what the
   repo actually exposes).
2. Add to `package.json`:
   ```json
   "scripts": {
     "audit:cities": "tsx scripts/audit-cities.ts"
   }
   ```
3. Install tsx if missing: `npm i -D tsx`
4. Run: `npm run audit:cities`
5. If any of the 9 existing cities are broken, FIX THEM FIRST. Do not wire
   any new city until the existing ones are audited healthy.
6. Commit: `chore(audit): add city audit script + initial baseline`
7. Save the first `test-results/audit-*.json` as the baseline.

### G1.6 — Deployment smoke test (8 min)
Make a trivial verifiable change — a comment, a timestamp in a footer, anything
— commit it, push it, and confirm it lands on `https://trashalert.io`:
```bash
git add .
git commit -m "chore(smoke): deployment smoke test"
git push
# Wait 2 min, then:
curl -s https://trashalert.io/ | grep -i "smoke test marker"
```
If the marker doesn't appear, run `vercel --prod` as fallback. If that still
doesn't land, DEPLOYMENT IS BROKEN — stop and flag.

**Gate 1 exit criteria:**
- [ ] `npm run build` passes
- [ ] Supabase indexes created
- [ ] `npm run audit:cities` exists and ran
- [ ] All 9 existing cities audited healthy (≥90% pass rate)
- [ ] Smoke-test commit deployed and visible at trashalert.io
- [ ] CHECKPOINT.md has Gate 1 results written down

If all checks pass, remove the smoke-test marker in a follow-up commit and
proceed to Gate 2.

---

## GATE 2 — WIRE THREE CONFIRMED CITIES (2 hours)

Pick the three highest-leverage cities from Tier 1 of the big directive. These
already have confirmed ArcGIS endpoints from prior research, so there's no
discovery risk — this run validates the wiring pattern, not research skill.

### G2.1 — San Antonio (~350K addresses)
Endpoint: `gis.sanantonio.gov/swmd/mycollectionday`

Process:
1. Curl the page. Find the underlying FeatureServer / MapServer URL in the
   JavaScript or network requests.
2. Document fields (zone id, day of week, any holiday calendar reference) in
   `source-docs/san-antonio.md`.
3. Write `lib/cities/san-antonio.ts`:
   - `geocode(address) → { lat, lng }` (use existing Mapbox helper)
   - `zoneForCoord({ lat, lng }) → zoneId` (ArcGIS point-in-polygon query)
   - `scheduleForZone(zoneId) → { trashDay, recyclingDay, bulkPickup, holidays }`
4. Register in `lib/city-geocode.ts`.
5. Test with ≥3 real San Antonio addresses. Save responses to
   `test-results/san-antonio.json`.
6. Add `SOURCE_REGISTRY.md` entry:
   ```
   ## San Antonio, TX
   - Source: gis.sanantonio.gov/swmd/mycollectionday
   - Type: ArcGIS FeatureServer (public)
   - Verified: 2026-04-17
   - Addresses: ~350,000
   - Permission basis: City of San Antonio public GIS
   - Sample tests: test-results/san-antonio.json
   ```
7. Commit: `feat(cities): wire up San Antonio (~350k addresses)`
8. Push. Verify Vercel deploy lands.
9. Hit the production URL with one of your test addresses. Confirm real data
   comes back.
10. Update CHECKPOINT.md.

### G2.2 — Indianapolis (~300K addresses)
Endpoint: `gistest.indy.gov/server/rest/services/OpenData/OpenData_SolidWasteCollectionAreasFS/MapServer`
Same pattern as G2.1. New city = new commit = new deploy = new audit entry.

### G2.3 — Baltimore (~250K addresses)
Endpoint: `geodata.baltimorecity.gov/egis/rest/services/CityView/Trash_Recycle_Day/MapServer`
Same pattern.

**Rules during Gate 2:**
- Hard cap of 40 minutes per city. If you're still fighting one at 40 min,
  stop, log what's blocking in `CITIES_RESEARCHED.md`, move on.
- After each city goes live, re-run `npm run audit:cities` (now including
  the new city in `TEST_ADDRESSES`). All cities must still be healthy.
- One commit per city. No batching. No "fix a bunch of stuff" commits.

**Gate 2 exit criteria:**
- [ ] San Antonio live, audit passes
- [ ] Indianapolis live, audit passes
- [ ] Baltimore live, audit passes
- [ ] All 9 original cities still passing audit
- [ ] Homepage numbers updated to reflect new total
- [ ] REPORT.md written with 2-hour summary

---

## GATE 3 — ONE PROGRAMMATIC-SEO PAGE, ONE ITERATION (45 minutes)

Validate the pSEO template on a single city so the full 500+ page run
overnight has a proven pattern.

### G3.1 — Build the template (25 min)
Create `app/schedule/[city]/page.tsx` as a dynamic route that:
- Takes `city` slug param
- Reads city metadata from a config (hauler name, bin types, holiday calendar)
- Renders: H1, live lookup widget, hauler info, FAQ, schema.org structured data
- Sets canonical URL and meta tags
- Returns 404 for unknown cities

### G3.2 — Generate ONE page (10 min)
For San Antonio specifically:
- Create `content/cities/san-antonio.mdx` (or equivalent config) with 200+ words
  of unique hand-researched copy: hauler (City of San Antonio Solid Waste
  Management Department), service area notes, holiday calendar.
- Verify page renders at `/schedule/san-antonio`.

### G3.3 — Submit to Search Console (5 min)
- Update `sitemap.xml` to include the new page.
- Log the URL for manual submission in REPORT.md (don't actually hit GSC in
  this run — batch submission is for the big run).

### G3.4 — Commit & verify (5 min)
```
feat(pseo): city schedule template + san antonio page
```

**Gate 3 exit criteria:**
- [ ] `/schedule/san-antonio` returns 200, renders real content
- [ ] Structured data validates against Google's Rich Results test (manual
      check noted in REPORT.md)
- [ ] Sitemap.xml updated
- [ ] No other cities have pSEO pages yet (that's the big run's job)

---

## GATE 4 — FINAL AUDIT, REPORT, CHECKPOINT (30 minutes)

### G4.1 — Full audit run
```bash
npm run audit:cities
```
Save to `test-results/audit-final-4h.json`. All 12 cities (9 original + 3 new)
must pass.

### G4.2 — Homepage accuracy
Update:
- Hero address count → new total including ~900K new addresses
- "Cities Live" badge → 12
- Stats section → match

Commit: `chore(site): update homepage for +3 cities`

### G4.3 — Write the final REPORT.md
Use the format from the big directive. Must include:
- Starting state
- Every commit deployed with hash
- Every city test-results JSON path
- Any blockers hit
- Clear handoff paragraph: "Ready for full 12-hour run: Y/N, and why"

### G4.4 — Write the go/no-go verdict
At the bottom of REPORT.md, the agent writes one of:

**GO** — if:
- All gates passed
- No reverts
- Audit healthy
- Deployment chain verified twice (G1.6 and G2.1)
- No surprises

**NO-GO** — if any of the above failed. Include exactly what to fix before
the 12-hour run.

---

## SCOPE-DISCIPLINE REMINDERS

Things that are TEMPTING but OUT OF SCOPE for this 4-hour run:

- ❌ Hauler API attempts (WM, Republic, etc.) — deferred to big run
- ❌ County-level integrations — deferred
- ❌ More than 3 new cities — deferred
- ❌ Portfolio Tier build — deferred
- ❌ Ad / analytics / Stripe work — deferred
- ❌ Rebranding, visual redesign — deferred
- ❌ "While I'm in here" refactors — NO. Ship the directive, nothing else.

The point of this run is to prove the pipeline, not to make the most progress.
Progress overnight is cheaper than progress right now.

---

## EMERGENCY STOP CONDITIONS

Halt immediately and write to CHECKPOINT.md if:
- `npm run build` breaks and can't be fixed in 15 min
- Deployment chain fails twice in a row
- Any existing city drops to broken in the audit
- You hit a Supabase rate limit or quota error
- You find yourself drafting a commit that touches >5 files

On halt: write a clear SUMMARY.md explaining the failure mode, expected cause,
and proposed fix. That's the artifact you hand back to HT.

---

## EXPECTED TIMELINE

| Phase | Duration | Cumulative |
|---|---|---|
| Gate 1: pre-flight + audit baseline | 45 min | 0:45 |
| Gate 2: wire 3 cities | 2 hr | 2:45 |
| Gate 3: pSEO template + 1 page | 45 min | 3:30 |
| Gate 4: final audit + report | 30 min | 4:00 |

Finish under 4 hours. If you're running long, skip Gate 3 (pSEO is least
critical for pipeline validation) rather than compressing Gate 2 or Gate 4.

---

## GO

Read CHECKPOINT.md (may be empty), then start Gate 1.

No ceremony. No celebration. When you finish, the artifact is:
- A clean Vercel production with 12 live cities
- A green audit
- A REPORT.md that says **GO** or says exactly what needs to be fixed before
  the 12-hour run

Ship it.
