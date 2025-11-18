# Load Test Quick Start Guide

## Prerequisites

```bash
# Install k6
brew install k6  # macOS
# or see README.md for other platforms

# Start the API
cd /path/to/TrashAlert
docker-compose up -d
```

## Run All Tests (Recommended)

```bash
./load-tests/run-load-tests.sh
```

This will:
- ✅ Run 5k/min baseline test
- ✅ Run 10k/min target test (success criteria)
- ✅ Run 20k/min stress test
- ✅ Monitor CPU and memory
- ✅ Generate performance_report.md

**Duration:** ~8-10 minutes total

## View Results

```bash
# View performance report
cat load-tests/results/performance_report.md

# Or open in browser/editor
code load-tests/results/performance_report.md
```

## Run Individual Tests

### Quick 10k/min Test (1 minute)
```bash
TARGET_RPS=167 TEST_DURATION=1m k6 run \
  -e TARGET_RPS=167 \
  -e TEST_DURATION=1m \
  -e BASE_URL=http://localhost \
  load-tests/scripts/load-test.js
```

### Full 10k/min Test (2 minutes)
```bash
TARGET_RPS=167 TEST_DURATION=2m k6 run \
  -e TARGET_RPS=167 \
  -e TEST_DURATION=2m \
  -e BASE_URL=http://localhost \
  load-tests/scripts/load-test.js
```

## Success Criteria (10k/min)

Your API passes if:
- ✅ Average response time < 200ms
- ✅ Error rate < 5%
- ✅ Memory stable (no leaks)

Look for this in the output:
```
SUCCESS CRITERIA MET! 🎉
```

## Troubleshooting

### API not running
```bash
docker-compose up -d
curl http://localhost/  # Should return {"status":"healthy"}
```

### k6 not installed
```bash
# macOS
brew install k6

# Ubuntu/Debian
curl -s https://dl.k6.io/key.gpg | sudo apt-key add -
echo "deb https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6
```

### Rate limiting
If you see many 429 errors, the API rate limiter may be blocking requests. For load testing:

1. Edit `app/rate_limiter.py`
2. Temporarily increase limits:
   ```python
   RATE_LIMIT_PER_MINUTE = 1000
   RATE_LIMIT_PER_HOUR = 10000
   ```
3. Restart API: `docker-compose restart api`

## What Gets Tested

The load tests simulate realistic traffic:
- 70% - GET /lookup (address lookups)
- 15% - POST /report (submit reports)
- 10% - GET /stats (statistics)
- 5% - POST /interpret-address (AI interpretation)

## Next Steps

1. ✅ Run the full test suite
2. 📊 Review performance_report.md
3. 🔍 Identify bottlenecks
4. ⚡ Optimize based on recommendations
5. 🔄 Re-run tests to validate improvements

For detailed documentation, see [README.md](README.md).

---

**Quick tip:** Use `AUTO_RUN=true ./load-tests/run-load-tests.sh` to skip confirmation prompt.
