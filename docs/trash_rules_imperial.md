# Imperial (City) Trash Pickup Rules

## Service Provider
**Republic Services**
- City staff and Republic Services staff monitor organic waste compliance

## Official Sources
- City of Imperial Trash & Recycling: https://www.cityofimperial.org/trash-recycling
- City Main Website: https://www.cityofimperial.org/

## Pickup Zone System

### Zone Definition
**UNIFORM CITYWIDE SCHEDULE** - All residential areas serviced on the same day

### Pickup Day
**Wednesday mornings** - All three carts collected together

## Collection Schedule

### Service Details
- **Trash Day**: Wednesday (citywide)
- **Recycling Day**: Wednesday (citywide)
- **Green Waste Day**: Wednesday (citywide)
- **Collection Time**: Morning hours (specific time not documented)

### Cart System
Three-cart automated system:
- **Black toter**: Regular household trash (items not suitable for recycling/green waste)
- **Blue container**: Recyclables
- **Green container**: Organic waste (food scraps and yard waste)

### Bulky Item Pickup
- **Frequency**: 3 free bulky item pickups per calendar year
- **Limit**: 4 items per pickup
- **Scheduling**: Contact Republic Services to arrange

### Holiday Schedule
- Assumed to follow standard Republic Services holiday schedule
- Contact Republic Services for specific holiday adjustments

## GIS Data Availability

### Status
**NOT NEEDED** - Single uniform collection day for entire city

### Zone Structure
Imperial does not appear to use zone-based collection. The entire city receives service on Wednesday.

This simplifies implementation:
- **Logic**: If address is in City of Imperial → trash_day = "Wednesday"
- **No zone mapping required**

### Verification Needed
While sources indicate Wednesday collection, should verify:
1. Are there any exceptions (commercial areas, specific neighborhoods)?
2. Has this changed for 2025?
3. Contact City of Imperial to confirm citywide Wednesday schedule

## Notes
- Simplest pickup structure of all pilot cities
- No zone complexity - single day for all services
- Republic Services monitors organic waste compliance along with city staff
- City emphasizes organic waste diversion (food scraps, yard waste)
- May be ideal pilot city for testing due to schedule uniformity
