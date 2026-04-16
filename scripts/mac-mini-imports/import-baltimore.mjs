#!/usr/bin/env node
/**
 * Import Baltimore MD waste collection schedules
 *
 * Source: Baltimore DPW Trash collection street segments (ArcGIS FeatureServer)
 * https://services3.arcgis.com/bpeS3swje8g57sok/arcgis/rest/services/Trash/FeatureServer/0
 *
 * This city has street-segment level data (1,940 segments) with address ranges,
 * richer than most zone-based cities. Each segment has LEFT_FROM/LEFT_TO (odd) and
 * RIGHT_FROM/RIGHT_TO (even) address ranges, which we expand into individual
 * address records (~100K+ generated addresses).
 *
 * Fields: TRASH_RT (route), TRASH_DAY (trash collection day), RECYCL_DAY (recycling day),
 *         BIN_COLOR, STR_NAME (street name), STR_TYPE (street type like ST/AVE),
 *         PREFIX_DIR (N/S/E/W), LEFT_FROM, LEFT_TO, RIGHT_FROM, RIGHT_TO
 *
 * Records: ~1,940 street segments -> ~100K+ individual address records
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing env vars. Run with: node --env-file=.env.local scripts/mac-mini-imports/import-baltimore.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const BASE_URL = 'https://services3.arcgis.com/bpeS3swje8g57sok/arcgis/rest/services/Trash/FeatureServer/0/query'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500
const MAX_RANGE_SPAN = 500 // Skip segments with address ranges > 500 (likely bad data)

const DAY_MAP = {
  'MON': 'monday', 'MONDAY': 'monday',
  'TUE': 'tuesday', 'TUESDAY': 'tuesday',
  'WED': 'wednesday', 'WEDNESDAY': 'wednesday',
  'THU': 'thursday', 'THURSDAY': 'thursday',
  'FRI': 'friday', 'FRIDAY': 'friday',
  'SAT': 'saturday', 'SATURDAY': 'saturday',
  'SUN': 'sunday', 'SUNDAY': 'sunday',
  'M': 'monday', 'T': 'tuesday', 'W': 'wednesday',
  'TH': 'thursday', 'F': 'friday',
  'MO': 'monday', 'TU': 'tuesday', 'WE': 'wednesday',
  'FR': 'friday', 'SA': 'saturday', 'SU': 'sunday',
}

function normalizeDay(raw) {
  if (!raw) return null
  const cleaned = raw.toUpperCase().trim()
  return DAY_MAP[cleaned] || null
}

/**
 * Generate individual addresses from a segment's address ranges.
 * Left side = odd numbers, Right side = even numbers.
 * Steps by 2 to stay on the correct parity.
 */
function generateAddresses(attrs) {
  const prefixDir = (attrs.PREFIX_DIR || '').trim()
  const strName = (attrs.STR_NAME || '').trim()
  const strType = (attrs.STR_TYPE || '').trim()

  if (!strName) return []

  const addresses = []

  // Left side: odd numbers
  const leftFrom = parseInt(attrs.LEFT_FROM, 10)
  const leftTo = parseInt(attrs.LEFT_TO, 10)
  if (!isNaN(leftFrom) && !isNaN(leftTo) && leftFrom > 0 && leftTo > 0) {
    const lo = Math.min(leftFrom, leftTo)
    const hi = Math.max(leftFrom, leftTo)
    if ((hi - lo) <= MAX_RANGE_SPAN) {
      // Ensure we start on an odd number
      const start = lo % 2 === 1 ? lo : lo + 1
      for (let num = start; num <= hi; num += 2) {
        addresses.push(buildAddress(num, prefixDir, strName, strType))
      }
    }
  }

  // Right side: even numbers
  const rightFrom = parseInt(attrs.RIGHT_FROM, 10)
  const rightTo = parseInt(attrs.RIGHT_TO, 10)
  if (!isNaN(rightFrom) && !isNaN(rightTo) && rightFrom > 0 && rightTo > 0) {
    const lo = Math.min(rightFrom, rightTo)
    const hi = Math.max(rightFrom, rightTo)
    if ((hi - lo) <= MAX_RANGE_SPAN) {
      // Ensure we start on an even number
      const start = lo % 2 === 0 ? lo : lo + 1
      for (let num = start; num <= hi; num += 2) {
        addresses.push(buildAddress(num, prefixDir, strName, strType))
      }
    }
  }

  return addresses
}

