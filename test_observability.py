#!/usr/bin/env python3
"""Test script for observability features."""
import requests
import json
import time
from pathlib import Path

BASE_URL = "http://localhost:8000"


def test_health_check():
    """Test the health check endpoint."""
    print("\n1. Testing health check endpoint...")
    response = requests.get(f"{BASE_URL}/")
    print(f"   Status: {response.status_code}")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200
    assert "/stats" in response.json()["endpoints"]
    print("   ✓ Health check passed")


def test_lookup_endpoint():
    """Test the lookup endpoint with metrics."""
    print("\n2. Testing /lookup endpoint...")

    # Test with a known address (from init_db.py)
    test_addresses = [
        "123 Main St, El Centro, CA 92243",
        "456 Oak Ave, San Diego, CA 92101",
        "789 Palm Dr, Calexico, CA 92231",
        "999 Unknown St, Unknown City, CA 99999"  # Should not be found
    ]

    for addr in test_addresses:
        print(f"\n   Looking up: {addr}")
        response = requests.get(f"{BASE_URL}/lookup", params={"address": addr})
        print(f"   Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"   Source: {data['source']}")
            print(f"   Normalized: {data['normalized_address']}")

            # Check for response time header
            if 'X-Response-Time' in response.headers:
                print(f"   Response Time: {response.headers['X-Response-Time']}")

        time.sleep(0.5)  # Small delay between requests

    print("   ✓ Lookup endpoint tested")


def test_report_endpoint():
    """Test the report endpoint with metrics."""
    print("\n3. Testing /report endpoint...")

    # Submit a test report
    report_data = {
        "address": "123 Main St, El Centro, CA 92243",
        "trash_day": "MON",
        "recycling_day": "WED",
        "green_day": "FRI",
        "user_hash": "test_user_123"
    }

    print(f"   Submitting report: {report_data['address']}")
    response = requests.post(f"{BASE_URL}/report", json=report_data)
    print(f"   Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print(f"   Success: {data['success']}")
        print(f"   Message: {data['message']}")

        if data.get('consensus'):
            consensus = data['consensus']
            print(f"   Reports count: {consensus['reports_count']}")
            print(f"   Is verified: {consensus['is_verified']}")

        # Check for response time header
        if 'X-Response-Time' in response.headers:
            print(f"   Response Time: {response.headers['X-Response-Time']}")

    print("   ✓ Report endpoint tested")


def test_stats_endpoint():
    """Test the enhanced /stats endpoint."""
    print("\n4. Testing /stats endpoint...")

    response = requests.get(f"{BASE_URL}/stats")
    print(f"   Status: {response.status_code}")

    if response.status_code == 200:
        stats = response.json()
        print(f"\n   API Metrics:")
        api_metrics = stats.get('api_metrics', {})
        print(f"     Total lookups: {api_metrics.get('total_lookups', 0)}")
        print(f"     Total reports: {api_metrics.get('total_reports', 0)}")
        print(f"     Total errors: {api_metrics.get('total_errors', 0)}")
        print(f"     Avg lookup time: {api_metrics.get('avg_lookup_time_ms', 0):.2f}ms")
        print(f"     Avg report time: {api_metrics.get('avg_report_time_ms', 0):.2f}ms")

        print(f"\n   Lookup by City:")
        for city, count in stats.get('lookup_by_city', {}).items():
            print(f"     {city}: {count}")

        print(f"\n   Report by City:")
        for city, count in stats.get('report_by_city', {}).items():
            print(f"     {city}: {count}")

        print(f"\n   Database Stats:")
        db_stats = stats.get('database_stats', {})
        print(f"     Total addresses: {db_stats.get('total_addresses', 0)}")
        print(f"     Total crowd reports: {db_stats.get('total_crowd_reports', 0)}")
        print(f"     Total consensus: {db_stats.get('total_consensus', 0)}")
        print(f"     Verified consensus: {db_stats.get('verified_consensus', 0)}")

        print(f"\n   Endpoint Details:")
        endpoint_details = stats.get('endpoint_details', {})
        for endpoint, details in endpoint_details.items():
            print(f"     {endpoint}:")
            print(f"       Total requests: {details.get('total_requests', 0)}")
            print(f"       Avg response time: {details.get('avg_response_time_ms', 0):.2f}ms")
            print(f"       Success rate: {details.get('success_rate', 0):.2f}%")

    print("   ✓ Stats endpoint tested")


def test_logs_created():
    """Check if log files were created."""
    print("\n5. Checking log files...")

    log_dir = Path(__file__).parent / "logs"
    log_files = ["access.log", "error.log", "app.log"]

    for log_file in log_files:
        log_path = log_dir / log_file
        if log_path.exists():
            size = log_path.stat().st_size
            print(f"   ✓ {log_file} exists ({size} bytes)")
        else:
            print(f"   ✗ {log_file} NOT found")

    print("   ✓ Log files checked")


def main():
    """Run all observability tests."""
    print("=" * 60)
    print("TrashAlert Observability Test Suite")
    print("=" * 60)

    try:
        test_health_check()
        test_lookup_endpoint()
        test_report_endpoint()
        test_stats_endpoint()
        test_logs_created()

        print("\n" + "=" * 60)
        print("All tests completed successfully!")
        print("=" * 60)

    except requests.exceptions.ConnectionError:
        print("\n✗ ERROR: Could not connect to the API.")
        print("  Please make sure the server is running:")
        print("  uvicorn app.main:app --reload")
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
