# TRASHALERT — CLAUDE CODE DIRECTIVE: ROAD TO 150M
## 12+ Hour Autonomous Sprint — April 17, 2026

**Mission:** Wire up every publicly accessible municipal, county, state, and hauler trash/recycling data source in the United States until no more remain or the session ends. Target the full 150M US residential addresses. Fall back gracefully where data is locked.

**Current baseline:** ~6.28M addresses across 44+ cities in `schedule_reports` per the 2026-04-18 diagnostic (see `DIAGNOSIS.md`). Heaviest by row count: boston, houston, san-antonio, dallas, philadelphia, san-francisco, denver, austin, phoenix. Long tail (28) is the EDCO / north-county-SD bundle (escondido, vista, san marcos, encinitas, fallbrook, el cajon, la mesa, lakewood, etc.) plus charlotte, chicago, seattle from recent imports. Note: several of these are zone-level data that `/api/schedule` doesn't yet resolve by address (e.g. chicago, houston report `found:false` — data exists in DB, address→zone resolver is the gap).
**Stop conditions:** No new sources findable after exhaustive search, OR 12 hours elapsed, OR explicit user halt.
**Non-stop condition:** Context compaction. You recover via the resume protocol and continue.

---

## LAUNCH COMMAND

From the TrashAlert repo root:

```bash
claude --dangerously-skip-permissions \
  --model claude-opus-4-7 \
  --max-turns 500 \
  -p "$(cat DAISY_DIRECTIVE_ROAD_TO_150M.md)"
```

If session terminates or compacts:

```bash
claude --dangerously-skip-permissions --continue
```

Checkpoint state lives in `~/trashalert/CHECKPOINT.md`. Always read it first on resume.

---

## RESUME PROTOCOL (READ FIRST ON EVERY COLD START)

Before doing anything else:

1. `cat CHECKPOINT.md` — last known state
2. `cat SOURCE_REGISTRY.md | tail -100` — what's already wired
3. `git log --oneline -30` — recent commits
4. `cat CITIES_RESEARCHED.md` — what's been tried, what failed, what's pending
5. Pick up from the "NEXT ACTION" line in CHECKPOINT.md.

After every 3 commits, append to CHECKPOINT.md:
```
## Checkpoint [ISO timestamp]
- Commits since last checkpoint: [list with hashes]
- Cities live: [count], addresses: [running total]
- Current tier: [N]
- NEXT ACTION: [exact next step if resumed cold]
```

---

## THE MATH — WHY 150M

US residential addresses total: ~150M. Current: 4.8M = 3.2% of US homes. The top 100 US cities by population = ~25M households. Top 500 = ~55M. Waste Management + Republic Services + Waste Connections + GFL + Casella + WasteConnections combined serve ~60M+ customer endpoints. County + state datasets cover another ~25M in suburban/rural overlay.

**The multipliers in order of leverage:**
1. **Hauler APIs** — one successful integration = 5-20M addresses
2. **County-level ArcGIS** — one county = 100K to 1.5M addresses
3. **State aggregators** — NJ Recycle Coach state contract, CalRecycle, etc.
4. **City ArcGIS/Socrata** — 50K to 1M per city
5. **National Address DB overlay** — pre-compute zones against NAD

Do all five in parallel across the session. Don't serialize into one strategy.

---

## EXECUTION RULES (NON-NEGOTIABLE)

