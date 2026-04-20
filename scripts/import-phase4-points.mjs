#!/usr/bin/env node
/**
 * Phase 4 per-address point importers (4 cities).
 * - Novi MI            ~16,498 polygons (Kerik / Trash_and_Recycling_Collection L1)
 * - Wauwatosa WI       ~16,217 points  (RefuseRecyclingCustomers L0)
 * - South Fulton GA    ~38,362 points  (Solid_Waste_by_Day_WFL1 L2)
 * - Herndon VA         ~5,219  points  (Addresses_In_Refuse_Recycle_Routes L0)
 */
import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Run with: node --env-file=.env.local scripts/import-phase4-points.mjs [city|all]')
  process.exit(1)
}
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const PAGE_SIZE = 1000
const BATCH_SIZE = 500
const DAY_MAP = { monday:'monday', tuesday:'tuesday', wednesday:'wednesday', thursday:'thursday', friday:'friday', saturday:'saturday', sunday:'sunday' }

function normDay(raw) {
  if (!raw) return null
  const first = String(raw).split(/[\/,&\s\-]+/)[0].trim().toLowerCase()
  return DAY_MAP[first] || null
}

function centroidRings(rings) {
  if (!rings?.length) return [null, null]
  let sx = 0, sy = 0, n = 0
  for (const ring of rings) for (const [x, y] of ring) { sx += x; sy += y; n++ }
  return n ? [sx / n, sy / n] : [null, null]
}

const SOURCES = {
  'novi-mi': {
    state: 'MI', hauler: 'City of Novi (multi-hauler)',
    url: 'https://services1.arcgis.com/jwbgoAzqzCbiJmg4/arcgis/rest/services/Trash_and_Recycling_Collection/FeatureServer/1',
    fields: 'PROPADD,PROPCITY,PROPZIP,COLLECTIONDAY,TRASHHAULER,OBJECTID',
    addr: a => String(a.PROPADD || '').trim().toLowerCase(),
    day: a => normDay(a.COLLECTIONDAY),
    nbhd: a => String(a.TRASHHAULER || '').trim(),
    zip: a => String(a.PROPZIP || '').trim(),
    geom: 'rings',
  },
  'wauwatosa-wi': {
    state: 'WI', hauler: 'City of Wauwatosa',
    url: 'https://services5.arcgis.com/gyXZ0hXCxDXxFxHi/arcgis/rest/services/RefuseRecyclingCustomers/FeatureServer/0',
    fields: 'ADDRESS,Refuse_Day,Recycling_Day,OWNERZIP,OBJECTID_1',
    addr: a => String(a.ADDRESS || '').trim().toLowerCase(),
    day: a => normDay(a.Refuse_Day),
    nbhd: a => `Recycling: ${a.Recycling_Day || ''}`,
    zip: a => String(a.OWNERZIP || '').trim(),
    geom: 'point',
    orderBy: 'OBJECTID_1 ASC',
  },
  'south-fulton-ga': {
    state: 'GA', hauler: 'City of South Fulton',
    url: 'https://services3.arcgis.com/y2BJK2GUfoTwH7py/arcgis/rest/services/Solid_Waste_by_Day_WFL1/FeatureServer/2',
    fields: 'USER_Column2,USER_Day,District,Bulk_Waste_Pickup,ObjectID',
    addr: a => String(a.USER_Column2 || '').trim().toLowerCase().replace(/\s+south fulton ga.*$/i, ''),
    day: a => normDay(a.USER_Day),
    nbhd: a => String(a.District || '').trim(),
    zip: a => '',
    geom: 'point',
    orderBy: 'ObjectID ASC',
  },
  'herndon-va': {
    state: 'VA', hauler: 'Town of Herndon',
    url: 'https://services5.arcgis.com/2cXwnjwGfP3U05WQ/arcgis/rest/services/Addresses_In_Refuse_Recycle_Routes_WFL1_July2019/FeatureServer/0',
    fields: 'Street_Number,Street_Name,Street_Suffix,Current_Refuse_Collection_Day,Current_Recycling_Collection_Da,ZIP,OBJECTID',
    addr: a => `${(a.Street_Number||'').trim()} ${(a.Street_Name||'').trim()} ${(a.Street_Suffix||'').trim()}`.toLowerCase().replace(/\s+/g, ' ').trim(),
    day: a => normDay(a.Current_Refuse_Collection_Day),
    nbhd: a => `Recycling: ${a.Current_Recycling_Collection_Da || ''}`,
    zip: a => String(a.ZIP || '').trim(),
    geom: 'point',
  },
  'cocoa-fl': {
    state: 'FL', hauler: 'Waste Management',
    url: 'https://services1.arcgis.com/Tex1uhbqnOZPx6qT/arcgis/rest/services/WM_All_Pickup_Types/FeatureServer/3',
    fields: 'ServiceAddress,Trash_DOW,Recycle_DOW,YardBulkWaste,OBJECTID',
    addr: a => String(a.ServiceAddress || '').trim().toLowerCase(),
    day: a => normDay(a.Trash_DOW),
    nbhd: a => `Recycle: ${a.Recycle_DOW || ''} | Yard: ${a.YardBulkWaste || ''}`,
    zip: a => '',
    geom: 'rings',
  },
}

