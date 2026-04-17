#!/usr/bin/env node
/**
 * Import Mesa AZ waste collection zone data
 *
 * Source: Mesa Geocortex "Identify" layer (city-services polygon layer)
 * https://gis.mesaaz.gov/mesaaz/rest/services/Geocortex/GCX_ExploreMesa/MapServer/16
 *
 * Fields:
 * - BLACK: Trash barrel pickup day (MONDAY, THURSDAY, etc.)
 * - BLUE: Recycling barrel pickup day
 * - GREEN: Green/yard waste barrel pickup day
 * - District: Council district number
 *
 * Records: ~270 zones with active collection schedules (filter: BLACK <> '')
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing env vars. Run with: node --env-file=.env.local scripts/mac-mini-imports/import-mesa.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://gis.mesaaz.gov/mesaaz/rest/services/Geocortex/GCX_ExploreMesa/MapServer/16/query'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

const DAY_MAP = {
  'MONDAY': 'monday', 'MON': 'monday', 'Monday': 'monday',
  'TUESDAY': 'tuesday', 'TUE': 'tuesday', 'Tuesday': 'tuesday',
  'WEDNESDAY': 'wednesday', 'WED': 'wednesday', 'Wednesday': 'wednesday',
  'THURSDAY': 'thursday', 'THU': 'thursday', 'Thursday': 'thursday',
  'FRIDAY': 'friday', 'FRI': 'friday', 'Friday': 'friday',
  'SATURDAY': 'saturday', 'SAT': 'saturday', 'Saturday': 'saturday',
}

function normalizeDay(raw) {
  if (!raw) return null
  const s = String(raw).trim()
  return DAY_MAP[s] || DAY_MAP[s.toUpperCase()] || null
}

async function fetchPage(offset) {
  const params = new URLSearchParams({
    where: "BLACK <> '' AND BLACK <> 'City No Service'",
    outFields: '*',
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
    .upsert(rows, { onConflict: 'address,city', ignoreDuplicates: true })

  if (error) {
    const { error: insertError } = await supabase.from('schedule_reports').insert(rows)
    if (insertError) return { ok: false, error: insertError.message }
  }
  return { ok: true }
}

async function main() {
  console.log('TrashAlert -- Mesa AZ Data Import')
  console.log('==================================')

  const { count: existing } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'mesa')

  console.log(`Existing Mesa records: ${existing || 0}`)

  if (existing && existing > 200) {
    console.log('Mesa data already imported. Skipping.')
    process.exit(0)
  }

  const reporterHash = crypto.createHash('sha256').update('city_api_mesa_az').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let batchBuffer = []
  const seen = new Set()

  console.log('\nFetching Mesa waste zones...\n')

  while (true) {
    const features = await fetchPage(offset)
    if (features.length === 0) break

    totalFetched += features.length

    for (const feature of features) {
      const a = feature.attributes
      const trashDay = normalizeDay(a.BLACK)
      if (!trashDay) { totalSkipped++; continue }

      const recycleDay = normalizeDay(a.BLUE)
      const greenDay = normalizeDay(a.GREEN)
      const district = a.District || a.OBJECTID || 'unknown'

      const address = `mesa district ${district} zone ${a.OBJECTID}`.toLowerCase()

      if (seen.has(address)) { totalSkipped++; continue }
      seen.add(address)

      batchBuffer.push({
        address,
        city: 'mesa',
        state: 'AZ',
        zip_code: '',
        neighborhood: `District ${district}`,
        collection_day: trashDay,
        recycling_week: 'A',
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        data_source_type: 'gis',
        hauler: 'City of Mesa Solid Waste',
        data_source_url: 'https://gis.mesaaz.gov/mesaaz/rest/services/Geocortex/GCX_ExploreMesa/MapServer/16',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        lat: null,
        lng: null,
      })

      if (batchBuffer.length >= BATCH_SIZE) {
        const result = await importBatch(batchBuffer)
        if (result.ok) totalImported += batchBuffer.length
        else {
          totalErrors += batchBuffer.length
          if (totalErrors <= 500) console.error(`  Batch error: ${result.error}`)
        }
        batchBuffer = []
        await new Promise(r => setTimeout(r, 50))
      }
    }

    process.stdout.write(`  Fetched: ${totalFetched} | Imported: ${totalImported} | Skipped: ${totalSkipped} | Errors: ${totalErrors}    \r`)

    if (features.length < PAGE_SIZE) break
    offset += PAGE_SIZE
    await new Promise(r => setTimeout(r, 200))
  }

  // Flush remaining
  if (batchBuffer.length > 0) {
    const result = await importBatch(batchBuffer)
    if (result.ok) totalImported += batchBuffer.length
    else totalErrors += batchBuffer.length
  }

  console.log(`\n\n==================================`)
  console.log(`Import complete!`)
  console.log(`   Fetched:  ${totalFetched}`)
  console.log(`   Imported: ${totalImported}`)
  console.log(`   Skipped:  ${totalSkipped}`)
  console.log(`   Errors:   ${totalErrors}`)

  const { count: mesaCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'mesa')

  const { count: totalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\nFinal counts:`)
  console.log(`   Mesa:  ${mesaCount}`)
  console.log(`   Total: ${totalCount}`)
}

main().catch(err => { console.error('\nFatal:', err); process.exit(1) })