1. **One commit per source integration.** Change → local test → commit → push → verify Vercel deploy → THEN next source. No batches.
2. **30-minute research cap per city.** If no public endpoint found in 30 min, downgrade to "coming soon" with waitlist, log in CITIES_RESEARCHED.md, move on.
3. **Every new source gets a SOURCE_REGISTRY.md entry** with: source URL, data type (ArcGIS/Socrata/hauler-API/scraped/FOIA), last verified date, address count, sample address tested, response format notes.
4. **Test every integration with ≥3 real residential addresses** in that jurisdiction before marking live. Log test addresses + responses in `test-results/[city-slug].json`.
5. **Never fake data.** If the API returns nothing for a valid address, the city is not "live" — it's in degraded state. Never seed fake schedules to inflate numbers.
6. **Respect robots.txt + ToS.** No scraping where explicitly disallowed. Prefer official ArcGIS endpoints, Socrata, and documented public APIs. Document each source's permission basis.
7. **Rate limit every outbound call.** 1 req/sec default per endpoint, exponential backoff on 429/503. Never hammer a municipal server.
8. **No Prisma `--accept-data-loss`, no Supabase destructive migrations** without creating a backup branch first.
9. **Visual changes get `NEEDS VISUAL REVIEW` in commit message.** You're headless. You can't judge rendering.
10. **If Vercel auto-deploy fails silently, run `vercel --prod`** as fallback. Check every deploy lands.
11. **If a city's data source is blocked by reCAPTCHA Enterprise / Salesforce Visualforce Remoting** (like San Diego GetItDone), log it as `BLOCKED_NEEDS_FOIA` and move on. Do not burn hours.
12. **Update homepage numbers after every 5 new live cities.** Accurate counts only.

---

## TIER 0: PRE-FLIGHT — FIX EXISTING BROKEN STATE

Complete before any new city work.

### 0A. Supabase Performance Index
```sql
CREATE INDEX IF NOT EXISTS idx_schedule_reports_city ON schedule_reports(city);
CREATE INDEX IF NOT EXISTS idx_schedule_reports_address ON schedule_reports(address);
CREATE INDEX IF NOT EXISTS idx_schedule_reports_city_zip ON schedule_reports(city, zip);
```

### 0B. Fix Dallas (currently claiming 253K with no API)
ChatGPT analysis pending — research `Dallas ArcGIS sanitation services`, `dallascityhall.com trash schedule API`, `gis.dallascityhall.com REST services`. If no public endpoint → "coming soon."

### 0C. Fix San Antonio (currently claiming 347K with no API)
Endpoint: `gis.sanantonio.gov/swmd/mycollectionday/default.html` — wire the underlying ArcGIS service.

### 0D. Audit the 9 currently "live" cities
For each of NYC, LA, Houston, Philly, Phoenix, Austin, Denver, Boston, EDCO SD:
- Hit 5 random real addresses
- Verify real schedule returned, not fallback
- Log results in `test-results/audit-2026-04-17.json`
- Fix any silently-broken integrations BEFORE expanding

### 0E. Baseline Homepage
After 0A-0D, update hero and stats to reflect audited reality. No inflated numbers.

### 0F. Create tracking files if missing
```bash
touch CHECKPOINT.md CITIES_RESEARCHED.md HAULERS_RESEARCHED.md
mkdir -p test-results source-docs
```

---

## TIER 1: CONFIRMED ENDPOINTS — TOP 10 (Target: +2.5M)

Wire these in order. Each one is already scoped by prior research.

| # | City | Est. Addresses | Endpoint |
|---|------|---|---|
| 1A | San Antonio | 350K | `gis.sanantonio.gov/swmd/mycollectionday` |
| 1B | Indianapolis | 300K | `gistest.indy.gov/server/rest/services/OpenData/OpenData_SolidWasteCollectionAreasFS/MapServer` |
| 1C | Baltimore | 250K | `geodata.baltimorecity.gov/egis/rest/services/CityView/Trash_Recycle_Day/MapServer` |
| 1D | Oklahoma City | 250K | `okc.maps.arcgis.com/apps/instant/basic/index.html?appid=837d288b446d493d9f63b47f3208eb6d` |
| 1E | Albuquerque | 200K | `cabq.gov/gis/address-report` |
| 1F | Tucson | 200K | `experience.arcgis.com/experience/0b8b033f0303402c95c2ef41e2c7f337` |
| 1G | Riverside | 100K | `mapriverside.riversideca.gov/server/rest/services/Waste/SolidWaste/MapServer/3` |
| 1H | San Jose | 350K | `sanjoseca.gov/.../utility-services-lookup` |
| 1I | Charlotte | 300K | `experience.arcgis.com/experience/19bcaee4275e4a278dd452f5056590f2/page/My-Charlotte-Lookup` |
| 1J | Kansas City MO | 200K | ArcGIS parcel viewer `Trash_Pick_Up_Days` layer |

