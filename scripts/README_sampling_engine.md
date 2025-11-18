# Address Sampling Engine - Quick Start

## TL;DR

Generate 50 random addresses per city using OSM:

```bash
python scripts/sample_addresses_engine.py
```

## Quick Examples

```bash
# Sample all cities (50 addresses each)
python scripts/sample_addresses_engine.py

# Sample specific city
python scripts/sample_addresses_engine.py --only "Brawley, California"

# Sample all cities in California
python scripts/sample_addresses_engine.py --state CA

# Generate 100 samples per city
python scripts/sample_addresses_engine.py --samples 100

# Custom output directory
python scripts/sample_addresses_engine.py --output-dir /custom/path
```

## What It Does

1. ✅ Loads city boundary polygons
2. ✅ Generates random points within boundaries
3. ✅ Reverse geocodes to addresses (Nominatim API)
4. ✅ Normalizes to USPS format
5. ✅ Saves results to `data/processed/addresses/{city}.json`

## Output Location

```
data/processed/addresses/
├── brawley.json          # 50 valid addresses
├── el_centro.json        # 50 valid addresses
├── san_diego.json        # 50 valid addresses
└── brawley_failed.json   # Failed lookups (if any)
```

## Success Criteria (from requirements)

✅ **50 valid addresses** per city
✅ **Zero script crashes** (robust error handling)
✅ **Standardized output** (USPS format)
✅ **Rate limiting** (1 req/sec for Nominatim)
✅ **Retry logic** (exponential backoff: 2s, 4s, 8s)
✅ **Caching** (avoids duplicate API calls)
✅ **Failed lookups saved** separately

## Expected Runtime

- **Per city**: ~52 seconds (50 addresses × 1 req/sec + overhead)
- **All 6 cities**: ~5 minutes

## Troubleshooting

### "403 Forbidden" from Nominatim

**Cause**: Nominatim blocks requests without proper identification
**Solution**: Script includes correct User-Agent header. If issue persists, check network/firewall.

### "No boundary found for city"

**Cause**: City boundary not in cache
**Solution**: Manually create `data/cache/{city}_boundary.geojson` with polygon coordinates

### Very few successful addresses

**Cause**: City boundary may include unpopulated areas
**Solution**: Increase `--samples` value or refine boundary polygon

## Full Documentation

See: [docs/ADDRESS_SAMPLING_ENGINE.md](../docs/ADDRESS_SAMPLING_ENGINE.md)

## Support

Report issues: https://github.com/TombStoneDash/TrashAlert/issues
