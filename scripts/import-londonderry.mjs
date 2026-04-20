#!/usr/bin/env node
/**
 * Londonderry NH (Town of Londonderry — TOL) — per-address waste.
 * Source: services2.arcgis.com/r6DCOO5nDt5tIToY/.../AGOL_Trash_Addresses/FeatureServer/0
 * 9,714 address points with TrashPickup + RecyclePickup.
 */
import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
if (!SUPABASE_URL || !SUPABASE_KEY) { console.error('need .env.local'); process.exit(1) }
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://services2.arcgis.com/r6DCOO5nDt5tIToY/arcgis/rest/services/AGOL_Trash_Addresses/FeatureServer/0/query'
const FIELDS = 'OBJECTID_1,address,addr_zip,TrashPickup,RecyclePickup,fire_dist'
const PAGE_SIZE = 1000

const DAY_MAP = { monday:'monday', tuesday:'tuesday', wednesday:'wednesday', thursday:'thursday', friday:'friday', saturday:'saturday', sunday:'sunday' }
const normDay = (raw) => raw ? (DAY_MAP[String(raw).trim().toLowerCase()] || null) : null

async function fetchPage(offset) {
  const params = new URLSearchParams({
    where: 'TrashPickup IS NOT NULL', outFields: FIELDS, outSR: '4326', returnGeometry: 'true',
    resultOffset: String(offset), resultRecordCount: String(PAGE_SIZE),
    orderByFields: 'OBJECTID_1 ASC', f: 'json',
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
  console.log('Londonderry NH Import (~9.7K addresses)')
  const reporterHash = crypto.createHash('sha256').update('city_api_londonderry_nh').digest('hex').substring(0, 16)
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
      const day = normDay(a.TrashPickup)
      if (!day) { skipped++; continue }
      const street = String(a.address || '').trim().toLowerCase()
      if (!street) { skipped++; continue }
      if (seen.has(street)) { skipped++; continue }
      seen.add(street)
      batch.push({
        address: street, city: 'londonderry-nh', state: 'NH',
        zip_code: String(a.addr_zip || '').trim(),
        neighborhood: a.fire_dist || '',
        collection_day: day, recycling_week: 'A',
        reporter_hash: reporterHash, verified: true, verification_count: 1,
        source: 'city_api', fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(`${street}${day}`).digest('hex'),
        hauler: 'Town of Londonderry',
        data_source_url: BASE_URL.replace('/query', ''),
        data_source_type: 'gis',
        lat: f.geometry?.y ?? null, lng: f.geometry?.x ?? null,
      })

      if (batch.length >= 500) {
        const { error } = await supabase.from('schedule_reports').upsert(batch, { onConflict: 'address,city', ignoreDuplicates: true })
        if (!error) imported += batch.length
        else { const { error: ie } = await supabase.from('schedule_reports').insert(batch); if (!ie) imported += batch.length; else { errors += batch.length; console.error(ie.message) } }
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
    const { error } = await supabase.from('schedule_reports').upsert(batch, { onConflict: 'address,city', ignoreDuplicates: true })
    if (!error) imported += batch.length
    else { const { error: ie } = await supabase.from('schedule_reports').insert(batch); if (!ie) imported += batch.length; else { errors += batch.length; console.error(ie.message) } }
  }
  console.log(`\nLondonderry: fetched=${fetched} imported=${imported} skipped=${skipped} errors=${errors}`)
}
main().catch(e => { console.error('Fatal:', e); process.exit(1) })
