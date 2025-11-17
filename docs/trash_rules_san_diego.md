# San Diego Trash Pickup Rules

## Service Provider
**City of San Diego Environmental Services Department (ESD)**
- Customer Service: (858) 694-7000
- Email: trash@sandiego.gov
- Website: https://www.sandiego.gov/environmental-services
- Serves approximately 225,000 residential customers

## Official Sources
- Environmental Services Collection: https://www.sandiego.gov/environmental-services/collection
- Collection Schedules: https://www.sandiego.gov/environmental-services/collection/schedule
- Get It Done Collection Lookup: https://getitdone.sandiego.gov/CollectionMapLookup
- Residential Waste Portal: https://wasteportal.sandiego.gov/

## Pickup Zone System

### Zone Lookup Tool
San Diego provides an **interactive zone map and address lookup tool**:
- **URL**: https://getitdone.sandiego.gov/CollectionMapLookup
- **Features**:
  - Zone map visualization
  - Address search bar
  - Returns specific collection schedule by address
  - Shows trash, recycling, and organic waste pickup days

### How Zones Are Defined
- **Geographic Zones**: City divided into zones by collection routes
- **Zone-to-Day Mapping**: Each zone assigned specific day of week (Monday-Friday)
- **Lookup Required**: Must use online tool or call to find specific zone/day
- **No Public Zone Boundaries**: GIS data for zone polygons not publicly available (as of research date)

## Collection Schedule

### Service Details
- **Trash (Black Bin)**: Weekly collection
- **Organic Waste (Green Bin)**: Weekly collection
- **Recycling (Blue Bin)**: Bi-weekly (every other week) collection
- **Collection Days**: Monday through Friday
- **Collection Hours**: 6:00 AM to 5:30 PM
- **Placement Time**: Bins must be at curb by 6:00 AM on collection day

### 2025 Holiday Schedule
No collection on the following city-observed holidays:
- Wednesday, January 1, 2025 – New Year's Day
- Monday, May 26, 2025 – Memorial Day
- Friday, July 4, 2025 – Independence Day
- Monday, September 1, 2025 – Labor Day
- Thursday, November 27, 2025 – Thanksgiving Day
- Thursday, December 25, 2025 – Christmas Day

**Holiday Delay Policy**: When a holiday occurs, collection is delayed by one day for the rest of that week.

## GIS Data Availability

### Status
**Used Internally, Public Access Uncertain**

### Known GIS Infrastructure
- City of San Diego uses GIS to manage waste collection routes for refuse, recycling, and green waste
- Route optimization and management done via GIS systems
- Interactive map tool (Get It Done) suggests underlying GIS data exists

### Potential Sources
1. **SanGIS Regional Data Warehouse**
   - URL: https://www.sangis.org/download/
   - URL: https://rdw.sandag.org/
   - Contains 419+ layers from City, County, State, and Federal sources
   - Free access after registration and accepting data disclaimer
   - Data format: Compressed shapefiles (.shp)
   - **Status**: Unclear if waste collection zones are included in public warehouse

2. **SANDAG/SanGIS Open Data Portal**
   - URL: https://sdgis-sandag.opendata.arcgis.com/
   - Popular layers published as GIS web services
   - **Status**: Street sweeping schedule available, trash zones not confirmed

3. **City of San Diego Open Data Portal**
   - URL: https://data.sandiego.gov/
   - Various city datasets available
   - **Status**: Street sweeping dataset exists, trash collection zones not found

### Recommended Actions
1. **Register for SanGIS Access**: Create account at Regional Data Warehouse to browse all available layers
2. **Contact GIS Team**: Email GISTeam@sandag.org to inquire about waste collection zone data
3. **Contact Environmental Services**:
   - Call (858) 694-7000
   - Email trash@sandiego.gov
   - Request GIS shapefile for collection zones/routes
4. **Submit Public Records Request**: If data exists but not published, may need formal request
5. **Reverse Engineer from Lookup Tool**: As fallback, could query lookup tool with sample addresses to build zone map

### Expected Data Structure
If obtainable, the dataset would likely include:
- **Geometry Type**: Polygon (collection zones) or LineString (routes)
- **Key Fields**:
  - Zone/route identifier
  - Collection day of week (Monday-Friday)
  - Trash collection schedule
  - Recycling collection schedule (week A/B or specific dates)
  - Organic waste collection schedule
  - Route number
  - District or service area

## Additional Services

### Bulky Item Pickup
- Schedule through Get It Done app or call customer service
- Limits and fees may apply

### Brush Collection
- Separate from regular trash/recycling
- Schedule varies by zone

### Special Programs
- Electronic waste recycling
- Household hazardous waste collection
- Appliance collection

## Notes
- San Diego is the largest and most complex of the pilot cities
- City-run service (not contracted to private company like Imperial County cities)
- Recent transition to citywide organic waste recycling program
- New Residential Waste Collection Services Portal launched for account management
- Interactive lookup tool is well-developed and actively maintained
- GIS data used internally but public shapefile access uncertain
- May need to build zone map from lookup tool queries if GIS data unavailable
