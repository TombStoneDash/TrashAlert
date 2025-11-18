---
sidebar_position: 4
title: GET /stats
slug: /api/endpoints/stats
---

# GET /stats - System Statistics

Get comprehensive statistics about the TrashAlert system, database coverage, and data quality.

## Endpoint

```
GET /stats
```

## Description

This endpoint provides system-wide statistics including:
- Total addresses in the database
- Report submission statistics
- Consensus coverage and verification rates
- Per-city breakdowns
- System health indicators

Use this endpoint to understand database coverage, data quality, and system status.

## Query Parameters

None required. This is a simple GET endpoint with no parameters.

## Request Examples

```bash
# Get system statistics
curl https://api.trashalert.com/v1/stats

# Pretty-print JSON response
curl https://api.trashalert.com/v1/stats | jq .
```

## Response Schema

### Success Response (200 OK)

```json
{
  "total_addresses": 248,
  "total_reports": 1024,
  "total_consensus": 156,
  "verified_consensus": 92,
  "cities": [
    {
      "city": "El Centro",
      "address_count": 50
    },
    {
      "city": "Imperial",
      "address_count": 50
    },
    {
      "city": "Brawley",
      "address_count": 48
    },
    {
      "city": "Holtville",
      "address_count": 50
    },
    {
      "city": "Calexico",
      "address_count": 50
    },
    {
      "city": "San Diego",
      "address_count": 0
    }
  ],
  "pilot_cities": [
    "El Centro",
    "Imperial",
    "Brawley",
    "Holtville",
    "Calexico",
    "San Diego"
  ]
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `total_addresses` | integer | Total number of addresses in database |
| `total_reports` | integer | Total crowdsourced reports submitted |
| `total_consensus` | integer | Total consensus records computed |
| `verified_consensus` | integer | Consensus records meeting verification threshold |
| `cities` | array | Per-city statistics |
| `cities[].city` | string | City name |
| `cities[].address_count` | integer | Number of addresses in that city |
| `pilot_cities` | array | List of all supported pilot cities |

## Statistics Interpretation

### Coverage Metrics

- **Total Addresses**: Number of sampled addresses in database
  - Higher is better but limited by sampling strategy (50 per city initially)
  - Indicates geographic coverage

- **Total Reports**: Cumulative crowdsourced observations
  - Shows community engagement level
  - More reports = better consensus

- **Total Consensus**: Number of addresses with at least one report
  - Indicates percentage of database with crowdsourced data
  - Formula: `total_consensus / total_addresses`

### Data Quality Metrics

- **Verified Consensus**: Addresses with high-confidence consensus
  - Requires ≥3 reports with ≥67% agreement
  - Formula: `verified_consensus / total_consensus`
  - Higher percentage = better data quality

- **Verification Rate**: Percentage of addresses with verified consensus
  - Formula: `verified_consensus / total_addresses`
  - Good target: 50%+ verified coverage

### Example Analysis

```
Total Addresses: 248
Total Reports: 1024
Total Consensus: 156
Verified Consensus: 92

