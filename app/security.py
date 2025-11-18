"""Security utilities and middleware for TrashAlert API."""

import re
import logging
from typing import Optional, List, Tuple
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import html

logger = logging.getLogger(__name__)


# ============================================================================
# MALICIOUS PATTERN DETECTION
# ============================================================================

# SQL Injection patterns
SQL_INJECTION_PATTERNS = [
    r"(\bunion\b.*\bselect\b)",
    r"(\bselect\b.*\bfrom\b)",
    r"(\binsert\b.*\binto\b)",
    r"(\bupdate\b.*\bset\b)",
    r"(\bdelete\b.*\bfrom\b)",
    r"(\bdrop\b.*\btable\b)",
    r"(\bexec\b|\bexecute\b)",
    r"(;.*--)",
    r"(--.*$)",
    r"(/\*.*\*/)",
    r"(\bor\b.*=.*)",
    r"(\band\b.*=.*)",
    r"('.*or.*'.*=.*')",
    r"(1=1)",
    r"(1' or '1'='1)",
    r"(' or 1=1--)",
    r"(\bxp_cmdshell\b)",
]

# XSS patterns
XSS_PATTERNS = [
    r"<script[^>]*>.*?</script>",
    r"javascript:",
    r"onerror\s*=",
    r"onload\s*=",
    r"onclick\s*=",
    r"<iframe[^>]*>",
    r"<embed[^>]*>",
    r"<object[^>]*>",
    r"eval\s*\(",
    r"expression\s*\(",
]

# Path traversal patterns
PATH_TRAVERSAL_PATTERNS = [
    r"\.\./",
    r"\.\.",
    r"%2e%2e",
    r"%252e%252e",
    r"\.\.\\",
]

# Command injection patterns
COMMAND_INJECTION_PATTERNS = [
    r";.*\b(ls|cat|wget|curl|rm|chmod)\b",
    r"\|.*\b(ls|cat|wget|curl|rm|chmod)\b",
    r"`.*`",
    r"\$\(.*\)",
]


def detect_sql_injection(text: str) -> Tuple[bool, Optional[str]]:
    """
    Detect potential SQL injection attempts.

    Returns:
        Tuple of (is_suspicious, matched_pattern)
    """
    text_lower = text.lower()
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True, pattern
    return False, None


def detect_xss(text: str) -> Tuple[bool, Optional[str]]:
    """
    Detect potential XSS attempts.

    Returns:
        Tuple of (is_suspicious, matched_pattern)
    """
    for pattern in XSS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True, pattern
    return False, None


def detect_path_traversal(text: str) -> Tuple[bool, Optional[str]]:
    """
    Detect potential path traversal attempts.

    Returns:
        Tuple of (is_suspicious, matched_pattern)
    """
    for pattern in PATH_TRAVERSAL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True, pattern
    return False, None


def detect_command_injection(text: str) -> Tuple[bool, Optional[str]]:
    """
    Detect potential command injection attempts.

    Returns:
        Tuple of (is_suspicious, matched_pattern)
    """
    for pattern in COMMAND_INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True, pattern
    return False, None


def sanitize_input(text: str) -> str:
    """
    Sanitize user input by HTML encoding special characters.

    Args:
        text: Raw user input

    Returns:
        Sanitized text with HTML entities escaped
    """
    return html.escape(text)


def validate_input_security(text: str, field_name: str = "input") -> List[str]:
    """
    Run all security checks on user input.

    Args:
        text: Input text to validate
        field_name: Name of the field for logging

    Returns:
        List of detected security issues (empty if clean)
    """
    if not text:
        return []

    issues = []

    # Check for SQL injection
    is_sql, pattern = detect_sql_injection(text)
    if is_sql:
        issues.append(f"SQL injection attempt detected in {field_name}: {pattern}")
        logger.warning(f"SECURITY: SQL injection attempt in {field_name}: {text[:100]}")

    # Check for XSS
    is_xss, pattern = detect_xss(text)
    if is_xss:
        issues.append(f"XSS attempt detected in {field_name}: {pattern}")
        logger.warning(f"SECURITY: XSS attempt in {field_name}: {text[:100]}")

    # Check for path traversal
    is_path, pattern = detect_path_traversal(text)
    if is_path:
        issues.append(f"Path traversal attempt detected in {field_name}: {pattern}")
        logger.warning(f"SECURITY: Path traversal attempt in {field_name}: {text[:100]}")

    # Check for command injection
    is_cmd, pattern = detect_command_injection(text)
    if is_cmd:
        issues.append(f"Command injection attempt detected in {field_name}: {pattern}")
        logger.warning(f"SECURITY: Command injection attempt in {field_name}: {text[:100]}")

    return issues


# ============================================================================
# IP ADDRESS EXTRACTION (X-Forwarded-For support)
# ============================================================================

