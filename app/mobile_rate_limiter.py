"""Rate limiter for mobile endpoints with API key support."""
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
import threading
from app.models import ApiKey


class MobileRateLimiter:
    """Rate limiter for mobile endpoints.

    Supports dual rate limiting:
    1. Per-API-key limits (configurable per key)
    2. Per-IP limits (fallback for requests without valid keys)

    Uses sliding window algorithm with separate minute and hour windows.
    """

    def __init__(
        self,
        default_requests_per_minute: int = 30,
        default_requests_per_hour: int = 500
    ):
        """Initialize rate limiter.

        Args:
            default_requests_per_minute: Default minute limit (for IP-based)
            default_requests_per_hour: Default hour limit (for IP-based)
        """
        self.default_rpm = default_requests_per_minute
        self.default_rph = default_requests_per_hour

        # Storage: {key: [timestamp1, timestamp2, ...]}
        # Key can be "api_key:{id}" or "ip:{address}"
        self.requests: Dict[str, list] = defaultdict(list)

        # Thread lock for concurrent access
        self.lock = threading.Lock()

        # Start cleanup thread
        self._start_cleanup()

    def _start_cleanup(self):
        """Start background thread to clean up old request logs."""
        def cleanup_old_entries():
            while True:
                time.sleep(300)  # Run every 5 minutes
                with self.lock:
                    cutoff = time.time() - 3600  # Remove entries older than 1 hour
                    for key in list(self.requests.keys()):
                        self.requests[key] = [
                            ts for ts in self.requests[key] if ts > cutoff
                        ]
                        # Remove empty keys
                        if not self.requests[key]:
                            del self.requests[key]

        thread = threading.Thread(target=cleanup_old_entries, daemon=True)
        thread.start()

    def _get_key(self, api_key_id: Optional[int] = None, ip_address: Optional[str] = None) -> str:
        """Generate storage key for rate limiting.

        Args:
            api_key_id: API key ID (takes precedence)
            ip_address: IP address (fallback)

        Returns:
            Storage key string
        """
        if api_key_id is not None:
            return f"api_key:{api_key_id}"
        elif ip_address:
            return f"ip:{ip_address}"
        else:
            return "unknown"

    def _get_limits(self, api_key: Optional[ApiKey] = None) -> Tuple[int, int]:
        """Get rate limits for this request.

        Args:
            api_key: ApiKey record (if authenticated)

        Returns:
            Tuple of (requests_per_minute, requests_per_hour)
        """
        if api_key:
            return (
                api_key.rate_limit_per_minute or self.default_rpm,
                api_key.rate_limit_per_hour or self.default_rph
            )
        else:
            return self.default_rpm, self.default_rph

    def is_allowed(
        self,
        api_key: Optional[ApiKey] = None,
        ip_address: Optional[str] = None
    ) -> Tuple[bool, str, Dict[str, int]]:
        """Check if request is allowed under rate limits.

        Args:
            api_key: ApiKey record (if authenticated)
            ip_address: Client IP address

        Returns:
            Tuple of:
            - allowed (bool): True if request is allowed
            - message (str): Error message if not allowed
            - stats (dict): Current usage stats
        """
        with self.lock:
            now = time.time()

            # Determine storage key and limits
            if api_key:
                storage_key = self._get_key(api_key_id=api_key.id)
            else:
                storage_key = self._get_key(ip_address=ip_address)

            rpm_limit, rph_limit = self._get_limits(api_key)

            # Get request timestamps for this key
            timestamps = self.requests[storage_key]

            # Remove timestamps older than 1 hour
            cutoff_hour = now - 3600
            timestamps = [ts for ts in timestamps if ts > cutoff_hour]
            self.requests[storage_key] = timestamps

            # Count requests in last minute and hour
            cutoff_minute = now - 60
            count_minute = sum(1 for ts in timestamps if ts > cutoff_minute)
            count_hour = len(timestamps)

            # Build stats
            stats = {
                "requests_last_minute": count_minute,
                "requests_last_hour": count_hour,
                "limit_per_minute": rpm_limit,
                "limit_per_hour": rph_limit,
                "remaining_minute": max(0, rpm_limit - count_minute),
                "remaining_hour": max(0, rph_limit - count_hour)
            }

            # Check limits
            if count_minute >= rpm_limit:
                return False, f"Rate limit exceeded: {rpm_limit} requests per minute", stats

            if count_hour >= rph_limit:
                return False, f"Rate limit exceeded: {rph_limit} requests per hour", stats

            # Allow request - add timestamp
            self.requests[storage_key].append(now)

            return True, "", stats

    def get_stats(
        self,
        api_key: Optional[ApiKey] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, int]:
        """Get current usage statistics.

        Args:
            api_key: ApiKey record (if authenticated)
            ip_address: Client IP address

        Returns:
            Dictionary with usage statistics
        """
        with self.lock:
            now = time.time()

            if api_key:
                storage_key = self._get_key(api_key_id=api_key.id)
            else:
                storage_key = self._get_key(ip_address=ip_address)

            rpm_limit, rph_limit = self._get_limits(api_key)

            timestamps = self.requests.get(storage_key, [])

            # Count requests in windows
            cutoff_minute = now - 60
            cutoff_hour = now - 3600

            count_minute = sum(1 for ts in timestamps if ts > cutoff_minute)
            count_hour = sum(1 for ts in timestamps if ts > cutoff_hour)

            return {
                "requests_last_minute": count_minute,
                "requests_last_hour": count_hour,
                "limit_per_minute": rpm_limit,
                "limit_per_hour": rph_limit,
                "remaining_minute": max(0, rpm_limit - count_minute),
                "remaining_hour": max(0, rph_limit - count_hour)
            }


# Global rate limiter instance for mobile endpoints
mobile_rate_limiter = MobileRateLimiter(
    default_requests_per_minute=30,  # More restrictive than web (60)
    default_requests_per_hour=500    # More restrictive than web (1000)
)
