#!/usr/bin/env node
/**
 * Discover candidate ReCollect (place_id, service_id) tuples by
 * scraping the Home Assistant `hacs_waste_collection_schedule`
 * project's ReCollect source module.
 *
 * Background
 *   ReCollect's public API has no enumeration endpoint. The only way
 *   to expand TrashAlert's ReCollect-backed coverage beyond the 16
 *   tuples already in `import-recollect.mjs` is to harvest more
 *   `(slug, place_id, service_id)` tuples from a community-curated
 *   source. The HACS waste-collection-schedule integration ships a
 *   SERVICE_MAP dict that maps slugs → tuples; this is currently the
 *   richest public source.
 *
 *   See RECOLLECT_RESEARCH_APR26.md and RECOLLECT_DISCOVERY_PLAN.md
 *   for the full reasoning.
 *
 * What this script does
 *   1. Fetches the HACS source file
 *   2. Parses the SERVICE_MAP dict (regex, intentionally loose)
 *   3. Filters out the 16 tuples we already import
 *   4. Optionally probes each new tuple against api.recollect.net to
 *      verify the place still resolves (some ReCollect contracts end
 *      and the place gets deactivated)
 *   5. Writes scripts/recollect-candidates.json
 *
 * Side effects
 *   None. Read-only against HACS GitHub raw URL and api.recollect.net.
 *   Does not touch Supabase, does not modify schedule_reports.
 *
 * Usage
 *   node scripts/discover-recollect-tuples.mjs            # parse only, no API probes
 *   node scripts/discover-recollect-tuples.mjs --probe   # also probe each tuple (~250ms each)
 *
 * Idempotent. Safe to re-run.
 *
 * Risks / known limits
 *   - HACS upstream may rename SERVICE_MAP or restructure the source.
 *     The regex is loose to survive minor reformatting; if upstream
 *     switches to a JSON or YAML data file the parser must be updated.
 *     The script prints a clear error if SERVICE_MAP is not found.
 *   - HACS is GPL-3.0. Importing the *data* (which is public via
 *     ReCollect's API anyway) is fine. Redistributing the lookup table
 *     verbatim might not be — keep the candidate file out of git
 *     unless you're confident in the licensing posture.
 *   - Each ReCollect tuple still produces only 1 row in
 *     `schedule_reports` (the "default service area" placeholder
 *     pattern). This is breadth, not depth.
 *
 * NOT executed automatically — run by HT during waking hours so
 * surprises (HACS format change, network issue, unexpected probe-fail
 * rate) are caught in real time.
 */
import fs from 'node:fs/promises'
import path from 'node:path'

const HACS_RAW =
  'https://raw.githubusercontent.com/mampfes/hacs_waste_collection_schedule/master/custom_components/waste_collection_schedule/waste_collection_schedule/source/recollect_net.py'

const PROBE = process.argv.includes('--probe')
const OUT = path.join('scripts', 'recollect-candidates.json')

/** The 16 (place_id, service_id) tuples already in PLACES[] of
 *  scripts/import-recollect.mjs. Updated 2026-04-26.
 *  If you add new entries to import-recollect.mjs, mirror them here. */
const ALREADY_IMPORTED = new Set([
  'ottawa-on', 'denver-co', 'austin-tx', 'san-francisco-ca',
  'cambridge-ma', 'vancouver-bc', 'halton-on', 'saanich-bc',
  'richmond-bc', 'davenport-ia', 'georgetown-tx', 'peterborough-on',
  'sherwood-park-ab', 'morris-mb', 'hardin-id', 'king-county-wa',
])

async function fetchText(url) {
  const r = await fetch(url, { headers: { 'User-Agent': 'trashalert-discovery/1.0' } })
  if (!r.ok) throw new Error(`${url} → HTTP ${r.status}`)
  return r.text()
}

function parseHacsTuples(py) {
  const dictMatch = py.match(/SERVICE_MAP\s*=\s*\{([\s\S]*?)^\}/m)
  if (!dictMatch) {
    console.error('ERROR: SERVICE_MAP dict not found in HACS source.')
    console.error('       Upstream may have refactored. Open the file manually:')
    console.error(`       ${HACS_RAW}`)
    return []
  }
  const body = dictMatch[1]
  // Match entries like:
  //   "city-slug": (PlaceID, ServiceID),
  // or with quoted placeID:
  //   "city-slug": ("PLACE-UUID", 208),
  const entryRe =
    /"([^"]+)"\s*:\s*\(\s*"?([0-9A-Fa-f-]{36})"?\s*,\s*([0-9]+)\s*\)/g
  const out = []
  let m
  while ((m = entryRe.exec(body)) !== null) {
    out.push({ slug: m[1], place_id: m[2], service_id: parseInt(m[3], 10) })
  }
  return out
}

async function probeOne(t) {
  try {
    const r = await fetch(`https://api.recollect.net/api/places/${t.place_id}`)
    if (!r.ok) return { ...t, probe_status: r.status, probe_ok: false }
    const j = await r.json()
    return {
      ...t,
      probe_status: 200,
      probe_ok: true,
      real_city: j.place?.city ?? null,
      real_street: j.place?.street ?? null,
      lat: j.place?.lat ?? null,
      lng: j.place?.lng ?? null,
    }
  } catch (e) {
    return { ...t, probe_status: 0, probe_ok: false, probe_err: e.message }
  }
}

async function main() {
  console.log('1/3 — Fetching HACS recollect_net.py …')
  const py = await fetchText(HACS_RAW)
  console.log(`     ${py.length.toLocaleString()} bytes received`)

  console.log('2/3 — Parsing SERVICE_MAP …')
  const tuples = parseHacsTuples(py)
  console.log(`     parsed ${tuples.length} candidate tuples`)
  if (tuples.length === 0) {
    console.error('No tuples parsed; halting before --probe pass.')
    process.exit(1)
  }

  const fresh = tuples.filter((t) => !ALREADY_IMPORTED.has(t.slug))
  console.log(`     ${fresh.length} are NOT already in import-recollect.mjs`)

  let result = fresh
  if (PROBE) {
    console.log('3/3 — Probing api.recollect.net for each fresh tuple (~300ms each) …')
    result = []
    for (const [i, t] of fresh.entries()) {
      result.push(await probeOne(t))
      if ((i + 1) % 10 === 0) console.log(`     ...${i + 1}/${fresh.length}`)
      await new Promise((r) => setTimeout(r, 300))
    }
    const ok = result.filter((r) => r.probe_ok).length
    const stale = result.filter((r) => !r.probe_ok).length
    console.log(`     verified live:  ${ok}`)
    console.log(`     stale / failed: ${stale}`)
  } else {
    console.log('3/3 — Skipping live probe (pass --probe to enable)')
  }

  await fs.writeFile(OUT, JSON.stringify(result, null, 2))
  console.log(`\nWrote ${OUT}  (${result.length} entries)`)
  console.log('Next step: review the candidates, then add the live ones')
  console.log('to PLACES[] in scripts/import-recollect.mjs and run the')
  console.log('existing import the standard way.')
}

main().catch((e) => {
  console.error('Fatal:', e.message)
  process.exit(1)
})
