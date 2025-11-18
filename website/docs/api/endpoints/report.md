---
sidebar_position: 2
title: POST /report
slug: /api/endpoints/report
---

# POST /report - Submit Crowdsourced Report

Submit an observation of trash collection day at a specific address.

## Endpoint

```
POST /report
```

## Description

This endpoint allows users to contribute crowdsourced data by reporting when they observe trash, recycling, or green waste collection at an address. Multiple reports are aggregated to calculate a consensus schedule with confidence scores.

Reports are the foundation of TrashAlert's self-correcting database. Your observations help the system become more accurate over time.

## Request Schema

### Content-Type
```
application/json
```

### Body Parameters

| Parameter | Type | Required | Description | Constraints |
|-----------|------|----------|-------------|-------------|
| `address` | string | Yes | Full address string | 5-500 characters |
| `trash_day` | string | No | Trash pickup day observed | MON, TUE, WED, THU, FRI, SAT, SUN (or full names) |
| `recycling_day` | string | No | Recycling pickup day observed | Same as above |
| `green_day` | string | No | Green waste pickup day observed | Same as above |
| `user_hash` | string | No | Anonymous user identifier | Max 64 characters, stable identifier recommended |

**Note**: At least one pickup day must be provided (trash_day, recycling_day, or green_day).

### Day Format

Days can be specified in multiple formats:
- **Abbreviations**: `MON`, `TUE`, `WED`, `THU`, `FRI`, `SAT`, `SUN`
- **Full names**: `MONDAY`, `TUESDAY`, `WEDNESDAY`, `THURSDAY`, `FRIDAY`, `SATURDAY`, `SUNDAY`
- **Case insensitive**: `mon`, `Mon`, `MON` all accepted

## Request Examples

### Minimal Report

```bash
curl -X POST https://api.trashalert.com/v1/report \
  -H "Content-Type: application/json" \
  -d '{
    "address": "1122 Palmview Ave, El Centro, CA",
    "trash_day": "WED"
  }'
```

### Complete Report

```bash
curl -X POST https://api.trashalert.com/v1/report \
  -H "Content-Type: application/json" \
  -d '{
    "address": "1122 Palmview Ave, El Centro, CA",
    "trash_day": "WEDNESDAY",
    "recycling_day": "FRIDAY",
    "green_day": "WEDNESDAY",
    "user_hash": "user_identifier_hash"
  }'
```

### With User Identifier

```bash
curl -X POST https://api.trashalert.com/v1/report \
  -H "Content-Type: application/json" \
  -H "User-Agent: MyApp/1.0" \
  -d '{
    "address": "1122 Palmview Ave, El Centro, CA",
    "trash_day": "WED",
    "user_hash": "abc123def456"
  }'
```

## Response Schema

### Success Response (200 OK)

