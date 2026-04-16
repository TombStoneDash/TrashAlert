#!/usr/bin/env node
/**
 * Import Tucson AZ waste collection zone data
 *
 * Two data sources:
 * 1. Brush & Bulky: 238 zones with BBArea, ServiceDates, Cycle1Date, Cycle2Date
 *    https://utility.arcgis.com/usrsvcs/servers/c12b866163a04387ad7dcd4ebc6c4926/rest/services/PublicMaps/EnvironmentalGeneralServices/MapServer/239
 *
 * 2. Recycling: 131 zones with CollWeek (A/B), DOS (day of service), PRIMARY_RT
 *    https://mapdata.tucsonaz.gov/arcgis/rest/services/IT/ZoomTucson/MapServer/56
 *
 * Each zone becomes one schedule_reports row.
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing env vars. Run with: node --env-file=.env.local scripts/mac-mini-imports/import-tucson.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BRUSH_BULKY_URL = 'https://utility.arcgis.com/usrsvcs/servers/c12b866163a04387ad7dcd4ebc6c4926/rest/services/PublicMaps/EnvironmentalGeneralServices/MapServer/239/query'
const RECYCLING_URL = 'https://mapdata.tucsonaz.gov/arcgis/rest/services/IT/ZoomTucson/MapServer/56/query'
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

/**
 * Try to parse a day-of-week from ServiceDates text.
 * ServiceDates may contain things like "Monday, Jan 6 - Jan 17" or free-form text.
 * We look for a recognizable day name; if none found, return 'varies'.
 */
function parseDayFromServiceDates(serviceDates) {
  if (!serviceDates) return 'varies'
  const text = serviceDates.toString().trim()
  if (!text) return 'varies'

  // Try to find a day name anywhere in the text
  for (const [key, val] of Object.entries(DAY_MAP)) {
    // Match whole-word only to avoid false positives
    const regex = new RegExp(`\\b${key}\\b`, 'i')
    if (regex.test(text)) return val
  }

  return 'varies'
}

