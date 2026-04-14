#!/usr/bin/env node
/**
 * Import Philadelphia PA waste collection schedules
 *
 * Strategy:
 * 1. Load 67 rubbish collection zone polygons (collday + secondary_rubbish_day)
 * 2. Fetch ~583K property records from OPA with coordinates
 * 3. Point-in-polygon to assign each address its collection days
 * 4. Philly has TWICE-WEEKLY rubbish collection — collday is primary, secondary_rubbish_day is the second day
 *
 * Sources:
 * - Zones: https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/Rubbish_Recyc_Coll_Bnd/FeatureServer/0
 * - Addresses: https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/opa_properties_public/FeatureServer/0
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'
import { readFileSync } from 'fs'
import booleanPointInPolygon from '@turf/boolean-point-in-polygon'
import { point } from '@turf/helpers'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing env vars. Run with: node --env-file=.env.local scripts/import-philadelphia.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const ADDR_URL = 'https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/opa_properties_public/FeatureServer/0/query'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

const DAY_MAP = {
  'MON': 'monday', 'TUE': 'tuesday', 'WED': 'wednesday', 'THU': 'thursday', 'FRI': 'friday',
  'MONDAY': 'monday', 'TUESDAY': 'tuesday', 'WEDNESDAY': 'wednesday', 'THURSDAY': 'thursday', 'FRIDAY': 'friday',
}

function loadZones(filepath) {
  const raw = readFileSync(filepath, 'utf8')
  const geojson = JSON.parse(raw)
  return geojson.features.filter(f => f.geometry && f.properties.collday && f.properties.collday.trim())
}

function findZone(lng, lat, zones) {
  const pt = point([lng, lat])
  for (const zone of zones) {
    try {
      if (booleanPointInPolygon(pt, zone)) return zone.properties
    } catch { /* skip */ }
  }
  return null
}

async function fetchPage(offset) {
  const params = new URLSearchParams({
    where: '1=1',
    outFields: 'location,zip_code',
    outSR: '4326',
    returnGeometry: 'true',
    geometryPrecision: 6,
    resultOffset: String(offset),
    resultRecordCount: String(PAGE_SIZE),
    orderByFields: 'OBJECTID ASC',
    f: 'json'
  })

  const res = await fetch(`${ADDR_URL}?${params}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  if (data.error) throw new Error(data.error.message)
  return data.features || []
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
  console.log('🗑️  TrashAlert — Philadelphia PA Data Import')
  console.log('=============================================')

  const { count: existing } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'philadelphia')

  console.log(`📊 Existing Philadelphia records: ${existing || 0}`)
  if (existing && existing > 400000) {
    console.log('⚠️  Already imported. Skipping.')
    process.exit(0)
  }

  console.log('\n📍 Loading rubbish zone polygons...')
  const zones = loadZones('data/philly-rubbish-zones.geojson')
  console.log(`   ${zones.length} zones loaded`)

  const reporterHash = crypto.createHash('sha256').update('city_api_philadelphia_pa').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let noZoneCount = 0
  let batchBuffer = []
  const seen = new Set()

  console.log('\n📥 Fetching Philadelphia properties...\n')

  while (true) {
    const features = await fetchPage(offset)
    if (features.length === 0) break

    totalFetched += features.length

    for (const f of features) {
      const a = f.attributes
      const geom = f.geometry

      const address = (a.location || '').toLowerCase().replace(/\s+/g, ' ').trim()
      if (!address || address.length < 3) { totalSkipped++; continue }

      if (seen.has(address)) { totalSkipped++; continue }
      seen.add(address)

      if (!geom || !geom.x || !geom.y) { totalSkipped++; continue }
      const lng = geom.x
      const lat = geom.y

      const zoneProps = findZone(lng, lat, zones)
      if (!zoneProps) { noZoneCount++; totalSkipped++; continue }

      const primaryDay = DAY_MAP[zoneProps.collday.trim()]
      if (!primaryDay) { totalSkipped++; continue }

      const zip = String(a.zip_code || '').substring(0, 5)

      batchBuffer.push({
        address,
        city: 'philadelphia',
        state: 'PA',
        zip_code: zip || '',
        neighborhood: 'Philadelphia',
        collection_day: primaryDay,
        recycling_week: 'A',
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler: 'Philadelphia Streets Department',
        data_source_url: 'https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/opa_properties_public/FeatureServer/0',
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

    if (features.length < PAGE_SIZE) break
    await new Promise(r => setTimeout(r, 200))
  }

  if (batchBuffer.length > 0) {
    const result = await importBatch(batchBuffer)
    if (result.ok) totalImported += batchBuffer.length
    else totalErrors += batchBuffer.length
  }

  console.log(`\n\n=============================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Fetched:  ${totalFetched}`)
  console.log(`   Imported: ${totalImported}`)
  console.log(`   Skipped:  ${totalSkipped} (${noZoneCount} outside zones)`)
  console.log(`   Errors:   ${totalErrors}`)

  const { count: c } = await supabase.from('schedule_reports').select('*', { count: 'exact', head: true }).eq('city', 'philadelphia')
  const { count: t } = await supabase.from('schedule_reports').select('*', { count: 'exact', head: true })
  console.log(`\n📊 Final: Philadelphia=${c}, Total=${t}`)
}

main().catch(err => { console.error('\nFatal:', err); process.exit(1) })