```json
{
  "success": true,
  "message": "Report submitted successfully",
  "address_id": 12345,
  "normalized_address": "1122 Palmview Ave, El Centro, CA",
  "consensus": {
    "trash_day": "Wednesday",
    "recycling_day": "Friday",
    "green_day": "Wednesday",
    "reports_count": 12,
    "trash_agreement_ratio": 0.92,
    "recycling_agreement_ratio": 0.85,
    "green_agreement_ratio": 0.88,
    "is_verified": true
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether the report was submitted successfully |
| `message` | string | Human-readable confirmation message |
| `address_id` | integer | Unique identifier for the address in the database |
| `normalized_address` | string | The normalized form of the submitted address |
| `consensus` | object | Updated consensus from all reports for this address |
| `consensus.trash_day` | string | Full day name for trash pickup |
| `consensus.recycling_day` | string | Full day name for recycling pickup |
| `consensus.green_day` | string | Full day name for green waste pickup |
| `consensus.reports_count` | integer | Total number of reports for this address |
| `consensus.trash_agreement_ratio` | number | Agreement ratio (0.0-1.0) for trash day |
| `consensus.recycling_agreement_ratio` | number | Agreement ratio for recycling day |
| `consensus.green_agreement_ratio` | number | Agreement ratio for green waste day |
| `consensus.is_verified` | boolean | Whether consensus meets verification threshold |

## Error Responses

### 400 Bad Request - Missing Required Fields

```json
{
  "error": "Bad Request",
  "message": "At least one pickup day (trash_day, recycling_day, or green_day) must be provided",
  "path": "/report"
}
```

### 400 Bad Request - Invalid Day

```json
{
  "error": "Bad Request",
  "message": "Invalid day 'XYZ'. Must be MON-SUN or MONDAY-SUNDAY",
  "path": "/report"
}
```

### 422 Validation Error - Field Validation

```json
{
  "error": "Validation Error",
  "message": "Request validation failed",
  "details": [
    {
      "field": "address",
      "message": "ensure this value has at least 5 characters",
      "type": "value_error.string.too_short"
    }
  ],
  "path": "/report"
}
```

### 429 Rate Limited

```json
{
  "error": "Too Many Requests",
  "message": "Rate limit exceeded. Max 10 reports per IP per 15 minutes.",
  "client_ip": "192.168.1.1"
}
```

Per-address limit:

```json
{
  "error": "Too Many Requests",
  "message": "Rate limit exceeded for this address. Max 3 reports per address per 15 minutes.",
  "client_ip": "192.168.1.1"
}
```

### 500 Server Error

```json
{
  "error": "Internal Server Error",
  "message": "An unexpected error occurred. Please try again later.",
  "path": "/report"
}
```

## HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Report submitted successfully |
| 400 | Bad request (missing fields, invalid day, etc.) |
| 422 | Validation error (field constraints violated) |
| 429 | Rate limit exceeded |
| 500 | Server error |

## Consensus Verification

When enough reports agree, a consensus becomes **verified**:

- **Verification Threshold**: ≥3 reports with ≥67% agreement on a pickup day
- **Verified Status**: `is_verified = true` in response
- **Data Priority**: Verified consensus takes priority over official data

Example:
```
Reports for Trash Day:
- Wednesday: 10 reports (71% agreement) ✓ VERIFIED
- Thursday: 4 reports (29%)
```

## Rate Limiting

The API enforces per-IP rate limits:

- **Global Limit**: Max 10 reports per IP per 15-minute window
- **Per-Address Limit**: Max 3 reports per IP per address per 15-minute window

Headers in response show remaining allowances:
```
X-RateLimit-Remaining-Minute: 8
```

## Examples

### JavaScript/Fetch

```javascript
async function submitReport(address, trashDay, recyclingDay = null) {
  const body = {
    address: address,
    trash_day: trashDay
  };

  if (recyclingDay) {
    body.recycling_day = recyclingDay;
  }

  // Optional: Generate stable user hash
  body.user_hash = generateUserHash();

  try {
    const response = await fetch('https://api.trashalert.com/v1/report', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'User-Agent': 'MyApp/1.0'
      },
      body: JSON.stringify(body)
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message);
    }

    const data = await response.json();
    console.log('Report submitted:', data.message);
    console.log('Consensus:', data.consensus);

    return data;
  } catch (error) {
    console.error('Report failed:', error);
    if (error.status === 429) {
      alert('Too many reports. Please try again later.');
    }
  }
}

function generateUserHash() {
  // Generate stable hash for this device
  let hash = localStorage.getItem('trashalert_user_hash');
  if (!hash) {
    hash = Math.random().toString(36).substring(7);
    localStorage.setItem('trashalert_user_hash', hash);
  }
  return hash;
}

// Usage
await submitReport('1122 Palmview Ave, El Centro, CA', 'WED', 'FRI');
```

### Python

```python
import requests
import hashlib

def submit_report(address, trash_day, recycling_day=None, green_day=None):
    """Submit a crowdsourced report."""
    url = 'https://api.trashalert.com/v1/report'

    body = {
        'address': address,
        'trash_day': trash_day
    }

    if recycling_day:
        body['recycling_day'] = recycling_day
    if green_day:
        body['green_day'] = green_day

    # Generate stable user hash
    body['user_hash'] = generate_user_hash()

    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'MyApp/1.0'
    }

    try:
        response = requests.post(url, json=body, headers=headers, timeout=10)

        if response.status_code == 429:
            print("Rate limited. Please wait before submitting more reports.")
            return None

        response.raise_for_status()
        data = response.json()

        print(f"Report submitted!")
        print(f"Consensus: {data['consensus']['trash_day']}")

        return data
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None

def generate_user_hash():
    """Generate stable user identifier."""
    # In production, use device ID or similar
    import uuid
    device_id = str(uuid.getnode())  # MAC address
    return hashlib.sha256(device_id.encode()).hexdigest()

# Usage
submit_report('1122 Palmview Ave, El Centro, CA', 'WED', recycling_day='FRI')
```

### cURL

```bash
# Simple report
curl -X POST https://api.trashalert.com/v1/report \
  -H "Content-Type: application/json" \
  -d '{
    "address": "1122 Palmview Ave, El Centro, CA",
    "trash_day": "WED"
  }'

# Complete report with all days
curl -X POST https://api.trashalert.com/v1/report \
  -H "Content-Type: application/json" \
  -H "User-Agent: MyApp/1.0" \
  -d '{
    "address": "1122 Palmview Ave, El Centro, CA",
    "trash_day": "WEDNESDAY",
    "recycling_day": "FRIDAY",
    "green_day": "WEDNESDAY",
    "user_hash": "user123"
  }' | jq .
```

## Best Practices

1. **Use Stable User Hash**: Generate and reuse a user hash to help prevent spam while maintaining privacy.

2. **Report Complete Information**: If you know all pickup days, report them all. More complete data improves consensus.

3. **Report Accurately**: Only report days you've actually observed. False reports degrade data quality.

4. **Handle Rate Limits**: Implement exponential backoff if you hit rate limits.

5. **Test Locally First**: Use local API at http://localhost:8000 for testing.

