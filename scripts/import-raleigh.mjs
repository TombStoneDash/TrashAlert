#!/usr/bin/env node
/**
 * Import Raleigh NC waste collection schedules.
 *
 * Source: City of Raleigh Solid Waste Services collection points
 *   https://services.arcgis.com/v400IkDOw1ad7Yad/arcgis/rest/services/RALEIGH_SWS_COLLECTION/FeatureServer/0
 *
 * This is a per-address point dataset (~122K points, one per service
 * connection). Each row carries SERVICEDAY (Mon-Fri) and DAY_WEEK
 * (e.g. "TUESDAY WEEK_B" → recycling week A/B).
 */
import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Run with: node --env-file=.env.local scripts/import-raleigh.mjs')
  process.exit(1)
}
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://services.arcgis.com/v400IkDOw1ad7Yad/arcgis/rest/services/RALEIGH_SWS_COLLECTION/FeatureServer/0/query'
const FIELDS = 'ADDRESS,CITY,STATE,ZIPCODE,SERVICEDAY,DAY_WEEK,RECYCLE,GARBAGE,OBJECTID'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

const DAY_MAP = {
  MON: 'monday', TUE: 'tuesday', WED: 'wednesday', THU: 'thursday', FRI: 'friday', SAT: 'saturday',
  MONDAY: 'monday', TUESDAY: 'tuesday', WEDNESDAY: 'wednesday', THURSDAY: 'thursday', FRIDAY: 'friday', SATURDAY: 'saturday',
}
const normalizeDay = raw => (raw && DAY_MAP[String(raw).split(/\s+/)[0].trim().toUpperCase()]) || null

function recyclingWeek(dayWeek) {
  const s = String(dayWeek || '').toUpperCase()
  if (s.includes('WEEK_A') || s.includes('WEEK A')) return 'A'
  if (s.includes('WEEK_B') || s.includes('WEEK B')) return 'B'
  return 'A'
}

async function fetchPage(offset) {
  const params = new URLSearchParams({
    where: '1=1', outFields: FIELDS, outSR: '4326', returnGeometry: 'true',
    resultOffset: String(offset), resultRecordCount: String(PAGE_SIZE),
    orderByFields: 'OBJECTID ASC', f: 'json',
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
  console.log('🗑️  TrashAlert — Raleigh NC Data Import')
  console.log('=======================================')
  const reporterHash = crypto.createHash('sha256').update('city_api_raleigh_nc').digest('hex').substring(0, 16)
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
      const day = normalizeDay(a.SERVICEDAY)
      if (!day) { skipped++; continue }
      const street = String(a.ADDRESS || '').trim().toLowerCase()
      if (!street) { skipped++; continue }
      if (seen.has(street)) { skipped++; continue }
      seen.add(street)

      const lat = f.geometry?.y ?? null
      const lng = f.geometry?.x ?? null

      batch.push({
        address: street, city: 'raleigh-nc', state: 'NC',
        zip_code: String(a.ZIPCODE || '').trim(),
        neighborhood: '',
        collection_day: day, recycling_week: recyclingWeek(a.DAY_WEEK),
        reporter_hash: reporterHash, verified: true, verification_count: 1,
        source: 'city_api', fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(`${street}${day}`).digest('hex'),
        hauler: 'City of Raleigh Solid Waste Services',
        data_source_url: BASE_URL.replace('/query', ''),
        data_source_type: 'gis', lat, lng,
      })

      if (batch.length >= BATCH_SIZE) {
        const r = await importBatch(batch)
        if (r.ok) imported += batch.length
        else { errors += batch.length; if (errors <= 2500) console.error(`  ⚠️ ${r.error}`) }
        batch = []
        await new Promise(r => setTimeout(r, 50))
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
  console.log(`\n🎉 Raleigh: fetched=${fetched} imported=${imported} skipped=${skipped} errors=${errors}`)
}
main().catch(e => { console.error('Fatal:', e); process.exit(1) })
