#!/usr/bin/env node
/**
 * Import NYC DSNY collection schedule zone data from NYC Open Data (Socrata)
 * 
 * Dataset: rv63-53db — DSNY Garbage Collection Schedule (frequency boundaries)
 * ~610 records — zone-level collection frequencies for refuse, recycling, organics, bulk
 * 
 * Each record represents a DSNY section with polygon boundaries and collection schedules.
 * Districts are coded by borough: MN=Manhattan, BKN/BKS=Brooklyn, QE/QW=Queens, BX=Bronx, SI=Staten Island
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

const DATASET_ID = 'rv63-53db'
const BATCH_SIZE = 200
const API_PAGE_SIZE = 1000

// Map DSNY district prefixes to boroughs/neighborhoods
function getBoroughFromDistrict(district) {
  if (district.startsWith('MN')) return 'Manhattan'
  if (district.startsWith('BKN') || district.startsWith('BKS')) return 'Brooklyn'
  if (district.startsWith('QE') || district.startsWith('QW')) return 'Queens'
  if (district.startsWith('BX')) return 'Bronx'
  if (district.startsWith('SI')) return 'Staten Island'
  return 'New York'
}

// Get the primary collection day from a frequency string like "Mon, Thu" or "Tue, Fri"
function getPrimaryCollectionDay(freqStr) {
  if (!freqStr) return 'monday'
  const dayMap = {
    'Mon': 'monday', 'Tue': 'tuesday', 'Wed': 'wednesday',
    'Thu': 'thursday', 'Fri': 'friday', 'Sat': 'saturday', 'Sun': 'sunday'
  }
  const first = freqStr.split(',')[0].trim()
  return dayMap[first] || 'monday'
}

async function fetchData() {
  let offset = 0
  let allRecords = []
  
  console.log(`\n📥 Fetching NYC DSNY collection schedule data (${DATASET_ID})...`)
  
  while (true) {
    // Exclude geometry to keep response small
    const url = `https://data.cityofnewyork.us/resource/${DATASET_ID}.json?$limit=${API_PAGE_SIZE}&$offset=${offset}&$select=district,section,frequency,schedulecode,freq_refuse,freq_recycling,freq_organics,freq_bulk,objectid`
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
    
    await new Promise(r => setTimeout(r, 200))
  }
  
  console.log(`  ✅ Total: ${allRecords.length} records fetched`)
  return allRecords
}

async function importToSupabase(records) {
  const now = new Date().toISOString()
  let imported = 0
  let errors = 0
  
  const rows = []
  for (const record of records) {
    const district = record.district || ''
    const section = record.section || ''
    const borough = getBoroughFromDistrict(district)
    const collDay = getPrimaryCollectionDay(record.freq_refuse)
    
    // Build a descriptive address for the zone
    const address = `nyc dsny district ${district} section ${section} - ${borough.toLowerCase()} collection zone`.toLowerCase()
    
    const reporterHash = crypto.createHash('sha256')
      .update(`city_api_nyc_dsny_${section}`)
      .digest('hex')
      .substring(0, 16)
    
    // Build schedule summary
    const schedParts = []
    if (record.freq_refuse) schedParts.push(`Refuse: ${record.freq_refuse}`)
    if (record.freq_recycling) schedParts.push(`Recycling: ${record.freq_recycling}`)
    if (record.freq_organics) schedParts.push(`Organics: ${record.freq_organics}`)
    if (record.freq_bulk) schedParts.push(`Bulk: ${record.freq_bulk}`)
    const schedSummary = schedParts.join('; ')
    
    rows.push({
      address,
      city: 'new-york',
      state: 'NY',
      zip_code: '',
      neighborhood: borough,
      collection_day: collDay,
      recycling_week: 'A', // NYC recycling is weekly in most zones
      reporter_hash: reporterHash,
      verified: true,
      verification_count: 1,
      source: 'city_api',
      data_source_type: 'api',
      hauler: 'DSNY (Department of Sanitation NYC)',
      fetched_at: now,
      raw_payload_hash: crypto.createHash('md5').update(schedSummary).digest('hex'),
    })
  }
  
  console.log(`  📋 ${rows.length} zone records to import`)
  
  // Batch insert
  for (let i = 0; i < rows.length; i += BATCH_SIZE) {
    const batch = rows.slice(i, i + BATCH_SIZE)
    
    const { error } = await supabase
      .from('schedule_reports')
      .insert(batch)
    
    if (error) {
      errors += batch.length
      if (errors <= 10) console.error(`\n  ⚠️ Insert error: ${error.message}`)
    } else {
      imported += batch.length
    }
    
    process.stdout.write(`  📦 NYC: ${imported} imported, ${errors} errors...\r`)
    await new Promise(r => setTimeout(r, 100))
  }
  
  console.log(`\n  ✅ NYC: ${imported} imported, ${errors} errors`)
  return { imported, errors }
}

async function main() {
  console.log('🗑️ TrashAlert — NYC DSNY Data Import')
  console.log('=====================================\n')
  
  const { count: existingCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'new-york')
  
  console.log(`📊 Existing NYC records: ${existingCount || 0}`)
  
  if (existingCount && existingCount > 100) {
    console.log('⚠️ NYC data already imported. Skipping.')
    process.exit(0)
  }
  
  const records = await fetchData()
  const result = await importToSupabase(records)
  
  console.log('\n=====================================')
  console.log(`🎉 Import complete!`)
  console.log(`   Imported: ${result.imported}`)
  console.log(`   Errors:   ${result.errors}`)
  
  const { count: finalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'new-york')
  
  console.log(`\n📊 NYC records: ${finalCount}`)
}

main().catch(err => {
  console.error('Fatal error:', err)
  process.exit(1)
})
