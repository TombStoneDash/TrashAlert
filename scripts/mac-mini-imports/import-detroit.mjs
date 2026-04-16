#!/usr/bin/env node
/**
 * Import Detroit MI waste collection zone data
 *
 * Source: DPW Trash collection zones (ArcGIS FeatureServer)
 * https://services2.arcgis.com/qvkbeam7Wirps6zC/arcgis/rest/services/dpw_trash/FeatureServer/0
 *
 * Fields: day (collection day), week (recycling week A/B),
 *         contractor (Advance or GFL), services (service types)
 *
 * ~15 zones total.
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing env vars. Run with: node --env-file=.env.local scripts/mac-mini-imports/import-detroit.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://services2.arcgis.com/qvkbeam7Wirps6zC/arcgis/rest/services/dpw_trash/FeatureServer/0'
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
  'MON': 'monday',
  'TUE': 'tuesday',
  'WED': 'wednesday',
  'THU': 'thursday',
  'FRI': 'friday',
  'SAT': 'saturday',
  'SUN': 'sunday',
}

function normalizeDay(day) {
  if (!day) return null
  const key = day.toUpperCase().trim()
  return DAY_MAP[key] || null
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

  const url = `${BASE_URL}/query?${params}`
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
  console.log('🗑️  TrashAlert — Detroit MI Data Import')
  console.log('========================================')
  console.log('Source: DPW Trash collection zones (ArcGIS FeatureServer)')
  console.log(`Endpoint: ${BASE_URL}`)
  console.log(`Expected: ~15 zones\n`)

  // Check existing Detroit records
  const { count: existing } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'detroit')

  console.log(`📊 Existing Detroit records: ${existing || 0}`)

  if (existing && existing > 10) {
    console.log('⚠️  Detroit data already imported (>10 records). Skipping.')
    console.log('   To re-import, delete Detroit records first.')
    process.exit(0)
  }

  const reporterHash = crypto.createHash('sha256').update('city_api_detroit_mi').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  console.log(`\n📥 Fetching Detroit waste zones (${PAGE_SIZE} per page)...\n`)

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let batchBuffer = []

  while (true) {
    const features = await fetchPage(offset)
    if (features.length === 0) break

    totalFetched += features.length

    for (const feature of features) {
      const a = feature.attributes
      const objectId = a.OBJECTID || a.objectid || a.ObjectId || ''
      const contractor = (a.contractor || a.CONTRACTOR || '').trim()
      const dayRaw = a.day || a.DAY || ''
      const week = (a.week || a.WEEK || '').trim()
      const services = a.services || a.SERVICES || ''

      const collectionDay = normalizeDay(dayRaw)
      if (!collectionDay) {
        totalSkipped++
        continue
      }

      const address = `detroit waste zone ${objectId} ${contractor}`.toLowerCase().replace(/\s+/g, ' ').trim()
      const recyclingWeek = (week === 'A' || week === 'B') ? week : 'A'

      batchBuffer.push({
        address,
        city: 'detroit',
        state: 'MI',
        zip_code: '',
        neighborhood: 'Detroit',
        collection_day: collectionDay,
        recycling_week: recyclingWeek,
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler: contractor || 'Detroit DPW',
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
  console.log(`   Skipped:  ${totalSkipped}`)
  console.log(`   Errors:   ${totalErrors}`)

  // Verify final counts
  const { count: detroitCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'detroit')

  const { count: totalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\n📊 Final counts:`)
  console.log(`   Detroit:  ${detroitCount}`)
  console.log(`   Total DB: ${totalCount}`)
}

main().catch(err => {
  console.error('\nFatal error:', err)
  process.exit(1)
})
