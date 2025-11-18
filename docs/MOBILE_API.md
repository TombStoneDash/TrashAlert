# Mobile API Endpoints

Lightweight mobile-optimized endpoints designed for minimal payloads and low data connections.

## Key Features

- **Minimal payloads**: All responses < 1KB (typically 50-250 bytes)
- **Error-tolerant**: Graceful handling of missing data
- **Low-bandwidth friendly**: Optimized for 2G/3G connections
- **Abbreviated fields**: Single-letter field names and codes

## Field Naming Convention

Mobile endpoints use abbreviated field names to minimize payload size:

### Common Fields
- `addr` - Address string
- `c` - City ID
- `lat` - Latitude
- `lon` - Longitude
- `t` - Trash pickup
- `r` - Recycling pickup
- `g` - Green waste pickup
- `src` - Data source
- `cnt` - Count/number of reports
- `agr` - Agreement ratio
- `d` - Date
- `ok` - Success status
- `msg` - Message
- `ver` - Verified status
- `u` - User hash
- `err` - Error code

## Day Codes

Single-letter codes for days of the week:

- `M` - Monday
- `T` - Tuesday
- `W` - Wednesday
- `R` - Thursday (R to avoid conflict with Tuesday)
- `F` - Friday
- `S` - Saturday
- `U` - Sunday (U for sUnday)

## Source Codes

Single-letter codes for data sources:

- `V` - CROWD_VERIFIED (≥3 reports with ≥75% agreement)
- `O` - OFFICIAL (Municipal data)
- `U` - CROWD_UNVERIFIED (Consensus with <3 reports or <75% agreement)
- `X` - UNKNOWN (No data available)

---

## Endpoints

### 1. GET /mobile/lookup

Look up trash pickup schedule with minimal payload.

**Query Parameters:**
- `address` (optional) - Full address string
- `lat` (optional) - Latitude (requires `lon`)
- `lon` (optional) - Longitude (requires `lat`)
- `city_id` (optional) - City identifier

Must provide either `address` OR both `lat` and `lon`.

**Response Example:**
```json
{
  "addr": "1122 Palmview Ave, El Centro, CA",
  "c": "el_centro",
  "lat": 32.6345,
  "lon": -115.5631,
  "t": "W",
  "r": "F",
  "g": null,
  "src": "V",
  "cnt": 5,
  "agr": 0.95
}
```

**Response Size:** 150-250 bytes typical

**Field Descriptions:**
- `addr` - Matched address from database
- `c` - City ID
- `lat`, `lon` - Coordinates
- `t`, `r`, `g` - Trash, recycling, green waste pickup days (M/T/W/R/F/S/U or null)
- `src` - Data source (V/O/U/X)
- `cnt` - Number of crowdsourced reports (only for crowd data)
- `agr` - Agreement ratio 0-1 (only for crowd data)

---

### 2. GET /mobile/daily-schedule

Ultra-minimal endpoint returning only TODAY's schedule.

**Query Parameters:**
- `address` (optional) - Full address string
- `lat` (optional) - Latitude (requires `lon`)
- `lon` (optional) - Longitude (requires `lat`)
- `city_id` (optional) - City identifier

**Response Example:**
```json
{
  "d": "20250118",
  "t": true,
  "r": false,
  "g": false,
  "nt": "20250125",
  "nr": "20250120",
  "ng": null
}
```

**Response Size:** 50-150 bytes typical

**Field Descriptions:**
- `d` - Today's date (YYYYMMDD format)
- `t`, `r`, `g` - Boolean flags for pickups TODAY
- `nt`, `nr`, `ng` - Next pickup dates (YYYYMMDD format or null)

**Use Case:** Perfect for home screen widgets and daily notifications.

---

### 3. POST /mobile/report

Submit crowdsourced pickup schedule report.

**Request Body:**
```json
{
  "addr": "1122 Palmview Ave, El Centro, CA 92243",
  "t": "W",
  "r": "F",
  "g": null,
  "u": "user123hash"
}
```

**Request Size:** ~100 bytes typical

**Field Descriptions:**
- `addr` - Address string (required)
- `t`, `r`, `g` - Trash, recycling, green waste days (M/T/W/R/F/S/U or null)
- `u` - Optional stable user identifier

**Response Example:**
```json
{
  "ok": true,
  "msg": "Submitted",
  "addr": "1122 Palmview Ave",
  "cnt": 3,
  "ver": false
}
```

