#!/usr/bin/env node
/**
 * Import Pittsburgh PA waste collection schedules.
 *
 * Source: Pittsburgh Department of Public Works trash-collection database,
 * published via the Pittsburgh Open Data initiative (pgh.st / WPRDC).
 *
 *   API root: http://www.pgh.st/api/data/location
 *   Schema:   http://www.pgh.st/api/data/location/schema
 *   Mirror:   https://data.wprdc.org/dataset/  (WPRDC ArcGIS portal)
 *
 * The published dataset has one row per city block:
 *   { street, house_number_from, house_number_to, collection_day }
 * We expand each block into individual house addresses (capped at 50/block)
 * and import them as verified schedule_reports rows.
 *
 * NOTE ON ENDPOINT STABILITY: pgh.st is a community-maintained proxy and
 * may be unavailable.  If it fails, try the WPRDC ArcGIS portal at
 * https://pghgishub-pittsburghpa.opendata.arcgis.com/ and substitute the
 * dataset-specific FeatureServer URL below.
 */
import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Run with: node --env-file=.env.local scripts/import-pittsburgh.mjs')
  process.exit(1)
}
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const PRIMARY_URL = 'http://www.pgh.st/api/data/location'
const WPRDC_FALLBACK = 'https://pghgishub-pittsburghpa.opendata.arcgis.com/'
const BATCH_SIZE = 500
const MAX_HOUSES_PER_BLOCK = 50

const DAY_MAP = {
  MON: 'monday', TUE: 'tuesday', WED: 'wednesday', THU: 'thursday', FRI: 'friday',
  MONDAY: 'monday', TUESDAY: 'tuesday', WEDNESDAY: 'wednesday', THURSDAY: 'thursday', FRIDAY: 'friday',
  M: 'monday', T: 'tuesday', W: 'wednesday', R: 'thursday', F: 'friday',
}
const normalizeDay = raw => (raw && DAY_MAP[String(raw).trim().toUpperCase()]) || null

function* expandHouses(from, to) {
  if (!from || !to) return
  const lo = Math.min(Number(from), Number(to))
  const hi = Math.max(Number(from), Number(to))
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return
  let count = 0
  for (let h = lo; h <= hi; h++) {
    if (count++ >= MAX_HOUSES_PER_BLOCK) break
    yield h
  }
}

async function importBatch(rows) {
  const { error } = await supabase.from('schedule_reports').upsert(rows, { onConflict: 'address,city', ignoreDuplicates: true })
  if (error) {
    const { error: ie } = await supabase.from('schedule_reports').insert(rows)
    if (ie) return { ok: false, error: ie.message }
  }
  return { ok: true }
}

async function main() {
  console.log('🗑️  TrashAlert — Pittsburgh PA Data Import')
  console.log('==========================================')
  console.log(`Primary:  ${PRIMARY_URL}`)
  console.log(`Fallback: ${WPRDC_FALLBACK}`)

  let blocks = []
  try {
    const res = await fetch(PRIMARY_URL, { headers: { 'User-Agent': 'TrashAlert/1.0 (schedule import)' } })
    if (!res.ok) throw new Error(`pgh.st status ${res.status}`)
    blocks = await res.json()
  } catch (err) {
    console.error(`\n⚠️  Primary endpoint failed (${err.message}).`)
    console.error(`   Pittsburgh import requires browsing ${WPRDC_FALLBACK} to find the current`)
    console.error(`   Public Works trash-pickup FeatureServer URL, or using the WPRDC package:`)
    console.error(`   https://data.wprdc.org/dataset/?q=trash+collection`)
    process.exit(2)
  }

  const reporterHash = crypto.createHash('sha256').update('city_api_pittsburgh_pa').digest('hex').substring(0, 16)
  const now = new Date().toISOString()
  let imported = 0, skipped = 0, errors = 0
  let batch = []
  const seen = new Set()

  for (const b of blocks) {
    const day = normalizeDay(b.collection_day || b.day)
    if (!day) { skipped++; continue }
    const street = String(b.street || b.name || '').trim().toLowerCase()
    if (!street) { skipped++; continue }
    const from = b.house_number_from ?? b.from ?? b.low
    const to   = b.house_number_to   ?? b.to   ?? b.high

    const lat = Number(b.lat ?? b.latitude ?? 40.4406)
    const lng = Number(b.lng ?? b.longitude ?? -79.9959)

    for (const h of expandHouses(from, to)) {
      const address = `${h} ${street}`
      if (seen.has(address)) { skipped++; continue }
      seen.add(address)

      batch.push({
        address, city: 'pittsburgh', state: 'PA', zip_code: '',
        neighborhood: b.neighborhood || '',
        collection_day: day, recycling_week: 'A',
        reporter_hash: reporterHash, verified: true, verification_count: 1,
        source: 'city_api', fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(`${h}${street}${day}`).digest('hex'),
        hauler: 'City of Pittsburgh Department of Public Works',
        data_source_url: PRIMARY_URL,
        data_source_type: 'api', lat, lng,
      })

      if (batch.length >= BATCH_SIZE) {
        const r = await importBatch(batch)
        if (r.ok) imported += batch.length
        else { errors += batch.length; if (errors <= 2500) console.error(`  ⚠️ ${r.error}`) }
        batch = []
        await new Promise(r => setTimeout(r, 50))
      }
    }
  }

  if (batch.length) {
    const r = await importBatch(batch)
    if (r.ok) imported += batch.length
    else errors += batch.length
  }
  console.log(`\n🎉 Pittsburgh: blocks=${blocks.length} imported=${imported} skipped=${skipped} errors=${errors}`)
}
main().catch(e => { console.error('Fatal:', e); process.exit(1) })
