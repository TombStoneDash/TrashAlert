#!/usr/bin/env node
/**
 * Import Charlotte NC waste collection schedules from City of Charlotte ArcGIS
 *
 * Source: Solid Waste Collection FeatureServer
 * https://services.arcgis.com/9Nl857LBlQVyzq54/arcgis/rest/services/Solid_Waste_Collection/FeatureServer/0
 *
 * Fields used:
 * - WORK_DAY: collection day (MON, TUE, WED, THU, FRI)
 * - ROUTE_TYPE: service type (GARB=garbage, RECY=recycling, YARD=yard waste)
 * - SERVED_BY: hauler name (e.g., "WASTE MANAGEMENT")
 * - ROUTE_NAME: route identifier (e.g., "4R13R")
 * - ROUTE_NOTE: description (e.g., "THU Collection for Recycling on ORANGE week")
 * - WORK_ZONE: zone category
 * - UNIT_COUNT: number of units served by route
 *
 * Data type: Route zone polygons by service type
 * Approach: Filter GARB routes, compute centroids, import zone-level records.
 *           Also extract recycling week from ROUTE_NOTE when available.
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing SUPABASE_URL or SUPABASE_SERVICE_KEY')
  console.error('Run with: node --env-file=.env.local scripts/import-charlotte.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://services.arcgis.com/9Nl857LBlQVyzq54/arcgis/rest/services/Solid_Waste_Collection/FeatureServer/0/query'
const FIELDS = 'WORK_DAY,ROUTE_TYPE,SERVED_BY,ROUTE_NAME,ROUTE_NOTE,WORK_ZONE,UNIT_COUNT'
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

function parseRecyclingWeek(routeNote) {
  // "THU Collection for Recycling on ORANGE week" → "A" or "B"
  if (!routeNote) return 'A'
  const note = routeNote.toUpperCase()
  if (note.includes('BLUE')) return 'A'
  if (note.includes('ORANGE')) return 'B'
  return 'A'
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

async function fetchPage(offset) {
  const params = new URLSearchParams({
    where: '1=1',
    outFields: FIELDS,
    outSR: '4326',
    returnGeometry: 'true',
    resultOffset: String(offset),
    resultRecordCount: String(PAGE_SIZE),
    orderByFields: 'OBJECTID ASC',
    f: 'json'
  })

  const url = `${BASE_URL}?${params}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`)

  const data = await res.json()
  if (data.error) throw new Error(`ArcGIS error: ${data.error.message}`)

  return data.features || []
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
  console.log('🗑️  TrashAlert — Charlotte NC Data Import')
  console.log('==========================================')
  console.log('Source: City of Charlotte Solid Waste Collection FeatureServer')
  console.log('')

  const { count: existingCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'charlotte')

  console.log(`📊 Existing Charlotte records: ${existingCount || 0}`)

  const reporterHash = crypto.createHash('sha256').update('city_api_charlotte_nc').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let garbageCount = 0
  let recycleCount = 0
  let yardCount = 0
  let batchBuffer = []
  const seen = new Set()

  console.log(`\n📥 Fetching Charlotte collection routes (${PAGE_SIZE} per page)...\n`)

  while (true) {
    const features = await fetchPage(offset)
    if (features.length === 0) break

    totalFetched += features.length

    for (const feature of features) {
      const a = feature.attributes
      const geom = feature.geometry

      const routeType = (a.ROUTE_TYPE || '').toUpperCase()
      const workDay = normalizeDay(a.WORK_DAY)
      if (!workDay) { totalSkipped++; continue }

      // Track service type distribution
      if (routeType === 'GARB') garbageCount++
      else if (routeType === 'RECY') recycleCount++
      else if (routeType === 'YARD') yardCount++

      // Compute centroid from polygon
      const centroid = computeCentroid(geom?.rings)
      if (!centroid) { totalSkipped++; continue }

      // Build unique address from route info
      const routeName = (a.ROUTE_NAME || `${routeType}-${a.OBJECTID}`).toLowerCase()
      const serviceLabel = routeType === 'GARB' ? 'garbage' : routeType === 'RECY' ? 'recycling' : 'yard-waste'
      const address = `charlotte ${serviceLabel} route ${routeName}`

      if (seen.has(address)) { totalSkipped++; continue }
      seen.add(address)

      const recyclingWeek = routeType === 'RECY' ? parseRecyclingWeek(a.ROUTE_NOTE) : 'A'
      const hauler = a.SERVED_BY || 'City of Charlotte Solid Waste Services'

      batchBuffer.push({
        address,
        city: 'charlotte',
        state: 'NC',
        zip_code: '',
        neighborhood: a.WORK_ZONE || `Route ${routeName}`,
        collection_day: workDay,
        recycling_week: recyclingWeek,
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler,
        data_source_url: 'https://services.arcgis.com/9Nl857LBlQVyzq54/arcgis/rest/services/Solid_Waste_Collection/FeatureServer/0',
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

    process.stdout.write(`  📊 Fetched: ${totalFetched} | Imported: ${totalImported} | Skipped: ${totalSkipped} | Errors: ${totalErrors}    \r`)

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
  console.log(`   Fetched:  ${totalFetched} route zones`)
  console.log(`   Imported: ${totalImported}`)
  console.log(`   Skipped:  ${totalSkipped}`)
  console.log(`   Errors:   ${totalErrors}`)
  console.log(`   By type:  ${garbageCount} garbage, ${recycleCount} recycling, ${yardCount} yard waste`)

  const { count: charlotteCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'charlotte')

  const { count: totalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\n📊 Final counts:`)
  console.log(`   Charlotte: ${charlotteCount}`)
  console.log(`   Total DB:  ${totalCount}`)
}

main().catch(err => {
  console.error('\nFatal error:', err)
  process.exit(1)
})
