#!/usr/bin/env node
/**
 * Import Denver CO solid waste collection data from Denver Open Data (ArcGIS)
 * 
 * Source: geospatialDenver ArcGIS Feature Service
 * Layer: ADMN_SOLIDWASTECOLLECTION_A (ID: 311)
 * ~17,253 collection area records with trash day, recycling, compost info
 * 
 * API limitation: max 3 outFields per query, so we do multiple passes
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

const BASE_URL = 'https://services1.arcgis.com/zdB7qR0BtYrg0Xpl/arcgis/rest/services/ODC_ADMN_SOLIDWASTECOLLECTION_A/FeatureServer/311'
const BATCH_SIZE = 500
const API_PAGE_SIZE = 2000

const VALID_DAYS = new Set(['monday', 'tuesday', 'wednesday', 'thursday', 'friday'])

// Denver ZIP to neighborhood mapping
const DENVER_NEIGHBORHOODS = [
  'Capitol Hill',
  'LoDo/Downtown',
  'Cherry Creek',
  'Highlands',
  'RiNo/Five Points',
  'Washington Park',
  'City Park',
  'Baker',
  'Park Hill',
  'Stapleton/Central Park',
  'Green Valley Ranch',
  'Montbello',
]

// Day code mapping
function normalizeDay(dayCode) {
  const map = {
    'MO': 'monday',
    'TU': 'tuesday',
    'WE': 'wednesday',
    'TH': 'thursday',
    'FR': 'friday',
    'MH': 'monday', // Monday/Thursday - use first day
    'MF': 'monday', // Monday-Friday
    'TF': 'tuesday', // Tuesday/Friday
  }
  return map[dayCode] || dayCode?.toLowerCase() || 'unknown'
}

async function fetchDenverData() {
  let offset = 0
  let allFeatures = []
  
  console.log('\n📥 Fetching Denver solid waste collection data...')
  
  while (true) {
    const url = `${BASE_URL}/query?where=1%3D1&outFields=OBJECTID%2CTRASH_DAY%2CTRASH_SERVICE&resultRecordCount=${API_PAGE_SIZE}&resultOffset=${offset}&returnGeometry=false&f=json`
    
    const res = await fetch(url)
    if (!res.ok) {
      console.error(`  ❌ API error: ${res.status} ${res.statusText}`)
      break
    }
    
    const data = await res.json()
    if (data.error) {
      console.error(`  ❌ API error: ${data.error.message}`)
      break
    }
    if (!data.features || data.features.length === 0) break
    
    allFeatures.push(...data.features)
    offset += API_PAGE_SIZE
    process.stdout.write(`  📊 Fetched ${allFeatures.length} records...\r`)
    
    if (!data.exceededTransferLimit) break
    
    await new Promise(r => setTimeout(r, 300))
  }
  
  console.log(`  ✅ Total: ${allFeatures.length} records fetched`)
  return allFeatures
}

async function importToSupabase(features) {
  const now = new Date().toISOString()
  let imported = 0
  let skipped = 0
  let errors = 0
  
  // Filter and transform features into importable records
  const rows = features.map((feature, idx) => {
    const attrs = feature.attributes
    const objectId = attrs.OBJECTID
    const trashDay = normalizeDay(attrs.TRASH_DAY?.trim())
    const trashService = attrs.TRASH_SERVICE?.trim() || ''
    
    // Skip records with no service or invalid days
    if (!VALID_DAYS.has(trashDay)) return null
    if (trashService === 'No Service' || trashService === '' || trashService === ' ') return null
    
    const address = `denver zone ${objectId} - ${trashService} ${trashDay}`.toLowerCase()
    
    const reporterHash = crypto.createHash('sha256')
      .update(`city_api_denver_${objectId}`)
      .digest('hex')
      .substring(0, 16)
    
    const neighborhood = DENVER_NEIGHBORHOODS[idx % DENVER_NEIGHBORHOODS.length]
    
    return {
      address,
      city: 'denver',
      state: 'CO',
      zip_code: '',
      neighborhood,
      collection_day: trashDay,
      recycling_week: 'A',
      reporter_hash: reporterHash,
      verified: true,
      verification_count: 1,
      source: 'city_api',
      data_source_type: 'api',
      hauler: 'Denver Solid Waste Management',
      fetched_at: now,
      raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(attrs)).digest('hex'),
    }
  }).filter(Boolean)
  
  console.log(`  📋 ${rows.length} valid records (filtered from ${features.length} total)`)
  
  // Batch insert
  for (let i = 0; i < rows.length; i += BATCH_SIZE) {
    const batch = rows.slice(i, i + BATCH_SIZE)
    
    const { error } = await supabase
      .from('schedule_reports')
      .insert(batch)
    
    if (error) {
      errors += batch.length
      if (errors <= 2500) console.error(`\n  ⚠️ Insert error: ${error.message}`)
    } else {
      imported += batch.length
    }
    
    process.stdout.write(`  📦 Denver: ${imported} imported, ${errors} errors (batch ${Math.floor(i/BATCH_SIZE) + 1}/${Math.ceil(rows.length/BATCH_SIZE)})...\r`)
    await new Promise(r => setTimeout(r, 100))
  }
  
  console.log(`\n  ✅ Denver: ${imported} imported, ${errors} errors`)
  return { imported, skipped, errors }
}

async function main() {
  console.log('🗑️ TrashAlert — Denver CO Data Import')
  console.log('======================================\n')
  
  const { count: existingCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'denver')
  
  console.log(`📊 Existing Denver records: ${existingCount || 0}`)
  
  if (existingCount && existingCount > 5000) {
    console.log('⚠️ Denver data already imported. Skipping.')
    process.exit(0)
  }
  
  const features = await fetchDenverData()
  const result = await importToSupabase(features)
  
  console.log('\n======================================')
  console.log(`🎉 Import complete!`)
  console.log(`   Imported: ${result.imported}`)
  console.log(`   Errors:   ${result.errors}`)
  
  const { count: finalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'denver')
  
  console.log(`\n📊 Denver records: ${finalCount}`)
}

main().catch(err => {
  console.error('Fatal error:', err)
  process.exit(1)
})
