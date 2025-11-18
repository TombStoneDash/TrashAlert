# TrashAlert Mobile API Documentation

## Overview

The TrashAlert Mobile API provides simplified, bandwidth-optimized endpoints for mobile applications. These endpoints feature:

- **API Key Authentication** - Secure access control
- **Per-API-Key Rate Limiting** - Default 30 req/min, 500 req/hour
- **Simplified Payloads** - Minimal JSON to reduce bandwidth
- **Abbreviated Data** - Day names as MON-SUN instead of MONDAY-SUNDAY
- **Usage Tracking** - Detailed analytics per API key

## Table of Contents

1. [Authentication](#authentication)
2. [Rate Limiting](#rate-limiting)
3. [Endpoints](#endpoints)
   - [GET /mobile/lookup](#get-mobilelookup)
   - [POST /mobile/report](#post-mobilereport)
4. [API Key Management](#api-key-management)
5. [Error Handling](#error-handling)
6. [Examples](#examples)

---

## Authentication

All mobile endpoints require API key authentication via the `X-API-Key` header.

### Request Header

```http
X-API-Key: ta_abc123def456ghi789...
```

### Getting an API Key

API keys are created using the management CLI:

```bash
python scripts/manage_api_keys.py create \
  --name "iOS App v1.0" \
  --description "Production iOS application"
```

**⚠️ IMPORTANT:** The full API key is only shown once during creation. Save it securely!

### Authentication Errors

| Status | Description |
|--------|-------------|
| `401 Unauthorized` | Missing or invalid API key |
| `401 Unauthorized` | API key expired or revoked |

---

## Rate Limiting

Mobile endpoints use stricter rate limits than web endpoints.

### Default Limits (per API key)

- **Per Minute:** 30 requests
- **Per Hour:** 500 requests

### Rate Limit Headers (on 429 response)

```http
X-RateLimit-Limit-Minute: 30
X-RateLimit-Limit-Hour: 500
X-RateLimit-Remaining-Minute: 0
X-RateLimit-Remaining-Hour: 245
```

### Customizing Rate Limits

When creating an API key, you can specify custom limits:

```bash
python scripts/manage_api_keys.py create \
  --name "Premium App" \
  --rpm 60 \
  --rph 2000
```

### Rate Limit Response (429)

```json
{
  "detail": "Rate limit exceeded: 30 requests per minute"
}
```

---

## Endpoints

### GET /mobile/lookup

Look up trash pickup schedule by address or coordinates.

#### Request

**Query Parameters** (provide one of):

- `address` (string) - Full address string
- `lat` (float) + `lon` (float) - Coordinates

**Headers:**
- `X-API-Key` (required) - Your API key

#### Response (200 OK)

```json
{
  "address": "123 MAIN ST, SAN DIEGO, CA",
  "city": "San Diego",
  "trash": "TUE",
  "recycling": "FRI",
  "green": null,
  "source": "verified",
  "lat": 32.7157,
  "lon": -117.1611
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `address` | string | Normalized address |
| `city` | string\|null | City name |
| `trash` | string\|null | Trash pickup day (MON-SUN) |
| `recycling` | string\|null | Recycling day (MON-SUN) |
| `green` | string\|null | Green waste day (MON-SUN) |
| `source` | string | Data quality: `verified`, `official`, `unverified`, `unknown` |
| `lat` | float\|null | Latitude |
| `lon` | float\|null | Longitude |

#### Data Source Priority

1. **verified** - Crowdsourced data with ≥3 reports and ≥67% agreement
2. **official** - Municipal/official data
3. **unverified** - Crowdsourced data below verification threshold
4. **unknown** - No data available

#### Example Requests

**Address Lookup:**
```bash
curl -X GET "https://api.trashalert.com/mobile/lookup?address=123%20Main%20St%2C%20San%20Diego" \
  -H "X-API-Key: ta_your_key_here"
```

**Coordinate Lookup:**
```bash
curl -X GET "https://api.trashalert.com/mobile/lookup?lat=32.7157&lon=-117.1611" \
  -H "X-API-Key: ta_your_key_here"
```

#### Error Responses

| Status | Description |
|--------|-------------|
| `400 Bad Request` | Invalid coordinates |
| `401 Unauthorized` | Missing/invalid API key |
| `404 Not Found` | Address not found |
| `422 Unprocessable Entity` | Missing required parameters |
| `429 Too Many Requests` | Rate limit exceeded |

---

### POST /mobile/report

Submit a crowdsourced pickup schedule report.

#### Request

**Headers:**
- `X-API-Key` (required) - Your API key
- `Content-Type: application/json`

**Body:**

```json
{
  "address": "123 Main St, San Diego, CA",
  "trash": "TUE",
  "recycling": "FRI",
  "green": "FRI",
  "user_id": "optional_user_hash_123"
}
```

#### Request Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `address` | string | ✓ | Full address (5-500 chars) |
| `trash` | string | * | Trash day (MON-SUN) |
| `recycling` | string | * | Recycling day (MON-SUN) |
| `green` | string | * | Green waste day (MON-SUN) |
| `user_id` | string | ✗ | Optional user identifier (max 64 chars) |

\* At least one pickup day required

#### Valid Day Values

- Abbreviated: `MON`, `TUE`, `WED`, `THU`, `FRI`, `SAT`, `SUN`
- Full names: `MONDAY`, `TUESDAY`, etc. (auto-converted to abbreviated)

#### Response (200 OK)

```json
{
  "success": true,
  "message": "Report submitted successfully",
  "address": "123 MAIN ST, SAN DIEGO, CA",
  "verified": true,
  "reports": 5
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether report was saved |
| `message` | string | Status message |
| `address` | string | Normalized address |
| `verified` | boolean | True if consensus is now verified (≥3 reports, ≥67% agreement) |
| `reports` | int\|null | Number of reports if verified, null otherwise |

#### Example Request

```bash
curl -X POST "https://api.trashalert.com/mobile/report" \
  -H "X-API-Key: ta_your_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "address": "123 Main St, San Diego, CA",
    "trash": "TUE",
    "recycling": "FRI"
  }'
```

#### Error Responses

| Status | Description |
|--------|-------------|
| `401 Unauthorized` | Missing/invalid API key |
| `422 Unprocessable Entity` | Invalid day value or missing required fields |
| `429 Too Many Requests` | Rate limit exceeded |

---

## API Key Management

### Create a New Key

```bash
python scripts/manage_api_keys.py create \
  --name "iOS App v1.0" \
  --description "Production iOS application" \
  --rpm 30 \
  --rph 500 \
  --expires-days 365
```

**Output:**
```
================================================================================
API KEY CREATED SUCCESSFULLY
================================================================================

API Key: ta_abc123def456ghi789jkl012mno345pqr678stu901

⚠️  IMPORTANT: Save this key now! It won't be shown again.
================================================================================

Key Details:
  ID: 1
  Prefix: ta_abc123de
  Name: iOS App v1.0
  Description: Production iOS application
  Scopes: mobile:lookup, mobile:report
  Rate Limits: 30/min, 500/hour
  Expires: 2026-01-15 10:30:00 UTC
  Created: 2025-01-15 10:30:00 UTC
================================================================================
```

### List All Keys

```bash
python scripts/manage_api_keys.py list
```

### View Key Statistics

```bash
python scripts/manage_api_keys.py stats --prefix ta_abc123de
```

**Output:**
```
================================================================================
API KEY STATISTICS: iOS App v1.0
================================================================================

Key Details:
  ID: 1
  Prefix: ta_abc123de
  Active: Yes
  Total Requests: 1,234
  Last Used: 2025-01-15 14:30:00 UTC
  Created: 2025-01-15 10:30:00 UTC

Recent Usage (last 10 requests):
  Endpoint              Method   Status   Time (ms)    Timestamp
  ---------------------------------------------------------------------------
  /mobile/lookup        GET      200      45.23        2025-01-15 14:30:00
  /mobile/report        POST     200      89.12        2025-01-15 14:28:33
  ...

Endpoint Breakdown:
  Endpoint              Requests     Avg Time (ms)
  --------------------------------------------------
  /mobile/lookup        850          52.34
  /mobile/report        384          95.67
================================================================================
```

### Revoke a Key

```bash
python scripts/manage_api_keys.py revoke --prefix ta_abc123de
```

### Reactivate a Key

```bash
python scripts/manage_api_keys.py activate --prefix ta_abc123de
```

---

## Error Handling

### Error Response Format

All errors return JSON with standard format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common Status Codes

| Code | Name | Description |
|------|------|-------------|
| 200 | OK | Request successful |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Authentication failed |
| 404 | Not Found | Resource not found |
| 422 | Unprocessable Entity | Validation failed |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error (rare) |

---

## Examples

### iOS (Swift)

```swift
import Foundation

class TrashAlertAPI {
    private let baseURL = "https://api.trashalert.com"
    private let apiKey = "ta_your_key_here"

    func lookup(address: String, completion: @escaping (Result<LookupResponse, Error>) -> Void) {
        guard let encodedAddress = address.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) else {
            completion(.failure(NSError(domain: "Invalid address", code: 400)))
            return
        }

        let urlString = "\(baseURL)/mobile/lookup?address=\(encodedAddress)"
        guard let url = URL(string: urlString) else {
            completion(.failure(NSError(domain: "Invalid URL", code: 400)))
            return
        }

        var request = URLRequest(url: url)
        request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }

            guard let data = data else {
                completion(.failure(NSError(domain: "No data", code: 500)))
                return
            }

            do {
                let decoder = JSONDecoder()
                let result = try decoder.decode(LookupResponse.self, from: data)
                completion(.success(result))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }

    func report(address: String, trash: String?, completion: @escaping (Result<ReportResponse, Error>) -> Void) {
        let urlString = "\(baseURL)/mobile/report"
        guard let url = URL(string: urlString) else {
            completion(.failure(NSError(domain: "Invalid URL", code: 400)))
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "address": address,
            "trash": trash ?? NSNull()
        ]

        request.httpBody = try? JSONSerialization.data(withJSONObject: body)

        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion(.failure(error))
                return
            }

            guard let data = data else {
                completion(.failure(NSError(domain: "No data", code: 500)))
                return
            }

            do {
                let decoder = JSONDecoder()
                let result = try decoder.decode(ReportResponse.self, from: data)
                completion(.success(result))
            } catch {
                completion(.failure(error))
            }
        }.resume()
    }
}

struct LookupResponse: Codable {
    let address: String
    let city: String?
    let trash: String?
    let recycling: String?
    let green: String?
    let source: String
    let lat: Double?
    let lon: Double?
}

struct ReportResponse: Codable {
    let success: Bool
    let message: String
    let address: String
    let verified: Bool
    let reports: Int?
}
```

### Android (Kotlin)

```kotlin
import okhttp3.*
import kotlinx.serialization.*
import kotlinx.serialization.json.*
import java.io.IOException

class TrashAlertAPI(private val apiKey: String) {
    private val baseUrl = "https://api.trashalert.com"
    private val client = OkHttpClient()
    private val json = Json { ignoreUnknownKeys = true }

    fun lookup(address: String, callback: (LookupResponse?) -> Unit) {
        val url = "$baseUrl/mobile/lookup?address=${address.urlEncode()}"

        val request = Request.Builder()
            .url(url)
            .addHeader("X-API-Key", apiKey)
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                callback(null)
            }

            override fun onResponse(call: Call, response: Response) {
                response.body?.string()?.let { body ->
                    val result = json.decodeFromString<LookupResponse>(body)
                    callback(result)
                }
            }
        })
    }

    fun report(address: String, trash: String?, callback: (ReportResponse?) -> Unit) {
        val url = "$baseUrl/mobile/report"

        val requestBody = buildJsonObject {
            put("address", address)
            trash?.let { put("trash", it) }
        }.toString()

        val body = requestBody.toRequestBody("application/json".toMediaType())

        val request = Request.Builder()
            .url(url)
            .post(body)
            .addHeader("X-API-Key", apiKey)
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                callback(null)
            }

            override fun onResponse(call: Call, response: Response) {
                response.body?.string()?.let { responseBody ->
                    val result = json.decodeFromString<ReportResponse>(responseBody)
                    callback(result)
                }
            }
        })
    }
}

@Serializable
data class LookupResponse(
    val address: String,
    val city: String?,
    val trash: String?,
    val recycling: String?,
    val green: String?,
    val source: String,
    val lat: Double?,
    val lon: Double?
)

@Serializable
data class ReportResponse(
    val success: Boolean,
    val message: String,
    val address: String,
    val verified: Boolean,
    val reports: Int?
)
```

---

## Best Practices

### 1. Cache Responses

Cache lookup results locally to reduce API calls:

```swift
// Cache for 24 hours
let cacheExpirationInterval: TimeInterval = 24 * 60 * 60
```

### 2. Handle Rate Limits Gracefully

Implement exponential backoff for 429 responses:

```swift
func retryWithBackoff(attempt: Int, maxAttempts: Int = 3) {
    if attempt >= maxAttempts { return }

    let delay = pow(2.0, Double(attempt)) // 1s, 2s, 4s
    DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
        // Retry request
    }
}
```

### 3. Use Coordinates When Available

GPS coordinates are more accurate than addresses:

```swift
if let location = locationManager.location {
    api.lookup(lat: location.coordinate.latitude,
               lon: location.coordinate.longitude)
}
```

### 4. Batch User Reports

Don't submit reports on every user action. Batch them:

```swift
// Submit only when user explicitly confirms
func confirmAndSubmit() {
    guard userHasReviewed else { return }
    api.report(address: address, trash: selectedDay)
}
```

---

## Support

For issues or questions:
- GitHub Issues: https://github.com/TombStoneDash/TrashAlert/issues
- Email: support@trashalert.com

---

**Last Updated:** 2025-01-15
**API Version:** 1.0.0
