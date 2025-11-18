---
sidebar_position: 5
title: Error Handling
slug: /api/errors
---

# Error Handling Guide

TrashAlert API uses standard HTTP status codes and consistent error response formats. Learn how to handle errors gracefully in your application.

## HTTP Status Codes

| Code | Meaning | Typical Cause | Retry? |
|------|---------|---------------|--------|
| 200 | OK | Success | No |
| 400 | Bad Request | Invalid parameters | No |
| 404 | Not Found | Address not found | No |
| 422 | Validation Error | Field validation failed | No |
| 429 | Too Many Requests | Rate limit exceeded | Yes (with backoff) |
| 500 | Server Error | Unexpected error | Yes (with backoff) |
| 503 | Service Unavailable | Maintenance | Yes (with backoff) |

## Error Response Format

All error responses follow this structure:

```json
{
  "error": "Error Type",
  "message": "Human-readable description",
  "path": "/api/endpoint",
  "details": []
}
```

## Common Errors

### 400 Bad Request

**Cause**: Invalid request parameters

```json
{
  "error": "Bad Request",
  "message": "Must provide either 'address' or both 'lat' and 'lon'",
  "path": "/lookup"
}
```

**How to fix**:
- Provide required parameters
- Check parameter format
- Review endpoint documentation

### 422 Validation Error

**Cause**: Field values violate constraints

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

**How to fix**:
- Check field lengths
- Validate day format (MON-SUN or MONDAY-SUNDAY)
- Ensure required fields are present
- Remove extra whitespace

### 404 Not Found (Address)

**Cause**: Address doesn't exist in database

**Note**: A 200 status is returned, but with `data_source: "UNKNOWN"`

```json
{
  "matched_address": "Unknown Address",
  "data_source": "UNKNOWN",
  "trash_day_of_week": null,
  "recycling_day_of_week": null,
  "green_waste_day_of_week": null
}
```

**How to handle**:
- Try a different address format
- Use [/interpret-address](/docs/api/endpoints/interpret-address) endpoint for help parsing
- Submit crowdsourced reports to help build data
- Ask user to verify address

### 429 Too Many Requests

**Cause**: Rate limit exceeded

```json
{
  "error": "Too Many Requests",
  "message": "Rate limit exceeded. Max 60 requests per minute.",
  "client_ip": "192.168.1.1"
}
```

**Rate limit tiers**:
- **Global**: 60 requests per minute per IP
- **Reports**: 10 reports per IP per 15 minutes
- **Per-address**: 3 reports per IP per address per 15 minutes

**How to handle**:
- Implement exponential backoff
- Cache results to reduce API calls
- Use [user_hash](/docs/api/models/report) for better rate limits
- Contact support if you need higher limits

### 500 Server Error

**Cause**: Unexpected server error

```json
{
  "error": "Internal Server Error",
  "message": "An unexpected error occurred. Please try again later.",
  "path": "/lookup"
}
```

