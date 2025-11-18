---
sidebar_position: 3
title: Address Sampling Strategy
slug: /pipeline/address-sampling
---

# Address Sampling Strategy

How to select representative address samples while maintaining geographic diversity.

Based on `/home/user/TrashAlert/docs/ADDRESS_SAMPLING_ENGINE.md`.

## Overview

TrashAlert uses stratified sampling to select a representative subset of addresses from each city.

**Goals**:
- Limit database size (50 addresses/city)
- Maintain geographic representation
- Ensure coverage across neighborhoods
- Prevent sampling bias

## Sampling Algorithm

### Step 1: Load Raw Addresses

```python
# Load addresses from OSM collection
raw_addresses = load_csv("addresses_osm_raw.csv")
# Example: El Centro has 500 raw addresses
```

### Step 2: Detect Subdivisions

Group addresses by neighborhood/subdivision:

```python
subdivisions = group_by_subdivision(raw_addresses)

# Results:
# "North": 150 addresses (30%)
# "Central": 200 addresses (40%)
# "South": 150 addresses (30%)
```

### Step 3: Stratified Sampling

Sample proportionally from each subdivision:

```python
target_per_city = 50
samples = {}

for subdivision, addresses in subdivisions.items():
    proportion = len(addresses) / len(raw_addresses)
    target_for_subdivision = target_per_city * proportion

    # Randomly select
    sampled = random.sample(addresses, target_for_subdivision)
    samples[subdivision] = sampled

# Results:
# "North": 15 samples (30% of 50)
# "Central": 20 samples (40% of 50)
# "South": 15 samples (30% of 50)
```

### Step 4: Deduplication

Remove duplicates by coordinate proximity:

```python
def is_duplicate(addr1, addr2, min_distance_meters=50):
    """Check if addresses are too close."""
    distance = haversine(addr1.lat, addr1.lon,
                         addr2.lat, addr2.lon)
    return distance < min_distance_meters

# Filter out nearby duplicates
unique_samples = []
for addr in sampled_addresses:
    if not is_duplicate(addr, unique_samples):
        unique_samples.append(addr)
```

### Step 5: Null Handling

Remove addresses missing critical data:

```python
# Filter out nulls
valid_samples = [a for a in unique_samples
                 if a.lat and a.lon and a.street]
```

## Configuration

### Sampling Limits

In `/config/config.yaml`:

```yaml
processing:
  max_addresses_per_city: 50
  min_distance_between_samples_meters: 50
```

### City-Specific Overrides

For cities with special requirements:

```yaml
cities:
  - city_id: ca_san_diego
    name: San Diego
    sampling:
      max_addresses: 200  # More samples for large city
      stratify_by: "neighborhood"  # Custom stratification
```

## Usage

### Command-line Interface

```bash
# Sample addresses for one city
python scripts/sample_addresses_per_city.py --city-id ca_el_centro

# Sample for all cities
python scripts/sample_addresses_per_city.py --all

# Custom sample count
python scripts/sample_addresses_per_city.py --city-id ca_el_centro --samples 100

# Custom output
python scripts/sample_addresses_per_city.py --output-dir /custom/path
```

### Output

CSV file with sampled addresses:

**File**: `data/processed/addresses_sampled_50_per_city.csv`

```csv
city_id,city_name,house_number,street,lat,lon,subdivision
ca_el_centro,El Centro,1122,Palmview Ave,32.7971,-115.2645,North
ca_el_centro,El Centro,1245,Main Street,32.8001,-115.2650,Central
ca_el_centro,El Centro,567,Broadway,32.7890,-115.2700,South
ca_imperial,Imperial,234,Fourth St,32.8431,-115.4100,Downtown
...
```

## Statistics

### Example Output

```
Address Sampling Report
Generated: 2025-11-18

Cities Processed: 6

El Centro:
- Raw addresses: 500
- Target samples: 50
- North (30%): 15 samples
- Central (40%): 20 samples
- South (30%): 15 samples
- Duplicates removed: 3
- Final count: 47 addresses

Imperial:
- Raw addresses: 380
- Target samples: 50
- East (45%): 22 samples
- West (55%): 28 samples
- Duplicates removed: 1
- Final count: 49 addresses

[Similar for other cities...]

Total across all cities:
- Total raw: 2,843
- Total sampled: 246
- Coverage: 8.6%
- Deduplication rate: 0.8%
```

