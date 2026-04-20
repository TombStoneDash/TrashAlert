#!/usr/bin/env node
/**
 * Generic zone-polygon importer — writes to collection_zones (not
 * schedule_reports). Configure one source per city, each producing:
 *   { city, zone_id, zone_name, collection_day, recycling_week, source, geom }
 *
 * Assumes the 20260420000000_collection_zones.sql migration in
 * trashalert-web has been applied (PostGIS extension + table + RPC).
 *
 * Run:  node --env-file=.env.local scripts/import-zone-polygons.mjs [city-slug]
 */
import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Run with: node --env-file=.env.local scripts/import-zone-polygons.mjs [city]')
  process.exit(1)
}
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const DAY_MAP = {
  mon: 'monday', monday: 'monday',
  tue: 'tuesday', tues: 'tuesday', tuesday: 'tuesday',
  wed: 'wednesday', weds: 'wednesday', wednesday: 'wednesday',
  thu: 'thursday', thur: 'thursday', thurs: 'thursday', thursday: 'thursday',
  fri: 'friday', friday: 'friday',
  sat: 'saturday', saturday: 'saturday',
  sun: 'sunday', sunday: 'sunday',
}
function pickDay(raw) {
  if (raw == null) return null
  const first = String(raw).split(/[\/,&\s\-]+/)[0].trim().toLowerCase()
  return DAY_MAP[first] || null
}

// Convert an ArcGIS "rings" geometry to GeoJSON MultiPolygon.
function arcgisToGeoJSON(geom) {
  if (!geom?.rings?.length) return null
  // ArcGIS: outer ring = clockwise, inner (hole) = counter-clockwise.
  // GeoJSON: outer = counter-clockwise, inner = clockwise — but Postgres
  // ST_GeomFromGeoJSON is forgiving about winding; ST_MakeValid handles it.
  const polygons = []
  let current = null
  for (const ring of geom.rings) {
    if (signedArea(ring) < 0) {
      if (current) polygons.push(current)
      current = [ring]
    } else if (current) {
      current.push(ring)
    } else {
      current = [ring]
    }
  }
  if (current) polygons.push(current)
  return { type: 'MultiPolygon', coordinates: polygons }
}
function signedArea(ring) {
  let a = 0
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    a += (ring[j][0] + ring[i][0]) * (ring[j][1] - ring[i][1])
  }
  return a / 2
}

// One config per zone-level city. Each returns an array of:
//   { zone_id, zone_name, collection_day, recycling_week, source, geom (GeoJSON) }
const SOURCES = {
  // Chicago — wards via data.cityofchicago.org SODA. Day data isn't in the
  // ward boundary feed directly, so we tag every ward with 'varies'; the web
  // response will return zone_name = "Ward N" and source = 'chicago_wards'.
  // Users get a real zone boundary instead of "we don't know your city".
  // Follow-up: correlate with DSS route data once a public join exists.
  'chicago-wards': {
    city: 'chicago',
    fetch: async () => {
      const url = 'https://services.arcgis.com/wrhcHrQqaLbDkS9z/arcgis/rest/services/WARDS_2023/FeatureServer/0/query?where=1%3D1&outFields=WARD&returnGeometry=true&outSR=4326&f=json'
      const res = await fetch(url, { signal: AbortSignal.timeout(60_000) })
      if (!res.ok) throw new Error(`Chicago wards fetch: ${res.status}`)
      const data = await res.json()
      const out = []
      for (const f of data.features || []) {
        const geom = arcgisToGeoJSON(f.geometry)
        if (!geom) continue
        const ward = f.attributes.WARD
        out.push({
          zone_id: `ward-${ward}`,
          zone_name: `Ward ${ward}`,
          collection_day: null,
          recycling_week: null,
          source: 'chicago_wards',
          geom,
        })
      }
      return out
    },
  },

  // Houston — Solid Waste service areas by collection day.
  // cohgis-mycity.opendata.arcgis.com hosts the polygons under SWM.
  'houston-swm': {
    city: 'houston',
    fetch: async () => {
      const url = 'https://services.arcgis.com/lqRTrQp2HrfnJt8U/arcgis/rest/services/SolidWaste_RecyclingRoutes/FeatureServer/0/query?where=1%3D1&outFields=SERVICE_DAY,ROUTE&returnGeometry=true&outSR=4326&f=json'
      const res = await fetch(url, { signal: AbortSignal.timeout(60_000) })
      if (!res.ok) throw new Error(`Houston SWM fetch: ${res.status}`)
      const data = await res.json()
      const out = []
      for (const f of data.features || []) {
        const geom = arcgisToGeoJSON(f.geometry)
        if (!geom) continue
        const day = pickDay(f.attributes.SERVICE_DAY)
        if (!day) continue
        out.push({
          zone_id: `route-${f.attributes.ROUTE}`,
          zone_name: `Route ${f.attributes.ROUTE}`,
          collection_day: day,
          recycling_week: null,
          source: 'houston_swm',
          geom,
        })
      }
      return out
    },
  },

  // Indianapolis — DPW solid waste district polygons.
  'indianapolis-dpw': {
    city: 'indianapolis',
    fetch: async () => {
      const url = 'https://services.arcgis.com/79kfd2K6fskCAkyg/arcgis/rest/services/Trash_Zones/FeatureServer/0/query?where=1%3D1&outFields=*&returnGeometry=true&outSR=4326&f=json'
      const res = await fetch(url, { signal: AbortSignal.timeout(60_000) })
      if (!res.ok) throw new Error(`Indy DPW fetch: ${res.status}`)
      const data = await res.json()
      const out = []
      for (const f of data.features || []) {
        const geom = arcgisToGeoJSON(f.geometry)
        if (!geom) continue
        const a = f.attributes
        const day = pickDay(a.DAY || a.TRASH_DAY || a.COLLECTION || a.SERVICE_DAY || a.DAY_NAME)
        if (!day) continue
        out.push({
          zone_id: `zone-${a.OBJECTID || a.FID || a.ZONE}`,
          zone_name: String(a.ZONE || a.DISTRICT || a.NAME || '').trim() || null,
          collection_day: day,
          recycling_week: null,
          source: 'indianapolis_dpw',
          geom,
        })
      }
      return out
    },
  },
}

