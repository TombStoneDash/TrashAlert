#!/usr/bin/env node
/**
 * Import collection zone GeoJSON into the Supabase collection_zones table.
 *
 * Reads zone polygons from municipal GeoJSON sources (local files or URLs),
 * extracts zone name / collection day / estimated addresses, and upserts
 * each polygon into collection_zones via the Supabase REST API.
 *
 * Usage:
 *   node scripts/import-zones.mjs --file <path.geojson> --city <slug> [options]
 *   node scripts/import-zones.mjs --url  <geojson-url>  --city <slug> [options]
 *
 * Options:
 *   --city <slug>           City slug (e.g. "houston", "san-diego")
 *   --file <path>           Path to a local GeoJSON file
 *   --url  <url>            URL to fetch GeoJSON from
 *   --day-field <name>      Property field containing collection day (default: "collection_day")
 *   --zone-field <name>     Property field containing zone name     (default: "zone_name")
 *   --addr-field <name>     Property field with estimated addresses (default: "estimated_addresses")
 *   --source-url <url>      Attribution URL for the municipal source
 *   --dry-run               Print what would be imported without writing to Supabase
 *
 * Environment:
 *   SUPABASE_URL            Supabase project URL
 *   SUPABASE_KEY            Supabase service-role key
 */

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// ---------------------------------------------------------------------------
// Config from env
// ---------------------------------------------------------------------------

const SUPABASE_URL = process.env.SUPABASE_URL
  || process.env.NEXT_PUBLIC_SUPABASE_URL
  || 'https://qsuzfemakaaroeakyick.supabase.co'

const SUPABASE_KEY = process.env.SUPABASE_KEY
  || process.env.SUPABASE_SERVICE_KEY
  || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  || ''

if (!SUPABASE_KEY) {
  console.error('ERROR: SUPABASE_KEY (or SUPABASE_SERVICE_KEY) must be set in env')
  process.exit(1)
}

const HEADERS = {
  apikey: SUPABASE_KEY,
  Authorization: `Bearer ${SUPABASE_KEY}`,
  'Content-Type': 'application/json',
  Prefer: 'resolution=merge-duplicates',
}

// ---------------------------------------------------------------------------
// Day normalization (matches existing DAY_MAP pattern)
// ---------------------------------------------------------------------------

const DAY_MAP = {
  1: 'Monday', 2: 'Tuesday', 3: 'Wednesday', 4: 'Thursday', 5: 'Friday', 6: 'Saturday',
  MON: 'Monday', TUE: 'Tuesday', WED: 'Wednesday', THU: 'Thursday', FRI: 'Friday', SAT: 'Saturday',
  MONDAY: 'Monday', TUESDAY: 'Tuesday', WEDNESDAY: 'Wednesday', THURSDAY: 'Thursday', FRIDAY: 'Friday', SATURDAY: 'Saturday',
  Monday: 'Monday', Tuesday: 'Tuesday', Wednesday: 'Wednesday', Thursday: 'Thursday', Friday: 'Friday', Saturday: 'Saturday',
  M: 'Monday', T: 'Tuesday', W: 'Wednesday', R: 'Thursday', F: 'Friday', S: 'Saturday',
}

function normalizeDay(value) {
  if (!value) return null
  const s = String(value).trim()
  return DAY_MAP[s] || DAY_MAP[s.toUpperCase()] || null
}

// ---------------------------------------------------------------------------
// GeoJSON loading
// ---------------------------------------------------------------------------

async function loadGeoJSON(filePath, url) {
  if (filePath) {
    const abs = path.isAbsolute(filePath) ? filePath : path.resolve(process.cwd(), filePath)
    console.log(`Reading local file: ${abs}`)
    const raw = fs.readFileSync(abs, 'utf-8')
    return JSON.parse(raw)
  }

  if (url) {
    console.log(`Fetching: ${url}`)
    const res = await fetch(url)
    if (!res.ok) throw new Error(`Fetch failed (${res.status}): ${await res.text().then(t => t.slice(0, 200))}`)
    return res.json()
  }

  throw new Error('Provide --file <path> or --url <url>')
}

// ---------------------------------------------------------------------------
// Convert GeoJSON polygon to WKT for PostGIS
// ---------------------------------------------------------------------------

function polygonToWKT(geometry) {
  if (!geometry) return null

  // Handle both Polygon and MultiPolygon — take first polygon from Multi
  let rings
  if (geometry.type === 'Polygon') {
    rings = geometry.coordinates
  } else if (geometry.type === 'MultiPolygon') {
    rings = geometry.coordinates[0] // first polygon
  } else {
    console.warn(`  Skipping unsupported geometry type: ${geometry.type}`)
    return null
  }

  // Build WKT POLYGON string: POLYGON((lng lat, lng lat, ...))
  const ringStrs = rings.map(ring =>
    '(' + ring.map(([lng, lat]) => `${lng} ${lat}`).join(', ') + ')'
  )
  return `SRID=4326;POLYGON(${ringStrs.join(', ')})`
}

// ---------------------------------------------------------------------------
// Upsert zones to Supabase via PostgREST
// ---------------------------------------------------------------------------

