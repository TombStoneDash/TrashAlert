---
sidebar_position: 1
title: Address Model
slug: /api/models/address
---

# Address Model

The Address model represents a physical location in the TrashAlert system.

## Schema

```typescript
interface Address {
  matched_address: string;          // Normalized full address
  city_id: string | null;           // City identifier (e.g., "CA_EL_CENTRO")
  city_name: string | null;         // Human-readable city name
  lat: number | null;               // Latitude coordinate
  lon: number | null;               // Longitude coordinate
  state: string | null;             // State abbreviation (e.g., "CA")
  zip_code: string | null;          // ZIP code
  house_number?: string;            // Street number
  street?: string;                  // Street name
}
```

## Field Descriptions

### matched_address
- **Type**: String
- **Required**: Yes
- **Description**: The normalized address string as stored in the database
- **Example**: "1122 Palmview Ave, El Centro, CA 92243"
- **Format**: Follows USPS standards

### city_id
- **Type**: String or null
- **Required**: No
- **Description**: Unique identifier for the city from configuration
- **Example**: "CA_EL_CENTRO"
- **Format**: Uppercase with underscore separator

### city_name
- **Type**: String or null
- **Required**: No
- **Description**: Full name of the city
- **Example**: "El Centro"

### lat
- **Type**: Number or null
- **Required**: No
- **Description**: Latitude coordinate (WGS84)
- **Range**: -90 to 90
- **Example**: 32.7971
- **Precision**: Up to 7 decimal places (±0.01 meter accuracy)

### lon
- **Type**: Number or null
- **Required**: No
- **Description**: Longitude coordinate (WGS84)
- **Range**: -180 to 180
- **Example**: -115.2645
- **Precision**: Up to 7 decimal places (±0.01 meter accuracy)

### state
- **Type**: String or null
- **Required**: No
- **Description**: Two-letter state abbreviation
- **Example**: "CA"
- **Format**: ISO 3166-2 standard

### zip_code
- **Type**: String or null
- **Required**: No
- **Description**: Five-digit ZIP code
- **Example**: "92243"
- **Format**: XXXXX (5 digits)

### house_number
- **Type**: String (optional)
- **Required**: No
- **Description**: Street/house number component
- **Example**: "1122"

### street
- **Type**: String (optional)
- **Required**: No
- **Description**: Street name component
- **Example**: "Palmview Ave"

## JSON Example

```json
{
  "matched_address": "1122 Palmview Ave, El Centro, CA 92243",
  "city_id": "CA_EL_CENTRO",
  "city_name": "El Centro",
  "lat": 32.7971,
  "lon": -115.2645,
  "state": "CA",
  "zip_code": "92243",
  "house_number": "1122",
  "street": "Palmview Ave"
}
```

## Normalization Rules

Addresses are automatically normalized according to these rules:

1. **Street Type Abbreviations**
   - "Street" → "St"
   - "Avenue" → "Ave"
   - "Boulevard" → "Blvd"
   - "Drive" → "Dr"
   - "Road" → "Rd"

2. **Case Normalization**
   - All uppercase for consistency
   - Example: "main street" → "MAIN ST"

3. **Directional Abbreviations**
   - "North" → "N"
   - "South" → "S"
   - "East" → "E"
   - "West" → "W"

4. **Spacing**
   - Extra spaces removed
   - Consistent single space separation

5. **Duplicates**
   - Uniquely identified by (city_id, house_number, street)
   - Duplicate addresses not stored

## Supported Cities

| City | State | city_id | Status |
|------|-------|---------|--------|
| El Centro | CA | CA_EL_CENTRO | Active |
| Imperial | CA | CA_IMPERIAL | Active |
| Brawley | CA | CA_BRAWLEY | Active |
| Holtville | CA | CA_HOLTVILLE | Active |
| Calexico | CA | CA_CALEXICO | Active |
| San Diego | CA | CA_SAN_DIEGO | Active |

## Database Schema