async function fetchPage(src, offset) {
  const params = new URLSearchParams({
    where: '1=1', outFields: src.fields, outSR: '4326', returnGeometry: 'true',
    resultOffset: String(offset), resultRecordCount: String(PAGE_SIZE),
    orderByFields: src.orderBy || 'OBJECTID ASC', f: 'json',
  })
  for (let attempt = 1; attempt <= 5; attempt++) {
    try {
      const res = await fetch(`${src.url}/query?${params}`, { signal: AbortSignal.timeout(60_000) })
      if (!res.ok) throw new Error(`API ${res.status}`)
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

async function importBatch(rows) {
  const { error } = await supabase.from('schedule_reports').upsert(rows, { onConflict: 'address,city', ignoreDuplicates: true })
  if (!error) return { n: rows.length }
  const { error: ie } = await supabase.from('schedule_reports').insert(rows)
  if (!ie) return { n: rows.length }
  let ok = 0, fail = 0, lastErr = ie.message
  for (const row of rows) {
    const { error: e } = await supabase.from('schedule_reports').insert([row])
    if (e) { fail++; lastErr = e.message } else { ok++ }
  }
  return { n: ok, error: fail ? `${fail} fails: ${lastErr}` : null }
}

async function importCity(slug) {
  const src = SOURCES[slug]
  if (!src) { console.error(`Unknown: ${slug}`); return }
  console.log(`\n=== ${slug} ===`)
  const reporterHash = crypto.createHash('sha256').update(`city_api_${slug}`).digest('hex').substring(0, 16)
  const now = new Date().toISOString()
  let offset = 0, fetched = 0, imported = 0, skipped = 0, errors = 0
  let batch = []
  const seen = new Set()

  while (true) {
    const features = await fetchPage(src, offset)
    if (features.length === 0) break
    fetched += features.length

    for (const f of features) {
      const a = f.attributes
      const day = src.day(a)
      if (!day) { skipped++; continue }
      const street = src.addr(a)
      if (!street) { skipped++; continue }
      if (seen.has(street)) { skipped++; continue }
      seen.add(street)

      let lat = null, lng = null
      if (src.geom === 'point') { lat = f.geometry?.y ?? null; lng = f.geometry?.x ?? null }
      else if (src.geom === 'rings') { const [x, y] = centroidRings(f.geometry?.rings); lng = x; lat = y }

      batch.push({
        address: street, city: slug, state: src.state,
        zip_code: src.zip(a), neighborhood: src.nbhd(a),
        collection_day: day, recycling_week: 'A',
        reporter_hash: reporterHash, verified: true, verification_count: 1,
        source: 'city_api', fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(`${street}${day}`).digest('hex'),
        hauler: src.hauler,
        data_source_url: src.url,
        data_source_type: 'gis',
        lat, lng,
      })

      if (batch.length >= BATCH_SIZE) {
        const r = await importBatch(batch)
        imported += r.n || 0
        errors += batch.length - (r.n || 0)
        if (r.error) console.error(`  ${r.error}`)
        batch = []
        await new Promise(r => setTimeout(r, 50))
      }
    }
    process.stdout.write(`  F:${fetched} I:${imported} S:${skipped} E:${errors}  \r`)
    offset += PAGE_SIZE
    if (features.length < PAGE_SIZE) break
    await new Promise(r => setTimeout(r, 200))
  }

  if (batch.length) {
    const r = await importBatch(batch)
    imported += r.n || 0
    errors += batch.length - (r.n || 0)
  }
  console.log(`\n${slug}: fetched=${fetched} imported=${imported} skipped=${skipped} errors=${errors}`)
}

async function main() {
  const arg = process.argv[2] || 'all'
  const cities = arg === 'all' ? Object.keys(SOURCES) : [arg]
  for (const c of cities) await importCity(c)
}
main().catch(e => { console.error('Fatal:', e); process.exit(1) })
