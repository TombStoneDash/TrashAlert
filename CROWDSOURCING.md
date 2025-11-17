# Crowdsourcing Engine Documentation

## Overview

The TrashAlert crowdsourcing engine allows users to submit reports about trash pickup schedules, which are aggregated into a consensus view. This provides coverage for addresses not in the official database.

## Database Schema

### `crowd_reports` Table

Stores individual user reports:

- `id`: Primary key
- `address_id`: Foreign key to addresses table
- `trash_day`: Reported trash pickup day (MON, TUE, WED, THU, FRI, SAT, SUN)
- `recycling_day`: Reported recycling pickup day
- `green_day`: Reported green waste pickup day
- `user_hash`: Optional anonymous user identifier (for preventing duplicate reports)
- `ip_address`: Request IP (for spam prevention)
- `created_at`: Timestamp of report submission

### `crowd_consensus` Table

Stores aggregated consensus data per address:

- `id`: Primary key
- `address_id`: Foreign key to addresses table (unique)
- `consensus_trash_day`: Most commonly reported trash day
- `consensus_recycling_day`: Most commonly reported recycling day
- `consensus_green_day`: Most commonly reported green waste day
- `total_reports`: Number of reports for this address
- `trash_agreement_ratio`: Percentage agreement for trash day
- `recycling_agreement_ratio`: Percentage agreement for recycling day
- `green_agreement_ratio`: Percentage agreement for green waste day
- `is_verified`: Boolean flag indicating if consensus meets verification threshold
- `created_at`: When consensus was first created
- `updated_at`: When consensus was last updated

## Consensus Algorithm

### Calculation Logic

For each address with crowdsourced reports:

1. **Aggregate Reports**: Group all reports by address_id
2. **Calculate Most Common**: For each day type (trash, recycling, green):
   - Find the most frequently reported value
   - Calculate agreement ratio = (count of most common) / (total non-null reports)
3. **Overall Agreement**: Average the agreement ratios across all day types
4. **Verification**: Mark as verified if BOTH conditions are met:
   - Total reports ≥ 3
   - Average agreement ratio ≥ 0.75 (75%)

### Example

Given reports for "123 Main St":
- User A: trash=MON, recycling=WED
- User B: trash=MON, recycling=WED
- User C: trash=MON, recycling=THU
- User D: trash=TUE, recycling=WED

Results:
- Trash day: MON (3/4 = 75% agreement)
- Recycling day: WED (3/4 = 75% agreement)
- Overall agreement: 75%
- **Status**: VERIFIED (4 reports ≥ 3, 75% agreement ≥ 75%)

## API Endpoints

### POST /report

Submit a crowdsourced report.

**Request Body**:
```json
{
  "address": "123 Main Street, San Diego, CA",
  "trash_day": "MON",
  "recycling_day": "WED",
  "green_day": null,
  "user_hash": "optional-anonymous-identifier"
}
```

**Validations**:
- At least one day type must be provided
- Day values must be valid (MON, TUE, WED, THU, FRI, SAT, SUN)
- Address must be parseable

**Rate Limiting**:
- Maximum 10 reports per IP per 15 minutes (global limit)
- Maximum 3 reports per IP per address per 15 minutes (prevents address spam)

**Response**:
```json
{
  "success": true,
  "message": "Report submitted successfully",
  "address_id": 42,
  "normalized_address": "123 MAIN STREET, SAN DIEGO, CA",
  "consensus": {
    "trash_day": "MON",
    "recycling_day": "WED",
    "green_day": null,
    "reports_count": 3,
    "trash_agreement_ratio": 1.0,
    "recycling_agreement_ratio": 1.0,
    "green_agreement_ratio": 0.0,
    "is_verified": true
  }
}
```

### GET /lookup

Lookup trash pickup schedule for an address.

**Data Source Priority**:
1. **CROWD_VERIFIED**: Verified crowdsourced consensus (≥3 reports, ≥75% agreement)
2. **OFFICIAL**: Official GIS/municipality data
3. **CROWD_UNVERIFIED**: Unverified crowdsourced data (< 3 reports or < 75% agreement)
4. **UNKNOWN**: No data available

**Query Parameters**:
- `address`: Address string to lookup

