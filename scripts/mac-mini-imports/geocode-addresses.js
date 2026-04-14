#!/usr/bin/env node
/**
 * Geocode addresses in Supabase using Mapbox Geocoding API
 * Free tier: 100K requests/month
 * Rate limit: 600 requests/minute
 */

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN || 'REDACTED_USE_ENV_VAR';
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://qsuzfemakaaroeakyick.supabase.co';
const SUPABASE_KEY = 'REDACTED_USE_ENV_VAR';

const BATCH_SIZE = 50; // Update batch size for Supabase
const RATE_LIMIT_MS = 110; // ~9 req/sec (well under 600/min)

async function geocode(address) {
  const encoded = encodeURIComponent(address);
  const url = `https://api.mapbox.com/geocoding/v5/mapbox.places/${encoded}.json?access_token=${MAPBOX_TOKEN}&limit=1&country=US`;
  const res = await fetch(url);
  if (!res.ok) {
    if (res.status === 429) {
      console.log('  Rate limited, waiting 5s...');
      await new Promise(r => setTimeout(r, 5000));
      return geocode(address); // retry
    }
    throw new Error(`Mapbox ${res.status}`);
  }
  const data = await res.json();
  if (data.features && data.features.length > 0) {
    const [lng, lat] = data.features[0].center;
    return { lat, lng };
  }
  return null;
}

async function getUngeocodedRecords(offset, limit) {
  const res = await fetch(
    `${SUPABASE_URL}/rest/v1/schedule_reports?lat=is.null&select=id,address&offset=${offset}&limit=${limit}&order=id`,
    { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` } }
  );
  return res.json();
}

async function updateRecord(id, lat, lng) {
  const res = await fetch(
    `${SUPABASE_URL}/rest/v1/schedule_reports?id=eq.${id}`,
    {
      method: 'PATCH',
      headers: {
        apikey: SUPABASE_KEY,
        Authorization: `Bearer ${SUPABASE_KEY}`,
        'Content-Type': 'application/json',
        Prefer: 'return=minimal',
      },
      body: JSON.stringify({ lat, lng }),
    }
  );
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Update failed: ${err}`);
  }
}

async function updateBatch(updates) {
  // Batch update via individual PATCH calls (Supabase doesn't support bulk PATCH easily)
  for (const { id, lat, lng } of updates) {
    await updateRecord(id, lat, lng);
  }
}

async function main() {
  console.log('🌍 Geocoding TrashAlert addresses via Mapbox');
  console.log('=============================================');
  
  // First check how many need geocoding
  const countRes = await fetch(
    `${SUPABASE_URL}/rest/v1/schedule_reports?lat=is.null&select=count`,
    { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}`, Prefer: 'count=exact' } }
  );
  const totalCount = countRes.headers.get('content-range');
  console.log(`Records needing geocoding: ${totalCount}`);
  
  let offset = 0;
  let totalGeocoded = 0;
  let totalFailed = 0;
  const startTime = Date.now();
  
  while (true) {
    const records = await getUngeocodedRecords(offset, BATCH_SIZE);
    if (!records || records.length === 0) break;
    
    for (const rec of records) {
      try {
        const coords = await geocode(rec.address);
        if (coords) {
          await updateRecord(rec.id, coords.lat, coords.lng);
          totalGeocoded++;
        } else {
          totalFailed++;
        }
      } catch (err) {
        console.error(`  Error geocoding "${rec.address}": ${err.message}`);
        totalFailed++;
      }
      
      await new Promise(r => setTimeout(r, RATE_LIMIT_MS));
    }
    
    // Don't increment offset since we're filtering by lat=is.null and updating them
    // Records we've geocoded will no longer appear in the query
    
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(0);
    const rate = (totalGeocoded / (elapsed / 60)).toFixed(0);
    console.log(`Geocoded: ${totalGeocoded} | Failed: ${totalFailed} | Rate: ${rate}/min | Elapsed: ${elapsed}s`);
    
    // Safety: stop at 95K to stay under 100K/month free tier
    if (totalGeocoded >= 95000) {
      console.log('⚠️ Approaching Mapbox free tier limit, stopping');
      break;
    }
  }
  
  const elapsed = ((Date.now() - startTime) / 1000 / 60).toFixed(1);
  console.log(`\n✅ Done! Geocoded: ${totalGeocoded} | Failed: ${totalFailed} | Time: ${elapsed} minutes`);
}

main().catch(console.error);
