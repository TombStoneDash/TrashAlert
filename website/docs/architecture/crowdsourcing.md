---
sidebar_position: 3
title: Crowdsourcing & Consensus
slug: /architecture/crowdsourcing
---

# Crowdsourcing and Consensus Algorithm

How TrashAlert aggregates community observations into reliable schedules.

Based on `/home/user/TrashAlert/docs/crowdsourcing.md`.

## Why Crowdsourcing?

Many cities don't publish digital trash schedules, schedules change without notice, and routes vary by neighborhood. Crowdsourcing lets the community build accurate, real-time data.

## The Consensus Algorithm

### Core Principle

**The day reported most frequently is the consensus day.**

However, we need quality metrics:
- Minimum reports required
- High agreement threshold
- Recent data weighted higher
- Conflict detection

### Algorithm Steps

#### 1. Collect Reports

Users submit observations:

```json
{
  "address": "1122 Palmview Ave, El Centro, CA",
  "trash_day": "Wednesday",
  "recycling_day": "Friday",
  "reported_at": "2025-11-18T10:30:00Z",
  "user_hash": "user_abc123"
}
```

Reports are filtered:
- Last 6 months only (schedules can change)
- Optional flagging of incorrect reports
- By specific address and collection type

#### 2. Calculate Mode

Count occurrences of each day:

```
Wednesday: 10 reports (83%)
Thursday:  2 reports (17%)
```

The day with most reports = consensus day.

#### 3. Apply Weighting

Recent reports are more reliable:

```python
# Exponential decay weighting
# Half-life: ~125 days
weight = e^(-age_days / 180)

Wednesday (recent): 10.8 weighted score
Thursday (older):   1.2 weighted score
```

#### 4. Determine Consensus

```python
consensus_day = day_with_highest_score
agreement_ratio = count_agreeing / total_count
is_verified = (total_count >= 3) and (agreement_ratio >= 0.67)
```

### Example Calculation

**Scenario**: 12 reports for Wednesday trash pickup

```
Report Data:
- 2025-11-15: Wednesday ← Recent
- 2025-11-08: Wednesday
- 2025-11-01: Wednesday
- 2025-10-25: Thursday  ← Older
- 2025-10-18: Wednesday
- 2025-10-11: Wednesday
- 2025-10-04: Wednesday
- 2025-09-27: Thursday
- 2025-09-20: Wednesday
- 2025-09-13: Wednesday
- 2025-09-06: Wednesday
- 2025-08-30: Wednesday

Consensus Calculation:
- Total reports: 12
- Wednesday: 10 (83%)
- Thursday: 2 (17%)

Consensus day: Wednesday
Agreement ratio: 10/12 = 0.833 (83%)
Verified: Yes (12 >= 3 and 0.833 >= 0.67)
```

## Verification Thresholds

### Required Criteria

Both must be met for **is_verified = true**:

| Criterion | Threshold | Rationale |
|-----------|-----------|-----------|
| Minimum Reports | >=3 | Prevents single-user spoofing |
| Minimum Agreement | >=67% | (2/3 majority) Requires strong consensus |

### Verification States

**VERIFIED** (is_verified = true)
- High confidence
- >=3 reports with >=67% agreement
- Can be used as primary data source
- Displayed prominently to users

**UNVERIFIED** (is_verified = false)
- Lower confidence
- &lt;3 reports OR &lt;67% agreement
- Used as fallback when official data unavailable
- Marked as community data

**NO CONSENSUS**
- No reports submitted
- Address not in consensus table
- Data source = UNKNOWN

## Quality Metrics

### Agreement Ratio

Percentage of reports agreeing with consensus:

```
9 reports agree / 12 total = 0.75 (75% agreement)
```

**Quality mapping**:

| Ratio | Level | Confidence |
|-------|-------|-----------|
| 90-100% | Excellent | Very high |
| 80-89% | Good | High |
| 67-79% | Fair | Acceptable |
| 50-66% | Poor | Low |
| 0-49% | Conflicting | Requires review |

### Conflict Detection

When multiple days have similar report counts:

```
Reports by day:
- Wednesday: 5 (42%)
- Thursday:  6 (50%)
- Friday:    1 (8%)

Status: CONFLICTING
- Threshold: Top days within 2.5x of each other
- 6/5 = 1.2x → Conflict detected
- Needs manual review or more reports
```

