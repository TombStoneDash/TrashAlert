# TrashAlert Data Sources Research

**Last updated:** 2026-04-15
**Goal:** Identify open data endpoints for US cities with 200K+ population

## Cities with Confirmed ArcGIS / Open Data Endpoints

| City | Endpoint Type | Records | Day Field | Import Script |
|------|--------------|---------|-----------|---------------|
| Seattle, WA | ArcGIS FeatureServer | 205 garbage + 287 recycling zones | PCKUP_DAY | `import-seattle.mjs` |
| Charlotte, NC | ArcGIS FeatureServer | 848 zones (GARB/RECY/YARD) | WORK_DAY | `import-charlotte.mjs` |
| Columbus, OH | ArcGIS MapServer | 15,678 refuse + 13,301 recycling | UNIT_NAME (color+day) | `import-columbus.mjs` |
| Jacksonville, FL | ArcGIS FeatureServer | 97 zones | GarbDay/RecyDay | `import-jacksonville.mjs` |
| Indianapolis, IN | ArcGIS MapServer | 485 zones | DAY/RC_DAY | `import-indianapolis.mjs` |
| Louisville, KY | ArcGIS FeatureServer | ~50-100 zones | SRA_DAY | `import-louisville.mjs` |
| Baltimore, MD | ArcGIS FeatureServer | 1,940 street segments (with address ranges) | TRASH_DAY/RECYCL_DAY | `import-baltimore.mjs` |
| Milwaukee, WI | ArcGIS MapServer | 442 route polygons (day-specific layers 3-7) | Layer = day | `import-milwaukee.mjs` |
| Kansas City, MO | ArcGIS MapServer | 303 zones | TRASHDAY | `import-kansas-city.mjs` |
| Detroit, MI | ArcGIS FeatureServer | 15 zones | day/week/contractor | `import-detroit.mjs` |
| Miami-Dade, FL | ArcGIS FeatureServer | 783 garbage routes + recycling zones | COLLDAY/WEEKDAYS | `import-miami.mjs` |
| Albuquerque, NM | ArcGIS MapServer | 9 zones | Pickup_Day | `import-albuquerque.mjs` |
| Tucson, AZ | ArcGIS MapServer | 238 brush/bulky + 131 recycling | ServiceDates/DOS | `import-tucson.mjs` |
| LA County (unincorporated) | ArcGIS FeatureServer | 239 zones | PICKUP_DAY | `import-la-county.mjs` |

## Endpoint Details

### Seattle, WA
- **Garbage:** `https://services.arcgis.com/ZOyb2t4B0UYuYNYH/ArcGIS/rest/services/Residential_Garbage_Routes/FeatureServer/0`
- **Recycling:** `https://services.arcgis.com/ZOyb2t4B0UYuYNYH/ArcGIS/rest/services/Residential_Recycle_Routes/FeatureServer/0`
- **Food/Yard Waste:** `https://services.arcgis.com/ZOyb2t4B0UYuYNYH/ArcGIS/rest/services/Residential_Food_and_Yard_Waste_Routes/FeatureServer/3`
- Fields: ZONE, CONTRACTOR (Recology/WM), PCKUP_DAY, ROUTE_ID, SUBZONE

### Charlotte, NC
- **All routes:** `https://services.arcgis.com/9Nl857LBlQVyzq54/arcgis/rest/services/Solid_Waste_Collection/FeatureServer/0`
- Fields: ROUTE_TYPE (GARB/RECY/YARD), WORK_DAY, SERVED_BY, ROUTE_NAME, UNIT_COUNT

### Columbus, OH
- **Refuse:** `https://maps2.columbus.gov/arcgis/rest/services/Schemas/PublicService/MapServer/11`
- **Recycling:** `https://maps2.columbus.gov/arcgis/rest/services/Schemas/PublicService/MapServer/12`
- Fields: UNIT_NAME (e.g. "Gold Tuesday"), OBJECTID

### Jacksonville, FL
- **Solid Waste:** `https://services1.arcgis.com/NXfNVaFp7QMxnE3j/arcgis/rest/services/All_WP_Changes_2022/FeatureServer/23`
- Fields: COMPANY (CITY/WP/MW), DISTRICT, GarbDay, RecyDay, YardDay, BulkDay

### Indianapolis, IN
- **Collection Areas:** `https://gis.indy.gov/server/rest/services/InforPS/InforPS/MapServer/29`
- Fields: HAULER, ROUTE_NO, DISTRICT, DAY, HVYTRASHDA, RC_HAULER, RC_DAY

