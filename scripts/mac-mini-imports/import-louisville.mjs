#!/usr/bin/env node
/**
 * Import Louisville KY waste collection zone data
 *
 * Source: Jefferson County / Louisville Metro Open Data (ArcGIS FeatureServer)
 * https://services1.arcgis.com/79kfd2K6fskCAkyg/ArcGIS/rest/services/OpenDataJeflib/FeatureServer/21
 *
 * Fields used:
 * - SRA_GARB: Garbage route area ID
 * - SRA_DAY: Collection day (e.g. MON, TUE, WED, THU, FRI)
 * - SRA_ROUTE: Route number
 *
 * Records: ~50-100 garbage collection zones
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing SUPABASE_URL or SUPABASE_SERVICE_KEY')
  console.error('Run with: node --env-file=.env.local scripts/mac-mini-imports/import-louisville.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://services1.arcgis.com/79kfd2K6fskCAkyg/ArcGIS/rest/services/OpenDataJeflib/FeatureServer/21/query'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

const DAY_MAP = {
  'MON': 'monday',
  'MONDAY': 'monday',
  'TUE': 'tuesday',
  'TUES': 'tuesday',
  'TUESDAY': 'tuesday',
  'WED': 'wednesday',
  'WEDNESDAY': 'wednesday',
  'THU': 'thursday',
  'THUR': 'thursday',
  'THURS': 'thursday',
  'THURSDAY': 'thursday',
  'FRI': 'friday',
  'FRIDAY': 'friday',
  'SAT': 'saturday',
  'SATURDAY': 'saturday',
  'SUN': 'sunday',
  'SUNDAY': 'sunday',
}

function normalizeDay(raw) {
  if (!raw) return 'unknown'
  const upper = raw.toUpperCase().trim()
  return DAY_MAP[upper] || raw.toLowerCase().trim()
}

async function fetchPage(offset) {
  const params = new URLSearchParams({
    where: '1=1',
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

  return data
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
  console.log('🗑️  TrashAlert — Louisville KY Data Import')
  console.log('===========================================')
  console.log(`Source: Louisville Metro / Jefferson County Open Data`)
  console.log(`Endpoint: ${BASE_URL}\n`)

  // Check existing Louisville records
  const { count: existingCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'louisville')

  console.log(`📊 Existing Louisville records: ${existingCount || 0}`)

  if (existingCount && existingCount > 50) {
    console.log('⚠️  Louisville data already imported (>50 records). Skipping.')
    console.log('   To re-import, delete Louisville records first.')
    process.exit(0)
  }

  const reporterHash = crypto.createHash('sha256').update('city_api_louisville_ky').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let batchBuffer = []
  const seen = new Set()

  console.log(`\n📥 Fetching Louisville garbage collection zones (${PAGE_SIZE} per page)...\n`)

  while (true) {
    const data = await fetchPage(offset)
    const features = data.features || []
    if (features.length === 0) break

    totalFetched += features.length

    for (const feature of features) {
      const a = feature.attributes

      const sraGarb = a.SRA_GARB || ''
      const sraDay = a.SRA_DAY || ''
      const sraRoute = a.SRA_ROUTE || ''

      if (!sraGarb && !sraRoute) { totalSkipped++; continue }

      const address = `louisville garbage route ${sraRoute} area ${sraGarb}`.toLowerCase().trim()

      // Dedup
      if (seen.has(address)) { totalSkipped++; continue }
      seen.add(address)

      const collectionDay = normalizeDay(sraDay)

      batchBuffer.push({
        address,
        city: 'louisville',
        state: 'KY',
        zip_code: '',
        neighborhood: `Route ${sraRoute}`,
        collection_day: collectionDay,
        recycling_week: 'A',
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        data_source_type: 'gis',
        hauler: 'Louisville Metro Public Works',
        data_source_url: 'https://services1.arcgis.com/79kfd2K6fskCAkyg/ArcGIS/rest/services/OpenDataJeflib/FeatureServer/21',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
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
    // Also check exceededTransferLimit
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

  console.log(`\n\n===========================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Fetched:  ${totalFetched}`)
  console.log(`   Imported: ${totalImported}`)
  console.log(`   Skipped:  ${totalSkipped} (dupes/invalid)`)
  console.log(`   Errors:   ${totalErrors}`)

  // Verify final counts
  const { count: louisvilleCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'louisville')

  const { count: totalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\n📊 Final counts:`)
  console.log(`   Louisville: ${louisvilleCount}`)
  console.log(`   Total DB:   ${totalCount}`)
}

main().catch(err => {
  console.error('\nFatal error:', err)
  process.exit(1)
})
