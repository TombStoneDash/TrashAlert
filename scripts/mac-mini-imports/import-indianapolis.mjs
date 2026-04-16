#!/usr/bin/env node
/**
 * Import Indianapolis IN waste collection zone data
 *
 * Source: Indianapolis/Marion County GIS — InforPS MapServer Layer 29
 * https://gis.indy.gov/server/rest/services/InforPS/InforPS/MapServer/29
 *
 * Fields used:
 * - HAULER: trash hauler name
 * - ROUTE_NO: route number
 * - DISTRICT: collection district
 * - DAY: trash collection day (MONDAY, MON, Monday, M, etc.)
 * - HVYTRASHDA: heavy trash day
 * - RC_HAULER: recycling hauler
 * - RC_DAY: recycling collection day
 *
 * Total: ~485 zone records
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing env vars. Run with: node --env-file=.env.local scripts/mac-mini-imports/import-indianapolis.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://gis.indy.gov/server/rest/services/InforPS/InforPS/MapServer/29'
const PAGE_SIZE = 2000   // ArcGIS max per request
const BATCH_SIZE = 500   // Supabase insert batch size

/** Normalize day-of-week values to lowercase full names */
const DAY_MAP = {
  // Full names (any case)
  'MONDAY': 'monday', 'Monday': 'monday', 'monday': 'monday',
  'TUESDAY': 'tuesday', 'Tuesday': 'tuesday', 'tuesday': 'tuesday',
  'WEDNESDAY': 'wednesday', 'Wednesday': 'wednesday', 'wednesday': 'wednesday',
  'THURSDAY': 'thursday', 'Thursday': 'thursday', 'thursday': 'thursday',
  'FRIDAY': 'friday', 'Friday': 'friday', 'friday': 'friday',
  'SATURDAY': 'saturday', 'Saturday': 'saturday', 'saturday': 'saturday',
  'SUNDAY': 'sunday', 'Sunday': 'sunday', 'sunday': 'sunday',
  // 3-letter abbreviations
  'MON': 'monday', 'Mon': 'monday', 'mon': 'monday',
  'TUE': 'tuesday', 'Tue': 'tuesday', 'tue': 'tuesday',
  'WED': 'wednesday', 'Wed': 'wednesday', 'wed': 'wednesday',
  'THU': 'thursday', 'Thu': 'thursday', 'thu': 'thursday',
  'FRI': 'friday', 'Fri': 'friday', 'fri': 'friday',
  'SAT': 'saturday', 'Sat': 'saturday', 'sat': 'saturday',
  'SUN': 'sunday', 'Sun': 'sunday', 'sun': 'sunday',
  // Single-letter codes
  'M': 'monday',
  'T': 'tuesday',
  'W': 'wednesday',
  'R': 'thursday',
  'F': 'friday',
}

function normalizeDay(raw) {
  if (!raw) return null
  const trimmed = raw.trim()
  return DAY_MAP[trimmed] || null
}

async function fetchPage(offset) {
  const url = `${BASE_URL}/query?where=1%3D1&outFields=*&returnGeometry=false&resultOffset=${offset}&resultRecordCount=${PAGE_SIZE}&orderByFields=OBJECTID+ASC&f=json`

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
  console.log('🗑️  TrashAlert — Indianapolis IN Data Import')
  console.log('==============================================')
  console.log(`Source: Indianapolis/Marion County GIS — InforPS MapServer Layer 29`)
  console.log(`Endpoint: ${BASE_URL}\n`)

  // Check existing Indianapolis records
  const { count: existingCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'indianapolis')

  console.log(`📊 Existing Indianapolis records: ${existingCount || 0}`)

  if (existingCount && existingCount > 400) {
    console.log('⚠️  Indianapolis data already imported (>400 records). Skipping.')
    console.log('   To re-import, delete Indianapolis records first.')
    process.exit(0)
  }

  const reporterHash = crypto.createHash('sha256').update('city_api_indianapolis_in').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let batchBuffer = []
  const seen = new Set()

  console.log(`\n📥 Fetching Indianapolis zone records (${PAGE_SIZE} per page)...\n`)

  while (true) {
    const features = await fetchPage(offset)
    if (features.length === 0) break

    totalFetched += features.length

    for (const feature of features) {
      const a = feature.attributes

      const routeNo = a.ROUTE_NO || ''
      const district = a.DISTRICT || ''

      if (!routeNo && !district) { totalSkipped++; continue }

      const address = `indianapolis route ${routeNo} district ${district}`.toLowerCase().replace(/\s+/g, ' ').trim()

      // Dedup
      if (seen.has(address)) { totalSkipped++; continue }
      seen.add(address)

      const collectionDay = normalizeDay(a.DAY)
      if (!collectionDay) { totalSkipped++; continue }

      const hauler = a.HAULER || 'Indianapolis DPW'

      batchBuffer.push({
        address,
        city: 'indianapolis',
        state: 'IN',
        zip_code: '',
        neighborhood: `District ${district}`,
        collection_day: collectionDay,
        recycling_week: 'A',
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler,
        data_source_url: BASE_URL,
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

  console.log(`\n\n==============================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Fetched:  ${totalFetched}`)
  console.log(`   Imported: ${totalImported}`)
  console.log(`   Skipped:  ${totalSkipped} (dupes/no day/invalid)`)
  console.log(`   Errors:   ${totalErrors}`)

  // Verify final counts
  const { count: indyCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'indianapolis')

  const { count: totalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\n📊 Final counts:`)
  console.log(`   Indianapolis: ${indyCount}`)
  console.log(`   Total DB:     ${totalCount}`)
}

main().catch(err => {
  console.error('\nFatal error:', err)
  process.exit(1)
})
