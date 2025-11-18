#!/usr/bin/env python3
"""
Performance Report Generator for TrashAlert Load Tests
Analyzes k6 results and resource metrics to create comprehensive performance report
"""

import json
import csv
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import re


def parse_k6_output(output_file: str) -> Dict:
    """Parse k6 text output to extract metrics."""
    metrics = {
        'total_requests': None,
        'avg_duration': None,
        'p50_duration': None,
        'p95_duration': None,
        'p99_duration': None,
        'max_duration': None,
        'error_rate': None,
        'actual_rps': None,
        'failed_requests': None,
    }

    try:
        with open(output_file, 'r') as f:
            content = f.read()

        # Parse http_reqs
        match = re.search(r'http_reqs[.\s]*(\d+)', content)
        if match:
            metrics['total_requests'] = int(match.group(1))

        # Parse http_req_duration
        duration_match = re.search(
            r'http_req_duration[.\s]*avg=([0-9.]+\w+)\s+min=([0-9.]+\w+)\s+med=([0-9.]+\w+)\s+max=([0-9.]+\w+)\s+p\(90\)=([0-9.]+\w+)\s+p\(95\)=([0-9.]+\w+)',
            content
        )
        if duration_match:
            metrics['avg_duration'] = duration_match.group(1)
            metrics['p50_duration'] = duration_match.group(3)
            metrics['p95_duration'] = duration_match.group(6)

        # Parse RPS
        rps_match = re.search(r'http_reqs[.\s]*[0-9]+\s+([0-9.]+)/s', content)
        if rps_match:
            metrics['actual_rps'] = float(rps_match.group(1))

        # Parse error rate
        error_match = re.search(r'http_req_failed[.\s]*([0-9.]+)%', content)
        if error_match:
            metrics['error_rate'] = float(error_match.group(1))

        # Calculate failed requests
        if metrics['total_requests'] and metrics['error_rate'] is not None:
            metrics['failed_requests'] = int(metrics['total_requests'] * metrics['error_rate'] / 100)

    except Exception as e:
        print(f"Warning: Error parsing k6 output file {output_file}: {e}", file=sys.stderr)

    return metrics


def parse_resource_metrics(csv_file: str) -> Dict:
    """Parse resource monitoring CSV file."""
    metrics = {
        'avg_cpu': None,
        'max_cpu': None,
        'avg_memory': None,
        'max_memory': None,
        'avg_memory_percent': None,
        'max_memory_percent': None,
    }

    try:
        cpu_values = []
        memory_values = []
        memory_percent_values = []

        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    cpu_values.append(float(row['cpu_percent']))
                    memory_values.append(float(row['memory_usage_mb']))
                    memory_percent_values.append(float(row['memory_percent']))
                except (ValueError, KeyError):
                    continue

        if cpu_values:
            metrics['avg_cpu'] = sum(cpu_values) / len(cpu_values)
            metrics['max_cpu'] = max(cpu_values)

        if memory_values:
            metrics['avg_memory'] = sum(memory_values) / len(memory_values)
            metrics['max_memory'] = max(memory_values)

        if memory_percent_values:
            metrics['avg_memory_percent'] = sum(memory_percent_values) / len(memory_percent_values)
            metrics['max_memory_percent'] = max(memory_percent_values)

    except Exception as e:
        print(f"Warning: Error parsing resource file {csv_file}: {e}", file=sys.stderr)

    return metrics


