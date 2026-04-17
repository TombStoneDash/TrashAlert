#!/usr/bin/env node
/**
 * Import Miami-Dade FL waste collection schedules.
 *
 * Source: Miami-Dade Solid Waste FeatureServer
 *   Garbage routes: https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/GarbagePickupRoute_gdb/FeatureServer/0
 *   Recycling zones: https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/RecyclingZone_gdb/FeatureServer/0
 *
 * Fields: ROUTE, COLLDAY, WEEKDAYS, WCSAREA, TYPE
 * Approach: 783 garbage routes + separate recycling zones — fetch both endpoints,
 *           compute centroid, import.
 */
import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Run with: node --env-file=.env.local scripts/import-miami-dade.mjs')
  process.exit(1)
}
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const ENDPOINTS = [
  {
    name: 'garbage',
    url: 'https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/GarbagePickupRoute_gdb/FeatureServer/0/query',
    fields: 'ROUTE,COLLDAY,WEEKDAYS,WCSAREA,TYPE,OBJECTID',
    label: 'garbage',
  },
  {
    name: 'recycling',
    url: 'https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/RecyclingZone_gdb/FeatureServer/0/query',
    fields: 'ROUTE,COLLDAY,WEEKDAYS,WCSAREA,TYPE,OBJECTID',
    label: 'recycling',
  },
]
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

const DAY_MAP = {
  MON: 'monday', TUE: 'tuesday', WED: 'wednesday', THU: 'thursday', FRI: 'friday', SAT: 'saturday',
  MONDAY: 'monday', TUESDAY: 'tuesday', WEDNESDAY: 'wednesday', THURSDAY: 'thursday', FRIDAY: 'friday', SATURDAY: 'saturday',
}
const normalizeDay = raw => {
  if (!raw) return null
  // WEEKDAYS sometimes looks like "MON/THU" — take first.
  const first = String(raw).split(/[\/,&-]/)[0].trim().toUpperCase()
  return DAY_MAP[first] || null
}

function computeCentroid(rings) {
  if (!rings?.[0]?.length) return null
  let sx = 0, sy = 0, n = 0
  for (const [x, y] of rings[0]) { sx += x; sy += y; n++ }
  return n ? { lng: sx / n, lat: sy / n } : null
}

async function fetchPage(url, fields, offset) {
  const params = new URLSearchParams({
    where: '1=1', outFields: fields, outSR: '4326', returnGeometry: 'true',
    resultOffset: String(offset), resultRecordCount: String(PAGE_SIZE),
    orderByFields: 'OBJECTID ASC', f: 'json',
  })
  const res = await fetch(`${url}?${params}`)
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
  console.log('🗑️  TrashAlert — Miami-Dade FL Data Import')
  console.log('==========================================')
  const reporterHash = crypto.createHash('sha256').update('city_api_miami_dade_fl').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let fetched = 0, imported = 0, skipped = 0, errors = 0
  let batch = []
  const seen = new Set()

  for (const ep of ENDPOINTS) {
    let offset = 0
    while (true) {
      const features = await fetchPage(ep.url, ep.fields, offset)
      if (features.length === 0) break
      fetched += features.length

      for (const f of features) {
        const a = f.attributes
        const day = normalizeDay(a.COLLDAY) || normalizeDay(a.WEEKDAYS)
        if (!day) { skipped++; continue }
        const centroid = computeCentroid(f.geometry?.rings)
        if (!centroid) { skipped++; continue }

        const route = a.ROUTE || a.OBJECTID
        const address = `miami-dade ${ep.label} route ${String(route).toLowerCase()}`
        if (seen.has(address)) { skipped++; continue }
        seen.add(address)

        batch.push({
          address, city: 'miami-dade', state: 'FL', zip_code: '',
          neighborhood: a.WCSAREA || `Route ${route}`,
          collection_day: day, recycling_week: 'A',
          reporter_hash: reporterHash, verified: true, verification_count: 1,
          source: 'city_api', fetched_at: now,
          raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a) + ep.label).digest('hex'),
          hauler: 'Miami-Dade Solid Waste Management',
          data_source_url: ep.url.replace('/query', ''),
          data_source_type: 'gis', lat: centroid.lat, lng: centroid.lng,
        })

        if (batch.length >= BATCH_SIZE) {
          const r = await importBatch(batch)
          if (r.ok) imported += batch.length
          else { errors += batch.length; if (errors <= 2500) console.error(`  ⚠️ ${r.error}`) }
          batch = []
          await new Promise(r => setTimeout(r, 50))
        }
      }

      process.stdout.write(`  📊 ${ep.label} F:${fetched} I:${imported} S:${skipped} E:${errors}  \r`)
      offset += PAGE_SIZE
      if (features.length < PAGE_SIZE) break
      await new Promise(r => setTimeout(r, 200))
    }
    console.log('')
  }

  if (batch.length) {
    const r = await importBatch(batch)
    if (r.ok) imported += batch.length
    else errors += batch.length
  }
  console.log(`\n🎉 Miami-Dade: fetched=${fetched} imported=${imported} skipped=${skipped} errors=${errors}`)
}
main().catch(e => { console.error('Fatal:', e); process.exit(1) })