```sql
CREATE TABLE addresses (
  id INTEGER PRIMARY KEY,
  normalized_address VARCHAR(500) NOT NULL,
  house_number VARCHAR(20),
  street VARCHAR(200),
  city_slug VARCHAR(50) NOT NULL,
  city_name VARCHAR(100) NOT NULL,
  state VARCHAR(2),
  zip_code VARCHAR(10),
  lat FLOAT,
  lon FLOAT,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);

CREATE INDEX idx_normalized_address ON addresses(normalized_address);
CREATE INDEX idx_city_slug ON addresses(city_slug);
CREATE INDEX idx_lat_lon ON addresses(lat, lon);
```

## Validation Rules

| Field | Min | Max | Pattern |
|-------|-----|-----|---------|
| matched_address | 5 | 500 | Non-empty |
| house_number | 1 | 20 | Alphanumeric |
| street | 3 | 200 | Alphanumeric + spaces |
| city_name | 2 | 100 | Letters + spaces |
| state | 2 | 2 | [A-Z]{2} |
| zip_code | 5 | 10 | [0-9]{5} |
| lat | -90 | 90 | Decimal |
| lon | -180 | 180 | Decimal |

## Usage Examples

### Extracting Components

```javascript
const address = {
  matched_address: "1122 Palmview Ave, El Centro, CA 92243",
  house_number: "1122",
  street: "Palmview Ave",
  city_name: "El Centro",
  state: "CA",
  zip_code: "92243"
};

// Extract for display
const displayAddress = `${address.house_number} ${address.street}, ${address.city_name}, ${address.state}`;
```

### Building a Query

```python
def format_address_for_search(address):
    """Format address for database query."""
    # Normalize and create searchable string
    return f"{address.house_number} {address.street}".upper().strip()

# Usage
search_str = format_address_for_search(address)
# Results: "1122 PALMVIEW AVE"
```

### Coordinate-based Lookup

```javascript
function getAddressNearby(userLat, userLon, radius = 50) {
  // Find addresses within radius (meters)
  return fetch(
    `/lookup?lat=${userLat}&lon=${userLon}`,
    { headers: { 'Accept': 'application/json' } }
  );
}
```

### Displaying Pickup Schedules

```react
function AddressScheduleCard({ address, schedule }) {
  return (
    <div className="address-card">
      <h3>{address.matched_address}</h3>
      <p>{address.city_name}, {address.state} {address.zip_code}</p>

      <div className="schedule">
        <p>Trash: {schedule.trash_day_of_week}</p>
        <p>Recycling: {schedule.recycling_day_of_week}</p>
        <p>Green Waste: {schedule.green_waste_day_of_week}</p>
      </div>

      <p className="confidence">
        Source: {schedule.data_source}
      </p>
    </div>
  );
}
```

## Address Lookup Strategies

### 1. Exact Match
Look for exact normalized address:

```sql
SELECT * FROM addresses
WHERE normalized_address = '1122 PALMVIEW AVE'
AND city_slug = 'CA_EL_CENTRO';
```

### 2. Partial Match
Search by components:

```sql
SELECT * FROM addresses
WHERE house_number = '1122'
AND street LIKE '%PALMVIEW%'
AND city_slug = 'CA_EL_CENTRO';
```

### 3. Coordinate-based
Find nearest address:

```sql
SELECT * FROM addresses
WHERE (lat BETWEEN 32.79 AND 32.81)
AND (lon BETWEEN -115.27 AND -115.25)
ORDER BY (lat - 32.797) + (lon - (-115.265))
LIMIT 1;
```

## Best Practices

1. **Always validate addresses** before sending to API
2. **Cache address objects** to reduce API calls
3. **Use city_id** when available for faster lookups
4. **Store both normalized and original** addresses for reference
5. **Handle null coordinates** gracefully in UI

## Related Models

- [Report Model](/docs/api/models/report) - Crowdsourced observations for an address
- [Consensus Model](/docs/api/models/consensus) - Aggregated consensus from reports
- [LookupResponse](/docs/api/endpoints/lookup) - Response format for address lookups

