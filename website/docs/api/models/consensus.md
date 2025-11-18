---
sidebar_position: 3
title: Consensus Model
slug: /api/models/consensus
---

# Consensus Model

The Consensus model represents the aggregated, calculated schedule based on multiple crowdsourced reports.

## Schema

```typescript
interface Consensus {
  trash_day?: string;                    // Most common trash pickup day
  recycling_day?: string;                // Most common recycling pickup day
  green_day?: string;                    // Most common green waste pickup day
  reports_count: number;                 // Total reports used
  trash_agreement_ratio: number;         // Agreement %: 0.0 to 1.0
  recycling_agreement_ratio: number;     // Agreement %: 0.0 to 1.0
  green_agreement_ratio: number;         // Agreement %: 0.0 to 1.0
  is_verified: boolean;                  // Meets verification threshold
}
```

## Field Descriptions

### trash_day
- **Type**: String or undefined
- **Description**: Most commonly reported trash pickup day
- **Example**: "Wednesday"
- **Format**: Full day name (Monday-Sunday)
- **Calculation**: Mode (most frequent) of all reports

### recycling_day
- **Type**: String or undefined
- **Description**: Most commonly reported recycling pickup day
- **Example**: "Friday"
- **Format**: Full day name
- **Calculation**: Mode of all recycling reports

### green_day
- **Type**: String or undefined
- **Description**: Most commonly reported green waste pickup day
- **Example**: "Wednesday"
- **Format**: Full day name
- **Calculation**: Mode of all green waste reports

### reports_count
- **Type**: Integer
- **Description**: Total number of crowdsourced reports used
- **Range**: 0 to N
- **Example**: 12
- **Note**: Each report may include 1-3 days (trash/recycling/green)

### trash_agreement_ratio
- **Type**: Number
- **Description**: Percentage of reports agreeing with trash consensus
- **Range**: 0.0 to 1.0
- **Example**: 0.92 (92% agreement)
- **Calculation**: Agreeing reports / Total trash reports

### recycling_agreement_ratio
- **Type**: Number
- **Description**: Percentage of reports agreeing with recycling consensus
- **Range**: 0.0 to 1.0
- **Example**: 0.85 (85% agreement)

### green_agreement_ratio
- **Type**: Number
- **Description**: Percentage of reports agreeing with green waste consensus
- **Range**: 0.0 to 1.0
- **Example**: 0.88 (88% agreement)

### is_verified
- **Type**: Boolean
- **Description**: Whether consensus meets verification threshold
- **Verification Criteria**:
  - >=3 reports total
  - >=67% agreement on the day
- **Example**: true
- **Impact**: Determines data source priority in lookup responses

## Consensus Calculation Algorithm

### Step 1: Collect Reports
```
Address: 1122 Palmview Ave
Period: Last 6 months

Reports:
1. trash_day: WED (2025-11-15)
2. trash_day: WED (2025-11-08)
3. trash_day: WED (2025-11-01)
4. trash_day: THU (2025-10-25)
5. trash_day: WED (2025-10-18)
6. trash_day: WED (2025-10-11)
7. trash_day: WED (2025-10-04)
8. trash_day: THU (2025-09-27)
9. trash_day: WED (2025-09-20)
10. trash_day: WED (2025-09-13)
11. trash_day: WED (2025-09-06)
12. trash_day: WED (2025-08-30)
```

### Step 2: Count Occurrences
```
Wednesday: 10 reports (83%)
Thursday:  2 reports (17%)
```

### Step 3: Determine Consensus
```
Consensus Day: Wednesday (highest count)
Agreement Ratio: 10/12 = 0.833 (83%)
```

### Step 4: Verify
```
Criteria:
- Reports >= 3: 12 ✓
- Agreement >= 67%: 83% ✓

Result: is_verified = true
```

## Verification Thresholds

| Metric | Threshold | Status |
|--------|-----------|--------|
| Minimum Reports | >=3 | Required for verification |
| Minimum Agreement | >=67% (2/3) | Required for verification |
| Both Criteria | Must both pass | For is_verified = true |

### Verification States

**VERIFIED** (is_verified = true)
- >=3 reports with >=67% agreement
- High confidence in consensus
- Used as primary data source in lookups
- Example: 10/12 = 83% agreement

**UNVERIFIED** (is_verified = false)
- &lt;3 reports OR &lt;67% agreement
- Lower confidence
- Used as fallback in lookups
- Example: 2/4 = 50% agreement

**NO CONSENSUS**
- No reports submitted yet
- Not yet in consensus table
- Data source = UNKNOWN

## Quality Levels

Based on agreement ratio:

| Agreement | Level | Quality | Action |
|-----------|-------|---------|--------|
| 90-100% | Excellent | Very high confidence | Use as primary |
| 80-89% | Good | High confidence | Use as primary |
| 67-79% | Fair | Acceptable confidence | Use, monitor for changes |
| 50-66% | Poor | Low confidence | Requires verification |
| 0-49% | Conflicting | Multiple valid days | Flag for review |

## JSON Example

### High Confidence Consensus

```json
{
  "trash_day": "Wednesday",
  "recycling_day": "Friday",
  "green_day": "Wednesday",
  "reports_count": 12,
  "trash_agreement_ratio": 0.92,
  "recycling_agreement_ratio": 0.85,
  "green_agreement_ratio": 0.88,
  "is_verified": true
}
```

### Lower Confidence Consensus

