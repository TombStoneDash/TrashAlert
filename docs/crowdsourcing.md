# TrashAlert Crowdsourcing & Consensus Logic

## Overview

TrashAlert uses a crowdsourcing approach to determine trash collection schedules. Instead of relying on official (often outdated or incomplete) city data, the system aggregates observations from multiple users to build consensus on when trash is actually collected.

This document explains how the consensus algorithm works, quality metrics, and conflict resolution strategies.

## Why Crowdsourcing?

### Challenges with Official Data
- Many cities don't publish digital trash schedules
- Official schedules may be outdated or incorrect
- Complex subdivision-based schedules are hard to navigate
- Routes change but documentation lags

### Benefits of Crowdsourcing
- Real-time data from actual observations
- Self-correcting as more users contribute
- Covers gaps in official information
- Can detect schedule changes quickly

## Data Collection

### User Report Structure

Each user report contains:

```json
{
  "address_id": 12345,
  "collection_day": "Wednesday",
  "collection_type": "trash",
  "reported_at": "2025-11-16T08:30:00Z",
  "user_token": "hashed_anonymous_id",
  "notes": "Saw truck at 7am"
}
```

**Fields**:
- `address_id`: The address being reported on
- `collection_day`: Day of week when collection was observed
- `collection_type`: Type (trash, recycling, green_waste, bulk)
- `reported_at`: When the observation occurred
- `user_token`: Anonymous user identifier (for rate limiting)
- `notes`: Optional user comments

### Collection Types

The system tracks multiple collection types:

1. **Trash**: Regular garbage collection
2. **Recycling**: Recyclable materials
3. **Green Waste**: Yard waste, composting
4. **Bulk**: Large item pickup (less frequent)

Each type can have a different schedule, calculated independently.

## Consensus Algorithm

### Core Principle

**The day reported most frequently is the consensus day.**

However, we need to ensure quality by:
- Requiring minimum number of reports
- Weighting recent reports higher
- Calculating confidence scores
- Detecting conflicts

### Algorithm Steps

#### 1. Filter Reports

```sql
SELECT
    collection_day,
    reported_at
FROM user_reports
WHERE address_id = ?
  AND collection_type = ?
  AND reported_at > NOW() - INTERVAL '6 months'  -- Recency filter
  AND is_verified = TRUE OR is_verified IS NULL  -- Exclude flagged reports
```

**Filters**:
- Only reports from last 6 months (schedules can change)
- Optionally exclude reports flagged as incorrect
- Filter by specific address and collection type

#### 2. Calculate Raw Counts

```sql
SELECT
    collection_day,
    COUNT(*) as report_count
FROM filtered_reports
GROUP BY collection_day
ORDER BY report_count DESC
```

**Example Result**:
```
collection_day | report_count
---------------|-------------
Wednesday      | 12
Thursday       | 3
Monday         | 1
```

#### 3. Apply Recency Weighting

More recent reports are more reliable (schedules may have changed):

```python
def calculate_weighted_score(reports):
    """
    Apply exponential decay weighting based on report age.
    Recent reports weighted higher than old ones.
    """
    scores = {}
    now = datetime.now()

    for report in reports:
        day = report['collection_day']
        age_days = (now - report['reported_at']).days

        # Exponential decay: weight = e^(-age/180)
        # Half-life of ~125 days
        weight = math.exp(-age_days / 180)

        scores[day] = scores.get(day, 0) + weight

    return scores
```

**Example with Weighting**:
```
collection_day | raw_count | weighted_score
---------------|-----------|---------------
Wednesday      | 12        | 10.8  (mostly recent)
Thursday       | 3         | 1.2   (older reports)
Monday         | 1         | 0.9   (old report)
```

#### 4. Determine Consensus Day

The day with the highest weighted score becomes the consensus:

```python
consensus_day = max(scores.items(), key=lambda x: x[1])[0]
# Result: "Wednesday"
```

#### 5. Calculate Confidence Score

Confidence score (0-100) based on:
- **Agreement**: How many reports agree vs total
- **Count**: Total number of reports
- **Recency**: How recent the reports are

