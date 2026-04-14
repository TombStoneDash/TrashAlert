#!/usr/bin/env node
/**
 * Import remaining EDCO records that weren't imported in the first run.
 * Checks against existing reporter_hash values to avoid duplicates.
 */

const fs = require('fs');
const readline = require('readline');

const SUPABASE_URL = 'https://qsuzfemakaaroeakyick.supabase.co';
const SUPABASE_KEY = 'REDACTED_USE_ENV_VAR';
const BATCH_SIZE = 200;

const REGION_TO_CITY = {
  'Alpine': 'alpine', 'Bonita': 'bonita', 'Bonsall': 'bonsall',
  'Buena Park': 'buena park', 'CITY OF EL CAJON': 'el cajon', 'Campo': 'campo',
  'City Of Escondido': 'escondido', 'City Of La Mesa': 'la mesa',
  'City Of San Marcos': 'san marcos', 'City Of Vista': 'vista',
  'Coronado': 'coronado', 'Del Mar': 'del mar', 'Descanso': 'descanso',
  'Dulzura': 'dulzura', 'El Cajon County': 'el cajon', 'El Segundo': 'el segundo',
  'Encinitas': 'encinitas', 'Escondido County': 'escondido',
  'Fallbrook': 'fallbrook', 'Guatay': 'guatay', 'Imperial Beach': 'imperial beach',
  'Jamul': 'jamul', 'La Jolla': 'san diego', 'La Mesa County': 'la mesa',
  'La Mirada': 'la mirada', 'La Palma': 'la palma', 'Lakeside': 'lakeside',
  'Lakewood': 'lakewood', 'Lemon Grove': 'lemon grove', 'Long Beach': 'long beach',
  'National City': 'national city', 'Pala': 'pala', 'Pauma Valley': 'pauma valley',
  'Pine Valley': 'pine valley', 'Poway': 'poway', 'Ramona': 'ramona',
  'Rancho Santa Fe': 'rancho santa fe', 'Rpv': 'rancho palos verdes',
  'San Diego': 'san diego', 'San Marcos County': 'san marcos',
  'Signal Hill': 'signal hill', 'Solana Beach': 'solana beach',
  'Spring Valley': 'spring valley', 'Valley Center': 'valley center',
  'Vista County': 'vista',
};

async function importBatch(records) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/schedule_reports`, {
    method: 'POST',
    headers: {
      'apikey': SUPABASE_KEY,
      'Authorization': `Bearer ${SUPABASE_KEY}`,
      'Content-Type': 'application/json',
      'Prefer': 'resolution=ignore-duplicates,return=minimal',
    },
    body: JSON.stringify(records),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Supabase ${res.status}: ${err}`);
  }
}

async function getExistingHashes() {
  // Get all existing EDCO reporter_hashes to skip
  const hashes = new Set();
  let offset = 0;
  const limit = 1000;
  
  while (true) {
    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/schedule_reports?source=eq.edco&select=reporter_hash&offset=${offset}&limit=${limit}`,
      { headers: { apikey: SUPABASE_KEY, Authorization: `Bearer ${SUPABASE_KEY}` } }
    );
    const data = await res.json();
    if (data.length === 0) break;
    for (const d of data) hashes.add(d.reporter_hash);
    offset += limit;
    if (offset % 10000 === 0) console.log(`  Loaded ${hashes.size} existing hashes...`);
  }
  
  return hashes;
}

async function main() {
  const inputFile = process.argv[2] || 'data/edco-full.jsonl';
  
  console.log('📥 EDCO Remaining Import');
  console.log('========================');
  
  // Step 1: Get existing hashes
  console.log('Loading existing records...');
  const existingHashes = await getExistingHashes();
  console.log(`Found ${existingHashes.size} existing EDCO records`);
  
  // Step 2: Read JSONL and find missing records
  const rl = readline.createInterface({ input: fs.createReadStream(inputFile), crlfDelay: Infinity });
  
  let batch = [];
  let totalImported = 0;
  let totalSkipped = 0;
  let batchNum = 0;
  
  for await (const line of rl) {
    if (!line.trim()) continue;
    const rec = JSON.parse(line);
    const hash = `edco-import-${rec.id}`;
    
    if (existingHashes.has(hash)) {
      totalSkipped++;
      continue;
    }
    
    const parts = rec.address.split(',').map(s => s.trim());
    const zip = parts[parts.length - 1] || '';
    const cityName = REGION_TO_CITY[rec.region] || (parts[parts.length - 3] || '').toLowerCase();
    
    batch.push({
      address: rec.address,
      city: cityName,
      state: 'CA',
      zip_code: zip,
      neighborhood: rec.region,
      collection_day: rec.dayName.toLowerCase(),
      recycling_week: 'A',
      reporter_hash: hash,
      verified: true,
      verification_count: 10,
      source: 'edco',
      fetched_at: new Date().toISOString(),
    });
    
    if (batch.length >= BATCH_SIZE) {
      try {
        await importBatch(batch);
        totalImported += batch.length;
        batchNum++;
        if (batchNum % 5 === 0) {
          console.log(`Batch ${batchNum}: +${totalImported} imported, ${totalSkipped} skipped`);
        }
      } catch (err) {
        console.error(`Batch ${batchNum} failed: ${err.message}`);
        // Try smaller batches on failure
        for (let i = 0; i < batch.length; i += 50) {
          try {
            const smallBatch = batch.slice(i, i + 50);
            await importBatch(smallBatch);
            totalImported += smallBatch.length;
          } catch (e2) {
            console.error(`  Sub-batch failed: ${e2.message.substring(0, 100)}`);
          }
          await new Promise(r => setTimeout(r, 200));
        }
      }
      batch = [];
      await new Promise(r => setTimeout(r, 150));
    }
  }
  
  // Final batch
  if (batch.length > 0) {
    try {
      await importBatch(batch);
      totalImported += batch.length;
    } catch (err) {
      console.error(`Final batch: ${err.message}`);
    }
  }
  
  console.log(`\n✅ Done! Imported: ${totalImported} | Skipped (existing): ${totalSkipped}`);
}

main().catch(console.error);