```json
{
  "trash_day": "Monday",
  "recycling_day": null,
  "green_day": null,
  "reports_count": 4,
  "trash_agreement_ratio": 0.75,
  "recycling_agreement_ratio": 0.0,
  "green_agreement_ratio": 0.0,
  "is_verified": true
}
```

### Unverified Consensus

```json
{
  "trash_day": "Tuesday",
  "recycling_day": "Thursday",
  "green_day": null,
  "reports_count": 2,
  "trash_agreement_ratio": 0.50,
  "recycling_agreement_ratio": 0.50,
  "green_agreement_ratio": 0.0,
  "is_verified": false
}
```

## Database Schema

```sql
CREATE TABLE crowd_consensus (
  id INTEGER PRIMARY KEY,
  address_id INTEGER NOT NULL UNIQUE,
  consensus_trash_day VARCHAR(20),
  consensus_recycling_day VARCHAR(20),
  consensus_green_day VARCHAR(20),

  total_reports INTEGER DEFAULT 0,
  trash_agreement_ratio DECIMAL(3,2) DEFAULT 0,
  recycling_agreement_ratio DECIMAL(3,2) DEFAULT 0,
  green_agreement_ratio DECIMAL(3,2) DEFAULT 0,

  is_verified BOOLEAN DEFAULT FALSE,

  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (address_id) REFERENCES addresses(id),
  CONSTRAINT agreement_check CHECK (
    trash_agreement_ratio BETWEEN 0 AND 1.0
  )
);

CREATE INDEX idx_consensus_verified ON crowd_consensus(is_verified);
CREATE INDEX idx_consensus_address ON crowd_consensus(address_id);
```

## Update Frequency

Consensus is recalculated:
- After each new report submission
- On-demand API request
- Cached for 5 minutes
- Full recalculation weekly

## Conflict Detection

Addresses with conflicting reports are detected:

```javascript
// Detect conflict (multiple days with high agreement)
function hasConflict(consensus, reports) {
  const dayScores = {};

  reports.forEach(report => {
    const day = report.trash_day;
    dayScores[day] = (dayScores[day] || 0) + 1;
  });

  const topDays = Object.entries(dayScores)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 2);

  // Conflict if top 2 days are close
  if (topDays.length === 2) {
    const ratio = topDays[1][1] / topDays[0][1];
    return ratio > 0.4;  // Less than 2.5x difference
  }

  return false;
}
```

Example conflicting address:
```
Wednesday: 5 reports (42%)
Thursday:  6 reports (50%)
Monday:    2 reports (8%)

Conflict: True (Thursday barely wins)
```

## Usage Examples

### Interpreting Consensus Strength

```javascript
function getConfidenceLevel(consensus) {
  if (!consensus.is_verified) {
    return 'Low - Insufficient data';
  }

  const avgRatio = (
    consensus.trash_agreement_ratio +
    consensus.recycling_agreement_ratio +
    consensus.green_agreement_ratio
  ) / 3;

  if (avgRatio > 0.9) return 'Very High';
  if (avgRatio > 0.8) return 'High';
  if (avgRatio > 0.7) return 'Moderate';
  return 'Fair';
}

// Usage
const level = getConfidenceLevel(consensus);
console.log(`Confidence: ${level}`);
```

### Building User Feedback

```react
function ConsensusDisplay({ consensus }) {
  const agreementPct = Math.round(
    consensus.trash_agreement_ratio * 100
  );

  return (
    <div className="consensus-info">
      <h3>{consensus.trash_day}</h3>

      <div className="agreement-bar">
        <div
          className="bar-fill"
          style={{ width: `${agreementPct}%` }}
        />
        <span>{agreementPct}%</span>
      </div>

      <p className="reports-count">
        Based on {consensus.reports_count} community reports
      </p>

      {consensus.is_verified ? (
        <p className="verified">✓ Verified consensus</p>
      ) : (
        <p className="unverified">
          Help verify by submitting your observation
        </p>
      )}
    </div>
  );
}
```

### Monitoring Data Quality

```python
def assess_data_quality(consensus):
    """Return quality assessment."""
    if not consensus['is_verified']:
        return 'INSUFFICIENT_DATA'

    avg_agreement = (
        consensus['trash_agreement_ratio'] +
        consensus['recycling_agreement_ratio'] +
        consensus['green_agreement_ratio']
    ) / 3

    if avg_agreement > 0.85:
        return 'EXCELLENT'
    elif avg_agreement > 0.75:
        return 'GOOD'
    elif avg_agreement > 0.67:
        return 'FAIR'
    else:
        return 'NEEDS_REVIEW'

# Usage
quality = assess_data_quality(consensus)
print(f"Data Quality: {quality}")
```

## Data Source Priority

In lookups, consensus is used with this priority:

1. **CROWD_VERIFIED** (is_verified = true)
   - Best data source when available
   - >=3 reports with >=67% agreement

2. **OFFICIAL** (municipal data)
   - Authoritative but possibly outdated
   - Used when consensus unavailable

3. **CROWD_UNVERIFIED** (is_verified = false)
   - Lower confidence consensus
   - Better than nothing

4. **UNKNOWN**
   - No data available
   - Community contributions welcome

## Related Models

- [Address Model](/docs/api/models/address) - The address being reported on
- [Report Model](/docs/api/models/report) - Individual reports contributing to consensus
- [LookupResponse](/docs/api/endpoints/lookup) - Response that includes consensus data

