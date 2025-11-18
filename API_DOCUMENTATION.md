# TrashAlert API Documentation

**Version**: 1.0
**Base URL**: `https://api.trashalert.com` (production) | `http://localhost:8000` (development)
**Protocol**: HTTPS/REST
**Format**: JSON

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Rate Limiting](#rate-limiting)
4. [Endpoints](#endpoints)
   - [Lookup Schedule](#lookup-schedule)
   - [Submit Report](#submit-report)
   - [Get Statistics](#get-statistics)
   - [Health Check](#health-check)
   - [List Cities](#list-cities)
5. [Data Models](#data-models)
6. [Error Handling](#error-handling)
7. [Code Examples](#code-examples)
8. [Best Practices](#best-practices)
9. [Changelog](#changelog)

---

## Overview

The TrashAlert API provides programmatic access to trash pickup schedule data for addresses across the United States. Our API combines crowdsourced community observations with official municipal schedules to provide the most accurate and comprehensive data available.

### Key Features

- **Multi-Source Data**: Verified crowd data, official schedules, and unverified community reports
- **High Performance**: <100ms response times, 99.9% uptime SLA
- **Flexible Input**: Support for full addresses, GPS coordinates, or structured address components
- **Confidence Scoring**: Transparent data quality indicators (HIGH, MEDIUM, LOW, NONE)
- **Comprehensive Coverage**: Growing database of 500+ cities with 10,000+ verified addresses

### Use Cases

- **Consumer Apps**: Mobile/web apps for finding trash schedules
- **Property Management**: Multi-property schedule tracking
- **Real Estate Platforms**: "Know before you move" feature integration
- **Smart Home**: Alexa/Google Home integrations
- **Municipal Services**: White-label widgets for city websites

---

## Authentication

### Current (Open Beta)

During the beta period, API access is **open and free** with rate limiting applied per IP address. No API key required.

### Future (Production)

API keys will be required for production use. Three tiers:

| Tier | Rate Limit | Price | Use Case |
|------|------------|-------|----------|
| **Free** | 100 requests/month | $0 | Testing, personal projects |
| **Starter** | 1,000 requests/month | $49/month | Small apps, startups |
| **Pro** | 10,000 requests/month | $199/month | Production apps, property managers |
| **Enterprise** | Custom | Custom | White-label, bulk access, municipalities |

#### Using API Keys (Future)

```http
GET /lookup?address=123+Main+St
Authorization: Bearer YOUR_API_KEY
```

---

## Rate Limiting

### Current Limits (Beta)

Applied per IP address:

| Endpoint | Limit | Window |
|----------|-------|--------|
| `GET /lookup` | 30 requests | 1 minute |
| `POST /report` | 10 requests | 15 minutes |
| `GET /stats` | 30 requests | 1 minute |
| Other endpoints | 60 requests | 1 minute |

### Rate Limit Headers

All responses include rate limit information:

```http
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 27
X-RateLimit-Reset: 1640000000
```

### Rate Limit Exceeded Response

```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Please try again in 15 minutes.",
  "retry_after": 900
}
```

HTTP Status Code: `429 Too Many Requests`

---

## Endpoints

### Lookup Schedule

Retrieve trash pickup schedule for a specific address.

#### Endpoint

```
GET /lookup
```

#### Parameters

You can provide address information in one of three ways:

**Option 1: Full Address String**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `address` | string | Yes | Full address (e.g., "123 Main St, San Diego, CA 92101") |

**Option 2: GPS Coordinates**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `lat` | float | Yes | Latitude (-90 to 90) |
| `lon` | float | Yes | Longitude (-180 to 180) |

**Option 3: Structured Address (Most Precise)**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `street_number` | string | Yes | Street number (e.g., "123") |
| `street_name` | string | Yes | Street name (e.g., "Main St") |
| `city` | string | Yes | City name (e.g., "San Diego") |
| `state` | string | Yes | State code (e.g., "CA") |
| `zip_code` | string | No | ZIP code (e.g., "92101") |

#### Response

**Success (200 OK)**

```json
{
  "success": true,
  "address": "123 MAIN STREET, SAN DIEGO, CA",
  "coordinates": {
    "latitude": 32.7157,
    "longitude": -117.1611
  },
  "schedule": {
    "trash": {
      "days": ["MONDAY", "THURSDAY"],
      "next_pickup": "2025-11-19"
    },
    "recycling": {
      "days": ["MONDAY"],
      "next_pickup": "2025-11-18"
    },
    "green_waste": {
      "days": ["THURSDAY"],
      "next_pickup": "2025-11-21"
    }
  },
  "data_source": "CROWD_VERIFIED",
  "confidence": "HIGH",
  "metadata": {
    "total_reports": 5,
    "trash_agreement": "100%",
    "recycling_agreement": "100%",
    "green_waste_agreement": "80%",
    "last_updated": "2025-11-15T10:30:00Z",
    "verified": true
  }
}
```

**Address Not Found (404 Not Found)**

```json
{
  "success": false,
  "message": "Address not found in our database. Be the first to report!",
  "address": "999 NONEXISTENT ST, NOWHERE, CA",
  "data_source": "UNKNOWN",
  "confidence": "NONE",
  "suggestion": "You can submit schedule data via POST /report"
}
```

**Low Confidence Data (200 OK)**

```json
{
  "success": true,
  "address": "456 ELM STREET, SAN DIEGO, CA",
  "schedule": {
    "trash": {
      "days": ["TUESDAY", "FRIDAY"],
      "next_pickup": "2025-11-19"
    }
  },
  "data_source": "CROWD_UNVERIFIED",
  "confidence": "LOW",
  "metadata": {
    "total_reports": 2,
    "trash_agreement": "50%",
    "verified": false,
    "warning": "Not yet verified. Data may be inaccurate. Help verify by submitting your observation!"
  }
}
```

#### Data Source Types

| Source | Confidence | Description |
|--------|------------|-------------|
| `CROWD_VERIFIED` | HIGH | ≥3 independent reports with ≥67% agreement |
| `OFFICIAL` | MEDIUM | Official municipal or hauler-provided schedule |
| `CROWD_UNVERIFIED` | LOW | <3 reports or <67% agreement |
| `UNKNOWN` | NONE | No data available |

#### Example Requests

**Full Address**
```bash
curl "https://api.trashalert.com/lookup?address=123+Main+St,+San+Diego,+CA"
```

**GPS Coordinates**
```bash
curl "https://api.trashalert.com/lookup?lat=32.7157&lon=-117.1611"
```

**Structured Address**
```bash
curl "https://api.trashalert.com/lookup?street_number=123&street_name=Main+St&city=San+Diego&state=CA"
```

---

### Submit Report

Submit a crowdsourced trash pickup observation for an address.

#### Endpoint

```
POST /report
```

#### Request Body

```json
{
  "address": "123 Main St, San Diego, CA",
  "trash_days": ["MONDAY", "THURSDAY"],
  "recycling_days": ["MONDAY"],
  "green_waste_days": ["THURSDAY"],
  "notes": "Pickup is usually around 7am"
}
```

#### Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `address` | string | Yes | Full address string |
| `trash_days` | array[string] | No | Trash pickup days (uppercase day names) |
| `recycling_days` | array[string] | No | Recycling pickup days |
| `green_waste_days` | array[string] | No | Green waste/yard waste pickup days |
| `notes` | string | No | Additional notes (max 500 chars) |

**Valid Day Names**: `MONDAY`, `TUESDAY`, `WEDNESDAY`, `THURSDAY`, `FRIDAY`, `SATURDAY`, `SUNDAY`

**At least one service** (`trash_days`, `recycling_days`, or `green_waste_days`) must be provided.

#### Response

**Success (201 Created)**

```json
{
  "success": true,
  "message": "Thank you! Your report has been submitted.",
  "report_id": 12345,
  "address": "123 MAIN STREET, SAN DIEGO, CA",
  "consensus_updated": true,
  "new_consensus": {
    "trash": {
      "days": ["MONDAY", "THURSDAY"],
      "total_reports": 3,
      "agreement": "100%",
      "verified": true
    },
    "recycling": {
      "days": ["MONDAY"],
      "total_reports": 3,
      "agreement": "100%",
      "verified": true
    }
  },
  "status_change": "This address is now VERIFIED! Thanks for helping your community."
}
```

**Validation Error (400 Bad Request)**

```json
{
  "error": "validation_error",
  "message": "Invalid day name in trash_days",
  "details": {
    "field": "trash_days",
    "invalid_value": "Moonday",
    "valid_values": ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
  }
}
```

**Rate Limited (429 Too Many Requests)**

```json
{
  "error": "rate_limit_exceeded",
  "message": "You've submitted 10 reports in the last 15 minutes. Please wait before submitting more.",
  "retry_after": 450
}
```

**Spam Detected (403 Forbidden)**

```json
{
  "error": "spam_detected",
  "message": "Suspicious activity detected. Your report was not accepted.",
  "reason": "duplicate_reports",
  "contact": "support@trashalert.com"
}
```

#### Example Request

```bash
curl -X POST https://api.trashalert.com/report \
  -H "Content-Type: application/json" \
  -d '{
    "address": "123 Main St, San Diego, CA",
    "trash_days": ["MONDAY", "THURSDAY"],
    "recycling_days": ["MONDAY"]
  }'
```

---

### Get Statistics

Retrieve system-wide and per-city statistics.

#### Endpoint

```
GET /stats
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `city` | string | No | Filter by city name (e.g., "San Diego") |

#### Response

**System-Wide Stats (200 OK)**

```json
{
  "timestamp": "2025-11-18T12:00:00Z",
  "summary": {
    "total_addresses": 542,
    "verified_addresses": 47,
    "total_reports": 128,
    "total_cities": 10,
    "coverage_states": ["CA"]
  },
  "api_metrics": {
    "total_requests_24h": 1247,
    "avg_response_time_ms": 34,
    "cache_hit_rate": 0.68,
    "uptime_percentage": 99.95
  },
  "cities": [
    {
      "name": "San Diego",
      "state": "CA",
      "total_addresses": 250,
      "verified_addresses": 23,
      "total_reports": 67,
      "last_report": "2025-11-18T11:45:00Z",
      "coverage_percentage": 9.2
    },
    {
      "name": "El Centro",
      "state": "CA",
      "total_addresses": 50,
      "verified_addresses": 5,
      "total_reports": 12,
      "last_report": "2025-11-17T09:30:00Z",
      "coverage_percentage": 10.0
    }
  ],
  "top_contributors": [
    {
      "user_hash": "abc123...",
      "total_reports": 15,
      "verified_contributions": 8
    }
  ]
}
```

**City-Specific Stats (200 OK)**

```bash
curl "https://api.trashalert.com/stats?city=San+Diego"
```

```json
{
  "city": "San Diego",
  "state": "CA",
  "total_addresses": 250,
  "verified_addresses": 23,
  "unverified_addresses": 12,
  "total_reports": 67,
  "verification_rate": 0.092,
  "neighborhoods": [
    {
      "name": "Downtown",
      "addresses": 45,
      "verified": 8
    },
    {
      "name": "La Jolla",
      "addresses": 32,
      "verified": 5
    }
  ],
  "recent_activity": [
    {
      "date": "2025-11-18",
      "new_reports": 5,
      "new_verified": 2
    },
    {
      "date": "2025-11-17",
      "new_reports": 3,
      "new_verified": 1
    }
  ]
}
```

---

### Health Check

Check API health and status.

#### Endpoint

```
GET /health
```

#### Response

**Healthy (200 OK)**

```json
{
  "status": "healthy",
  "timestamp": "2025-11-18T12:00:00Z",
  "version": "1.0.0",
  "services": {
    "database": "connected",
    "cache": "operational",
    "external_apis": "operational"
  },
  "uptime_seconds": 2592000
}
```

**Unhealthy (503 Service Unavailable)**

```json
{
  "status": "unhealthy",
  "timestamp": "2025-11-18T12:00:00Z",
  "services": {
    "database": "disconnected",
    "cache": "operational",
    "external_apis": "operational"
  },
  "error": "Database connection failed"
}
```

---

### List Cities

Get list of all cities with available data.

#### Endpoint

```
GET /cities
```

#### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `state` | string | No | Filter by state code (e.g., "CA") |
| `min_coverage` | integer | No | Minimum verified addresses (default: 1) |

#### Response

**Success (200 OK)**

```json
{
  "total_cities": 10,
  "cities": [
    {
      "id": 1,
      "name": "San Diego",
      "state": "CA",
      "country": "US",
      "total_addresses": 250,
      "verified_addresses": 23,
      "coverage_percentage": 9.2,
      "official_data_available": true,
      "waste_providers": ["San Diego Environmental Services"]
    },
    {
      "id": 2,
      "name": "El Centro",
      "state": "CA",
      "country": "US",
      "total_addresses": 50,
      "verified_addresses": 5,
      "coverage_percentage": 10.0,
      "official_data_available": true,
      "waste_providers": ["CR&R Environmental Services"]
    }
  ]
}
```

---

## Data Models

### Schedule Object

```typescript
{
  "days": string[],           // Day names: ["MONDAY", "THURSDAY"]
  "next_pickup": string       // ISO date: "2025-11-19"
}
```

### Coordinates Object

```typescript
{
  "latitude": number,         // -90 to 90
  "longitude": number         // -180 to 180
}
```

### Metadata Object

```typescript
{
  "total_reports": number,              // Total crowd reports for this address
  "trash_agreement": string,            // Agreement percentage: "100%"
  "recycling_agreement": string,
  "green_waste_agreement": string,
  "verified": boolean,                  // TRUE if verified (≥3 reports, ≥67% agreement)
  "last_updated": string,               // ISO timestamp
  "source_name": string,                // For official data: "CR&R El Centro"
  "zone": string,                       // For zone-based schedules: "Zone 1"
  "warning": string                     // Warning message for low-confidence data
}
```

---

## Error Handling

### Error Response Format

All errors follow this structure:

```json
{
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {
    // Additional context (optional)
  }
}
```

### HTTP Status Codes

| Code | Name | Description |
|------|------|-------------|
| `200` | OK | Successful request |
| `201` | Created | Report submitted successfully |
| `400` | Bad Request | Invalid input parameters |
| `401` | Unauthorized | Missing or invalid API key (future) |
| `403` | Forbidden | Access denied (spam detection) |
| `404` | Not Found | Address not found in database |
| `429` | Too Many Requests | Rate limit exceeded |
| `500` | Internal Server Error | Server error (contact support) |
| `503` | Service Unavailable | Temporary service disruption |

### Common Error Codes

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `validation_error` | 400 | Invalid input format or values |
| `address_not_found` | 404 | Address doesn't exist in database |
| `rate_limit_exceeded` | 429 | Too many requests |
| `spam_detected` | 403 | Suspicious activity blocked |
| `invalid_api_key` | 401 | API key missing or invalid (future) |
| `service_unavailable` | 503 | Temporary outage |

---

## Code Examples

### JavaScript (Fetch API)

```javascript
// Lookup schedule
async function getSchedule(address) {
  const params = new URLSearchParams({ address });
  const response = await fetch(`https://api.trashalert.com/lookup?${params}`);

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const data = await response.json();
  return data;
}

// Submit report
async function submitReport(address, trashDays, recyclingDays) {
  const response = await fetch('https://api.trashalert.com/report', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      address,
      trash_days: trashDays,
      recycling_days: recyclingDays
    })
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.message || 'Failed to submit report');
  }

  return data;
}

// Example usage
getSchedule('123 Main St, San Diego, CA')
  .then(schedule => {
    console.log('Trash days:', schedule.schedule.trash.days);
    console.log('Next pickup:', schedule.schedule.trash.next_pickup);
    console.log('Confidence:', schedule.confidence);
  })
  .catch(error => console.error('Error:', error));
```

### Python (Requests)

```python
import requests

BASE_URL = 'https://api.trashalert.com'

def get_schedule(address=None, lat=None, lon=None):
    """Lookup trash schedule for an address."""
    params = {}
    if address:
        params['address'] = address
    elif lat and lon:
        params['lat'] = lat
        params['lon'] = lon
    else:
        raise ValueError("Must provide address or coordinates")

    response = requests.get(f'{BASE_URL}/lookup', params=params)
    response.raise_for_status()
    return response.json()

def submit_report(address, trash_days=None, recycling_days=None, green_waste_days=None):
    """Submit crowdsourced schedule observation."""
    data = {'address': address}
    if trash_days:
        data['trash_days'] = trash_days
    if recycling_days:
        data['recycling_days'] = recycling_days
    if green_waste_days:
        data['green_waste_days'] = green_waste_days

    response = requests.post(f'{BASE_URL}/report', json=data)
    response.raise_for_status()
    return response.json()

# Example usage
try:
    schedule = get_schedule(address='123 Main St, San Diego, CA')
    print(f"Trash days: {schedule['schedule']['trash']['days']}")
    print(f"Data source: {schedule['data_source']}")
    print(f"Confidence: {schedule['confidence']}")
except requests.exceptions.HTTPError as e:
    print(f"Error: {e.response.json()['message']}")
```

### cURL

```bash
# Lookup schedule
curl "https://api.trashalert.com/lookup?address=123+Main+St,+San+Diego,+CA"

# Submit report
curl -X POST https://api.trashalert.com/report \
  -H "Content-Type: application/json" \
  -d '{
    "address": "123 Main St, San Diego, CA",
    "trash_days": ["MONDAY", "THURSDAY"],
    "recycling_days": ["MONDAY"]
  }'

# Get statistics
curl "https://api.trashalert.com/stats"

# Health check
curl "https://api.trashalert.com/health"
```

### Ruby

```ruby
require 'net/http'
require 'json'
require 'uri'

class TrashAlertAPI
  BASE_URL = 'https://api.trashalert.com'

  def self.get_schedule(address:)
    uri = URI("#{BASE_URL}/lookup")
    uri.query = URI.encode_www_form(address: address)

    response = Net::HTTP.get_response(uri)
    raise "HTTP #{response.code}: #{response.message}" unless response.is_a?(Net::HTTPSuccess)

    JSON.parse(response.body)
  end

  def self.submit_report(address:, trash_days: nil, recycling_days: nil)
    uri = URI("#{BASE_URL}/report")

    data = { address: address }
    data[:trash_days] = trash_days if trash_days
    data[:recycling_days] = recycling_days if recycling_days

    response = Net::HTTP.post(uri, data.to_json, 'Content-Type' => 'application/json')
    raise "HTTP #{response.code}: #{response.message}" unless response.is_a?(Net::HTTPSuccess)

    JSON.parse(response.body)
  end
end

# Example usage
schedule = TrashAlertAPI.get_schedule(address: '123 Main St, San Diego, CA')
puts "Trash days: #{schedule['schedule']['trash']['days'].join(', ')}"
puts "Confidence: #{schedule['confidence']}"
```

---

## Best Practices

### 1. Caching

Results are cached for 5 minutes. Implement client-side caching to reduce API calls:

```javascript
const cache = new Map();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

async function getCachedSchedule(address) {
  const cacheKey = address.toLowerCase();
  const cached = cache.get(cacheKey);

  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    return cached.data;
  }

  const data = await getSchedule(address);
  cache.set(cacheKey, { data, timestamp: Date.now() });
  return data;
}
```

### 2. Error Handling

Always handle rate limits gracefully:

```javascript
async function getScheduleWithRetry(address, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await getSchedule(address);
    } catch (error) {
      if (error.status === 429) {
        const retryAfter = error.retryAfter || 60;
        await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
        continue;
      }
      throw error;
    }
  }
  throw new Error('Max retries exceeded');
}
```

### 3. Address Normalization

Normalize addresses before lookup for better cache hit rates:

```python
def normalize_address(address):
    """Normalize address for consistent lookups."""
    address = address.upper().strip()

    # Standardize abbreviations
    replacements = {
        ' ST,': ' STREET,',
        ' AVE,': ' AVENUE,',
        ' BLVD,': ' BOULEVARD,',
        ' DR,': ' DRIVE,',
        ' RD,': ' ROAD,',
    }

    for old, new in replacements.items():
        address = address.replace(old, new)

    return address
```

### 4. Confidence Handling

Display different UI based on confidence level:

```javascript
function displaySchedule(schedule) {
  const { data_source, confidence, schedule: pickupSchedule, metadata } = schedule;

  switch (confidence) {
    case 'HIGH':
      // Show with green badge: "Verified by 5 neighbors"
      return renderVerified(pickupSchedule, metadata);

    case 'MEDIUM':
      // Show with blue badge: "Official schedule"
      return renderOfficial(pickupSchedule, metadata);

    case 'LOW':
      // Show with yellow badge: "Unverified - help confirm!"
      return renderUnverified(pickupSchedule, metadata);

    case 'NONE':
      // Show empty state: "Be the first to report"
      return renderEmpty();
  }
}
```

### 5. GPS Lookup Optimization

Use GPS lookup for mobile apps, but always show the resolved address:

```javascript
async function getScheduleByLocation() {
  const position = await getCurrentPosition();
  const schedule = await getSchedule(
    lat: position.coords.latitude,
    lon: position.coords.longitude
  );

  // Always display the resolved address to user
  console.log(`Found schedule for: ${schedule.address}`);
  return schedule;
}
```

---

## Changelog

### Version 1.0 (November 2025)

**Initial Release**
- Lookup endpoint with multi-format address support
- Report submission with consensus algorithm
- Statistics endpoint
- Health check endpoint
- Cities list endpoint
- Rate limiting per IP
- Crowdsourced verification (≥3 reports, ≥67% agreement)

**Future Roadmap**

### Version 1.1 (Q1 2026)
- API key authentication
- Webhook support for schedule changes
- Bulk lookup endpoint
- Advanced filtering (by service type, confidence)
- Exception handling (holiday schedules)

### Version 1.2 (Q2 2026)
- Real-time notifications via WebSocket
- Historical data access
- Analytics endpoints
- White-label customization
- SLA guarantees for enterprise

### Version 2.0 (Q3 2026)
- GraphQL API support
- Mobile SDK (iOS/Android)
- Enhanced geospatial queries
- Machine learning schedule predictions
- International support (Canada)

---

## Support

### Documentation

- **API Docs**: https://docs.trashalert.com/api
- **Getting Started Guide**: https://docs.trashalert.com/quickstart
- **FAQ**: https://docs.trashalert.com/faq

### Contact

- **Email**: api@trashalert.com
- **Support Portal**: https://support.trashalert.com
- **Status Page**: https://status.trashalert.com
- **GitHub Issues**: https://github.com/trashalert/api-issues

### Community

- **Discord**: https://discord.gg/trashalert
- **Developer Forum**: https://forum.trashalert.com
- **Twitter**: @trashalert
- **Newsletter**: https://trashalert.com/newsletter

---

## Terms of Service

By using the TrashAlert API, you agree to:

1. **Attribution**: Display "Powered by TrashAlert" in your application
2. **Fair Use**: Respect rate limits and don't abuse the service
3. **Data Quality**: Submit accurate reports (no spam or fake data)
4. **Privacy**: Don't collect or share user PII without consent
5. **Compliance**: Follow applicable laws (GDPR, CCPA, etc.)

Full Terms: https://trashalert.com/terms
Privacy Policy: https://trashalert.com/privacy

---

**TrashAlert API v1.0 - Making trash schedules universally accessible.**

*Questions? Contact us at api@trashalert.com*
