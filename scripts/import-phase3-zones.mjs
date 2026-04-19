#!/usr/bin/env node
/**
 * Phase 3 zone-level importer — runs against 11 ArcGIS sources discovered
 * during Phase 3 research and writes one row per zone (centroid-based).
 *
 * Each source has a different schema, so configs below carry the field
 * mapping per source. Most are small (5-1500 features); aggregate
 * total ~3,500 rows.
 */
import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Run with: node --env-file=.env.local scripts/import-phase3-zones.mjs')
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

function centroid(geom) {
  if (geom?.rings?.[0]) {
    const r = geom.rings[0]
    let sx = 0, sy = 0
    for (const [x, y] of r) { sx += x; sy += y }
    return { lng: sx / r.length, lat: sy / r.length }
  }
  if (geom?.paths?.[0]) {
    const p = geom.paths[0]
    let sx = 0, sy = 0
    for (const [x, y] of p) { sx += x; sy += y }
    return { lng: sx / p.length, lat: sy / p.length }
  }
  return null
}

const SOURCES = [
  {
    slug: 'nyc',  state: 'NY', hauler: 'NYC Department of Sanitation (DSNY)',
    url: 'https://services.arcgis.com/uKN48PkxmWiqJM9q/arcgis/rest/services/DSNY_FREQUENCIES/FeatureServer/0',
    fields: 'DISTRICT,SECTION,FREQUENCY,SCHEDULECODE,FREQ_REFUSE',
    addr: a => `nyc dsny code ${a.SCHEDULECODE || a.SECTION}`.toLowerCase(),
    day:  a => pickDay(a.FREQ_REFUSE),
    nbhd: a => `District ${a.DISTRICT} (${a.FREQ_REFUSE})`,
  },
  {
    slug: 'houston',  state: 'TX', hauler: 'City of Houston Solid Waste Mgmt',
    url: 'https://services.arcgis.com/NummVBqZSIJKUeVR/arcgis/rest/services/COH_Solid_Waste_Automated_Trash_Pickup_Areas_view/FeatureServer/18',
    fields: 'SEC_NAME,DAY,QUAD,SERVICE_TYPE,DISTRICTID,DISTTYPE,NAME',
    addr: a => `houston ${(a.SERVICE_TYPE || a.DISTTYPE || 'pickup').toLowerCase().replace(/\s+/g,'-')} section ${a.SEC_NAME || a.DISTRICTID || a.NAME}`.toLowerCase(),
    day:  a => pickDay(a.DAY),
    nbhd: a => `${a.SERVICE_TYPE || ''} Section ${a.SEC_NAME || a.DISTRICTID} ${a.QUAD || ''}`.trim(),
  },
  {
    slug: 'san-antonio',  state: 'TX', hauler: 'San Antonio Solid Waste Mgmt',
    url: 'https://services.arcgis.com/g1fRTDLeMgspWrYp/arcgis/rest/services/RECYCLEROUTES_WEBMAP/FeatureServer/0',
    fields: 'CollectionDay,CollectionMethod,RouteNumber,Commodity,RouteID,DistrictCenter',
    addr: a => `san-antonio ${(a.Commodity || 'recycle').toLowerCase().replace(/\s+/g,'-')} route ${a.RouteID || a.RouteNumber}`.toLowerCase(),
    day:  a => pickDay(a.CollectionDay),
    nbhd: a => `${a.Commodity || 'Recycle'} Route ${a.RouteNumber} ${a.DistrictCenter || ''}`.trim(),
  },
  {
    slug: 'dekalb-ga',  state: 'GA', hauler: 'DeKalb County Sanitation',
    url: 'https://services2.arcgis.com/IxVN2oUE9EYLSnPE/arcgis/rest/services/Dekalb_County_Sanitation_layer_Garbage_Route/FeatureServer/0',
    fields: 'Lot,Route,Day,Count_,Tonnage',
    addr: (a, i) => `dekalb-ga route ${a.Route}-${a.Lot}-${i}`.toLowerCase(),
    day:  a => pickDay(a.Day),
    nbhd: a => `Route ${a.Route} Lot ${a.Lot}`,
  },
  {
    slug: 'nashville',  state: 'TN', hauler: 'Metro Nashville Public Works',
    url: 'https://services2.arcgis.com/HdTo6HJqh92wn4D8/arcgis/rest/services/Trash_Collection_Routes_5_Day_Public_View/FeatureServer/0',
    fields: 'Route,Hauler,RouteDay,Miles',
    addr: a => `nashville trash route ${a.Route}`.toLowerCase(),
    day:  a => pickDay(a.RouteDay),
    nbhd: a => `${a.Hauler || ''} Route ${a.Route}`.trim(),
  },
  {
    slug: 'boston',  state: 'MA', hauler: 'Boston Public Works',
    url: 'https://gisportal.boston.gov/arcgis/rest/services/Infrastructure/OpenData/MapServer/10',
    fields: 'RECOLLECT,PWDDIST,TRASHDAY,CURR_SCHED,DT',
    addr: a => `boston trash zone ${a.DT || a.PWDDIST || a.RECOLLECT}`.toLowerCase(),
    day:  a => {
      const t = String(a.TRASHDAY || '').toUpperCase()
      if (t.startsWith('TH')) return 'thursday'
      if (t.startsWith('M'))  return 'monday'
      if (t.startsWith('T'))  return 'tuesday'
      if (t.startsWith('W'))  return 'wednesday'
      if (t.startsWith('F'))  return 'friday'
      if (t.startsWith('S'))  return 'saturday'
      return null
    },
    nbhd: a => `District ${a.PWDDIST} (${a.CURR_SCHED || a.TRASHDAY || ''})`,
  },
  {
    slug: 'phoenix-az',  state: 'AZ', hauler: 'Phoenix Public Works',
    url: 'https://services9.arcgis.com/xdpiCgT89eSIEpbi/arcgis/rest/services/Trash_Routes/FeatureServer/0',
    fields: 'Pickup_Days,Recycle_Days',
    addr: (a, i) => `phoenix-az trash zone ${pickDay(a.Pickup_Days) || 'z' + i}`.toLowerCase(),
    day:  a => pickDay(a.Pickup_Days),
    nbhd: a => `Recycle ${a.Recycle_Days || ''}`,
  },
  {
    slug: 'orlando',  state: 'FL', hauler: 'City of Orlando Solid Waste',
    url: 'https://services5.arcgis.com/mMuoPCaIYD4wEgDl/arcgis/rest/services/OrlandoSWGarbage/FeatureServer/0',
    fields: 'GarbageRouteNum,GarbageDay,Color,Phase',
    addr: a => `orlando garbage route ${a.GarbageRouteNum}`.toLowerCase(),
    day:  a => pickDay(a.GarbageDay),
    nbhd: a => `Route ${a.GarbageRouteNum} ${a.Color || ''}`.trim(),
  },
  {
    slug: 'philadelphia',  state: 'PA', hauler: 'Philadelphia Streets Dept',
    url: 'https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/Service_Areas/FeatureServer/2',
    fields: 'COLLDAY',
    addr: a => `philadelphia trash zone ${pickDay(a.COLLDAY) || 'unk'}`.toLowerCase(),
    day:  a => pickDay(a.COLLDAY),
    nbhd: a => `Citywide ${a.COLLDAY}`,
  },
  {
    slug: 'arlington-tx',  state: 'TX', hauler: 'City of Arlington TX',
    url: 'https://gis2.arlingtontx.gov/agsext2/rest/services/OpenData/OD_Community/MapServer/4',
    fields: 'RouteDay',
    addr: a => `arlington-tx trash zone ${pickDay(a.RouteDay) || 'unk'}`.toLowerCase(),
    day:  a => pickDay(a.RouteDay),
    nbhd: a => `Day ${a.RouteDay}`,
  },
]

