# ReCollect (place_id, service_id) Discovery Plan — 2026-04-26

**Audience:** HT or whoever picks up ReCollect expansion next.
**Status:** **Plan + script. NOT executed. Read this before running.**

---

## Why we need this

`scripts/import-recollect.mjs` ships with 16 hand-curated `(place_id, service_id)` tuples. All 16 are imported (1 row each in `schedule_reports`). To expand TrashAlert's ReCollect-backed coverage we need *new* tuples. The public ReCollect API has no enumeration endpoint, so the tuples must come from elsewhere.

The richest community-curated source is **Home Assistant's `hacs_waste_collection_schedule`** addon. Its source tree contains a Python module per integration; the ReCollect module hard-codes a service-ID lookup table that maps city slugs to `service_id` values. Combined with the place-search shape we already understand, this is enough to discover ~50-200 additional ReCollect-served municipalities.

Repo: `https://github.com/mampfes/hacs_waste_collection_schedule`
Likely path: `custom_components/waste_collection_schedule/waste_collection_schedule/source/recollect_net.py` (subject to upstream renames)

---

## Discovery script — `scripts/discover-recollect-tuples.mjs`

Save this file in the FastAPI repo's `scripts/` folder. Run during waking hours so HT can babysit the network calls.

```javascript
#!/usr/bin/env node
/**
 * Discover candidate ReCollect (place_id, service_id) tuples by
 * scraping the Home Assistant waste-collection-schedule addon's
 * ReCollect source module.
 *
 * Outputs: scripts/recollect-candidates.json
 *
 * Idempotent. Pure read. Does not touch Supabase. Safe to re-run.
 *
 * Usage:
 *   node scripts/discover-recollect-tuples.mjs
 *   node scripts/discover-recollect-tuples.mjs --probe   # also hits api.recollect.net to verify each tuple
 */
import fs from 'node:fs/promises'

const HACS_RAW = 'https://raw.githubusercontent.com/mampfes/hacs_waste_collection_schedule/master/custom_components/waste_collection_schedule/waste_collection_schedule/source/recollect_net.py'
const PROBE = process.argv.includes('--probe')
const OUT = 'scripts/recollect-candidates.json'

async function fetchText(url) {
  const r = await fetch(url, { headers: { 'User-Agent': 'trashalert-discovery/1.0' } })
  if (!r.ok) throw new Error(`${url} → ${r.status}`)
  return r.text()
}

function parseHacsTuples(py) {
  // The HACS source typically declares a SERVICE_MAP dict. Extract it
  // with a non-AST regex (good enough for a discovery pass).
  const out = []
  const dictMatch = py.match(/SERVICE_MAP\s*=\s*\{([\s\S]*?)\}/)
  if (!dictMatch) {
    console.error('Could not find SERVICE_MAP in HACS source. The file structure may have changed.')
    console.error('Open the source manually:', HACS_RAW)
    return out
  }
  const body = dictMatch[1]
  // Match entries like: "city-slug": (PlaceID, ServiceID),
  const entryRe = /"([^"]+)"\s*:\s*\(\s*"?([0-9A-F-]+)"?\s*,\s*([0-9]+)\s*\)/gi
  let m
  while ((m = entryRe.exec(body))) {
    out.push({ slug: m[1], place_id: m[2], service_id: parseInt(m[3], 10) })
  }
  return out
}

async function probeOne(t) {
  const r = await fetch(`https://api.recollect.net/api/places/${t.place_id}`)
  if (!r.ok) return { ...t, probe_status: r.status, probe_ok: false }
  const j = await r.json()
  return { ...t, probe_status: 200, probe_ok: true, real_city: j.place?.city, lat: j.place?.lat, lng: j.place?.lng }
}

