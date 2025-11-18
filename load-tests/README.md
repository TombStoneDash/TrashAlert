# TrashAlert API - Load Test Suite

Comprehensive automated load testing suite for the TrashAlert API, built with k6 for performance validation and benchmarking.

## Overview

This load test suite validates that the TrashAlert API can handle production traffic levels while maintaining acceptable response times and error rates.

### Test Scenarios

The suite includes three load test scenarios:

| Scenario | Requests/Min | RPS | Purpose |
|----------|--------------|-----|---------|
| **5k/min** | 5,000 | 83 | Baseline performance measurement |
| **10k/min** | 10,000 | 167 | Production readiness validation ⭐ |
| **20k/min** | 20,000 | 333 | Stress testing and limit identification |

### Success Criteria (10k/min)

The application must meet the following criteria at 10,000 requests/minute:

- ✅ **Average response time** < 200ms
- ✅ **Error rate** < 5%
- ✅ **Memory usage** stable (no leaks)

## Quick Start

### Prerequisites

1. **k6** - Load testing tool
   ```bash
   # macOS
   brew install k6

   # Ubuntu/Debian
   sudo gpg -k
   sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
   echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
   sudo apt-get update
   sudo apt-get install k6

   # Or download from: https://k6.io/docs/getting-started/installation/
   ```

2. **Docker** (optional, for resource monitoring)
   - Required to track CPU and memory usage during tests

3. **Running TrashAlert API**
   ```bash
   docker-compose up -d
   ```

### Running All Tests

Run the complete test suite (5k, 10k, 20k):

```bash
./load-tests/run-load-tests.sh
```

This will:
1. Run all three load test scenarios
2. Monitor resource usage (CPU, memory)
3. Generate a comprehensive performance report
4. Save detailed metrics to `load-tests/results/`

### Running Individual Tests

#### 5k/min (Baseline)
```bash
TARGET_RPS=83 TEST_DURATION=2m k6 run \
  -e TARGET_RPS=83 \
  -e TEST_DURATION=2m \
  -e BASE_URL=http://localhost \
  load-tests/scripts/load-test.js
```

#### 10k/min (Target Load)
```bash
TARGET_RPS=167 TEST_DURATION=2m k6 run \
  -e TARGET_RPS=167 \
  -e TEST_DURATION=2m \
  -e BASE_URL=http://localhost \
  load-tests/scripts/load-test.js
```

#### 20k/min (Stress Test)
```bash
TARGET_RPS=333 TEST_DURATION=2m k6 run \
  -e TARGET_RPS=333 \
  -e TEST_DURATION=2m \
  -e BASE_URL=http://localhost \
  load-tests/scripts/load-test.js
```

## Test Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TARGET_RPS` | 83 | Target requests per second |
| `TEST_DURATION` | 2m | Duration of sustained load phase |
| `BASE_URL` | http://localhost | API base URL |
| `AUTO_RUN` | false | Skip confirmation prompt |

### Example: Custom Test
```bash
# Test at custom load for 5 minutes
TARGET_RPS=200 TEST_DURATION=5m BASE_URL=http://api.example.com k6 run \
  -e TARGET_RPS=200 \
  -e TEST_DURATION=5m \
  -e BASE_URL=http://api.example.com \
  load-tests/scripts/load-test.js
```

## Traffic Simulation

The load tests simulate realistic production traffic patterns:

### Endpoint Distribution

- **70%** - GET /lookup (address and coordinate lookups)
- **15%** - POST /report (crowdsourced reports)
- **10%** - GET /stats (statistics)
- **5%** - POST /interpret-address (AI interpretation)

### Request Patterns

**GET /lookup (70% of traffic)**
- 60% address-based: `?address=123 Main St, San Diego, CA`
- 30% coordinate-based: `?lat=32.71&lon=-117.16&city_id=ca_san_diego`
- 10% coordinate-only: `?lat=32.71&lon=-117.16`

**POST /report (15% of traffic)**
```json
{
  "address": "123 Main St, San Diego, CA",
  "trash_day": "WED",
  "recycling_day": "FRI",
  "green_day": null,
  "user_hash": "loadtest-xyz123"
}
```

**GET /stats (10% of traffic)**
- Simple endpoint: `GET /stats`

