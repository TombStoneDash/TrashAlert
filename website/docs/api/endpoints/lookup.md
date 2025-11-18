---
sidebar_position: 1
title: GET /lookup
slug: /api/endpoints/lookup
---

# GET /lookup - Address Schedule Lookup

Look up trash, recycling, and green waste pickup schedules for an address.

## Endpoint

```
GET /lookup
```

## Description

This endpoint allows you to query the TrashAlert database using multiple input formats. It returns the most current schedule information from available sources (official municipal data, crowdsourced consensus, or both).

The endpoint intelligently prioritizes data sources:
1. CROWD_VERIFIED - Verified crowdsourced consensus (highest reliability)
2. OFFICIAL - Official municipal data
3. CROWD_UNVERIFIED - Unverified crowdsourced data
4. UNKNOWN - No data available

## Query Parameters

### Option 1: Address String (Most Common)

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `address` | string | Yes | Full address string | `1122 Palmview Ave, El Centro, CA` |
| `city_id` | string | No | City identifier for more precise matching | `CA_EL_CENTRO` |

### Option 2: Coordinates

| Parameter | Type | Required | Description | Range |
|-----------|------|----------|-------------|-------|
| `lat` | number | Yes (with lon) | Latitude | -90 to 90 |
| `lon` | number | Yes (with lat) | Longitude | -180 to 180 |
| `city_id` | string | No | Restrict search to specific city | `CA_EL_CENTRO` |

**Note**: You must provide either `address` OR both `lat` and `lon`.

## Request Examples

### Lookup by Address

```bash
curl "https://api.trashalert.com/v1/lookup?address=1122%20Palmview%20Ave,%20El%20Centro,%20CA"
```

### Lookup by Coordinates

```bash
curl "https://api.trashalert.com/v1/lookup?lat=32.7971&lon=-115.2645"
```

### Lookup by Address with City Filter

```bash
curl "https://api.trashalert.com/v1/lookup?address=Main%20St&city_id=CA_EL_CENTRO"
```

## Response Schema

### Success Response (200 OK)

```json
{
  "matched_address": "1122 Palmview Ave",
  "city_id": "CA_EL_CENTRO",
  "city_name": "El Centro",
  "lat": 32.7971,
  "lon": -115.2645,
  "trash_day_of_week": "Wednesday",
  "recycling_day_of_week": "Friday",
  "green_waste_day_of_week": "Wednesday",
  "data_source": "CROWD_VERIFIED",
  "consensus_reports_count": 12,
  "consensus_agreement_ratio": 0.92,
  "consensus_details": {
    "reports_count": 12,
    "agreement_ratio": 0.92
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `matched_address` | string | The normalized address that was matched |
| `city_id` | string | City identifier from configuration |
| `city_name` | string | Human-readable city name |
| `lat` | number | Latitude of the address |
| `lon` | number | Longitude of the address |
| `trash_day_of_week` | string | Full day name for trash pickup (e.g., "Monday") |
| `recycling_day_of_week` | string | Full day name for recycling pickup |
| `green_waste_day_of_week` | string | Full day name for green waste pickup |
| `data_source` | string | Source of the data (CROWD_VERIFIED, OFFICIAL, CROWD_UNVERIFIED, UNKNOWN) |
| `consensus_reports_count` | integer | Number of reports used for crowdsourced consensus |
| `consensus_agreement_ratio` | number | Agreement ratio (0.0-1.0) for crowdsourced data |
| `consensus_details` | object | Detailed consensus metrics |

### Address Not Found (200 OK with UNKNOWN source)

```json
{
  "matched_address": "Unknown Address",
  "city_id": null,
  "city_name": null,
  "lat": null,
  "lon": null,
  "trash_day_of_week": null,
  "recycling_day_of_week": null,
  "green_waste_day_of_week": null,
  "data_source": "UNKNOWN",
  "consensus_reports_count": null,
  "consensus_agreement_ratio": null,
  "consensus_details": null
}
```

## Error Responses

### 400 Bad Request

Missing required parameters:

```json
{
  "error": "Bad Request",
  "message": "Must provide either 'address' or both 'lat' and 'lon'",
  "path": "/lookup"
}
```

### 422 Validation Error

Invalid parameter values:

```json
{
  "error": "Validation Error",
  "message": "Request validation failed",
  "details": [
    {
      "field": "lat",
      "message": "ensure this value is less than or equal to 90",
      "type": "value_error.number.not_le"
    }
  ],
  "path": "/lookup"
}
```

### 429 Rate Limited

Too many requests:

```json
{
  "error": "Too Many Requests",
  "message": "Rate limit exceeded. Max 60 requests per minute.",
  "client_ip": "192.168.1.1"
}
```

### 500 Server Error

Unexpected error:

```json
{
  "error": "Internal Server Error",
  "message": "An unexpected error occurred. Please try again later.",
  "path": "/lookup"
}
```

## HTTP Status Codes

| Code | Meaning | Scenario |
|------|---------|----------|
| 200 | OK | Lookup completed (address found or not found) |
| 400 | Bad Request | Invalid or missing required parameters |
| 422 | Validation Error | Parameter validation failed |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Server Error | Unexpected server error |

## Examples

### JavaScript/Fetch

```javascript
// Lookup by address
async function lookupAddress(address) {
  const params = new URLSearchParams({
    address: address
  });

  try {
    const response = await fetch(
      `https://api.trashalert.com/v1/lookup?${params}`,
      {
        headers: {
          'User-Agent': 'MyApp/1.0'
        }
      }
    );

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    const data = await response.json();

    if (data.data_source === 'UNKNOWN') {
      console.log('Address not found');
      return null;
    }

    console.log(`Trash day: ${data.trash_day_of_week}`);
    return data;
  } catch (error) {
    console.error('Lookup failed:', error);
  }
}

