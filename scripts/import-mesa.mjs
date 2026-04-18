#!/usr/bin/env node
/**
 * Import Mesa AZ waste collection schedules — PLACEHOLDER.
 *
 * STATUS: No public ArcGIS FeatureServer URL located for solid-waste
 * collection days during initial research (2026-04-16).
 *
 * WHAT WAS SEARCHED:
 *   - https://opengis.mesaaz.gov/   → Mesa Open GIS portal (no waste layer exposed)
 *   - https://gis.mesaaz.gov/Html5Viewer/  → interactive map only (no public API)
 *   - https://www.mesaaz.gov/Utilities/Trash-Recycling  → address-lookup tool, no API
 *   - ArcGIS Hub dataset search for "mesa solid waste" → no match
 *
 * WHY IT FAILED:
 *   Mesa uses an internal GIS that powers the Html5Viewer widget but does
 *   not publish its solid-waste schedule layer as a public FeatureServer.
 *   The resident-facing tool at mesaaz.gov scrapes into a private service.
 *
 * NEXT STEPS TO PROMOTE THIS TO A REAL IMPORT:
 *   1. Inspect XHR calls on gis.mesaaz.gov/Html5Viewer — capture the
 *      backing service URL (likely a private proxy into gis.mesaaz.gov).
 *   2. Contact Mesa Solid Waste Division (480-644-6789) and request API
 *      access or a flat export (GeoJSON / shapefile of collection zones).
 *   3. If neither works, fall back to scraping mesaaz.gov's address lookup
 *      (one-request-per-address) behind a polite rate limit.
 *
 * When a URL is confirmed, model this script on scripts/import-albuquerque.mjs
 * (single-layer zone polygons with Pickup_Day field).
 */
console.error('[mesa] placeholder — no public data source identified yet.')
console.error('[mesa] see comment header for search trail and next steps.')
process.exit(2)
