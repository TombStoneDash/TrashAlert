#!/usr/bin/env node
/**
 * Import Milwaukee WI waste collection schedules.
 *
 * Source: Milwaukee DPW Sanitation MapServer
 *   https://milwaukeemaps.milwaukee.gov/arcgis/rest/services/DPW/DPW_Sanitation/MapServer
 *
 * Day layers: 3=Monday, 4=Tuesday, 5=Wednesday, 6=Thursday, 7=Friday
 * Summer routes (layer 9): 442 records; winter routes (layer 21).
 * Approach: One day per layer — fetch each day layer in sequence, import zone polys.
 */
import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Run with: node --env-file=.env.local scripts/import-milwaukee.mjs')
  process.exit(1)
}
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE = 'https://milwaukeemaps.milwaukee.gov/arcgis/rest/services/DPW/DPW_Sanitation/MapServer'
const DAY_LAYERS = [
  { layer: 3, day: 'monday' },
  { layer: 4, day: 'tuesday' },
  { layer: 5, day: 'wednesday' },
  { layer: 6, day: 'thursday' },
  { layer: 7, day: 'friday' },
]
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

function computeCentroid(rings) {
  if (!rings?.[0]?.length) return null
  let sx = 0, sy = 0, n = 0
  for (const [x, y] of rings[0]) { sx += x; sy += y; n++ }
  return n ? { lng: sx / n, lat: sy / n } : null
}

async function fetchPage(layerId, offset) {
  const params = new URLSearchParams({
    where: '1=1', outFields: '*', outSR: '4326', returnGeometry: 'true',
    resultOffset: String(offset), resultRecordCount: String(PAGE_SIZE),
    orderByFields: 'OBJECTID ASC', f: 'json',
  })
  const res = await fetch(`${BASE}/${layerId}/query?${params}`)
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
  console.log('🗑️  TrashAlert — Milwaukee WI Data Import')
  console.log('=========================================')
  const reporterHash = crypto.createHash('sha256').update('city_api_milwaukee_wi').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let fetched = 0, imported = 0, skipped = 0, errors = 0
  let batch = []
  const seen = new Set()

  for (const { layer, day } of DAY_LAYERS) {
    let offset = 0
    while (true) {
      const features = await fetchPage(layer, offset)
      if (features.length === 0) break
      fetched += features.length

      for (const f of features) {
        const a = f.attributes
        const centroid = computeCentroid(f.geometry?.rings)
        if (!centroid) { skipped++; continue }

        const routeId = a.ROUTE_ID || a.ROUTE || a.OBJECTID
        const address = `milwaukee ${day} route ${String(routeId).toLowerCase()}`
        if (seen.has(address)) { skipped++; continue }
        seen.add(address)

        batch.push({
          address, city: 'milwaukee', state: 'WI', zip_code: '',
          neighborhood: `Layer ${layer} route ${routeId}`,
          collection_day: day, recycling_week: 'A',
          reporter_hash: reporterHash, verified: true, verification_count: 1,
          source: 'city_api', fetched_at: now,
          raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
          hauler: 'City of Milwaukee DPW Sanitation',
          data_source_url: `${BASE}/${layer}`,
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

      process.stdout.write(`  📊 layer=${layer}(${day}) F:${fetched} I:${imported} S:${skipped} E:${errors}  \r`)
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
  console.log(`\n🎉 Milwaukee: fetched=${fetched} imported=${imported} skipped=${skipped} errors=${errors}`)
}
main().catch(e => { console.error('Fatal:', e); process.exit(1) })
