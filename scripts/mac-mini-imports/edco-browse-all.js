#!/usr/bin/env node
/**
 * EDCO Complete Index Scraper v2
 * Uses Algolia query API with alphabetical prefix searches to export ALL 303K+ records.
 * Algolia limits query results to 1000 pages — so we search by letter prefixes to stay under limits.
 */

const APP = 'TA4ET9PNBI';
const KEY = '09d4628a77899912b751f608ae0dd456';
const INDEX = 'collection_day';
const fs = require('fs');

async function query(searchQuery, page = 0) {
  const r = await fetch(`https://${APP}-dsn.algolia.net/1/indexes/${INDEX}/query`, {
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

async function getAllForPrefix(prefix) {
  const records = [];
  let page = 0;
  while (true) {
    const result = await query(prefix, page);
    if (!result.hits || result.hits.length === 0) break;
    records.push(...result.hits);
    if (page >= result.nbPages - 1) break;
    page++;
    await new Promise(r => setTimeout(r, 100));
  }
  return records;
}

async function main() {
  const outputFile = 'data/edco-all-303k.jsonl';
  if (!fs.existsSync('data')) fs.mkdirSync('data', { recursive: true });

  console.log('🗑️ EDCO Full Index Scraper v2 — ALL 303K+ records');
  console.log('===================================================');

  // Check total
  const check = await query('', 0);
  console.log(`Total in index: ${check.nbHits.toLocaleString()}`);
  console.log(`Max pages available for empty query: ${check.nbPages}`);

  const seen = new Set();
  const ws = fs.createWriteStream(outputFile);
  let totalWritten = 0;
  const regionCounts = {};
  const cityCounts = {};

  // Strategy: Addresses start with house numbers (1-99999)
  // Search by number prefixes: 1, 2, 3... 10, 11... 100, 101... etc.
  // Also search by street name starting letters for any that start with letters
  
  // Phase 1: Search by leading digits (covers most addresses like "123 Main St")
  const numPrefixes = [];
  // Single digits
  for (let i = 1; i <= 9; i++) numPrefixes.push(String(i));
  // Two-digit combos for thoroughness  
  for (let i = 10; i <= 99; i++) numPrefixes.push(String(i));
  // Three-digit for high-density ranges
  for (let i = 100; i <= 999; i++) numPrefixes.push(String(i));
  // Four-digit ranges
  for (let i = 1000; i <= 9999; i += 100) numPrefixes.push(String(i));
  for (let i = 10000; i <= 99999; i += 1000) numPrefixes.push(String(i));

  console.log(`Searching ${numPrefixes.length} numeric prefixes...`);

  let queriesMade = 0;
  for (const prefix of numPrefixes) {
    const result = await query(prefix, 0);
    if (!result.hits || result.hits.length === 0) {
      await new Promise(r => setTimeout(r, 50));
      queriesMade++;
      continue;
    }

    const totalHits = result.nbHits;
    let allHits = [...result.hits];

    // If more than 1000, paginate (max 100 pages in Algolia)
    if (totalHits > 1000) {
      const pages = Math.min(result.nbPages, 100);
      for (let p = 1; p < pages; p++) {
        const pr = await query(prefix, p);
        if (pr.hits) allHits.push(...pr.hits);
        await new Promise(r => setTimeout(r, 100));
        queriesMade++;
      }
    }

    let newCount = 0;
    for (const h of allHits) {
      if (seen.has(h.objectID)) continue;
      seen.add(h.objectID);

      const parts = (h.full || '').split(',').map(s => s.trim());
      const city = parts.length >= 2 ? parts[1] : 'Unknown';

      const rec = {
        address: h.full,
        day: h.day,
        dayName: ['', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'][h.day] || 'Unknown',
        region: h.region || 'Unknown',
        city,
        id: h.objectID,
      };
      ws.write(JSON.stringify(rec) + '\n');
      totalWritten++;
      newCount++;
      regionCounts[rec.region] = (regionCounts[rec.region] || 0) + 1;
      cityCounts[city] = (cityCounts[city] || 0) + 1;
    }

    queriesMade++;
    if (queriesMade % 100 === 0) {
      console.log(`Queries: ${queriesMade} | Prefix: "${prefix}" | Hits: ${totalHits} | New: ${newCount} | Total unique: ${totalWritten.toLocaleString()}`);
    }

    await new Promise(r => setTimeout(r, 80));
  }

  ws.end();

  console.log('\n📊 Records by Region (top 40):');
  Object.entries(regionCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 40)
    .forEach(([region, count]) => {
      console.log(`  ${count.toLocaleString().padStart(8)} ${region}`);
    });

  console.log('\n🏙️ Records by City (top 40):');
  Object.entries(cityCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 40)
    .forEach(([city, count]) => {
      console.log(`  ${count.toLocaleString().padStart(8)} ${city}`);
    });

  console.log(`\n✅ Wrote ${totalWritten.toLocaleString()} unique records to ${outputFile}`);
  console.log(`🔑 Total unique IDs seen: ${seen.size.toLocaleString()}`);
}

main().catch(console.error);
