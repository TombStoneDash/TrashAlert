#!/usr/bin/env node
/**
 * Import Miami-Dade County FL waste collection zone data
 *
 * Strategy:
 * 1. Fetch 783 garbage route polygons from GarbagePickupRoute_gdb FeatureServer
 * 2. Map COLLDAY (1-5) or WEEKDAYS string to normalized day names
 * 3. Fetch recycling zones from RecyclingZone_gdb FeatureServer
 * 4. Batch import both to Supabase
 *
 * Sources:
 * - Garbage:   https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/GarbagePickupRoute_gdb/FeatureServer/0
 * - Recycling: https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/RecyclingZone_gdb/FeatureServer/0
 *
 * Key fields (garbage): ROUTE (int), COLLDAY (smallint 1-5), WEEKDAYS (string), WCSAREA (smallint), TYPE (string)
 * Records: ~783 garbage route polygons
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing env vars. Run with: node --env-file=.env.local scripts/mac-mini-imports/import-miami.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const GARBAGE_URL = 'https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/GarbagePickupRoute_gdb/FeatureServer/0'
const RECYCLING_URL = 'https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/RecyclingZone_gdb/FeatureServer/0'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

// Map both COLLDAY numbers and WEEKDAYS strings to normalized day names
const DAY_MAP = {
  // Numeric COLLDAY values (1-5)
  '1': 'monday',
  '2': 'tuesday',
  '3': 'wednesday',
  '4': 'thursday',
  '5': 'friday',
  // String WEEKDAYS values
  'monday': 'monday',
  'tuesday': 'tuesday',
  'wednesday': 'wednesday',
  'thursday': 'thursday',
  'friday': 'friday',
  'mon': 'monday',
  'tue': 'tuesday',
  'wed': 'wednesday',
  'thu': 'thursday',
  'fri': 'friday',
  'tues': 'tuesday',
  'thurs': 'thursday',
}

function normalizeDay(collday, weekdays) {
  // Try WEEKDAYS string first (more descriptive)
  if (weekdays) {
    const key = weekdays.toLowerCase().trim()
    if (DAY_MAP[key]) return DAY_MAP[key]
  }
  // Fall back to COLLDAY number
  if (collday != null) {
    const key = String(collday)
    if (DAY_MAP[key]) return DAY_MAP[key]
  }
  return null
}

async function fetchPage(baseUrl, offset) {
  const params = new URLSearchParams({
    where: '1=1',
    outFields: '*',
    returnGeometry: 'false',
    resultOffset: String(offset),
    resultRecordCount: String(PAGE_SIZE),
    orderByFields: 'OBJECTID ASC',
    f: 'json',
  })

  const url = `${baseUrl}/query?${params}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`)

  const data = await res.json()
  if (data.error) throw new Error(`ArcGIS error: ${data.error.message}`)

  return data.features || []
}

async function importBatch(rows) {
  const { error } = await supabase
    .from('schedule_reports')
    .upsert(rows, { onConflict: 'address,city', ignoreDuplicates: true })

  if (error) {
    // Fallback to insert if upsert fails
    const { error: insertError } = await supabase
      .from('schedule_reports')
      .insert(rows)

    if (insertError) {
      return { ok: false, error: insertError.message }
    }
  }

  return { ok: true }
}

async function importGarbageRoutes(reporterHash, now) {
  console.log(`\n📥 Fetching Garbage routes (${PAGE_SIZE} per page)...\n`)

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let batchBuffer = []
  const seen = new Set()

  while (true) {
    const features = await fetchPage(GARBAGE_URL, offset)
    if (features.length === 0) break

    totalFetched += features.length

    for (const feature of features) {
      const a = feature.attributes

      const route = a.ROUTE
      const wcsarea = a.WCSAREA
      const collday = a.COLLDAY
      const weekdays = a.WEEKDAYS
      const type = a.TYPE

      if (route == null) { totalSkipped++; continue }

      const address = `miami-dade garbage route ${route} area ${wcsarea || 0}`.toLowerCase().replace(/\s+/g, ' ').trim()

      // Dedup within this run
      if (seen.has(address)) { totalSkipped++; continue }
      seen.add(address)

      const collectionDay = normalizeDay(collday, weekdays)
      if (!collectionDay) { totalSkipped++; continue }

      batchBuffer.push({
        address,
        city: 'miami',
        state: 'FL',
        zip_code: '',
        neighborhood: `Area ${wcsarea || 0}`,
        collection_day: collectionDay,
        recycling_week: 'A',
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler: 'Miami-Dade County DSWM',
        data_source_url: GARBAGE_URL,
        data_source_type: 'gis',
        lat: null,
        lng: null,
      })

      // Flush batch
      if (batchBuffer.length >= BATCH_SIZE) {
        const result = await importBatch(batchBuffer)
        if (result.ok) {
          totalImported += batchBuffer.length
        } else {
          totalErrors += batchBuffer.length
          if (totalErrors <= 2500) console.error(`  ⚠️  Batch error: ${result.error}`)
        }
        batchBuffer = []
        await new Promise(r => setTimeout(r, 50))
      }
    }

    process.stdout.write(`  📊 [Garbage] Fetched: ${totalFetched} | Imported: ${totalImported} | Skipped: ${totalSkipped} | Errors: ${totalErrors}    \r`)

    offset += PAGE_SIZE

    // If we got fewer than PAGE_SIZE, we're done
    if (features.length < PAGE_SIZE) break

    // Polite delay between pages
    await new Promise(r => setTimeout(r, 200))
  }

  // Flush remaining
  if (batchBuffer.length > 0) {
    const result = await importBatch(batchBuffer)
    if (result.ok) {
      totalImported += batchBuffer.length
    } else {
      totalErrors += batchBuffer.length
    }
  }

  console.log(`\n  ✅ Garbage: fetched=${totalFetched}, imported=${totalImported}, skipped=${totalSkipped}, errors=${totalErrors}`)

  return { totalFetched, totalImported, totalSkipped, totalErrors }
}

async function importRecyclingZones(reporterHash, now) {
  console.log(`\n📥 Fetching Recycling zones (${PAGE_SIZE} per page)...\n`)

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let batchBuffer = []
  const seen = new Set()

  while (true) {
    const features = await fetchPage(RECYCLING_URL, offset)
    if (features.length === 0) break

    totalFetched += features.length

    for (const feature of features) {
      const a = feature.attributes

      // Recycling zones may have different field names — use what's available
      const zone = a.ZONE || a.ROUTE || a.OBJECTID
      const collday = a.COLLDAY
      const weekdays = a.WEEKDAYS || a.COLLDAY_NAME || a.DAY

      if (zone == null) { totalSkipped++; continue }

      const address = `miami-dade recycling zone ${zone}`.toLowerCase().replace(/\s+/g, ' ').trim()

      // Dedup within this run
      if (seen.has(address)) { totalSkipped++; continue }
      seen.add(address)

      const collectionDay = normalizeDay(collday, weekdays)
      if (!collectionDay) { totalSkipped++; continue }

      batchBuffer.push({
        address,
        city: 'miami',
        state: 'FL',
        zip_code: '',
        neighborhood: `Recycling Zone ${zone}`,
        collection_day: collectionDay,
        recycling_week: 'A',
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler: 'Miami-Dade County DSWM',
        data_source_url: RECYCLING_URL,
        data_source_type: 'gis',
        lat: null,
        lng: null,
      })

      // Flush batch
      if (batchBuffer.length >= BATCH_SIZE) {
        const result = await importBatch(batchBuffer)
        if (result.ok) {
          totalImported += batchBuffer.length
        } else {
          totalErrors += batchBuffer.length
          if (totalErrors <= 2500) console.error(`  ⚠️  Batch error: ${result.error}`)
        }
        batchBuffer = []
        await new Promise(r => setTimeout(r, 50))
      }
    }

    process.stdout.write(`  📊 [Recycling] Fetched: ${totalFetched} | Imported: ${totalImported} | Skipped: ${totalSkipped} | Errors: ${totalErrors}    \r`)

    offset += PAGE_SIZE

    // If we got fewer than PAGE_SIZE, we're done
    if (features.length < PAGE_SIZE) break

    // Polite delay between pages
    await new Promise(r => setTimeout(r, 200))
  }

  // Flush remaining
  if (batchBuffer.length > 0) {
    const result = await importBatch(batchBuffer)
    if (result.ok) {
      totalImported += batchBuffer.length
    } else {
      totalErrors += batchBuffer.length
    }
  }

  console.log(`\n  ✅ Recycling: fetched=${totalFetched}, imported=${totalImported}, skipped=${totalSkipped}, errors=${totalErrors}`)

  return { totalFetched, totalImported, totalSkipped, totalErrors }
}

async function main() {
  console.log('🗑️  TrashAlert — Miami-Dade County FL Data Import')
  console.log('==================================================')
  console.log('Source: Miami-Dade County ArcGIS FeatureServer')
  console.log(`  Garbage:   GarbagePickupRoute_gdb (~783 routes)`)
  console.log(`  Recycling: RecyclingZone_gdb\n`)

  // Check existing Miami records
  const { count: existing } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'miami')

  console.log(`📊 Existing Miami records: ${existing || 0}`)

  if (existing && existing > 700) {
    console.log('⚠️  Miami data already imported (>700 records). Skipping.')
    console.log('   To re-import, delete Miami records first.')
    process.exit(0)
  }

  const reporterHash = crypto.createHash('sha256').update('city_api_miami_fl').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  // --- Import garbage routes ---
  const garbage = await importGarbageRoutes(reporterHash, now)

  // --- Import recycling zones ---
  const recycling = await importRecyclingZones(reporterHash, now)

  // Summary
  const grandFetched = garbage.totalFetched + recycling.totalFetched
  const grandImported = garbage.totalImported + recycling.totalImported
  const grandSkipped = garbage.totalSkipped + recycling.totalSkipped
  const grandErrors = garbage.totalErrors + recycling.totalErrors

  console.log(`\n\n==================================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Garbage routes:   ${garbage.totalFetched} fetched, ${garbage.totalImported} imported`)
  console.log(`   Recycling zones:  ${recycling.totalFetched} fetched, ${recycling.totalImported} imported`)
  console.log(`   Total fetched:    ${grandFetched}`)
  console.log(`   Total imported:   ${grandImported}`)
  console.log(`   Total skipped:    ${grandSkipped}`)
  console.log(`   Total errors:     ${grandErrors}`)

  // Verify final counts
  const { count: miamiCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'miami')

  const { count: totalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\n📊 Final counts:`)
  console.log(`   Miami:    ${miamiCount}`)
  console.log(`   Total DB: ${totalCount}`)
}

main().catch(err => {
  console.error('\nFatal error:', err)
  process.exit(1)
})
