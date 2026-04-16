#!/usr/bin/env node
/**
 * Import Jacksonville FL waste collection zone data
 *
 * Source: All WP Changes 2022 (ArcGIS FeatureServer Layer 23)
 * https://services1.arcgis.com/NXfNVaFp7QMxnE3j/arcgis/rest/services/All_WP_Changes_2022/FeatureServer/23
 *
 * Fields: COMPANY (hauler: CITY/WP/MW), DISTRICT, GarbDay, RecyDay, YardDay, BulkDay
 *
 * ~97 zones total.
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing env vars. Run with: node --env-file=.env.local scripts/mac-mini-imports/import-jacksonville.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://services1.arcgis.com/NXfNVaFp7QMxnE3j/arcgis/rest/services/All_WP_Changes_2022/FeatureServer/23/query'
const DATA_SOURCE_URL = 'https://services1.arcgis.com/NXfNVaFp7QMxnE3j/arcgis/rest/services/All_WP_Changes_2022/FeatureServer/23'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

const DAY_MAP = {
  'MON': 'monday',
  'MONDAY': 'monday',
  'Mon': 'monday',
  'Monday': 'monday',
  'TUE': 'tuesday',
  'TUESDAY': 'tuesday',
  'Tue': 'tuesday',
  'Tuesday': 'tuesday',
  'WED': 'wednesday',
  'WEDNESDAY': 'wednesday',
  'Wed': 'wednesday',
  'Wednesday': 'wednesday',
  'THU': 'thursday',
  'THURSDAY': 'thursday',
  'Thu': 'thursday',
  'Thursday': 'thursday',
  'FRI': 'friday',
  'FRIDAY': 'friday',
  'Fri': 'friday',
  'Friday': 'friday',
  'SAT': 'saturday',
  'SATURDAY': 'saturday',
  'Sat': 'saturday',
  'Saturday': 'saturday',
  'SUN': 'sunday',
  'SUNDAY': 'sunday',
  'Sun': 'sunday',
  'Sunday': 'sunday',
}

const HAULER_MAP = {
  'CITY': 'City of Jacksonville',
  'WP': 'Waste Pro',
  'MW': 'MidWay',
}

function normalizeDay(dayStr) {
  if (!dayStr) return null
  const trimmed = dayStr.trim()
  return DAY_MAP[trimmed] || DAY_MAP[trimmed.toUpperCase()] || null
}

function mapHauler(company) {
  if (!company) return 'City of Jacksonville'
  const key = company.trim().toUpperCase()
  return HAULER_MAP[key] || company.trim()
}

async function fetchPage(offset) {
  const params = new URLSearchParams({
    where: '1=1',
    outFields: '*',
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

async function main() {
  console.log('🗑️  TrashAlert — Jacksonville FL Data Import')
  console.log('=============================================')
  console.log('Source: All WP Changes 2022 (ArcGIS FeatureServer Layer 23)')
  console.log(`Endpoint: ${DATA_SOURCE_URL}\n`)

  // Check existing Jacksonville records
  const { count: existing } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'jacksonville')

  console.log(`📊 Existing Jacksonville records: ${existing || 0}`)

  if (existing && existing > 50) {
    console.log('⚠️  Jacksonville data already imported (>50 records). Skipping.')
    console.log('   To re-import, delete Jacksonville records first.')
    process.exit(0)
  }

  const reporterHash = crypto.createHash('sha256').update('city_api_jacksonville_fl').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let batchBuffer = []
  const seen = new Set()

  console.log('\n📥 Fetching Jacksonville waste collection zones...\n')

  while (true) {
    const features = await fetchPage(offset)
    if (features.length === 0) break

    totalFetched += features.length

    for (const feature of features) {
      const a = feature.attributes

      const objectid = a.OBJECTID || a.FID || ''
      const district = (a.DISTRICT || '').toString().trim()
      const company = (a.COMPANY || '').trim()

      if (!objectid) { totalSkipped++; continue }

      const address = `jacksonville district ${district} zone ${objectid}`.toLowerCase().replace(/\s+/g, ' ').trim()

      // Dedup within this run
      if (seen.has(address)) { totalSkipped++; continue }
      seen.add(address)

      const collectionDay = normalizeDay(a.GarbDay)
      if (!collectionDay) { totalSkipped++; continue }

      const hauler = mapHauler(company)

      batchBuffer.push({
        address,
        city: 'jacksonville',
        state: 'FL',
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
        data_source_url: DATA_SOURCE_URL,
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
  const { count: jaxCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'jacksonville')

  const { count: totalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\n📊 Final counts:`)
  console.log(`   Jacksonville: ${jaxCount}`)
  console.log(`   Total DB:     ${totalCount}`)
}

main().catch(err => {
  console.error('\nFatal error:', err)
  process.exit(1)
})
