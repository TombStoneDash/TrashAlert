#!/usr/bin/env node
/**
 * Import Seattle WA waste collection schedules from Seattle City GIS ArcGIS
 *
 * Source: Residential Garbage Routes FeatureServer
 * https://services.arcgis.com/ZOyb2t4B0UYuYNYH/arcgis/rest/services/Residential_Garbage_Routes/FeatureServer/0
 *
 * Also available:
 * - Recycle Routes: .../Residential_Recycle_Routes/FeatureServer/0
 * - Yard Waste Routes: .../Residential_Food_and_Yard_Waste_Routes/FeatureServer/3
 *
 * Fields used:
 * - PCKUP_DAY: pickup day (MON, TUE, WED, THU, FRI)
 * - CONTRACTOR: hauler code (RECOLOGY, WM)
 * - CNTR_DESC: full contractor name (e.g., "RECOLOGY CLEANSCAPES")
 * - ZONE: zone code (G1, G2, etc.)
 * - ROUTE_ID: route identifier
 *
 * Data type: Route zone polygons with pickup day and contractor
 * Approach: Query garbage route zones, compute centroids, import zone-level records
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing SUPABASE_URL or SUPABASE_SERVICE_KEY')
  console.error('Run with: node --env-file=.env.local scripts/import-seattle.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const GARBAGE_URL = 'https://services.arcgis.com/ZOyb2t4B0UYuYNYH/arcgis/rest/services/Residential_Garbage_Routes/FeatureServer/0/query'
const RECYCLE_URL = 'https://services.arcgis.com/ZOyb2t4B0UYuYNYH/arcgis/rest/services/Residential_Recycle_Routes/FeatureServer/0/query'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

function normalizeDay(raw) {
  if (!raw) return null
  const dayMap = {
    'MON': 'monday', 'TUE': 'tuesday', 'WED': 'wednesday',
    'THU': 'thursday', 'FRI': 'friday', 'SAT': 'saturday',
    'MONDAY': 'monday', 'TUESDAY': 'tuesday', 'WEDNESDAY': 'wednesday',
    'THURSDAY': 'thursday', 'FRIDAY': 'friday', 'SATURDAY': 'saturday',
  }
  return dayMap[raw.trim().toUpperCase()] || raw.toLowerCase().trim()
}

function normalizeContractor(code, desc) {
  if (desc) return desc
  if (code === 'RECOLOGY') return 'Recology Cleanscapes'
  if (code === 'WM') return 'Waste Management'
  return code || 'Seattle Public Utilities'
}

function computeCentroid(rings) {
  if (!rings || !rings[0] || rings[0].length === 0) return null
  const ring = rings[0]
  let sumX = 0, sumY = 0, count = 0
  for (const [x, y] of ring) {
    sumX += x
    sumY += y
    count++
  }
  if (count === 0) return null
  return { lng: sumX / count, lat: sumY / count }
}

async function fetchPage(baseUrl, offset) {
  const params = new URLSearchParams({
    where: '1=1',
    outFields: '*',
    outSR: '4326',
    returnGeometry: 'true',
    resultOffset: String(offset),
    resultRecordCount: String(PAGE_SIZE),
    orderByFields: 'OBJECTID ASC',
    f: 'json'
  })

  const url = `${baseUrl}?${params}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`)

  const data = await res.json()
  if (data.error) throw new Error(`ArcGIS error: ${data.error.message}`)

  return data.features || []
}

async function fetchAllFeatures(baseUrl, label) {
  const all = []
  let offset = 0
  console.log(`📍 Fetching ${label}...`)

  while (true) {
    const features = await fetchPage(baseUrl, offset)
    if (features.length === 0) break
    all.push(...features)
    console.log(`   Fetched ${all.length} ${label} zones...`)
    if (features.length < PAGE_SIZE) break
    offset += PAGE_SIZE
    await new Promise(r => setTimeout(r, 200))
  }

  return all
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
  console.log('🗑️  TrashAlert — Seattle WA Data Import')
  console.log('========================================')
  console.log('Source: Seattle City GIS Residential Garbage/Recycle Routes')
  console.log('')

  const { count: existingCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'seattle')

  console.log(`📊 Existing Seattle records: ${existingCount || 0}`)

  // Fetch garbage routes
  const garbageRoutes = await fetchAllFeatures(GARBAGE_URL, 'garbage routes')

  // Fetch recycle routes
  const recycleRoutes = await fetchAllFeatures(RECYCLE_URL, 'recycle routes')

  // Log distribution
  const dayDist = {}
  const contractorDist = {}
  for (const r of garbageRoutes) {
    const d = normalizeDay(r.attributes.PCKUP_DAY) || 'unknown'
    const c = r.attributes.CONTRACTOR || 'unknown'
    dayDist[d] = (dayDist[d] || 0) + 1
    contractorDist[c] = (contractorDist[c] || 0) + 1
  }
  console.log('\n   Garbage day distribution:', dayDist)
  console.log('   Contractor distribution:', contractorDist)

  // Build recycle day lookup by zone
  const recycleByZone = {}
  for (const r of recycleRoutes) {
    const zone = r.attributes.ZONE
    if (zone) {
      recycleByZone[zone] = normalizeDay(r.attributes.PCKUP_DAY)
    }
  }

  const reporterHash = crypto.createHash('sha256').update('city_api_seattle_wa').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let batchBuffer = []
  const seen = new Set()

  console.log(`\n📥 Processing ${garbageRoutes.length} garbage route zones...\n`)

  for (const feature of garbageRoutes) {
    const a = feature.attributes
    const geom = feature.geometry

    const pickupDay = normalizeDay(a.PCKUP_DAY)
    if (!pickupDay) { totalSkipped++; continue }

    const centroid = computeCentroid(geom?.rings)
    if (!centroid) { totalSkipped++; continue }

    const zone = (a.ZONE || '').trim()
    const routeId = (a.ROUTE_ID || '').trim()
    const subzone = (a.SUBZONE || '').trim()

    // Build unique address from zone + route
    const address = `seattle garbage zone ${zone} route ${routeId}`.toLowerCase()
    if (seen.has(address)) { totalSkipped++; continue }
    seen.add(address)

    const hauler = normalizeContractor(a.CONTRACTOR, a.CNTR_DESC)

    // Cross-reference recycle day from the same zone prefix
    // Garbage zones are G1, G2, etc. Recycle zones are R1, R2, etc.
    // Match by zone number
    const zoneNum = zone.replace(/^[A-Z]+/, '')
    const recycleZoneKey = `R${zoneNum}`
    const recycleDay = recycleByZone[recycleZoneKey]

    batchBuffer.push({
      address,
      city: 'seattle',
      state: 'WA',
      zip_code: '',
      neighborhood: `Zone ${zone}${subzone ? '-' + subzone : ''}`,
      collection_day: pickupDay,
      recycling_week: 'A', // Seattle has every-other-week recycling
      reporter_hash: reporterHash,
      verified: true,
      verification_count: 1,
      source: 'city_api',
      fetched_at: now,
      raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
      hauler,
      data_source_url: 'https://services.arcgis.com/ZOyb2t4B0UYuYNYH/arcgis/rest/services/Residential_Garbage_Routes/FeatureServer/0',
      data_source_type: 'gis',
      lat: centroid.lat,
      lng: centroid.lng,
    })

    if (batchBuffer.length >= BATCH_SIZE) {
      const result = await importBatch(batchBuffer)
      if (result.ok) totalImported += batchBuffer.length
      else {
        totalErrors += batchBuffer.length
        if (totalErrors <= 2500) console.error(`  ⚠️  Batch error: ${result.error}`)
      }
      batchBuffer = []
      await new Promise(r => setTimeout(r, 50))
    }
  }

  // Flush remaining
  if (batchBuffer.length > 0) {
    const result = await importBatch(batchBuffer)
    if (result.ok) totalImported += batchBuffer.length
    else totalErrors += batchBuffer.length
  }

  console.log(`========================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Garbage routes: ${garbageRoutes.length}`)
  console.log(`   Recycle routes: ${recycleRoutes.length} (used for cross-reference)`)
  console.log(`   Imported: ${totalImported}`)
  console.log(`   Skipped:  ${totalSkipped}`)
  console.log(`   Errors:   ${totalErrors}`)

  const { count: seattleCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'seattle')

  const { count: totalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\n📊 Final counts:`)
  console.log(`   Seattle: ${seattleCount}`)
  console.log(`   Total DB: ${totalCount}`)
}

main().catch(err => {
  console.error('\nFatal error:', err)
  process.exit(1)
})
