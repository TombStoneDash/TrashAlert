"""
Test script for TrashAlert API.

This script demonstrates:
1. Submitting crowdsourced reports via POST /report
2. Looking up addresses via GET /lookup
3. Showing how consensus is built from multiple reports
4. Showing different data sources (CROWD_VERIFIED, OFFICIAL, UNKNOWN)

Usage:
1. Start the API server: uvicorn app.main:app --reload
2. Run this script: python test_api.py
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"


def print_response(title, response):
    """Pretty print API response."""
    print(f"\n{'=' * 60}")
    print(f"{title}")
    print(f"{'=' * 60}")
    print(f"Status: {response.status_code}")
    print(f"Response:")
    print(json.dumps(response.json(), indent=2))


def test_lookup_official():
    """Test lookup with official data."""
    print("\n\n### TEST 1: Lookup address with official data ###")

    response = requests.get(
        f"{BASE_URL}/lookup",
        params={"address": "456 Main St, San Diego, CA"}
    )
    print_response("GET /lookup - Official Data", response)


def test_lookup_unknown():
    """Test lookup for unknown address."""
    print("\n\n### TEST 2: Lookup unknown address ###")

    response = requests.get(
        f"{BASE_URL}/lookup",
        params={"address": "9999 Nonexistent St, Nowhere, CA"}
    )
    print_response("GET /lookup - Unknown Address", response)


def test_crowdsourced_flow():
    """Test full crowdsourced flow: report -> consensus -> lookup."""
    print("\n\n### TEST 3: Crowdsourced data flow ###")

    address = "1122 Palmview Ave, El Centro, CA"

    # Submit first report
    print("\n--- Report 1: Single report (not verified yet) ---")
    report1 = {
        "address": address,
        "trash_day": "WED",
        "recycling_day": "FRI",
        "green_day": None,
        "user_hash": "user_001"
    }
    response = requests.post(f"{BASE_URL}/report", json=report1)
    print_response("POST /report #1", response)

    # Lookup after first report
    time.sleep(0.5)
    response = requests.get(f"{BASE_URL}/lookup", params={"address": address})
    print_response("GET /lookup after 1 report", response)

    # Submit second report (same data)
    print("\n--- Report 2: Two reports (still not verified) ---")
    report2 = {
        "address": address,
        "trash_day": "WED",
        "recycling_day": "FRI",
        "green_day": None,
        "user_hash": "user_002"
    }
    response = requests.post(f"{BASE_URL}/report", json=report2)
    print_response("POST /report #2", response)

    # Submit third report (same data - should reach verification threshold)
    print("\n--- Report 3: Three reports with 100% agreement (VERIFIED!) ---")
    report3 = {
        "address": address,
        "trash_day": "WED",
        "recycling_day": "FRI",
        "green_day": None,
        "user_hash": "user_003"
    }
    response = requests.post(f"{BASE_URL}/report", json=report3)
    print_response("POST /report #3", response)

    # Lookup after verification
    time.sleep(0.5)
    response = requests.get(f"{BASE_URL}/lookup", params={"address": address})
    print_response("GET /lookup after 3 reports (VERIFIED)", response)

    # Submit a conflicting report
    print("\n--- Report 4: Conflicting data (lowers agreement ratio) ---")
    report4 = {
        "address": address,
        "trash_day": "MON",  # Different from consensus!
        "recycling_day": "FRI",
        "green_day": None,
        "user_hash": "user_004"
    }
    response = requests.post(f"{BASE_URL}/report", json=report4)
    print_response("POST /report #4 (conflicting)", response)

    # Lookup after conflicting report
    time.sleep(0.5)
    response = requests.get(f"{BASE_URL}/lookup", params={"address": address})
    print_response("GET /lookup after conflicting report", response)


def test_new_address_crowdsourced():
    """Test crowdsourced data for address with no official data."""
    print("\n\n### TEST 4: New address with crowdsourced data only ###")

    address = "789 Oak Ave, Calexico, CA"

    # Submit multiple reports to reach verification
    reports = [
        {
            "address": address,
            "trash_day": "THU",
            "recycling_day": "THU",
            "green_day": "MON",
            "user_hash": f"user_{i}"
        }
        for i in range(3)
    ]

    for i, report in enumerate(reports, 1):
        print(f"\n--- Report {i} for new address ---")
        response = requests.post(f"{BASE_URL}/report", json=report)
        print_response(f"POST /report #{i}", response)

    # Lookup the new address
    time.sleep(0.5)
    response = requests.get(f"{BASE_URL}/lookup", params={"address": address})
    print_response("GET /lookup - Crowdsourced only (verified)", response)


def test_stats():
    """Get database statistics."""
    print("\n\n### Database Statistics ###")
    response = requests.get(f"{BASE_URL}/stats")
    print_response("GET /stats", response)


def main():
    """Run all tests."""
    print("=" * 60)
    print("TrashAlert API Test Suite")
    print("=" * 60)

    try:
        # Check if server is running
        response = requests.get(BASE_URL)
        print("✓ API server is running")
    except requests.exceptions.ConnectionError:
        print("✗ Error: API server is not running!")
        print("\nPlease start the server first:")
        print("  uvicorn app.main:app --reload")
        return

    # Run tests
    test_lookup_official()
    test_lookup_unknown()
    test_crowdsourced_flow()
    test_new_address_crowdsourced()
    test_stats()

    print("\n\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