**Pattern for each:**
```
1. curl the endpoint, discover the underlying FeatureServer/MapServer URL
2. Inspect fields — find day-of-week + zone ID attributes
3. Write `lib/cities/[city-slug].ts` with geocode → zone lookup → schedule function
4. Add city to the registry in `lib/city-geocode.ts`
5. Test 3+ real addresses
6. Add SOURCE_REGISTRY.md entry
7. Commit: `feat(cities): wire up [City] (~Xk addresses)`
8. Push, verify Vercel deploy
9. Update CHECKPOINT.md
```

---

## TIER 2: TOP 50 US CITIES — RESEARCH + WIRE (Target: +8-12M)

For every city not already covered in Tiers 0-1, in order of 2025 Census population rank:

Jacksonville FL, Columbus OH, Fort Worth TX, Nashville TN, Memphis TN, Louisville KY, Milwaukee WI, Las Vegas NV, Sacramento CA, Mesa AZ, Virginia Beach VA, Atlanta GA, Omaha NE, Raleigh NC, Long Beach CA, Minneapolis MN, Tampa FL, St. Louis MO, Pittsburgh PA, Cincinnati OH, Cleveland OH, Aurora CO, Colorado Springs CO, Anaheim CA, Santa Ana CA, Corpus Christi TX, Lexington KY, Stockton CA, Henderson NV, Saint Paul MN, St. Petersburg FL, Newark NJ, Plano TX, Greensboro NC, Lincoln NE, Buffalo NY, Jersey City NJ, Chula Vista CA, Orlando FL, Norfolk VA, Chandler AZ, Laredo TX, Madison WI, Winston-Salem NC, Lubbock TX, Baton Rouge LA, Durham NC, Garland TX, Glendale AZ, Reno NV.

**Research sequence per city (30-min cap):**
```
1. Search: "[city] ArcGIS trash collection day"
2. Search: "[city] open data solid waste schedule"
3. Search: "[city] GIS rest services sanitation"
4. Check: data.[city].gov, opendata.[city].gov, gis.[city].gov
5. Check: [city].maps.arcgis.com
6. Inspect network traffic on their public schedule lookup page
7. If found → wire it, test, commit, move on
8. If not found → mark "coming soon" in UI, waitlist form live,
   log in CITIES_RESEARCHED.md with: what was searched, what was found,
   contact email for FOIA follow-up
```

Do not stop Tier 2 mid-list because of a hard one. Skip and continue. You can come back.

---

## TIER 3: HAULER API INTEGRATIONS — THE MULTIPLIER (Target: +15-30M)

This is where a single successful integration adds millions. Invest serious effort here, but cap each hauler at 2 hours before moving on.

### 3A. Republic Services (~14M customers)
- Schedule lookup URL: `republicservices.com/customer-support/my-schedule`
- Inspect network tab — look for JSON API behind the lookup form
- Check for Algolia index, GraphQL endpoint, or REST API
- If zipcode-only lookup: build zipcode → schedule map
- If address-level: wire it end to end

### 3B. Waste Management (~21M customers)
- Schedule lookup URL: `wm.com/us/en/myaccount/schedule-pickup`
- MyWM app almost certainly hits a public-facing API
- Inspect with Chrome DevTools network panel replay
- Document auth flow if needed

### 3C. Waste Connections (~8M customers)
- Regional operating companies each have their own portals — map them
- Check for a shared backend

### 3D. GFL Environmental (~5M customers)
- Check municipal contracts + customer portal

### 3E. Casella Waste Systems (~1M customers, Northeast)
### 3F. Advanced Disposal / WM (merged)
### 3G. Rumpke (Ohio, ~1M)
### 3H. Waste Pro USA (~2M, Southeast)
### 3I. LRS (Lakeshore Recycling Systems, Midwest)
### 3J. Recology (~800K, SF Bay Area)

