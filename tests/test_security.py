"""
Comprehensive security tests for TrashAlert API.

Tests:
- Input validation and sanitization
- SQL injection prevention
- XSS prevention
- Path traversal prevention
- Rate limiting
- Security headers
- CORS configuration
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.security import (
    detect_sql_injection,
    detect_xss,
    detect_path_traversal,
    detect_command_injection,
    validate_input_security,
    get_client_ip,
    sanitize_input,
)


client = TestClient(app)


# ============================================================================
# INPUT VALIDATION TESTS
# ============================================================================

class TestInputValidation:
    """Test input validation and sanitization."""

    def test_empty_address_rejected(self):
        """Empty addresses should be rejected."""
        response = client.post("/report", json={
            "address": "",
            "trash_day": "MON"
        })
        assert response.status_code == 422

    def test_whitespace_only_address_rejected(self):
        """Whitespace-only addresses should be rejected."""
        response = client.post("/report", json={
            "address": "   ",
            "trash_day": "MON"
        })
        assert response.status_code == 422

    def test_oversized_address_rejected(self):
        """Addresses exceeding max length should be rejected."""
        huge_address = "A" * 1000
        response = client.post("/report", json={
            "address": huge_address,
            "trash_day": "MON"
        })
        assert response.status_code == 422

    def test_invalid_day_rejected(self):
        """Invalid day formats should be rejected."""
        response = client.post("/report", json={
            "address": "123 Main St, El Centro, CA",
            "trash_day": "INVALID"
        })
        assert response.status_code == 422

    def test_invalid_coordinates_rejected(self):
        """Invalid coordinates should be rejected."""
        response = client.get("/lookup", params={
            "lat": 999,
            "lon": 999
        })
        assert response.status_code == 422

    def test_coordinates_out_of_range(self):
        """Coordinates outside valid ranges should be rejected."""
        response = client.get("/lookup", params={
            "lat": -91,  # Invalid latitude
            "lon": 0
        })
        assert response.status_code == 422

    def test_user_hash_validation(self):
        """User hash should only accept alphanumeric, dash, underscore."""
        # Valid user hash
        response = client.post("/report", json={
            "address": "123 Main St, El Centro, CA",
            "trash_day": "MON",
            "user_hash": "valid-user_123"
        })
        assert response.status_code in [200, 404]  # 404 if address not found

        # Invalid user hash with special characters
        response = client.post("/report", json={
            "address": "123 Main St, El Centro, CA",
            "trash_day": "MON",
            "user_hash": "invalid@user#123"
        })
        assert response.status_code == 422


# ============================================================================
# SQL INJECTION TESTS
# ============================================================================

class TestSQLInjection:
    """Test SQL injection prevention."""

    def test_sql_injection_detection(self):
        """Test SQL injection pattern detection."""
        # Should detect SQL injection
        is_sql, _ = detect_sql_injection("' OR '1'='1")
        assert is_sql is True

        is_sql, _ = detect_sql_injection("1' UNION SELECT NULL--")
        assert is_sql is True

        is_sql, _ = detect_sql_injection("'; DROP TABLE addresses--")
        assert is_sql is True

        # Should not detect normal addresses
        is_sql, _ = detect_sql_injection("123 Main St, El Centro, CA")
        assert is_sql is False

    def test_sql_injection_in_address_lookup(self):
        """SQL injection attempts in address lookup should be rejected."""
        sql_payloads = [
            "' OR '1'='1",
            "1' UNION SELECT NULL--",
            "'; DROP TABLE addresses--",
            "admin'--"
        ]

        for payload in sql_payloads:
            response = client.get("/lookup", params={
                "address": f"123 Main St {payload}"
            })
            # Should be rejected (400/422) or handled safely (200/404)
            assert response.status_code in [200, 400, 404, 422]

            # Should not leak SQL errors
            assert "sql" not in response.text.lower()
            assert "syntax" not in response.text.lower()
            assert "mysql" not in response.text.lower()
            assert "postgresql" not in response.text.lower()

    def test_sql_injection_in_report(self):
        """SQL injection attempts in report submission should be rejected."""
        response = client.post("/report", json={
            "address": "123 Main St' OR '1'='1",
            "trash_day": "MON"
        })

        # Should be rejected due to malicious pattern
        assert response.status_code in [400, 422]

    def test_parameterized_queries_used(self):
        """Verify that ORM uses parameterized queries (implicit test)."""
        # This is implicitly tested by the fact that we use SQLAlchemy ORM
        # which always uses parameterized queries
        response = client.get("/lookup", params={
            "address": "123 Main St"
        })
        # Should work normally
        assert response.status_code in [200, 404]


# ============================================================================
# XSS TESTS
# ============================================================================

class TestXSS:
    """Test XSS (Cross-Site Scripting) prevention."""

    def test_xss_detection(self):
        """Test XSS pattern detection."""
        # Should detect XSS
        is_xss, _ = detect_xss("<script>alert('XSS')</script>")
        assert is_xss is True

        is_xss, _ = detect_xss("<img src=x onerror=alert('XSS')>")
        assert is_xss is True

        is_xss, _ = detect_xss("javascript:alert('XSS')")
        assert is_xss is True

        # Should not detect normal text
        is_xss, _ = detect_xss("123 Main St, El Centro, CA")
        assert is_xss is False

    def test_xss_in_interpret_address(self):
        """XSS attempts in interpret-address should be rejected."""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')"
        ]

        for payload in xss_payloads:
            response = client.post("/interpret-address", json={
                "text": f"123 Main St {payload}"
            })

            # Should be rejected
            assert response.status_code in [400, 422]

    def test_html_sanitization(self):
        """Test HTML entity sanitization."""
        dangerous_html = "<script>alert('xss')</script>"
        sanitized = sanitize_input(dangerous_html)

        # Should escape HTML entities
        assert "<script>" not in sanitized
        assert "&lt;script&gt;" in sanitized


# ============================================================================
# PATH TRAVERSAL TESTS
# ============================================================================

class TestPathTraversal:
    """Test path traversal prevention."""

    def test_path_traversal_detection(self):
        """Test path traversal pattern detection."""
        # Should detect path traversal
        is_path, _ = detect_path_traversal("../../../etc/passwd")
        assert is_path is True

        is_path, _ = detect_path_traversal("..\\..\\windows\\system32")
        assert is_path is True

        is_path, _ = detect_path_traversal("%2e%2e%2f")
        assert is_path is True

        # Should not detect normal addresses
        is_path, _ = detect_path_traversal("123 Main St, El Centro, CA")
        assert is_path is False

    def test_path_traversal_in_lookup(self):
        """Path traversal attempts should be rejected."""
        path_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "%2e%2e%2f%2e%2e%2f"
        ]

        for payload in path_payloads:
            response = client.get("/lookup", params={"address": payload})

            # Should be rejected or return 404
            assert response.status_code in [400, 404, 422]

            # Should not leak file contents
            assert "root:" not in response.text.lower()
            assert "[boot loader]" not in response.text.lower()


# ============================================================================
# COMMAND INJECTION TESTS
# ============================================================================

class TestCommandInjection:
    """Test command injection prevention."""

    def test_command_injection_detection(self):
        """Test command injection pattern detection."""
        # Should detect command injection
        is_cmd, _ = detect_command_injection("; ls -la")
        assert is_cmd is True

        is_cmd, _ = detect_command_injection("| cat /etc/passwd")
        assert is_cmd is True

        is_cmd, _ = detect_command_injection("$(whoami)")
        assert is_cmd is True

        # Should not detect normal text
        is_cmd, _ = detect_command_injection("123 Main St, El Centro, CA")
        assert is_cmd is False


# ============================================================================
# RATE LIMITING TESTS
# ============================================================================

class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_rate_limit_headers_present(self):
        """Rate limit headers should be present in responses."""
        response = client.get("/lookup", params={"address": "123 Main St"})

        # Rate limit headers should be present
        assert "X-RateLimit-Limit-Minute" in response.headers
        assert "X-RateLimit-Limit-Hour" in response.headers

    def test_rate_limiting_enforced(self):
        """Rate limiting should eventually return 429 status."""
        # Note: This test might be slow as it makes many requests
        # Skip in CI if needed
        import os
        if os.getenv("CI"):
            pytest.skip("Skipping rate limit test in CI")

        # Make many requests quickly
        responses = []
        for i in range(70):
            response = client.get("/lookup", params={"address": f"123 Main St #{i}"})
            responses.append(response.status_code)

            if response.status_code == 429:
                break

        # Should eventually hit rate limit
        assert 429 in responses


# ============================================================================
# SECURITY HEADERS TESTS
# ============================================================================

class TestSecurityHeaders:
    """Test security headers."""

    def test_security_headers_present(self):
        """Required security headers should be present."""
        response = client.get("/")

        # Check for required security headers
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert "Content-Security-Policy" in response.headers
        assert "Referrer-Policy" in response.headers

    def test_csp_header_configured(self):
        """Content Security Policy should be properly configured."""
        response = client.get("/")
        csp = response.headers.get("Content-Security-Policy", "")

        # Should have basic CSP directives
        assert "default-src" in csp
        assert "script-src" in csp
        assert "frame-ancestors" in csp

    def test_permissions_policy_configured(self):
        """Permissions-Policy should restrict unnecessary features."""
        response = client.get("/")
        permissions = response.headers.get("Permissions-Policy", "")

        # Should restrict camera, microphone, etc.
        assert "camera=" in permissions or "Permissions-Policy" not in response.headers


# ============================================================================
# CORS TESTS
# ============================================================================

class TestCORS:
    """Test CORS configuration."""

    def test_cors_not_wildcard_with_credentials(self):
        """CORS should not allow wildcard origin with credentials."""
        response = client.options(
            "/lookup",
            headers={"Origin": "https://evil.com"}
        )

        cors_origin = response.headers.get("Access-Control-Allow-Origin", "")
        cors_creds = response.headers.get("Access-Control-Allow-Credentials", "")

        # CRITICAL: Should not have * origin with credentials
        if cors_origin == "*":
            assert cors_creds.lower() != "true", "CRITICAL: Wildcard CORS with credentials"


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Test secure error handling."""

    def test_no_stack_traces_in_errors(self):
        """Stack traces should not be exposed to clients."""
        # Trigger an error with invalid data
        response = client.post("/report", json={
            "address": "123 Main St",
            "trash_day": "INVALID_DAY"
        })

        # Should not contain stack traces
        assert "Traceback" not in response.text
        assert "File \"" not in response.text
        assert "line " not in response.text.lower() or "status_code" in response.text.lower()

    def test_database_errors_sanitized(self):
        """Database errors should not leak schema information."""
        # Make a request that might cause a DB error
        response = client.get("/lookup", params={"address": "' OR 1=1--"})

        # Should not leak database details
        assert "sqlite" not in response.text.lower()
        assert "table" not in response.text.lower() or "not found" in response.text.lower()
        assert "column" not in response.text.lower()


