#!/usr/bin/env node
/**
 * Import Denver CO waste collection schedules (expanded)
 *
 * Strategy:
 * 1. Load ~17K waste collection zone polygons with TRASH_DAY
 * 2. Fetch ~211K address points from GIS_INF_SUBADDRESS Layer 1
 * 3. Point-in-polygon to assign each address its collection day
 * 4. Batch import to Supabase
 *
 * Source:
 * - Addresses: https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/GIS_INF_SUBADDRESS/FeatureServer/1
 * - Waste zones: https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/ODC_ADMN_SOLIDWASTECOLLECTION_A/FeatureServer/311
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'
import { readFileSync } from 'fs'
import booleanPointInPolygon from '@turf/boolean-point-in-polygon'
import { point } from '@turf/helpers'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing env vars. Run with: node --env-file=.env.local scripts/import-denver-v2.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const ADDR_URL = 'https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/GIS_INF_SUBADDRESS/FeatureServer/1/query'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

const DAY_MAP = {
  'MO': 'monday', 'TU': 'tuesday', 'WE': 'wednesday', 'TH': 'thursday', 'FR': 'friday',
  'MONDAY': 'monday', 'TUESDAY': 'tuesday', 'WEDNESDAY': 'wednesday', 'THURSDAY': 'thursday', 'FRIDAY': 'friday',
}

const RECYCLE_WEEK_MAP = {
  'MA': 'A', 'MB': 'B', 'TA': 'A', 'TB': 'B',
  'WA': 'A', 'WB': 'B', 'HA': 'A', 'HB': 'B',
  'FA': 'A', 'FB': 'B',
}

function loadZones(filepath) {
  const raw = readFileSync(filepath, 'utf8')
  const geojson = JSON.parse(raw)
  return geojson.features.filter(f =>
    f.geometry &&
    f.properties.TRASH_DAY &&
    DAY_MAP[f.properties.TRASH_DAY]
  )
}

function findZone(lng, lat, zones) {
  const pt = point([lng, lat])
  for (const zone of zones) {
    try {
      if (booleanPointInPolygon(pt, zone)) return zone.properties
    } catch { /* skip malformed */ }
  }
  return null
}

async function fetchAddressPage(offset) {
  const params = new URLSearchParams({
    where: "STATUS='A'",
    outFields: 'FULL_ADDRESS,LATITUDE,LONGITUDE,ZIPCODE',
    returnGeometry: 'false',
    resultOffset: String(offset),
    resultRecordCount: String(PAGE_SIZE),
    orderByFields: 'OBJECTID ASC',
    f: 'json'
  })

  const res = await fetch(`${ADDR_URL}?${params}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  if (data.error) throw new Error(data.error.message)
  return { features: data.features || [], exceeded: data.exceededTransferLimit || false }
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
  console.log('🗑️  TrashAlert — Denver CO Data Import (v2 Expanded)')
  console.log('====================================================')

  const { count: existing } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'denver')

  console.log(`📊 Existing Denver records: ${existing || 0}`)

  // Delete old zone-based records if they exist (they were synthetic)
  if (existing && existing > 0 && existing < 20000) {
    console.log('🧹 Deleting old zone-based records (synthetic addresses)...')
    await supabase.from('schedule_reports').delete().eq('city', 'denver')
    console.log('   Done.')
  }

  if (existing && existing > 200000) {
    console.log('⚠️  Already imported. Skipping.')
    process.exit(0)
  }

  // Load waste zone polygons
  console.log('\n📍 Loading waste zone polygons...')
  const zones = loadZones('data/denver-waste-zones.geojson')
  console.log(`   ${zones.length} valid zones loaded`)

  const reporterHash = crypto.createHash('sha256').update('city_api_denver_co').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let noZoneCount = 0
  let batchBuffer = []
  const seen = new Set()

  console.log('\n📥 Fetching Denver addresses...\n')

  while (true) {
    const { features, exceeded } = await fetchAddressPage(offset)
    if (features.length === 0) break

    totalFetched += features.length

    for (const f of features) {
      const a = f.attributes
      const address = (a.FULL_ADDRESS || '').toLowerCase().replace(/\s+/g, ' ').trim()
      if (!address || address.length < 3) { totalSkipped++; continue }

      if (seen.has(address)) { totalSkipped++; continue }
      seen.add(address)

      const lat = a.LATITUDE
      const lng = a.LONGITUDE
      if (!lat || !lng) { totalSkipped++; continue }

      // Spatial join
      const zoneProps = findZone(lng, lat, zones)
      if (!zoneProps) { noZoneCount++; totalSkipped++; continue }

      const trashDay = DAY_MAP[zoneProps.TRASH_DAY]
      if (!trashDay) { totalSkipped++; continue }

      const recycleWeek = RECYCLE_WEEK_MAP[zoneProps.RECYCLE_DAY] || 'A'
      const zip = String(a.ZIPCODE || '').substring(0, 5)

      batchBuffer.push({
        address,
        city: 'denver',
        state: 'CO',
        zip_code: (zip && zip !== '0') ? zip : '',
        neighborhood: 'Denver',
        collection_day: trashDay,
        recycling_week: recycleWeek,
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler: 'Denver Solid Waste Management',
        data_source_url: 'https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/GIS_INF_SUBADDRESS/FeatureServer/1',
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
    }

    offset += PAGE_SIZE
    if (totalFetched % 10000 === 0) {
      process.stdout.write(`  📊 Fetched: ${totalFetched} | Imported: ${totalImported} | Skipped: ${totalSkipped} (${noZoneCount} no zone) | Errors: ${totalErrors}    \r`)
    }

    if (features.length < PAGE_SIZE && !exceeded) break
    await new Promise(r => setTimeout(r, 200))
  }

  if (batchBuffer.length > 0) {
    const result = await importBatch(batchBuffer)
    if (result.ok) totalImported += batchBuffer.length
    else totalErrors += batchBuffer.length
  }

  console.log(`\n\n====================================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Fetched:  ${totalFetched}`)
  console.log(`   Imported: ${totalImported}`)
  console.log(`   Skipped:  ${totalSkipped} (${noZoneCount} outside zones)`)
  console.log(`   Errors:   ${totalErrors}`)

  const { count: c } = await supabase.from('schedule_reports').select('*', { count: 'exact', head: true }).eq('city', 'denver')
  const { count: t } = await supabase.from('schedule_reports').select('*', { count: 'exact', head: true })
  console.log(`\n📊 Final: Denver=${c}, Total=${t}`)
}

main().catch(err => { console.error('\nFatal:', err); process.exit(1) })