**Pattern for each hauler:**
```
1. Open their residential schedule lookup page
2. Enable network recording
3. Submit a real address from a known service area
4. Capture every XHR/fetch request
5. Document: endpoint URL, method, headers, payload, response shape
6. Check if auth token is required (and whether it's obtainable anonymously)
7. If viable: build `lib/haulers/[hauler-slug].ts`
8. Geocode → determine if address is in hauler's service area → call their API
9. Test 10+ real addresses across 5+ states
10. Commit: `feat(haulers): integrate [Hauler] (~XM customers)`
11. Log contract-level permission basis in SOURCE_REGISTRY
```

**If blocked:** document exactly what blocks (auth wall, captcha, cloudflare, WAF), log in HAULERS_RESEARCHED.md, try the next one. Never burn more than 2 hours on one hauler in a single pass.

---

## TIER 4: COUNTY-LEVEL ARCGIS SWEEP (Target: +10M)

Counties publish collection zone polygons more consistently than cities. Attack the top 100 US counties by population.

Start with (in order): Los Angeles County, Cook County IL, Harris County TX, Maricopa County AZ, San Diego County, Orange County CA, Miami-Dade County, Dallas County TX, Kings County NY (Brooklyn — covered by NYC), Queens County NY, Riverside County CA, San Bernardino County CA, King County WA, Tarrant County TX, Santa Clara County CA, Broward County FL, Bexar County TX, Wayne County MI, Alameda County CA, Middlesex County MA, Suffolk County NY, Sacramento County CA, Bronx County NY, Clark County NV, Palm Beach County FL, Hillsborough County FL, Oakland County MI, Orange County FL, Franklin County OH, Hennepin County MN, Fairfax County VA, Contra Costa County CA, Salt Lake County UT, Montgomery County MD, Pima County AZ, Honolulu County HI, Travis County TX, Wake County NC, Mecklenburg County NC, Cuyahoga County OH, DuPage County IL, Allegheny County PA, Fresno County CA, Prince George's County MD, Kern County CA, Fulton County GA, Westchester County NY, Shelby County TN, Nassau County NY, Erie County NY.

**Per-county pattern (20-min cap):**
```
1. Check [county].gov/gis OR gis.[county].gov
2. Search ArcGIS Hub for "[county name] solid waste" or "sanitation"
3. Check for franchise/hauler zone datasets
4. If unincorporated areas have county-contracted pickup, wire the zone map
5. Cross-reference with known hauler APIs from Tier 3
6. Commit + log
```

---

## TIER 5: STATE-LEVEL + FEDERAL DATA

### 5A. New Jersey — Recycle Coach State Contract
NJ has a statewide Recycle Coach integration. Check for public data access or partnership path. Log contact for B2G outreach.

### 5B. California — CalRecycle
- `calrecycle.ca.gov` publishes SB 1383 compliance data
- Jurisdiction Program data may include collection schedules
- Inspect `data.ca.gov` for waste-related datasets

### 5C. Massachusetts — MassDEP
- `mass.gov/orgs/massachusetts-department-of-environmental-protection`
- Check for municipal program datasets

### 5D. Washington State — Ecology
### 5E. Oregon — DEQ
### 5F. Vermont — ANR Solid Waste Districts

### 5G. Federal — US DOT National Address Database
- Download NAD for backbone address coverage
- Overlay collection zone polygons from all integrated cities/counties/haulers
- Pre-compute schedules into a Supabase materialized view
- This creates fallback address coverage for addresses not yet in our main index

### 5H. data.gov
Search for any federal waste collection datasets. Likely limited, but worth 30 minutes.

---

## TIER 6: PROGRAMMATIC SEO AT SCALE (Runs in parallel)

For every city researched in Tiers 1-3 (whether wired live or "coming soon"), generate a landing page at `/schedule/[city-slug]` that captures search intent.

