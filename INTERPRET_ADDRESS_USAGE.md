# AI-Powered Address Interpretation Endpoint

## Overview

The `/interpret-address` endpoint provides intelligent address parsing and normalization using AI (OpenAI or Anthropic) with automatic geocoding fallback via Nominatim.

## Endpoint Details

- **URL**: `/interpret-address`
- **Method**: `POST`
- **Content-Type**: `application/json`

## Request Format

```json
{
  "text": "I live at 123 Main Street in San Diego, 92101",
  "use_geocoding": true
}
```

### Request Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `text` | string | Yes | - | Freeform text containing an address (3-1000 chars) |
| `use_geocoding` | boolean | No | `true` | Enable geocoding fallback for low-confidence results |

## Response Format

### Success Response (200 OK)

```json
{
  "success": true,
  "normalized_address": "123 Main Street, San Diego, CA 92101",
  "confidence": 0.95,
  "city": "San Diego",
  "city_id": "ca_san_diego",
  "state": "CA",
  "zip_code": "92101",
  "lat": 32.7157,
  "lon": -117.1611,
  "interpretation_method": "ai",
  "ai_reasoning": "Clear address with all components present",
  "geocoding_quality": null,
  "error": null
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether interpretation was successful |
| `normalized_address` | string | Standardized address format |
| `confidence` | float | Confidence score (0.0 to 1.0) |
| `city` | string | Extracted city name |
| `city_id` | string | Matched city ID from config (if supported) |
| `state` | string | State abbreviation |
| `zip_code` | string | ZIP/postal code |
| `lat` | float | Latitude (from geocoding) |
| `lon` | float | Longitude (from geocoding) |
| `interpretation_method` | string | Method used: `"ai"`, `"geocoding"`, or `"hybrid"` |
| `ai_reasoning` | string | AI's explanation of interpretation |
| `geocoding_quality` | string | Geocoding match quality: `"high"`, `"medium"`, or `"low"` |
| `error` | string | Error message if interpretation failed |

## Interpretation Methods

### 1. AI-Only (`interpretation_method: "ai"`)
- High-confidence AI interpretation (≥0.7)
- No geocoding needed
- Fast response time

### 2. Hybrid (`interpretation_method: "hybrid"`)
- AI interpretation with low confidence (<0.7)
- Geocoding used to validate and enhance results
- Confidence boosted based on geocoding quality

### 3. Geocoding-Only (`interpretation_method: "geocoding"`)
- AI interpretation failed
- Falls back to pure geocoding
- Confidence based on geocoding quality

## Example Usage

### Example 1: Complete Address

**Request:**
```bash
curl -X POST http://localhost:8000/interpret-address \
  -H "Content-Type: application/json" \
  -d '{
    "text": "123 Main Street, San Diego, CA 92101"
  }'
```

**Response:**
```json
{
  "success": true,
  "normalized_address": "123 Main Street, San Diego, CA 92101",
  "confidence": 0.95,
  "city": "San Diego",
  "city_id": "ca_san_diego",
  "interpretation_method": "ai"
}
```

### Example 2: Partial Address with Geocoding

**Request:**
```bash
curl -X POST http://localhost:8000/interpret-address \
  -H "Content-Type: application/json" \
  -d '{
    "text": "somewhere on Main Street in El Centro",
    "use_geocoding": true
  }'
```

**Response:**
```json
{
  "success": true,
  "normalized_address": "Main Street, El Centro, CA",
  "confidence": 0.65,
  "city": "El Centro",
  "city_id": "ca_el_centro",
  "lat": 32.7920,
  "lon": -115.5630,
  "interpretation_method": "hybrid",
  "geocoding_quality": "medium"
}
```

### Example 3: Conversational Input

**Request:**
```bash
curl -X POST http://localhost:8000/interpret-address \
  -H "Content-Type: application/json" \
  -d '{
    "text": "I just moved to apartment 4B at 456 Elm Ave, its in Fresno"
  }'
```

**Response:**
```json
{
  "success": true,
  "normalized_address": "456 Elm Avenue, Apartment 4B, Fresno, CA",
  "confidence": 0.85,
  "city": "Fresno",
  "city_id": "ca_fresno",
  "interpretation_method": "ai"
}
```

## Configuration

### Environment Variables

Set these environment variables to enable AI interpretation:

```bash
# Option 1: Use Anthropic Claude (recommended)
export ANTHROPIC_API_KEY="sk-ant-..."

# Option 2: Use OpenAI GPT
export OPENAI_API_KEY="sk-..."

# Optional: Set provider preference (default: "anthropic")
export AI_PROVIDER_PREFERENCE="anthropic"  # or "openai"
```

### Provider Fallback

The system automatically tries both providers:
1. Tries preferred provider first
2. Falls back to alternative if first fails
3. Falls back to geocoding if both fail

## Supported Cities

The endpoint automatically matches cities from `config/cities.yaml`:

- San Diego, CA (`ca_san_diego`)
- El Centro, CA (`ca_el_centro`)
- Calexico, CA (`ca_calexico`)
- Brawley, CA (`ca_brawley`)
- Imperial, CA (`ca_imperial`)
- Holtville, CA (`ca_holtville`)
- Fresno, CA (`ca_fresno`)
- Riverside, CA (`ca_riverside`)
- Sacramento, CA (`ca_sacramento`)
- Bakersfield, CA (`ca_bakersfield`)

Unsupported cities will still be interpreted but won't have a `city_id`.

## Error Handling

### Validation Errors (422)

```json
{
  "error": "Validation Error",
  "message": "Request validation failed",
  "details": [
    {
      "field": "text",
      "message": "Text cannot be empty or whitespace only",
      "type": "value_error"
    }
  ]
}
```

### Interpretation Failure (200 with success: false)

```json
{
  "success": false,
  "normalized_address": "",
  "confidence": 0.0,
  "interpretation_method": "ai",
  "error": "Failed to interpret address with both AI and geocoding"
}
```

## Integration with Existing Endpoints

The interpreted address can be used with other TrashAlert endpoints:

```bash
# 1. Interpret address
RESULT=$(curl -X POST http://localhost:8000/interpret-address \
  -H "Content-Type: application/json" \
  -d '{"text": "123 Main St, San Diego"}')

# 2. Extract normalized address
ADDRESS=$(echo $RESULT | jq -r '.normalized_address')

# 3. Look up trash schedule
curl "http://localhost:8000/lookup?address=$ADDRESS"
```

## Performance Considerations

- **AI calls**: 1-3 seconds (depending on provider)
- **Geocoding**: 0.5-2 seconds (Nominatim)
- **Hybrid**: 2-5 seconds (AI + geocoding)
- **Caching**: Consider caching results for frequently queried addresses

## Rate Limiting

The endpoint respects the global rate limits:
- 60 requests/minute per IP
- 1000 requests/hour per IP

## Testing

Run the test suite:

```bash
pytest tests/test_interpret_address.py -v
```

All tests use mocked AI responses for consistent, fast testing without requiring API keys.
