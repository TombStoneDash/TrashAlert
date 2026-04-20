#!/usr/bin/env node
/**
 * Hillsborough County FL — per-address waste collection.
 * Source: services.arcgis.com/apTfC6SUmnNfnxuF/.../SolidWaste_CustomerPermits_Dec2022/FeatureServer/1
 * 310,848 per-address points, twice-weekly (USER_G1___DAYS + USER_G2___DAYS).
 * Spans Tampa-area unincorporated Hillsborough (Odessa, Lutz, Tampa, Brandon, Riverview, etc.).
 */
import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Run with: node --env-file=.env.local scripts/import-hillsborough.mjs')
  process.exit(1)
}
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://services.arcgis.com/apTfC6SUmnNfnxuF/arcgis/rest/services/SolidWaste_CustomerPermits_Dec2022/FeatureServer/1/query'
const FIELDS = 'USER_PROPERTY_ADDRESS,USER_CITY,USER_ZIP_CODE,USER_Hauler,USER_G1___DAYS,USER_G2___DAYS,USER_SERVICE_DAY___RECYCLING,USER_SERVICE_DAY___YARD_WASTE,OBJECTID'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

const DAY_MAP = {
  monday:'monday', mon:'monday',
  tuesday:'tuesday', tue:'tuesday', tues:'tuesday',
  wednesday:'wednesday', wed:'wednesday',
  thursday:'thursday', thu:'thursday', thur:'thursday', thurs:'thursday',
  friday:'friday', fri:'friday',
  saturday:'saturday', sat:'saturday',
  sunday:'sunday', sun:'sunday',
}
function normDay(raw) {
  if (!raw) return null
  return DAY_MAP[String(raw).trim().toLowerCase()] || null
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
      process.stdout.write(`\n    ↻ retry ${attempt} @ offset ${offset}: ${e.message} (${wait}ms)\n`)
      await new Promise(r => setTimeout(r, wait))
    }
  }
  throw new Error(`exhausted retries at offset ${offset}`)
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

async function main() {
  console.log('Hillsborough County FL Import (~310K addresses)')
  const reporterHash = crypto.createHash('sha256').update('city_api_hillsborough_fl').digest('hex').substring(0, 16)
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
      const day = normDay(a.USER_G1___DAYS)
      if (!day) { skipped++; continue }
      const street = String(a.USER_PROPERTY_ADDRESS || '').trim().toLowerCase()
      if (!street) { skipped++; continue }
      if (seen.has(street)) { skipped++; continue }
      seen.add(street)

      const day2 = normDay(a.USER_G2___DAYS)
      const recycling = normDay(a.USER_SERVICE_DAY___RECYCLING)
      batch.push({
        address: street, city: 'hillsborough-county-fl', state: 'FL',
        zip_code: String(a.USER_ZIP_CODE || '').trim(),
        neighborhood: `${a.USER_CITY || ''} | trash2: ${day2 || ''} | recycle: ${recycling || ''}`,
        collection_day: day, recycling_week: 'A',
        reporter_hash: reporterHash, verified: true, verification_count: 1,
        source: 'city_api', fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(`${street}${day}`).digest('hex'),
        hauler: String(a.USER_Hauler || 'Hillsborough County').trim(),
        data_source_url: BASE_URL.replace('/query', ''),
        data_source_type: 'gis',
        lat: f.geometry?.y ?? null, lng: f.geometry?.x ?? null,
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
    await new Promise(r => setTimeout(r, 250))
  }

  if (batch.length) {
    const r = await importBatch(batch)
    imported += r.n || 0
    errors += batch.length - (r.n || 0)
  }
  console.log(`\nHillsborough: fetched=${fetched} imported=${imported} skipped=${skipped} errors=${errors}`)
}
main().catch(e => { console.error('Fatal:', e); process.exit(1) })
