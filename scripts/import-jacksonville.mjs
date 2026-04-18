#!/usr/bin/env node
/**
 * Import Jacksonville FL waste collection schedules.
 *
 * Source: Jacksonville Solid Waste FeatureServer
 *   https://services1.arcgis.com/NXfNVaFp7QMxnE3j/arcgis/rest/services/All_WP_Changes_2022/FeatureServer/23
 *
 * Fields: COMPANY (CITY/WP/MW), DISTRICT, GarbDay, RecyDay, YardDay, BulkDay
 * Approach: 97 service zones — one row per service type per zone.
 */
import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Run with: node --env-file=.env.local scripts/import-jacksonville.mjs')
  process.exit(1)
}
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://services1.arcgis.com/NXfNVaFp7QMxnE3j/arcgis/rest/services/All_WP_Changes_2022/FeatureServer/23/query'
const FIELDS = 'COMPANY,DISTRICT,GarbDay,RecyDay,YardDay,BulkDay,OBJECTID'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

const DAY_MAP = {
  MON: 'monday', TUE: 'tuesday', WED: 'wednesday', THU: 'thursday', FRI: 'friday', SAT: 'saturday',
  MONDAY: 'monday', TUESDAY: 'tuesday', WEDNESDAY: 'wednesday', THURSDAY: 'thursday', FRIDAY: 'friday', SATURDAY: 'saturday',
  M: 'monday', T: 'tuesday', W: 'wednesday', R: 'thursday', F: 'friday',
}
const normalizeDay = raw => (raw && DAY_MAP[String(raw).trim().toUpperCase()]) || null

const HAULER_MAP = { CITY: 'City of Jacksonville', WP: 'Waste Pro', MW: 'Meridian Waste' }

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
  console.log('🗑️  TrashAlert — Jacksonville FL Data Import')
  console.log('============================================')
  const reporterHash = crypto.createHash('sha256').update('city_api_jacksonville_fl').digest('hex').substring(0, 16)
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
      const centroid = computeCentroid(f.geometry?.rings)
      if (!centroid) { skipped++; continue }
      const hauler = HAULER_MAP[a.COMPANY] || a.COMPANY || 'City of Jacksonville'
      const district = a.DISTRICT || `zone-${a.OBJECTID}`

      const services = [
        { key: 'GarbDay',  label: 'garbage',   day: normalizeDay(a.GarbDay) },
        { key: 'RecyDay',  label: 'recycling', day: normalizeDay(a.RecyDay) },
        { key: 'YardDay',  label: 'yard',      day: normalizeDay(a.YardDay) },
      ]

      for (const svc of services) {
        if (!svc.day) { skipped++; continue }
        const address = `jacksonville ${svc.label} district ${String(district).toLowerCase()}`
        if (seen.has(address)) { skipped++; continue }
        seen.add(address)

        batch.push({
          address, city: 'jacksonville', state: 'FL', zip_code: '',
          neighborhood: `District ${district}`,
          collection_day: svc.day, recycling_week: 'A',
          reporter_hash: reporterHash, verified: true, verification_count: 1,
          source: 'city_api', fetched_at: now,
          raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a) + svc.key).digest('hex'),
          hauler, data_source_url: BASE_URL.replace('/query', ''),
          data_source_type: 'gis', lat: centroid.lat, lng: centroid.lng,
        })
      }
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
  console.log(`\n🎉 Jacksonville: fetched=${fetched} imported=${imported} skipped=${skipped} errors=${errors}`)
}
main().catch(e => { console.error('Fatal:', e); process.exit(1) })
