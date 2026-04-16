#!/usr/bin/env node
/**
 * Import Los Angeles County waste collection zone data
 *
 * Source: LA County Waste Service Collection Areas (ArcGIS FeatureServer)
 * https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/Los_Angeles_County_Waste_Service_Collection_Areas_view/FeatureServer/0
 *
 * Fields: AREA_NAME (zone name), WASTE_HAUL (hauler name), PICKUP_DAY (day of week)
 * Records: 239 zones
 *
 * Each zone becomes one schedule_reports row keyed by
 * "la county waste zone {areaName}" (lowercase)
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing env vars. Run with: node --env-file=.env.local scripts/mac-mini-imports/import-la-county.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/Los_Angeles_County_Waste_Service_Collection_Areas_view/FeatureServer/0/query'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

const DAY_MAP = {
  'MONDAY': 'monday', 'MON': 'monday', 'Monday': 'monday', 'Mon': 'monday', 'M': 'monday', '1': 'monday',
  'TUESDAY': 'tuesday', 'TUE': 'tuesday', 'Tuesday': 'tuesday', 'Tue': 'tuesday', 'T': 'tuesday', '2': 'tuesday',
  'WEDNESDAY': 'wednesday', 'WED': 'wednesday', 'Wednesday': 'wednesday', 'Wed': 'wednesday', 'W': 'wednesday', '3': 'wednesday',
  'THURSDAY': 'thursday', 'THU': 'thursday', 'Thursday': 'thursday', 'Thu': 'thursday', 'R': 'thursday', '4': 'thursday',
  'FRIDAY': 'friday', 'FRI': 'friday', 'Friday': 'friday', 'Fri': 'friday', 'F': 'friday', '5': 'friday',
  'SATURDAY': 'saturday', 'SAT': 'saturday', 'Saturday': 'saturday', 'Sat': 'saturday',
}

function normalizeDay(raw) {
  if (!raw) return null
  const trimmed = raw.toString().trim()
  return DAY_MAP[trimmed] || DAY_MAP[trimmed.toUpperCase()] || null
}

async function fetchPage(offset) {
  const params = new URLSearchParams({
    where: '1=1',
    outFields: 'AREA_NAME,WASTE_HAUL,PICKUP_DAY,OBJECTID',
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

  return data
}

async function importBatch(rows) {
  const { error } = await supabase
    .from('schedule_reports')
    .upsert(rows, { onConflict: 'address,city', ignoreDuplicates: true })

  if (error) {
    // Fallback to plain insert if upsert fails
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
  console.log('🗑️  TrashAlert — Los Angeles County CA Data Import')
  console.log('====================================================')
  console.log(`Source: LA County Waste Service Collection Areas`)
  console.log(`Endpoint: ${BASE_URL}\n`)

  // Check existing LA County records
  const { count: existing } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'los angeles county')

  console.log(`📊 Existing LA County records: ${existing || 0}`)

  if (existing && existing > 200) {
    console.log('⚠️  LA County data already imported (>200 records). Skipping.')
    console.log('   To re-import, delete LA County records first.')
    process.exit(0)
  }

  const reporterHash = crypto.createHash('sha256').update('city_api_la_county_ca').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let batchBuffer = []
  const seen = new Set()

  console.log(`\n📥 Fetching LA County waste collection zones (~239 zones)...\n`)

  while (true) {
    const data = await fetchPage(offset)
    const features = data.features || []
    if (features.length === 0) break

    totalFetched += features.length

    for (const feature of features) {
      const a = feature.attributes
      const areaName = (a.AREA_NAME || '').toString().trim()
      const wasteHaul = (a.WASTE_HAUL || '').toString().trim()
      const pickupDay = (a.PICKUP_DAY || '').toString().trim()

      if (!areaName) { totalSkipped++; continue }

      const address = `la county waste zone ${areaName}`.toLowerCase().replace(/\s+/g, ' ').trim()

      // Dedup within this run
      if (seen.has(address)) { totalSkipped++; continue }
      seen.add(address)

      const collectionDay = normalizeDay(pickupDay)
      if (!collectionDay) { totalSkipped++; continue }

      const hauler = wasteHaul || 'LA County Waste Services'

      batchBuffer.push({
        address,
        city: 'los angeles county',
        state: 'CA',
        zip_code: '',
        neighborhood: areaName,
        collection_day: collectionDay,
        recycling_week: 'A',
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler,
        data_source_url: 'https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/Los_Angeles_County_Waste_Service_Collection_Areas_view/FeatureServer/0',
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
    if (!data.exceededTransferLimit) break

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

  console.log(`\n\n====================================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Fetched:  ${totalFetched}`)
  console.log(`   Imported: ${totalImported}`)
  console.log(`   Skipped:  ${totalSkipped}`)
  console.log(`   Errors:   ${totalErrors}`)

  // Verify final counts
  const { count: laCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'los angeles county')

  const { count: totalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\n📊 Final counts:`)
  console.log(`   LA County: ${laCount}`)
  console.log(`   Total DB:  ${totalCount}`)
}

main().catch(err => {
  console.error('\nFatal error:', err)
  process.exit(1)
})