```python
def calculate_confidence(day_scores, total_reports):
    """
    Calculate confidence score (0-100) for the consensus.

    Factors:
    - Agreement percentage (0-60 points)
    - Report count (0-30 points)
    - Recency (0-10 points)
    """
    # Get consensus day and its score
    consensus_day, consensus_score = max(day_scores.items(), key=lambda x: x[1])
    total_weighted = sum(day_scores.values())

    # 1. Agreement component (0-60 points)
    agreement_pct = (consensus_score / total_weighted) * 100
    agreement_points = min(agreement_pct * 0.6, 60)

    # 2. Report count component (0-30 points)
    # Logarithmic scale: 3 reports = ~15pts, 10 reports = ~25pts, 20+ = 30pts
    count_points = min(math.log(total_reports + 1) * 10, 30)

    # 3. Recency component (0-10 points)
    # Based on average age of reports
    avg_age_days = calculate_average_age(reports)
    recency_points = max(10 - (avg_age_days / 30), 0)  # Decay over 300 days

    confidence = agreement_points + count_points + recency_points
    return round(confidence, 2)
```

**Example Calculation**:
```
Scenario: 12 reports for Wednesday, 3 for Thursday (total 15)

Agreement: 12/15 = 80%
  → 80 * 0.6 = 48 points

Report Count: 15 reports
  → log(16) * 10 = 27.7 points

Recency: Average 45 days old
  → 10 - (45/30) = 8.5 points

Total Confidence: 48 + 27.7 + 8.5 = 84.2/100
```

#### 6. Calculate Agreement Percentage

Simple percentage of reports agreeing with consensus:

```python
agreement_percentage = (reports_for_consensus_day / total_reports) * 100
# Example: 12/15 = 80%
```

### Confidence Tiers

Reports are categorized into confidence tiers:

| Tier | Confidence Score | Min Reports | Agreement | Display |
|------|------------------|-------------|-----------|---------|
| **High** | ≥75 | ≥5 | ≥75% | ✅ "Reliable" |
| **Medium** | 50-74 | ≥3 | ≥60% | ⚠️ "Likely" |
| **Low** | 25-49 | ≥2 | ≥50% | ❓ "Uncertain" |
| **Very Low** | <25 | <2 | <50% | ⛔ "Insufficient Data" |

**User-Facing Display**:
- **High**: "Trash collected on Wednesday" (green check)
- **Medium**: "Likely Wednesday, but verify" (yellow warning)
- **Low**: "Uncertain - please report your observation" (red question)
- **Very Low**: "No data - be the first to report!" (gray)

## Conflict Detection

### What is a Conflict?

A conflict occurs when:
- Multiple days have significant report counts
- No clear consensus (e.g., 45% say Wed, 55% say Thu)
- High disagreement between recent and old reports

### Detection Algorithm

```python
def detect_conflict(day_scores, total_reports, threshold=0.75):
    """
    Detect if there's a schedule conflict.

    Conflict exists if:
    1. Top day has <75% of weighted votes
    2. At least 2 days have >20% each
    3. Total reports ≥ 5 (enough data to be meaningful)
    """
    if total_reports < 5:
        return False  # Not enough data

    sorted_days = sorted(day_scores.items(), key=lambda x: x[1], reverse=True)
    top_score = sorted_days[0][1]
    total_score = sum(day_scores.values())

    # Top day percentage
    top_pct = top_score / total_score

    if top_pct < threshold:
        # Check if there are competing days
        competing_days = [
            day for day, score in sorted_days[1:]
            if (score / total_score) > 0.20
        ]

        if len(competing_days) >= 1:
            return True, {
                'top_day': sorted_days[0][0],
                'top_percentage': top_pct * 100,
                'competing_days': competing_days,
                'severity': 'high' if top_pct < 0.60 else 'medium'
            }

    return False, None
```

**Example Conflict**:
```
collection_day | report_count | percentage
---------------|--------------|------------
Wednesday      | 8            | 53%
Thursday       | 6            | 40%
Friday         | 1            | 7%

Status: CONFLICT DETECTED
Severity: Medium (top day <60%)
Competing: Wednesday (53%) vs Thursday (40%)
```

### Conflict Storage

Conflicts are stored in `schedule_conflicts` table:

```json
{
  "address_id": 12345,
  "collection_type": "trash",
  "conflict_details": {
    "Wednesday": 8,
    "Thursday": 6,
    "Friday": 1
  },
  "severity": "medium",
  "detected_at": "2025-11-16T10:00:00Z",
  "resolved": false
}
```

## Conflict Resolution

### Automatic Resolution

Conflicts can auto-resolve when:
1. More reports come in favoring one day (>75% agreement)
2. Recent reports clearly favor one day (old reports caused conflict)
3. Admin marks old reports as invalid

### Manual Resolution

Admins can:
1. **Verify in person**: Check the actual schedule
2. **Contact city**: Confirm official schedule
3. **Mark reports invalid**: Flag incorrect reports
4. **Override consensus**: Set known correct schedule

### Resolution Workflow

