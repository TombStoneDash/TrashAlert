#!/usr/bin/env node
/**
 * Import Phoenix AZ waste collection schedules
 *
 * Strategy:
 * 1. Load garbage zone polygons (196 zones with DOC=day) from GeoJSON
 * 2. Load recycling zone polygons (242 zones with DOC=day) from GeoJSON
 * 3. Read Phoenix address CSV (397K addresses with State Plane coords)
 * 4. Convert coords from AZ State Plane (EPSG:2868) to WGS84 (EPSG:4326)
 * 5. Point-in-polygon to assign each address its garbage + recycling day
 * 6. Batch import to Supabase
 *
 * Sources:
 * - Zones: https://maps.phoenix.gov/pub/rest/services/Public/GarbagePickUp/MapServer
 * - Addresses: https://phoenixopendata.com - Solid Waste Active Service Addresses
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'
import { readFileSync, createReadStream } from 'fs'
import { createInterface } from 'readline'
import booleanPointInPolygon from '@turf/boolean-point-in-polygon'
import { point } from '@turf/helpers'
import proj4 from 'proj4'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing env vars. Run with: node --env-file=.env.local scripts/import-phoenix.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)
const BATCH_SIZE = 500

// Arizona Central State Plane (EPSG:2868) - NAD83(HARN), US feet
// See: https://epsg.io/2868
proj4.defs('EPSG:2868', '+proj=tmerc +lat_0=31 +lon_0=-111.9166666666667 +k=0.9999 +x_0=213360 +y_0=0 +ellps=GRS80 +towgs84=0,0,0,0,0,0,0 +units=ft +no_defs')

function loadZones(filepath) {
  const raw = readFileSync(filepath, 'utf8')
  const geojson = JSON.parse(raw)
  return geojson.features.filter(f => f.geometry && f.properties.DOC)
}

function findZoneDay(lng, lat, zones) {
  const pt = point([lng, lat])
  for (const zone of zones) {
    try {
      if (booleanPointInPolygon(pt, zone)) {
        return zone.properties.DOC.toLowerCase()
      }
    } catch { /* skip malformed polygons */ }
  }
  return null
}

// Phoenix ZIP to neighborhood mapping
function getNeighborhood(zip) {
  const areas = {
    '85003': 'Downtown', '85004': 'Downtown', '85006': 'Encanto', '85007': 'Central City South',
    '85008': 'Camelback East', '85009': 'Alhambra', '85012': 'Encanto', '85013': 'Alhambra',
    '85014': 'Camelback East', '85015': 'Alhambra', '85016': 'Camelback East',
    '85017': 'Alhambra', '85018': 'Camelback East', '85019': 'Maryvale',
    '85020': 'North Mountain', '85021': 'North Mountain', '85022': 'Paradise Valley Village',
    '85023': 'Deer Valley', '85024': 'Paradise Valley Village', '85027': 'Deer Valley',
    '85028': 'Paradise Valley Village', '85029': 'North Mountain', '85031': 'Maryvale',
    '85032': 'Paradise Valley Village', '85033': 'Maryvale', '85034': 'South Mountain',
    '85035': 'Maryvale', '85037': 'Estrella', '85040': 'South Mountain',
    '85041': 'Laveen', '85042': 'South Mountain', '85043': 'Laveen',
    '85044': 'Ahwatukee Foothills', '85045': 'Ahwatukee Foothills',
    '85048': 'Ahwatukee Foothills', '85050': 'Paradise Valley Village',
    '85051': 'North Mountain', '85053': 'Deer Valley', '85054': 'Paradise Valley Village',
    '85083': 'Deer Valley', '85085': 'North Gateway', '85086': 'North Gateway',
    '85087': 'North Gateway', '85339': 'Laveen',
  }
  const zip5 = (zip || '').substring(0, 5)
  return areas[zip5] || 'Phoenix'
}

async function importBatch(rows) {
  const { error } = await supabase
    .from('schedule_reports')
    .upsert(rows, { onConflict: 'address,city', ignoreDuplicates: true })

  if (error) {
    const { error: insertError } = await supabase.from('schedule_reports').insert(rows)
    if (insertError) return { ok: false, error: insertError.message }
  }
  return { ok: true }
}