async function upsertZone(zone) {
  const url = `${SUPABASE_URL}/rest/v1/collection_zones`
  const res = await fetch(url, {
    method: 'POST',
    headers: HEADERS,
    body: JSON.stringify(zone),
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Supabase upsert failed (${res.status}): ${text.slice(0, 300)}`)
  }
}

// Supabase REST doesn't accept WKT directly for geometry columns.
// Use the RPC approach: insert with raw SQL via an RPC function.
async function insertZoneViaRPC(zone) {
  const sql = `
    INSERT INTO collection_zones (city, zone_name, collection_day, estimated_addresses, source_url, geom)
    VALUES ($1, $2, $3, $4, $5, ST_GeomFromEWKT($6))
    ON CONFLICT (zone_id) DO UPDATE SET
      collection_day = EXCLUDED.collection_day,
      estimated_addresses = EXCLUDED.estimated_addresses,
      source_url = EXCLUDED.source_url,
      geom = EXCLUDED.geom,
      updated_at = now()
    RETURNING zone_id
  `

  // Use Supabase's raw SQL endpoint if available, or fall back to
  // inserting via PostgREST with geom as GeoJSON text
  const url = `${SUPABASE_URL}/rest/v1/collection_zones`
  const body = {
    city: zone.city,
    zone_name: zone.zone_name,
    collection_day: zone.collection_day,
    estimated_addresses: zone.estimated_addresses,
    source_url: zone.source_url,
    // PostgREST accepts GeoJSON for geometry columns
    geom: zone.geojson,
  }

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      ...HEADERS,
      Prefer: 'return=representation',
    },
    body: JSON.stringify(body),
  })

  if (!res.ok) {
    const text = await res.text()
    throw new Error(`Insert failed (${res.status}): ${text.slice(0, 300)}`)
  }

  const rows = await res.json()
  return rows[0]?.zone_id
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const args = process.argv.slice(2)

  const getArg = (flag) => {
    const idx = args.indexOf(flag)
    return idx >= 0 && idx + 1 < args.length ? args[idx + 1] : null
  }

  const city = getArg('--city')
  const filePath = getArg('--file')
  const url = getArg('--url')
  const dayField = getArg('--day-field') || 'collection_day'
  const zoneField = getArg('--zone-field') || 'zone_name'
  const addrField = getArg('--addr-field') || 'estimated_addresses'
  const sourceUrl = getArg('--source-url') || ''
  const dryRun = args.includes('--dry-run')

  if (!city || (!filePath && !url)) {
    console.log(`
Usage:
  node scripts/import-zones.mjs --file <path.geojson> --city <slug> [options]
  node scripts/import-zones.mjs --url  <geojson-url>  --city <slug> [options]

Options:
  --city <slug>           City slug (e.g. "houston", "san-diego")
  --file <path>           Path to a local GeoJSON file
  --url  <url>            URL to fetch GeoJSON from
  --day-field <name>      Property field for collection day (default: "collection_day")
  --zone-field <name>     Property field for zone name     (default: "zone_name")
  --addr-field <name>     Property field for estimated addresses (default: "estimated_addresses")
  --source-url <url>      Attribution URL for the municipal source
  --dry-run               Print what would be imported without writing

Environment:
  SUPABASE_URL            Supabase project URL
  SUPABASE_KEY            Supabase service-role key
`)
    process.exit(0)
  }

  console.log(`\n=== Import Zones: ${city} ===`)
  if (dryRun) console.log('  [DRY RUN — no writes]')

  // Load the GeoJSON
  const geojson = await loadGeoJSON(filePath, url)

  if (geojson.type !== 'FeatureCollection' || !Array.isArray(geojson.features)) {
    console.error('ERROR: Expected a GeoJSON FeatureCollection')
    process.exit(1)
  }

  console.log(`  Features found: ${geojson.features.length}`)

  // Process each feature
  let imported = 0
  let skipped = 0
  const dayCounts = {}

  for (const feature of geojson.features) {
    const props = feature.properties || {}
    const geom = feature.geometry

    if (!geom || (geom.type !== 'Polygon' && geom.type !== 'MultiPolygon')) {
      skipped++
      continue
    }

    const zoneName = props[zoneField] || props.zone || props.Zone || props.ZONE || `Zone ${imported + 1}`
    const rawDay = props[dayField] || props.day || props.Day || props.DAY || props.Collection_Day
    const day = normalizeDay(rawDay)
    const estAddresses = parseInt(props[addrField] || props.addresses || props.count || '0', 10) || 0

    // For PostgREST, send the geometry as a GeoJSON object string
    // (Supabase/PostgREST can parse GeoJSON geometry for geometry columns)
    const geojsonGeom = geom.type === 'MultiPolygon'
      ? { type: 'Polygon', coordinates: geom.coordinates[0] }
      : geom

    if (day) {
      dayCounts[day] = (dayCounts[day] || 0) + 1
    }

    if (dryRun) {
      console.log(`  [dry-run] ${zoneName} | day=${day || 'unknown'} | est=${estAddresses}`)
      imported++
      continue
    }

    try {
      const zoneId = await insertZoneViaRPC({
        city,
        zone_name: String(zoneName),
        collection_day: day,
        estimated_addresses: estAddresses,
        source_url: sourceUrl,
        geojson: geojsonGeom,
      })
      imported++
      if (imported % 25 === 0) {
        console.log(`  Imported ${imported} zones...`)
      }
    } catch (err) {
      console.error(`  ERROR importing zone "${zoneName}": ${err.message}`)
      skipped++
    }
  }

  console.log(`\n=== Summary ===`)
  console.log(`  City:     ${city}`)
  console.log(`  Imported: ${imported}`)
  console.log(`  Skipped:  ${skipped}`)
  console.log(`  Day distribution:`, dayCounts)
  if (sourceUrl) console.log(`  Source:   ${sourceUrl}`)
}

main().catch(err => {
  console.error('Fatal error:', err)
  process.exit(1)
})
