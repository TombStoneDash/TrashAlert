#!/usr/bin/env node
/**
 * Import waste collection schedules from the ReCollect public API.
 *
 * ReCollect (recollect.net, now Routeware) addresses places by opaque
 * UUID `place_id` + integer `service_id`. There is no city-slug
 * collection endpoint, so we use a curated list of (place, service)
 * tuples sourced from the home-assistant `hacs_waste_collection_schedule`
 * canonical table.
 *
 * For each entry we:
 *   1. fetch /api/places/{place_id}             → street, city, lat, lng
 *   2. fetch /api/places/{place_id}/services/{service_id}/events?after&before
 *   3. group events by flag.name (garbage/recycle/organics/...) and
 *      derive the most-common day-of-week → that's the collection day
 *   4. write one schedule row per city/zone
 *
 * Caveat: this gives one row per city covered. Total volume is small
 * (~16 cities) but each adds a real, externally-verifiable signal to
 * `schedule_reports`.
 */
import { createClient } from '@supabase/supabase-js'
import crypto from 'crypto'

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_KEY
if (!SUPABASE_URL || !SUPABASE_KEY) {
  console.error('Run with: node --env-file=.env.local scripts/import-recollect.mjs')
  process.exit(1)
}
const supabase = createClient(SUPABASE_URL, SUPABASE_KEY)

const PLACES = [
  { slug: 'ottawa-on',       place: 'BCCDF30E-578B-11E4-AD38-5839C200407A', service: 208, state: 'ON', hauler: 'City of Ottawa'              },
  { slug: 'denver-co',       place: '464342A6-3CBF-11E5-9D27-D51A47A8A7C0', service: 248, state: 'CO', hauler: 'Denver Solid Waste Mgmt'    },
  { slug: 'austin-tx',       place: '2587D9F6-DF59-11E8-96F5-0E2C682931C6', service: 323, state: 'TX', hauler: 'Austin Resource Recovery'   },
  { slug: 'san-francisco-ca',place: 'F8DA6588-B076-11E8-BA4B-30AA635824F2', service: 265, state: 'CA', hauler: 'Recology SF'                 },
  { slug: 'cambridge-ma',    place: 'F2BCBBF2-ACC9-11E8-B4BD-CFDD30C1D4D8', service: 761, state: 'MA', hauler: 'City of Cambridge DPW'      },
  { slug: 'vancouver-bc',    place: '3734BF46-A9A1-11E2-8B00-43B94144C028', service: 193, state: 'BC', hauler: 'City of Vancouver'           },
  { slug: 'halton-on',       place: '97323326-A43B-11E2-A636-ABBA3CA4474E', service: 224, state: 'ON', hauler: 'Halton Region'               },
  { slug: 'saanich-bc',      place: '46BC2620-B477-11E3-B3D4-47898BE95184', service: 214, state: 'BC', hauler: 'District of Saanich'         },
  { slug: 'richmond-bc',     place: '966E4642-75A4-11E8-BBDF-683FCE8203D4', service: 200, state: 'BC', hauler: 'City of Richmond'            },
  { slug: 'davenport-ia',    place: '9A775DEE-C7FF-11E7-822B-76228DB90E2A', service: 319, state: 'IA', hauler: 'City of Davenport'           },
  { slug: 'georgetown-tx',   place: '9EA385D4-4AF9-11EB-B308-E6A235C11932', service: 611, state: 'TX', hauler: 'City of Georgetown'          },
  { slug: 'peterborough-on', place: 'C0A33242-3365-11EC-A104-84C872B788E8', service: 345, state: 'ON', hauler: 'City of Peterborough'        },
  { slug: 'sherwood-park-ab',place: 'F5A5C1D2-3D25-11EE-A377-8D1C706BDDF3', service: 238, state: 'AB', hauler: 'Strathcona County'           },
  { slug: 'morris-mb',       place: '2DC90F42-E8AA-11EB-A726-598C8684B99B', service: 397, state: 'MB', hauler: 'Town of Morris'              },
  { slug: 'hardin-id',       place: '0495A9DC-DB0F-11E9-8172-34B19DD5B1B2', service: 881, state: 'ID', hauler: 'Hardin Sanitation'           },
  { slug: 'king-county-wa',  place: '6D1AA3AC-D794-11EC-AFDF-27CF02E3D7CF', service: 282, state: 'WA', hauler: 'Recology CleanScapes'        },
]