def get_client_ip(request: Request) -> str:
    """
    Extract the real client IP address, respecting X-Forwarded-For header.

    When behind a reverse proxy (Nginx, CloudFlare, etc.), the X-Forwarded-For
    header contains the original client IP. The format is:
    X-Forwarded-For: client, proxy1, proxy2

    We take the leftmost IP (the original client).

    Args:
        request: FastAPI request object

    Returns:
        Client IP address as string
    """
    # Check X-Forwarded-For header first (for proxy setups)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP (original client)
        client_ip = forwarded_for.split(",")[0].strip()
        return client_ip

    # Check X-Real-IP header (used by some proxies)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fall back to direct connection IP
    if request.client:
        return request.client.host

    return "unknown"


# ============================================================================
# SECURITY HEADERS MIDDLEWARE
# ============================================================================

async def add_security_headers(request: Request, call_next):
    """
    Add security headers to all responses.

    Headers added:
    - X-Content-Type-Options: nosniff (prevent MIME sniffing)
    - X-Frame-Options: DENY (prevent clickjacking)
    - X-XSS-Protection: 1; mode=block (enable XSS filter in old browsers)
    - Strict-Transport-Security: enforce HTTPS
    - Content-Security-Policy: restrict resource loading
    - Referrer-Policy: control referrer information
    - Permissions-Policy: restrict browser features
    """
    response = await call_next(request)

    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"

    # Enable XSS protection in older browsers
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Enforce HTTPS (only if not in development)
    # Note: Only enable this if you have HTTPS configured
    # response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # Content Security Policy - restrict resource loading
    # This is a strict policy that only allows resources from the same origin
    csp_policy = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    response.headers["Content-Security-Policy"] = csp_policy

    # Control referrer information
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Restrict browser features
    response.headers["Permissions-Policy"] = (
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "gyroscope=(), "
        "accelerometer=()"
    )

    return response


# ============================================================================
# REQUEST VALIDATION MIDDLEWARE
# ============================================================================

async def validate_request_security(request: Request, call_next):
    """
    Validate incoming requests for security threats.

    This middleware:
    1. Checks for malicious patterns in query parameters
    2. Checks for malicious patterns in path
    3. Validates request size
    4. Checks for suspicious user agents
    5. Logs suspicious activity
    """
    # Check request size (prevent DoS via large payloads)
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            size = int(content_length)
            MAX_REQUEST_SIZE = 1024 * 1024  # 1 MB
            if size > MAX_REQUEST_SIZE:
                logger.warning(
                    f"SECURITY: Request size too large: {size} bytes from "
                    f"{get_client_ip(request)}"
                )
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "Payload Too Large",
                        "message": "Request size exceeds maximum allowed"
                    }
                )
        except ValueError:
            pass

    # Check path for malicious patterns
    path = str(request.url.path)
    path_issues = validate_input_security(path, "path")
    if path_issues:
        client_ip = get_client_ip(request)
        logger.warning(f"SECURITY: Malicious path from {client_ip}: {path}")
        return JSONResponse(
            status_code=400,
            content={
                "error": "Bad Request",
                "message": "Invalid request path"
            }
        )

    # Check query parameters
    for key, value in request.query_params.items():
        param_issues = validate_input_security(value, f"query.{key}")
        if param_issues:
            client_ip = get_client_ip(request)
            logger.warning(
                f"SECURITY: Malicious query parameter from {client_ip}: "
                f"{key}={value[:50]}"
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Bad Request",
                    "message": f"Invalid query parameter: {key}"
                }
            )

    # Check for suspicious user agents (common bot/scanner patterns)
    user_agent = request.headers.get("user-agent", "").lower()
    suspicious_agents = ["sqlmap", "nikto", "nmap", "masscan", "zap", "burp"]
    if any(agent in user_agent for agent in suspicious_agents):
        client_ip = get_client_ip(request)
        logger.warning(
            f"SECURITY: Suspicious user agent from {client_ip}: {user_agent}"
        )
        # Don't block, just log for now

    response = await call_next(request)
    return response


# ============================================================================
# BODY VALIDATION HELPER
# ============================================================================

async def validate_request_body(request: Request) -> Optional[dict]:
    """
    Validate request body for security threats.

    This should be called by endpoints that accept JSON bodies
    to validate all string fields in the payload.

    Args:
        request: FastAPI request object

    Returns:
        Dictionary of validation errors, or None if valid
    """
    try:
        # Try to parse JSON body
        body = await request.json()

        if not isinstance(body, dict):
            return None

        # Check all string values
        all_issues = []
        for key, value in body.items():
            if isinstance(value, str):
                issues = validate_input_security(value, f"body.{key}")
                if issues:
                    all_issues.extend(issues)

        if all_issues:
            client_ip = get_client_ip(request)
            logger.warning(
                f"SECURITY: Malicious request body from {client_ip}: {all_issues}"
            )
            return {
                "error": "Bad Request",
                "message": "Request contains potentially malicious content",
                "details": all_issues
            }

        return None

    except Exception:
        # Not JSON or already consumed - that's fine
        return None