**Template fields per page:**
- H1: "[City] Trash Pickup Schedule & Recycling Calendar"
- Status badge: "Live" / "Coming Soon — Join Waitlist"
- If Live: address lookup widget prominent above the fold
- If Coming Soon: email capture, promise of launch notification
- Hauler name, bin types, holiday calendar (research from city website)
- FAQ section: "When is trash day in [city]?", "Does [city] collect on [holidays]?", "Who is the trash hauler in [city]?"
- Neighborhood sub-pages if city is large (e.g., /schedule/nyc/brooklyn-heights)
- Structured data: LocalBusiness schema, FAQPage schema, BreadcrumbList
- Internal links to 5 nearby cities + to national map
- Meta title: "[City] Trash Pickup Schedule 2026 | TrashAlert"
- Meta description: "Find your [City] trash pickup day, recycling schedule, and holiday calendar. Free reminders by email or SMS."

**Rules:**
- Every page must have unique, non-templated text in at least 200 words
- Pull real hauler names and holiday schedules from city websites
- No fake reviews, no fake testimonials
- Canonical tags correct
- Submit sitemap to Google Search Console after every 20 new pages

Target: 500+ pages by end of session.

---

## TIER 7: PORTFOLIO TIER MVP — $99/MONTH (Build in background)

The monetization layer. Build in parallel once Tiers 1-3 are producing.

### 7A. Bulk address upload
- CSV upload at `/portfolio/upload`
- Column mapping UI
- Deduplicate + geocode + lookup schedules
- Store in `portfolio_addresses` table under `portfolio_account_id`

### 7B. Dashboard
- All addresses visible
- Next pickup date per address
- Holiday changes highlighted
- Export to CSV / iCal

### 7C. Weekly digest email
- Every Sunday evening
- Per-property-manager summary of next week's pickups
- Highlights holiday changes
- Send via Resend

### 7D. Resident-facing share
- Each address gets a share URL `/share/[token]`
- Printable move-in packet PDF
- QR code for residents to add to their phone

### 7E. Stripe checkout
- $99/month, 14-day free trial
- Webhook creates portfolio account
- Plan limits: 50 addresses (Starter), 250 (Growth), unlimited (Enterprise)

### 7F. Landing page
- `/for/property-managers`
- Pain-point focused headline
- Pricing table
- Testimonial placeholders (to be filled post-launch, do NOT fabricate)

---

## TIER 8: TRUST + POLISH (Always running)

Every hour, do one of these:

- Run Lighthouse on 3 random pages. Log scores. Fix any regressions.
- Check Google Search Console for indexing errors, fix.
- Check Sentry (if installed) / Vercel logs for errors, triage top 3.
- Run `npm run build` locally to catch TypeScript errors early.
- Update `robots.txt` and `sitemap.xml` if new routes added.
- Verify no PII in logs.
- Review recent commits for accidental secrets leakage.

---

## TIER 9: DATA QUALITY + VERIFICATION (Every 2 hours)

Run the audit skill:

```bash
npm run audit:cities
```

This hits 10 random real addresses in every "live" city and verifies:
- Address geocodes correctly
- Schedule is returned (not a fallback)
- Day-of-week makes sense (no "trash day: Funday")
- Holiday adjustments apply where expected

Log results to `test-results/hourly-[timestamp].json`. If any city drops below 90% pass rate, move it to "degraded" status in UI and open an issue.

---

## SACRED FILES — DO NOT MODIFY WITHOUT EXPLICIT APPROVAL

- `prisma/migrations/**/production*.sql`
- `.env.production`
- `vercel.json` (unless required for new route)
- Any file in `/archive/**`
- `SOURCE_REGISTRY.md` historical entries (append only, never edit past entries)
- Payment logic in `lib/stripe/webhook.ts`

---

## COMMIT MESSAGE STANDARDS

