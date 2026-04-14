#!/usr/bin/env node
/**
 * Import collection zone data from city ArcGIS services.
 *
 * Target cities with public GIS data:
 *   - Pittsburgh PA — ArcGIS feature service
 *   - Costa Mesa CA — ArcGIS feature service
 *   - Yuma AZ — city GIS portal
 *   - South Euclid OH — interactive map / GIS
 *
 * Usage:
 *   node scripts/import-arcgis-cities.mjs --city <slug> [--dry-run]
 *   node scripts/import-arcgis-cities.mjs --all [--dry-run]
 */

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const DATA_DIR = path.join(__dirname, '..', 'data')

const DAY_MAP = {
  1: 'monday', 2: 'tuesday', 3: 'wednesday', 4: 'thursday', 5: 'friday', 6: 'saturday',
  'MON': 'monday', 'TUE': 'tuesday', 'WED': 'wednesday', 'THU': 'thursday', 'FRI': 'friday', 'SAT': 'saturday',
  'MONDAY': 'monday', 'TUESDAY': 'tuesday', 'WEDNESDAY': 'wednesday', 'THURSDAY': 'thursday', 'FRIDAY': 'friday', 'SATURDAY': 'saturday',
  'Monday': 'monday', 'Tuesday': 'tuesday', 'Wednesday': 'wednesday', 'Thursday': 'thursday', 'Friday': 'friday', 'Saturday': 'saturday',
  'M': 'monday', 'T': 'tuesday', 'W': 'wednesday', 'R': 'thursday', 'F': 'friday', 'S': 'saturday',
}

// City configurations with ArcGIS endpoints
const CITIES = {
  pittsburgh: {
    name: 'Pittsburgh',
    state: 'PA',
    serviceUrl: 'https://services1.arcgis.com/YZCmUqbHCOZJ3JHY/arcgis/rest/services/Refuse_Waste_Collection_Areas/FeatureServer/0',
    dayField: 'DAY',
    zoneField: 'ZONE',
    center: [-79.99, 40.44],
  },
  'costa-mesa': {
    name: 'Costa Mesa',
    state: 'CA',
    serviceUrl: 'https://services2.arcgis.com/z5tlnpYHokW9tFhd/arcgis/rest/services/Refuse_Collection_Day/FeatureServer/0',
    dayField: 'Collection_Day',
    zoneField: 'Zone',
    center: [-117.91, 33.66],
  },
  yuma: {
    name: 'Yuma',
    state: 'AZ',
    serviceUrl: 'https://services.arcgis.com/l5QYXqnvPBJnMJTk/arcgis/rest/services/Solid_Waste_Collection_Zones/FeatureServer/0',
    dayField: 'COLLECTION_DAY',
    zoneField: 'ZONE_NAME',
    center: [-114.62, 32.69],
  },
  'south-euclid': {
    name: 'South Euclid',
    state: 'OH',
    serviceUrl: 'https://services5.arcgis.com/GfwWNkhOj9bNBqoJ/arcgis/rest/services/Trash_Collection_Zones/FeatureServer/0',
    dayField: 'Day',
    zoneField: 'Zone',
    center: [-81.52, 41.52],
  },
}

/**
 * Query an ArcGIS Feature Service for all features.
 */
async function queryArcGIS(serviceUrl, { outFields = '*', where = '1=1', resultOffset = 0, resultRecordCount = 2000 } = {}) {
  const params = new URLSearchParams({
    where,
    outFields,
    outSR: '4326',
    f: 'geojson',
    resultOffset: String(resultOffset),
    resultRecordCount: String(resultRecordCount),
  })

  const url = `${serviceUrl}/query?${params}`
  console.log(`  Fetching: ${url.slice(0, 100)}...`)

  const res = await fetch(url)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`ArcGIS query failed (${res.status}): ${text.slice(0, 200)}`)
  }

  const data = await res.json()
  return data
}

/**
 * Fetch all features from an ArcGIS service, handling pagination.
 */
async function fetchAllFeatures(serviceUrl) {
  const allFeatures = []
  let offset = 0
  const pageSize = 2000

  while (true) {
    try {
      const data = await queryArcGIS(serviceUrl, { resultOffset: offset, resultRecordCount: pageSize })

      if (!data.features || data.features.length === 0) break
      allFeatures.push(...data.features)
      console.log(`  Got ${data.features.length} features (total: ${allFeatures.length})`)

      if (data.features.length < pageSize) break
      offset += pageSize
    } catch (err) {
      if (offset === 0) throw err
      // May have hit the end, return what we have
      break
    }
  }

  return allFeatures
}