async function upsertZones(city, rows) {
  // Insert via raw EWKT string — PostgREST accepts geometry as text when the
  // target column is geometry and the string parses via ST_GeomFromText.
  // We convert GeoJSON → EWKT client-side to keep a single insert path.
  const payload = rows.map((r) => ({
    city,
    zone_id: r.zone_id,
    zone_name: r.zone_name,
    collection_day: r.collection_day,
    recycling_week: r.recycling_week,
    source: r.source,
    geom: geojsonToEwkt(r.geom),
  }))

  const CHUNK = 100
  let imported = 0, failed = 0
  for (let i = 0; i < payload.length; i += CHUNK) {
    const batch = payload.slice(i, i + CHUNK)
    const { error } = await supabase
      .from('collection_zones')
      .upsert(batch, { onConflict: 'city,zone_id' })
    if (error) {
      failed += batch.length
      console.error(`  ✗ batch ${i}-${i + batch.length}: ${error.message}`)
    } else {
      imported += batch.length
      process.stdout.write(`\r  upserted ${imported}/${payload.length}`)
    }
  }
  process.stdout.write('\n')
  return { imported, failed }
}

function geojsonToEwkt(geom) {
  if (geom.type !== 'MultiPolygon') throw new Error(`Unsupported geom: ${geom.type}`)
  const polys = geom.coordinates.map((poly) => {
    const rings = poly.map((ring) => {
      const pts = ring.map(([x, y]) => `${x} ${y}`).join(',')
      return `(${pts})`
    }).join(',')
    return `(${rings})`
  }).join(',')
  return `SRID=4326;MULTIPOLYGON(${polys})`
}

async function runSource(name) {
  const cfg = SOURCES[name]
  if (!cfg) { console.error(`Unknown source: ${name}`); return }
  console.log(`→ ${name} (${cfg.city})`)
  try {
    const rows = await cfg.fetch()
    console.log(`  fetched ${rows.length} polygons`)
    if (rows.length === 0) return
    const { imported, failed } = await upsertZones(cfg.city, rows)
    console.log(`  imported=${imported}  failed=${failed}`)
  } catch (e) {
    console.error(`  ✗ ${e.message}`)
  }
}

async function main() {
  const only = process.argv[2]
  const names = only ? [only] : Object.keys(SOURCES)
  console.log('🗺️  TrashAlert — Zone polygon import')
  console.log('====================================')
  for (const n of names) await runSource(n)
}

main().catch((e) => { console.error(e); process.exit(1) })
