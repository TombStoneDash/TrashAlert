#!/usr/bin/env node
/**
 * Import Fort Worth TX waste collection schedules from City of Fort Worth ArcGIS
 *
 * Source: CodeComp/SolidWaste MapServer
 * https://mapitwest.fortworthtexas.gov/ags/rest/services/CodeComp/SolidWaste/MapServer
 *
 * Strategy:
 * 1. Fetch garbage route zone polygons from Layer 3 (Garbage Route) with Weekday field
 * 2. Fetch address parcels from Layer 0 (Solid Waste View) with StreetAddress field
 * 3. Use parcel centroid + zone polygon spatial matching to assign collection days
 * 4. Batch import to Supabase
 *
 * Layer 3 fields: Route (number), Contractor (WM), Weekday (MON/TUE/etc.)
 * Layer 0 fields: StreetAddress, CFWLAND_ID
 *
 * Note: Layer 0 has parcel polygons with addresses but no collection day.
 *       Layer 3 has route polygons with collection day but no addresses.
 *       We combine both via spatial intersection.
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing SUPABASE_URL or SUPABASE_SERVICE_KEY')
  console.error('Run with: node --env-file=.env.local scripts/import-fort-worth.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const SW_BASE = 'https://mapitwest.fortworthtexas.gov/ags/rest/services/CodeComp/SolidWaste/MapServer'
const ROUTE_LAYER = 3   // Garbage Route — has Weekday
const ADDR_LAYER = 0    // Solid Waste View — has StreetAddress
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

function normalizeAddress(addr) {
  if (!addr) return null
  return addr.toLowerCase().replace(/\s+/g, ' ').trim()
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
  return { x: sumX / count, y: sumY / count }
}

function pointInPolygon(px, py, rings) {
  if (!rings || !rings[0]) return false
  const ring = rings[0]
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0], yi = ring[i][1]
    const xj = ring[j][0], yj = ring[j][1]
    if (((yi > py) !== (yj > py)) && (px < (xj - xi) * (py - yi) / (yj - yi) + xi)) {
      inside = !inside
    }
  }
  return inside
}

async function fetchArcGIS(layer, { where = '1=1', outFields = '*', returnGeometry = true, offset = 0 } = {}) {
  const params = new URLSearchParams({
    where,
    outFields,
    outSR: '4326',
    returnGeometry: String(returnGeometry),
    resultOffset: String(offset),
    resultRecordCount: String(PAGE_SIZE),
    orderByFields: 'OBJECTID ASC',
    f: 'json'
  })

  const url = `${SW_BASE}/${layer}/query?${params}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`)

  const data = await res.json()
  if (data.error) throw new Error(`ArcGIS error: ${data.error.message}`)

  return data.features || []
}

async function fetchAllRouteZones() {
  console.log('📍 Fetching garbage route zones...')
  const zones = []
  let offset = 0

  while (true) {
    const features = await fetchArcGIS(ROUTE_LAYER, {
      outFields: 'Route,Contractor,Weekday',
      offset
    })
    if (features.length === 0) break
    zones.push(...features)
    console.log(`   Fetched ${zones.length} route zones...`)
    if (features.length < PAGE_SIZE) break
    offset += PAGE_SIZE
    await new Promise(r => setTimeout(r, 200))
  }

  console.log(`   Total route zones: ${zones.length}`)
  return zones
}

function findCollectionDay(x, y, routeZones) {
  for (const zone of routeZones) {
    if (!zone.geometry || !zone.geometry.rings) continue
    if (pointInPolygon(x, y, zone.geometry.rings)) {
      return {
        day: normalizeDay(zone.attributes.Weekday),
        contractor: zone.attributes.Contractor || 'WM',
        route: zone.attributes.Route,
      }
    }
  }
  return null
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
  console.log('🗑️  TrashAlert — Fort Worth TX Data Import')
  console.log('==========================================')
  console.log('Source: City of Fort Worth SolidWaste MapServer')
  console.log('')

  const { count: existingCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'fort-worth')

  console.log(`📊 Existing Fort Worth records: ${existingCount || 0}`)

  if (existingCount && existingCount > 200000) {
    console.log('⚠️  Fort Worth already imported. Skipping.')
    process.exit(0)
  }

  // Step 1: Fetch garbage route zone polygons (with Weekday)
  const routeZones = await fetchAllRouteZones()

  // Log day distribution
  const dayDist = {}
  for (const z of routeZones) {
    const d = normalizeDay(z.attributes.Weekday) || 'unknown'
    dayDist[d] = (dayDist[d] || 0) + 1
  }
  console.log('   Day distribution:', dayDist)

  // Step 2: Fetch address parcels and spatial join with route zones
  const reporterHash = crypto.createHash('sha256').update('city_api_fort_worth_tx').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let noZoneCount = 0
  let batchBuffer = []
  const seen = new Set()

  console.log(`\n📥 Fetching Fort Worth address parcels...\n`)

  while (true) {
    const features = await fetchArcGIS(ADDR_LAYER, {
      outFields: 'StreetAddress,CFWLAND_ID',
      offset
    })
    if (features.length === 0) break

    totalFetched += features.length

    for (const feature of features) {
      const a = feature.attributes
      const geom = feature.geometry

      const address = normalizeAddress(a.StreetAddress)
      if (!address || address.length < 3) { totalSkipped++; continue }

      if (seen.has(address)) { totalSkipped++; continue }
      seen.add(address)

      // Compute centroid of parcel polygon
      const centroid = computeCentroid(geom?.rings)
      if (!centroid) { totalSkipped++; continue }

      // Spatial join: find which garbage route zone this parcel falls in
      const match = findCollectionDay(centroid.x, centroid.y, routeZones)
      if (!match || !match.day) { noZoneCount++; totalSkipped++; continue }

      const haulerName = match.contractor === 'WM'
        ? 'Waste Management (Fort Worth)'
        : `${match.contractor} (Fort Worth)`

      batchBuffer.push({
        address,
        city: 'fort-worth',
        state: 'TX',
        zip_code: '',
        neighborhood: `Route ${match.route || 'Unknown'}`,
        collection_day: match.day,
        recycling_week: 'A',
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler: haulerName,
        data_source_url: `${SW_BASE}/${ADDR_LAYER}`,
        data_source_type: 'gis',
        lat: centroid.y,
        lng: centroid.x,
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

    process.stdout.write(`  📊 Fetched: ${totalFetched} | Imported: ${totalImported} | Skipped: ${totalSkipped} (${noZoneCount} no zone) | Errors: ${totalErrors}    \r`)

    offset += PAGE_SIZE
    if (features.length < PAGE_SIZE) break
    await new Promise(r => setTimeout(r, 200))
  }

  // Flush remaining
  if (batchBuffer.length > 0) {
    const result = await importBatch(batchBuffer)
    if (result.ok) totalImported += batchBuffer.length
    else totalErrors += batchBuffer.length
  }

  console.log(`\n\n==========================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Fetched:  ${totalFetched} parcels`)
  console.log(`   Imported: ${totalImported}`)
  console.log(`   Skipped:  ${totalSkipped} (${noZoneCount} outside zones)`)
  console.log(`   Errors:   ${totalErrors}`)

  const { count: fwCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'fort-worth')

  const { count: totalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\n📊 Final counts:`)
  console.log(`   Fort Worth: ${fwCount}`)
  console.log(`   Total DB:   ${totalCount}`)
}

main().catch(err => {
  console.error('\nFatal error:', err)
  process.exit(1)
})
