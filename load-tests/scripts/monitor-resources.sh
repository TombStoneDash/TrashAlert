#!/bin/bash

# Resource monitoring script for Docker containers during load testing
# Tracks CPU, memory, and network usage

OUTPUT_FILE="${1:-load-tests/results/resource_metrics.csv}"
INTERVAL="${2:-2}" # Sample every 2 seconds
CONTAINER_NAME="trashalert-api-1" # Default container name

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting resource monitoring...${NC}"
echo "Container: $CONTAINER_NAME"
echo "Output: $OUTPUT_FILE"
echo "Interval: ${INTERVAL}s"
echo ""

# Create output directory if it doesn't exist
mkdir -p "$(dirname "$OUTPUT_FILE")"

# Write CSV header
echo "timestamp,cpu_percent,memory_usage_mb,memory_limit_mb,memory_percent,network_rx_mb,network_tx_mb,block_read_mb,block_write_mb" > "$OUTPUT_FILE"

# Get initial network stats
PREV_NET_RX=0
PREV_NET_TX=0
PREV_BLOCK_READ=0
PREV_BLOCK_WRITE=0

# Function to extract numeric value from string like "1.5GiB"
parse_bytes() {
    local value=$1
    local number=$(echo "$value" | grep -oE '[0-9.]+')
    local unit=$(echo "$value" | grep -oE '[A-Za-z]+')

    case "$unit" in
        GiB|GB|G)
            echo "scale=2; $number * 1024" | bc
            ;;
        MiB|MB|M)
            echo "$number" | bc
            ;;
        KiB|KB|K)
            echo "scale=2; $number / 1024" | bc
            ;;
        B)
            echo "scale=2; $number / 1024 / 1024" | bc
            ;;
        *)
            echo "0"
            ;;
    esac
}

# Function to handle script termination
cleanup() {
    echo ""
    echo -e "${GREEN}Monitoring stopped. Results saved to: $OUTPUT_FILE${NC}"

    # Calculate summary statistics
    if [ -f "$OUTPUT_FILE" ]; then
        echo ""
        echo "=== Resource Usage Summary ==="

        # Calculate averages and peaks using awk
        awk -F',' 'NR>1 {
            cpu_sum += $2; cpu_count++;
            if ($2 > cpu_max) cpu_max = $2;

            mem_sum += $3; mem_count++;
            if ($3 > mem_max) mem_max = $3;

            mem_pct_sum += $5; mem_pct_count++;
            if ($5 > mem_pct_max) mem_pct_max = $5;
        }
        END {
            printf "CPU Usage:\n";
            printf "  Average: %.2f%%\n", cpu_sum / cpu_count;
            printf "  Peak: %.2f%%\n", cpu_max;
            printf "\nMemory Usage:\n";
            printf "  Average: %.2f MB (%.2f%%)\n", mem_sum / mem_count, mem_pct_sum / mem_pct_count;
            printf "  Peak: %.2f MB (%.2f%%)\n", mem_max, mem_pct_max;
        }' "$OUTPUT_FILE"
    fi

    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM EXIT

# Check if container exists
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${YELLOW}Warning: Container '$CONTAINER_NAME' not found or not running${NC}"
    echo "Available containers:"
    docker ps --format 'table {{.Names}}\t{{.Status}}'
    echo ""
    echo "Trying to find TrashAlert container..."

    # Try to find any running TrashAlert container
    CONTAINER_NAME=$(docker ps --filter "name=trashalert" --format '{{.Names}}' | head -n 1)

    if [ -z "$CONTAINER_NAME" ]; then
        echo "Error: No TrashAlert container found running"
        exit 1
    fi

    echo "Found container: $CONTAINER_NAME"
fi

echo -e "${GREEN}Monitoring container: $CONTAINER_NAME${NC}"
echo "Press Ctrl+C to stop monitoring"
echo ""

# Main monitoring loop
while true; do
    # Get current timestamp
    TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M:%S")

    # Get container stats (single sample)
    STATS=$(docker stats --no-stream --format "{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}},{{.NetIO}},{{.BlockIO}}" "$CONTAINER_NAME" 2>/dev/null)

    if [ -z "$STATS" ]; then
        echo "Warning: Could not get stats for container $CONTAINER_NAME"
        sleep "$INTERVAL"
        continue
    fi

    # Parse stats
    CPU_PERCENT=$(echo "$STATS" | cut -d',' -f1 | tr -d '%')
    MEM_USAGE=$(echo "$STATS" | cut -d',' -f2 | awk '{print $1}')
    MEM_LIMIT=$(echo "$STATS" | cut -d',' -f2 | awk '{print $3}')
    MEM_PERCENT=$(echo "$STATS" | cut -d',' -f3 | tr -d '%')
    NET_IO=$(echo "$STATS" | cut -d',' -f4)
    BLOCK_IO=$(echo "$STATS" | cut -d',' -f5)

    # Parse memory values
    MEM_USAGE_MB=$(parse_bytes "$MEM_USAGE")
    MEM_LIMIT_MB=$(parse_bytes "$MEM_LIMIT")

    # Parse network I/O
    NET_RX=$(echo "$NET_IO" | awk '{print $1}')
    NET_TX=$(echo "$NET_IO" | awk '{print $3}')
    NET_RX_MB=$(parse_bytes "$NET_RX")
    NET_TX_MB=$(parse_bytes "$NET_TX")

    # Parse block I/O
    BLOCK_READ=$(echo "$BLOCK_IO" | awk '{print $1}')
    BLOCK_WRITE=$(echo "$BLOCK_IO" | awk '{print $3}')
    BLOCK_READ_MB=$(parse_bytes "$BLOCK_READ")
    BLOCK_WRITE_MB=$(parse_bytes "$BLOCK_WRITE")

    # Write to CSV
    echo "$TIMESTAMP,$CPU_PERCENT,$MEM_USAGE_MB,$MEM_LIMIT_MB,$MEM_PERCENT,$NET_RX_MB,$NET_TX_MB,$BLOCK_READ_MB,$BLOCK_WRITE_MB" >> "$OUTPUT_FILE"

    # Print current stats to console
    printf "\r[%s] CPU: %6.2f%% | Memory: %8.2f MB (%5.2f%%) | Network RX: %8.2f MB | TX: %8.2f MB" \
        "$TIMESTAMP" "$CPU_PERCENT" "$MEM_USAGE_MB" "$MEM_PERCENT" "$NET_RX_MB" "$NET_TX_MB"

    sleep "$INTERVAL"
done