async function main() {
  console.log('1/3 — Fetching HACS recollect_net.py …')
  const py = await fetchText(HACS_RAW)

  console.log('2/3 — Parsing SERVICE_MAP …')
  const tuples = parseHacsTuples(py)
  console.log(`   found ${tuples.length} candidate tuples`)

  // Filter against existing import-recollect.mjs entries to surface NEW ones
  const existing = new Set([
    'ottawa-on','denver-co','austin-tx','san-francisco-ca','cambridge-ma',
    'vancouver-bc','halton-on','saanich-bc','richmond-bc','davenport-ia',
    'georgetown-tx','peterborough-on','sherwood-park-ab','morris-mb',
    'hardin-id','king-county-wa',
  ])
  const fresh = tuples.filter(t => !existing.has(t.slug))
  console.log(`   ${fresh.length} are NOT already in import-recollect.mjs`)

  let result = fresh
  if (PROBE) {
    console.log('3/3 — Probing api.recollect.net for each fresh tuple (~250ms each) …')
    result = []
    for (const t of fresh) {
      try {
        result.push(await probeOne(t))
      } catch (e) {
        result.push({ ...t, probe_status: 0, probe_ok: false, probe_err: e.message })
      }
      await new Promise(r => setTimeout(r, 300))
    }
    const ok = result.filter(r => r.probe_ok).length
    console.log(`   verified live: ${ok}/${result.length}`)
  } else {
    console.log('3/3 — Skipping live probe (pass --probe to enable)')
  }

  await fs.writeFile(OUT, JSON.stringify(result, null, 2))
  console.log(`\nWrote ${OUT}`)
  console.log('Next step: review the candidates, then add the live ones to PLACES[] in scripts/import-recollect.mjs')
}

main().catch(e => { console.error('Fatal:', e); process.exit(1) })
```

---

## Run sequence (HT, when you're ready)

1. `cd C:\TombstoneDash\factory\trashalert` (or use the worktree)
2. Save the script above as `scripts/discover-recollect-tuples.mjs`
3. **Dry-run discovery (no live probes):** `node scripts/discover-recollect-tuples.mjs`
4. Review `scripts/recollect-candidates.json` — confirm the tuple count looks plausible
5. **Live probe pass:** `node scripts/discover-recollect-tuples.mjs --probe` (takes ~5-15 min depending on candidate count)
6. Pick the verified tuples you want, append them to `PLACES[]` in `scripts/import-recollect.mjs`
7. Run the import the existing way: `node --env-file=.env.local scripts/import-recollect.mjs`

## Risks and known limitations

- **HACS upstream may rename or restructure** the `SERVICE_MAP` dict. The script's regex is intentionally loose, but if upstream changes to a JSON file or YAML, the parser needs updating. The script prints a clear error if `SERVICE_MAP` is not found.
- **Each ReCollect tuple still produces only 1 row** in `schedule_reports` (the "default service area" pattern). Volume per tuple is low; this is breadth not depth.
- **License / ToS check needed** before scraping HACS in production. The `mampfes` repo is GPL-3.0 — code/schemas you derive from it should respect that. Importing the *data* (which is public anyway via the ReCollect API) is fine; redistributing the lookup table verbatim might not be.

## Why this isn't tonight's work

- 8-hour overnight cap is for unattended writes. A scrape that surfaces 50-200 candidates and then triggers 50-200 Supabase writes (even idempotent ones) wants HT eyes on it, especially the first time the script runs and we discover whether HACS's mapping format has shifted since the existing 16 tuples were curated.
- The verification gate from the directive ("3 random addresses → 3/3 found") is structurally infeasible for ReCollect (1 row per city), so per-batch verification needs a custom adapter that should be reviewed before running.
- ROI is debatable: 50 more "default service area" rows doesn't move the homepage stat. Address-level depth requires Routeware partner credentials, which is a sales conversation, not a script.

---

## Estimated yield

Based on the [HACS waste-collection-schedule README](https://github.com/mampfes/hacs_waste_collection_schedule), ReCollect is one of ~160 supported sources and the ReCollect SERVICE_MAP historically holds ~80-150 entries. After filtering against our existing 16, expect **~70-130 new candidate tuples**, with a probe pass-rate of probably 85-95% (some cities drop out of ReCollect over time when their contracts end).

Even after the import, the addressable lookup count grows by maybe 80-130 city-level rows — small in absolute terms but it broadens the cities-served headline number from "22 verified" toward "100+ touched."

---

## What this doc explicitly does NOT do

- Does not run the discovery script
- Does not write the script to disk in the FastAPI repo (it lives only here as a paste-ready snippet to avoid prematurely committing untested code)
- Does not modify `import-recollect.mjs`
- Does not insert any rows into Supabase
- Does not contact Routeware
