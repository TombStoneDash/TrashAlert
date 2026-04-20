#!/usr/bin/env node
/**
 * Portland OR — garbage collection zones (multi-hauler).
 * Source: portlandmaps.com/od/rest/services/COP_OpenData_Boundary/MapServer/5
 * 900 zone polygons with Hauler, Coll_Day_N (current day), schedule details.
 */
import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Run with: node --env-file=.env.local scripts/import-portland-or.mjs')
  process.exit(1)
}
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://www.portlandmaps.com/od/rest/services/COP_OpenData_Boundary/MapServer/5/query'
const PAGE_SIZE = 500
const DAY_MAP = { monday:'monday', tuesday:'tuesday', wednesday:'wednesday', thursday:'thursday', friday:'friday', saturday:'saturday', sunday:'sunday' }

function centroidRings(rings) {
  if (!rings?.length) return [null, null]
  let sx = 0, sy = 0, n = 0
  for (const ring of rings) for (const [x, y] of ring) { sx += x; sy += y; n++ }
  return n ? [sx / n, sy / n] : [null, null]
}

async function fetchPage(offset) {
  const params = new URLSearchParams({
    where: '1=1', outFields: 'OBJECTID,Hauler,Coll_Day_N,Coll_Cal_N,G_Sched_N,R_Sched_N,Phone_Num,Website',
    outSR: '4326', returnGeometry: 'true',
    resultOffset: String(offset), resultRecordCount: String(PAGE_SIZE),
    orderByFields: 'OBJECTID ASC', f: 'json',
  })
  for (let attempt = 1; attempt <= 5; attempt++) {
    try {
      const res = await fetch(`${BASE_URL}?${params}`, { signal: AbortSignal.timeout(60_000) })
      const data = await res.json()
      if (data.error) throw new Error(`ArcGIS: ${data.error.message}`)
      return data.features || []
    } catch (e) {
      const wait = Math.min(30_000, 2000 * attempt)
      process.stdout.write(`\n    ↻ retry ${attempt}: ${e.message} (${wait}ms)\n`)
      await new Promise(r => setTimeout(r, wait))
    }
  }
  throw new Error('exhausted retries')
}

async function main() {
  console.log('Portland OR Import (~900 zones)')
  const reporterHash = crypto.createHash('sha256').update('city_api_portland_or').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let offset = 0, fetched = 0, imported = 0, skipped = 0
  const seen = new Set()
  const rows = []

  while (true) {
    const features = await fetchPage(offset)
    if (features.length === 0) break
    fetched += features.length

    for (const f of features) {
      const a = f.attributes
      const day = DAY_MAP[String(a.Coll_Day_N || '').trim().toLowerCase()]
      if (!day) { skipped++; continue }
      const [lng, lat] = centroidRings(f.geometry?.rings)
      const street = `portland-or zone ${a.OBJECTID} ${a.Hauler || ''}`.toLowerCase().replace(/\s+/g, ' ').trim()
      if (seen.has(street)) { skipped++; continue }
      seen.add(street)
      rows.push({
        address: street, city: 'portland-or', state: 'OR',
        zip_code: '', neighborhood: `${a.Hauler || ''} | ${a.Coll_Cal_N || ''} cal`,
        collection_day: day, recycling_week: a.Coll_Cal_N === 'Orange' ? 'B' : 'A',
        reporter_hash: reporterHash, verified: true, verification_count: 1,
        source: 'city_api', fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(`${street}${day}`).digest('hex'),
        hauler: String(a.Hauler || 'Portland OR multi-hauler').trim(),
        data_source_url: BASE_URL.replace('/query', ''),
        data_source_type: 'gis',
        lat, lng,
      })
    }
    offset += PAGE_SIZE
    if (features.length < PAGE_SIZE) break
    await new Promise(r => setTimeout(r, 200))
  }

  console.log(`Inserting ${rows.length} zones (skipped ${skipped})`)
  for (let i = 0; i < rows.length; i += 500) {
    const batch = rows.slice(i, i + 500)
    const { error } = await supabase.from('schedule_reports').upsert(batch, { onConflict: 'address,city', ignoreDuplicates: true })
    if (!error) imported += batch.length
    else { const { error: ie } = await supabase.from('schedule_reports').insert(batch); if (!ie) imported += batch.length; else console.error(ie.message) }
  }
  console.log(`Portland OR: fetched=${fetched} imported=${imported} skipped=${skipped}`)
}
main().catch(e => { console.error('Fatal:', e); process.exit(1) })
