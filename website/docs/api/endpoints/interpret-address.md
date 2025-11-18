---
sidebar_position: 3
title: POST /interpret-address
slug: /api/endpoints/interpret-address
---

# POST /interpret-address - Parse Freeform Address Text

Parse and normalize a freeform address using AI with optional geocoding fallback.

## Endpoint

```
POST /interpret-address
```

## Description

This endpoint uses artificial intelligence to parse unstructured address text and extract address components. It intelligently interprets messy, informal, or incomplete address strings and returns a normalized address with confidence scoring.

The endpoint supports multiple interpretation methods:
- **AI**: Direct AI-based interpretation
- **Hybrid**: AI with geocoding fallback for low confidence results
- **Geocoding**: Fallback to Nominatim reverse geocoding

## Request Schema

### Content-Type
```
application/json
```

### Body Parameters

| Parameter | Type | Required | Description | Constraints |
|-----------|------|----------|-------------|-------------|
| `text` | string | Yes | Freeform text containing an address | 3-1000 characters |
| `use_geocoding` | boolean | No | Use geocoding fallback for low confidence results | Default: true |

## Request Examples

### Simple Address Text

```bash
curl -X POST https://api.trashalert.com/v1/interpret-address \
  -H "Content-Type: application/json" \
  -d '{
    "text": "1122 Palmview Ave, El Centro, CA"
  }'
```

### Informal Address Text

```bash
curl -X POST https://api.trashalert.com/v1/interpret-address \
  -H "Content-Type: application/json" \
  -d '{
    "text": "you know, by the old post office on main street near downtown"
  }'
```

### With Geocoding Disabled

```bash
curl -X POST https://api.trashalert.com/v1/interpret-address \
  -H "Content-Type: application/json" \
  -d '{
    "text": "somewhere in el centro",
    "use_geocoding": false
  }'
```

## Response Schema

### Success Response (200 OK)

```json
{
  "success": true,
  "normalized_address": "1122 Palmview Ave, El Centro, CA",
  "confidence": 0.95,
  "city": "El Centro",
  "city_id": "CA_EL_CENTRO",
  "state": "CA",
  "zip_code": "92243",
  "lat": 32.7971,
  "lon": -115.2645,
  "interpretation_method": "ai",
  "ai_reasoning": "Address clearly specifies house number, street, city, and state",
  "geocoding_quality": null
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether interpretation succeeded |
| `normalized_address` | string | Standardized address string |
| `confidence` | number | Confidence score (0.0 to 1.0) |
| `city` | string | Extracted city name |
| `city_id` | string | Matched city ID from configuration |
| `state` | string | State abbreviation |
| `zip_code` | string | ZIP code (if found) |
| `lat` | number | Latitude (from geocoding if enabled) |
| `lon` | number | Longitude (from geocoding if enabled) |
| `interpretation_method` | string | Method used (ai, geocoding, hybrid) |
| `ai_reasoning` | string | Explanation of AI interpretation |
| `geocoding_quality` | string | Geocoding match quality (high, medium, low) |

### Partial Match Response

```json
{
  "success": true,
  "normalized_address": "Main Street, El Centro, CA",
  "confidence": 0.65,
  "city": "El Centro",
  "city_id": "CA_EL_CENTRO",
  "state": "CA",
  "zip_code": null,
  "lat": 32.8050,
  "lon": -115.2600,
  "interpretation_method": "hybrid",
  "ai_reasoning": "Street name identified but house number missing",
  "geocoding_quality": "medium"
}
```

### Failure Response (200 OK with success=false)

```json
{
  "success": false,
  "normalized_address": "",
  "confidence": 0.0,
  "interpretation_method": "ai",
  "error": "Failed to interpret address with both AI and geocoding"
}
```

## Error Responses

### 422 Validation Error

```json
{
  "error": "Validation Error",
  "message": "Request validation failed",
  "details": [
    {
      "field": "text",
      "message": "ensure this value has at least 3 characters",
      "type": "value_error.string.too_short"
    }
  ],
  "path": "/interpret-address"
}
```

### 429 Rate Limited

```json
{
  "error": "Too Many Requests",
  "message": "Rate limit exceeded. Please try again later.",
  "client_ip": "192.168.1.1"
}
```

### 500 Server Error

```json
{
  "error": "Internal Server Error",
  "message": "An unexpected error occurred. Please try again later.",
  "path": "/interpret-address"
}
```

## HTTP Status Codes

| Code | Meaning | Notes |
|------|---------|-------|
| 200 | OK | Interpretation attempted (check success field) |
| 422 | Validation Error | Text too short or invalid |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Server Error | Unexpected error |

## Confidence Scores

The confidence score indicates how certain the interpretation is:

| Score | Reliability | Interpretation |
|-------|------------|-----------------|
| 0.9-1.0 | Very High | Precise address with all components |
| 0.75-0.9 | High | Complete address with minor variations |
| 0.6-0.75 | Medium | Partial address or some uncertainty |
| 0.4-0.6 | Low | Vague address, geocoding fallback used |
| 0.0-0.4 | Very Low | Unable to interpret reliably |

## Interpretation Methods

### AI Method
- Uses language models to parse address text
- Extracts components: number, street, city, state, ZIP
- Works with formal and informal addresses
- Fastest response time

### Geocoding Method
- Uses Nominatim reverse geocoding
- More robust for incomplete addresses
- Slower but more reliable for vague queries
- Returns coordinates

### Hybrid Method
- Starts with AI interpretation
- Uses geocoding as fallback if confidence is low
- Combines benefits of both methods
- Highest accuracy potential

## Examples

### JavaScript/Fetch

```javascript
async function interpretAddress(text, useGeocoding = true) {
  const body = {
    text: text,
    use_geocoding: useGeocoding
  };

  try {
    const response = await fetch(
      'https://api.trashalert.com/v1/interpret-address',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'User-Agent': 'MyApp/1.0'
        },
        body: JSON.stringify(body)
      }
    );

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    const data = await response.json();

    if (!data.success) {
      console.log('Failed to interpret address:', data.error);
      return null;
    }

    console.log(`Interpreted: ${data.normalized_address}`);
    console.log(`Confidence: ${(data.confidence * 100).toFixed(1)}%`);
    console.log(`Method: ${data.interpretation_method}`);

    return data;
  } catch (error) {
    console.error('Interpretation failed:', error);
  }
}

