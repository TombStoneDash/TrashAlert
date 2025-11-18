"""Simple in-memory IP-based rate limiter."""
import time
from collections import defaultdict
from typing import Dict, Tuple
import threading


class RateLimiter:
    """
    Simple in-memory rate limiter using sliding window algorithm.

    Tracks requests per IP address and enforces rate limits.
    Thread-safe implementation with automatic cleanup of old entries.
    """

    def __init__(self, requests_per_minute: int = 60, requests_per_hour: int = 1000):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests allowed per minute per IP
            requests_per_hour: Maximum requests allowed per hour per IP
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour

        # Store: {ip: [(timestamp1, timestamp2, ...)]}
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = threading.Lock()

        # Cleanup old entries every 5 minutes
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes

    def _cleanup_old_entries(self):
        """Remove requests older than 1 hour to prevent memory bloat."""
        current_time = time.time()

        # Only cleanup every 5 minutes
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        cutoff_time = current_time - 3600  # 1 hour ago

        with self._lock:
            # Remove old timestamps
            for ip in list(self._requests.keys()):
                self._requests[ip] = [
                    ts for ts in self._requests[ip]
                    if ts > cutoff_time
                ]
                # Remove IP if no recent requests
                if not self._requests[ip]:
                    del self._requests[ip]

            self._last_cleanup = current_time

    def is_allowed(self, ip: str) -> Tuple[bool, str]:
        """
        Check if request from IP is allowed based on rate limits.

        Args:
            ip: IP address to check

        Returns:
            Tuple of (is_allowed: bool, reason: str)
        """
        current_time = time.time()

        # Periodic cleanup
        self._cleanup_old_entries()

        with self._lock:
            # Get request history for this IP
            requests = self._requests[ip]

            # Check minute limit
            minute_ago = current_time - 60
            recent_requests = [ts for ts in requests if ts > minute_ago]

            if len(recent_requests) >= self.requests_per_minute:
                return False, f"Rate limit exceeded: {self.requests_per_minute} requests per minute"

            # Check hour limit
            hour_ago = current_time - 3600
            hourly_requests = [ts for ts in requests if ts > hour_ago]

            if len(hourly_requests) >= self.requests_per_hour:
                return False, f"Rate limit exceeded: {self.requests_per_hour} requests per hour"

            # Record this request
            self._requests[ip].append(current_time)

            return True, "OK"

    def get_stats(self, ip: str) -> Dict[str, int]:
        """
        Get current request counts for an IP.

        Args:
            ip: IP address to check

        Returns:
            Dict with requests_last_minute and requests_last_hour
        """
        current_time = time.time()

        with self._lock:
            requests = self._requests.get(ip, [])

            minute_ago = current_time - 60
            hour_ago = current_time - 3600

            return {
                "requests_last_minute": len([ts for ts in requests if ts > minute_ago]),
                "requests_last_hour": len([ts for ts in requests if ts > hour_ago]),
                "limit_per_minute": self.requests_per_minute,
                "limit_per_hour": self.requests_per_hour
            }


# Global rate limiter instance
rate_limiter = RateLimiter(
    requests_per_minute=60,  # 60 requests per minute (1 per second average)
    requests_per_hour=1000   # 1000 requests per hour
)