**POST /interpret-address (5% of traffic)**
```json
{
  "text": "i live at 123 main street in san diego",
  "use_geocoding": true
}
```

## Metrics Collected

### Response Time Metrics
- **Average** - Mean response time
- **P50** - Median (50th percentile)
- **P95** - 95th percentile
- **P99** - 99th percentile
- **Max** - Maximum response time

### Throughput Metrics
- **Total Requests** - Total number of requests
- **Actual RPS** - Achieved requests per second
- **Request Duration** - Time to complete requests

### Error Metrics
- **Error Rate** - Percentage of failed requests
- **Failed Requests** - Count of failed requests
- **HTTP Status Codes** - Distribution of response codes

### Resource Metrics (Docker)
- **CPU Usage** - Average and peak CPU %
- **Memory Usage** - Average and peak memory (MB)
- **Memory %** - Memory usage as % of limit
- **Network I/O** - RX/TX bytes
- **Block I/O** - Read/write bytes

## Results and Reports

### Output Files

After running tests, results are saved to `load-tests/results/`:

```
load-tests/results/
├── 5k_YYYYMMDD_HHMMSS_k6_output.txt      # Full k6 output
├── 5k_YYYYMMDD_HHMMSS_summary.json        # Structured summary
├── 5k_YYYYMMDD_HHMMSS_resources.csv       # Resource metrics
├── 5k_YYYYMMDD_HHMMSS_metrics.json        # Raw k6 metrics
├── 10k_YYYYMMDD_HHMMSS_k6_output.txt
├── 10k_YYYYMMDD_HHMMSS_summary.json
├── 10k_YYYYMMDD_HHMMSS_resources.csv
├── 10k_YYYYMMDD_HHMMSS_metrics.json
├── 20k_YYYYMMDD_HHMMSS_k6_output.txt
├── 20k_YYYYMMDD_HHMMSS_summary.json
├── 20k_YYYYMMDD_HHMMSS_resources.csv
├── 20k_YYYYMMDD_HHMMSS_metrics.json
└── performance_report.md                   # Comprehensive report
```

### Performance Report

The `performance_report.md` includes:

- ✅ Success criteria validation
- 📊 Response time analysis
- 📈 Throughput metrics
- 🔴 Error rate trends
- 💾 Resource utilization
- 🎯 Bottleneck identification
- 💡 Optimization recommendations

View the report:
```bash
cat load-tests/results/performance_report.md
```

Or open in your favorite markdown viewer.

## Resource Monitoring

### Manual Monitoring

Run the resource monitor separately:

```bash
./load-tests/scripts/monitor-resources.sh [output_file] [interval]
```

Example:
```bash
# Sample every 2 seconds
./load-tests/scripts/monitor-resources.sh ./my-results.csv 2
```

Press `Ctrl+C` to stop and view summary statistics.

### Docker Container Detection

The monitoring script automatically detects TrashAlert containers. If multiple containers are running, it will use the first match for `trashalert*`.

To monitor a specific container:
```bash
# Edit the script and set CONTAINER_NAME
CONTAINER_NAME="trashalert-api-1" ./load-tests/scripts/monitor-resources.sh
```

## Interpreting Results

### Success Indicators ✅

**10k/min test passes if:**
- Average response time < 200ms
- P95 response time < 500ms
- Error rate < 5%
- No memory leaks (stable usage)
- CPU < 90% sustained

### Warning Signs ⚠️

Look for these issues:
- Increasing response times over test duration
- Error rate climbing during sustained load
- Memory usage growing continuously
- CPU at or near 100%
- High P99 latency (>1000ms)

### Bottleneck Identification

**High Response Times**
- Check database query performance
- Review consensus calculation efficiency
- Consider caching frequently accessed data

**High Error Rates**
- Check rate limiting configuration
- Review application logs for exceptions
- Verify database connection pool size

**Memory Issues**
- Check for memory leaks in application code
- Review caching strategy and TTLs
- Monitor database connection handling

