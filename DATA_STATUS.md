# TrashAlert Data Status

**Last updated:** 2026-04-15
**Total records in Supabase:** 3,442,121

## Supabase Database

- **URL:** `https://qsuzfemakaaroeakyick.supabase.co`
- **Table:** `schedule_reports`
- **Schema:** id, address, city, state, zip_code, neighborhood, collection_day, recycling_week, reporter_hash, verified, source, hauler, lat, lng

## Real Data vs Sample Data by City

### Cities with REAL data in Supabase

| City | Slug | Real Addresses | Source | Import Script |
|------|------|---------------|--------|---------------|
| San Antonio, TX | `san-antonio` | 346,580 | City ArcGIS | `import-san-antonio.mjs` |
| Dallas, TX | `dallas` | 253,286 | City ArcGIS | `import-dallas.mjs` |
| San Francisco, CA | `san-francisco` | 34,443 | City ArcGIS | `import-san-francisco.mjs` |
| Portland, OR | `portland` | 898 | City data | `import-portland.mjs` |
| **SD County (EDCO)** | *(multiple)* | **~274,000** | EDCO scraper | `import-274k.js` |

**SD County EDCO breakdown:**
| Suburb | Addresses |
|--------|-----------|
| Escondido | 31,916 |
| Vista | 20,440 |
| San Marcos | 18,829 |
| El Cajon | 17,786 |
| Encinitas | 16,754 |
| La Mesa | 14,908 |
| Fallbrook | 12,294 |
| Poway | 11,431 |
| Ramona | 9,431 |
| Spring Valley | 8,324 |
| National City | 6,251 |
| Lemon Grove | 5,768 |
| Imperial Beach | 4,004 |
| Lakeside | 3,194 |
| Coronado | 3,014 |
| Solana Beach | 3,061 |
| Bonita | 2,389 |
| Alpine | 1,809 |
| Jamul | 1,472 |
| Del Mar | 1,167 |
| Bonsall | 1,117 |

### Cities with SAMPLE data only (200 generated addresses each)

These cities have import scripts on the Mac Mini but the imports have **not been run** against Supabase yet. The `data/addresses_normalized.csv` has 200 sample addresses per city for API/map demo purposes.

| City | Slug | Sample | Import Script Exists | Data Source |
|------|------|--------|---------------------|-------------|
| San Diego, CA | `san-diego` | 200 | `import-sd-addresses.js` | SanGIS / City of SD 311 |
| Houston, TX | `houston` | 200 | `import-houston.mjs` | City ArcGIS (~474K eligible) |
| Phoenix, AZ | `phoenix` | 200 | `import-phoenix.mjs` | City ArcGIS |
| Austin, TX | `austin` | 200 | `import-austin.mjs` | City ArcGIS |
| Boston, MA | `boston` | 200 | `import-boston.mjs` | City ArcGIS |
| Denver, CO | `denver` | 200 | `import-denver-v2.mjs` | City ArcGIS |
| Chicago, IL | `chicago` | 200 | `import-chicago.mjs` | City ArcGIS |
| Seattle, WA | `seattle` | 200 | `import-seattle.mjs` | City ArcGIS (205 garbage + 287 recycling zones) |
| New York, NY | `new-york` | 200 | `import-nyc.mjs` | City ArcGIS |
| Los Angeles, CA | `los-angeles` | 200 | `import-la-county.mjs` | LA County ArcGIS (239 zones, unincorporated) |
| Philadelphia, PA | `philadelphia` | 200 | `import-philadelphia.mjs` | City ArcGIS |
| Charlotte, NC | `charlotte` | 200 | `import-charlotte.mjs` | City ArcGIS (848 zones) |
| Columbus, OH | `columbus` | 200 | `import-columbus.mjs` | City ArcGIS (15,678 refuse + 13,301 recycling) |
| Oklahoma City, OK | `oklahoma-city` | 200 | — | Behind WAF, needs browser scraping |
| Minneapolis, MN | `minneapolis` | 200 | — | No public GIS endpoint found |
| Detroit, MI | `detroit` | 200 | `import-detroit.mjs` | City ArcGIS (15 zones) |
| Atlanta, GA | `atlanta` | 200 | — | No public GIS endpoint found |
| Miami, FL | `miami` | 200 | `import-miami.mjs` | Miami-Dade ArcGIS (783 garbage routes) |

