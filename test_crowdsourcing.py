#!/usr/bin/env python3
"""
Test script for crowdsourcing functionality.

Tests:
1. Submit multiple reports for the same address
2. Verify consensus is calculated
3. Test verification threshold (3 reports, 75% agreement)
4. Test rate limiting
"""

import requests
import json
from time import sleep

BASE_URL = "http://localhost:8000"

def submit_report(address, trash_day, recycling_day=None, green_day=None, user_hash=None):
    """Submit a crowd report."""
    payload = {
        "address": address,
        "trash_day": trash_day,
        "recycling_day": recycling_day,
        "green_day": green_day,
        "user_hash": user_hash
    }
    response = requests.post(f"{BASE_URL}/report", json=payload)
    return response

def lookup_address(address):
    """Lookup an address."""
    response = requests.get(f"{BASE_URL}/lookup", params={"address": address})
    return response

def test_crowdsourcing():
    """Test crowdsourcing flow."""
    print("=" * 80)
    print("CROWDSOURCING ENGINE TEST")
    print("=" * 80)

    test_address = "123 Test Street, San Diego, CA"

    print("\n1. Testing initial lookup (should be UNKNOWN)...")
    response = lookup_address(test_address)
    print(f"   Status: {response.status_code}")
    data = response.json()
    print(f"   Source: {data['source']}")
    print(f"   Data: {data}")

    print("\n2. Submitting first report (MON)...")
    response = submit_report(test_address, "MON", "WED", user_hash="user1")
    print(f"   Status: {response.status_code}")
    data = response.json()
    if data['consensus']:
        print(f"   Consensus: {data['consensus']['trash_day']}")
        print(f"   Reports: {data['consensus']['reports_count']}")
        print(f"   Verified: {data['consensus']['is_verified']}")
        print(f"   Agreement: {data['consensus']['trash_agreement_ratio']:.1%}")

    print("\n3. Submitting second report (MON)...")
    response = submit_report(test_address, "MON", "WED", user_hash="user2")
    print(f"   Status: {response.status_code}")
    data = response.json()
    if data['consensus']:
        print(f"   Consensus: {data['consensus']['trash_day']}")
        print(f"   Reports: {data['consensus']['reports_count']}")
        print(f"   Verified: {data['consensus']['is_verified']}")
        print(f"   Agreement: {data['consensus']['trash_agreement_ratio']:.1%}")

    print("\n4. Submitting third report (MON) - should trigger verification...")
    response = submit_report(test_address, "MON", "WED", user_hash="user3")
    print(f"   Status: {response.status_code}")
    data = response.json()
    if data['consensus']:
        print(f"   Consensus: {data['consensus']['trash_day']}")
        print(f"   Reports: {data['consensus']['reports_count']}")
        print(f"   Verified: {data['consensus']['is_verified']} ✓" if data['consensus']['is_verified'] else f"   Verified: False")
        print(f"   Agreement: {data['consensus']['trash_agreement_ratio']:.1%}")

    print("\n5. Lookup address (should show CROWD_VERIFIED)...")
    response = lookup_address(test_address)
    data = response.json()
    print(f"   Status: {response.status_code}")
    print(f"   Source: {data['source']}")
    print(f"   Trash day: {data['trash_day']}")
    print(f"   Recycling day: {data['recycling_day']}")
    print(f"   Reports: {data['consensus_reports_count']}")
    print(f"   Agreement: {data['consensus_agreement_ratio']:.1%}")

    print("\n6. Testing consensus with disagreement...")
    test_address2 = "456 Disagree Ave, San Diego, CA"

    # 3 reports: MON, MON, TUE (66% agreement - should not verify)
    submit_report(test_address2, "MON", user_hash="user1")
    submit_report(test_address2, "MON", user_hash="user2")
    response = submit_report(test_address2, "TUE", user_hash="user3")
    data = response.json()

    print(f"   Reports: MON, MON, TUE")
    if data['consensus']:
        print(f"   Consensus: {data['consensus']['trash_day']}")
        print(f"   Reports: {data['consensus']['reports_count']}")
        print(f"   Agreement: {data['consensus']['trash_agreement_ratio']:.1%}")
        print(f"   Verified: {data['consensus']['is_verified']} (should be False - below 75%)")

    print("\n7. Testing rate limiting...")
    test_address3 = "789 Rate Limit St, San Diego, CA"

    # Submit 3 reports quickly (should hit per-address limit)
    for i in range(4):
        response = submit_report(test_address3, "MON", user_hash=f"user{i}")
        if response.status_code == 429:
            print(f"   Report {i+1}: Rate limited ✓")
            break
        else:
            print(f"   Report {i+1}: {response.status_code}")

    print("\n8. Getting stats...")
    response = requests.get(f"{BASE_URL}/stats")
    stats = response.json()
    print(f"   Total addresses: {stats['total_addresses']}")
    print(f"   Total reports: {stats['total_reports']}")
    print(f"   Total consensus: {stats['total_consensus']}")
    print(f"   Verified consensus: {stats['verified_consensus']}")

    print("\n" + "=" * 80)
    print("✓ ALL TESTS COMPLETED")
    print("=" * 80)

if __name__ == "__main__":
    try:
        test_crowdsourcing()
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Cannot connect to API server.")
        print("   Please start the server first:")
        print("   uvicorn app.main:app --reload")