// Usage examples
await interpretAddress('1122 Palmview, El Centro');
await interpretAddress('main street in el centro');
await interpretAddress('that place near the old post office', true);
```

### Python

```python
import requests
import json

def interpret_address(text, use_geocoding=True):
    """Interpret and normalize a freeform address."""
    url = 'https://api.trashalert.com/v1/interpret-address'

    body = {
        'text': text,
        'use_geocoding': use_geocoding
    }

    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'MyApp/1.0'
    }

    try:
        response = requests.post(url, json=body, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()

        if not data['success']:
            print(f"Failed to interpret: {data['error']}")
            return None

        print(f"Interpreted: {data['normalized_address']}")
        print(f"Confidence: {data['confidence']:.1%}")
        print(f"City: {data['city']} ({data['city_id']})")
        print(f"Method: {data['interpretation_method']}")

        if data.get('ai_reasoning'):
            print(f"Reasoning: {data['ai_reasoning']}")

        return data
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None

# Usage examples
interpret_address('1122 Palmview Ave, El Centro, CA')
interpret_address('main street near the post office in el centro')
interpret_address('somewhere downtown el centro', use_geocoding=True)
```

### cURL

```bash
# Simple address text
curl -X POST https://api.trashalert.com/v1/interpret-address \
  -H "Content-Type: application/json" \
  -d '{
    "text": "1122 Palmview Ave, El Centro, CA"
  }' | jq .

# Informal address text
curl -X POST https://api.trashalert.com/v1/interpret-address \
  -H "Content-Type: application/json" \
  -d '{
    "text": "somewhere on main street in el centro"
  }' | jq .

# Without geocoding fallback
curl -X POST https://api.trashalert.com/v1/interpret-address \
  -H "Content-Type: application/json" \
  -d '{
    "text": "el centro ca",
    "use_geocoding": false
  }' | jq .
```

## Best Practices

1. **Provide Context**: More information leads to better interpretation
   ```
   Good: "1122 Palmview Ave, El Centro, California"
   Better: "my house at 1122 Palmview Ave in El Centro, California 92243"
   ```

2. **Handle Low Confidence**: Check confidence score and handle accordingly
   ```javascript
   if (data.confidence < 0.7) {
     askUserToConfirm(data.normalized_address);
   }
   ```

3. **Use Geocoding for Vague Addresses**: Enable geocoding for informal addresses
   ```javascript
   const result = await interpretAddress(userText, useGeocoding=true);
   ```

4. **Cache Results**: Store interpretations to avoid re-processing
   ```javascript
   const cache = new Map();
   if (cache.has(text)) return cache.get(text);
   ```

5. **Handle Failures Gracefully**: Not all addresses can be interpreted
   ```javascript
   if (!result.success) {
     return askUserToEnterAddressManually();
   }
   ```

## Supported Cities

The AI interpreter is trained on addresses from supported TrashAlert cities:
- El Centro, CA
- Imperial, CA
- Brawley, CA
- Holtville, CA
- Calexico, CA
- San Diego, CA

Other US addresses will still be interpreted but with lower confidence.

