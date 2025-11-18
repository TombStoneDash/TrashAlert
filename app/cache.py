"""Simple in-memory cache with TTL support."""
import time
from typing import Optional, Any, Dict
import threading
import hashlib
import json


class SimpleCache:
    """
    Thread-safe in-memory cache with TTL (Time To Live) support.

    Uses LRU-style eviction when max size is reached.
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        Initialize cache.

        Args:
            max_size: Maximum number of items to store
            default_ttl: Default time-to-live in seconds (300 = 5 minutes)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl

        # Store: {key: {"value": ..., "expires_at": timestamp, "last_accessed": timestamp}}
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

        # Stats
        self._hits = 0
        self._misses = 0

    def _generate_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        # Create deterministic key from args and kwargs
        key_data = {
            "args": args,
            "kwargs": sorted(kwargs.items())
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _evict_expired(self):
        """Remove expired entries."""
        current_time = time.time()
        expired_keys = [
            key for key, data in self._cache.items()
            if data["expires_at"] < current_time
        ]
        for key in expired_keys:
            del self._cache[key]

    def _evict_lru(self):
        """Remove least recently used item when cache is full."""
        if not self._cache:
            return

        # Find least recently accessed item
        lru_key = min(self._cache.items(), key=lambda x: x[1]["last_accessed"])[0]
        del self._cache[lru_key]

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            # Check if key exists
            if key not in self._cache:
                self._misses += 1
                return None

            data = self._cache[key]

            # Check if expired
            if data["expires_at"] < time.time():
                del self._cache[key]
                self._misses += 1
                return None

            # Update last accessed time
            data["last_accessed"] = time.time()
            self._hits += 1

            return data["value"]

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        if ttl is None:
            ttl = self.default_ttl

        current_time = time.time()

        with self._lock:
            # Evict expired entries periodically
            if len(self._cache) > self.max_size * 0.9:  # Cleanup at 90% capacity
                self._evict_expired()

            # Evict LRU if still full
            while len(self._cache) >= self.max_size:
                self._evict_lru()

            # Store value
            self._cache[key] = {
                "value": value,
                "expires_at": current_time + ttl,
                "last_accessed": current_time
            }

    def delete(self, key: str):
        """Delete key from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 2),
                "total_requests": total_requests
            }


# Global cache instance for lookup queries
# TTL = 300 seconds (5 minutes) - balances freshness with performance
lookup_cache = SimpleCache(max_size=1000, default_ttl=300)
