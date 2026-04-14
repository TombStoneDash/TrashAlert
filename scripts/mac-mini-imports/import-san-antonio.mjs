#!/usr/bin/env node
/**
 * Import San Antonio TX waste collection schedules
 *
 * Source: SWMD MapServer Layer 0 via public proxy
 * 357K addresses with GarbageDay, RecycleDay, OrganicsDay pre-assigned
 * Pagination via AddrKey range queries (450K - 1.1M)
 *
 * Proxy: https://gis.sanantonio.gov/proxy3/proxy.ashx?{arcgis_url}
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing env vars. Run with: node --env-file=.env.local scripts/import-san-antonio.mjs')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const PROXY_BASE = 'https://gis.sanantonio.gov/proxy3/proxy.ashx?'
const SERVICE_URL = 'https://gis.sanantonio.gov/arcgis/rest/services/SWMD/SWMDCollectionDay/MapServer/0/query'
const FIELDS = 'AddrKey,Address,GarbageDay,RecycleDay,OrganicsDay'
const RANGE_SIZE = 1000  // AddrKey range per query
const BATCH_SIZE = 500
const START_KEY = 450000
const END_KEY = 1110000

// San Antonio ZIP lookup via Layer 1 is slow — use neighborhood council districts instead
const SA_ZIPS = {
  // Major San Antonio zip codes by area
  'DOWNTOWN': '78205', 'ALAMO HEIGHTS': '78209', 'TERRELL HILLS': '78209',
  'MONTE VISTA': '78212', 'TOBIN HILL': '78212', 'MAHNCKE PARK': '78209',
  'OLMOS PARK': '78212', 'STONE OAK': '78258', 'THE DOMINION': '78257',
  'SHAVANO PARK': '78249', 'CASTLE HILLS': '78213', 'BALCONES HEIGHTS': '78201',
}

function normalizeDay(raw) {
  if (!raw) return null
  const day = raw.toLowerCase().trim()
  if (['monday','tuesday','wednesday','thursday','friday','saturday','sunday'].includes(day)) return day
  return null
}

async function fetchRange(startKey, endKey) {
  const where = `AddrKey>${startKey} AND AddrKey<=${endKey}`
  const params = new URLSearchParams({
    where,
    outFields: FIELDS,
    returnGeometry: 'false',
    f: 'json'
  })

  const url = `${PROXY_BASE}${SERVICE_URL}?${params}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)

  const text = await res.text()
  try {
    const data = JSON.parse(text)
    if (data.error) return []
    return data.features || []
  } catch {
    return []
  }
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
  console.log('🗑️  TrashAlert — San Antonio TX Data Import')
  console.log('=============================================')

  const { count: existing } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'san-antonio')

  console.log(`📊 Existing San Antonio records: ${existing || 0}`)
  if (existing && existing > 300000) {
    console.log('⚠️  Already imported. Skipping.')
    process.exit(0)
  }

  const reporterHash = crypto.createHash('sha256').update('city_api_san_antonio_tx').digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  let totalFetched = 0
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  let batchBuffer = []
  const seen = new Set()

  console.log(`\n📥 Fetching San Antonio addresses (AddrKey ${START_KEY}-${END_KEY})...\n`)

  for (let key = START_KEY; key < END_KEY; key += RANGE_SIZE) {
    try {
      const features = await fetchRange(key, key + RANGE_SIZE)
      totalFetched += features.length

      for (const f of features) {
        const a = f.attributes
        const address = (a.Address || '').toLowerCase().replace(/\s+/g, ' ').trim()
        if (!address || address.length < 3) { totalSkipped++; continue }

        const dedupKey = address
        if (seen.has(dedupKey)) { totalSkipped++; continue }
        seen.add(dedupKey)

        const garbageDay = normalizeDay(a.GarbageDay)
        if (!garbageDay) { totalSkipped++; continue }

        batchBuffer.push({
          address,
          city: 'san-antonio',
          state: 'TX',
          zip_code: '',
          neighborhood: 'San Antonio',
          collection_day: garbageDay,
          recycling_week: 'A',
          reporter_hash: reporterHash,
          verified: true,
          verification_count: 1,
          source: 'city_api',
          fetched_at: now,
          raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
          hauler: 'City of San Antonio Solid Waste Management',
          data_source_url: 'https://gis.sanantonio.gov/arcgis/rest/services/SWMD/SWMDCollectionDay/MapServer/0',
          data_source_type: 'gis',
        })

        if (batchBuffer.length >= BATCH_SIZE) {
          const result = await importBatch(batchBuffer)
          if (result.ok) totalImported += batchBuffer.length
          else { totalErrors += batchBuffer.length; if (totalErrors <= 2500) console.error(`  ⚠️  ${result.error}`) }
          batchBuffer = []
          await new Promise(r => setTimeout(r, 50))
        }
      }
    } catch (err) {
      // Skip failed ranges silently, retry logic not needed for one-time import
    }

    if ((key - START_KEY) % 10000 === 0) {
      process.stdout.write(`  📊 Key: ${key}/${END_KEY} | Fetched: ${totalFetched} | Imported: ${totalImported} | Skipped: ${totalSkipped} | Errors: ${totalErrors}    \r`)
    }

    // Polite delay between range queries
    await new Promise(r => setTimeout(r, 300))
  }

  // Flush remaining
  if (batchBuffer.length > 0) {
    const result = await importBatch(batchBuffer)
    if (result.ok) totalImported += batchBuffer.length
    else totalErrors += batchBuffer.length
  }

  console.log(`\n\n=============================================`)
  console.log(`🎉 Import complete!`)
  console.log(`   Fetched:  ${totalFetched}`)
  console.log(`   Imported: ${totalImported}`)
  console.log(`   Skipped:  ${totalSkipped}`)
  console.log(`   Errors:   ${totalErrors}`)

  const { count: saCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'san-antonio')

  const { count: total } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })

  console.log(`\n📊 Final: San Antonio=${saCount}, Total=${total}`)
}

main().catch(err => { console.error('\nFatal:', err); process.exit(1) })
