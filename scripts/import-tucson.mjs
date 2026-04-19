#!/usr/bin/env node
/**
 * Import Tucson AZ waste collection schedules.
 *
 * Sources:
 *   Brush & Bulky: https://utility.arcgis.com/usrsvcs/servers/c12b866163a04387ad7dcd4ebc6c4926/rest/services/PublicMaps/EnvironmentalGeneralServices/MapServer/239
 *   Recycling:     https://mapdata.tucsonaz.gov/arcgis/rest/services/IT/ZoomTucson/MapServer/56
 *
 * Fields: BBArea, ServiceDates, CollWeek (A/B), DOS, PRIMARY_RT
 * Approach: Service zones with day-of-service (DOS) and alternating week A/B.
 */
import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Run with: node --env-file=.env.local scripts/import-tucson.mjs')
  process.exit(1)
}
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const RECY_URL = 'https://mapdata.tucsonaz.gov/arcgis/rest/services/IT/ZoomTucson/MapServer/56/query'
const FIELDS = 'ServDates,CollWeek,DOS,PRIMARY_RT,OBJECTID'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

const DAY_MAP = {
  MON: 'monday', TUE: 'tuesday', WED: 'wednesday', THU: 'thursday', FRI: 'friday', SAT: 'saturday',
  MONDAY: 'monday', TUESDAY: 'tuesday', WEDNESDAY: 'wednesday', THURSDAY: 'thursday', FRIDAY: 'friday', SATURDAY: 'saturday',
  M: 'monday', T: 'tuesday', W: 'wednesday', R: 'thursday', F: 'friday',
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
  const res = await fetch(`${RECY_URL}?${params}`)
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
  console.log('🗑️  TrashAlert — Tucson AZ Data Import')
  console.log('======================================')
  const reporterHash = crypto.createHash('sha256').update('city_api_tucson_az').digest('hex').substring(0, 16)
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
      const day = normalizeDay(a.DOS) || normalizeDay(a.ServDates)
      if (!day) { skipped++; continue }
      const centroid = computeCentroid(f.geometry?.rings)
      if (!centroid) { skipped++; continue }

      const week = (a.CollWeek || 'A').toUpperCase() === 'B' ? 'B' : 'A'
      const routeId = a.PRIMARY_RT || a.OBJECTID
      const address = `tucson recycling route ${String(routeId).toLowerCase()}`
      if (seen.has(address)) { skipped++; continue }
      seen.add(address)

      batch.push({
        address, city: 'tucson', state: 'AZ', zip_code: '',
        neighborhood: `Route ${routeId}`,
        collection_day: day, recycling_week: week,
        reporter_hash: reporterHash, verified: true, verification_count: 1,
        source: 'city_api', fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler: 'City of Tucson Environmental & General Services',
        data_source_url: RECY_URL.replace('/query', ''),
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
  console.log(`\n🎉 Tucson: fetched=${fetched} imported=${imported} skipped=${skipped} errors=${errors}`)
}
main().catch(e => { console.error('Fatal:', e); process.exit(1) })