## Collection Types

Each type is calculated independently:

### Trash
- Regular garbage collection
- Most common pickup type
- Usually weekly

### Recycling
- Recyclable materials
- Often different day than trash
- Weekly or bi-weekly

### Green Waste
- Yard waste, compostables
- Seasonal in some areas
- Optional in many cities

## Data Source Priority

When returning a lookup result:

```
1. CROWD_VERIFIED
   ├─ >=3 reports
   ├─ >=67% agreement
   └─ Most reliable source

2. OFFICIAL
   ├─ Municipal GIS data
   ├─ City government schedules
   └─ Authoritative but may be outdated

3. CROWD_UNVERIFIED
   ├─ &lt;3 reports OR &lt;67% agreement
   ├─ Lower confidence
   └─ Better than nothing

4. UNKNOWN
   ├─ No data available
   ├─ Community contributions needed
   └─ Prompt user to report
```

## Consensus Recalculation

Consensus is recomputed:

- **After each report**: When new report submitted
- **Scheduled**: Daily/weekly batch updates
- **On-demand**: Via API request
- **Cached**: Results cached for 5 minutes

## Handling Disputes

When reports disagree:

### Single Conflicting Report

```
Reports: WED, WED, WED, THU

Result: Consensus = Wednesday (75%)
Action: Ignore Thursday as outlier
```

### Multiple Conflicts

```
Reports: MON, MON, MON, WED, WED, WED

Result: Conflicting (50/50 split)
Action: Flag for review
        Require more reports
        Manual verification
```

### Schedule Changes

```
Old reports: Wednesday (3 months ago)
New reports: Thursday (recent)

Result: Consensus shifts to Thursday
Action: Update consensus
        Keep old data for history
        Alert users to change
```

## User Contributions

### How Users Contribute

1. **Observe**: Watch when trash is collected
2. **Submit**: Send report via app/web
3. **Validate**: Verify they see their pickup
4. **Consensus Builds**: 3+ reports trigger verification

### Incentivizing Quality

- **Gamification**: Badges for contributors
- **Reputation**: Show contribution history
- **Feedback**: Tell users when their report helped
- **Transparency**: Show consensus and agreement

### Preventing Abuse

- **Rate limiting**: Max reports per IP
- **User hash**: Anonymous but trackable
- **Verification threshold**: Requires agreement
- **Manual review**: Moderators check conflicts

## Consensus Updates

### Incremental Updates

When new report submitted:

```python
# Get existing consensus
old_consensus = get_consensus(address_id)

# Add new report to calculation
new_consensus = recalculate(address_id)

# Check if changed significantly
if changed(old_consensus, new_consensus):
    # Update database
    # Log change
    # Notify interested users (future)
```

### Batch Updates

Scheduled daily batch jobs:

```python
# Recalculate all addresses
for address in all_addresses():
    consensus = calculate_consensus(address)
    if consensus.is_verified:
        update_database(consensus)
```

## Monitoring Data Quality

### Key Metrics

```
- Coverage: % of addresses with consensus
- Verification: % of consensus that's verified
- Agreement: Average agreement ratio
- Report velocity: Reports per address per week
- Conflict rate: % of addresses with conflicts
```

### Example Dashboard

```
Total Addresses: 248
Consensus Count: 156 (62.9% coverage)
Verified: 92 (58.9% of consensus)
Avg Agreement: 78%
Reports This Week: 45
Conflicts: 3 (1.9% of addresses)
```

## Future Enhancements

### Advanced Consensus

- **Time-based**: Different schedules for different seasons
- **Geospatial**: Weighted by proximity
- **Weighted**: User reputation weighting
- **Temporal**: Trend analysis over time

### Community Features

- **Subscriptions**: Get notified of schedule changes
- **Contributions**: Gamified contribution tracking
- **Moderation**: Community moderators
- **Disputes**: Resolution mechanism

### Integration

- **City APIs**: Integrate with official schedules
- **GTFS-RT**: Real-time transit data
- **Weather**: Account for weather delays
- **Holidays**: Automatic adjustment

## Related Documentation

- **[System Architecture](/docs/architecture/overview)** - How it fits in
- **[Database Schema](/docs/architecture/database)** - Data storage
- **[Report Endpoint](/docs/api/endpoints/report)** - How to submit reports
- **[Consensus Model](/docs/api/models/consensus)** - Data structure