### Louisville, KY
- **Garbage Routes:** `https://services1.arcgis.com/79kfd2K6fskCAkyg/ArcGIS/rest/services/OpenDataJeflib/FeatureServer/21`
- Fields: SRA_GARB, SRA_DAY, SRA_ROUTE

### Baltimore, MD
- **Trash (street segments):** `https://services3.arcgis.com/bpeS3swje8g57sok/arcgis/rest/services/Trash/FeatureServer/0`
- **Recycling Zones:** `https://services3.arcgis.com/bpeS3swje8g57sok/arcgis/rest/services/Trash/FeatureServer/1`
- Fields: TRASH_RT, TRASH_DAY, RECYCL_DAY, BIN_COLOR, STR_NAME, STR_TYPE, PREFIX_DIR, LEFT_FROM/TO, RIGHT_FROM/TO

### Milwaukee, WI
- **DPW Sanitation:** `https://milwaukeemaps.milwaukee.gov/arcgis/rest/services/DPW/DPW_Sanitation/MapServer`
- Day layers: 3=Monday, 4=Tuesday, 5=Wednesday, 6=Thursday, 7=Friday
- Summer routes (layer 9): 442 records, Winter routes (layer 21)

### Kansas City, MO
- **Trash Day Zones:** `https://mapd.kcmo.org/kcgis/rest/services/PublicWorks/TrashDay/MapServer/0`
- Fields: TRASHDAY (string day of week), 303 zones

### Detroit, MI
- **DPW Trash:** `https://services2.arcgis.com/qvkbeam7Wirps6zC/arcgis/rest/services/dpw_trash/FeatureServer/0`
- Fields: day, week (A/B), contractor (Advance/GFL), services

### Miami-Dade, FL
- **Garbage Routes:** `https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/GarbagePickupRoute_gdb/FeatureServer/0`
- **Recycling Zones:** `https://services.arcgis.com/8Pc9XBTAsYuxx9Ny/arcgis/rest/services/RecyclingZone_gdb/FeatureServer/0`
- Fields: ROUTE, COLLDAY, WEEKDAYS, WCSAREA, TYPE

### Albuquerque, NM
- **Solid Waste:** `https://abqgis01.cabq.gov/arcgis/rest/services/ABQData/SolidWaste/MapServer/0`
- Fields: Pickup_Day (Monday-Friday), 9 zones
- Portal: `https://data.cabq.gov/government/solidwaste/trashroutes/`

### Tucson, AZ
- **Brush & Bulky:** `https://utility.arcgis.com/usrsvcs/servers/c12b866163a04387ad7dcd4ebc6c4926/rest/services/PublicMaps/EnvironmentalGeneralServices/MapServer/239`
- **Recycling:** `https://mapdata.tucsonaz.gov/arcgis/rest/services/IT/ZoomTucson/MapServer/56`
- Fields: BBArea, ServiceDates, CollWeek (A/B), DOS, PRIMARY_RT

### LA County (unincorporated)
- **Waste Collection Areas:** `https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services/Los_Angeles_County_Waste_Service_Collection_Areas_view/FeatureServer/0`
- Fields: AREA_NAME, WASTE_HAUL (hauler), PICKUP_DAY
- Note: Covers LA County unincorporated areas, NOT City of LA

## Cities with NO Usable Public Endpoint

| City | Reason | Alternative |
|------|--------|-------------|
| Los Angeles, CA (City) | LASAN Collection Day Finder is proprietary, no public API | Scrape `sanitation.lacity.gov` address tool |
| San Jose, CA | Private franchise haulers, no public GIS | Scrape city utility lookup |
| Nashville, TN | New route system (Feb 2026) not exposed publicly | Scrape `nashville.gov` lookup |
| Memphis, TN | Only 311 service requests, no routes | Contact `sarah.harris@memphistn.gov` |
| Las Vegas, NV | Republic Services contracted, no city data | Scrape `republicservices.com/schedule` |
| Sacramento, CA | Only county-level refuse districts (9 hauler zones) | Scrape city calendar lookup |
| Atlanta, GA | No waste layers in GIS portal | Scrape SWS collection tool |

## Oklahoma City, OK (Special Case)
- **Portal:** `https://data.okc.gov/portal/page/viewer?datasetName=Trash+Zones`
- **API:** `https://data.okc.gov/services/portal/api/data?datasetName=Trash+Zones`
- **GIS:** `https://gis.okc.gov/arcgis/rest/services/Public/Data_OKC_Gov_Application_Service/MapServer`
- **Problem:** Both endpoints behind Incapsula WAF — blocks server requests, requires browser
- **Solution:** Browser-based scraping or user-agent spoofing needed
