import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const lookupLatency = new Trend('lookup_latency');
const reportLatency = new Trend('report_latency');
const interpretLatency = new Trend('interpret_latency');
const statsLatency = new Trend('stats_latency');
const healthLatency = new Trend('health_latency');
const requestCount = new Counter('total_requests');

// Test configuration - can be overridden via environment variables
const TARGET_RPS = __ENV.TARGET_RPS || '83'; // 5000 requests per minute = 83.33 RPS
const TEST_DURATION = __ENV.TEST_DURATION || '2m';
const BASE_URL = __ENV.BASE_URL || 'http://localhost';

// Sample data for testing
const addresses = [
  '1122 Palmview Ave, El Centro, CA',
  '123 Main St, San Diego, CA',
  '456 Oak Ave, El Centro, CA',
  '789 Pine St, Calexico, CA',
  '321 Elm Ave, Brawley, CA',
  '654 Maple Dr, Imperial, CA',
  '987 Cedar Ln, Holtville, CA',
  '147 Birch St, San Diego, CA',
  '258 Spruce Ave, El Centro, CA',
  '369 Willow Way, Calexico, CA',
];

const coordinates = [
  { lat: 32.792, lon: -115.563, city_id: 'ca_el_centro' },
  { lat: 32.7157, lon: -117.1611, city_id: 'ca_san_diego' },
  { lat: 32.6789, lon: -115.4989, city_id: 'ca_calexico' },
  { lat: 32.9789, lon: -115.5283, city_id: 'ca_brawley' },
  { lat: 32.8473, lon: -115.5694, city_id: 'ca_imperial' },
];

const days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];

const interpretTexts = [
  'i live at 123 main street in san diego',
  'my address is 456 oak avenue el centro california',
  '789 pine st calexico ca 92231',
  'we are located at 321 elm in brawley',
  'find me at 654 maple drive imperial ca',
];

// Test options - uses ramping VUs to achieve target RPS
export const options = {
  scenarios: {
    realistic_load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: Math.ceil(parseFloat(TARGET_RPS) / 2) }, // Ramp up to 50%
        { duration: '30s', target: parseFloat(TARGET_RPS) }, // Ramp up to 100%
        { duration: TEST_DURATION, target: parseFloat(TARGET_RPS) }, // Sustain load
        { duration: '30s', target: 0 }, // Ramp down
      ],
    },
  },
  thresholds: {
    // Success criteria: <200ms average response time for 95% of requests
    'http_req_duration': ['p(95)<200', 'p(99)<500'],
    'lookup_latency': ['p(95)<200'],
    'report_latency': ['p(95)<300'],
    'health_latency': ['p(95)<50'],
    'errors': ['rate<0.05'], // Less than 5% error rate
    'http_req_failed': ['rate<0.05'],
  },
};

// Helper function to get random element from array
function randomChoice(array) {
  return array[Math.floor(Math.random() * array.length)];
}

// Main test scenario
export default function () {
  const params = {
    headers: {
      'Content-Type': 'application/json',
    },
    tags: { name: 'TrashAlert API' },
  };

  // Simulate realistic traffic distribution
  const scenario = Math.random();

  if (scenario < 0.70) {
    // 70% - Address Lookup (GET /lookup)
    testLookup(params);
  } else if (scenario < 0.85) {
    // 15% - Report Submission (POST /report)
    testReport(params);
  } else if (scenario < 0.95) {
    // 10% - Stats (GET /stats)
    testStats(params);
  } else {
    // 5% - Address Interpretation (POST /interpret-address)
    testInterpret(params);
  }

  // Add slight random delay to simulate real user behavior
  sleep(Math.random() * 0.5 + 0.3); // 0.3-0.8 seconds
}

function testLookup(params) {
  const choice = Math.random();
  let url;

  if (choice < 0.6) {
    // 60% - Address-based lookup
    const address = randomChoice(addresses);
    url = `${BASE_URL}/lookup?address=${encodeURIComponent(address)}`;
  } else if (choice < 0.9) {
    // 30% - Coordinate-based lookup
    const coord = randomChoice(coordinates);
    url = `${BASE_URL}/lookup?lat=${coord.lat}&lon=${coord.lon}&city_id=${coord.city_id}`;
  } else {
    // 10% - Coordinate-only lookup
    const coord = randomChoice(coordinates);
    url = `${BASE_URL}/lookup?lat=${coord.lat}&lon=${coord.lon}`;
  }

  const startTime = new Date().getTime();
  const response = http.get(url, params);
  const duration = new Date().getTime() - startTime;

  requestCount.add(1);
  lookupLatency.add(duration);

  const success = check(response, {
    'lookup status is 200': (r) => r.status === 200,
    'lookup has matched_address': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.matched_address !== undefined;
      } catch (e) {
        return false;
      }
    },
  });

  if (!success || response.status >= 400) {
    errorRate.add(1);
  } else {
    errorRate.add(0);
  }
}