/**
 * Normalize a day value to lowercase weekday name.
 */
function normalizeDay(value) {
  if (!value) return null
  const s = String(value).trim()
  return DAY_MAP[s] || DAY_MAP[s.toUpperCase()] || null
}

/**
 * Process a city's ArcGIS data into zone GeoJSON.
 */
async function processCity(slug, config, dryRun) {
  console.log(`\n=== ${config.name}, ${config.state} ===`)
  console.log(`Service: ${config.serviceUrl}`)

  let features
  try {
    features = await fetchAllFeatures(config.serviceUrl)
  } catch (err) {
    console.error(`  ERROR: ${err.message}`)
    console.log(`  Skipping ${config.name} — endpoint may be unavailable or URL may have changed.`)
    return null
  }

  if (features.length === 0) {
    console.log(`  No features found. The endpoint may require different parameters.`)
    return null
  }

  console.log(`  Total features: ${features.length}`)

  // Map day colors
  const DAY_COLORS = {
    monday: '#3B82F6',
    tuesday: '#10B981',
    wednesday: '#F59E0B',
    thursday: '#8B5CF6',
    friday: '#EF4444',
    saturday: '#EC4899',
  }

  // Process features — add normalized day and color properties
  const processed = features.map(f => {
    const props = f.properties || {}
    const rawDay = props[config.dayField]
    const day = normalizeDay(rawDay)
    const zone = props[config.zoneField] || 'Unknown'

    return {
      ...f,
      properties: {
        ...props,
        day: day || 'unknown',
        dayLabel: day ? day.charAt(0).toUpperCase() + day.slice(1) : 'Unknown',
        color: day ? (DAY_COLORS[day] || '#888888') : '#888888',
        zone: String(zone),
        city: config.name,
        state: config.state,
      },
    }
  })

  // Stats
  const dayCounts = {}
  for (const f of processed) {
    const d = f.properties.day
    dayCounts[d] = (dayCounts[d] || 0) + 1
  }
  console.log(`  Day distribution:`, dayCounts)

  const geojson = {
    type: 'FeatureCollection',
    features: processed,
    metadata: {
      city: config.name,
      state: config.state,
      slug,
      source: config.serviceUrl,
      fetchedAt: new Date().toISOString(),
      featureCount: processed.length,
    },
  }

  if (!dryRun) {
    const outPath = path.join(DATA_DIR, `${slug}-zones.geojson`)
    fs.writeFileSync(outPath, JSON.stringify(geojson))
    console.log(`  Written to: ${outPath} (${(fs.statSync(outPath).size / 1024).toFixed(0)} KB)`)
  } else {
    console.log(`  [dry-run] Would write to data/${slug}-zones.geojson`)
  }

  return geojson
}

async function main() {
  const args = process.argv.slice(2)
  const dryRun = args.includes('--dry-run')
  const allCities = args.includes('--all')
  const cityIdx = args.indexOf('--city')
  const targetCity = cityIdx >= 0 ? args[cityIdx + 1] : null

  if (!allCities && !targetCity) {
    console.log('Usage:')
    console.log('  node scripts/import-arcgis-cities.mjs --city <slug>')
    console.log('  node scripts/import-arcgis-cities.mjs --all')
    console.log('')
    console.log('Available cities:', Object.keys(CITIES).join(', '))
    process.exit(0)
  }

  const targets = allCities ? Object.keys(CITIES) : [targetCity]
  const results = []

  for (const slug of targets) {
    const config = CITIES[slug]
    if (!config) {
      console.error(`Unknown city: ${slug}. Available: ${Object.keys(CITIES).join(', ')}`)
      continue
    }
    const result = await processCity(slug, config, dryRun)
    if (result) {
      results.push({ slug, featureCount: result.features.length })
    }
  }

  console.log(`\n=== Summary ===`)
  for (const r of results) {
    console.log(`  ${r.slug}: ${r.featureCount} zones`)
  }
  console.log(`Total: ${results.length} cities processed`)
}

main().catch(err => {
  console.error('Fatal error:', err)
  process.exit(1)
})