**Response**:
```json
{
  "address": "123 Main Street, San Diego, CA",
  "normalized_address": "123 MAIN STREET, SAN DIEGO, CA",
  "trash_day": "MON",
  "recycling_day": "WED",
  "green_day": null,
  "source": "CROWD_VERIFIED",
  "consensus_reports_count": 3,
  "consensus_agreement_ratio": 1.0,
  "lat": 32.7157,
  "lon": -117.1611
}
```

## Spam Prevention

### Rate Limiting

Simple in-memory rate limiter with two levels:

1. **Global limit**: 10 reports per IP per 15-minute window
2. **Per-address limit**: 3 reports per IP per address per 15-minute window

Rate limited requests return HTTP 429 with message: "Rate limit exceeded. Please try again later."

**Note**: In production, replace in-memory storage with Redis or similar distributed cache for multi-instance deployments.

### User Hash

Optional `user_hash` field allows:
- Tracking unique contributors without storing PII
- Preventing duplicate reports from same user
- Future analytics on report quality per user

**Privacy**: User hash should be generated client-side using a stable device identifier. Never send actual user identity.

## Maintenance Scripts

### scripts/processing/update_crowd_consensus.py

Batch script to recalculate consensus for all addresses.

**Usage**:
```bash
python scripts/processing/update_crowd_consensus.py
```

**When to run**:
- After database migrations
- To fix inconsistencies
- As periodic maintenance (though consensus auto-updates on each report)

**Output**:
```
✓ Updated consensus for 42 addresses
  15 addresses are VERIFIED (≥3 reports, ≥75% agreement)
  27 addresses are unverified
```

## Testing

### Manual Testing

Use the provided test script:

```bash
# Start the API server
uvicorn app.main:app --reload

# In another terminal, run tests
python test_crowdsourcing.py
```

### Test Cases

The test script verifies:
1. Initial lookup returns UNKNOWN for new addresses
2. First report creates consensus (unverified)
3. Third report with 100% agreement triggers verification
4. Lookup returns CROWD_VERIFIED source
5. Disagreement below 75% remains unverified
6. Rate limiting blocks excessive requests
7. Stats endpoint returns correct counts

## Security Considerations

### What's Protected

✅ **IP-based rate limiting** prevents automated spam
✅ **Anonymous user tracking** via optional hash (no PII stored)
✅ **Input validation** on all day values
✅ **SQL injection protection** via SQLAlchemy ORM

### What's NOT Protected (Future Enhancements)

⚠️ **No authentication** - anyone can submit reports
⚠️ **In-memory rate limiter** - resets on server restart, doesn't work across instances
⚠️ **No CAPTCHA** - vulnerable to bot attacks
⚠️ **No user reputation** - all reports weighted equally
⚠️ **No geographic validation** - users can report any address

### Recommendations for Production

1. **Add authentication** - Require user accounts with email verification
2. **Implement CAPTCHA** - Use reCAPTCHA or hCaptcha on /report endpoint
3. **Use Redis for rate limiting** - Persistent, distributed rate limiting
4. **Add geographic validation** - Only allow reports for addresses near user's location
5. **Implement user reputation** - Weight reports from trusted users more heavily
6. **Add moderation tools** - Admin interface to review/remove suspicious reports
7. **Monitor for patterns** - Alert on suspicious activity (many reports from same IP, sudden spikes, etc.)

## Verification Thresholds

Current settings (defined in `app/utils.py`):

```python
MIN_REPORTS = 3
MIN_AGREEMENT_RATIO = 0.75  # 75%
```

### Why These Values?

- **3 reports minimum**: Prevents single user from creating "verified" data
- **75% agreement**: High enough to ensure quality, low enough to allow some disagreement
  - 3/4 reports (75%) = verified
  - 2/3 reports (67%) = not verified
  - 4/5 reports (80%) = verified

### Adjusting Thresholds

To change verification rules, modify `app/utils.py:177`:

```python
# More strict: require 4 reports and 80% agreement
is_verified = total_reports >= 4 and avg_ratio >= 0.80

# More lenient: require 2 reports and 66% agreement
is_verified = total_reports >= 2 and avg_ratio >= 0.66
```

## Monitoring

Use the `/stats` endpoint to monitor system health:

```bash
curl http://localhost:8000/stats
```

**Key metrics to watch**:
- `verified_consensus` / `total_consensus` ratio (should be > 50%)
- Rapid growth in `total_reports` (could indicate spam)
- Large difference between `total_addresses` and `total_consensus` (indicates need for more crowdsourcing)