async function fetchAll(url, fields, pageSize = 1000) {
  const all = []
  let off = 0
  while (true) {
    const params = new URLSearchParams({
      where: '1=1', outFields: fields, outSR: '4326', returnGeometry: 'true',
      resultOffset: String(off), resultRecordCount: String(pageSize),
      orderByFields: 'OBJECTID ASC', f: 'json',
    })
    const r = await fetch(`${url}/query?${params}`)
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    const j = await r.json()
    if (j.error) throw new Error(`ArcGIS: ${j.error.message}`)
    const feats = j.features || []
    if (feats.length === 0) break
    all.push(...feats)
    if (feats.length < pageSize) break
    off += pageSize
    await new Promise(r => setTimeout(r, 200))
  }
  return all
}

async function importBatch(rows) {
  const { error } = await supabase.from('schedule_reports').upsert(rows, { onConflict: 'address,city', ignoreDuplicates: true })
  if (!error) return { ok: true, n: rows.length }
  const { error: ie } = await supabase.from('schedule_reports').insert(rows)
  if (!ie) return { ok: true, n: rows.length }
  let ok = 0, fail = 0, lastErr = ie.message
  for (const row of rows) {
    const { error: e } = await supabase.from('schedule_reports').insert([row])
    if (e) { fail++; lastErr = e.message } else { ok++ }
  }
  return { ok: ok > 0, n: ok, error: fail ? `${fail} fail: ${lastErr}` : null }
}

