#!/usr/bin/env node
/**
 * Import Raleigh NC waste collection ADDRESS-LEVEL data
 *
 * This is a gold-standard data source: 128,853 individual service addresses
 * with per-address collection day, recycling week, and route codes.
 *
 * Source: Solid Waste Collection (ArcGIS FeatureServer)
 * https://services.arcgis.com/v400IkDOw1ad7Yad/arcgis/rest/services/Solid_Waste_Collection/FeatureServer/1
 *
 * Key fields: ADDRESS, STNO, STNAME, STTYPE, STPRE, APT, CITY,
 *             SERVICEDAY, GARBAGE, RECYCLE, YARDWASTE, SER_WEEK
 *
 * Records: 128,853 individual service addresses
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing env vars. Run with: node --env-file=.env.local scripts/mac-mini-imports/import-raleigh.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://services.arcgis.com/v400IkDOw1ad7Yad/arcgis/rest/services/Solid_Waste_Collection/FeatureServer/1/query'
const DATA_SOURCE_URL = 'https://services.arcgis.com/v400IkDOw1ad7Yad/arcgis/rest/services/Solid_Waste_Collection/FeatureServer/1'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

const DAY_MAP = {
  'MONDAY': 'monday',
  'TUESDAY': 'tuesday',
  'WEDNESDAY': 'wednesday',
  'THURSDAY': 'thursday',
  'FRIDAY': 'friday',
  'SATURDAY': 'saturday',
  'SUNDAY': 'sunday',
}

function normalizeDay(serviceDay) {
  if (!serviceDay) return null
  return DAY_MAP[serviceDay.toUpperCase().trim()] || null
}

function normalizeRecyclingWeek(serWeek) {
  if (!serWeek) return null
  const upper = serWeek.toUpperCase().trim()
  if (upper === 'WEEK_A') return 'A'
  if (upper === 'WEEK_B') return 'B'
  return null
}

function buildAddress(a) {
  // Prefer the ADDRESS field; fall back to building from components
  const fullAddr = (a.ADDRESS || '').trim()
  if (fullAddr) return fullAddr.toLowerCase()

  const parts = [
    (a.STNO || '').toString().trim(),
    (a.STPRE || '').trim(),
    (a.STNAME || '').trim(),
    (a.STTYPE || '').trim(),
  ].filter(Boolean)

  const base = parts.join(' ')
  if (!base) return null

  const apt = (a.APT || '').trim()
  const full = apt ? `${base} ${apt}` : base

  return full.toLowerCase().replace(/\s+/g, ' ').trim()
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
  console.log('🗑️  TrashAlert — Raleigh NC Address-Level Data Import')
  console.log('=====================================================')
  console.log('Source: Solid Waste Collection (ArcGIS FeatureServer)')
  console.log('Type:   ADDRESS-LEVEL (gold-standard) — 128,853 service points')
  console.log(`URL:    ${DATA_SOURCE_URL}\n`)

  // Check existing Raleigh records
  const { count: existingCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'raleigh')

  console.log(`📊 Existing Raleigh records: ${existingCount || 0}`)

  if (existingCount && existingCount > 100000) {
    console.log('⚠️  Raleigh data already imported (>100,000 records). Skipping.')
    console.log('   To re-import, delete Raleigh records first.')
    process.exit(0)
  }

  const reporterHash = crypto.createHash('sha256').update('city_api_raleigh_nc').digest('hex').substring(0, 16)
  const now = new Date().toISOString()
  const seen = new Set()

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let batchBuffer = []

  console.log(`\n📥 Fetching address-level service points (${PAGE_SIZE} per page)...\n`)

  while (true) {
    const features = await fetchPage(offset)
    if (features.length === 0) break

    totalFetched += features.length

    for (const feature of features) {
      const a = feature.attributes

      const address = buildAddress(a)
      if (!address) { totalSkipped++; continue }

      // Dedup by address within this run
      if (seen.has(address)) { totalSkipped++; continue }
      seen.add(address)

      const collectionDay = normalizeDay(a.SERVICEDAY)
      if (!collectionDay) { totalSkipped++; continue }

      const recyclingWeek = normalizeRecyclingWeek(a.SER_WEEK) || 'A'

      batchBuffer.push({
        address,
        city: 'raleigh',
        state: 'NC',
        zip_code: '',
        neighborhood: 'Raleigh',
        collection_day: collectionDay,
        recycling_week: recyclingWeek,
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler: 'City of Raleigh Solid Waste Services',
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

        // Small delay between batches
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

  console.log(`\n\n=====================================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Fetched:  ${totalFetched}`)
  console.log(`   Imported: ${totalImported}`)
  console.log(`   Skipped:  ${totalSkipped}`)
  console.log(`   Errors:   ${totalErrors}`)

  // Verify final counts
  const { count: raleighCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'raleigh')

  const { count: totalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\n📊 Final counts:`)
  console.log(`   Raleigh:  ${raleighCount}`)
  console.log(`   Total DB: ${totalCount}`)
}

main().catch(err => {
  console.error('\nFatal error:', err)
  process.exit(1)
})
