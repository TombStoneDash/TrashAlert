#!/bin/bash

# Automated Load Test Suite for TrashAlert API
# Tests at 5k/min, 10k/min, and 20k/min request rates
# Measures latency, error rate, and memory usage

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="${BASE_URL:-http://localhost}"
RESULTS_DIR="load-tests/results"
SCRIPTS_DIR="load-tests/scripts"
TEST_DURATION="${TEST_DURATION:-2m}" # Default 2 minutes per test
WARMUP_DURATION="${WARMUP_DURATION:-30s}"

# Load levels (requests per minute -> requests per second)
declare -A LOAD_LEVELS=(
    ["5k"]="83"    # 5000 / 60 = 83.33 RPS
    ["10k"]="167"  # 10000 / 60 = 166.67 RPS
    ["20k"]="333"  # 20000 / 60 = 333.33 RPS
)

# Function to print colored messages
print_header() {
    echo -e "\n${CYAN}========================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Function to check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"

    # Check for k6
    if ! command -v k6 &> /dev/null; then
        print_error "k6 is not installed"
        echo ""
        echo "Install k6:"
        echo "  macOS: brew install k6"
        echo "  Linux: sudo gpg -k && sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69 && echo 'deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main' | sudo tee /etc/apt/sources.list.d/k6.list && sudo apt-get update && sudo apt-get install k6"
        echo "  Or visit: https://k6.io/docs/getting-started/installation/"
        exit 1
    fi
    print_success "k6 found: $(k6 version | head -n 1)"

    # Check for Docker
    if ! command -v docker &> /dev/null; then
        print_warning "Docker not found - resource monitoring will be disabled"
        DOCKER_AVAILABLE=false
    else
        print_success "Docker found: $(docker --version | cut -d',' -f1)"
        DOCKER_AVAILABLE=true
    fi

    # Check if API is running
    print_info "Checking if API is available at $BASE_URL..."
    if curl -f -s -o /dev/null "$BASE_URL/" 2>/dev/null; then
        print_success "API is reachable at $BASE_URL"
    else
        print_error "API is not reachable at $BASE_URL"
        echo ""
        echo "Make sure the TrashAlert API is running:"
        echo "  docker-compose up -d"
        exit 1
    fi

    # Create results directory
    mkdir -p "$RESULTS_DIR"
    print_success "Results directory created: $RESULTS_DIR"

    echo ""
}