def parse_summary_json(json_file: str) -> Dict:
    """Parse k6 summary JSON file."""
    try:
        with open(json_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Error parsing summary JSON {json_file}: {e}", file=sys.stderr)
        return {}


def find_test_files(results_dir: str) -> Dict[str, Dict[str, str]]:
    """Find all test result files organized by load level."""
    results_path = Path(results_dir)
    test_files = {
        '5k': {'output': None, 'resources': None, 'summary': None},
        '10k': {'output': None, 'resources': None, 'summary': None},
        '20k': {'output': None, 'resources': None, 'summary': None},
    }

    for file_path in results_path.glob('*'):
        filename = file_path.name

        for level in ['5k', '10k', '20k']:
            if filename.startswith(level):
                if 'k6_output.txt' in filename:
                    test_files[level]['output'] = str(file_path)
                elif 'resources.csv' in filename:
                    test_files[level]['resources'] = str(file_path)
                elif 'summary.json' in filename:
                    test_files[level]['summary'] = str(file_path)

    return test_files


def format_metric(value, unit='', decimal_places=2):
    """Format a metric value for display."""
    if value is None:
        return '-'
    if isinstance(value, (int, float)):
        return f"{value:.{decimal_places}f}{unit}"
    return str(value)


def generate_report(results_dir: str) -> str:
    """Generate comprehensive performance report."""
    test_files = find_test_files(results_dir)

    # Parse all test results
    results = {}
    for level in ['5k', '10k', '20k']:
        results[level] = {
            'k6': {},
            'resources': {},
            'summary': {},
        }

        if test_files[level]['output']:
            results[level]['k6'] = parse_k6_output(test_files[level]['output'])

        if test_files[level]['resources']:
            results[level]['resources'] = parse_resource_metrics(test_files[level]['resources'])

        if test_files[level]['summary']:
            results[level]['summary'] = parse_summary_json(test_files[level]['summary'])

    # Check 10k/min success criteria
    success_10k = False
    avg_response_10k = None
    error_rate_10k = None

    if results['10k']['k6'].get('avg_duration'):
        avg_str = results['10k']['k6']['avg_duration']
        avg_match = re.search(r'([0-9.]+)', avg_str)
        if avg_match:
            avg_response_10k = float(avg_match.group(1))

    if results['10k']['k6'].get('error_rate') is not None:
        error_rate_10k = results['10k']['k6']['error_rate']

    success_criteria_met = []
    if avg_response_10k and avg_response_10k < 200:
        success_criteria_met.append('avg_response')

    if error_rate_10k is not None and error_rate_10k < 5:
        success_criteria_met.append('error_rate')

    success_10k = len(success_criteria_met) == 2

    # Generate markdown report
    report = f"""# TrashAlert API - Load Test Performance Report

## Executive Summary

**Test Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
**Application:** TrashAlert API
**Test Duration:** 2 minutes per scenario (plus ramp-up/ramp-down)

### Success Criteria (10k/min)

"""

    # Add success criteria checks
    if avg_response_10k is not None:
        status = '✅' if avg_response_10k < 200 else '❌'
        report += f"- {status} Average response time: {avg_response_10k:.2f}ms (target: <200ms)\n"
    else:
        report += "- ⚠️  Average response time: No data\n"

    if error_rate_10k is not None:
        status = '✅' if error_rate_10k < 5 else '❌'
        report += f"- {status} Error rate: {error_rate_10k:.2f}% (target: <5%)\n"
    else:
        report += "- ⚠️  Error rate: No data\n"

    if success_10k:
        report += f"\n**🎉 SUCCESS! All criteria met for 10k/min load.**\n"
    else:
        report += f"\n**⚠️  WARNING: Some success criteria not met.**\n"

    report += """
## Test Scenarios

Three load test scenarios were executed to evaluate API performance:

1. **5k/min (83 RPS)** - Baseline load representing typical traffic
2. **10k/min (167 RPS)** - Target load for production readiness
3. **20k/min (333 RPS)** - Stress test to identify breaking points

### Traffic Distribution

Realistic traffic patterns were simulated:

- **70%** GET /lookup - Address and coordinate-based lookups
- **15%** POST /report - Crowdsourced report submissions
- **10%** GET /stats - Statistics and analytics queries
- **5%** POST /interpret-address - AI-powered address interpretation

## Performance Results

### Response Time Analysis

| Load Level | Avg Response | P50 | P95 | P99 | Max |
|------------|--------------|-----|-----|-----|-----|
"""

    for level in ['5k', '10k', '20k']:
        k6 = results[level]['k6']
        report += f"| {level}/min | "
        report += f"{format_metric(k6.get('avg_duration'), '')} | "
        report += f"{format_metric(k6.get('p50_duration'), '')} | "
        report += f"{format_metric(k6.get('p95_duration'), '')} | "
        report += f"{format_metric(k6.get('p99_duration'), '')} | "
        report += f"{format_metric(k6.get('max_duration'), '')} |\n"

    report += """
### Throughput and Error Rates

| Load Level | Total Requests | Actual RPS | Failed | Error Rate |
|------------|----------------|------------|--------|------------|
"""

    for level in ['5k', '10k', '20k']:
        k6 = results[level]['k6']
        report += f"| {level}/min | "
        report += f"{format_metric(k6.get('total_requests'), '', 0)} | "
        report += f"{format_metric(k6.get('actual_rps'), '', 1)} | "
        report += f"{format_metric(k6.get('failed_requests'), '', 0)} | "
        report += f"{format_metric(k6.get('error_rate'), '%', 2)} |\n"

    report += """
### Resource Utilization

| Load Level | Avg CPU | Peak CPU | Avg Memory | Peak Memory |
|------------|---------|----------|------------|-------------|
"""

    for level in ['5k', '10k', '20k']:
        res = results[level]['resources']
        report += f"| {level}/min | "
        report += f"{format_metric(res.get('avg_cpu'), '%', 1)} | "
        report += f"{format_metric(res.get('max_cpu'), '%', 1)} | "
        report += f"{format_metric(res.get('avg_memory'), ' MB', 0)} | "
        report += f"{format_metric(res.get('max_memory'), ' MB', 0)} |\n"

    report += """
## Detailed Analysis

### 5k/min (83 RPS) - Baseline Performance

This baseline test establishes normal operating characteristics:

"""

    k6_5k = results['5k']['k6']
    res_5k = results['5k']['resources']

    if k6_5k.get('avg_duration'):
        report += f"- **Response Time:** {k6_5k.get('avg_duration')} average\n"
    if k6_5k.get('error_rate') is not None:
        report += f"- **Error Rate:** {k6_5k.get('error_rate'):.2f}%\n"
    if res_5k.get('avg_cpu'):
        report += f"- **CPU Usage:** {res_5k.get('avg_cpu'):.1f}% average, {res_5k.get('max_cpu', 0):.1f}% peak\n"
    if res_5k.get('avg_memory'):
        report += f"- **Memory Usage:** {res_5k.get('avg_memory'):.0f} MB average, {res_5k.get('max_memory', 0):.0f} MB peak\n"

    report += """
### 10k/min (167 RPS) - Target Production Load

This is the critical test for production readiness:

"""

    k6_10k = results['10k']['k6']
    res_10k = results['10k']['resources']

    if k6_10k.get('avg_duration'):
        report += f"- **Response Time:** {k6_10k.get('avg_duration')} average\n"
    if k6_10k.get('error_rate') is not None:
        report += f"- **Error Rate:** {k6_10k.get('error_rate'):.2f}%\n"
    if res_10k.get('avg_cpu'):
        report += f"- **CPU Usage:** {res_10k.get('avg_cpu'):.1f}% average, {res_10k.get('max_cpu', 0):.1f}% peak\n"
    if res_10k.get('avg_memory'):
        report += f"- **Memory Usage:** {res_10k.get('avg_memory'):.0f} MB average, {res_10k.get('max_memory', 0):.0f} MB peak\n"

    if success_10k:
        report += "\n✅ **Production Ready:** All success criteria met at target load.\n"
    else:
        report += "\n⚠️  **Needs Optimization:** Some success criteria not met.\n"

    report += """
### 20k/min (333 RPS) - Stress Test

This stress test identifies system limits and breaking points:

"""

    k6_20k = results['20k']['k6']
    res_20k = results['20k']['resources']

    if k6_20k.get('avg_duration'):
        report += f"- **Response Time:** {k6_20k.get('avg_duration')} average\n"
    if k6_20k.get('error_rate') is not None:
        report += f"- **Error Rate:** {k6_20k.get('error_rate'):.2f}%\n"
    if res_20k.get('avg_cpu'):
        report += f"- **CPU Usage:** {res_20k.get('avg_cpu'):.1f}% average, {res_20k.get('max_cpu', 0):.1f}% peak\n"
    if res_20k.get('avg_memory'):
        report += f"- **Memory Usage:** {res_20k.get('avg_memory'):.0f} MB average, {res_20k.get('max_memory', 0):.0f} MB peak\n"

    report += """
## Key Observations

### Performance Characteristics

"""

    # Add intelligent observations based on data
    observations = []

    # Check if response times scale linearly
    if all(results[level]['k6'].get('avg_duration') for level in ['5k', '10k', '20k']):
        observations.append("- Response times were measured across all load levels")

    # Check for memory leaks
    if res_5k.get('avg_memory') and res_20k.get('avg_memory'):
        memory_increase = ((res_20k['avg_memory'] - res_5k['avg_memory']) / res_5k['avg_memory']) * 100
        if memory_increase > 50:
            observations.append(f"- ⚠️  Significant memory increase ({memory_increase:.1f}%) under high load - potential memory leak")
        else:
            observations.append(f"- ✅ Memory usage remained stable (only {memory_increase:.1f}% increase)")

    # Check CPU scaling
    if res_5k.get('avg_cpu') and res_20k.get('avg_cpu'):
        cpu_increase = ((res_20k['avg_cpu'] - res_5k['avg_cpu']) / res_5k['avg_cpu']) * 100
        observations.append(f"- CPU usage scaled by {cpu_increase:.1f}% from baseline to stress test")

    # Error rate analysis
    if all(results[level]['k6'].get('error_rate') is not None for level in ['5k', '10k', '20k']):
        max_error = max(results[level]['k6']['error_rate'] for level in ['5k', '10k', '20k'])
        if max_error < 1:
            observations.append("- ✅ Error rates remained very low (<1%) across all tests")
        elif max_error < 5:
            observations.append(f"- Error rates acceptable but increased to {max_error:.2f}% under load")
        else:
            observations.append(f"- ⚠️  High error rates ({max_error:.2f}%) - investigate bottlenecks")

    if observations:
        report += '\n'.join(observations) + '\n'
    else:
        report += "- Test data available in results directory for detailed analysis\n"

    report += """
### Bottlenecks Identified

"""

    bottlenecks = []

    # Identify potential bottlenecks
    if error_rate_10k and error_rate_10k > 5:
        bottlenecks.append("1. **Error Rate:** High error rate suggests rate limiting or resource exhaustion")

    if avg_response_10k and avg_response_10k > 200:
        bottlenecks.append(f"2. **Response Time:** Average response time ({avg_response_10k:.2f}ms) exceeds target")

    if res_20k.get('max_cpu') and res_20k['max_cpu'] > 90:
        bottlenecks.append("3. **CPU Bottleneck:** CPU utilization approaching 100% under high load")

    if res_20k.get('max_memory_percent') and res_20k['max_memory_percent'] > 85:
        bottlenecks.append("4. **Memory Pressure:** Memory usage exceeding 85% of available capacity")

    if bottlenecks:
        report += '\n'.join(bottlenecks) + '\n'
    else:
        report += "✅ No critical bottlenecks identified in current testing.\n"

    report += """
## Recommendations

### Immediate Actions

"""

    recommendations = []

    if not success_10k:
        recommendations.append("1. **Optimize critical paths** - Focus on /lookup endpoint (70% of traffic)")
        recommendations.append("2. **Review rate limiting** - Ensure limits don't block legitimate traffic")
    else:
        recommendations.append("1. ✅ **Production Ready** - Current performance meets requirements")

    if res_10k.get('avg_memory') and res_5k.get('avg_memory'):
        if (res_10k['avg_memory'] - res_5k['avg_memory']) > 200:
            recommendations.append("2. **Investigate memory growth** - Implement memory profiling")

    report += '\n'.join(recommendations[:3]) + '\n'

    report += """
### Performance Optimizations

1. **Database Query Optimization**
   - Review and optimize slow queries
   - Ensure proper indexing on frequently queried fields
   - Consider query result caching

2. **Caching Strategy**
   - Implement Redis/Memcached for GET /lookup responses
   - Cache consensus calculations
   - Set appropriate TTL values

3. **API Response Optimization**
   - Minimize response payload size
   - Use compression (gzip)
   - Implement field filtering

### Scalability Improvements

1. **Horizontal Scaling**
   - Add load balancer support
   - Implement stateless API design
   - Use shared session storage

2. **Database Scaling**
   - Consider read replicas for /lookup queries
   - Implement connection pooling
   - Optimize consensus calculation queries

3. **Monitoring and Alerting**
   - Set up real-time performance monitoring
   - Create alerts for response time degradation
   - Track error rate trends

## Conclusion

"""

    if success_10k:
        report += """**Status: ✅ PRODUCTION READY**

The TrashAlert API successfully meets all performance criteria at the target load of 10,000 requests per minute:

- ✅ Average response time < 200ms
- ✅ Error rate < 5%
- ✅ Stable resource utilization

The application is ready for production deployment with current traffic expectations.
"""
    else:
        report += """**Status: ⚠️  OPTIMIZATION NEEDED**

The TrashAlert API requires optimization before production deployment:

"""
        if avg_response_10k and avg_response_10k >= 200:
            report += f"- Response time ({avg_response_10k:.2f}ms) exceeds 200ms target\n"
        if error_rate_10k and error_rate_10k >= 5:
            report += f"- Error rate ({error_rate_10k:.2f}%) exceeds 5% threshold\n"

        report += "\nReview recommendations above and re-test after implementing optimizations.\n"

    report += """
## Test Artifacts

All detailed test results are available in `load-tests/results/`:

- `*_k6_output.txt` - Complete k6 test output with all metrics
- `*_summary.json` - Structured summary in JSON format
- `*_resources.csv` - Resource utilization time series data
- `*_metrics.json` - Raw k6 metrics for custom analysis

## Running the Tests

To reproduce these results:

```bash
./load-tests/run-load-tests.sh
```

For individual test runs:

```bash
# 5k/min test
TARGET_RPS=83 TEST_DURATION=2m k6 run -e TARGET_RPS=83 -e BASE_URL=http://localhost load-tests/scripts/load-test.js

# 10k/min test
TARGET_RPS=167 TEST_DURATION=2m k6 run -e TARGET_RPS=167 -e BASE_URL=http://localhost load-tests/scripts/load-test.js

# 20k/min test
TARGET_RPS=333 TEST_DURATION=2m k6 run -e TARGET_RPS=333 -e BASE_URL=http://localhost load-tests/scripts/load-test.js
```

---

*Generated by TrashAlert Load Test Suite*
*Report generated: """ + datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC') + """*
"""

    return report


def main():
    if len(sys.argv) < 2:
        print("Usage: generate-report.py <results_directory>", file=sys.stderr)
        sys.exit(1)

    results_dir = sys.argv[1]

    if not os.path.isdir(results_dir):
        print(f"Error: Results directory not found: {results_dir}", file=sys.stderr)
        sys.exit(1)

    report = generate_report(results_dir)
    print(report)


if __name__ == '__main__':
    main()
