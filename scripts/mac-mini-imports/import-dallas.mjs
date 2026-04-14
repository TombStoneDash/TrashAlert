#!/usr/bin/env node
/**
 * Import Dallas TX waste collection schedules
 *
 * Strategy:
 * 1. Load 25 garbage zone polygons from Layer 19 (DOW = day of week)
 * 2. Fetch 545K tax account address points from Layer 0 with coordinates
 * 3. Point-in-polygon to assign each address its collection day
 * 4. Batch import to Supabase
 *
 * Source: https://gis.dallascityhall.com/arcgis/rest/services/Crm_public/CrmLayers/MapServer
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'
import { readFileSync } from 'fs'
import booleanPointInPolygon from '@turf/boolean-point-in-polygon'
import { point } from '@turf/helpers'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing env vars. Run with: node --env-file=.env.local scripts/import-dallas.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const ADDR_URL = 'https://gis.dallascityhall.com/arcgis/rest/services/Crm_public/CrmLayers/MapServer/0/query'
const PAGE_SIZE = 2000
const BATCH_SIZE = 500

function loadZones(filepath) {
  const raw = readFileSync(filepath, 'utf8')
  const geojson = JSON.parse(raw)
  return geojson.features.filter(f => f.geometry && f.properties.DOW)
}

function findZoneDay(lng, lat, zones) {
  const pt = point([lng, lat])
  for (const zone of zones) {
    try {
      if (booleanPointInPolygon(pt, zone)) return zone.properties.DOW.toLowerCase()
    } catch { /* skip */ }
  }
  return null
}

async function fetchAddressPage(offset) {
  const params = new URLSearchParams({
    where: "ResCom='R'",  // Residential only
    outFields: 'SiteAddrNum,SiteStreetname,CityJuris,OwnerZip',
    outSR: '4326',
    returnGeometry: 'true',
    geometryPrecision: 6,
    resultOffset: String(offset),
    resultRecordCount: String(PAGE_SIZE),
    orderByFields: 'OBJECTID ASC',
    f: 'json'
  })

  const res = await fetch(`${ADDR_URL}?${params}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  if (data.error) throw new Error(data.error.message)
  return data.features || []
}

async function importBatch(rows) {
  const { error } = await supabase
    .from('schedule_reports')
    .upsert(rows, { onConflict: 'address,city', ignoreDuplicates: true })
  if (error) {
    const { error: e2 } = await supabase.from('schedule_reports').insert(rows)
    if (e2) return { ok: false, error: e2.message }
  }
  return { ok: true }
}

async function main() {
  console.log('🗑️  TrashAlert — Dallas TX Data Import')
  console.log('=======================================')

  const { count: existing } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'dallas')

  console.log(`📊 Existing Dallas records: ${existing || 0}`)
  if (existing && existing > 400000) {
    console.log('⚠️  Already imported. Skipping.')
    process.exit(0)
  }

  // Load zone polygons
  console.log('\n📍 Loading garbage zone polygons...')
  const garbageZones = loadZones('data/dallas-garbage-zones.geojson')
  console.log(`   ${garbageZones.length} zones loaded`)

  const reporterHash = crypto.createHash('sha256').update('city_api_dallas_tx').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let offset = 0
  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let noZoneCount = 0
  let batchBuffer = []
  const seen = new Set()

  console.log('\n📥 Fetching Dallas addresses (residential)...\n')

  while (true) {
    const features = await fetchAddressPage(offset)
    if (features.length === 0) break

    totalFetched += features.length

    for (const f of features) {
      const a = f.attributes
      const geom = f.geometry

      if (!a.SiteAddrNum || !a.SiteStreetname) { totalSkipped++; continue }

      const address = `${a.SiteAddrNum} ${a.SiteStreetname}`.toLowerCase().replace(/\s+/g, ' ').trim()
      if (address.length < 3) { totalSkipped++; continue }

      if (seen.has(address)) { totalSkipped++; continue }
      seen.add(address)

      // Get coordinates — Dallas layer returns point geometry
      let lng, lat
      if (geom && geom.x && geom.y) {
        lng = geom.x
        lat = geom.y
      } else { totalSkipped++; continue }

      // Spatial join to find collection day
      const collectionDay = findZoneDay(lng, lat, garbageZones)
      if (!collectionDay) { noZoneCount++; totalSkipped++; continue }

      const zip = (a.OwnerZip || '').substring(0, 5)

      batchBuffer.push({
        address,
        city: 'dallas',
        state: 'TX',
        zip_code: zip || '',
        neighborhood: 'Dallas',
        collection_day: collectionDay,
        recycling_week: 'A',
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
        hauler: 'City of Dallas Sanitation Services',
        data_source_url: 'https://gis.dallascityhall.com/arcgis/rest/services/Crm_public/CrmLayers/MapServer',
        data_source_type: 'gis',
        lat,
        lng,
      })

      if (batchBuffer.length >= BATCH_SIZE) {
        const result = await importBatch(batchBuffer)
        if (result.ok) totalImported += batchBuffer.length
        else { totalErrors += batchBuffer.length; if (totalErrors <= 2500) console.error(`  ⚠️  ${result.error}`) }
        batchBuffer = []
        await new Promise(r => setTimeout(r, 50))
      }
    }

    offset += PAGE_SIZE
    if (totalFetched % 10000 === 0) {
      process.stdout.write(`  📊 Fetched: ${totalFetched} | Imported: ${totalImported} | Skipped: ${totalSkipped} (${noZoneCount} no zone) | Errors: ${totalErrors}    \r`)
    }

    if (features.length < PAGE_SIZE) break
    await new Promise(r => setTimeout(r, 200))
  }

  if (batchBuffer.length > 0) {
    const result = await importBatch(batchBuffer)
    if (result.ok) totalImported += batchBuffer.length
    else totalErrors += batchBuffer.length
  }

  console.log(`\n\n=======================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Fetched:  ${totalFetched}`)
  console.log(`   Imported: ${totalImported}`)
  console.log(`   Skipped:  ${totalSkipped} (${noZoneCount} outside zones)`)
  console.log(`   Errors:   ${totalErrors}`)

  const { count: c } = await supabase.from('schedule_reports').select('*', { count: 'exact', head: true }).eq('city', 'dallas')
  const { count: t } = await supabase.from('schedule_reports').select('*', { count: 'exact', head: true })
  console.log(`\n📊 Final: Dallas=${c}, Total=${t}`)
}

main().catch(err => { console.error('\nFatal:', err); process.exit(1) })
