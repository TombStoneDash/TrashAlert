#!/usr/bin/env node
/**
 * Import Austin TX recycling schedule data from City of Austin Open Data (Socrata)
 * 
 * Datasets:
 * - Monday: 8zu2-guks (~41K)
 * - Tuesday: rb6p-jsp4 (~32K)
 * - Wednesday: ur6a-fvpc (~185K)
 * - Thursday: nynz-w2da (~39K)
 * - Friday: 3w87-zbw7 (~34K)
 * Total: ~331K addresses
 */

import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY

if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Missing SUPABASE_URL or SUPABASE_SERVICE_KEY')
  process.exit(1)
}

const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const DATASETS = [
  { id: '8zu2-guks', day: 'monday', label: 'Monday' },
  { id: 'rb6p-jsp4', day: 'tuesday', label: 'Tuesday' },
  { id: 'ur6a-fvpc', day: 'wednesday', label: 'Wednesday' },
  { id: 'nynz-w2da', day: 'thursday', label: 'Thursday' },
  { id: '3w87-zbw7', day: 'friday', label: 'Friday' },
]

const BATCH_SIZE = 500
const API_PAGE_SIZE = 5000

function normalizeAddress(record) {
  // Build address from components: house_no + st_dir + street_nam + street_typ + unit_no
  const parts = []
  if (record.house_no) parts.push(record.house_no.trim())
  if (record.st_dir) parts.push(record.st_dir.trim())
  if (record.street_nam) parts.push(record.street_nam.trim())
  if (record.street_typ) parts.push(record.street_typ.trim())
  
  let address = parts.join(' ').toLowerCase()
  
  // Append unit if present
  if (record.unit_no) {
    address += ` ${record.unit_no.trim().toLowerCase()}`
  }
  
  return address
}

function getNeighborhood(zip) {
  // Austin ZIP code to area mapping for neighborhood field
  const zipAreas = {
    '78701': 'Downtown', '78702': 'East Austin', '78703': 'Tarrytown/Clarksville',
    '78704': 'South Austin/Travis Heights', '78705': 'University/Hyde Park',
    '78721': 'East Austin', '78722': 'Cherrywood', '78723': 'Windsor Park',
    '78724': 'Northeast Austin', '78725': 'Southeast Austin', '78726': 'Northwest Hills',
    '78727': 'North Austin', '78728': 'Wells Branch', '78729': 'Milwood/McNeil',
    '78730': 'River Place', '78731': 'Northwest Hills', '78732': 'Steiner Ranch',
    '78733': 'Barton Creek', '78734': 'Lakeway/Bee Cave', '78735': 'Circle C/Southwest',
    '78736': 'Oak Hill', '78737': 'Shady Hollow', '78738': 'Bee Cave',
    '78739': 'Circle C Ranch', '78741': 'Southeast Austin', '78742': 'Montopolis',
    '78744': 'South Austin/Onion Creek', '78745': 'South Austin/Westgate',
    '78746': 'West Lake Hills', '78747': 'South Austin', '78748': 'Southpark Meadows',
    '78749': 'Southwest Austin', '78750': 'Anderson Mill', '78751': 'Brentwood/Crestview',
    '78752': 'North Austin/North Loop', '78753': 'North Austin/Copperfield',
    '78754': 'Northeast Austin', '78756': 'Rosedale/Allandale', '78757': 'Crestview/Brentwood',
    '78758': 'North Austin', '78759': 'Great Hills/Arboretum',
  }
  return zipAreas[zip] || 'Austin'
}

async function fetchDataset(datasetId, day, label) {
  let offset = 0
  let allRecords = []
  
  console.log(`\n📥 Fetching ${label} dataset (${datasetId})...`)
  
  while (true) {
    const url = `https://data.austintexas.gov/resource/${datasetId}.json?$limit=${API_PAGE_SIZE}&$offset=${offset}`
    const res = await fetch(url)
    if (!res.ok) {
      console.error(`  ❌ API error: ${res.status} ${res.statusText}`)
      break
    }
    
    const data = await res.json()
    if (data.length === 0) break
    
    allRecords.push(...data)
    offset += API_PAGE_SIZE
    process.stdout.write(`  📊 Fetched ${allRecords.length} records...\r`)
    
    // Small delay to be polite to the API
    await new Promise(r => setTimeout(r, 200))
  }
  
  console.log(`  ✅ ${label}: ${allRecords.length} total records`)
  return allRecords
}

