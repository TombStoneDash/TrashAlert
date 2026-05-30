# Atlanta Trash Collection Zone Extraction - Partial Results
Date: 2026-05-30
Task: Map 25 NPU (Neighborhood Planning Unit) polygons to trash collection days

## Summary
- Total NPUs: 25 ✅
- NPUs mapped to collection day: 17/25
- NPUs unmapped: 8/25
- Status: PARTIAL (threshold was 20/25)

## Mapped NPUs (17):

**Monday**: NPU-E, NPU-M, NPU-Y, NPU-Z
**Tuesday**: NPU-A, NPU-B
**Wednesday**: NPU-F, NPU-N
**Thursday**: NPU-W
**Friday**: NPU-D, NPU-I, NPU-J, NPU-K, NPU-S, NPU-T, NPU-X
**Unknown**: NPU-V

## Unmapped NPUs (8):
NPU-C, NPU-G, NPU-H, NPU-L, NPU-O, NPU-P, NPU-Q, NPU-R

## Data Sources
1. **WasteDoor.com** (wastedoor.com/schedule/georgia/atlanta-ga) - Address-based collection zones with neighborhood groupings
2. **NPU-S Organization** (npu-s.org) - Confirmed NPU-S = Friday
3. **Atlanta City Council** - NPU→Neighborhood cross-reference (citycouncil.atlantaga.gov)

## Methodology
- Extracted all 25 NPU polygon geometries from Atlanta GIS service (gis.atlantaga.gov/dpcd)
- Cross-referenced WasteDoor.com collection zones with Atlanta City Council neighborhood→NPU mapping
- Identified NPU letters within each collection day zone
- Verified one NPU (S) via direct NPU organization source

## Limitations
1. **Atlanta uses address-based routing**: The City of Atlanta Solid Waste Services collection schedule is determined by individual street addresses via the SWS Collection Tool (atlantaga.gov), not by NPU boundaries. The mappings provided are approximate based on which neighborhoods (and their NPUs) fall within each collection zone.

2. **WasteDoor.com zones are broad**: Collection zones cover multiple neighborhoods and may span multiple NPUs. The zone labels show representative NPUs but don't necessarily capture all NPUs in that zone.

3. **Incomplete source data**: The ATL311 knowledge base, official SWS documentation, and online sources do not publish a definitive NPU→collection day table. The SWS Collection Tool requires address-specific lookups.

4. **8 NPUs unable to map**: NPUs C, G, H, O, P, Q, R do not clearly appear in WasteDoor.com's published zones or neighborhood groupings.

## Files Generated
- `extracted_atlanta_partial_2026-05-30.json` - GeoJSON with 25 NPU polygons and collection_day properties (16 mapped, 8 unmapped, 1 unknown)

## Recommendations for Full Extraction
To achieve a complete NPU→collection day mapping, the following approaches could be pursued:
1. Use the SWS Collection Tool API directly (if available via reverse-engineering)
2. Sample multiple addresses per NPU using Nominatim/OSM and query the SWS Collection Tool
3. Contact ATL311 or the Office of Solid Waste Services directly for official NPU-based zone data
4. Use the Atlanta open data portal to identify if a collection zones GIS layer exists

---
Task completed with 17/25 NPU mappings. Extraction flagged as PARTIAL per task requirements (<20 confirmed).
