# GIS Data Status for Trash Pickup Zones

## Overview
This document tracks the status of downloadable GIS data (shapefiles, GeoJSON) for trash pickup zones in pilot cities.

## Data Availability

### ❌ No GIS Data Downloaded Yet

As of the research date (January 2025), **no GIS shapefiles or zone data have been downloaded** because:

1. **Access Restrictions**: Most data requires registration or direct requests
2. **Data Not Public**: Some cities don't publish zone boundaries publicly
3. **Manual Contact Required**: Need to contact cities/providers directly

## Potential GIS Data Sources

### San Diego
**Source**: SanGIS Regional Data Warehouse
- **URL**: https://rdw.sandag.org/
- **Status**: Requires free registration
- **Format**: Compressed shapefiles (.shp)
- **Layers**: 419+ layers available
- **Action Required**:
  - [ ] Register for SanGIS access
  - [ ] Browse for waste collection zone layers
  - [ ] Download if available

**Alternative**: City of San Diego Environmental Services
- **Contact**: trash@sandiego.gov or (858) 694-7000
- **Action**: Email/call to request collection zone shapefile

### El Centro
**Source**: City of El Centro (interactive map exists)
- **Map**: https://www.cityofelcentro.org/1316/Street-Sweeping
- **Contact**: Environmental Compliance (760-337-4538)
- **Action Required**:
  - [ ] Contact city to request underlying zone shapefile
  - [ ] Investigate if map has queryable API
  - [ ] May need to reverse-engineer from map queries

### Imperial County Cities (Brawley, Calexico, Holtville, Imperial)
**Source**: Imperial County GIS Data Portal
- **URL**: https://gis-imperialcounty.opendata.arcgis.com/datasets
- **Status**: Portal exists, content unknown
- **Action Required**:
  - [ ] Browse portal for municipal service zones
  - [ ] Contact county planning GIS (442-265-1736)

**Alternative**: Contact each service provider
- CR&R (El Centro, Holtville): (877) 482-5656
- Republic Services (Brawley, Calexico, Imperial): (877) 732-9253

## Expected Data Format

When GIS data becomes available, it should be saved in this directory with naming convention:

```
data/
  pickup_zones_el_centro.geojson
  pickup_zones_brawley.geojson
  pickup_zones_imperial.geojson (not needed - uniform schedule)
  pickup_zones_calexico.geojson
  pickup_zones_holtville.geojson
  pickup_zones_san_diego.geojson
```

### Expected Fields

Each zone dataset should include:
- **geometry**: Polygon or MultiPolygon
- **zone_id**: Unique identifier for the zone
- **trash_day**: Day of week for trash collection
- **recycling_day**: Day of week for recycling (if different)
- **green_waste_day**: Day of week for green waste (if different)
- **route_number**: Optional route identifier

Example GeoJSON structure:
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[...]]
      },
      "properties": {
        "zone_id": "MON-1",
        "trash_day": "Monday",
        "recycling_day": "Monday",
        "green_waste_day": "Monday",
        "route_number": "R-101"
      }
    }
  ]
}
```

## Alternative Approaches (If GIS Data Unavailable)

### 1. Address Lookup Database
Use interactive lookup tools to build address-to-zone mapping:
- Query each address in our dataset
- Store results in CSV/database
- Format: `address, city, zone, trash_day, recycling_day`

### 2. Manual Zone Digitization
If only zone maps (not shapefiles) are available:
- Import map images into GIS software (QGIS)
- Manually trace zone boundaries
- Export as shapefile/GeoJSON

### 3. Rule-Based Logic
If zones follow simple geographic rules:
- Document rules (e.g., "North of Main St = Monday")
- Implement as code logic
- No GIS file needed

## Next Steps

**Priority Order**:
1. ✅ Imperial - No GIS needed (uniform schedule)
2. 🔴 San Diego - Register for SanGIS, browse data warehouse
3. 🔴 El Centro - Contact city for zone shapefile
4. 🟡 Brawley, Calexico, Holtville - Contact providers for zone data

## Status Updates

Add updates here as data becomes available:

```
YYYY-MM-DD: [City] - [Status update]
```

Example:
```
2025-01-20: San Diego - Registered for SanGIS, found collection zones layer
2025-01-21: San Diego - Downloaded pickup_zones_san_diego.geojson
2025-01-22: El Centro - City provided zone shapefile
```