**How to handle**:
- Retry with exponential backoff
- Wait a few minutes before retrying
- Check [status page](https://status.trashalert.com) for incidents
- Contact support if persistent

## Error Handling Strategies

### Strategy 1: Exponential Backoff

Implement exponential backoff for retryable errors (429, 500, 503):

**JavaScript:**
```javascript
async function fetchWithRetry(url, options = {}, maxRetries = 3) {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      const response = await fetch(url, options);

      if (response.ok) {
        return await response.json();
      }

      // Retryable errors
      if ([429, 500, 503].includes(response.status)) {
        if (attempt < maxRetries - 1) {
          const delay = Math.pow(2, attempt) * 1000 +
                       Math.random() * 1000;
          await new Promise(r => setTimeout(r, delay));
          continue;
        }
      }

      // Non-retryable error
      const error = await response.json();
      throw new Error(error.message);
    } catch (error) {
      if (attempt === maxRetries - 1) throw error;
    }
  }
}

// Usage
const result = await fetchWithRetry(
  'https://api.trashalert.com/v1/lookup?address=...'
);
```

**Python:**
```python
import time
import random
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import requests

def create_session_with_retries(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504)
):
    """Create requests session with automatic retry."""
    session = requests.Session()

    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )

    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    return session

# Usage
session = create_session_with_retries()
response = session.get('https://api.trashalert.com/v1/lookup?address=...')
```

### Strategy 2: Caching

Reduce API calls by caching results:

**JavaScript:**
```javascript
class CachedAPI {
  constructor(ttlMinutes = 60) {
    this.cache = new Map();
    this.ttlMs = ttlMinutes * 60 * 1000;
  }

  async lookup(address) {
    const cacheKey = `lookup:${address}`;
    const cached = this.getFromCache(cacheKey);

    if (cached) {
      console.log('Using cached result');
      return cached;
    }

    const result = await fetch(
      `/lookup?address=${encodeURIComponent(address)}`
    ).then(r => r.json());

    this.setInCache(cacheKey, result);
    return result;
  }

  getFromCache(key) {
    const entry = this.cache.get(key);
    if (!entry) return null;

    if (Date.now() > entry.expiresAt) {
      this.cache.delete(key);
      return null;
    }

    return entry.value;
  }

  setInCache(key, value) {
    this.cache.set(key, {
      value,
      expiresAt: Date.now() + this.ttlMs
    });
  }
}

// Usage
const api = new CachedAPI(60);  // 1 hour cache
```

**Python:**
```python
from datetime import datetime, timedelta
from functools import wraps

def cache_results(ttl_minutes=60):
    """Decorator to cache API results."""
    cache = {}

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = str((args, tuple(sorted(kwargs.items()))))

            if cache_key in cache:
                value, expires_at = cache[cache_key]
                if datetime.now() < expires_at:
                    return value

            result = func(*args, **kwargs)
            cache[cache_key] = (
                result,
                datetime.now() + timedelta(minutes=ttl_minutes)
            )
            return result

        return wrapper
    return decorator

@cache_results(ttl_minutes=60)
def lookup(address):
    """Cached lookup."""
    return client.lookup(address)
```

### Strategy 3: User-Facing Error Messages

Provide helpful messages to users:

**JavaScript:**
```javascript
async function userFriendlyLookup(address) {
  try {
    const result = await api.lookup(address);

    if (result.data_source === 'UNKNOWN') {
      return {
        success: false,
        message: `We don't have data for "${address}" yet. ` +
                 'Please submit your trash day to help improve our database!'
      };
    }

    return {
      success: true,
      message: `Trash day for ${address}: ${result.trash_day_of_week}`
    };
  } catch (error) {
    if (error.status === 429) {
      return {
        success: false,
        message: 'Too many requests. Please wait a moment and try again.'
      };
    } else if (error.status === 500) {
      return {
        success: false,
        message: 'Our servers are having trouble. Please try again in a few moments.'
      };
    } else {
      return {
        success: false,
        message: 'Something went wrong. Please try again.'
      };
    }
  }
}
```

### Strategy 4: Request Validation

Validate before sending:

**JavaScript:**
```javascript
function validateAddress(address) {
  const errors = [];

  if (!address || address.trim().length === 0) {
    errors.push('Address cannot be empty');
  }

  if (address.length < 5) {
    errors.push('Address must be at least 5 characters');
  }

  if (address.length > 500) {
    errors.push('Address must be less than 500 characters');
  }

  return {
    valid: errors.length === 0,
    errors
  };
}

function validateDay(day) {
  const validDays = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN',
                     'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY',
                     'FRIDAY', 'SATURDAY', 'SUNDAY'];

  return {
    valid: validDays.includes(day.toUpperCase()),
    normalized: day.toUpperCase()
  };
}
```

## Error Handling Checklist

### Before Sending a Request

- [ ] Validate address format (not empty, not too long)
- [ ] Validate day format if providing days
- [ ] Check internet connection
- [ ] Implement caching for better performance

### Handling a Response

- [ ] Check HTTP status code
- [ ] Handle 429 with exponential backoff
- [ ] Handle 500/503 with retry
- [ ] Handle 400/422 with user-friendly message
- [ ] Handle 404/UNKNOWN with helpful guidance

### User Experience

- [ ] Show loading state while requesting
- [ ] Display error message clearly
- [ ] Suggest actions to resolve (try again, check address, etc.)
- [ ] Provide fallback options
- [ ] Log errors for debugging

## Monitoring and Debugging

### Request/Response Logging

**JavaScript:**
```javascript
const api = new TrashAlertAPI();

// Log all requests and responses
const originalFetch = api.request.bind(api);

api.request = async function(endpoint, options) {
  console.log(`[API] ${options?.method || 'GET'} ${endpoint}`);

  try {
    const response = await originalFetch(endpoint, options);
    console.log(`[API] ${endpoint} → 200 OK`);
    return response;
  } catch (error) {
    console.error(`[API] ${endpoint} → ${error.message}`);
    throw error;
  }
};
```

### Error Reporting

**JavaScript:**
```javascript
function reportError(context, error) {
  // Send to your error tracking service
  fetch('/api/errors', {
    method: 'POST',
    body: JSON.stringify({
      timestamp: new Date().toISOString(),
      context,
      error: error.message,
      stack: error.stack
    })
  });
}
```

## Testing Error Scenarios

### Test Invalid Address
```bash
curl "https://api.trashalert.com/v1/lookup?address=x"
# Expect: 422 Validation Error
```

### Test Rate Limit
```bash
for i in {1..70}; do
  curl -s "https://api.trashalert.com/v1/lookup?address=test" \
    | grep -q "Too Many Requests" && echo "Rate limited!" && break
done
```

### Test Coordinate Validation
```bash
curl "https://api.trashalert.com/v1/lookup?lat=91&lon=0"
# Expect: 422 Validation Error (latitude > 90)
```

## Support

If you encounter issues:

1. **Check the documentation** - Review endpoint requirements
2. **Validate your request** - Use the error messages to guide you
3. **Check the status page** - See if there are ongoing incidents
4. **Contact support** - Email support@trashalert.com with:
   - Your request (sanitized)
   - The exact error response
   - Steps to reproduce
   - Your use case