async function importToSupabase(records, day) {
  const reporterHash = crypto.createHash('sha256').update('city_api_austin_tx').digest('hex').substring(0, 16)
  const now = new Date().toISOString()
  let imported = 0
  let skipped = 0
  let errors = 0
  
  for (let i = 0; i < records.length; i += BATCH_SIZE) {
    const batch = records.slice(i, i + BATCH_SIZE)
    
    const rows = batch.map(record => {
      const address = normalizeAddress(record)
      if (!address || address.length < 3) return null
      
      const zip = record.zip || ''
      const collectionWeek = (record.collection_week || 'A').toUpperCase()
      
      return {
        address,
        city: 'austin',
        state: 'TX',
        zip_code: zip,
        neighborhood: getNeighborhood(zip),
        collection_day: day,
        recycling_week: collectionWeek === 'B' ? 'B' : 'A',
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        fetched_at: now,
        raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(record)).digest('hex'),
      }
    }).filter(Boolean)
    
    if (rows.length === 0) {
      skipped += batch.length
      continue
    }
    
    const { error } = await supabase
      .from('schedule_reports')
      .upsert(rows, { 
        onConflict: 'address,city',
        ignoreDuplicates: true 
      })
    
    if (error) {
      // If upsert fails (no unique constraint on address,city), fall back to insert
      const { error: insertError } = await supabase
        .from('schedule_reports')
        .insert(rows)
      
      if (insertError) {
        errors += rows.length
        if (errors <= 5) console.error(`  ⚠️ Insert error: ${insertError.message}`)
      } else {
        imported += rows.length
      }
    } else {
      imported += rows.length
    }
    
    process.stdout.write(`  📦 ${day}: ${imported} imported, ${skipped} skipped, ${errors} errors (batch ${Math.floor(i/BATCH_SIZE) + 1}/${Math.ceil(records.length/BATCH_SIZE)})...\r`)
    
    // Small delay between batches
    await new Promise(r => setTimeout(r, 100))
  }
  
  console.log(`\n  ✅ ${day}: ${imported} imported, ${skipped} skipped, ${errors} errors`)
  return { imported, skipped, errors }
}

async function main() {
  console.log('🗑️ TrashAlert — Austin TX Data Import')
  console.log('=====================================\n')
  
  // Check current Austin count
  const { count: existingCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'austin')
  
  console.log(`📊 Existing Austin records: ${existingCount || 0}`)
  
  if (existingCount && existingCount > 100000) {
    console.log('⚠️ Austin data already imported (>100K records). Skipping to avoid duplicates.')
    console.log('   To re-import, delete Austin records first.')
    process.exit(0)
  }
  
  let totalImported = 0
  let totalSkipped = 0
  let totalErrors = 0
  
  for (const dataset of DATASETS) {
    const records = await fetchDataset(dataset.id, dataset.day, dataset.label)
    const result = await importToSupabase(records, dataset.day)
    totalImported += result.imported
    totalSkipped += result.skipped
    totalErrors += result.errors
  }
  
  console.log('\n=====================================')
  console.log(`🎉 Import complete!`)
  console.log(`   Imported: ${totalImported}`)
  console.log(`   Skipped:  ${totalSkipped}`)
  console.log(`   Errors:   ${totalErrors}`)
  
  // Verify total count
  const { count: finalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
  
  const { count: austinCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'austin')
  
  console.log(`\n📊 Final counts:`)
  console.log(`   Total records: ${finalCount}`)
  console.log(`   Austin records: ${austinCount}`)
  console.log(`   San Diego records: ${(finalCount || 0) - (austinCount || 0)}`)
}

main().catch(err => {
  console.error('Fatal error:', err)
  process.exit(1)
})
