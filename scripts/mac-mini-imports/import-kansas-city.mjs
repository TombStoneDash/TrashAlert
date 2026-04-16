#!/usr/bin/env node
/**
 * Import Kansas City MO waste collection zone data
 *
 * Source: Trash Day zones (ArcGIS MapServer)
 * https://mapd.kcmo.org/kcgis/rest/services/PublicWorks/TrashDay/MapServer/0
 *
 * Fields: TRASHDAY (string — day of week, e.g. "MONDAY", "TUESDAY")
 *
 * ~303 zones total.
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing env vars. Run with: node --env-file=.env.local scripts/mac-mini-imports/import-kansas-city.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://mapd.kcmo.org/kcgis/rest/services/PublicWorks/TrashDay/MapServer/0'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

const DAY_MAP = {
  'MONDAY': 'monday',
  'TUESDAY': 'tuesday',
  'WEDNESDAY': 'wednesday',
  'THURSDAY': 'thursday',
  'FRIDAY': 'friday',
  'MON': 'monday',
  'TUE': 'tuesday',
  'WED': 'wednesday',
  'THU': 'thursday',
  'FRI': 'friday',
}

function normalizeDay(trashDay) {
  if (!trashDay) return null
  return DAY_MAP[trashDay.toUpperCase().trim()] || null
}

async function fetchPage(offset) {
  const url = `${BASE_URL}/query?where=1%3D1&outFields=*&returnGeometry=false&resultOffset=${offset}&resultRecordCount=${PAGE_SIZE}&orderByFields=OBJECTID+ASC&f=json`

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

async function main() {
  console.log('🗑️  TrashAlert — Kansas City MO Data Import')
  console.log('=============================================')
  console.log('Source: Trash Day zones (ArcGIS MapServer)')
  console.log(`Endpoint: ${BASE_URL}\n`)

  // Check existing Kansas City records
  const { count: existing } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'kansas city')

  console.log(`📊 Existing Kansas City records: ${existing || 0}`)

  if (existing && existing > 200) {
    console.log('⚠️  Kansas City data already imported (>200 records). Skipping.')
    console.log('   To re-import, delete Kansas City records first.')
    process.exit(0)
  }

  const reporterHash = crypto.createHash('sha256').update('city_api_kansas_city_mo').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let batchBuffer = []
  const seen = new Set()

  console.log('\n📥 Fetching Kansas City trash zones...\n')

  while (true) {
    const features = await fetchPage(offset)
    if (features.length === 0) break

    totalFetched += features.length

    for (const feature of features) {
      const a = feature.attributes

      const objectid = a.OBJECTID || a.FID || totalFetched
      const address = `kansas city trash zone ${objectid}`.toLowerCase()

      // Dedup within this run
      if (seen.has(address)) { totalSkipped++; continue }
      seen.add(address)

      const collectionDay = normalizeDay(a.TRASHDAY)
      if (!collectionDay) { totalSkipped++; continue }

      batchBuffer.push({
        address,
        city: 'kansas city',
        state: 'MO',
        zip_code: '',
        neighborhood: 'Kansas City',
        collection_day: collectionDay,
        recycling_week: 'A',
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler: 'Kansas City Public Works',
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
    if (result.ok) totalImported += batchBuffer.length
    else totalErrors += batchBuffer.length
  }

  console.log(`\n\n=============================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Fetched:  ${totalFetched}`)
  console.log(`   Imported: ${totalImported}`)
  console.log(`   Skipped:  ${totalSkipped}`)
  console.log(`   Errors:   ${totalErrors}`)

  // Verify final counts
  const { count: kcCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'kansas city')

  const { count: totalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\n📊 Final counts:`)
  console.log(`   Kansas City: ${kcCount}`)
  console.log(`   Total DB:    ${totalCount}`)
}

main().catch(err => {
  console.error('\nFatal error:', err)
  process.exit(1)
})
