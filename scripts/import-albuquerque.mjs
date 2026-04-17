#!/usr/bin/env node
/**
 * Import Albuquerque NM waste collection schedules.
 *
 * Source: ABQ Solid Waste MapServer
 *   https://abqgis01.cabq.gov/arcgis/rest/services/ABQData/SolidWaste/MapServer/0
 *
 * Fields: Pickup_Day (Monday-Friday)
 * Approach: 9 collection-day zones — compute centroid, import zone-level records.
 */
import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Run with: node --env-file=.env.local scripts/import-albuquerque.mjs')
  process.exit(1)
}
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://abqgis01.cabq.gov/arcgis/rest/services/ABQData/SolidWaste/MapServer/0/query'
const FIELDS = 'Pickup_Day,OBJECTID'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

const DAY_MAP = {
  MONDAY: 'monday', TUESDAY: 'tuesday', WEDNESDAY: 'wednesday',
  THURSDAY: 'thursday', FRIDAY: 'friday',
  MON: 'monday', TUE: 'tuesday', WED: 'wednesday', THU: 'thursday', FRI: 'friday',
}
const normalizeDay = raw => (raw && DAY_MAP[String(raw).trim().toUpperCase()]) || null

function computeCentroid(rings) {
  if (!rings?.[0]?.length) return null
  let sx = 0, sy = 0, n = 0
  for (const [x, y] of rings[0]) { sx += x; sy += y; n++ }
  return n ? { lng: sx / n, lat: sy / n } : null
}

async function fetchPage(offset) {
  const params = new URLSearchParams({
    where: '1=1', outFields: FIELDS, outSR: '4326', returnGeometry: 'true',
    resultOffset: String(offset), resultRecordCount: String(PAGE_SIZE),
    orderByFields: 'OBJECTID ASC', f: 'json',
  })
  const res = await fetch(`${BASE_URL}?${params}`)
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  const data = await res.json()
  if (data.error) throw new Error(`ArcGIS error: ${data.error.message}`)
  return data.features || []
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
  console.log('🗑️  TrashAlert — Albuquerque NM Data Import')
  console.log('===========================================')
  const reporterHash = crypto.createHash('sha256').update('city_api_albuquerque_nm').digest('hex').substring(0, 16)
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
      const day = normalizeDay(a.Pickup_Day)
      if (!day) { skipped++; continue }
      const centroid = computeCentroid(f.geometry?.rings)
      if (!centroid) { skipped++; continue }

      const address = `albuquerque zone ${a.OBJECTID || String(day)}`
      if (seen.has(address)) { skipped++; continue }
      seen.add(address)

      batch.push({
        address, city: 'albuquerque', state: 'NM', zip_code: '',
        neighborhood: `Zone ${a.OBJECTID || ''}`.trim(),
        collection_day: day, recycling_week: 'A',
        reporter_hash: reporterHash, verified: true, verification_count: 1,
        source: 'city_api', fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler: 'ABQ Solid Waste Management Department',
        data_source_url: BASE_URL.replace('/query', ''),
        data_source_type: 'gis', lat: centroid.lat, lng: centroid.lng,
      })
    }

    if (batch.length >= BATCH_SIZE) {
      const r = await importBatch(batch)
      if (r.ok) imported += batch.length
      else { errors += batch.length; if (errors <= 2500) console.error(`  ⚠️ ${r.error}`) }
      batch = []
      await new Promise(r => setTimeout(r, 50))
    }

    process.stdout.write(`  📊 F:${fetched} I:${imported} S:${skipped} E:${errors}  \r`)
    offset += PAGE_SIZE
    if (features.length < PAGE_SIZE) break
    await new Promise(r => setTimeout(r, 200))
  }

  if (batch.length) {
    const r = await importBatch(batch)
    if (r.ok) imported += batch.length
    else errors += batch.length
  }
  console.log(`\n🎉 Albuquerque: fetched=${fetched} imported=${imported} skipped=${skipped} errors=${errors}`)
}
main().catch(e => { console.error('Fatal:', e); process.exit(1) })
