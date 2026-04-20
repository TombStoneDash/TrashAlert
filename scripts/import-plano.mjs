#!/usr/bin/env node
/**
 * Plano TX — per-address waste collection.
 * Source: maps.planogis.org/.../Sustainability/ServicedAddresses/MapServer/0
 * 75,151 parcel polygons with ADDRESS, COLL_DAY, REC_WEEK, BULKY_DAY.
 */
import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Run with: node --env-file=.env.local scripts/import-plano.mjs [startOffset]')
  process.exit(1)
}
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://maps.planogis.org/arcgiswad/rest/services/Sustainability/ServicedAddresses/MapServer/0/query'
const FIELDS = 'OBJECTID,ADDRESS,COLL_DAY,REC_WEEK,BULKY_DAY,SERVICE,SUPERVISOR,PickUp'
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
const normDay = (raw) => raw ? (DAY_MAP[String(raw).trim().toLowerCase()] || null) : null

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
  const startOffset = parseInt(process.argv[2] || '0', 10)
  console.log(`Plano TX Import (~75K addresses) start=${startOffset}`)
  const reporterHash = crypto.createHash('sha256').update('city_api_plano_tx').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let offset = startOffset, fetched = 0, imported = 0, skipped = 0, errors = 0
  let batch = []
  const seen = new Set()

  while (true) {
    const features = await fetchPage(offset)
    if (features.length === 0) break
    fetched += features.length

    for (const f of features) {
      const a = f.attributes
      const day = normDay(a.COLL_DAY)
      if (!day) { skipped++; continue }
      const street = String(a.ADDRESS || '').trim().toLowerCase()
      if (!street) { skipped++; continue }
      if (seen.has(street)) { skipped++; continue }
      seen.add(street)
      const [lng, lat] = centroidRings(f.geometry?.rings)
      const recWeek = String(a.REC_WEEK || '').trim().toLowerCase() === 'purple' ? 'B' : 'A'
      batch.push({
        address: street, city: 'plano-tx', state: 'TX',
        zip_code: '',
        neighborhood: `${a.PickUp || ''} | bulky: ${a.BULKY_DAY || ''}`,
        collection_day: day, recycling_week: recWeek,
        reporter_hash: reporterHash, verified: true, verification_count: 1,
        source: 'city_api', fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(`${street}${day}`).digest('hex'),
        hauler: 'City of Plano',
        data_source_url: BASE_URL.replace('/query', ''),
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
  console.log(`\nPlano: fetched=${fetched} imported=${imported} skipped=${skipped} errors=${errors}`)
}
main().catch(e => { console.error('Fatal:', e); process.exit(1) })