### NEW cities with import scripts (not yet run)

| City | Import Script | Data Source | Records |
|------|--------------|-------------|---------|
| Jacksonville, FL | `import-jacksonville.mjs` | City ArcGIS | 97 zones |
| Indianapolis, IN | `import-indianapolis.mjs` | City ArcGIS | 485 zones |
| Louisville, KY | `import-louisville.mjs` | City ArcGIS | ~50-100 zones |
| Baltimore, MD | `import-baltimore.mjs` | City ArcGIS (street segments) | 1,940 segments (~100K+ addresses) |
| Milwaukee, WI | `import-milwaukee.mjs` | City ArcGIS (day layers) | 442 routes |
| Kansas City, MO | `import-kansas-city.mjs` | City ArcGIS | 303 zones |
| Albuquerque, NM | `import-albuquerque.mjs` | City ArcGIS | 9 zones |
| Tucson, AZ | `import-tucson.mjs` | City ArcGIS | 238 B&B + 131 recycling |
| LA County | `import-la-county.mjs` | LA County ArcGIS | 239 zones |

### Cities with NO data (not yet added)

These cities have import scripts but no sample data or Supabase records:

| City | Import Script | Potential Addresses |
|------|--------------|-------------------|
| Pittsburgh, PA | `import-arcgis-cities.mjs` | ArcGIS feature service |
| Costa Mesa, CA | `import-arcgis-cities.mjs` | ArcGIS feature service |

### Cities with NO public GIS data available

| City | Reason |
|------|--------|
| LA City (proper) | LASAN schedule tool is proprietary, no public API |
| San Jose, CA | Private franchise haulers, no public GIS |
| Nashville, TN | New route system (Feb 2026) not exposed |
| Memphis, TN | Only 311 service requests, no routes |
| Las Vegas, NV | Republic Services contracted, no city data |
| Sacramento, CA | Only county-level refuse districts |
| Atlanta, GA | No waste layers in GIS portal |
| Oklahoma City, OK | Behind Incapsula WAF, needs browser scraping |

## Import Scripts (from Mac Mini `ops@100.110.188.111`)

Located at `~/Projects/trashalert/scripts/` on the Mac Mini. Copies stored in `scripts/mac-mini-imports/` in this repo.

| Script | Cities | Data Source | Records |
|--------|--------|-------------|---------|
| `import-274k.js` | SD County (EDCO suburbs) | EDCO scraper | ~274K |
| `import-houston.mjs` | Houston | City ArcGIS (COH Thiessen) | ~474K eligible |
| `import-san-antonio.mjs` | San Antonio | City ArcGIS | ~346K imported |
| `import-dallas.mjs` | Dallas | City ArcGIS | ~253K imported |
| `import-san-francisco.mjs` | San Francisco | City ArcGIS | ~34K imported |
| `import-phoenix.mjs` | Phoenix | City ArcGIS | Pending |
| `import-austin.mjs` | Austin | City ArcGIS | Pending |
| `import-boston.mjs` | Boston | City ArcGIS | Pending |
| `import-chicago.mjs` | Chicago | City ArcGIS | Pending |
| `import-denver-v2.mjs` | Denver | City ArcGIS | Pending |
| `import-nyc.mjs` | NYC | City ArcGIS | Pending |
| `import-philadelphia.mjs` | Philadelphia | City ArcGIS | Pending |
| `import-portland.mjs` | Portland | City data | ~898 imported |
| `import-arcgis-cities.mjs` | Pittsburgh, Costa Mesa | ArcGIS multi-city | Pending |
| `import-seattle.mjs` | Seattle | City ArcGIS | Pending (205+ zones) |
| `import-charlotte.mjs` | Charlotte | City ArcGIS | Pending (848 zones) |
| `import-columbus.mjs` | Columbus | City ArcGIS | Pending (15,678+13,301 zones) |
| `import-jacksonville.mjs` | Jacksonville | City ArcGIS | Pending (97 zones) |
| `import-indianapolis.mjs` | Indianapolis | City ArcGIS | Pending (485 zones) |
| `import-louisville.mjs` | Louisville | City ArcGIS | Pending (~50-100 zones) |
| `import-baltimore.mjs` | Baltimore | City ArcGIS (segments) | Pending (~100K+ addresses) |
| `import-milwaukee.mjs` | Milwaukee | City ArcGIS (day layers) | Pending (442 routes) |
| `import-kansas-city.mjs` | Kansas City | City ArcGIS | Pending (303 zones) |
| `import-detroit.mjs` | Detroit | City ArcGIS | Pending (15 zones) |
| `import-miami.mjs` | Miami-Dade | County ArcGIS | Pending (783 routes) |
| `import-albuquerque.mjs` | Albuquerque | City ArcGIS | Pending (9 zones) |
| `import-tucson.mjs` | Tucson | City ArcGIS | Pending (238+131 zones) |
| `import-la-county.mjs` | LA County | County ArcGIS | Pending (239 zones) |
| `edco-scraper.js` | SD County | EDCO website | Raw scrape |
| `edco-full-scraper.js` | SD County | EDCO website | Full scrape |
| `geocode-addresses.js` | All | Geocoding utility | — |
| `build-address-index.py` | All | Address index builder | — |

