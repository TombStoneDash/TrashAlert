#!/usr/bin/env node
/**
 * Portland ME — per-street trash collection routes.
 * Source: services1.arcgis.com/Z84SVYy1QoXoOXkk/.../SolidWaste_Trash_Recycling_Routes_AGOL/FeatureServer/0
 * 1,477 polylines with Trash_Route (day name) + ST_Name + Route_Number.
 */
import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Run with: node --env-file=.env.local scripts/import-portland-me.mjs')
  process.exit(1)
}
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const URL_BASE = 'https://services1.arcgis.com/Z84SVYy1QoXoOXkk/arcgis/rest/services/SolidWaste_Trash_Recycling_Routes_AGOL/FeatureServer/0/query'
const DAY_MAP = { monday:'monday', tuesday:'tuesday', wednesday:'wednesday', thursday:'thursday', friday:'friday', saturday:'saturday', sunday:'sunday' }

function centroidPaths(paths) {
  if (!paths?.length) return [null, null]
  let sx = 0, sy = 0, n = 0
  for (const path of paths) for (const [x, y] of path) { sx += x; sy += y; n++ }
  return n ? [sx / n, sy / n] : [null, null]
}

async function main() {
  console.log('Portland ME Import')
  const reporterHash = crypto.createHash('sha256').update('city_api_portland_me').digest('hex').substring(0, 16)
  const now = new Date().toISOString()
  const params = new URLSearchParams({
    where: '1=1', outFields: 'Trash_Route,ST_Name,Route_Number,OBJECTID',
    outSR: '4326', returnGeometry: 'true', resultRecordCount: '5000',
    orderByFields: 'OBJECTID ASC', f: 'json',
  })
  const data = await fetch(`${URL_BASE}?${params}`, { signal: AbortSignal.timeout(60_000) }).then(r=>r.json())
  const features = data.features || []
  console.log(`Fetched ${features.length} features`)

  const seen = new Set()
  const rows = []
  let skipped = 0
  for (const f of features) {
    const a = f.attributes
    const day = DAY_MAP[String(a.Trash_Route || '').trim().toLowerCase()]
    if (!day) { skipped++; continue }
    const street = String(a.ST_Name || '').trim().toLowerCase()
    if (!street) { skipped++; continue }
    if (seen.has(street)) { skipped++; continue }
    seen.add(street)
    const [lng, lat] = centroidPaths(f.geometry?.paths)
    rows.push({
      address: street, city: 'portland-me', state: 'ME',
      zip_code: '', neighborhood: `Route ${a.Route_Number || ''}`,
      collection_day: day, recycling_week: 'A',
      reporter_hash: reporterHash, verified: true, verification_count: 1,
      source: 'city_api', fetched_at: now,
      raw_payload_hash: crypto.createHash('md5').update(`${street}${day}`).digest('hex'),
      hauler: 'City of Portland ME',
      data_source_url: URL_BASE.replace('/query', ''),
      data_source_type: 'gis',
      lat, lng,
    })
  }
  console.log(`Inserting ${rows.length} unique streets, skipped ${skipped}`)

  let imported = 0, errors = 0
  for (let i = 0; i < rows.length; i += 500) {
    const batch = rows.slice(i, i + 500)
    const { error } = await supabase.from('schedule_reports').upsert(batch, { onConflict: 'address,city', ignoreDuplicates: true })
    if (error) {
      const { error: ie } = await supabase.from('schedule_reports').insert(batch)
      if (ie) { errors += batch.length; console.error(ie.message) } else imported += batch.length
    } else imported += batch.length
  }
  console.log(`Portland ME: imported=${imported} errors=${errors}`)
}
main().catch(e => { console.error('Fatal:', e); process.exit(1) })
