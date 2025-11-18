"""Middleware for request logging and metrics collection."""
import time
from datetime import datetime, timedelta
from collections import defaultdict
from threading import Lock
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import Callable, Optional

from app.logging_config import access_logger, error_logger
from app.api_key_utils import hash_api_key


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all API requests with timing information.

    Logs:
    - Request method and path
    - Response status code
    - Response time in milliseconds
    - Client IP address
    - User agent
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details."""
        # Start timing
        start_time = time.time()

        # Extract request details
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code

            # Calculate response time
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000

            # Log successful request
            access_logger.info(
                f"{method} {path} - Status: {status_code} - "
                f"Time: {response_time_ms:.2f}ms - IP: {client_ip}"
            )

            # Add custom header with response time
            response.headers["X-Response-Time"] = f"{response_time_ms:.2f}ms"

            return response

        except Exception as e:
            # Calculate response time even for errors
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000

            # Log error
            error_logger.error(
                f"{method} {path} - ERROR after {response_time_ms:.2f}ms - "
                f"IP: {client_ip} - Error: {str(e)}",
                exc_info=True
            )

            # Re-raise the exception to be handled by FastAPI
            raise


class APIKeyRateLimiter:
    """
    Per-API-key rate limiter with sliding window algorithm.

    Tracks requests per minute, hour, and day for each API key.
    """

    def __init__(self):
        """Initialize the rate limiter."""
        self.requests = defaultdict(list)  # api_key_id -> list of request timestamps
        self.lock = Lock()

    def check_rate_limit(
        self,
        api_key_id: int,
        limits_per_minute: int,
        limits_per_hour: int,
        limits_per_day: int,
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a request should be allowed based on rate limits.

        Args:
            api_key_id: The API key ID
            limits_per_minute: Max requests per minute
            limits_per_hour: Max requests per hour
            limits_per_day: Max requests per day

        Returns:
            Tuple of (is_allowed, error_message)
        """
        now = datetime.utcnow()

        with self.lock:
            # Get request history for this key
            history = self.requests[api_key_id]

            # Remove requests older than 24 hours
            cutoff_day = now - timedelta(days=1)
            history[:] = [ts for ts in history if ts > cutoff_day]

            # Check daily limit
            if len(history) >= limits_per_day:
                return False, f"Daily rate limit exceeded ({limits_per_day} requests/day)"

            # Check hourly limit
            cutoff_hour = now - timedelta(hours=1)
            hour_count = sum(1 for ts in history if ts > cutoff_hour)
            if hour_count >= limits_per_hour:
                return False, f"Hourly rate limit exceeded ({limits_per_hour} requests/hour)"

            # Check minute limit
            cutoff_minute = now - timedelta(minutes=1)
            minute_count = sum(1 for ts in history if ts > cutoff_minute)
            if minute_count >= limits_per_minute:
                return False, f"Rate limit exceeded ({limits_per_minute} requests/minute)"

            # Add current request to history
            history.append(now)

            return True, None

    def cleanup_old_entries(self):
        """Remove old entries to prevent memory bloat."""
        now = datetime.utcnow()
        cutoff = now - timedelta(days=1)

        with self.lock:
            # Clean up old entries
            keys_to_remove = []
            for key_id, history in self.requests.items():
                history[:] = [ts for ts in history if ts > cutoff]
                if not history:
                    keys_to_remove.append(key_id)

            for key_id in keys_to_remove:
                del self.requests[key_id]


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to authenticate API requests using API keys.

    Checks for API key in:
    1. X-API-Key header
    2. Authorization: Bearer <key> header
    3. api_key query parameter

    Exempts certain endpoints from authentication (health checks, admin pages).
    """

    def __init__(self, app: ASGIApp, rate_limiter: APIKeyRateLimiter):
        """Initialize the middleware."""
        super().__init__(app)
        self.rate_limiter = rate_limiter

        # Endpoints that don't require API key authentication
        self.exempt_paths = {
            "/",  # Health check
            "/docs",  # API documentation
            "/openapi.json",  # OpenAPI schema
            "/redoc",  # ReDoc documentation
        }

        # Admin endpoints (will be protected separately)
        self.admin_paths_prefix = "/admin"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and validate API key."""
        path = request.url.path

        # Skip authentication for exempt paths
        if path in self.exempt_paths:
            return await call_next(request)

        # Skip authentication for admin paths (handle separately)
        if path.startswith(self.admin_paths_prefix):
            return await call_next(request)

        # Extract API key from request
        api_key = self._extract_api_key(request)

        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="API key required. Provide key in X-API-Key header, Authorization: Bearer header, or api_key query parameter.",
            )

        # Validate API key and get key info from database
        from app.database import get_db
        from app.models import APIKey

        db = next(get_db())
        try:
            key_hash = hash_api_key(api_key)
            api_key_obj = db.query(APIKey).filter(
                APIKey.key_hash == key_hash,
                APIKey.is_active == True
            ).first()

            if not api_key_obj:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid or inactive API key"
                )

            # Check if key is expired
            if api_key_obj.expires_at and api_key_obj.expires_at < datetime.utcnow():
                raise HTTPException(
                    status_code=401,
                    detail="API key has expired"
                )

            # Check rate limits
            is_allowed, error_msg = self.rate_limiter.check_rate_limit(
                api_key_obj.id,
                api_key_obj.rate_limit_per_minute,
                api_key_obj.rate_limit_per_hour,
                api_key_obj.rate_limit_per_day,
            )

            if not is_allowed:
                raise HTTPException(status_code=429, detail=error_msg)

            # Store API key info in request state for later use
            request.state.api_key_id = api_key_obj.id
            request.state.api_key_company = api_key_obj.company_name

            # Update last_used_at and total_requests (async, don't block)
            api_key_obj.last_used_at = datetime.utcnow()
            api_key_obj.total_requests += 1
            db.commit()

        finally:
            db.close()

        return await call_next(request)

    def _extract_api_key(self, request: Request) -> Optional[str]:
        """
        Extract API key from request headers or query parameters.

        Priority:
        1. X-API-Key header
        2. Authorization: Bearer header
        3. api_key query parameter
        """
        # Check X-API-Key header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return api_key

        # Check Authorization: Bearer header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove "Bearer " prefix

        # Check query parameter
        api_key = request.query_params.get("api_key")
        if api_key:
            return api_key

        return None


class APIUsageTrackingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track API usage for analytics.

    Records each API request to the api_usage table for billing and analytics.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log usage."""
        start_time = time.time()

        # Extract request details
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        # Get API key ID from request state (set by APIKeyAuthMiddleware)
        api_key_id = getattr(request.state, "api_key_id", None)

        # Process request
        response = None
        error_message = None
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            error_message = str(e)
            raise
        finally:
            # Calculate response time
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000

            # Log usage to database (only for authenticated requests)
            if api_key_id:
                try:
                    from app.database import get_db
                    from app.models import APIUsage

                    db = next(get_db())
                    try:
                        usage_log = APIUsage(
                            api_key_id=api_key_id,
                            endpoint=path,
                            method=method,
                            status_code=status_code,
                            response_time_ms=response_time_ms,
                            ip_address=client_ip,
                            user_agent=user_agent,
                            error_message=error_message,
                        )
                        db.add(usage_log)
                        db.commit()
                    finally:
                        db.close()
                except Exception as e:
                    # Don't let usage tracking errors break the request
                    error_logger.error(f"Failed to log API usage: {str(e)}", exc_info=True)

        return response
