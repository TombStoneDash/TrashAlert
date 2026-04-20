#!/usr/bin/env node
/**
 * The Woodlands TX — per-parcel waste collection.
 * Source: tharcgis2.thewoodlands-tx.gov/.../TRASH_SERVICE_AREAS/FeatureServer/3
 * 41,964 parcel polygons with FORMATTED_ADDRESS + COLLECTION_DAY.
 */
import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Run with: node --env-file=.env.local scripts/import-woodlands.mjs')
  process.exit(1)
}
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://tharcgis2.thewoodlands-tx.gov/arcgis/rest/services/TRASH_SERVICE_AREAS/FeatureServer/3/query'
const FIELDS = 'OBJECTID,FORMATTED_ADDRESS,ZIP_CODE,CITY,VILLAGENAM,VILLAGEGROUP,COLLECTION_DAY,Day_Abbrev'
const PAGE_SIZE = 2000

const DAY_MAP = {
  monday:'monday', mon:'monday', m:'monday',
  tuesday:'tuesday', tue:'tuesday', tu:'tuesday', t:'tuesday',
  wednesday:'wednesday', wed:'wednesday', w:'wednesday',
  thursday:'thursday', thu:'thursday', th:'thursday',
  friday:'friday', fri:'friday', f:'friday',
  saturday:'saturday', sat:'saturday', sa:'saturday', s:'saturday',
  sunday:'sunday', sun:'sunday', su:'sunday',
}
function normDay(raw) {
  if (!raw) return null
  return DAY_MAP[String(raw).trim().toLowerCase()] || null
}

function centroidRings(rings) {
  if (!rings?.length) return [null, null]
  let sx = 0, sy = 0, n = 0
  for (const ring of rings) for (const [x, y] of ring) { sx += x; sy += y; n++ }
  return n ? [sx / n, sy / n] : [null, null]
}

async function fetchPage(offset) {
  const params = new URLSearchParams({
    where: '1=1', outFields: FIELDS, outSR: '4326', returnGeometry: 'true',
    resultOffset: String(offset), resultRecordCount: String(PAGE_SIZE),
    orderByFields: 'OBJECTID ASC', f: 'json',
  })
  for (let attempt = 1; attempt <= 6; attempt++) {
    try {
      const res = await fetch(`${BASE_URL}?${params}`, { signal: AbortSignal.timeout(60_000) })
      if (!res.ok) throw new Error(`API ${res.status}`)
      const data = await res.json()
      if (data.error) throw new Error(`ArcGIS: ${data.error.message}`)
      return data.features || []
    } catch (e) {
      const wait = Math.min(45_000, 3000 * attempt)
      process.stdout.write(`\n    ↻ retry ${attempt}: ${e.message} (${wait}ms)\n`)
      await new Promise(r => setTimeout(r, wait))
    }
  }
  throw new Error('exhausted retries')
}

async function main() {
  console.log('The Woodlands TX Import (~42K parcels)')
  const reporterHash = crypto.createHash('sha256').update('city_api_woodlands_tx').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let offset = 0, fetched = 0, imported = 0, skipped = 0, errors = 0
  const seen = new Set()
  let batch = []

  while (true) {
    const features = await fetchPage(offset)
    if (features.length === 0) break
    fetched += features.length

    for (const f of features) {
      const a = f.attributes
      const day = normDay(a.COLLECTION_DAY) || normDay(a.Day_Abbrev)
      if (!day) { skipped++; continue }
      const street = String(a.FORMATTED_ADDRESS || '').trim().toLowerCase()
      if (!street) { skipped++; continue }
      if (seen.has(street)) { skipped++; continue }
      seen.add(street)
      const [lng, lat] = centroidRings(f.geometry?.rings)
      batch.push({
        address: street, city: 'the-woodlands-tx', state: 'TX',
        zip_code: String(a.ZIP_CODE || '').split('-')[0].trim(),
        neighborhood: `${a.VILLAGENAM || ''} | ${a.VILLAGEGROUP || ''}`.trim(),
        collection_day: day, recycling_week: 'A',
        reporter_hash: reporterHash, verified: true, verification_count: 1,
        source: 'city_api', fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(`${street}${day}`).digest('hex'),
        hauler: 'The Woodlands Township',
        data_source_url: BASE_URL.replace('/query', ''),
        data_source_type: 'gis',
        lat, lng,
      })

      if (batch.length >= 500) {
        const { error } = await supabase.from('schedule_reports').upsert(batch, { onConflict: 'address,city', ignoreDuplicates: true })
        if (!error) imported += batch.length
        else { const { error: ie } = await supabase.from('schedule_reports').insert(batch); if (!ie) imported += batch.length; else { errors += batch.length; console.error(ie.message) } }
        batch = []
        await new Promise(r => setTimeout(r, 50))
      }
    }
    process.stdout.write(`  F:${fetched} I:${imported} S:${skipped}  \r`)
    offset += PAGE_SIZE
    if (features.length < PAGE_SIZE) break
    await new Promise(r => setTimeout(r, 200))
  }

  if (batch.length) {
    const { error } = await supabase.from('schedule_reports').upsert(batch, { onConflict: 'address,city', ignoreDuplicates: true })
    if (!error) imported += batch.length
    else { const { error: ie } = await supabase.from('schedule_reports').insert(batch); if (!ie) imported += batch.length; else { errors += batch.length; console.error(ie.message) } }
  }
  console.log(`\nThe Woodlands: fetched=${fetched} imported=${imported} skipped=${skipped} errors=${errors}`)
}
main().catch(e => { console.error('Fatal:', e); process.exit(1) })
