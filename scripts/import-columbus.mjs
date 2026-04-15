#!/usr/bin/env node
/**
 * Import Columbus OH waste collection schedules from City of Columbus ArcGIS
 *
 * Source: Applications/Neighborhood MapServer — Refuse Colordays (Layer 24)
 * https://maps2.columbus.gov/arcgis/rest/services/Applications/Neighborhood/MapServer/24
 *
 * Columbus uses a "color day" system where zones are assigned colors or day names:
 * - Direct day codes: MON, TUE, WED, THU, FRI
 * - Color codes: GOLD, GRAY, NAVY, PINK, RUBY (each maps to a specific weekday)
 * - DAILY: daily collection areas (commercial/downtown)
 *
 * Data type: Zone polygons (no address-level data)
 * Approach: Query zone polygons, compute centroids, import zone-level records
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing SUPABASE_URL or SUPABASE_SERVICE_KEY')
  console.error('Run with: node --env-file=.env.local scripts/import-columbus.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://maps2.columbus.gov/arcgis/rest/services/Applications/Neighborhood/MapServer/24/query'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

// Columbus color-to-day mapping
// Source: City of Columbus Refuse Collection
const COLOR_DAY_MAP = {
  'MON': 'monday',
  'TUE': 'tuesday',
  'WED': 'wednesday',
  'THU': 'thursday',
  'FRI': 'friday',
  'MONDAY': 'monday',
  'TUESDAY': 'tuesday',
  'WEDNESDAY': 'wednesday',
  'THURSDAY': 'thursday',
  'FRIDAY': 'friday',
  'DAILY': 'daily',
  // Color codes — these rotate and may change; map to most common assignment
  'GOLD': 'monday',
  'GRAY': 'tuesday',
  'NAVY': 'wednesday',
  'PINK': 'thursday',
  'RUBY': 'friday',
}

function normalizeDay(unitName) {
  if (!unitName) return null
  const key = unitName.trim().toUpperCase()
  return COLOR_DAY_MAP[key] || null
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
    outFields: 'UNIT_NAME',
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
  console.log('🗑️  TrashAlert — Columbus OH Data Import')
  console.log('=========================================')
  console.log('Source: City of Columbus Refuse Colordays (zone polygons)')
  console.log('')

  const { count: existingCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'columbus')

  console.log(`📊 Existing Columbus records: ${existingCount || 0}`)

  const reporterHash = crypto.createHash('sha256').update('city_api_columbus_oh').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let batchBuffer = []
  const seen = new Set()

  console.log(`\n📥 Fetching Columbus refuse zones (${PAGE_SIZE} per page)...\n`)

  while (true) {
    const features = await fetchPage(offset)
    if (features.length === 0) break

    totalFetched += features.length

    for (const feature of features) {
      const a = feature.attributes
      const geom = feature.geometry

      const unitName = (a.UNIT_NAME || '').trim()
      if (!unitName) { totalSkipped++; continue }

      const collectionDay = normalizeDay(unitName)
      if (!collectionDay) { totalSkipped++; continue }

      // Compute centroid from polygon rings
      const centroid = computeCentroid(geom?.rings)
      if (!centroid) { totalSkipped++; continue }

      // Build a unique address identifier from the zone
      const zoneId = `zone-${unitName.toLowerCase()}-${a.OBJECTID || totalFetched}`
      const address = `columbus refuse zone ${unitName.toLowerCase()} #${a.OBJECTID || totalFetched}`

      if (seen.has(zoneId)) { totalSkipped++; continue }
      seen.add(zoneId)

      batchBuffer.push({
        address,
        city: 'columbus',
        state: 'OH',
        zip_code: '',
        neighborhood: `Zone ${unitName}`,
        collection_day: collectionDay,
        recycling_week: 'A',
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler: 'City of Columbus Division of Refuse Collection',
        data_source_url: 'https://maps2.columbus.gov/arcgis/rest/services/Applications/Neighborhood/MapServer/24',
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

  console.log(`\n\n=========================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Fetched:  ${totalFetched} zone polygons`)
  console.log(`   Imported: ${totalImported}`)
  console.log(`   Skipped:  ${totalSkipped}`)
  console.log(`   Errors:   ${totalErrors}`)

  const { count: columbusCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'columbus')

  const { count: totalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\n📊 Final counts:`)
  console.log(`   Columbus: ${columbusCount}`)
  console.log(`   Total DB: ${totalCount}`)
}

main().catch(err => {
  console.error('\nFatal error:', err)
  process.exit(1)
})
