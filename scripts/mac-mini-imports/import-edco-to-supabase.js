#!/usr/bin/env node
/**
 * Import EDCO scraped data into Supabase schedule_reports table
 * Maps EDCO regions to city names and parses addresses for zip codes
 */

const fs = require('fs');
const readline = require('readline');

const SUPABASE_URL = 'https://qsuzfemakaaroeakyick.supabase.co';
const SUPABASE_KEY = process.env.SUPABASE_KEY || 'REDACTED_USE_ENV_VAR';

const BATCH_SIZE = 500;

// Map EDCO regions to proper city names
const REGION_TO_CITY = {
  'Alpine': 'alpine',
  'Bonita': 'bonita',
  'Bonsall': 'bonsall',
  'Buena Park': 'buena park',
  'CITY OF EL CAJON': 'el cajon',
  'Campo': 'campo',
  'City Of Escondido': 'escondido',
  'City Of La Mesa': 'la mesa',
  'City Of San Marcos': 'san marcos',
  'City Of Vista': 'vista',
  'Coronado': 'coronado',
  'Del Mar': 'del mar',
  'Descanso': 'descanso',
  'Dulzura': 'dulzura',
  'El Cajon County': 'el cajon',
  'El Segundo': 'el segundo',
  'Encinitas': 'encinitas',
  'Escondido County': 'escondido',
  'Fallbrook': 'fallbrook',
  'Guatay': 'guatay',
  'Imperial Beach': 'imperial beach',
  'Jamul': 'jamul',
  'La Jolla': 'san diego',
  'La Mesa County': 'la mesa',
  'La Mirada': 'la mirada',
  'La Palma': 'la palma',
  'Lakeside': 'lakeside',
  'Lakewood': 'lakewood',
  'Lemon Grove': 'lemon grove',
  'Long Beach': 'long beach',
  'National City': 'national city',
  'Pala': 'pala',
  'Pauma Valley': 'pauma valley',
  'Pine Valley': 'pine valley',
  'Poway': 'poway',
  'Ramona': 'ramona',
  'Rancho Santa Fe': 'rancho santa fe',
  'Rpv': 'rancho palos verdes',
  'San Diego': 'san diego',
  'San Marcos County': 'san marcos',
  'Signal Hill': 'signal hill',
  'Solana Beach': 'solana beach',
  'Spring Valley': 'spring valley',
  'Valley Center': 'valley center',
  'Vista County': 'vista',
};

function parseAddress(fullAddress) {
  // Format: "1791 York View Cir, Vista, CA, 92084"
  const parts = fullAddress.split(',').map(s => s.trim());
  const zip = parts[parts.length - 1] || '';
  const state = parts[parts.length - 2] || 'CA';
  const city = parts[parts.length - 3] || '';
  const street = parts[0] || fullAddress;
  return { street, city, state, zip };
}

function generateReporterHash(id) {
  // Simple hash for the EDCO import batch
  return `edco-import-${id}`;
}

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
    throw new Error(`Supabase error ${res.status}: ${err}`);
  }
  return res.status;
}

async function main() {
  const inputFile = process.argv[2] || 'data/edco-full.jsonl';
  
  console.log('📥 Importing EDCO data to Supabase');
  console.log('===================================');
  
  const fileStream = fs.createReadStream(inputFile);
  const rl = readline.createInterface({ input: fileStream, crlfDelay: Infinity });
  
  let batch = [];
  let totalImported = 0;
  let totalSkipped = 0;
  let batchNum = 0;
  
  for await (const line of rl) {
    if (!line.trim()) continue;
    
    const rec = JSON.parse(line);
    const parsed = parseAddress(rec.address);
    const cityName = REGION_TO_CITY[rec.region] || parsed.city.toLowerCase();
    
    // Build schedule_reports record
    const report = {
      address: rec.address,
      city: cityName,
      state: 'CA',
      zip_code: parsed.zip,
      neighborhood: rec.region,
      collection_day: rec.dayName.toLowerCase(),
      recycling_week: 'A', // Default; EDCO data doesn't include this
      reporter_hash: generateReporterHash(rec.id),
      verified: true, // EDCO is the official hauler
      verification_count: 10, // High confidence
      source: 'edco',
      fetched_at: new Date().toISOString(),
    };
    
    batch.push(report);
    
    if (batch.length >= BATCH_SIZE) {
      try {
        await importBatch(batch);
        totalImported += batch.length;
        batchNum++;
        if (batchNum % 10 === 0) {
          console.log(`Batch ${batchNum}: ${totalImported.toLocaleString()} imported`);
        }
      } catch (err) {
        console.error(`Batch ${batchNum} failed: ${err.message}`);
        totalSkipped += batch.length;
      }
      batch = [];
      // Rate limit
      await new Promise(r => setTimeout(r, 200));
    }
  }
  
  // Final batch
  if (batch.length > 0) {
    try {
      await importBatch(batch);
      totalImported += batch.length;
    } catch (err) {
      console.error(`Final batch failed: ${err.message}`);
      totalSkipped += batch.length;
    }
  }
  
  console.log(`\n✅ Import complete!`);
  console.log(`   Imported: ${totalImported.toLocaleString()}`);
  console.log(`   Skipped: ${totalSkipped.toLocaleString()}`);
}

main().catch(console.error);