## Quality Metrics

### Geographic Representation

Verify samples spread across city:

```python
# Calculate sample coverage
bounds = get_city_bounds()
min_lat, max_lat, min_lon, max_lon = bounds

# Divide city into grid cells
cells = create_grid(bounds, rows=5, cols=5)

# Check coverage
coverage = count_cells_with_samples(cells, samples)
print(f"Grid coverage: {coverage}/25 cells ({coverage*4}%)")
```

### Distance Distribution

Check for spatial clustering:

```python
# Calculate distances between samples
distances = []
for i, addr1 in enumerate(samples):
    for addr2 in samples[i+1:]:
        dist = haversine(addr1.lat, addr1.lon,
                         addr2.lat, addr2.lon)
        distances.append(dist)

# Statistics
mean_distance = np.mean(distances)
min_distance = np.min(distances)
max_distance = np.max(distances)

print(f"Distance stats:")
print(f"  Mean: {mean_distance:.0f}m")
print(f"  Min: {min_distance:.0f}m")
print(f"  Max: {max_distance:.0f}m")
```

## Strategies

### Stratification Options

Choose how to divide city:

**1. By Subdivision** (Default)
- Uses neighborhood/subdivision data from OSM
- Best for cities with defined subdivisions
- Most balanced approach

**2. By Geographic Quadrants**
- Divide city into grid cells
- Sample from each cell
- Works even without subdivision data

**3. By Population Density**
- Oversample high-density areas
- Undersample sparse areas
- Matches user distribution

**4. Random Stratification**
- No stratification, purely random
- Simpler but may miss some areas
- Use only as fallback

### Adjusting Sample Size

For different city sizes:

```python
def get_target_sample_size(city_population):
    """Scale sample size by population."""
    if city_population < 50000:
        return 30  # Small cities
    elif city_population < 500000:
        return 50  # Medium cities
    else:
        return 200  # Large cities
```

## Handling Edge Cases

### Cities Without Subdivisions

If city has no subdivision data:

```python
if no_subdivisions_found():
    # Use geographic quadrants
    samples = sample_by_quadrants(raw_addresses, target=50)
```

### Very Small Cities

If fewer addresses than target:

```python
if len(raw_addresses) < target:
    # Include all addresses
    samples = raw_addresses
    logging.warning(f"City has {len(raw_addresses)} < target {target}")
```

### Very Large Cities

If many more addresses than target:

```python
if len(raw_addresses) > target * 10:
    # Increase sample size
    target = max(target, len(raw_addresses) / 20)
    logging.info(f"Increased target to {target}")
```

## Performance

### Speed

Sampling is fast (milliseconds):

```
Processing 500 addresses
├─ Load: 10ms
├─ Group by subdivision: 50ms
├─ Sample: 80ms
├─ Deduplicate: 120ms
├─ Filter nulls: 30ms
└─ Write CSV: 50ms
Total: 340ms
```

### Memory

Efficient memory usage:

```
Raw data (500 addr): ~2MB
Samples (50 addr): ~200KB
Dedup index: ~100KB
Total: ~2.3MB per city
```

## Validation

### Pre-Sampling Checks

```python
# Verify input file
assert file_exists("addresses_osm_raw.csv")
assert file_size > 1000  # Not empty

# Check data quality
for addr in addresses:
    assert addr.lat is not None
    assert addr.lon is not None
    assert addr.street is not None
```

### Post-Sampling Checks

```python
# Verify sample quality
samples = load_samples()

for city, addrs in samples.items():
    # Check count
    assert len(addrs) <= target, f"Too many: {len(addrs)}"

    # Check coverage
    assert is_geographically_diverse(addrs)

    # Check data integrity
    for addr in addrs:
        assert addr.lat and addr.lon
        assert not is_duplicate(addr, addrs)
```

## Integration with Full Pipeline

Sampling is step 2 of the full pipeline:

```bash
python scripts/run_full_pipeline.py --all

# Steps:
1. fetch_addresses_osm.py
2. ✓ sample_addresses_per_city.py (this script)
3. normalize_addresses.py
4. geocode_addresses.py
5. Database ingest + QA
```

## Related Documentation

- **[Data Pipeline Overview](/docs/pipeline/overview)** - Full pipeline
- **[OSM Collection](/docs/pipeline/osm-collection)** - Previous step
- **[Adding Cities](/docs/pipeline/adding-cities)** - Expand coverage

