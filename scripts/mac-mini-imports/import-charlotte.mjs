#!/usr/bin/env node
/**
 * Import Charlotte NC waste collection zone data
 *
 * Source: Solid Waste Collection zones (ArcGIS FeatureServer)
 * https://services.arcgis.com/9Nl857LBlQVyzq54/arcgis/rest/services/Solid_Waste_Collection/FeatureServer/0
 *
 * Fields: ROUTE_TYPE (GARB/RECY/YARD), WORK_DAY (MON/TUE/WED/THU/FRI),
 *         SERVED_BY (hauler name), ROUTE_NAME, UNIT_COUNT
 *
 * ~848 zones total across GARB, RECY, and YARD route types.
 * Imports each route type as separate schedule_reports records.
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing env vars. Run with: node --env-file=.env.local scripts/mac-mini-imports/import-charlotte.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://services.arcgis.com/9Nl857LBlQVyzq54/arcgis/rest/services/Solid_Waste_Collection/FeatureServer/0/query'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

const ROUTE_TYPES = ['GARB', 'RECY', 'YARD']

const DAY_MAP = {
  'MON': 'monday',
  'TUE': 'tuesday',
  'WED': 'wednesday',
  'THU': 'thursday',
  'FRI': 'friday',
}

function normalizeDay(workDay) {
  if (!workDay) return null
  return DAY_MAP[workDay.toUpperCase().trim()] || null
}

async function fetchPage(routeType, offset) {
  const params = new URLSearchParams({
    where: `ROUTE_TYPE='${routeType}'`,
    outFields: 'ROUTE_TYPE,WORK_DAY,SERVED_BY,ROUTE_NAME,UNIT_COUNT',
    returnGeometry: 'false',
    resultOffset: String(offset),
    resultRecordCount: String(PAGE_SIZE),
    orderByFields: 'OBJECTID ASC',
    f: 'json',
  })

  const url = `${BASE_URL}?${params}`
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

async function importRouteType(routeType, reporterHash, now) {
  const label = routeType === 'GARB' ? 'Garbage' : routeType === 'RECY' ? 'Recycling' : 'Yard Waste'
  console.log(`\n📥 Fetching ${label} routes (ROUTE_TYPE='${routeType}')...\n`)

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let batchBuffer = []
  const seen = new Set()

  while (true) {
    const features = await fetchPage(routeType, offset)
    if (features.length === 0) break

    totalFetched += features.length

    for (const feature of features) {
      const a = feature.attributes

      const routeName = (a.ROUTE_NAME || '').trim()
      const routeTypeLower = (a.ROUTE_TYPE || routeType).toLowerCase()

      if (!routeName) { totalSkipped++; continue }

      const address = `charlotte ${routeTypeLower} route ${routeName}`.toLowerCase().replace(/\s+/g, ' ').trim()

      // Dedup within this run
      if (seen.has(address)) { totalSkipped++; continue }
      seen.add(address)

      const collectionDay = normalizeDay(a.WORK_DAY)
      if (!collectionDay) { totalSkipped++; continue }

      const hauler = (a.SERVED_BY || '').trim() || 'Charlotte Solid Waste Services'

      batchBuffer.push({
        address,
        city: 'charlotte',
        state: 'NC',
        zip_code: '',
        neighborhood: 'Charlotte',
        collection_day: collectionDay,
        recycling_week: 'A',
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler,
        data_source_url: 'https://services.arcgis.com/9Nl857LBlQVyzq54/arcgis/rest/services/Solid_Waste_Collection/FeatureServer/0',
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

    process.stdout.write(`  📊 [${label}] Fetched: ${totalFetched} | Imported: ${totalImported} | Skipped: ${totalSkipped} | Errors: ${totalErrors}    \r`)

    offset += PAGE_SIZE

    // If we got fewer than PAGE_SIZE, we're done
    if (features.length < PAGE_SIZE) break

    // Polite delay between pages
    await new Promise(r => setTimeout(r, 200))
  }

  // Flush remaining
  if (batchBuffer.length > 0) {
    const result = await importBatch(batchBuffer)
    if (result.ok) totalImported += batchBuffer.length
    else totalErrors += batchBuffer.length
  }

  console.log(`\n  ✅ ${label}: Fetched ${totalFetched}, Imported ${totalImported}, Skipped ${totalSkipped}, Errors ${totalErrors}`)

  return { totalFetched, totalImported, totalSkipped, totalErrors }
}

async function main() {
  console.log('🗑️  TrashAlert — Charlotte NC Data Import')
  console.log('==========================================')
  console.log('Source: Solid Waste Collection (ArcGIS FeatureServer)')
  console.log(`Route types: ${ROUTE_TYPES.join(', ')}\n`)

  // Check existing Charlotte records
  const { count: existing } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'charlotte')

  console.log(`📊 Existing Charlotte records: ${existing || 0}`)

  if (existing && existing > 200) {
    console.log('⚠️  Charlotte data already imported (>200 records). Skipping.')
    console.log('   To re-import, delete Charlotte records first.')
    process.exit(0)
  }

  const reporterHash = crypto.createHash('sha256').update('city_api_charlotte_nc').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let grandFetched = 0
  let grandImported = 0
  let grandSkipped = 0
  let grandErrors = 0

  // Import all route types: GARB first, then RECY, then YARD
  for (const routeType of ROUTE_TYPES) {
    const counts = await importRouteType(routeType, reporterHash, now)
    grandFetched += counts.totalFetched
    grandImported += counts.totalImported
    grandSkipped += counts.totalSkipped
    grandErrors += counts.totalErrors
  }

  console.log(`\n\n==========================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Fetched:  ${grandFetched}`)
  console.log(`   Imported: ${grandImported}`)
  console.log(`   Skipped:  ${grandSkipped}`)
  console.log(`   Errors:   ${grandErrors}`)

  // Verify final counts
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