Analysis:
- Coverage Rate: 156/248 = 62.9% have consensus
- Verification Rate: 92/248 = 37.1% verified
- Avg Reports/Address: 1024/248 = 4.1 reports
- Reports/Consensus: 1024/156 = 6.6 reports per consensus
```

## City Breakdown

The `cities` array shows address distribution:

```
El Centro: 50 addresses (20.2%)
Imperial: 50 addresses (20.2%)
Brawley: 48 addresses (19.4%)
Holtville: 50 addresses (20.2%)
Calexico: 50 addresses (20.2%)
San Diego: 0 addresses (0%)
```

Use this to understand:
- Which cities have good coverage
- Where new address sampling is needed
- Geographic balance of data

## Performance Metrics

### Response Time
Expected: < 100ms

The endpoint returns cached statistics for performance. Cache is updated:
- Every 5 minutes
- After each report submission
- On-demand with cache invalidation

## Examples

### JavaScript/Fetch

```javascript
async function getStats() {
  try {
    const response = await fetch('https://api.trashalert.com/v1/stats', {
      headers: {
        'User-Agent': 'MyApp/1.0'
      }
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    const stats = await response.json();

    console.log(`Total Addresses: ${stats.total_addresses}`);
    console.log(`Total Reports: ${stats.total_reports}`);
    console.log(`Coverage: ${(stats.total_consensus / stats.total_addresses * 100).toFixed(1)}%`);
    console.log(`Verification: ${(stats.verified_consensus / stats.total_consensus * 100).toFixed(1)}%`);

    console.log('\nCities:');
    stats.cities.forEach(city => {
      console.log(`  ${city.city}: ${city.address_count} addresses`);
    });

    return stats;
  } catch (error) {
    console.error('Stats fetch failed:', error);
  }
}

// Display stats on page
async function displayStatsWidget() {
  const stats = await getStats();

  document.getElementById('total-addresses').textContent =
    stats.total_addresses.toLocaleString();
  document.getElementById('total-reports').textContent =
    stats.total_reports.toLocaleString();
  document.getElementById('verification-rate').textContent =
    `${(stats.verified_consensus / stats.total_consensus * 100).toFixed(1)}%`;
}
```

### Python

```python
import requests

def get_stats():
    """Get system statistics."""
    url = 'https://api.trashalert.com/v1/stats'

    headers = {
        'User-Agent': 'MyApp/1.0'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        stats = response.json()

        print(f"TrashAlert Statistics")
        print(f"=" * 40)
        print(f"Total Addresses: {stats['total_addresses']:,}")
        print(f"Total Reports: {stats['total_reports']:,}")
        print(f"Total Consensus: {stats['total_consensus']:,}")
        print(f"Verified Consensus: {stats['verified_consensus']:,}")

        coverage = stats['total_consensus'] / stats['total_addresses'] * 100
        verification = stats['verified_consensus'] / stats['total_consensus'] * 100 if stats['total_consensus'] > 0 else 0

        print(f"\nMetrics:")
        print(f"Coverage Rate: {coverage:.1f}%")
        print(f"Verification Rate: {verification:.1f}%")

        print(f"\nCity Breakdown:")
        for city in stats['cities']:
            if city['address_count'] > 0:
                pct = city['address_count'] / stats['total_addresses'] * 100
                print(f"  {city['city']}: {city['address_count']} ({pct:.1f}%)")

        return stats
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None

# Usage
stats = get_stats()
```

### cURL

```bash
# Get statistics
curl https://api.trashalert.com/v1/stats

# Pretty-print JSON
curl https://api.trashalert.com/v1/stats | jq .

# Get just city data
curl https://api.trashalert.com/v1/stats | jq '.cities'

# Get verification rate
curl https://api.trashalert.com/v1/stats | \
  jq '.verified_consensus / .total_consensus'
```

## Use Cases

### 1. Dashboard Widget
Display system health on a website:

```javascript
async function showHealthDashboard() {
  const stats = await getStats();

  return `
    <div class="stats-widget">
      <h3>TrashAlert Coverage</h3>
      <p>${stats.total_addresses} addresses tracked</p>
      <p>${stats.total_reports} community reports</p>
      <p>${(stats.verified_consensus / stats.total_addresses * 100).toFixed(1)}% verified</p>
    </div>
  `;
}
```

### 2. Data Quality Monitoring
Monitor data quality trends:

```python
import time
from datetime import datetime

def monitor_quality():
    """Monitor data quality over time."""
    stats = get_stats()

    verification_rate = stats['verified_consensus'] / stats['total_consensus']

    with open('stats_history.csv', 'a') as f:
        f.write(f"{datetime.now()},{stats['total_addresses']},"
                f"{stats['total_reports']},{stats['total_consensus']},"
                f"{stats['verified_consensus']},{verification_rate}\n")

    print(f"Verification rate: {verification_rate:.1%}")
```

### 3. City Coverage Planning
Identify cities needing more data:

```javascript
async function findUndercoveredCities() {
  const stats = await getStats();

  const undercovered = stats.cities.filter(city =>
    city.address_count < 40  // Less than 80% of 50 target
  );

  console.log('Cities needing more data:');
  undercovered.forEach(city => {
    console.log(`  ${city.city}: ${city.address_count}/50 addresses`);
  });
}
```

## Caching

Statistics are cached for 5 minutes. To get fresh statistics:
- Wait 5 minutes
- Submit a new report (triggers cache refresh)
- Contact API administrators for manual refresh

## Rate Limiting

This endpoint has relaxed rate limits:
- Standard rate limits still apply
- Up to 100 calls per minute recommended
- Suitable for frequent polling (every 30 seconds)

## Monitoring and Alerting

Set up alerts for these metrics:

```python
# Alert if verification rate drops below 30%
verification_rate = stats['verified_consensus'] / stats['total_consensus']
if verification_rate < 0.30:
    alert("Data quality degraded!")

# Alert if reports per address is too low
avg_reports = stats['total_reports'] / stats['total_addresses']
if avg_reports < 3:
    alert("Insufficient reports per address")
```