// Usage
await lookupAddress('1122 Palmview Ave, El Centro, CA');
```

### Python

```python
import requests

def lookup_address(address, city_id=None):
    """Look up trash schedule for an address."""
    url = 'https://api.trashalert.com/v1/lookup'

    params = {
        'address': address
    }
    if city_id:
        params['city_id'] = city_id

    headers = {
        'User-Agent': 'MyApp/1.0'
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()

        if data['data_source'] == 'UNKNOWN':
            print(f"Address not found: {address}")
            return None

        print(f"Trash day: {data['trash_day_of_week']}")
        print(f"Source: {data['data_source']}")

        return data
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None

# Usage
lookup_address('1122 Palmview Ave, El Centro, CA')
```

### cURL

```bash
# Basic lookup
curl "https://api.trashalert.com/v1/lookup?address=1122%20Palmview%20Ave,%20El%20Centro,%20CA" \
  -H "User-Agent: MyApp/1.0"

# Lookup with city filter
curl "https://api.trashalert.com/v1/lookup?address=Main%20St&city_id=CA_EL_CENTRO" \
  -H "User-Agent: MyApp/1.0"

# Coordinate-based lookup
curl "https://api.trashalert.com/v1/lookup?lat=32.7971&lon=-115.2645" \
  -H "User-Agent: MyApp/1.0"

# Pretty-print JSON response
curl -s "https://api.trashalert.com/v1/lookup?address=1122%20Palmview%20Ave,%20El%20Centro,%20CA" | jq .
```

## Notes

### Data Source Reliability

- **CROWD_VERIFIED**: 95%+ accuracy, continuously updated
- **OFFICIAL**: 85-90% accuracy, may be outdated
- **CROWD_UNVERIFIED**: 60-75% accuracy, limited data
- **UNKNOWN**: No data available, community contributions welcome

### Coordinate Precision

Latitude/longitude searches use a 50-meter radius. If no exact match is found, the system returns "UNKNOWN". Consider using address-based lookups for better accuracy.

### Address Normalization

The API automatically normalizes addresses:
- "Main St" vs "Main Street" → both match
- "Ave" vs "Avenue" → both match
- Case insensitive
- Extra spaces ignored

### Caching Recommendations

- Cache successful lookups for 24 hours
- Implement exponential backoff for rate limiting
- Always include a User-Agent header

