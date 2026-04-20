#!/usr/bin/env node
/**
 * Import Washington DC waste collection schedules.
 *
 * Source: DC DPW Trash and Recycling Collection Points (per-address)
 *   https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Public_Service_WebMercator/MapServer/2
 *
 * Fields: SERVICE_LOCATION, ADDRESS, ZIPCODE, TRASH_ROUTE, RECYCLING_ROUTE,
 *         DAY ("Monday"/"Tuesday/Friday"/etc.), WARD, MAR_ID
 * Count: ~105,894 per-address points.
 *
 * Notes:
 * - Some addresses have twice-weekly DAY (e.g. "Tuesday/Friday") — we
 *   take the first day for `collection_day` and store the original in
 *   `neighborhood`.
 */
import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Run with: node --env-file=.env.local scripts/import-dc.mjs')
  process.exit(1)
}
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Public_Service_WebMercator/MapServer/2/query'
const FIELDS = 'ADDRESS,ZIPCODE,TRASH_ROUTE,RECYCLING_ROUTE,DAY,WARD,OBJECTID'
const PAGE_SIZE = 1000
const BATCH_SIZE = 500

const DAY_MAP = {
  monday: 'monday', tuesday: 'tuesday', wednesday: 'wednesday',
  thursday: 'thursday', friday: 'friday', saturday: 'saturday', sunday: 'sunday',
}
function normalizeDay(raw) {
  if (!raw) return null
  const first = String(raw).split(/[\/,&\s\-]+/)[0].trim().toLowerCase()
  return DAY_MAP[first] || null
}

async function fetchPage(offset) {
  const params = new URLSearchParams({
    where: '1=1', outFields: FIELDS, outSR: '4326', returnGeometry: 'true',
    resultOffset: String(offset), resultRecordCount: String(PAGE_SIZE),
    orderByFields: 'OBJECTID ASC', f: 'json',
  })
  let lastErr
  for (let attempt = 1; attempt <= 5; attempt++) {
    try {
      const res = await fetch(`${BASE_URL}?${params}`, { signal: AbortSignal.timeout(60_000) })
      if (!res.ok) throw new Error(`API error: ${res.status}`)
      const data = await res.json()
      if (data.error) throw new Error(`ArcGIS error: ${data.error.message}`)
      return data.features || []
    } catch (e) {
      lastErr = e
      const wait = Math.min(30_000, 2000 * attempt)
      process.stdout.write(`\n    ↻ retry ${attempt} after ${e.message || e.name} (${wait}ms)\n`)
      await new Promise(r => setTimeout(r, wait))
    }
  }
  throw lastErr
}

async function importBatch(rows) {
  const { error } = await supabase.from('schedule_reports').upsert(rows, { onConflict: 'address,city', ignoreDuplicates: true })
  if (!error) return { ok: true, n: rows.length }
  const { error: ie } = await supabase.from('schedule_reports').insert(rows)
  if (!ie) return { ok: true, n: rows.length }
  let ok = 0, fail = 0, lastErr = ie.message
  for (const row of rows) {
    const { error: e } = await supabase.from('schedule_reports').insert([row])
    if (e) { fail++; lastErr = e.message } else { ok++ }
  }
  return { ok: ok > 0, n: ok, error: fail ? `${fail} per-row fails: ${lastErr}` : null }
}

async function main() {
  console.log('🗑️  TrashAlert — Washington DC Data Import')
  console.log('==========================================')
  const reporterHash = crypto.createHash('sha256').update('city_api_dc').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let offset = 0, fetched = 0, imported = 0, skipped = 0, errors = 0
  let batch = []
  const seen = new Set()

  while (true) {
    const features = await fetchPage(offset)
    if (features.length === 0) break
    fetched += features.length

    for (const f of features) {
      const a = f.attributes
      const day = normalizeDay(a.DAY)
      if (!day) { skipped++; continue }
      const street = String(a.ADDRESS || '').trim().toLowerCase()
      if (!street) { skipped++; continue }
      if (seen.has(street)) { skipped++; continue }
      seen.add(street)

      batch.push({
        address: street, city: 'washington-dc', state: 'DC',
        zip_code: String(a.ZIPCODE || '').trim(),
        neighborhood: `Ward ${a.WARD || ''} (${a.DAY})`,
        collection_day: day, recycling_week: 'A',
        reporter_hash: reporterHash, verified: true, verification_count: 1,
        source: 'city_api', fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(`${street}${day}`).digest('hex'),
        hauler: 'DC Department of Public Works',
        data_source_url: BASE_URL.replace('/query', ''),
        data_source_type: 'gis',
        lat: f.geometry?.y ?? null, lng: f.geometry?.x ?? null,
      })

      if (batch.length >= BATCH_SIZE) {
        const r = await importBatch(batch)
        imported += r.n || 0
        errors += batch.length - (r.n || 0)
        if (r.error) console.error(`  ⚠️ ${r.error}`)
        batch = []
        await new Promise(r => setTimeout(r, 50))
      }
    }

    process.stdout.write(`  📊 F:${fetched} I:${imported} S:${skipped} E:${errors}  \r`)
    offset += PAGE_SIZE
    if (features.length < PAGE_SIZE) break
    await new Promise(r => setTimeout(r, 200))
  }

  if (batch.length) {
    const r = await importBatch(batch)
    imported += r.n || 0
    errors += batch.length - (r.n || 0)
  }
  console.log(`\n🎉 DC: fetched=${fetched} imported=${imported} skipped=${skipped} errors=${errors}`)
}
main().catch(e => { console.error('Fatal:', e); process.exit(1) })
