---
sidebar_position: 2
title: Report Model
slug: /api/models/report
---

# Report Model

The Report model represents an individual user observation about trash collection at a specific address.

## Schema

```typescript
interface Report {
  address: string;              // Full address string to report on
  trash_day?: string;           // Observed trash pickup day
  recycling_day?: string;       // Observed recycling pickup day
  green_day?: string;           // Observed green waste pickup day
  user_hash?: string;           // Anonymous user identifier
}
```

## Request Schema (POST /report)

### address
- **Type**: String
- **Required**: Yes
- **Min Length**: 5 characters
- **Max Length**: 500 characters
- **Description**: Full address where pickup was observed
- **Example**: "1122 Palmview Ave, El Centro, CA"
- **Rules**:
  - Cannot be empty or whitespace only
  - Extra spaces will be normalized
  - Case insensitive

### trash_day
- **Type**: String
- **Required**: No (but at least one pickup day required)
- **Max Length**: 20 characters
- **Description**: Trash collection day observed
- **Valid Values**:
  - Abbreviations: `MON`, `TUE`, `WED`, `THU`, `FRI`, `SAT`, `SUN`
  - Full names: `MONDAY`, `TUESDAY`, `WEDNESDAY`, `THURSDAY`, `FRIDAY`, `SATURDAY`, `SUNDAY`
  - Case insensitive
- **Example**: "WED" or "WEDNESDAY"

### recycling_day
- **Type**: String
- **Required**: No (but at least one pickup day required)
- **Max Length**: 20 characters
- **Description**: Recycling collection day observed
- **Valid Values**: Same as trash_day
- **Example**: "FRI" or "FRIDAY"

### green_day
- **Type**: String
- **Required**: No (but at least one pickup day required)
- **Max Length**: 20 characters
- **Description**: Green waste collection day observed
- **Valid Values**: Same as trash_day
- **Example**: "THU" or "THURSDAY"

### user_hash
- **Type**: String
- **Required**: No
- **Max Length**: 64 characters
- **Description**: Stable identifier for the user (anonymous)
- **Purpose**: Rate limiting and spam prevention
- **Recommendation**: Generate once and store locally
- **Example**: "abc123def456" or SHA256 hash of device ID

## Request JSON Example

```json
{
  "address": "1122 Palmview Ave, El Centro, CA",
  "trash_day": "WEDNESDAY",
  "recycling_day": "FRIDAY",
  "green_day": "WEDNESDAY",
  "user_hash": "user_hash_abc123"
}
```

## Response Schema

### ReportResponse

```typescript
interface ReportResponse {
  success: boolean;
  message: string;
  address_id: number;
  normalized_address: string;
  consensus: ConsensusInfo;
}

interface ConsensusInfo {
  trash_day?: string;
  recycling_day?: string;
  green_day?: string;
  reports_count: number;
  trash_agreement_ratio: number;
  recycling_agreement_ratio: number;
  green_agreement_ratio: number;
  is_verified: boolean;
}
```

## Response Example

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

## Validation Rules

| Field | Rule | Error Message |
|-------|------|---------------|
| address | Min 5 chars | "Address must be at least 5 characters" |
| address | Max 500 chars | "Address must be less than 500 characters" |
| address | Not empty/whitespace | "Address cannot be empty or whitespace only" |
| trash_day | Valid day if provided | "Invalid day 'XYZ'. Must be MON-SUN or MONDAY-SUNDAY" |
| recycling_day | Valid day if provided | "Invalid day 'XYZ'. Must be MON-SUN or MONDAY-SUNDAY" |
| green_day | Valid day if provided | "Invalid day 'XYZ'. Must be MON-SUN or MONDAY-SUNDAY" |
| At least one day | Required | "At least one pickup day must be provided" |
| user_hash | Max 64 chars | "User hash must be less than 64 characters" |

## Collection Types

### Trash
Regular household garbage collection
- Most common pickup type
- Weekly or bi-weekly frequency
- Required for all reports

### Recycling
Recyclable materials (paper, plastic, metal)
- Often same day or different day than trash
- Sometimes multi-bin systems
- Frequency varies by city

### Green Waste
Yard waste, leaves, grass clippings
- Optional in some cities
- May be seasonal
- Usually weekly during growing season

## Day Format Variations

The API accepts flexible day formats:

```javascript
// All equivalent
const variations = [
  { trash_day: "MON" },
  { trash_day: "MONDAY" },
  { trash_day: "Mon" },
  { trash_day: "monday" },
  { trash_day: "   MONDAY   " }  // Extra spaces trimmed
];
```

## User Hash Generation

Generate a stable user hash for repeat users:

### JavaScript
```javascript
function generateUserHash() {
  // Option 1: Use localStorage for persistence
  let hash = localStorage.getItem('trashalert_user_hash');
  if (!hash) {
    hash = Math.random().toString(36).substring(2, 15) +
           Math.random().toString(36).substring(2, 15);
    localStorage.setItem('trashalert_user_hash', hash);
  }
  return hash;
}

// Option 2: Use browser fingerprint
async function generateFingerprintHash() {
  const data = {
    userAgent: navigator.userAgent,
    language: navigator.language,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone
  };
  const str = JSON.stringify(data);
  const buf = new TextEncoder().encode(str);
  const hashBuffer = await crypto.subtle.digest('SHA-256', buf);
  return Array.from(new Uint8Array(hashBuffer))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}
```

### Python
```python
import hashlib
import uuid

def generate_user_hash():
    """Generate stable user hash."""
    # Option 1: MAC address based
    device_id = uuid.getnode()  # MAC address
    return hashlib.sha256(str(device_id).encode()).hexdigest()

    # Option 2: Random UUID
    # return str(uuid.uuid4())

# Usage
user_hash = generate_user_hash()
```

## Database Schema

```sql
CREATE TABLE crowd_reports (
  id INTEGER PRIMARY KEY,
  address_id INTEGER NOT NULL,
  trash_day VARCHAR(20),
  recycling_day VARCHAR(20),
  green_day VARCHAR(20),
  user_hash VARCHAR(64),
  ip_address VARCHAR(45),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (address_id) REFERENCES addresses(id),
  CONSTRAINT trash_day_check CHECK (trash_day IN (
    'Monday', 'Tuesday', 'Wednesday', 'Thursday',
    'Friday', 'Saturday', 'Sunday', 'MON', 'TUE',
    'WED', 'THU', 'FRI', 'SAT', 'SUN'
  ))
);

CREATE INDEX idx_reports_address ON crowd_reports(address_id);
CREATE INDEX idx_reports_user ON crowd_reports(user_hash);
CREATE INDEX idx_reports_created ON crowd_reports(created_at);
```

## Rate Limiting

Reports are subject to rate limiting:

```
- Global: 10 reports per IP per 15 minutes
- Per-address: 3 reports per IP per address per 15 minutes
```

Example rate limit response:

```json
{
  "error": "Too Many Requests",
  "message": "Rate limit exceeded. Max 10 reports per IP per 15 minutes.",
  "client_ip": "192.168.1.1"
}
```

## Usage Examples

### Simple Report Submission

```javascript
async function submitReport(address, trashDay) {
  const response = await fetch('https://api.trashalert.com/v1/report', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      address: address,
      trash_day: trashDay,
      user_hash: generateUserHash()
    })
  });

  return await response.json();
}

// Usage
const result = await submitReport('1122 Palmview Ave, El Centro, CA', 'WED');
console.log(`Consensus: ${result.consensus.trash_day}`);
```

### Complete Report with All Days

```python
import requests

def submit_complete_report(address, trash, recycling, green):
    """Submit report with all pickup days."""
    url = 'https://api.trashalert.com/v1/report'

    payload = {
        'address': address,
        'trash_day': trash,
        'recycling_day': recycling,
        'green_day': green,
        'user_hash': generate_user_hash()
    }

    response = requests.post(url, json=payload)

    if response.status_code == 200:
        data = response.json()
        print(f"Success! Consensus: {data['consensus']}")
        return data
    elif response.status_code == 429:
        print("Rate limited. Try again later.")
    else:
        print(f"Error: {response.json()}")

# Usage
submit_complete_report(
    '1122 Palmview Ave, El Centro, CA',
    'WED', 'FRI', 'THU'
)
```

### Batch Reports

```javascript
async function submitBatchReports(reports) {
  const results = [];

  for (const report of reports) {
    try {
      const result = await submitReport(
        report.address,
        report.trash_day
      );
      results.push({ success: true, ...result });
    } catch (error) {
      results.push({ success: false, address: report.address, error });
    }

    // Rate limiting: delay between requests
    await new Promise(resolve => setTimeout(resolve, 1500));
  }

  return results;
}
```

## Best Practices

1. **Provide All Known Days**: If you know multiple pickup days, include them all
2. **Use Stable User Hash**: Generate once and reuse for rate limiting benefits
3. **Handle Rate Limits**: Implement exponential backoff for retries
4. **Validate Locally**: Check day format before submission
5. **Confirm Address**: Verify address normalization in response

## Related Models

- [Address Model](/docs/api/models/address) - The address being reported on
- [Consensus Model](/docs/api/models/consensus) - Aggregated data from multiple reports
- [POST /report Endpoint](/docs/api/endpoints/report) - How to submit reports

