---
sidebar_position: 1
title: API Overview
slug: /api/overview
---

# TrashAlert API Overview

The TrashAlert API provides a powerful REST interface for looking up trash pickup schedules and submitting crowdsourced reports. It combines official municipal data with community observations to provide accurate, real-time schedule information.

## Base URL

```
https://api.trashalert.com/v1
```

For local development:
```
http://localhost:8000
```

## Authentication

The current version of TrashAlert API does not require authentication for public endpoints. However, we recommend including a User-Agent header to help us track API usage and improve the service.

```bash
curl -H "User-Agent: MyApp/1.0" https://api.trashalert.com/v1/lookup
```

Future versions will support optional API keys for enhanced rate limits.

## Rate Limiting

TrashAlert implements intelligent rate limiting to ensure fair access:

### Rate Limit Rules

- **Global Limit**: Max 60 requests per minute per IP address
- **Report Limit**: Max 10 report submissions per IP per 15-minute window
- **Address Report Limit**: Max 3 reports per IP per address per 15-minute window

### Rate Limit Headers

Every response includes rate limit information:

```
X-RateLimit-Limit-Minute: 60
X-RateLimit-Remaining-Minute: 45
X-RateLimit-Limit-Hour: 500
X-RateLimit-Remaining-Hour: 425
X-Response-Time: 12.34ms
```

### Rate Limit Exceeded Response

When rate limited, the API returns a 429 status code:

```json
{
  "error": "Too Many Requests",
  "message": "Rate limit exceeded. Please try again later.",
  "client_ip": "192.168.1.1"
}
```

## Response Format

All successful responses follow this structure:

```json
{
  "status": "success",
  "data": {
    // endpoint-specific data
  },
  "timestamp": "2025-11-18T10:30:00Z"
}
```

Error responses:

```json
{
  "error": "Error Type",
  "message": "Human-readable error description",
  "path": "/api/endpoint",
  "details": []
}
```

## Supported Cities

TrashAlert currently supports the following cities:

### Imperial Valley, California
- El Centro (CA_EL_CENTRO)
- Imperial (CA_IMPERIAL)
- Brawley (CA_BRAWLEY)
- Holtville (CA_HOLTVILLE)
- Calexico (CA_CALEXICO)

### San Diego County, California
- San Diego (CA_SAN_DIEGO)

New cities are regularly added. Check the `/stats` endpoint for the current list.

## Data Sources

The API intelligently combines data from multiple sources with the following priority:

### 1. CROWD_VERIFIED
- Verified crowdsourced consensus
- Requires ≥3 reports with ≥67% agreement
- Updated continuously as new reports come in

### 2. OFFICIAL
- Official municipal GIS data
- City-provided schedules
- Highest authority but may be outdated

### 3. CROWD_UNVERIFIED
- Crowdsourced data below verification threshold
- Useful but lower confidence
- Single or a few reports

### 4. UNKNOWN
- No data available for this address
- Community contributions welcome

## Endpoints Summary

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/lookup` | Look up trash schedule by address or coordinates |
| POST | `/report` | Submit crowdsourced schedule report |
| POST | `/interpret-address` | Parse freeform text to normalized address |
| GET | `/stats` | Get system statistics and coverage info |
| GET | `/` | Health check |

See the [Endpoints Documentation](/docs/api/endpoints/lookup) for detailed information.

## Request/Response Examples

### Simple Lookup

```bash
curl "https://api.trashalert.com/v1/lookup?address=1122%20Palmview%20Ave,%20El%20Centro,%20CA"
```

Response:
```json
{
  "matched_address": "1122 Palmview Ave",
  "city_name": "El Centro",
  "city_id": "CA_EL_CENTRO",
  "trash_day_of_week": "Wednesday",
  "recycling_day_of_week": "Friday",
  "green_waste_day_of_week": "Wednesday",
  "data_source": "CROWD_VERIFIED",
  "consensus_reports_count": 12,
  "consensus_agreement_ratio": 0.92
}
```

### Submit a Report

```bash
curl -X POST https://api.trashalert.com/v1/report \
  -H "Content-Type: application/json" \
  -d '{
    "address": "1122 Palmview Ave, El Centro, CA",
    "trash_day": "WED",
    "recycling_day": "FRI",
    "green_day": "WED",
    "user_hash": "user_identifier"
  }'
```

## Error Handling

The API returns standard HTTP status codes:

| Code | Meaning | Example |
|------|---------|---------|
| 200 | Success | Lookup found |
| 400 | Bad Request | Invalid parameters |
| 404 | Not Found | Address not found |
| 422 | Validation Error | Missing required field |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Server Error | Unexpected error |

See [Error Handling Guide](/docs/api/errors) for detailed error codes.

## Best Practices

### 1. Cache Results
Store lookup results locally to reduce API calls:

```javascript
// Cache for 24 hours
localStorage.setItem(`trash_schedule_${address}`, JSON.stringify(result));
localStorage.setItem(`trash_schedule_${address}_ts`, Date.now());
```

### 2. Handle Rate Limits Gracefully
Implement exponential backoff:

```python
import time
import random

max_retries = 3
for attempt in range(max_retries):
    try:
        response = requests.get(url)
        if response.status_code == 429:
            wait_time = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(wait_time)
            continue
        break
    except Exception as e:
        print(f"Attempt {attempt + 1} failed: {e}")
```

### 3. Validate Input
Always validate and normalize addresses before sending:

```javascript
// Remove extra spaces, normalize case
const cleanAddress = address.trim().replace(/\s+/g, ' ');
```

### 4. Provide User-Agent
Help us improve by identifying your application:

```bash
curl -H "User-Agent: MyTrashApp/1.0 (+https://myapp.com)" https://api.trashalert.com/v1/lookup
```

### 5. Contribute Reports
Help improve data by submitting observations:

```bash
# When you observe trash collection, submit a report
curl -X POST https://api.trashalert.com/v1/report \
  -H "Content-Type: application/json" \
  -d '{"address": "...", "trash_day": "WED"}'
```

## Changelog

### v1.0.0 (Current)
- Initial public release
- Address lookup by string and coordinates
- Crowdsourced report submission
- Address interpretation with AI
- Rate limiting
- Multi-source data fusion

### Planned Features (v1.1.0+)
- API authentication with keys
- Bulk lookup endpoint
- Schedule change notifications
- Historical data tracking
- Advanced filtering options

## Support

Need help? Check out these resources:

- **[Quick Start Guide](/docs/guides/quickstart)** - Get started in 5 minutes
- **[Code Examples](/docs/api/examples)** - Real-world usage examples
- **[FAQ](#faq)** - Common questions and answers
- **[GitHub Issues](https://github.com/TombStoneDash/TrashAlert/issues)** - Report problems

## FAQ

### How accurate is the data?

Data accuracy depends on the data source:
- **CROWD_VERIFIED**: 95%+ accuracy (community consensus)
- **OFFICIAL**: 85-90% accuracy (may be outdated)
- **CROWD_UNVERIFIED**: 60-75% accuracy (limited reports)

### Can I use this API commercially?

Yes! TrashAlert is open source (MIT License). See our [License](https://github.com/TombStoneDash/TrashAlert/blob/main/LICENSE) for details.

### How do I add my city?

See [Adding Cities](/docs/pipeline/adding-cities) for detailed instructions.

### What about privacy?

TrashAlert respects user privacy:
- No personal information required
- Optional anonymous reporting
- User data never sold or shared
- TrashAlert is committed to protecting user privacy. All reports are anonymous.