function testReport(params) {
  const address = randomChoice(addresses);
  const payload = {
    address: address,
    trash_day: randomChoice(days),
    recycling_day: randomChoice(days),
    green_day: Math.random() > 0.5 ? randomChoice(days) : null,
    user_hash: `loadtest-${Math.random().toString(36).substring(7)}`,
  };

  const startTime = new Date().getTime();
  const response = http.post(`${BASE_URL}/report`, JSON.stringify(payload), params);
  const duration = new Date().getTime() - startTime;

  requestCount.add(1);
  reportLatency.add(duration);

  const success = check(response, {
    'report status is 200': (r) => r.status === 200,
    'report has success flag': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.success === true;
      } catch (e) {
        return false;
      }
    },
  });

  if (!success || response.status >= 400) {
    errorRate.add(1);
  } else {
    errorRate.add(0);
  }
}

function testStats(params) {
  const startTime = new Date().getTime();
  const response = http.get(`${BASE_URL}/stats`, params);
  const duration = new Date().getTime() - startTime;

  requestCount.add(1);
  statsLatency.add(duration);

  const success = check(response, {
    'stats status is 200': (r) => r.status === 200,
    'stats has total_addresses': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.total_addresses !== undefined;
      } catch (e) {
        return false;
      }
    },
  });

  if (!success || response.status >= 400) {
    errorRate.add(1);
  } else {
    errorRate.add(0);
  }
}

function testInterpret(params) {
  const text = randomChoice(interpretTexts);
  const payload = {
    text: text,
    use_geocoding: true,
  };

  const startTime = new Date().getTime();
  const response = http.post(`${BASE_URL}/interpret-address`, JSON.stringify(payload), params);
  const duration = new Date().getTime() - startTime;

  requestCount.add(1);
  interpretLatency.add(duration);

  const success = check(response, {
    'interpret status is 200': (r) => r.status === 200,
    'interpret has success flag': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.success !== undefined;
      } catch (e) {
        return false;
      }
    },
  });

  if (!success || response.status >= 400) {
    errorRate.add(1);
  } else {
    errorRate.add(0);
  }
}

// Health check test (run separately)
export function healthCheck() {
  const startTime = new Date().getTime();
  const response = http.get(`${BASE_URL}/`);
  const duration = new Date().getTime() - startTime;

  healthLatency.add(duration);

  check(response, {
    'health check status is 200': (r) => r.status === 200,
    'health check response time < 50ms': () => duration < 50,
  });
}

// Teardown function to print summary
export function handleSummary(data) {
  const summary = {
    timestamp: new Date().toISOString(),
    test_duration: data.metrics.http_req_duration ? `${data.state.testRunDurationMs / 1000}s` : 'N/A',
    target_rps: TARGET_RPS,
    total_requests: data.metrics.total_requests ? data.metrics.total_requests.values.count : 0,

    // HTTP metrics
    http_req_duration: {
      avg: data.metrics.http_req_duration ? data.metrics.http_req_duration.values.avg.toFixed(2) : 'N/A',
      p50: data.metrics.http_req_duration ? data.metrics.http_req_duration.values['p(50)'].toFixed(2) : 'N/A',
      p95: data.metrics.http_req_duration ? data.metrics.http_req_duration.values['p(95)'].toFixed(2) : 'N/A',
      p99: data.metrics.http_req_duration ? data.metrics.http_req_duration.values['p(99)'].toFixed(2) : 'N/A',
      max: data.metrics.http_req_duration ? data.metrics.http_req_duration.values.max.toFixed(2) : 'N/A',
    },

    // Endpoint-specific latency
    lookup_latency: data.metrics.lookup_latency ? {
      avg: data.metrics.lookup_latency.values.avg.toFixed(2),
      p95: data.metrics.lookup_latency.values['p(95)'].toFixed(2),
    } : 'N/A',

    report_latency: data.metrics.report_latency ? {
      avg: data.metrics.report_latency.values.avg.toFixed(2),
      p95: data.metrics.report_latency.values['p(95)'].toFixed(2),
    } : 'N/A',

    interpret_latency: data.metrics.interpret_latency ? {
      avg: data.metrics.interpret_latency.values.avg.toFixed(2),
      p95: data.metrics.interpret_latency.values['p(95)'].toFixed(2),
    } : 'N/A',

    stats_latency: data.metrics.stats_latency ? {
      avg: data.metrics.stats_latency.values.avg.toFixed(2),
      p95: data.metrics.stats_latency.values['p(95)'].toFixed(2),
    } : 'N/A',

    // Error rates
    error_rate: data.metrics.errors ? (data.metrics.errors.values.rate * 100).toFixed(2) + '%' : 'N/A',
    http_req_failed_rate: data.metrics.http_req_failed ? (data.metrics.http_req_failed.values.rate * 100).toFixed(2) + '%' : 'N/A',

    // Throughput
    actual_rps: data.metrics.http_reqs ? (data.metrics.http_reqs.values.rate).toFixed(2) : 'N/A',

    // Checks
    checks_passed: data.metrics.checks ? (data.metrics.checks.values.passes / data.metrics.checks.values.count * 100).toFixed(2) + '%' : 'N/A',
  };

  return {
    'stdout': '\n' + JSON.stringify(summary, null, 2) + '\n',
    'load-tests/results/summary.json': JSON.stringify(summary, null, 2),
  };
}