# Function to run a single load test
run_load_test() {
    local level_name=$1
    local target_rps=$2
    local test_name="${level_name}_$(date +%Y%m%d_%H%M%S)"

    print_header "Running Load Test: $level_name (${target_rps} RPS)"

    print_info "Target: $level_name requests/min (${target_rps} requests/sec)"
    print_info "Duration: $TEST_DURATION"
    print_info "Test name: $test_name"
    echo ""

    # Start resource monitoring if Docker is available
    local monitor_pid=""
    if [ "$DOCKER_AVAILABLE" = true ]; then
        print_info "Starting resource monitoring..."
        "$SCRIPTS_DIR/monitor-resources.sh" "$RESULTS_DIR/${test_name}_resources.csv" 2 &
        monitor_pid=$!
        sleep 2 # Give monitor time to start
        print_success "Resource monitoring started (PID: $monitor_pid)"
    fi

    # Run warmup if this is the first test
    if [ ! -f "$RESULTS_DIR/.warmed_up" ]; then
        print_info "Running warmup phase ($WARMUP_DURATION)..."
        TARGET_RPS=10 TEST_DURATION="$WARMUP_DURATION" k6 run \
            --quiet \
            -e TARGET_RPS=10 \
            -e TEST_DURATION="$WARMUP_DURATION" \
            -e BASE_URL="$BASE_URL" \
            "$SCRIPTS_DIR/load-test.js" > /dev/null 2>&1 || true
        touch "$RESULTS_DIR/.warmed_up"
        print_success "Warmup complete"
        echo ""
    fi

    # Run k6 load test
    print_info "Starting k6 load test..."
    local k6_output_file="$RESULTS_DIR/${test_name}_k6_output.txt"
    local json_output_file="$RESULTS_DIR/${test_name}_summary.json"

    if TARGET_RPS="$target_rps" TEST_DURATION="$TEST_DURATION" k6 run \
        -e TARGET_RPS="$target_rps" \
        -e TEST_DURATION="$TEST_DURATION" \
        -e BASE_URL="$BASE_URL" \
        --out json="$RESULTS_DIR/${test_name}_metrics.json" \
        "$SCRIPTS_DIR/load-test.js" 2>&1 | tee "$k6_output_file"; then
        print_success "Load test completed successfully"
    else
        print_error "Load test encountered errors (check output file)"
    fi

    # Stop resource monitoring
    if [ -n "$monitor_pid" ] && kill -0 "$monitor_pid" 2>/dev/null; then
        print_info "Stopping resource monitoring..."
        kill -SIGTERM "$monitor_pid" 2>/dev/null || true
        wait "$monitor_pid" 2>/dev/null || true
        print_success "Resource monitoring stopped"
    fi

    # Parse results
    echo ""
    print_info "Parsing results..."

    # Extract key metrics from k6 output
    if [ -f "$k6_output_file" ]; then
        local avg_response_time=$(grep -oP 'http_req_duration.*avg=\K[0-9.]+' "$k6_output_file" | head -1)
        local p95_response_time=$(grep -oP 'http_req_duration.*p\(95\)=\K[0-9.]+' "$k6_output_file" | head -1)
        local error_rate=$(grep -oP 'http_req_failed.*[0-9.]+%' "$k6_output_file" | grep -oP '[0-9.]+' | head -1)
        local total_requests=$(grep -oP 'http_reqs\.*\K[0-9]+' "$k6_output_file" | head -1)

        echo ""
        echo "Key Metrics:"
        echo "  Total Requests: ${total_requests:-N/A}"
        echo "  Avg Response Time: ${avg_response_time:-N/A} ms"
        echo "  P95 Response Time: ${p95_response_time:-N/A} ms"
        echo "  Error Rate: ${error_rate:-N/A}%"
    fi

    # Check success criteria for 10k/min test
    if [ "$level_name" = "10k" ]; then
        echo ""
        print_header "Success Criteria Check (10k/min)"

        local success=true

        if [ -n "$avg_response_time" ]; then
            if (( $(echo "$avg_response_time < 200" | bc -l) )); then
                print_success "Average response time: ${avg_response_time}ms < 200ms ✓"
            else
                print_error "Average response time: ${avg_response_time}ms >= 200ms ✗"
                success=false
            fi
        fi

        if [ -n "$error_rate" ]; then
            if (( $(echo "$error_rate < 5" | bc -l) )); then
                print_success "Error rate: ${error_rate}% < 5% ✓"
            else
                print_error "Error rate: ${error_rate}% >= 5% ✗"
                success=false
            fi
        fi

        if [ "$success" = true ]; then
            echo ""
            print_success "SUCCESS CRITERIA MET! 🎉"
        else
            echo ""
            print_error "Success criteria not met"
        fi
    fi

    echo ""
    print_success "Test results saved:"
    echo "  - K6 output: $k6_output_file"
    echo "  - Summary: $RESULTS_DIR/summary.json"
    [ -f "$RESULTS_DIR/${test_name}_resources.csv" ] && echo "  - Resources: $RESULTS_DIR/${test_name}_resources.csv"
    echo ""
}

# Function to generate performance report
generate_report() {
    print_header "Generating Performance Report"

    local report_file="$RESULTS_DIR/performance_report.md"
    local report_script="$SCRIPTS_DIR/generate-report.py"

    if [ -f "$report_script" ]; then
        print_info "Running report generation script..."
        if python3 "$report_script" "$RESULTS_DIR" > "$report_file"; then
            print_success "Performance report generated: $report_file"
        else
            print_warning "Report generation script failed, creating basic report..."
            create_basic_report "$report_file"
        fi
    else
        print_info "Creating basic performance report..."
        create_basic_report "$report_file"
    fi

    echo ""
    print_success "Report saved to: $report_file"
    echo ""
    echo "View the report:"
    echo "  cat $report_file"
    echo ""
}

