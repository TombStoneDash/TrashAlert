#!/usr/bin/env node
/**
 * EDCO Full Index Scraper
 * Uses per-zip-code prefix queries to bypass Algolia's 1000-result limit.
 * Covers 303K+ addresses across SD County + parts of LA County.
 */

const APP = 'TA4ET9PNBI';
const KEY = '09d4628a77899912b751f608ae0dd456';
const fs = require('fs');

async function query(searchQuery, page = 0) {
  const r = await fetch(`https://${APP}-dsn.algolia.net/1/indexes/collection_day/query`, {
    method: 'POST',
    headers: {
      'X-Algolia-API-Key': KEY,
      'X-Algolia-Application-Id': APP,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query: searchQuery,
      hitsPerPage: 1000,
      page,
      attributesToRetrieve: ['full', 'day', 'region', 'objectID'],
    }),
  });
  return r.json();
}

async function getAllForQuery(searchQuery) {
  const records = [];
  let page = 0;
  while (true) {
    const result = await query(searchQuery, page);
    if (!result.hits || result.hits.length === 0) break;
    records.push(...result.hits);
    if (page >= result.nbPages - 1) break;
    page++;
    await new Promise(r => setTimeout(r, 120));
  }
  return records;
}

async function main() {
  const outputFile = process.argv[2] || 'data/edco-full.jsonl';
  if (!fs.existsSync('data')) fs.mkdirSync('data', { recursive: true });

  console.log('🗑️ EDCO Full Index Scraper');
  console.log('================================');

  // Strategy: Search by zip code prefixes (all SD + LA zips EDCO covers)
  // SD County: 919xx, 920xx, 921xx
  // LA County (EDCO areas): 907xx, 908xx, 906xx, 905xx, 904xx, 903xx, 902xx, 901xx, 900xx
  const zipPrefixes = [];
  
  // San Diego County (91901-92199)
  for (let i = 91900; i <= 92199; i++) zipPrefixes.push(String(i));
  
  // LA County EDCO areas
  for (let i = 90000; i <= 90899; i++) zipPrefixes.push(String(i));

  const seen = new Set();
  const ws = fs.createWriteStream(outputFile);
  let totalWritten = 0;
  const regionCounts = {};

  // Also search by common street number prefixes for comprehensive coverage
  // But zip codes should be more efficient
  
  // Actually, let's be smarter - search by the zip codes that appear in addresses
  // First, sample to find zip code patterns
  const sampleResult = await query('', 0);
  console.log(`Total in index: ${sampleResult.nbHits}`);

  // Search using each 5-digit zip code
  let queriesMade = 0;
  let emptyCount = 0;

  for (const zip of zipPrefixes) {
    const result = await query(zip, 0);
    if (result.nbHits === 0) {
      emptyCount++;
      continue;
    }

    // If more than 1000 hits, we need to paginate
    let allHits = [...result.hits];
    if (result.nbHits > 1000) {
      const pages = Math.min(result.nbPages, 100);
      for (let p = 1; p < pages; p++) {
        const pageResult = await query(zip, p);
        allHits.push(...pageResult.hits);
        await new Promise(r => setTimeout(r, 120));
        queriesMade++;
      }
    }

    let newCount = 0;
    for (const h of allHits) {
      if (seen.has(h.objectID)) continue;
      seen.add(h.objectID);
      
      const rec = {
        address: h.full,
        day: h.day,
        dayName: ['', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'][h.day] || 'Unknown',
        region: h.region || 'Unknown',
        id: h.objectID,
      };
      ws.write(JSON.stringify(rec) + '\n');
      totalWritten++;
      newCount++;
      regionCounts[rec.region] = (regionCounts[rec.region] || 0) + 1;
    }

    queriesMade++;
    if (queriesMade % 50 === 0) {
      console.log(`Queries: ${queriesMade} | Zip: ${zip} | New: ${newCount} | Total: ${totalWritten} | Empty: ${emptyCount}`);
    }
    
    await new Promise(r => setTimeout(r, 120));
  }

  ws.end();

  console.log('\n📊 Records by Region:');
  Object.entries(regionCounts)
    .sort((a, b) => b[1] - a[1])
    .forEach(([region, count]) => {
      console.log(`  ${region}: ${count.toLocaleString()}`);
    });

  console.log(`\nQueries made: ${queriesMade}`);
  console.log(`✅ Wrote ${totalWritten.toLocaleString()} unique records to ${outputFile}`);
}

main().catch(console.error);