const DAYS = ['sunday','monday','tuesday','wednesday','thursday','friday','saturday']

async function fetchPlace(placeId) {
  const r = await fetch(`https://api.recollect.net/api/places/${placeId}`)
  if (!r.ok) throw new Error(`place ${placeId} → ${r.status}`)
  return r.json()
}

async function fetchEvents(placeId, serviceId) {
  const today = new Date()
  const after = today.toISOString().slice(0, 10)
  const before = new Date(today.getTime() + 28 * 86400_000).toISOString().slice(0, 10)
  const url = `https://api.recollect.net/api/places/${placeId}/services/${serviceId}/events?after=${after}&before=${before}&locale=en-US`
  const r = await fetch(url)
  if (!r.ok) throw new Error(`events ${placeId} → ${r.status}`)
  return r.json()
}

const TRASH_RE = /trash|garbage|refuse|waste|garbagecart/i
const RECYC_RE = /recycle|recycling|bluebox|cart_recycling/i

function dominantDay(events, regex) {
  const counts = new Array(7).fill(0)
  for (const e of events) {
    const hit = (e.flags || []).some(f => regex.test(f.name))
    if (!hit) continue
    const d = new Date(e.day + 'T12:00:00Z').getUTCDay()
    counts[d]++
  }
  const max = Math.max(...counts)
  if (max === 0) return null
  return DAYS[counts.indexOf(max)]
}

async function processOne(entry) {
  const place = await fetchPlace(entry.place)
  const evJson = await fetchEvents(entry.place, entry.service)
  const events = evJson.events || []
  const garbageDay = dominantDay(events, TRASH_RE)
  const recycleDay = dominantDay(events, RECYC_RE)
  const day = garbageDay || recycleDay
  if (!day) return { ok: false, reason: 'no garbage/recycle events', slug: entry.slug }

  const street = (place.street || place.address || '').toString().trim().toLowerCase()
  const cityName = (place.city || entry.slug).toString().trim().toLowerCase()
  const address = street ? street : `${entry.slug} default service area`
  const reporterHash = crypto.createHash('sha256').update(`recollect_${entry.slug}`).digest('hex').substring(0, 16)
  const now = new Date().toISOString()

  const row = {
    address, city: entry.slug, state: entry.state, zip_code: String(place.postal_code || '').trim(),
    neighborhood: cityName,
    collection_day: day,
    recycling_week: 'A',
    reporter_hash: reporterHash, verified: true, verification_count: 1,
    source: 'recollect_api', fetched_at: now,
    raw_payload_hash: crypto.createHash('md5').update(`${entry.place}${entry.service}`).digest('hex'),
    hauler: entry.hauler,
    data_source_url: `https://api.recollect.net/api/places/${entry.place}/services/${entry.service}/events`,
    data_source_type: 'api',
    lat: place.lat ?? null, lng: place.lng ?? null,
  }
  const { error } = await supabase.from('schedule_reports').upsert([row], { onConflict: 'address,city', ignoreDuplicates: true })
  if (error) {
    const { error: ie } = await supabase.from('schedule_reports').insert([row])
    if (ie) return { ok: false, reason: ie.message, slug: entry.slug }
  }
  return { ok: true, slug: entry.slug, day, address }
}

async function main() {
  console.log('🗑️  TrashAlert — ReCollect API Import')
  console.log('=====================================')
  let imported = 0, failed = 0
  for (const entry of PLACES) {
    try {
      const r = await processOne(entry)
      if (r.ok) { imported++; console.log(`  ✅ ${r.slug}: ${r.day} (${r.address})`) }
      else      { failed++;   console.log(`  ⚠️  ${entry.slug}: ${r.reason}`) }
    } catch (e) {
      failed++
      console.log(`  ❌ ${entry.slug}: ${e.message}`)
    }
    await new Promise(r => setTimeout(r, 250))
  }
  console.log(`\n🎉 ReCollect: imported=${imported} failed=${failed} of ${PLACES.length}`)
}
main().catch(e => { console.error('Fatal:', e); process.exit(1) })