async function processSource(src) {
  process.stdout.write(`\n  ${src.slug}: fetch … `)
  const feats = await fetchAll(src.url, src.fields)
  process.stdout.write(`${feats.length} features\n`)
  const reporterHash = crypto.createHash('sha256').update(`city_api_${src.slug}`).digest('hex').substring(0, 16)
  const now = new Date().toISOString()
  const seen = new Set()
  const rows = []
  let skipped = 0

  feats.forEach((f, i) => {
    const a = f.attributes
    const day = src.day(a)
    if (!day) { skipped++; return }
    const c = centroid(f.geometry)
    if (!c) { skipped++; return }
    const address = src.addr(a, i)
    if (seen.has(address)) { skipped++; return }
    seen.add(address)
    rows.push({
      address, city: src.slug, state: src.state, zip_code: '',
      neighborhood: src.nbhd(a),
      collection_day: day, recycling_week: 'A',
      reporter_hash: reporterHash, verified: true, verification_count: 1,
      source: 'city_api', fetched_at: now,
      raw_payload_hash: crypto.createHash('md5').update(JSON.stringify(a)).digest('hex'),
      hauler: src.hauler,
      data_source_url: src.url,
      data_source_type: 'gis',
      lat: c.lat, lng: c.lng,
    })
  })

  let imported = 0, errors = 0
  for (let i = 0; i < rows.length; i += 500) {
    const batch = rows.slice(i, i + 500)
    const r = await importBatch(batch)
    imported += r.n || 0
    errors += batch.length - (r.n || 0)
    if (r.error) console.error(`    ⚠️  ${r.error}`)
  }
  console.log(`    → imported=${imported} skipped=${skipped} errors=${errors}`)
  return { slug: src.slug, imported, skipped, errors, fetched: feats.length }
}

async function main() {
  console.log('🗑️  TrashAlert — Phase 3 Zone Sources')
  console.log('=====================================')
  const summary = []
  for (const src of SOURCES) {
    try {
      summary.push(await processSource(src))
    } catch (e) {
      console.error(`  ❌ ${src.slug}: ${e.message}`)
      summary.push({ slug: src.slug, imported: 0, skipped: 0, errors: 0, fetched: 0, fatal: e.message })
    }
  }
  console.log('\n📋 Summary:')
  let total = 0
  for (const s of summary) {
    total += s.imported
    console.log(`  ${s.slug.padEnd(16)} fetched=${String(s.fetched).padStart(5)}  imported=${String(s.imported).padStart(5)}  skipped=${String(s.skipped).padStart(4)}  errors=${s.errors}${s.fatal ? '  ❌ ' + s.fatal : ''}`)
  }
  console.log(`\n🎉 Total imported across phase 3 zones: ${total}`)
}
main().catch(e => { console.error('Fatal:', e); process.exit(1) })
