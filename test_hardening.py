#!/usr/bin/env python3
"""
Quick test script to verify hardening improvements.
"""
import sys
import time

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    try:
        from app.main import app
        from app.rate_limiter import rate_limiter
        from app.cache import lookup_cache
        from app.models import Address, CrowdReport, CrowdConsensus
        from app.schemas import ReportRequest, LookupResponse
        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        return False


def test_rate_limiter():
    """Test rate limiter functionality."""
    print("\nTesting rate limiter...")
    try:
        from app.rate_limiter import RateLimiter

        # Create test limiter
        limiter = RateLimiter(requests_per_minute=5, requests_per_hour=10)

        # Should allow first 5 requests
        for i in range(5):
            allowed, reason = limiter.is_allowed("test_ip")
            assert allowed, f"Request {i+1} should be allowed"

        # 6th request should be blocked
        allowed, reason = limiter.is_allowed("test_ip")
        assert not allowed, "6th request should be blocked"
        assert "per minute" in reason.lower()

        print("✓ Rate limiter works correctly")
        return True
    except Exception as e:
        print(f"✗ Rate limiter test failed: {e}")
        return False


def test_cache():
    """Test cache functionality."""
    print("\nTesting cache...")
    try:
        from app.cache import SimpleCache

        cache = SimpleCache(max_size=10, default_ttl=1)

        # Test set and get
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1", "Cache get should return stored value"

        # Test cache miss
        assert cache.get("nonexistent") is None, "Cache miss should return None"

        # Test TTL expiration
        cache.set("key2", "value2", ttl=1)
        time.sleep(1.1)
        assert cache.get("key2") is None, "Expired key should return None"

        # Test delete
        cache.set("key3", "value3")
        cache.delete("key3")
        assert cache.get("key3") is None, "Deleted key should return None"

        # Test stats
        stats = cache.get_stats()
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats

        print("✓ Cache works correctly")
        return True
    except Exception as e:
        print(f"✗ Cache test failed: {e}")
        return False


def test_validation():
    """Test Pydantic validation."""
    print("\nTesting request validation...")
    try:
        from app.schemas import ReportRequest
        from pydantic import ValidationError

        # Valid request
        valid_req = ReportRequest(
            address="123 Main St, City, CA 12345",
            trash_day="MON"
        )
        assert valid_req.address == "123 Main St, City, CA 12345"
        assert valid_req.trash_day == "MON"

        # Test address normalization
        req_with_spaces = ReportRequest(
            address="  123   Main   St  ",
            trash_day="MONDAY"
        )
        assert req_with_spaces.address == "123 Main St"

        # Test invalid day
        try:
            invalid_day = ReportRequest(
                address="123 Main St",
                trash_day="INVALID"
            )
            assert False, "Should have raised validation error"
        except ValidationError:
            pass  # Expected

        # Test no days provided
        try:
            no_days = ReportRequest(address="123 Main St")
            assert False, "Should have raised validation error for no days"
        except ValidationError:
            pass  # Expected

        # Test address too short
        try:
            short_addr = ReportRequest(
                address="123",
                trash_day="MON"
            )
            assert False, "Should have raised validation error for short address"
        except ValidationError:
            pass  # Expected

        print("✓ Request validation works correctly")
        return True
    except Exception as e:
        print(f"✗ Validation test failed: {e}")
        return False


def test_exception_handlers():
    """Test that exception handlers are registered."""
    print("\nTesting exception handlers...")
    try:
        from app.main import app

        # Check that exception handlers are registered
        assert 404 in app.exception_handlers, "404 handler should be registered"
        # RequestValidationError handler is registered differently

        print("✓ Exception handlers registered")
        return True
    except Exception as e:
        print(f"✗ Exception handler test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("TrashAlert Hardening Test Suite")
    print("=" * 60)

    tests = [
        test_imports,
        test_rate_limiter,
        test_cache,
        test_validation,
        test_exception_handlers
    ]

    results = []
    for test in tests:
        results.append(test())

    print("\n" + "=" * 60)
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    print("=" * 60)

    return all(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
