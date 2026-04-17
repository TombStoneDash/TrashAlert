#!/usr/bin/env node
/**
 * Import Baltimore MD waste collection schedules.
 *
 * Source: City of Baltimore Trash FeatureServer
 *   Trash (street segments):  https://services3.arcgis.com/bpeS3swje8g57sok/arcgis/rest/services/Trash/FeatureServer/0
 *   Recycling zones:          https://services3.arcgis.com/bpeS3swje8g57sok/arcgis/rest/services/Trash/FeatureServer/1
 *
 * Fields: TRASH_RT, TRASH_DAY, RECYCL_DAY, BIN_COLOR, STR_NAME, STR_TYPE,
 *         PREFIX_DIR, LEFT_FROM, LEFT_TO, RIGHT_FROM, RIGHT_TO
 * Approach: Street-segment polylines with address ranges. Expand LEFT_FROM..LEFT_TO
 *           (even) and RIGHT_FROM..RIGHT_TO (odd) into individual house addresses.
 *           Cap per-segment expansion at 100 houses to avoid runaway fetches.
 */
import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Run with: node --env-file=.env.local scripts/import-baltimore.mjs')
  process.exit(1)
}
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const TRASH_URL = 'https://services3.arcgis.com/bpeS3swje8g57sok/arcgis/rest/services/Trash/FeatureServer/0/query'
const FIELDS = 'TRASH_RT,TRASH_DAY,RECYCL_DAY,BIN_COLOR,STR_NAME,STR_TYPE,PREFIX_DIR,LEFT_FROM,LEFT_TO,RIGHT_FROM,RIGHT_TO'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500
const MAX_HOUSES_PER_SEGMENT = 100

const DAY_MAP = {
  MON: 'monday', TUE: 'tuesday', WED: 'wednesday', THU: 'thursday', FRI: 'friday', SAT: 'saturday',
  MONDAY: 'monday', TUESDAY: 'tuesday', WEDNESDAY: 'wednesday', THURSDAY: 'thursday', FRIDAY: 'friday', SATURDAY: 'saturday',
}
const normalizeDay = raw => (raw && DAY_MAP[String(raw).trim().toUpperCase()]) || null

function midpoint(paths) {
  if (!paths?.[0]?.length) return null
  const line = paths[0]
  const mid = line[Math.floor(line.length / 2)]
  return mid ? { lng: mid[0], lat: mid[1] } : null
}

function* expandRange(from, to, parity) {
  if (!from || !to) return
  const lo = Math.min(from, to), hi = Math.max(from, to)
  for (let h = lo; h <= hi; h++) {
    if (parity === 'even' && h % 2 !== 0) continue
    if (parity === 'odd' && h % 2 === 0) continue
    yield h
  }
}

async function fetchPage(offset) {
  const params = new URLSearchParams({
    where: '1=1', outFields: FIELDS, outSR: '4326', returnGeometry: 'true',
    resultOffset: String(offset), resultRecordCount: String(PAGE_SIZE),
    orderByFields: 'OBJECTID ASC', f: 'json',
  })
  const res = await fetch(`${TRASH_URL}?${params}`)
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

function streetName(a) {
  const parts = [a.PREFIX_DIR, a.STR_NAME, a.STR_TYPE].filter(Boolean).map(s => String(s).trim())
  return parts.join(' ').toLowerCase()
}

async function main() {
  console.log('🗑️  TrashAlert — Baltimore MD Data Import')
  console.log('=========================================')
  const reporterHash = crypto.createHash('sha256').update('city_api_baltimore_md').digest('hex').substring(0, 16)
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
      const trashDay = normalizeDay(a.TRASH_DAY)
      if (!trashDay) { skipped++; continue }
      const recyDay = normalizeDay(a.RECYCL_DAY)

      const mid = midpoint(f.geometry?.paths)
      if (!mid) { skipped++; continue }
      const street = streetName(a)
      if (!street) { skipped++; continue }

      const recyWeek = (a.BIN_COLOR || '').toUpperCase().includes('BLUE') ? 'A'
        : (a.BIN_COLOR || '').toUpperCase().includes('GREEN') ? 'B' : 'A'

      // Expand LEFT_FROM..LEFT_TO (even), RIGHT_FROM..RIGHT_TO (odd)
      const houses = [
        ...expandRange(a.LEFT_FROM, a.LEFT_TO, 'even'),
        ...expandRange(a.RIGHT_FROM, a.RIGHT_TO, 'odd'),
      ].slice(0, MAX_HOUSES_PER_SEGMENT)

      if (houses.length === 0) {
        // Fall back to one zone-level record per segment.
        const address = `baltimore trash route ${String(a.TRASH_RT || 'zone').toLowerCase()} ${street}`
        if (!seen.has(address)) {
          seen.add(address)
          batch.push({
            address, city: 'baltimore', state: 'MD', zip_code: '',
            neighborhood: `Route ${a.TRASH_RT || ''}`.trim(),
            collection_day: trashDay, recycling_week: recyWeek,
            reporter_hash: reporterHash, verified: true, verification_count: 1,
            source: 'city_api', fetched_at: now,
            raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
            hauler: 'Baltimore DPW', data_source_url: TRASH_URL.replace('/query', ''),
            data_source_type: 'gis', lat: mid.lat, lng: mid.lng,
          })
        } else skipped++
      } else {
        for (const h of houses) {
          const address = `${h} ${street}`
          if (seen.has(address)) { skipped++; continue }
          seen.add(address)
          batch.push({
            address, city: 'baltimore', state: 'MD', zip_code: '',
            neighborhood: `Route ${a.TRASH_RT || ''}`.trim(),
            collection_day: trashDay, recycling_week: recyWeek,
            reporter_hash: reporterHash, verified: true, verification_count: 1,
            source: 'city_api', fetched_at: now,
            raw_payload_hash: crypto.createHash('md5').update(String(h) + street).digest('hex'),
            hauler: 'Baltimore DPW', data_source_url: TRASH_URL.replace('/query', ''),
            data_source_type: 'gis', lat: mid.lat, lng: mid.lng,
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
  console.log(`\n🎉 Baltimore: fetched=${fetched} imported=${imported} skipped=${skipped} errors=${errors}`)
}
main().catch(e => { console.error('Fatal:', e); process.exit(1) })