function buildAddress(num, prefixDir, strName, strType) {
  const parts = [String(num)]
  if (prefixDir) parts.push(prefixDir)
  parts.push(strName)
  if (strType) parts.push(strType)
  return parts.join(' ').toLowerCase().replace(/\s+/g, ' ').trim()
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
  console.log('🗑️  TrashAlert — Baltimore MD Data Import')
  console.log('==========================================')
  console.log('Source: Baltimore DPW Trash (ArcGIS FeatureServer)')
  console.log('Strategy: Expand street-segment address ranges into individual addresses\n')

  // Check existing Baltimore records
  const { count: existing } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'baltimore')

  console.log(`📊 Existing Baltimore records: ${existing || 0}`)

  if (existing && existing > 50000) {
    console.log('⚠️  Baltimore data already imported (>50,000 records). Skipping.')
    console.log('   To re-import, delete Baltimore records first.')
    process.exit(0)
  }

  const reporterHash = crypto.createHash('sha256').update('city_api_baltimore_md').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let offset = 0
  let totalSegments = 0
  let totalAddresses = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let skippedBadRange = 0
  let batchBuffer = []
  const seen = new Set()

  console.log('\n📥 Fetching Baltimore street segments...\n')

  while (true) {
    const features = await fetchPage(offset)
    if (features.length === 0) break

    totalSegments += features.length

    for (const feature of features) {
      const a = feature.attributes

      const collectionDay = normalizeDay(a.TRASH_DAY)
      if (!collectionDay) { totalSkipped++; continue }

      const rawPayloadHash = crypto.createHash('md5').update(JSON.stringify(a)).digest('hex')

      // Generate individual addresses from this segment's ranges
      const addresses = generateAddresses(a)

      if (addresses.length === 0) {
        totalSkipped++
        continue
      }

      for (const address of addresses) {
        if (!address || address.length < 3) { totalSkipped++; continue }

        // Dedup within this run
        if (seen.has(address)) { totalSkipped++; continue }
        seen.add(address)

        totalAddresses++

        batchBuffer.push({
          address,
          city: 'baltimore',
          state: 'MD',
          zip_code: '',
          neighborhood: 'Baltimore',
          collection_day: collectionDay,
          recycling_week: 'A',
          reporter_hash: reporterHash,
          verified: true,
          verification_count: 1,
          source: 'city_api',
          fetched_at: now,
          raw_payload_hash: rawPayloadHash,
          hauler: 'Baltimore DPW',
          data_source_url: 'https://services3.arcgis.com/bpeS3swje8g57sok/arcgis/rest/services/Trash/FeatureServer/0',
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
    }

    process.stdout.write(`  📊 Segments: ${totalSegments} | Addresses generated: ${totalAddresses} | Imported: ${totalImported} | Skipped: ${totalSkipped} | Errors: ${totalErrors}    \r`)

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

  console.log(`\n\n==========================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Segments fetched:    ${totalSegments}`)
  console.log(`   Addresses generated: ${totalAddresses}`)
  console.log(`   Imported:            ${totalImported}`)
  console.log(`   Skipped:             ${totalSkipped}`)
  console.log(`   Errors:              ${totalErrors}`)

  // Verify final counts
  const { count: baltimoreCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'baltimore')

  const { count: totalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\n📊 Final counts:`)
  console.log(`   Baltimore: ${baltimoreCount}`)
  console.log(`   Total DB:  ${totalCount}`)
}

main().catch(err => {
  console.error('\nFatal error:', err)
  process.exit(1)
})