**CPU Bottlenecks**
- Profile CPU-intensive operations
- Consider horizontal scaling
- Optimize hot code paths

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Load Tests

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 2 * * 1'  # Weekly on Monday at 2 AM

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install k6
        run: |
          sudo gpg -k
          sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
          echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
          sudo apt-get update
          sudo apt-get install k6

      - name: Start TrashAlert API
        run: docker-compose up -d

      - name: Wait for API
        run: |
          timeout 60 bash -c 'until curl -f http://localhost/; do sleep 2; done'

      - name: Run load tests
        run: AUTO_RUN=true ./load-tests/run-load-tests.sh

      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: load-test-results
          path: load-tests/results/

      - name: Check success criteria
        run: |
          # Parse performance_report.md for success/failure
          if grep -q "SUCCESS! All criteria met" load-tests/results/performance_report.md; then
            echo "✅ Load tests passed"
            exit 0
          else
            echo "❌ Load tests failed"
            exit 1
          fi
```

## Troubleshooting

### k6 Not Found
```bash
# Install k6
brew install k6  # macOS
# or follow installation instructions above
```

### API Not Reachable
```bash
# Check if API is running
docker-compose ps

# Start API
docker-compose up -d

# Check logs
docker-compose logs -f api
```

### Rate Limiting Issues

The TrashAlert API has rate limits (60 req/min per IP). To bypass during load testing:

1. **Use multiple source IPs** (not recommended for local testing)
2. **Temporarily increase limits** in `app/rate_limiter.py`:
   ```python
   RATE_LIMIT_PER_MINUTE = 1000  # Temporarily increased
   RATE_LIMIT_PER_HOUR = 10000   # Temporarily increased
   ```
3. **Disable rate limiting** for testing (not recommended for production)

### Docker Monitoring Not Working

If resource monitoring fails:
```bash
# Check Docker is running
docker ps

# Find your container name
docker ps --format 'table {{.Names}}\t{{.Status}}'

# Update monitor script with correct container name
CONTAINER_NAME="your-container-name" ./load-tests/scripts/monitor-resources.sh
```

## Advanced Usage

### Custom Load Profile

Edit `load-tests/scripts/load-test.js` to customize:

```javascript
// Modify traffic distribution
if (scenario < 0.80) {
  // 80% lookups instead of 70%
  testLookup(params);
}

// Add custom endpoints
function testMyEndpoint(params) {
  const response = http.get(`${BASE_URL}/my-endpoint`, params);
  // ... checks
}

// Modify ramp-up pattern
stages: [
  { duration: '1m', target: 50 },   // Slow ramp-up
  { duration: '5m', target: 100 },  // Extended test
  { duration: '1m', target: 0 },    // Ramp down
]
```

### Custom Metrics

Add custom metrics to track specific behaviors:

```javascript
import { Trend } from 'k6/metrics';

const myCustomMetric = new Trend('custom_metric');

export default function() {
  const start = new Date().getTime();
  // ... operation
  const duration = new Date().getTime() - start;
  myCustomMetric.add(duration);
}
```

### Distributed Load Testing

For testing beyond single-machine capacity:

```bash
# Run k6 in cloud mode (requires k6 cloud account)
k6 cloud load-tests/scripts/load-test.js

# Or use k6 operator on Kubernetes
kubectl apply -f k6-load-test.yaml
```

## Best Practices

### Before Testing

1. ✅ **Ensure clean state** - Clear caches, restart services
2. ✅ **Stable environment** - No ongoing deployments
3. ✅ **Baseline metrics** - Know normal resource usage
4. ✅ **Monitoring ready** - Set up logging/monitoring

### During Testing

1. 📊 **Monitor in real-time** - Watch for anomalies
2. 🔍 **Check application logs** - Look for errors
3. 💾 **Watch resource usage** - Ensure headroom
4. 📈 **Verify test execution** - Confirm target RPS achieved

### After Testing

1. 📝 **Document results** - Save reports and artifacts
2. 🔬 **Analyze bottlenecks** - Identify optimization opportunities
3. 🎯 **Set baselines** - Track improvements over time
4. 🔄 **Iterate** - Test after each optimization

## Contributing

To improve the load test suite:

1. **Add test scenarios** - New endpoints or patterns
2. **Enhance metrics** - Additional measurements
3. **Improve reporting** - Better visualizations
4. **Update documentation** - Keep README current

## Support

For issues or questions:

1. Check this README first
2. Review k6 documentation: https://k6.io/docs/
3. Check TrashAlert API documentation
4. Open an issue in the repository

## License

This load test suite is part of the TrashAlert project.

---

**Happy Load Testing! 🚀**
