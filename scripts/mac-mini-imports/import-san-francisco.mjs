#!/usr/bin/env node
/**
 * Import San Francisco street sweeping schedule data from DataSF (Socrata)
 * 
 * Dataset: yhqp-riqs — Street Sweeping Schedule
 * ~37,878 records — block-level street sweeping schedules
 * Fields: corridor (street name), limits (block range), weekday, fromhour, tohour, week1-5
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

const DATASET_ID = 'yhqp-riqs'
const BATCH_SIZE = 500
const API_PAGE_SIZE = 5000

// SF ZIP codes to neighborhood mapping
const SF_NEIGHBORHOODS = {
  // We'll derive neighborhood from street name patterns since dataset doesn't include ZIP
  'Market St': 'Downtown/SOMA',
  'Mission St': 'Mission',
  'Valencia St': 'Mission',
  'Castro St': 'Castro',
  'Haight St': 'Haight-Ashbury',
  'Divisadero St': 'NoPa',
  'Fillmore St': 'Western Addition',
  'Geary Blvd': 'Richmond',
  'Clement St': 'Richmond',
  'Irving St': 'Sunset',
  'Judah St': 'Sunset',
  'Taraval St': 'Sunset',
  'Ocean Ave': 'Ingleside',
  'Columbus Ave': 'North Beach',
  'Broadway': 'North Beach',
  'Grant Ave': 'Chinatown',
  'Stockton St': 'Chinatown',
  'Van Ness Ave': 'Civic Center',
  'Potrero Ave': 'Potrero Hill',
  '3rd St': 'Bayview',
  'Bayshore Blvd': 'Bayview',
}

function getNeighborhood(corridor) {
  if (!corridor) return 'San Francisco'
  
  // Check direct matches
  for (const [street, hood] of Object.entries(SF_NEIGHBORHOODS)) {
    if (corridor.toLowerCase().includes(street.toLowerCase())) return hood
  }
  
  // Check numbered avenues (Richmond/Sunset)
  const aveMatch = corridor.match(/^(\d+)(st|nd|rd|th)\s+Ave$/i)
  if (aveMatch) {
    const num = parseInt(aveMatch[1])
    if (num <= 25) return 'Richmond'
    return 'Sunset'
  }
  
  return 'San Francisco'
}

const VALID_DAYS = new Set(['monday', 'tuesday', 'wednesday', 'thursday', 'friday'])

function normalizeWeekday(weekday) {
  const map = {
    'Mon': 'monday',
    'Tues': 'tuesday',
    'Tue': 'tuesday',
    'Wed': 'wednesday',
    'Thu': 'thursday',
    'Thur': 'thursday',
    'Fri': 'friday',
    'Sat': 'saturday',
    'Sun': 'sunday',
  }
  return map[weekday] || weekday?.toLowerCase() || 'unknown'
}

function getRecyclingWeek(record) {
  // Use week pattern to determine A/B week
  // If week1 and week3 are on, it's "A" pattern
  // If week2 and week4 are on, it's "B" pattern
  // If all weeks, it's weekly (return 'A' as default)
  const w1 = record.week1 === '1'
  const w2 = record.week2 === '1'
  const w3 = record.week3 === '1'
  const w4 = record.week4 === '1'
  
  if (w1 && w2 && w3 && w4) return 'A' // weekly
  if (w1 && w3 && !w2 && !w4) return 'A'
  if (w2 && w4 && !w1 && !w3) return 'B'
  return 'A'
}

async function fetchAllRecords() {
  let offset = 0
  let allRecords = []
  
  console.log(`\n📥 Fetching San Francisco street sweeping data (${DATASET_ID})...`)
  
  while (true) {
    const url = `https://data.sfgov.org/resource/${DATASET_ID}.json?$limit=${API_PAGE_SIZE}&$offset=${offset}`
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
  let skipped = 0
  let errors = 0
  
  for (let i = 0; i < records.length; i += BATCH_SIZE) {
    const batch = records.slice(i, i + BATCH_SIZE)
    
    const rows = batch.map(record => {
      const corridor = record.corridor || ''
      const limits = record.limits || ''
      const blockside = record.blockside || ''
      
      // Build address: "corridor (limits) [blockside]"
      const address = `${corridor} ${limits}`.trim().toLowerCase()
      if (!address || address.length < 3) return null
      
      const weekday = normalizeWeekday(record.weekday)
      
      // Skip non-weekday records — DB constraint only allows monday-friday
      if (!VALID_DAYS.has(weekday)) return null
      
      const neighborhood = getNeighborhood(corridor)
      
      const reporterHash = crypto.createHash('sha256')
        .update(`city_api_san-francisco_${address}_${blockside}`)
        .digest('hex')
        .substring(0, 16)
      
      return {
        address: `${corridor.toLowerCase()} (${limits.toLowerCase()}) ${blockside.toLowerCase()}`.trim(),
        city: 'san-francisco',
        state: 'CA',
        zip_code: '', // Not available in this dataset
        neighborhood,
        collection_day: weekday,
        recycling_week: getRecyclingWeek(record),
        reporter_hash: reporterHash,
        verified: true,
        verification_count: 1,
        source: 'city_api',
        data_source_type: 'api',
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
      .insert(rows)
    
    if (error) {
      errors += rows.length
      if (errors <= 2500) console.error(`\n  ⚠️ Insert error (batch ${Math.floor(i/BATCH_SIZE) + 1}): ${error.message} | code: ${error.code} | details: ${error.details}`)
    } else {
      imported += rows.length
    }
    
    process.stdout.write(`  📦 SF: ${imported} imported, ${skipped} skipped, ${errors} errors (batch ${Math.floor(i/BATCH_SIZE) + 1}/${Math.ceil(records.length/BATCH_SIZE)})...\r`)
    
    await new Promise(r => setTimeout(r, 100))
  }
  
  console.log(`\n  ✅ SF: ${imported} imported, ${skipped} skipped, ${errors} errors`)
  return { imported, skipped, errors }
}

async function main() {
  console.log('🗑️ TrashAlert — San Francisco Street Sweeping Data Import')
  console.log('==========================================================\n')
  
  // Check current SF count
  const { count: existingCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'san-francisco')
  
  console.log(`📊 Existing San Francisco records: ${existingCount || 0}`)
  
  if (existingCount && existingCount > 30000) {
    console.log('⚠️ SF data already imported (>30K records). Skipping to avoid duplicates.')
    console.log('   To re-import, delete SF records first.')
    process.exit(0)
  }
  
  const records = await fetchAllRecords()
  const result = await importToSupabase(records)
  
  console.log('\n==========================================================')
  console.log(`🎉 Import complete!`)
  console.log(`   Imported: ${result.imported}`)
  console.log(`   Skipped:  ${result.skipped}`)
  console.log(`   Errors:   ${result.errors}`)
  
  // Verify
  const { count: finalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'san-francisco')
  
  console.log(`\n📊 San Francisco records: ${finalCount}`)
}

main().catch(err => {
  console.error('Fatal error:', err)
  process.exit(1)
})