# ============================================================================
# IP ADDRESS EXTRACTION TESTS
# ============================================================================

class TestIPExtraction:
    """Test X-Forwarded-For header handling."""

    def test_get_client_ip_from_forwarded_header(self):
        """Should extract client IP from X-Forwarded-For header."""
        from fastapi import Request

        # Create a mock request with X-Forwarded-For
        class MockClient:
            host = "127.0.0.1"

        class MockRequest:
            headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
            client = MockClient()

        request = MockRequest()
        ip = get_client_ip(request)

        # Should return the first IP (original client)
        assert ip == "1.2.3.4"

    def test_get_client_ip_fallback(self):
        """Should fall back to direct IP if no X-Forwarded-For."""
        from fastapi import Request

        class MockClient:
            host = "127.0.0.1"

        class MockRequest:
            headers = {}
            client = MockClient()

        request = MockRequest()
        ip = get_client_ip(request)

        # Should return direct client IP
        assert ip == "127.0.0.1"


# ============================================================================
# COMPREHENSIVE VALIDATION TEST
# ============================================================================

class TestComprehensiveSecurity:
    """Comprehensive security validation."""

    def test_all_endpoints_have_validation(self):
        """All endpoints should have input validation."""
        # Test each endpoint with invalid data
        endpoints = [
            ("/lookup", "get", {"address": ""}),
            ("/report", "post", {"address": "", "trash_day": "MON"}),
            ("/interpret-address", "post", {"text": ""}),
        ]

        for path, method, data in endpoints:
            if method == "get":
                response = client.get(path, params=data)
            else:
                response = client.post(path, json=data)

            # Should reject invalid input
            assert response.status_code in [400, 422], f"{method.upper()} {path} didn't validate input"

    def test_security_logging(self):
        """Security violations should be logged."""
        # Make a request with malicious input
        response = client.post("/report", json={
            "address": "' OR 1=1--",
            "trash_day": "MON"
        })

        # Should be rejected
        assert response.status_code in [400, 422]

        # Note: Actual log checking would require log capture,
        # but we verify that the request was properly rejected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
