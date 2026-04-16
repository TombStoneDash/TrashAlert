#!/usr/bin/env node
/**
 * Import Seattle WA waste collection zone schedules from Seattle GIS
 *
 * Sources:
 * - Garbage: https://services.arcgis.com/ZOyb2t4B0UYuYNYH/ArcGIS/rest/services/Residential_Garbage_Routes/FeatureServer/0
 * - Recycle: https://services.arcgis.com/ZOyb2t4B0UYuYNYH/ArcGIS/rest/services/Residential_Recycle_Routes/FeatureServer/0
 *
 * Fields used:
 * - ZONE: zone identifier
 * - CONTRACTOR: hauler name (Recology / WM)
 * - PCKUP_DAY: MON/TUE/WED/THU/FRI
 * - ROUTE_ID: route identifier
 * - SUBZONE: sub-zone identifier
 *
 * This imports zone-level polygon data (no individual addresses).
 * Each record represents a collection zone/route combination.
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing SUPABASE_URL or SUPABASE_SERVICE_KEY')
  console.error('Run with: node --env-file=.env.local scripts/mac-mini-imports/import-seattle.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const GARBAGE_URL = 'https://services.arcgis.com/ZOyb2t4B0UYuYNYH/ArcGIS/rest/services/Residential_Garbage_Routes/FeatureServer/0'
const RECYCLE_URL = 'https://services.arcgis.com/ZOyb2t4B0UYuYNYH/ArcGIS/rest/services/Residential_Recycle_Routes/FeatureServer/0'
const PAGE_SIZE = 2000   // ArcGIS max per request
const BATCH_SIZE = 500   // Supabase insert batch size

const DAY_MAP = {
  MON: 'monday',
  TUE: 'tuesday',
  WED: 'wednesday',
  THU: 'thursday',
  FRI: 'friday',
  MONDAY: 'monday',
  TUESDAY: 'tuesday',
  WEDNESDAY: 'wednesday',
  THURSDAY: 'thursday',
  FRIDAY: 'friday',
}

function normalizeDay(raw) {
  if (!raw) return null
  const key = raw.toUpperCase().trim()
  return DAY_MAP[key] || raw.toLowerCase().trim()
}

function normalizeContractor(raw) {
  if (!raw) return 'City of Seattle'
  const upper = raw.toUpperCase().trim()
  if (upper.includes('WM') || upper.includes('WASTE MANAGEMENT')) return 'Waste Management'
  if (upper.includes('RECOLOGY')) return 'Recology'
  return raw.trim()
}

async function fetchPage(baseUrl, offset) {
  const params = new URLSearchParams({
    where: '1=1',
    outFields: '*',
    returnGeometry: 'false',
    resultOffset: String(offset),
    resultRecordCount: String(PAGE_SIZE),
    orderByFields: 'OBJECTID ASC',
    f: 'json'
  })

  const url = `${baseUrl}/query?${params}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`)

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

async function fetchAllFeatures(baseUrl, label) {
  let offset = 0
  let allFeatures = []

  console.log(`\n📥 Fetching ${label} (${PAGE_SIZE} per page)...`)

  while (true) {
    const features = await fetchPage(baseUrl, offset)
    if (features.length === 0) break

    allFeatures = allFeatures.concat(features)
    process.stdout.write(`  📊 ${label}: fetched ${allFeatures.length} features so far\r`)

    offset += PAGE_SIZE

    // If we got fewer than PAGE_SIZE, we're done
    if (features.length < PAGE_SIZE) break

    // Polite delay between pages
    await new Promise(r => setTimeout(r, 200))
  }

  console.log(`  📊 ${label}: fetched ${allFeatures.length} features total     `)
  return allFeatures
}

async function main() {
  console.log('🗑️  TrashAlert — Seattle WA Data Import')
  console.log('========================================')
  console.log(`Sources:`)
  console.log(`  Garbage: ${GARBAGE_URL}`)
  console.log(`  Recycle: ${RECYCLE_URL}\n`)

  // Check existing Seattle records
  const { count: existingCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'seattle')

  console.log(`📊 Existing Seattle records: ${existingCount || 0}`)

  if (existingCount && existingCount > 5000) {
    console.log('⚠️  Seattle zone data already imported (>5K records). Skipping.')
    console.log('   To re-import, delete Seattle records first.')
    process.exit(0)
  }

  if (existingCount && existingCount > 0) {
    console.log(`ℹ️  Partial import detected (${existingCount} records). Resuming to fill gaps...`)
  }

  const reporterHash = crypto.createHash('sha256').update('city_api_seattle_wa').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  // ── Phase 1: Import Garbage Routes ──────────────────────────────

  console.log('\n── Phase 1: Garbage Routes ──────────────────────')

  const garbageFeatures = await fetchAllFeatures(GARBAGE_URL, 'Garbage Routes')

  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let batchBuffer = []
  const seen = new Set()
  const zoneRecords = new Map()  // zone -> record, for recycling matching later

  for (const feature of garbageFeatures) {
    const a = feature.attributes
    const zone = a.ZONE || a.Zone || a.zone
    const routeId = a.ROUTE_ID || a.Route_ID || a.route_id || ''
    const pickupDay = a.PCKUP_DAY || a.Pckup_Day || a.pckup_day
    const contractor = a.CONTRACTOR || a.Contractor || a.contractor
    const subzone = a.SUBZONE || a.Subzone || a.subzone || ''

    if (!zone) { totalSkipped++; continue }

    const collectionDay = normalizeDay(pickupDay)
    if (!collectionDay) { totalSkipped++; continue }

    const address = `seattle zone ${zone} route ${routeId}`.toLowerCase().replace(/\s+/g, ' ').trim()

    // Dedup by address
    if (seen.has(address)) { totalSkipped++; continue }
    seen.add(address)

    const record = {
      address,
      city: 'seattle',
      state: 'WA',
      zip_code: '',
      neighborhood: `Zone ${zone}`,
      collection_day: collectionDay,
      recycling_week: 'A',
      reporter_hash: reporterHash,
      verified: true,
      verification_count: 1,
      source: 'city_api',
      data_source_type: 'gis',
      hauler: normalizeContractor(contractor),
      data_source_url: GARBAGE_URL,
      fetched_at: now,
      raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
      lat: null,
      lng: null,
    }

    batchBuffer.push(record)
    zoneRecords.set(`${zone}|${routeId}`, record)

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

      // Small delay to be polite
      await new Promise(r => setTimeout(r, 50))
    }

    process.stdout.write(`  📊 Processed: ${seen.size} | Imported: ${totalImported} | Skipped: ${totalSkipped} | Errors: ${totalErrors}    \r`)
  }

  // Flush remaining garbage batch
  if (batchBuffer.length > 0) {
    const result = await importBatch(batchBuffer)
    if (result.ok) {
      totalImported += batchBuffer.length
    } else {
      totalErrors += batchBuffer.length
    }
    batchBuffer = []
  }

  console.log(`\n  ✅ Garbage routes: imported ${totalImported}, skipped ${totalSkipped}, errors ${totalErrors}`)

  // ── Phase 2: Import Recycle Routes ──────────────────────────────

  console.log('\n── Phase 2: Recycle Routes ──────────────────────')

  const recycleFeatures = await fetchAllFeatures(RECYCLE_URL, 'Recycle Routes')

  let recycleUpdated = 0
  let recycleNew = 0
  let recycleSkipped = 0
  let recycleErrors = 0
  const recycleSeen = new Set()
  batchBuffer = []

  for (const feature of recycleFeatures) {
    const a = feature.attributes
    const zone = a.ZONE || a.Zone || a.zone
    const routeId = a.ROUTE_ID || a.Route_ID || a.route_id || ''
    const pickupDay = a.PCKUP_DAY || a.Pckup_Day || a.pckup_day
    const contractor = a.CONTRACTOR || a.Contractor || a.contractor
    const subzone = a.SUBZONE || a.Subzone || a.subzone || ''

    if (!zone) { recycleSkipped++; continue }

    const collectionDay = normalizeDay(pickupDay)

    const zoneKey = `${zone}|${routeId}`
    const address = `seattle zone ${zone} route ${routeId}`.toLowerCase().replace(/\s+/g, ' ').trim()

    // Dedup within recycle set
    if (recycleSeen.has(address)) { recycleSkipped++; continue }
    recycleSeen.add(address)

    // Check if we already have a garbage record for this zone/route
    if (zoneRecords.has(zoneKey)) {
      // Update the existing record via upsert — set recycling_week based on recycle data
      const existing = zoneRecords.get(zoneKey)
      const updateRecord = {
        ...existing,
        recycling_week: 'A',  // Recycle route exists for this zone
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
      }

      const { error } = await supabase
        .from('schedule_reports')
        .upsert([updateRecord], {
          onConflict: 'address,city',
          ignoreDuplicates: false
        })

      if (error) {
        recycleErrors++
        if (recycleErrors <= 10) console.error(`  ⚠️  Update error for zone ${zone}: ${error.message}`)
      } else {
        recycleUpdated++
      }
    } else {
      // New zone from recycle routes not in garbage — create a record
      const record = {
        address,
        city: 'seattle',
        state: 'WA',
        zip_code: '',
        neighborhood: `Zone ${zone}`,
        collection_day: collectionDay || 'unknown',
        recycling_week: 'A',
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        data_source_type: 'gis',
        hauler: normalizeContractor(contractor),
        data_source_url: RECYCLE_URL,
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        lat: null,
        lng: null,
      }

      batchBuffer.push(record)

      // Flush batch
      if (batchBuffer.length >= BATCH_SIZE) {
        const result = await importBatch(batchBuffer)
        if (result.ok) {
          recycleNew += batchBuffer.length
        } else {
          recycleErrors += batchBuffer.length
          if (recycleErrors <= 10) console.error(`  ⚠️  Batch error: ${result.error}`)
        }
        batchBuffer = []
        await new Promise(r => setTimeout(r, 50))
      }
    }

    process.stdout.write(`  📊 Updated: ${recycleUpdated} | New: ${recycleNew} | Skipped: ${recycleSkipped} | Errors: ${recycleErrors}    \r`)
  }

  // Flush remaining recycle batch
  if (batchBuffer.length > 0) {
    const result = await importBatch(batchBuffer)
    if (result.ok) {
      recycleNew += batchBuffer.length
    } else {
      recycleErrors += batchBuffer.length
    }
  }

  console.log(`\n  ✅ Recycle routes: updated ${recycleUpdated}, new ${recycleNew}, skipped ${recycleSkipped}, errors ${recycleErrors}`)

  // ── Final Summary ───────────────────────────────────────────────

  console.log(`\n========================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Garbage fetched:   ${garbageFeatures.length}`)
  console.log(`   Garbage imported:  ${totalImported}`)
  console.log(`   Garbage skipped:   ${totalSkipped}`)
  console.log(`   Garbage errors:    ${totalErrors}`)
  console.log(`   Recycle fetched:   ${recycleFeatures.length}`)
  console.log(`   Recycle updated:   ${recycleUpdated}`)
  console.log(`   Recycle new:       ${recycleNew}`)
  console.log(`   Recycle skipped:   ${recycleSkipped}`)
  console.log(`   Recycle errors:    ${recycleErrors}`)

  // Verify final counts
  const { count: seattleCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'seattle')

  const { count: totalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\n📊 Final counts:`)
  console.log(`   Seattle: ${seattleCount}`)
  console.log(`   Total DB: ${totalCount}`)
}

main().catch(err => {
  console.error('\nFatal error:', err)
  process.exit(1)
})
