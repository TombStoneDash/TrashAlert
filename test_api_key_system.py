#!/usr/bin/env python3
"""
Test script for API key system.

This script:
1. Creates a test API key
2. Makes API requests using the key
3. Verifies rate limiting works
4. Checks usage tracking
5. Views the usage dashboard
"""

import sys
import requests
import time
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent))

from app.database import engine
from sqlalchemy.orm import Session
from app.models import APIKey, APIUsage
from app.api_key_utils import generate_api_key

BASE_URL = "http://localhost:8000"


def create_test_api_key():
    """Create a test API key in the database."""
    print("=" * 60)
    print("Creating test API key...")
    print("=" * 60)

    # Generate API key
    full_key, key_hash, key_prefix = generate_api_key()

    # Create API key record
    session = Session(engine)
    try:
        api_key = APIKey(
            key_hash=key_hash,
            key_prefix=key_prefix,
            company_name="Test Company",
            contact_email="test@example.com",
            rate_limit_per_minute=5,  # Low limit for testing
            rate_limit_per_hour=100,
            rate_limit_per_day=1000,
        )

        session.add(api_key)
        session.commit()
        session.refresh(api_key)

        print(f"✓ API Key created successfully!")
        print(f"  ID: {api_key.id}")
        print(f"  Prefix: {api_key.key_prefix}")
        print(f"  Full Key: {full_key}")
        print(f"  Company: {api_key.company_name}")
        print(f"  Rate Limits: {api_key.rate_limit_per_minute}/min, {api_key.rate_limit_per_hour}/hr, {api_key.rate_limit_per_day}/day")
        print()

        return full_key, api_key.id

    finally:
        session.close()


def test_api_request_with_key(api_key):
    """Test making an API request with the key."""
    print("=" * 60)
    print("Testing API request with key...")
    print("=" * 60)

    # Test the health check endpoint (should work without key)
    print("\n1. Testing health check (no key required)...")
    response = requests.get(f"{BASE_URL}/")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   ✓ Health check passed")
    else:
        print(f"   ✗ Health check failed")

    # Test with API key in header
    print("\n2. Testing with API key in X-API-Key header...")
    headers = {"X-API-Key": api_key}
    response = requests.get(f"{BASE_URL}/lookup?address=123 Main St, San Diego, CA", headers=headers)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        print(f"   ✓ Request with API key succeeded")
    else:
        print(f"   ✗ Request failed: {response.json()}")

    # Test without API key (should fail)
    print("\n3. Testing without API key (should fail)...")
    response = requests.get(f"{BASE_URL}/lookup?address=123 Main St, San Diego, CA")
    print(f"   Status: {response.status_code}")
    if response.status_code == 401:
        print(f"   ✓ Request correctly rejected without API key")
    else:
        print(f"   ✗ Request should have been rejected")

    print()


def test_rate_limiting(api_key):
    """Test rate limiting."""
    print("=" * 60)
    print("Testing rate limiting (5 requests/min limit)...")
    print("=" * 60)

    headers = {"X-API-Key": api_key}

    # Make requests up to the limit
    for i in range(1, 7):
        response = requests.get(f"{BASE_URL}/stats", headers=headers)
        print(f"  Request {i}: Status {response.status_code}")

        if response.status_code == 429:
            print(f"  ✓ Rate limit enforced after {i-1} requests")
            print(f"  Error: {response.json()['detail']}")
            break
        elif i == 6 and response.status_code == 200:
            print(f"  ⚠ Warning: Rate limit not enforced (expected 429 on request 6)")

        time.sleep(0.1)  # Small delay between requests

    print()


def check_usage_tracking(api_key_id):
    """Check that usage is being tracked."""
    print("=" * 60)
    print("Checking usage tracking...")
    print("=" * 60)

    session = Session(engine)
    try:
        # Get usage logs for this key
        usage_logs = session.query(APIUsage).filter(
            APIUsage.api_key_id == api_key_id
        ).all()

        print(f"✓ Found {len(usage_logs)} usage log entries")

        if usage_logs:
            print("\nRecent requests:")
            for log in usage_logs[-5:]:  # Show last 5
                print(f"  - {log.method} {log.endpoint} -> {log.status_code} ({log.response_time_ms:.2f}ms)")

        # Check API key total_requests counter
        api_key = session.query(APIKey).filter(APIKey.id == api_key_id).first()
        print(f"\nAPI Key total_requests counter: {api_key.total_requests}")
        print(f"Last used at: {api_key.last_used_at}")

    finally:
        session.close()

    print()


def test_admin_endpoints(api_key):
    """Test admin endpoints."""
    print("=" * 60)
    print("Testing admin endpoints...")
    print("=" * 60)

    # Note: Admin endpoints don't require API key (they're exempt)

    # List API keys
    print("\n1. GET /admin/keys - List all API keys")
    response = requests.get(f"{BASE_URL}/admin/keys")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        keys = response.json()
        print(f"   ✓ Found {len(keys)} API key(s)")
        for key in keys:
            print(f"     - {key['key_prefix']}... ({key['company_name']}) - {key['total_requests']} requests")

    # Get usage dashboard
    print("\n2. GET /admin/usage - Usage dashboard")
    response = requests.get(f"{BASE_URL}/admin/usage")
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        dashboard = response.json()
        print(f"   ✓ Dashboard loaded")
        print(f"     Total API keys: {dashboard['total_api_keys']}")
        print(f"     Active API keys: {dashboard['active_api_keys']}")
        print(f"     Requests today: {dashboard['total_requests_today']}")
        print(f"     Requests (7 days): {dashboard['total_requests_7days']}")
        print(f"     Error rate: {dashboard['error_rate']:.2%}")

    print()


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("API KEY SYSTEM TEST SUITE")
    print("=" * 60)
    print()

    # Note: Make sure the API server is running before testing
    try:
        response = requests.get(f"{BASE_URL}/", timeout=2)
    except requests.exceptions.ConnectionError:
        print("ERROR: API server is not running!")
        print("Please start the server with: uvicorn app.main:app --reload")
        return 1

    # Create test API key
    api_key, api_key_id = create_test_api_key()

    # Run tests
    test_api_request_with_key(api_key)
    test_rate_limiting(api_key)
    check_usage_tracking(api_key_id)
    test_admin_endpoints(api_key)

    print("=" * 60)
    print("TEST SUITE COMPLETE")
    print("=" * 60)
    print()

    return 0


if __name__ == "__main__":
    exit(main())