**Response Size:** ~80 bytes typical

**Field Descriptions:**
- `ok` - Success status
- `msg` - Response message
- `addr` - Normalized address
- `cnt` - Total reports for this address
- `ver` - Whether consensus is verified (≥3 reports with ≥75% agreement)

---

## Error Responses

All mobile endpoints return minimal error responses:

```json
{
  "err": "NOT_FOUND",
  "msg": "Address not found in database",
  "retry": true,
  "wait": 5
}
```

**Common Error Codes:**
- `BAD_REQUEST` - Invalid input parameters
- `NOT_FOUND` - Address not found
- `SERVER_ERROR` - Internal server error
- `RATE_LIMIT` - Too many requests

---

## Comparison: Standard vs Mobile Endpoints

### Lookup Endpoint Comparison

**Standard /lookup response:**
```json
{
  "matched_address": "1122 Palmview Ave",
  "city_id": "el_centro",
  "city_name": "El Centro",
  "lat": 32.6345,
  "lon": -115.5631,
  "trash_day_of_week": "Wednesday",
  "recycling_day_of_week": "Friday",
  "green_waste_day_of_week": null,
  "data_source": "CROWD_VERIFIED",
  "consensus_reports_count": 5,
  "consensus_agreement_ratio": 0.95,
  "consensus_details": {
    "reports_count": 5,
    "agreement_ratio": 0.95
  }
}
```
**Size:** ~350 bytes

**Mobile /mobile/lookup response:**
```json
{
  "addr": "1122 Palmview Ave, El Centro, CA",
  "c": "el_centro",
  "lat": 32.6345,
  "lon": -115.5631,
  "t": "W",
  "r": "F",
  "g": null,
  "src": "V",
  "cnt": 5,
  "agr": 0.95
}
```
**Size:** ~160 bytes

**Reduction:** ~54% smaller

---

## Best Practices

### For Mobile Apps

1. **Use daily-schedule for widgets**: The minimal boolean flags are perfect for quick checks
2. **Cache responses**: Standard HTTP caching headers are included
3. **Batch requests**: Make multiple calls in parallel when needed
4. **Handle offline mode**: All endpoints return graceful errors when data is missing

### For Low-Bandwidth Scenarios

1. **Prefer coordinate lookups**: Slightly smaller than full address strings
2. **Use city_id when known**: Reduces address ambiguity and payload size
3. **Request only what you need**: Use `/mobile/daily-schedule` instead of `/mobile/lookup` when you only need today's schedule

### Error Handling

```javascript
// Example error handling
try {
  const response = await fetch('/mobile/lookup?lat=32.6&lon=-115.5');
  const data = await response.json();

  if (data.err) {
    // Handle error
    if (data.retry && data.wait) {
      // Wait and retry
      setTimeout(() => retry(), data.wait * 1000);
    }
  } else if (data.src === 'X') {
    // No data available for this address
    showNoDataMessage();
  } else {
    // Use the data
    displaySchedule(data);
  }
} catch (error) {
  // Network error - retry with exponential backoff
}
```

---

## Performance Metrics

Based on testing with typical responses:

| Endpoint | Avg Size | Max Size | Compression vs Standard |
|----------|----------|----------|------------------------|
| /mobile/lookup | 160 bytes | 250 bytes | ~54% smaller |
| /mobile/daily-schedule | 80 bytes | 150 bytes | ~70% smaller |
| /mobile/report (request) | 100 bytes | 120 bytes | ~50% smaller |
| /mobile/report (response) | 85 bytes | 100 bytes | ~60% smaller |

**All payloads < 1KB guaranteed** ✓

---

## Implementation Notes

### Data Fidelity

Despite the minimal payloads, mobile endpoints maintain **full data fidelity**:

- All pickup days are preserved
- Data source priority is maintained (CROWD_VERIFIED > OFFICIAL > CROWD_UNVERIFIED)
- Consensus metrics are included when relevant
- Coordinate precision is maintained

### Backwards Compatibility

Mobile endpoints are **additive only**:
- Standard endpoints remain unchanged
- Both APIs can be used simultaneously
- No breaking changes to existing clients

### Rate Limiting

Mobile endpoints share the same rate limits as standard endpoints:
- 60 requests/minute per IP
- 1000 requests/hour per IP

Rate limit headers are included in all responses.