async function fetchPage(baseUrl, outFields, offset) {
  const params = new URLSearchParams({
    where: '1=1',
    outFields,
    returnGeometry: 'false',
    resultOffset: String(offset),
    resultRecordCount: String(PAGE_SIZE),
    orderByFields: 'OBJECTID ASC',
    f: 'json',
  })

  const url = `${baseUrl}?${params}`
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

async function importBrushBulky(reporterHash, now) {
  console.log(`\n📥 Fetching Brush & Bulky zones (~238 zones)...\n`)

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let batchBuffer = []
  const seen = new Set()

  while (true) {
    const data = await fetchPage(BRUSH_BULKY_URL, 'BBArea,ServiceDates,Cycle1Date,Cycle2Date,OBJECTID', offset)
    const features = data.features || []
    if (features.length === 0) break

    totalFetched += features.length

    for (const feature of features) {
      const a = feature.attributes
      const bbarea = (a.BBArea || '').toString().trim()

      if (!bbarea) { totalSkipped++; continue }

      const address = `tucson brush bulky area ${bbarea}`.toLowerCase().replace(/\s+/g, ' ').trim()

      // Dedup within this run
      if (seen.has(address)) { totalSkipped++; continue }
      seen.add(address)

      const collectionDay = parseDayFromServiceDates(a.ServiceDates)

      batchBuffer.push({
        address,
        city: 'tucson',
        state: 'AZ',
        zip_code: '',
        neighborhood: `BB Area ${bbarea}`,
        collection_day: collectionDay,
        recycling_week: 'A',
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler: 'City of Tucson Environmental Services',
        data_source_url: 'https://utility.arcgis.com/usrsvcs/servers/c12b866163a04387ad7dcd4ebc6c4926/rest/services/PublicMaps/EnvironmentalGeneralServices/MapServer/239',
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

    process.stdout.write(`  📊 [Brush & Bulky] Fetched: ${totalFetched} | Imported: ${totalImported} | Skipped: ${totalSkipped} | Errors: ${totalErrors}    \r`)

    offset += PAGE_SIZE

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

  console.log(`\n  ✅ Brush & Bulky: Fetched ${totalFetched}, Imported ${totalImported}, Skipped ${totalSkipped}, Errors ${totalErrors}`)

  return { totalFetched, totalImported, totalSkipped, totalErrors }
}

async function importRecycling(reporterHash, now) {
  console.log(`\n📥 Fetching Recycling routes (~131 zones)...\n`)

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let batchBuffer = []
  const seen = new Set()

  while (true) {
    const data = await fetchPage(RECYCLING_URL, 'CollWeek,DOS,PRIMARY_RT,OBJECTID', offset)
    const features = data.features || []
    if (features.length === 0) break

    totalFetched += features.length

    for (const feature of features) {
      const a = feature.attributes
      const primaryRt = (a.PRIMARY_RT || '').toString().trim()
      const dos = (a.DOS || '').toString().trim()
      const collWeek = (a.CollWeek || '').toString().trim()

      if (!primaryRt) { totalSkipped++; continue }

      const address = `tucson recycling route ${primaryRt}`.toLowerCase().replace(/\s+/g, ' ').trim()

      // Dedup within this run
      if (seen.has(address)) { totalSkipped++; continue }
      seen.add(address)

      const collectionDay = normalizeDay(dos) || 'unknown'

      batchBuffer.push({
        address,
        city: 'tucson',
        state: 'AZ',
        zip_code: '',
        neighborhood: `Route ${primaryRt}`,
        collection_day: collectionDay,
        recycling_week: collWeek.toUpperCase() === 'B' ? 'B' : 'A',
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler: 'City of Tucson Environmental Services',
        data_source_url: 'https://mapdata.tucsonaz.gov/arcgis/rest/services/IT/ZoomTucson/MapServer/56',
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

    process.stdout.write(`  📊 [Recycling] Fetched: ${totalFetched} | Imported: ${totalImported} | Skipped: ${totalSkipped} | Errors: ${totalErrors}    \r`)

    offset += PAGE_SIZE

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

  console.log(`\n  ✅ Recycling: Fetched ${totalFetched}, Imported ${totalImported}, Skipped ${totalSkipped}, Errors ${totalErrors}`)

  return { totalFetched, totalImported, totalSkipped, totalErrors }
}

async function main() {
  console.log('🗑️  TrashAlert — Tucson AZ Data Import')
  console.log('=======================================')
  console.log('Sources:')
  console.log('  1. Brush & Bulky (238 zones)')
  console.log('  2. Recycling routes (131 zones)\n')

  // Check existing Tucson records
  const { count: existing } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'tucson')

  console.log(`📊 Existing Tucson records: ${existing || 0}`)

  if (existing && existing > 200) {
    console.log('⚠️  Tucson data already imported (>200 records). Skipping.')
    console.log('   To re-import, delete Tucson records first.')
    process.exit(0)
  }

  const reporterHash = crypto.createHash('sha256').update('city_api_tucson_az').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  // --- Import Brush & Bulky zones ---
  const bb = await importBrushBulky(reporterHash, now)

  // --- Import Recycling routes ---
  const recy = await importRecycling(reporterHash, now)

  // Summary
  const grandFetched = bb.totalFetched + recy.totalFetched
  const grandImported = bb.totalImported + recy.totalImported
  const grandSkipped = bb.totalSkipped + recy.totalSkipped
  const grandErrors = bb.totalErrors + recy.totalErrors

  console.log(`\n\n=======================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Brush & Bulky: ${bb.totalFetched} fetched, ${bb.totalImported} imported`)
  console.log(`   Recycling:     ${recy.totalFetched} fetched, ${recy.totalImported} imported`)
  console.log(`   Total fetched:  ${grandFetched}`)
  console.log(`   Total imported: ${grandImported}`)
  console.log(`   Total skipped:  ${grandSkipped}`)
  console.log(`   Total errors:   ${grandErrors}`)

  // Verify final counts
  const { count: tucsonCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'tucson')

  const { count: totalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\n📊 Final counts:`)
  console.log(`   Tucson:   ${tucsonCount}`)
  console.log(`   Total DB: ${totalCount}`)
}

main().catch(err => {
  console.error('\nFatal error:', err)
  process.exit(1)
})
