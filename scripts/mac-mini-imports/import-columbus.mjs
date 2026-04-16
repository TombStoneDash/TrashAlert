#!/usr/bin/env node
/**
 * Import Columbus OH waste collection zone data
 *
 * Strategy:
 * 1. Fetch refuse zone polygons from ArcGIS Layer 11 (15,678 records)
 * 2. Parse UNIT_NAME (e.g. "Gold Tuesday") to extract collection day + color group
 * 3. Fetch recycling zone polygons from ArcGIS Layer 12 (13,301 records)
 * 4. Batch import both to Supabase
 *
 * Sources:
 * - Refuse:    https://maps2.columbus.gov/arcgis/rest/services/Schemas/PublicService/MapServer/11
 * - Recycling: https://maps2.columbus.gov/arcgis/rest/services/Schemas/PublicService/MapServer/12
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing env vars. Run with: node --env-file=.env.local scripts/mac-mini-imports/import-columbus.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const REFUSE_URL = 'https://maps2.columbus.gov/arcgis/rest/services/Schemas/PublicService/MapServer/11'
const RECYCLING_URL = 'https://maps2.columbus.gov/arcgis/rest/services/Schemas/PublicService/MapServer/12'
const PAGE_SIZE = 2000   // ArcGIS max per request
const BATCH_SIZE = 500   // Supabase insert batch size

const VALID_DAYS = new Set(['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'])

function parseUnitName(unitName) {
  // "Gold Tuesday" -> { color: 'Gold', day: 'tuesday' }
  // "Blue Wednesday" -> { color: 'Blue', day: 'wednesday' }
  if (!unitName) return { color: null, day: null }
  const parts = unitName.trim().split(/\s+/)
  if (parts.length < 2) return { color: parts[0] || null, day: null }
  const day = parts[parts.length - 1].toLowerCase()
  const color = parts.slice(0, parts.length - 1).join(' ')
  return {
    color,
    day: VALID_DAYS.has(day) ? day : null
  }
}

async function fetchPage(baseUrl, offset) {
  const url = `${baseUrl}/query?where=1%3D1&outFields=*&returnGeometry=false&resultOffset=${offset}&resultRecordCount=${PAGE_SIZE}&orderByFields=OBJECTID+ASC&f=json`

  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`)

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

async function importLayer({ layerName, baseUrl, hauler, reporterHash, now }) {
  console.log(`\n📥 Fetching ${layerName} zones (${PAGE_SIZE} per page)...\n`)

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let batchBuffer = []

  while (true) {
    const features = await fetchPage(baseUrl, offset)
    if (features.length === 0) break

    totalFetched += features.length

    for (const feature of features) {
      const a = feature.attributes
      const objectId = a.OBJECTID
      const unitName = a.UNIT_NAME || ''

      const { color, day } = parseUnitName(unitName)

      if (!day) {
        totalSkipped++
        continue
      }

      const addressLabel = `columbus ${layerName.toLowerCase()} zone ${objectId} ${unitName}`.toLowerCase().replace(/\s+/g, ' ').trim()
      const neighborhood = color ? `${color} Zone` : 'Columbus'

      batchBuffer.push({
        address: addressLabel,
        city: 'columbus',
        state: 'OH',
        zip_code: '',
        neighborhood,
        collection_day: day,
        recycling_week: 'A',
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler,
        data_source_url: baseUrl,
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

  console.log(`\n  ✅ ${layerName}: fetched=${totalFetched}, imported=${totalImported}, skipped=${totalSkipped}, errors=${totalErrors}`)

  return { totalFetched, totalImported, totalSkipped, totalErrors }
}

async function main() {
  console.log('🗑️  TrashAlert — Columbus OH Data Import')
  console.log('=========================================')
  console.log('Source: City of Columbus Public Service MapServer')
  console.log(`  Refuse:    Layer 11 (~15,678 zones)`)
  console.log(`  Recycling: Layer 12 (~13,301 zones)\n`)

  // Check existing Columbus records
  const { count: existingCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'columbus')

  console.log(`📊 Existing Columbus records: ${existingCount || 0}`)

  if (existingCount && existingCount > 15000) {
    console.log('⚠️  Columbus data already imported (>15,000 records). Skipping.')
    console.log('   To re-import, delete Columbus records first.')
    process.exit(0)
  }

  const reporterHash = crypto.createHash('sha256').update('city_api_columbus_oh').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  // --- Import refuse zones (Layer 11) ---
  const refuse = await importLayer({
    layerName: 'Refuse',
    baseUrl: REFUSE_URL,
    hauler: 'City of Columbus Refuse Collection',
    reporterHash,
    now,
  })

  // --- Import recycling zones (Layer 12) ---
  const recycling = await importLayer({
    layerName: 'Recycling',
    baseUrl: RECYCLING_URL,
    hauler: 'City of Columbus Refuse Collection',
    reporterHash,
    now,
  })

  // Summary
  const grandFetched = refuse.totalFetched + recycling.totalFetched
  const grandImported = refuse.totalImported + recycling.totalImported
  const grandSkipped = refuse.totalSkipped + recycling.totalSkipped
  const grandErrors = refuse.totalErrors + recycling.totalErrors

  console.log(`\n=========================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Refuse zones:    ${refuse.totalFetched} fetched, ${refuse.totalImported} imported`)
  console.log(`   Recycling zones: ${recycling.totalFetched} fetched, ${recycling.totalImported} imported`)
  console.log(`   Total fetched:   ${grandFetched}`)
  console.log(`   Total imported:  ${grandImported}`)
  console.log(`   Total skipped:   ${grandSkipped}`)
  console.log(`   Total errors:    ${grandErrors}`)

  // Verify final counts
  const { count: columbusCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'columbus')

  const { count: totalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\n📊 Final counts:`)
  console.log(`   Columbus: ${columbusCount}`)
  console.log(`   Total DB: ${totalCount}`)
}

main().catch(err => {
  console.error('\nFatal error:', err)
  process.exit(1)
})
