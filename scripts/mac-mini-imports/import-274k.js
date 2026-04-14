#!/usr/bin/env node
/**
 * Import 274K EDCO records to Supabase (clean reimport)
 * Uses service_role key to bypass RLS for delete + insert
 */

const fs = require('fs');
const readline = require('readline');

const SUPABASE_URL = 'https://qsuzfemakaaroeakyick.supabase.co';
const SERVICE_KEY = 'REDACTED_USE_ENV_VAR';

const BATCH_SIZE = 500;
const DELAY_MS = 300;

const REGION_CITY = {
  'Alpine': 'alpine', 'Bonita': 'bonita', 'Bonsall': 'bonsall',
  'Borrego Springs': 'borrego springs', 'Buena Park': 'buena park',
  'CITY OF EL CAJON': 'el cajon', 'Campo': 'campo', 'Cardiff': 'cardiff',
  'City Of Escondido': 'escondido', 'City Of La Mesa': 'la mesa',
  'City Of San Marcos': 'san marcos', 'City Of Vista': 'vista',
  'Coronado': 'coronado', 'Del Mar': 'del mar', 'Descanso': 'descanso',
  'Dulzura': 'dulzura', 'El Cajon County': 'el cajon', 'El Segundo': 'el segundo',
  'Encinitas': 'encinitas', 'Escondido County': 'escondido',
  'Fallbrook': 'fallbrook', 'Guatay': 'guatay', 'Imperial Beach': 'imperial beach',
  'Jamul': 'jamul', 'Julian': 'julian', 'La Jolla': 'san diego',
  'La Mesa County': 'la mesa', 'La Mirada': 'la mirada', 'La Palma': 'la palma',
  'Lakeside': 'lakeside', 'Lakewood': 'lakewood', 'Lemon Grove': 'lemon grove',
  'Long Beach': 'long beach', 'National City': 'national city',
  'Pala': 'pala', 'Pauma Valley': 'pauma valley', 'Pine Valley': 'pine valley',
  'Poway': 'poway', 'Ramona': 'ramona', 'Rancho Santa Fe': 'rancho santa fe',
  'Rpv': 'rancho palos verdes', 'San Diego': 'san diego',
  'San Marcos County': 'san marcos', 'Santa Ysabel': 'santa ysabel',
  'Signal Hill': 'signal hill', 'Solana Beach': 'solana beach',
  'Spring Valley': 'spring valley', 'Valley Center': 'valley center',
  'Vista County': 'vista', 'Warner Springs': 'warner springs',
};

const headers = {
  'apikey': SERVICE_KEY,
  'Authorization': `Bearer ${SERVICE_KEY}`,
  'Content-Type': 'application/json',
};

async function deleteEdcoRecords() {
  console.log('🗑️ Deleting existing EDCO records...');
  const r = await fetch(`${SUPABASE_URL}/rest/v1/schedule_reports?source=eq.edco`, {
    method: 'DELETE',
    headers: { ...headers, 'Prefer': 'return=minimal' },
  });
  console.log(`Delete status: ${r.status}`);

  // Also delete any test records
  await fetch(`${SUPABASE_URL}/rest/v1/schedule_reports?reporter_hash=like.edco-v2*`, {
    method: 'DELETE',
    headers: { ...headers, 'Prefer': 'return=minimal' },
  });

  // Verify count
  const r2 = await fetch(`${SUPABASE_URL}/rest/v1/schedule_reports?select=count`, {
    headers: { ...headers, 'Prefer': 'count=exact', 'Range': '0-0' },
  });
  console.log(`Remaining records after delete: ${r2.headers.get('content-range')}`);
}

async function importBatch(records) {
  const res = await fetch(`${SUPABASE_URL}/rest/v1/schedule_reports`, {
    method: 'POST',
    headers: { ...headers, 'Prefer': 'return=minimal' },
    body: JSON.stringify(records),
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`${res.status}: ${err.substring(0, 200)}`);
  }
  return 'ok';
}

async function main() {
  const inputFile = 'data/edco-all-303k.jsonl';
  console.log('📥 EDCO 274K Import — Clean Reimport');
  console.log('=====================================');

  // Step 1: Delete existing EDCO records
  await deleteEdcoRecords();

  // Step 2: Import all 274K records
  const total = fs.readFileSync(inputFile, 'utf8').split('\n').filter(l => l.trim()).length;
  console.log(`\n📊 Importing ${total.toLocaleString()} records...`);

  const fileStream = fs.createReadStream(inputFile);
  const rl = readline.createInterface({ input: fileStream, crlfDelay: Infinity });

  let batch = [];
  let imported = 0;
  let errors = 0;
  let batchNum = 0;
  const now = new Date().toISOString();
  const startTime = Date.now();

  for await (const line of rl) {
    if (!line.trim()) continue;
    const rec = JSON.parse(line);
    const parts = rec.address.split(',').map(s => s.trim());
    const cityName = REGION_CITY[rec.region] || rec.city?.toLowerCase() || (parts[1] || '').toLowerCase();

    batch.push({
      address: rec.address,
      city: cityName,
      state: 'CA',
      zip_code: parts[parts.length - 1] || '',
      neighborhood: rec.region,
      collection_day: rec.dayName.toLowerCase(),
      recycling_week: 'A',
      reporter_hash: `edco-import-${rec.id}`,
      verified: true,
      verification_count: 10,
      source: 'edco',
      hauler: 'EDCO',
      data_source_type: 'api',
      data_source_url: 'https://edcodisposal.com',
      fetched_at: now,
    });

    if (batch.length >= BATCH_SIZE) {
      batchNum++;
      try {
        await importBatch(batch);
        imported += batch.length;
      } catch (err) {
        console.error(`Batch ${batchNum} error: ${err.message}`);
        // Try smaller chunks
        for (let i = 0; i < batch.length; i += 50) {
          try {
            await importBatch(batch.slice(i, i + 50));
            imported += Math.min(50, batch.length - i);
          } catch (e2) {
            errors += Math.min(50, batch.length - i);
          }
          await new Promise(r => setTimeout(r, 100));
        }
      }

      if (batchNum % 20 === 0) {
        const pct = ((imported / total) * 100).toFixed(1);
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(0);
        const rate = (imported / (elapsed || 1)).toFixed(0);
        console.log(`Batch ${batchNum} | ${imported.toLocaleString()}/${total.toLocaleString()} (${pct}%) | ${rate} rec/s | Errors: ${errors}`);
      }
      batch = [];
      await new Promise(r => setTimeout(r, DELAY_MS));
    }
  }

  if (batch.length > 0) {
    try {
      await importBatch(batch);
      imported += batch.length;
    } catch (err) {
      errors += batch.length;
    }
  }

  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  console.log(`\n✅ Import complete in ${elapsed}s!`);
  console.log(`   Imported: ${imported.toLocaleString()}`);
  console.log(`   Errors:   ${errors.toLocaleString()}`);

  // Verify final count
  const r = await fetch(`${SUPABASE_URL}/rest/v1/schedule_reports?select=count`, {
    headers: { ...headers, 'Prefer': 'count=exact', 'Range': '0-0' },
  });
  console.log(`   Total in DB: ${r.headers.get('content-range')}`);
}

main().catch(console.error);