async function main() {
  console.log('🗑️  TrashAlert — Phoenix AZ Data Import')
  console.log('========================================')

  // Check existing
  const { count: existing } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'phoenix')

  console.log(`📊 Existing Phoenix records: ${existing || 0}`)
  if (existing && existing > 300000) {
    console.log('⚠️  Phoenix already imported. Skipping.')
    process.exit(0)
  }

  // Load zone polygons
  console.log('\n📍 Loading zone polygons...')
  const garbageZones = loadZones('data/phoenix-garbage-zones.geojson')
  const recyclingZones = loadZones('data/phoenix-recycling-zones.geojson')
  console.log(`   Garbage zones: ${garbageZones.length}`)
  console.log(`   Recycling zones: ${recyclingZones.length}`)

  // Process CSV
  console.log('\n📥 Processing Phoenix addresses...\n')

  const reporterHash = crypto.createHash('sha256').update('city_api_phoenix_az').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let totalRead = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let noZoneCount = 0
  let batchBuffer = []
  const seen = new Set()

  // Read CSV line by line
  const rl = createInterface({ input: createReadStream('data/phoenix-sw-addresses.csv') })
  let headers = null

  for await (const line of rl) {
    if (!headers) {
      headers = line.split(',').map(h => h.replace(/"/g, '').trim())
      continue
    }

    totalRead++

    // Simple CSV parse (handles quoted fields)
    const values = line.match(/(".*?"|[^",\s]+)(?=\s*,|\s*$)/g) || []
    const record = {}
    headers.forEach((h, i) => {
      record[h] = (values[i] || '').replace(/^"|"$/g, '').trim()
    })

    const address = (record['service address'] || '').toLowerCase().replace(/\s+/g, ' ').trim()
    if (!address || address.length < 3) { totalSkipped++; continue }

    const zip = record['Zip'] || ''
    const zip5 = zip.substring(0, 5)
    const key = `${address}|${zip5}`
    if (seen.has(key)) { totalSkipped++; continue }
    seen.add(key)

    // Convert coordinates from AZ State Plane to WGS84
    const x = parseFloat(record['GIS_X_COORDINATE'])
    const y = parseFloat(record['GIS_Y_COORDINATE'])
    if (isNaN(x) || isNaN(y) || x === 0 || y === 0) { totalSkipped++; continue }

    const [lng, lat] = proj4('EPSG:2868', 'EPSG:4326', [x, y])

    // Find garbage + recycling day via spatial join
    const garbageDay = findZoneDay(lng, lat, garbageZones)
    if (!garbageDay) { noZoneCount++; totalSkipped++; continue }

    const recycleDay = findZoneDay(lng, lat, recyclingZones)

    batchBuffer.push({
      address,
      city: 'phoenix',
      state: 'AZ',
      zip_code: zip5,
      neighborhood: getNeighborhood(zip5),
      collection_day: garbageDay,
      recycling_week: 'A', // Phoenix is weekly recycling, no A/B rotation
      reporter_hash: reporterHash,
      verified: true,
      verification_count: 1,
      source: 'city_api',
      fetched_at: now,
      raw_payload_hash: crypto.createHash('md5').update(line).digest('hex'),
      hauler: 'City of Phoenix Public Works',
      data_source_url: 'https://www.phoenixopendata.com/dataset/public-works-solid-waste-active-service-addresses',
      data_source_type: 'gis',
      lat,
      lng,
    })

    if (batchBuffer.length >= BATCH_SIZE) {
      const result = await importBatch(batchBuffer)
      if (result.ok) {
        totalImported += batchBuffer.length
      } else {
        totalErrors += batchBuffer.length
        if (totalErrors <= 2500) console.error(`  ⚠️  ${result.error}`)
      }
      batchBuffer = []
      await new Promise(r => setTimeout(r, 50))
    }

    if (totalRead % 10000 === 0) {
      process.stdout.write(`  📊 Read: ${totalRead} | Imported: ${totalImported} | Skipped: ${totalSkipped} (${noZoneCount} no zone) | Errors: ${totalErrors}    \r`)
    }
  }

  // Flush remaining
  if (batchBuffer.length > 0) {
    const result = await importBatch(batchBuffer)
    if (result.ok) totalImported += batchBuffer.length
    else totalErrors += batchBuffer.length
  }

  console.log(`\n\n========================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Read:     ${totalRead}`)
  console.log(`   Imported: ${totalImported}`)
  console.log(`   Skipped:  ${totalSkipped} (${noZoneCount} outside zones)`)
  console.log(`   Errors:   ${totalErrors}`)

  const { count: phxCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'phoenix')

  const { count: totalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\n📊 Final counts:`)
  console.log(`   Phoenix: ${phxCount}`)
  console.log(`   Total:   ${totalCount}`)
}

main().catch(err => { console.error('\nFatal:', err); process.exit(1) })
