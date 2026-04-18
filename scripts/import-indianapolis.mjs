#!/usr/bin/env node
/**
 * Import Indianapolis IN waste collection schedules.
 *
 * Source: InforPS MapServer (Collection Areas)
 *   https://gis.indy.gov/server/rest/services/InforPS/InforPS/MapServer/29
 *
 * Fields: HAULER, ROUTE_NO, DISTRICT, DAY, HVYTRASHDA, RC_HAULER, RC_DAY
 * Approach: Collection-area polygons — compute centroid, insert zone rows for
 *           garbage (DAY) and recycling (RC_DAY) service types.
 */
import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing SUPABASE_URL or SUPABASE_SERVICE_KEY')
  console.error('Run with: node --env-file=.env.local scripts/import-indianapolis.mjs')
  process.exit(1)
}
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://gis.indy.gov/server/rest/services/InforPS/InforPS/MapServer/29/query'
const FIELDS = 'HAULER,ROUTE_NO,DISTRICT,DAY,HVYTRASHDA,RC_HAULER,RC_DAY'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

const DAY_MAP = {
  MON: 'monday', TUE: 'tuesday', WED: 'wednesday', THU: 'thursday', FRI: 'friday', SAT: 'saturday',
  MONDAY: 'monday', TUESDAY: 'tuesday', WEDNESDAY: 'wednesday', THURSDAY: 'thursday', FRIDAY: 'friday', SATURDAY: 'saturday',
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
    where: '1=1', outFields: FIELDS, outSR: '4326',
    returnGeometry: 'true', resultOffset: String(offset),
    resultRecordCount: String(PAGE_SIZE), orderByFields: 'OBJECTID ASC', f: 'json',
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
  console.log('🗑️  TrashAlert — Indianapolis IN Data Import')
  console.log('============================================')
  const reporterHash = crypto.createHash('sha256').update('city_api_indianapolis_in').digest('hex').substring(0, 16)
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

      for (const svc of ['GARB', 'RECY']) {
        const day = normalizeDay(svc === 'GARB' ? a.DAY : a.RC_DAY)
        if (!day) { skipped++; continue }
        const hauler = (svc === 'GARB' ? a.HAULER : a.RC_HAULER) || 'City of Indianapolis DPW'
        const routeNo = a.ROUTE_NO || f.attributes.OBJECTID
        const address = `indianapolis ${svc === 'GARB' ? 'garbage' : 'recycling'} route ${String(routeNo).toLowerCase()}`
        if (seen.has(address)) { skipped++; continue }
        seen.add(address)

        batch.push({
          address, city: 'indianapolis', state: 'IN', zip_code: '',
          neighborhood: a.DISTRICT || `District ${routeNo}`,
          collection_day: day, recycling_week: 'A',
          reporter_hash: reporterHash, verified: true, verification_count: 1,
          source: 'city_api', fetched_at: now,
          raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
          hauler, data_source_url: BASE_URL.replace('/query', ''),
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
  console.log(`\n🎉 Indianapolis: fetched=${fetched} imported=${imported} skipped=${skipped} errors=${errors}`)
}
main().catch(e => { console.error('Fatal:', e); process.exit(1) })
