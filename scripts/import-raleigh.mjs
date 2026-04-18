#!/usr/bin/env node
/**
 * Import Raleigh NC waste collection schedules — PLACEHOLDER.
 *
 * STATUS: No public ArcGIS FeatureServer URL confirmed for solid-waste
 * collection days during initial research (2026-04-16).
 *
 * WHAT WAS SEARCHED:
 *   - https://data-ral.opendata.arcgis.com/  → Open Data Raleigh portal
 *     (browsed for "trash", "solid waste", "collection" — no direct match in
 *     the first page of datasets; deeper search required)
 *   - https://raleighnc.gov/apps-maps-and-open-data  → portal index
 *   - https://www.lib.ncsu.edu/gis/raleigh  → NCSU curated list (no match)
 *   - Wake County GIS → no city-of-Raleigh waste layer
 *
 * WHY IT FAILED:
 *   Raleigh Solid Waste Services publishes a resident-facing address lookup
 *   at raleighnc.gov but the backing data layer is not linked prominently
 *   from the open-data hub.  It likely exists — the hub supports
 *   ArcGIS FeatureServer for many operational datasets — but needs manual
 *   search or a direct city-IT inquiry.
 *
 * NEXT STEPS TO PROMOTE THIS TO A REAL IMPORT:
 *   1. Search data-ral.opendata.arcgis.com for "Collection", "Solid Waste",
 *      "Sanitation", "Yard Waste", "Recycling Route".
 *   2. If the hub doesn't surface it, email gisadmin@raleighnc.gov requesting
 *      the Solid Waste Services routes FeatureServer.
 *   3. Alternative: scrape raleighnc.gov/services/solid-waste (per-address).
 *
 * When a URL is confirmed, model this script on scripts/import-charlotte.mjs
 * (same state, similar multi-service-type pattern — GARB / RECY / YARD).
 */
console.error('[raleigh] placeholder — no public data source identified yet.')
console.error('[raleigh] see comment header for search trail and next steps.')
process.exit(2)