## How to Run Imports

```bash
# SSH to Mac Mini
ssh ops@100.110.188.111

# Navigate to project
cd ~/Projects/trashalert

# Copy new scripts from this repo first, then run:

# === STRATEGY 1: Run existing scripts (quick wins) ===
node --env-file=.env.local scripts/import-houston.mjs      # ~474K addresses
node --env-file=.env.local scripts/import-phoenix.mjs       # ~397K addresses
node --env-file=.env.local scripts/import-austin.mjs
node --env-file=.env.local scripts/import-boston.mjs
node --env-file=.env.local scripts/import-chicago.mjs
node --env-file=.env.local scripts/import-denver-v2.mjs
node --env-file=.env.local scripts/import-nyc.mjs
node --env-file=.env.local scripts/import-philadelphia.mjs

# === STRATEGY 2: New city import scripts ===
node --env-file=.env.local scripts/import-seattle.mjs
node --env-file=.env.local scripts/import-charlotte.mjs
node --env-file=.env.local scripts/import-columbus.mjs
node --env-file=.env.local scripts/import-jacksonville.mjs
node --env-file=.env.local scripts/import-indianapolis.mjs
node --env-file=.env.local scripts/import-louisville.mjs
node --env-file=.env.local scripts/import-baltimore.mjs     # ~100K+ from address ranges
node --env-file=.env.local scripts/import-milwaukee.mjs
node --env-file=.env.local scripts/import-kansas-city.mjs
node --env-file=.env.local scripts/import-detroit.mjs
node --env-file=.env.local scripts/import-miami.mjs
node --env-file=.env.local scripts/import-albuquerque.mjs
node --env-file=.env.local scripts/import-tucson.mjs
node --env-file=.env.local scripts/import-la-county.mjs
```

## Architecture Notes

- **Production Next.js app** reads from Supabase `schedule_reports` table
- **This FastAPI repo** reads from `data/addresses_normalized.csv` (sample data)
- The two systems are NOT connected — the FastAPI API serves sample data while the Next.js app serves real Supabase data
- To unify: update the FastAPI endpoints to query Supabase instead of CSV

## Priority Actions

1. **Run Strategy 1 imports** on Mac Mini: Houston (~474K), Phoenix (~397K), Austin, Boston, Chicago, Denver, NYC, Philadelphia
2. **Run Strategy 2 imports** on Mac Mini: Seattle, Charlotte, Columbus, Jacksonville, Indianapolis, Louisville, Baltimore (~100K+), Milwaukee, Kansas City, Detroit, Miami, Albuquerque, Tucson, LA County
3. **Zone extrapolation (Strategy 3)**: Build zones table + point-in-polygon lookup to count zone-covered addresses toward 50M total
4. **Connect FastAPI to Supabase** for the zone map API and lookup endpoints
5. **Backfill lat/lng** — many Supabase records have null coordinates (need geocoding)
6. **Research remaining cities** needing browser-based scraping: OKC, Nashville, Memphis, LA City, San Jose, Las Vegas, Sacramento, Atlanta
