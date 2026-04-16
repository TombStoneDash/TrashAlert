#!/usr/bin/env node
/**
 * Import Milwaukee WI waste collection zone data
 *
 * Source: Milwaukee DPW Sanitation (ArcGIS MapServer)
 * https://milwaukeemaps.milwaukee.gov/arcgis/rest/services/DPW/DPW_Sanitation/MapServer
 *
 * Strategy:
 * - Query day-specific garbage collection layers (3-7) instead of the combined layer 9
 *   Layer 3 = Monday (A), Layer 4 = Tuesday (B), Layer 5 = Wednesday (C),
 *   Layer 6 = Thursday (D), Layer 7 = Friday (E)
 * - Each polygon in these layers represents a specific day's collection area
 * - Use SUM_RT (summer route ID) and other available fields
 * - ~442 route polygons total across all 5 day layers
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing env vars. Run with: node --env-file=.env.local scripts/mac-mini-imports/import-milwaukee.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const MAP_SERVER_BASE = 'https://milwaukeemaps.milwaukee.gov/arcgis/rest/services/DPW/DPW_Sanitation/MapServer'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

// Day-specific garbage collection layers
const DAY_LAYERS = [
  { layerId: 3, day: 'monday',    label: 'Monday (A)' },
  { layerId: 4, day: 'tuesday',   label: 'Tuesday (B)' },
  { layerId: 5, day: 'wednesday', label: 'Wednesday (C)' },
  { layerId: 6, day: 'thursday',  label: 'Thursday (D)' },
  { layerId: 7, day: 'friday',    label: 'Friday (E)' },
]

async function fetchPage(layerId, offset) {
  const url = `${MAP_SERVER_BASE}/${layerId}/query?where=1%3D1&outFields=*&returnGeometry=false&resultOffset=${offset}&resultRecordCount=${PAGE_SIZE}&orderByFields=OBJECTID+ASC&f=json`

  const res = await fetch(url, { signal: AbortSignal.timeout(30000) })
  if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`)

  const data = await res.json()
  if (data.error) throw new Error(`ArcGIS error: ${data.error.message}`)

  return { features: data.features || [], exceededTransferLimit: !!data.exceededTransferLimit }
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

async function importLayer(layer, reporterHash, now, globalSeen) {
  const { layerId, day, label } = layer

  console.log(`\n📥 Fetching layer ${layerId}: ${label}...`)

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let batchBuffer = []

  while (true) {
    const { features, exceededTransferLimit } = await fetchPage(layerId, offset)
    if (features.length === 0) break

    totalFetched += features.length

    for (const feature of features) {
      const a = feature.attributes

      // Use SUM_RT (summer route ID) as the primary identifier
      const sumRt = a.SUM_RT || a.OBJECTID || ''
      const routeId = String(sumRt).trim()

      if (!routeId) { totalSkipped++; continue }

      const address = `milwaukee garbage route ${routeId} ${day}`.toLowerCase().replace(/\s+/g, ' ').trim()

      // Dedup within this run (across all layers)
      if (globalSeen.has(address)) { totalSkipped++; continue }
      globalSeen.add(address)

      batchBuffer.push({
        address,
        city: 'milwaukee',
        state: 'WI',
        zip_code: '',
        neighborhood: 'Milwaukee',
        collection_day: day,
        recycling_week: 'A',
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler: 'City of Milwaukee DPW',
        data_source_url: `${MAP_SERVER_BASE}/${layerId}`,
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

    process.stdout.write(`  📊 [${label}] Fetched: ${totalFetched} | Imported: ${totalImported} | Skipped: ${totalSkipped} | Errors: ${totalErrors}    \r`)

    offset += PAGE_SIZE

    // If we got fewer than PAGE_SIZE, we're done
    if (features.length < PAGE_SIZE && !exceededTransferLimit) break

    // Polite delay between pages
    await new Promise(r => setTimeout(r, 200))
  }

  // Flush remaining
  if (batchBuffer.length > 0) {
    const result = await importBatch(batchBuffer)
    if (result.ok) totalImported += batchBuffer.length
    else totalErrors += batchBuffer.length
  }

  console.log(`\n  ✅ ${label}: Fetched ${totalFetched}, Imported ${totalImported}, Skipped ${totalSkipped}, Errors ${totalErrors}`)

  return { totalFetched, totalImported, totalSkipped, totalErrors }
}

async function main() {
  console.log('🗑️  TrashAlert — Milwaukee WI Data Import')
  console.log('==========================================')
  console.log('Source: DPW Sanitation (ArcGIS MapServer)')
  console.log(`Layers: ${DAY_LAYERS.map(l => `${l.layerId} (${l.label})`).join(', ')}\n`)

  // Check existing Milwaukee records
  const { count: existing } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'milwaukee')

  console.log(`📊 Existing Milwaukee records: ${existing || 0}`)

  if (existing && existing > 400) {
    console.log('⚠️  Milwaukee data already imported (>400 records). Skipping.')
    console.log('   To re-import, delete Milwaukee records first.')
    process.exit(0)
  }

  const reporterHash = crypto.createHash('sha256').update('city_api_milwaukee_wi').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let grandFetched = 0
  let grandImported = 0
  let grandSkipped = 0
  let grandErrors = 0
  const globalSeen = new Set()

  // Import each day-specific layer
  for (const layer of DAY_LAYERS) {
    const counts = await importLayer(layer, reporterHash, now, globalSeen)
    grandFetched += counts.totalFetched
    grandImported += counts.totalImported
    grandSkipped += counts.totalSkipped
    grandErrors += counts.totalErrors
  }

  console.log(`\n\n==========================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Fetched:  ${grandFetched}`)
  console.log(`   Imported: ${grandImported}`)
  console.log(`   Skipped:  ${grandSkipped}`)
  console.log(`   Errors:   ${grandErrors}`)

  // Verify final counts
  const { count: milwaukeeCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'milwaukee')

  const { count: totalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\n📊 Final counts:`)
  console.log(`   Milwaukee: ${milwaukeeCount}`)
  console.log(`   Total DB:  ${totalCount}`)
}

main().catch(err => {
  console.error('\nFatal error:', err)
  process.exit(1)
})
