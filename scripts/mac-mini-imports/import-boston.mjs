#!/usr/bin/env node
/**
 * Import Boston MA waste collection schedules
 *
 * Strategy:
 * 1. Load 52 trash zone polygons with TRASHDAY (M/T/W/TH/F/MTH/MF/TF)
 * 2. Read 400K SAM addresses CSV with lat/lng
 * 3. Point-in-polygon to assign each address its collection day
 * 4. Some zones have multiple days (MTH = Monday+Thursday, MF = Monday+Friday)
 *    — we use the first day as the primary collection day
 *
 * Sources:
 * - Zones: data.boston.gov Trash Collection Days (GeoJSON)
 * - Addresses: data.boston.gov Live SAM Addresses (CSV)
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'
import { readFileSync, createReadStream } from 'fs'
import { createInterface } from 'readline'
import booleanPointInPolygon from '@turf/boolean-point-in-polygon'
import { point } from '@turf/helpers'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing env vars. Run with: node --env-file=.env.local scripts/import-boston.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)
const BATCH_SIZE = 500

const DAY_MAP = {
  'M': 'monday', 'T': 'tuesday', 'W': 'wednesday', 'TH': 'thursday', 'F': 'friday',
  'MTH': 'monday', 'MF': 'monday', 'TF': 'tuesday',  // Multi-day: use first day as primary
}

function loadZones(filepath) {
  const raw = readFileSync(filepath, 'utf8')
  const geojson = JSON.parse(raw)
  return geojson.features.filter(f => f.geometry && f.properties.TRASHDAY && DAY_MAP[f.properties.TRASHDAY])
}

function findZoneDay(lng, lat, zones) {
  const pt = point([lng, lat])
  for (const zone of zones) {
    try {
      if (booleanPointInPolygon(pt, zone)) return DAY_MAP[zone.properties.TRASHDAY]
    } catch { /* skip */ }
  }
  return null
}

const BOSTON_ZIPS = {
  '02108': 'Beacon Hill', '02109': 'Waterfront', '02110': 'Financial District',
  '02111': 'Chinatown', '02113': 'North End', '02114': 'West End',
  '02115': 'Fenway', '02116': 'Back Bay', '02118': 'South End',
  '02119': 'Roxbury', '02120': 'Mission Hill', '02121': 'Dorchester',
  '02122': 'Dorchester', '02124': 'Dorchester', '02125': 'Dorchester',
  '02126': 'Mattapan', '02127': 'South Boston', '02128': 'East Boston',
  '02129': 'Charlestown', '02130': 'Jamaica Plain', '02131': 'Roslindale',
  '02132': 'West Roxbury', '02134': 'Allston', '02135': 'Brighton',
  '02136': 'Hyde Park',
}

async function importBatch(rows) {
  const { error } = await supabase
    .from('schedule_reports')
    .upsert(rows, { onConflict: 'address,city', ignoreDuplicates: true })
  if (error) {
    const { error: e2 } = await supabase.from('schedule_reports').insert(rows)
    if (e2) return { ok: false, error: e2.message }
  }
  return { ok: true }
}

async function main() {
  console.log('🗑️  TrashAlert — Boston MA Data Import')
  console.log('=======================================')

  const { count: existing } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'boston')

  console.log(`📊 Existing Boston records: ${existing || 0}`)
  if (existing && existing > 300000) {
    console.log('⚠️  Already imported. Skipping.')
    process.exit(0)
  }

  console.log('\n📍 Loading trash zone polygons...')
  const zones = loadZones('data/boston-trash-zones.geojson')
  console.log(`   ${zones.length} zones loaded`)

  const reporterHash = crypto.createHash('sha256').update('city_api_boston_ma').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let totalRead = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let noZoneCount = 0
  let batchBuffer = []
  const seen = new Set()

  console.log('\n📥 Processing Boston addresses...\n')

  const rl = createInterface({ input: createReadStream('data/boston-addresses.csv') })
  let headers = null

  for await (const line of rl) {
    // Strip BOM from first line
    const cleanLine = line.replace(/^\uFEFF/, '')
    if (!headers) {
      headers = cleanLine.split(',').map(h => h.trim())
      continue
    }

    totalRead++

    // Parse CSV
    const values = cleanLine.split(',')
    const record = {}
    headers.forEach((h, i) => { record[h] = (values[i] || '').trim() })

    const address = (record['FULL_ADDRESS'] || '').toLowerCase().replace(/\s+/g, ' ').trim()
    if (!address || address.length < 3) { totalSkipped++; continue }

    if (seen.has(address)) { totalSkipped++; continue }
    seen.add(address)

    // CSV ends with: ...,lng_value,lat_value (note: -71=lng, 42=lat)
    const lng = parseFloat(values[values.length - 2])
    const lat = parseFloat(values[values.length - 1])

    if (isNaN(lat) || isNaN(lng) || lat === 0 || lng === 0) { totalSkipped++; continue }

    const collectionDay = findZoneDay(lng, lat, zones)
    if (!collectionDay) { noZoneCount++; totalSkipped++; continue }

    const zip = (record['ZIP_CODE'] || '').substring(0, 5)
    const neighborhood = BOSTON_ZIPS[zip] || record['MAILING_NEIGHBORHOOD'] || 'Boston'

    batchBuffer.push({
      address,
      city: 'boston',
      state: 'MA',
      zip_code: zip,
      neighborhood,
      collection_day: collectionDay,
      recycling_week: 'A',
      reporter_hash: reporterHash,
      verified: true,
      verification_count: 1,
      source: 'city_api',
      fetched_at: now,
      raw_payload_hash: crypto.createHash('md5').update(cleanLine).digest('hex'),
      hauler: 'Boston Public Works Department',
      data_source_url: 'https://data.boston.gov/dataset/live-street-address-management-sam-addresses',
      data_source_type: 'gis',
      lat,
      lng,
    })

    if (batchBuffer.length >= BATCH_SIZE) {
      const result = await importBatch(batchBuffer)
      if (result.ok) totalImported += batchBuffer.length
      else { totalErrors += batchBuffer.length; if (totalErrors <= 2500) console.error(`  ⚠️  ${result.error}`) }
      batchBuffer = []
      await new Promise(r => setTimeout(r, 50))
    }

    if (totalRead % 10000 === 0) {
      process.stdout.write(`  📊 Read: ${totalRead} | Imported: ${totalImported} | Skipped: ${totalSkipped} (${noZoneCount} no zone) | Errors: ${totalErrors}    \r`)
    }
  }

  if (batchBuffer.length > 0) {
    const result = await importBatch(batchBuffer)
    if (result.ok) totalImported += batchBuffer.length
    else totalErrors += batchBuffer.length
  }

  console.log(`\n\n=======================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Read:     ${totalRead}`)
  console.log(`   Imported: ${totalImported}`)
  console.log(`   Skipped:  ${totalSkipped} (${noZoneCount} outside zones)`)
  console.log(`   Errors:   ${totalErrors}`)

  const { count: c } = await supabase.from('schedule_reports').select('*', { count: 'exact', head: true }).eq('city', 'boston')
  const { count: t } = await supabase.from('schedule_reports').select('*', { count: 'exact', head: true })
  console.log(`\n📊 Final: Boston=${c}, Total=${t}`)
}

main().catch(err => { console.error('\nFatal:', err); process.exit(1) })
