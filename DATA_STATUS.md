# TrashAlert Data Status

**Last updated:** 2026-04-14
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
| Seattle, WA | `seattle` | 200 | No script yet | — |
| New York, NY | `new-york` | 200 | `import-nyc.mjs` | City ArcGIS |
| Los Angeles, CA | `los-angeles` | 200 | No script yet | — |
| Philadelphia, PA | `philadelphia` | 200 | `import-philadelphia.mjs` | City ArcGIS |
| Charlotte, NC | `charlotte` | 200 | No script yet | — |
| Columbus, OH | `columbus` | 200 | No script yet | — |
| Oklahoma City, OK | `oklahoma-city` | 200 | No script yet | — |
| Minneapolis, MN | `minneapolis` | 200 | No script yet | — |
| Detroit, MI | `detroit` | 200 | No script yet | — |
| Atlanta, GA | `atlanta` | 200 | No script yet | — |
| Miami, FL | `miami` | 200 | No script yet | — |

### Cities with NO data (not yet added)

These cities have import scripts but no sample data or Supabase records:

| City | Import Script | Potential Addresses |
|------|--------------|-------------------|
| Pittsburgh, PA | `import-arcgis-cities.mjs` | ArcGIS feature service |
| Costa Mesa, CA | `import-arcgis-cities.mjs` | ArcGIS feature service |

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

# Run a city import (uses .env.local for Supabase credentials)
node --env-file=.env.local scripts/import-houston.mjs
node --env-file=.env.local scripts/import-phoenix.mjs
node --env-file=.env.local scripts/import-austin.mjs
# etc.
```

## Architecture Notes

- **Production Next.js app** reads from Supabase `schedule_reports` table
- **This FastAPI repo** reads from `data/addresses_normalized.csv` (sample data)
- The two systems are NOT connected — the FastAPI API serves sample data while the Next.js app serves real Supabase data
- To unify: update the FastAPI endpoints to query Supabase instead of CSV

## Priority Actions

1. **Run pending imports** on Mac Mini: Houston (~474K), Phoenix, Austin, Boston, Chicago, Denver, NYC, Philadelphia
2. **Connect FastAPI to Supabase** for the zone map API and lookup endpoints
3. **Backfill lat/lng** — many Supabase records have null coordinates (need geocoding)
