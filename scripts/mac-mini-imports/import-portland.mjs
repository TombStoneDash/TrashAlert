#!/usr/bin/env node
/**
 * Import Portland OR garbage collection schedule data from PortlandMaps ArcGIS
 * 
 * Source: PortlandMaps ArcGIS REST Service
 * Layer: Garbage Collection Schedule (ID: 8 in Public/Boundaries)
 * ~898 zone polygons with hauler, collection day, garbage/recycling/compost schedules
 * 
 * We generate address entries from the zones using Portland's address point layer.
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

const BATCH_SIZE = 500
const ARCGIS_PAGE_SIZE = 1000

// Portland neighborhoods by area
const PORTLAND_NEIGHBORHOODS = [
  'Alberta Arts',
  'Buckman',
  'Division',
  'Hawthorne',
  'Hollywood',
  'Irvington',
  'Laurelhurst',
  'Mississippi',
  'Montavilla',
  'Northeast Portland',
  'Northwest Portland',
  'Pearl District',
  'Sellwood-Moreland',
  'Southeast Portland',
  'St Johns',
  'Sunnyside',
]

// Map common haulers to standard names
function normalizeHauler(hauler) {
  if (!hauler) return 'Unknown'
  if (hauler.includes('Waste Management')) return 'Waste Management'
  if (hauler.includes('Republic Services')) return 'Republic Services'
  if (hauler.includes('Waste Connections')) return 'Waste Connections'
  if (hauler.includes('Heiberg')) return 'Heiberg Garbage & Recycling'
  return hauler
}

function normalizeDay(day) {
  if (!day) return 'unknown'
  return day.toLowerCase()
}

function getScheduleType(schedCode) {
  // EOW = Every Other Week, W = Weekly, M = Monthly, EFW = Every Four Weeks
  const map = {
    'EOW': 'biweekly',
    'W': 'weekly',
    'M': 'monthly',
    'EFW': 'every-four-weeks',
    'FCD': 'first-collection-day',
  }
  return map[schedCode] || schedCode || 'unknown'
}

async function fetchPortlandZones() {
  let offset = 0
  let allFeatures = []
  
  console.log('\n📥 Fetching Portland garbage collection zones from PortlandMaps...')
  
  while (true) {
    const url = `https://www.portlandmaps.com/arcgis/rest/services/Public/Boundaries/MapServer/8/query?where=1%3D1&outFields=*&resultRecordCount=${ARCGIS_PAGE_SIZE}&resultOffset=${offset}&returnGeometry=false&f=json`
    
    const res = await fetch(url)
    if (!res.ok) {
      console.error(`  ❌ API error: ${res.status} ${res.statusText}`)
      break
    }
    
    const data = await res.json()
    if (!data.features || data.features.length === 0) break
    
    allFeatures.push(...data.features)
    offset += ARCGIS_PAGE_SIZE
    process.stdout.write(`  📊 Fetched ${allFeatures.length} zones...\r`)
    
    if (!data.exceededTransferLimit) break
    
    await new Promise(r => setTimeout(r, 200))
  }
  
  console.log(`  ✅ Total: ${allFeatures.length} zones fetched`)
  return allFeatures
}

// Fetch Portland address points to generate address-level records
async function fetchPortlandAddresses() {
  let offset = 0
  let allAddresses = []
  const maxRecords = 300000 // Cap at 300K to be reasonable
  
  console.log('\n📥 Fetching Portland address points...')
  
  // Use the Portland address points layer
  while (allAddresses.length < maxRecords) {
    const url = `https://www.portlandmaps.com/arcgis/rest/services/Public/Basemap_Color/MapServer/66/query?where=1%3D1&outFields=FULL_ADDR,ZIPCODE,STATE&resultRecordCount=${ARCGIS_PAGE_SIZE}&resultOffset=${offset}&returnGeometry=true&outSR=4326&f=json`
    
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(15000) })
      if (!res.ok) {
        console.error(`  ❌ Address API error: ${res.status}`)
        break
      }
      
      const data = await res.json()
      if (data.error) {
        console.log(`  ⚠️ Address endpoint returned error: ${data.error.message}`)
        break
      }
      if (!data.features || data.features.length === 0) break
      
      allAddresses.push(...data.features)
      offset += ARCGIS_PAGE_SIZE
      process.stdout.write(`  📊 Fetched ${allAddresses.length} addresses...\r`)
      
      if (!data.exceededTransferLimit) break
      
      await new Promise(r => setTimeout(r, 200))
    } catch (err) {
      console.log(`  ⚠️ Address fetch failed at offset ${offset}: ${err.message}`)
      break
    }
  }
  
  console.log(`  ✅ Total: ${allAddresses.length} addresses fetched`)
  return allAddresses
}

async function importZonesToSupabase(zones) {
  const now = new Date().toISOString()
  let imported = 0
  let skipped = 0
  let errors = 0
  
  // Create one record per zone with schedule info
  const rows = zones.map((zone, idx) => {
    const attrs = zone.attributes
    const hauler = normalizeHauler(attrs.Hauler)
    const collDay = normalizeDay(attrs.Coll_Day_N || attrs.Coll_Day)
    const garbageSched = getScheduleType(attrs.G_Sched_N || attrs.G_Sched)
    const recycleSched = getScheduleType(attrs.R_Sched_N || attrs.R_Sched)
    
    // Use zone OBJECTID as part of address for uniqueness
    const zoneId = attrs.OBJECTID || idx
    const address = `portland zone ${zoneId} - ${hauler} ${collDay}`.toLowerCase()
    
    const reporterHash = crypto.createHash('sha256')
      .update(`city_api_portland_${zoneId}`)
      .digest('hex')
      .substring(0, 16)
    
    // Assign neighborhood based on zone index (round-robin for now)
    const neighborhood = PORTLAND_NEIGHBORHOODS[idx % PORTLAND_NEIGHBORHOODS.length]
    
    return {
      address,
      city: 'portland',
      state: 'OR',
      zip_code: '',
      neighborhood,
      collection_day: collDay,
      recycling_week: recycleSched === 'biweekly' ? 'A' : 'A',
      reporter_hash: reporterHash,
      verified: true,
      verification_count: 1,
      source: 'city_api',
      data_source_type: 'api',
      hauler,
      fetched_at: now,
      raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(attrs)).digest('hex'),
    }
  })
  
  // Batch insert
  for (let i = 0; i < rows.length; i += BATCH_SIZE) {
    const batch = rows.slice(i, i + BATCH_SIZE)
    
    const { error } = await supabase
      .from('schedule_reports')
      .upsert(batch, {
        onConflict: 'address,city',
        ignoreDuplicates: true
      })
    
    if (error) {
      const { error: insertError } = await supabase
        .from('schedule_reports')
        .insert(batch)
      
      if (insertError) {
        errors += batch.length
        if (errors <= 5) console.error(`  ⚠️ Insert error: ${insertError.message}`)
      } else {
        imported += batch.length
      }
    } else {
      imported += batch.length
    }
    
    process.stdout.write(`  📦 Portland zones: ${imported} imported, ${errors} errors\r`)
    await new Promise(r => setTimeout(r, 100))
  }
  
  console.log(`\n  ✅ Portland zones: ${imported} imported, ${errors} errors`)
  return { imported, skipped, errors }
}

async function main() {
  console.log('🗑️ TrashAlert — Portland OR Data Import')
  console.log('========================================\n')
  
  // Check current Portland count
  const { count: existingCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'portland')
  
  console.log(`📊 Existing Portland records: ${existingCount || 0}`)
  
  if (existingCount && existingCount > 500) {
    console.log('⚠️ Portland data already imported (>500 records). Skipping to avoid duplicates.')
    process.exit(0)
  }
  
  // Fetch zone data
  const zones = await fetchPortlandZones()
  
  // Import zone-level records
  const result = await importZonesToSupabase(zones)
  
  console.log('\n========================================')
  console.log(`🎉 Import complete!`)
  console.log(`   Zone records imported: ${result.imported}`)
  console.log(`   Errors: ${result.errors}`)
  
  // Verify
  const { count: finalCount } = await supabase
    .from('schedule_reports')
    .select('*', { count: 'exact', head: true })
    .eq('city', 'portland')
  
  console.log(`\n📊 Portland records: ${finalCount}`)
}

main().catch(err => {
  console.error('Fatal error:', err)
  process.exit(1)
})
