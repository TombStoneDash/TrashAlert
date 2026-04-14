#!/usr/bin/env node
/**
 * EDCO Algolia Index Scraper
 * Pulls all 303K+ addresses with pickup day data from EDCO's public Algolia index
 * 
 * Data format per record:
 * { full: "1791 York View Cir, Vista, CA, 92084", day: 2, region: "Vista County" }
 * day: 1=Monday, 2=Tuesday, 3=Wednesday, 4=Thursday, 5=Friday
 */

const ALGOLIA_APP_ID = 'TA4ET9PNBI';
const ALGOLIA_API_KEY = '09d4628a77899912b751f608ae0dd456';
const INDEX_NAME = 'collection_day';
const HITS_PER_PAGE = 1000;

async function queryAlgolia(page = 0) {
  const res = await fetch(
    `https://${ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/${INDEX_NAME}/query`,
    {
      method: 'POST',
      headers: {
        'X-Algolia-API-Key': ALGOLIA_API_KEY,
        'X-Algolia-Application-Id': ALGOLIA_APP_ID,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        query: '',
        hitsPerPage: HITS_PER_PAGE,
        page,
        attributesToRetrieve: ['full', 'day', 'region', 'objectID'],
      }),
    }
  );
  return res.json();
}

async function browseAlgolia() {
  // Use browse endpoint for full index export
  const res = await fetch(
    `https://${ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/${INDEX_NAME}/browse`,
    {
      method: 'POST',
      headers: {
        'X-Algolia-API-Key': ALGOLIA_API_KEY,
        'X-Algolia-Application-Id': ALGOLIA_APP_ID,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        params: `hitsPerPage=${HITS_PER_PAGE}`,
      }),
    }
  );
  return res.json();
}

async function browseAlgoliaCursor(cursor) {
  const res = await fetch(
    `https://${ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/${INDEX_NAME}/browse`,
    {
      method: 'POST',
      headers: {
        'X-Algolia-API-Key': ALGOLIA_API_KEY,
        'X-Algolia-Application-Id': ALGOLIA_APP_ID,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        cursor,
      }),
    }
  );
  return res.json();
}

async function main() {
  const fs = require('fs');
  const outputFile = process.argv[2] || 'edco-data.jsonl';
  
  console.log('🗑️ EDCO Algolia Index Scraper');
  console.log('================================');
  
  // First check total
  const initial = await queryAlgolia(0);
  console.log(`Total records: ${initial.nbHits}`);
  console.log(`Max pages available: ${initial.nbPages} (Algolia limits to 1000 pages)`);
  
  // Algolia search API limits to 1000 pages. With 1000 hits/page = 1M max (enough for 303K)
  const totalPages = Math.min(initial.nbPages, 1000);
  
  // Ensure data dir exists
  if (!fs.existsSync('data')) fs.mkdirSync('data', { recursive: true });
  
  const ws = fs.createWriteStream(outputFile);
  let totalWritten = 0;
  const regionCounts = {};
  
  for (let page = 0; page < totalPages; page++) {
    const result = await queryAlgolia(page);
    
    for (const h of result.hits) {
      const rec = {
        address: h.full,
        day: h.day,
        dayName: ['', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'][h.day] || 'Unknown',
        region: h.region || 'Unknown',
        id: h.objectID,
      };
      ws.write(JSON.stringify(rec) + '\n');
      totalWritten++;
      regionCounts[rec.region] = (regionCounts[rec.region] || 0) + 1;
    }
    
    if (page % 10 === 0 || page === totalPages - 1) {
      console.log(`Page ${page + 1}/${totalPages}: ${totalWritten.toLocaleString()} records`);
    }
    
    // Rate limit: 150ms between requests
    await new Promise(r => setTimeout(r, 150));
  }
  
  ws.end();
  
  console.log('\n📊 Records by Region:');
  Object.entries(regionCounts)
    .sort((a, b) => b[1] - a[1])
    .forEach(([region, count]) => {
      console.log(`  ${region}: ${count.toLocaleString()}`);
    });
  
  console.log(`\n✅ Wrote ${totalWritten.toLocaleString()} records to ${outputFile}`);
}

main().catch(console.error);