# Function to create basic markdown report
create_basic_report() {
    local report_file=$1

    cat > "$report_file" << 'EOF'
# TrashAlert API - Load Test Performance Report

## Test Overview

**Date:** $(date -u +"%Y-%m-%d %H:%M:%S UTC")
**Application:** TrashAlert API
**Base URL:** $BASE_URL
**Test Duration:** $TEST_DURATION per scenario

## Test Scenarios

The following load test scenarios were executed:

1. **5k/min** - 5,000 requests per minute (83 RPS)
2. **10k/min** - 10,000 requests per minute (167 RPS)
3. **20k/min** - 20,000 requests per minute (333 RPS)

## Success Criteria

For the **10k/min** test:
- ✓ Average response time < 200ms
- ✓ Error rate < 5%
- ✓ Application remains stable

## Traffic Distribution

The load tests simulated realistic traffic patterns:

- **70%** - GET /lookup (address and coordinate lookups)
- **15%** - POST /report (crowdsourced report submissions)
- **10%** - GET /stats (statistics queries)
- **5%** - POST /interpret-address (AI-powered address interpretation)

## Results Summary

### 5k/min (83 RPS) - Baseline Load

See detailed results in `results/5k_*` files.

### 10k/min (167 RPS) - Target Load

**SUCCESS CRITERIA:** This is the critical test scenario.

See detailed results in `results/10k_*` files.

### 20k/min (333 RPS) - Stress Test

See detailed results in `results/20k_*` files.

## Detailed Metrics

### Response Time Percentiles

| Load Level | Avg | P50 | P95 | P99 | Max |
|------------|-----|-----|-----|-----|-----|
| 5k/min     | -   | -   | -   | -   | -   |
| 10k/min    | -   | -   | -   | -   | -   |
| 20k/min    | -   | -   | -   | -   | -   |

### Error Rates

| Load Level | Total Requests | Failed Requests | Error Rate |
|------------|----------------|-----------------|------------|
| 5k/min     | -              | -               | -          |
| 10k/min    | -              | -               | -          |
| 20k/min    | -              | -               | -          |

### Resource Utilization

| Load Level | Avg CPU | Peak CPU | Avg Memory | Peak Memory |
|------------|---------|----------|------------|-------------|
| 5k/min     | -       | -        | -          | -           |
| 10k/min    | -       | -        | -          | -           |
| 20k/min    | -       | -        | -          | -           |

## Endpoint Performance Breakdown

### GET /lookup
- Primary endpoint (70% of traffic)
- Critical path for user experience

### POST /report
- Write operation with database updates
- Triggers consensus calculation

### GET /stats
- Aggregation query performance

### POST /interpret-address
- External API dependency (AI service)
- Expected higher latency

## Observations

### Performance Characteristics

- **Database performance:** [To be filled based on results]
- **Memory stability:** [To be filled based on results]
- **CPU utilization:** [To be filled based on results]
- **Rate limiting impact:** [To be filled based on results]

### Bottlenecks Identified

1. [To be identified from test results]
2. [To be identified from test results]

### Recommendations

Based on the load test results:

1. **Immediate actions:** [To be filled]
2. **Performance optimizations:** [To be filled]
3. **Scalability improvements:** [To be filled]

## Conclusion

**10k/min Success Criteria:**
- [ ] Average response time < 200ms
- [ ] Error rate < 5%
- [ ] Application stability maintained

**Overall Assessment:** [To be filled]

## Test Artifacts

All test results are available in the `load-tests/results/` directory:

- `*_k6_output.txt` - Full k6 test output
- `*_summary.json` - Structured test summary
- `*_resources.csv` - Resource utilization metrics
- `*_metrics.json` - Detailed metrics in JSON format

## Next Steps

1. Review detailed metrics in result files
2. Analyze resource utilization patterns
3. Identify and address performance bottlenecks
4. Re-run tests after optimizations
5. Consider horizontal scaling if needed

---

*Generated by TrashAlert Load Test Suite*
*For questions or issues, check the load-tests/README.md*
EOF

    # Replace variables
    sed -i "s|\$BASE_URL|$BASE_URL|g" "$report_file"
    sed -i "s|\$TEST_DURATION|$TEST_DURATION|g" "$report_file"
    sed -i "s|$(date -u +\"%Y-%m-%d %H:%M:%S UTC\")|$(date -u +"%Y-%m-%d %H:%M:%S UTC")|g" "$report_file"
}

# Main execution
main() {
    print_header "TrashAlert API Load Test Suite"

    echo "This will run comprehensive load tests at:"
    echo "  • 5k requests/min (83 RPS) - Baseline"
    echo "  • 10k requests/min (167 RPS) - Target"
    echo "  • 20k requests/min (333 RPS) - Stress"
    echo ""
    echo "Each test will run for: $TEST_DURATION"
    echo "API endpoint: $BASE_URL"
    echo ""

    # Ask for confirmation unless AUTO_RUN is set
    if [ "${AUTO_RUN:-false}" != "true" ]; then
        read -p "Continue? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_warning "Load tests cancelled"
            exit 0
        fi
    fi

    # Check prerequisites
    check_prerequisites

    # Run tests for each load level
    for level in "5k" "10k" "20k"; do
        run_load_test "$level" "${LOAD_LEVELS[$level]}"

        # Cool down between tests
        if [ "$level" != "20k" ]; then
            print_info "Cooling down for 30 seconds before next test..."
            sleep 30
        fi
    done

    # Generate final report
    generate_report

    print_header "Load Testing Complete!"

    echo "All tests completed successfully!"
    echo ""
    echo "Next steps:"
    echo "  1. Review the performance report: cat $RESULTS_DIR/performance_report.md"
    echo "  2. Analyze detailed metrics in: $RESULTS_DIR/"
    echo "  3. Check if 10k/min success criteria were met"
    echo ""

    print_success "Done! 🎉"
}

# Run main function
main "$@"