```
1. Conflict detected
   ↓
2. Admin notified
   ↓
3. Admin reviews report history
   ↓
4. Admin takes action:
   - Invalidate bad reports
   - Add verified report
   - Override schedule
   ↓
5. System recalculates consensus
   ↓
6. If resolved (>75%), mark conflict resolved
```

## Edge Cases

### 1. Schedule Changes

**Problem**: City changes schedule mid-year

**Solution**:
- Recency weighting naturally phases out old reports
- Sudden influx of new-day reports triggers conflict detection
- Admins can manually verify and mark old reports as outdated

**Example**:
```
Jan-Oct: 20 reports for "Wednesday"
Nov-Now: 8 reports for "Thursday"

Weighted scores:
  Wednesday: 8.5 (old reports decay)
  Thursday: 7.8 (recent reports)

Status: Possible schedule change - needs review
```

### 2. Alternating Schedules

**Problem**: Some areas have alternating weeks (Week A/B)

**Current Limitation**: System doesn't handle alternating schedules yet

**Future Solution**:
- Add recurrence patterns ("biweekly-A", "biweekly-B")
- Track date of observation, not just day of week
- Detect patterns: "Every other Wednesday"

### 3. Holiday Delays

**Problem**: Collections delayed due to holidays

**Current Limitation**: One-off delays may cause conflict

**Mitigation**:
- Users can add notes: "Delayed due to Thanksgiving"
- System could detect and filter reports near known holidays
- Future: Add "holiday delay" flag to reports

### 4. Malicious Reports

**Problem**: User submits false data

**Mitigation**:
- Rate limiting per user_token (max 5 reports/day)
- Outlier detection (if one user reports differently than 10 others)
- Admin review of suspicious patterns
- Community flagging (future feature)

### 5. Sparse Data

**Problem**: Address has only 1-2 reports

**Solution**:
- Display low confidence warning
- Prompt users to contribute
- Allow "copy from nearby" suggestions (future)

## Quality Metrics

### System-Wide Metrics

Track overall data quality:

```sql
-- Addresses by confidence tier
SELECT
    CASE
        WHEN confidence_score >= 75 THEN 'High'
        WHEN confidence_score >= 50 THEN 'Medium'
        WHEN confidence_score >= 25 THEN 'Low'
        ELSE 'Very Low'
    END as confidence_tier,
    COUNT(*) as address_count
FROM trash_schedules
WHERE collection_type = 'trash'
GROUP BY confidence_tier;
```

**Target Goals**:
- 70% of addresses at "High" confidence
- <10% at "Very Low" confidence
- <5% with unresolved conflicts

### Per-Address Metrics

Display to users:

```
Address: 1234 Main St

Trash Schedule: Wednesday
Confidence: 84% (High)
Based on: 12 reports
Last reported: 2 days ago
Agreement: 80% of users agree
```

## User Interface Implications

### Lookup Results

Show confidence clearly:

```
✅ Trash: Wednesday (Reliable - 84% confidence)
   Based on 12 community reports

⚠️ Recycling: Friday (Likely - 68% confidence)
   Based on 4 reports - help verify!

❓ Green Waste: No data yet
   Be the first to report!
```

### Report Submission

Encourage contributions:

```
Did you see trash collection today?

Address: 1234 Main St
Day: [Dropdown: Monday-Sunday]
Type: [Trash] [Recycling] [Green] [Bulk]

Your report helps your community! ✨

[Submit Report]
```

### Conflict Warnings

Alert users to uncertainty:

```
⚠️ Conflicting Reports

We have mixed reports for this address:
- 53% say Wednesday
- 40% say Thursday

Please double-check and report what you observe.
```

## Future Enhancements

### Machine Learning

- Predict schedules based on nearby addresses
- Detect pattern anomalies (possible changes)
- Auto-flag suspicious reports

### Gamification

- User reputation scores
- Leaderboards for contributors
- Badges for verified reports

### Integration

- Import official city data where available
- Sync with Google Calendar
- Push notifications day before collection

### Advanced Consensus

- Bayesian inference for probability distributions
- Temporal patterns (biweekly, monthly)
- Geographic clustering (same schedule for neighborhood)

## Conclusion

The crowdsourcing consensus algorithm balances:
- **Simplicity**: Easy for users to understand
- **Accuracy**: Weighted voting produces reliable results
- **Robustness**: Handles conflicts and edge cases
- **Transparency**: Clear confidence scores and metrics

By aggregating community observations, TrashAlert creates a self-maintaining, up-to-date trash schedule database that improves with each contribution.
