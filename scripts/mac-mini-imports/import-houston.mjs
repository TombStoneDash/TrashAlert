#!/usr/bin/env node
/**
 * Import Houston TX waste collection schedules from City of Houston GIS
 *
 * Source: COH Address Thiessen Polygons MapServer
 * https://mycity2.houstontx.gov/pubgis01/rest/services/EGIS/COH_ADDRESS_THIESSEN_POLYGONS/MapServer/0
 *
 * Fields used:
 * - FULLADDRESS: full street address
 * - ZIPCODE: 5-digit zip
 * - SuperNeighborhood: Houston neighborhood name
 * - SWDGarbageDay: MONDAY/TUESDAY/etc.
 * - SWDRecyclingDAY: MONDAY-A/TUESDAY-B/etc. (day + biweekly rotation)
 * - SWDHeavyTrashDAY: "1st Tuesday", "3rd Thursday", etc.
 * - Latitude, Longitude: coordinates
 *
 * Total eligible: ~474K addresses (CITY='HOUSTON' AND SWDGarbageDay IS NOT NULL)
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing SUPABASE_URL or SUPABASE_SERVICE_KEY')
  console.error('Run with: node --env-file=.env.local scripts/import-houston.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://mycity2.houstontx.gov/pubgis01/rest/services/EGIS/COH_ADDRESS_THIESSEN_POLYGONS/MapServer/0/query'
const FIELDS = 'FULLADDRESS,ZIPCODE,SuperNeighborhood,SWDGarbageDay,SWDRecyclingDAY,SWDHeavyTrashDAY,Latitude,Longitude'
const WHERE = "CITY='HOUSTON' AND SWDGarbageDay IS NOT NULL"
const PAGE_SIZE = 2000  // ArcGIS max per request
const BATCH_SIZE = 500  // Supabase insert batch size

function parseRecyclingDay(raw) {
  // "MONDAY-A" -> { day: 'monday', week: 'A' }
  // "FRIDAY-B" -> { day: 'friday', week: 'B' }
  if (!raw) return { day: null, week: 'A' }
  const parts = raw.split('-')
  return {
    day: (parts[0] || '').toLowerCase(),
    week: parts[1] || 'A'
  }
}

function normalizeDay(raw) {
  if (!raw) return null
  return raw.toLowerCase().trim()
}

function normalizeAddress(fulladdress) {
  if (!fulladdress) return null
  // Normalize: lowercase, trim, collapse whitespace
  return fulladdress.toLowerCase().replace(/\s+/g, ' ').trim()
}

async function fetchPage(offset) {
  const params = new URLSearchParams({
    where: WHERE,
    outFields: FIELDS,
    returnGeometry: 'false',
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
    .upsert(rows, {
      onConflict: 'address,city',
      ignoreDuplicates: true
    })

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

async function main() {
  console.log('🗑️  TrashAlert — Houston TX Data Import')
  console.log('========================================')
  console.log(`Source: City of Houston Address Thiessen Polygons`)
  console.log(`Query: ${WHERE}\n`)

  // Check existing Houston records
  const { count: existingCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'houston')

  console.log(`📊 Existing Houston records: ${existingCount || 0}`)

  if (existingCount && existingCount > 470000) {
    console.log('⚠️  Houston data already fully imported (>470K records). Skipping.')
    console.log('   To re-import, delete Houston records first.')
    process.exit(0)
  }
  
  if (existingCount && existingCount > 200000) {
    console.log(`ℹ️  Partial import detected (${existingCount} records). Resuming to fill gaps...`)
  }

  const reporterHash = crypto.createHash('sha256').update('city_api_houston_tx').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let batchBuffer = []
  const seen = new Set()

  console.log(`\n📥 Fetching Houston addresses (${PAGE_SIZE} per page)...\n`)

  while (true) {
    const features = await fetchPage(offset)
    if (features.length === 0) break

    totalFetched += features.length

    for (const feature of features) {
      const a = feature.attributes
      const address = normalizeAddress(a.FULLADDRESS)
      if (!address || address.length < 3) { totalSkipped++; continue }

      // Dedup by address+zip
      const key = `${address}|${a.ZIPCODE}`
      if (seen.has(key)) { totalSkipped++; continue }
      seen.add(key)

      const garbageDay = normalizeDay(a.SWDGarbageDay)
      if (!garbageDay) { totalSkipped++; continue }

      const recycling = parseRecyclingDay(a.SWDRecyclingDAY)

      batchBuffer.push({
        address,
        city: 'houston',
        state: 'TX',
        zip_code: a.ZIPCODE || '',
        neighborhood: a.SuperNeighborhood || 'Houston',
        collection_day: garbageDay,
        recycling_week: recycling.week,
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler: 'City of Houston Solid Waste Management',
        data_source_url: 'https://mycity2.houstontx.gov/pubgis01/rest/services/EGIS/COH_ADDRESS_THIESSEN_POLYGONS/MapServer/0',
        data_source_type: 'gis',
        lat: a.Latitude || null,
        lng: a.Longitude || null,
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

        // Small delay to be polite
        await new Promise(r => setTimeout(r, 50))
      }
    }

    process.stdout.write(`  📊 Fetched: ${totalFetched} | Imported: ${totalImported} | Skipped: ${totalSkipped} | Errors: ${totalErrors}    \r`)

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

  console.log(`\n\n========================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Fetched:  ${totalFetched}`)
  console.log(`   Imported: ${totalImported}`)
  console.log(`   Skipped:  ${totalSkipped} (dupes/invalid)`)
  console.log(`   Errors:   ${totalErrors}`)

  // Verify final counts
  const { count: houstonCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'houston')

  const { count: totalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\n📊 Final counts:`)
  console.log(`   Houston:  ${houstonCount}`)
  console.log(`   Total DB: ${totalCount}`)
}

main().catch(err => {
  console.error('\nFatal error:', err)
  process.exit(1)
})