- `feat(cities): wire up [City] (~Xk addresses)` — new city live
- `feat(haulers): integrate [Hauler] (~XM customers)` — hauler integration
- `feat(counties): wire up [County] (~Xk addresses)` — county integration
- `feat(pseo): generate landing pages for [N] cities` — SEO batch
- `feat(portfolio): [component]` — Portfolio tier work
- `fix(cities): [City] schedule lookup returning fallback` — bug fix
- `chore(registry): log [source]` — SOURCE_REGISTRY update
- `perf(db): [change]` — Supabase / query work
- `docs: update CHECKPOINT.md` — checkpoints

Every commit message includes estimated address delta where applicable.

---

## REPORT FORMAT (Write to REPORT.md every 2 hours)

```markdown
## TrashAlert Sprint Report — [ISO timestamp]

### Addresses
- Starting: [N]
- Added this session: [N]
- Running total: [N]
- % of US homes (150M): [X%]

### Cities
- Live at start: [N]
- Added live: [list with commits]
- Added "coming soon": [list]
- Blocked / FOIA-needed: [list with reasons]

### Haulers
- Integrated: [list]
- Attempted but blocked: [list with blocker]
- Untouched: [list]

### Counties
- Wired: [list]
- Researched but no endpoint: [list]

### Programmatic SEO
- Pages generated: [N]
- Sitemap submitted: [Y/N]
- New indexed in GSC: [N]

### Portfolio Tier
- Components shipped: [list]
- Remaining: [list]

### Known issues
- [list]

### Next 2 hours
- [ordered list of next actions]
```

---

## MILESTONES (Ambition ladder)

| Milestone | Addresses | % of US | Status |
|-----------|-----------|---------|--------|
| Current | 4.8M | 3.2% | ✅ |
| Tier 0 complete | 5.4M | 3.6% | 🔧 |
| Tier 1 complete | 7.9M | 5.3% | 🎯 |
| Tier 2 complete (40/50 cities wired) | 16M | 10.7% | 🎯 |
| First hauler live | 25-45M | 17-30% | 🎯 |
| Two haulers live | 45-65M | 30-43% | 🎯 |
| County sweep 50% done | 55-75M | 37-50% | 🎯 |
| Three haulers + 100 counties | 80-100M | 53-67% | 🎯 |
| National coverage | 150M | 100% | 🏆 |

---

## WHAT SUCCESS LOOKS LIKE AT HOUR 12

Minimum acceptable:
- Tier 0 fully complete
- Tier 1 all 10 cities wired
- 20+ of Tier 2's 50 cities wired
- At least 1 hauler API integrated (even partial)
- 100+ pSEO pages live
- Portfolio Tier landing page + CSV upload working
- All 9 original cities audited, degraded ones flagged
- CHECKPOINT.md current
- REPORT.md current

Stretch:
- 2 haulers live
- 40+ cities wired
- 25+ counties integrated
- Portfolio Tier Stripe checkout live
- 500+ pSEO pages
- 50M+ addresses total

---

## EMERGENCY RULES

If you find yourself:
- **Looping on the same endpoint for >45 min** → stop, log as blocked, move on
- **Writing fake test data to show progress** → stop, revert, flag to user
- **Hitting Supabase rate limits** → slow ingestion to 1 addr/sec, batch inserts
- **Building a new feature not in this directive** → stop, finish current tier first
- **About to run any `DELETE`, `DROP`, `TRUNCATE`, or Prisma `--accept-data-loss`** → stop, write the command to a migration file, flag for user approval, continue with other work
- **Seeing "Everything up-to-date" on git push but expecting new commits** → investigate, you didn't actually commit
- **Vercel build failing on new city code** → revert immediately, fix locally, retry. Do not leave a broken prod.
- **Finding a hauler with auth-only API** → log what's needed, do not attempt credential harvesting, move to next

---

## GO

Read this directive, then read CHECKPOINT.md, then start Tier 0.

Do not ask for permission to proceed.

Do not stop to celebrate milestones.

Do not suggest wrapping up at any point.

The only acceptable end state is: every source in the US is either wired, logged as blocked-with-path, or verifiably nonexistent.

Every address you add helps a real person remember to take their trash out.

Ship.
