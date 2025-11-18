"""Redis-based caching layer with TTL support and cache invalidation."""
import redis
import json
import hashlib
import os
from typing import Optional, Any, Dict, List
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class RedisCache:
    """
    Redis-based cache with TTL support and pattern-based invalidation.

    Features:
    - JSON serialization for complex objects
    - TTL (Time To Live) support
    - Pattern-based key invalidation
    - Connection pooling
    - Graceful degradation (falls back to no caching if Redis unavailable)
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        default_ttl: int = 300,
        prefix: str = "trashalert:"
    ):
        """
        Initialize Redis cache.

        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password (optional)
            default_ttl: Default TTL in seconds (300 = 5 minutes)
            prefix: Key prefix to namespace cache keys
        """
        self.default_ttl = default_ttl
        self.prefix = prefix
        self.enabled = True

        try:
            # Create Redis connection with connection pool
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
                retry_on_timeout=True,
                health_check_interval=30
            )

            # Test connection
            self.redis_client.ping()
            logger.info(f"Redis cache connected to {host}:{port}")

        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.warning(f"Redis connection failed: {e}. Cache disabled.")
            self.enabled = False
            self.redis_client = None

    def _make_key(self, key: str) -> str:
        """Generate prefixed cache key."""
        return f"{self.prefix}{key}"

    def _generate_key(self, namespace: str, *args, **kwargs) -> str:
        """
        Generate deterministic cache key from namespace and arguments.

        Args:
            namespace: Key namespace (e.g., "lookup", "stats")
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Cache key string
        """
        # Create deterministic key from args and kwargs
        key_data = {
            "args": args,
            "kwargs": sorted(kwargs.items())
        }
        key_string = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.md5(key_string.encode()).hexdigest()

        return self._make_key(f"{namespace}:{key_hash}")

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value (deserialized from JSON) or None if not found
        """
        if not self.enabled:
            return None

        try:
            full_key = self._make_key(key)
            value = self.redis_client.get(full_key)

            if value is None:
                return None

            # Deserialize JSON
            return json.loads(value)

        except (redis.ConnectionError, redis.TimeoutError, json.JSONDecodeError) as e:
            logger.warning(f"Redis get failed for key {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache (will be serialized to JSON)
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        if not self.enabled:
            return

        if ttl is None:
            ttl = self.default_ttl

        try:
            full_key = self._make_key(key)

            # Serialize to JSON
            serialized = json.dumps(value, default=str)

            # Set with TTL
            self.redis_client.setex(full_key, ttl, serialized)

        except (redis.ConnectionError, redis.TimeoutError, TypeError) as e:
            logger.warning(f"Redis set failed for key {key}: {e}")

    def delete(self, key: str):
        """Delete key from cache."""
        if not self.enabled:
            return

        try:
            full_key = self._make_key(key)
            self.redis_client.delete(full_key)

        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.warning(f"Redis delete failed for key {key}: {e}")

    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.

        Args:
            pattern: Redis key pattern (e.g., "lookup:*", "stats:*")

        Returns:
            Number of keys deleted
        """
        if not self.enabled:
            return 0

        try:
            full_pattern = self._make_key(pattern)

            # Find all matching keys
            keys = list(self.redis_client.scan_iter(match=full_pattern, count=100))

            if not keys:
                return 0

            # Delete all matching keys
            deleted = self.redis_client.delete(*keys)
            logger.info(f"Invalidated {deleted} cache keys matching pattern: {pattern}")

            return deleted

        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.warning(f"Redis delete_pattern failed for pattern {pattern}: {e}")
            return 0

    def clear(self):
        """Clear all cache entries with the configured prefix."""
        if not self.enabled:
            return

        try:
            pattern = f"{self.prefix}*"
            keys = list(self.redis_client.scan_iter(match=pattern, count=100))

            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"Cleared {len(keys)} cache keys")

        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.warning(f"Redis clear failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        if not self.enabled:
            return {
                "enabled": False,
                "status": "disabled"
            }

        try:
            info = self.redis_client.info("stats")
            keyspace = self.redis_client.info("keyspace")

            # Count keys with our prefix
            pattern = f"{self.prefix}*"
            key_count = sum(1 for _ in self.redis_client.scan_iter(match=pattern, count=100))

            return {
                "enabled": True,
                "status": "connected",
                "total_keys": key_count,
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                ),
                "memory_used": info.get("used_memory_human", "unknown")
            }

        except (redis.ConnectionError, redis.TimeoutError) as e:
            logger.warning(f"Redis get_stats failed: {e}")
            return {
                "enabled": True,
                "status": "error",
                "error": str(e)
            }

    @staticmethod
    def _calculate_hit_rate(hits: int, misses: int) -> float:
        """Calculate cache hit rate percentage."""
        total = hits + misses
        if total == 0:
            return 0.0
        return round((hits / total) * 100, 2)

    # Cache invalidation helpers

    def invalidate_lookup_cache(self, address_id: Optional[int] = None):
        """
        Invalidate lookup cache.

        Args:
            address_id: Specific address ID to invalidate, or None for all
        """
        if address_id:
            # Invalidate specific address lookups
            self.delete_pattern(f"lookup:*")  # For now, invalidate all lookups
            logger.info(f"Invalidated lookup cache for address_id={address_id}")
        else:
            # Invalidate all lookup caches
            self.delete_pattern("lookup:*")
            logger.info("Invalidated all lookup caches")

    def invalidate_stats_cache(self):
        """Invalidate statistics cache."""
        self.delete_pattern("stats:*")
        logger.info("Invalidated stats cache")

    def invalidate_reverse_geocode_cache(self):
        """Invalidate reverse geocoding cache."""
        self.delete_pattern("reverse_geocode:*")
        logger.info("Invalidated reverse geocode cache")

    def invalidate_zone_cache(self):
        """Invalidate zone lookup cache."""
        self.delete_pattern("zone:*")
        logger.info("Invalidated zone cache")

    def invalidate_all(self):
        """Invalidate all caches."""
        self.clear()
        logger.info("Invalidated all caches")


# Global Redis cache instance
# Configuration from environment variables with sensible defaults
redis_cache = RedisCache(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=int(os.getenv("REDIS_DB", "0")),
    password=os.getenv("REDIS_PASSWORD"),
    default_ttl=int(os.getenv("REDIS_DEFAULT_TTL", "300")),  # 5 minutes
    prefix=os.getenv("REDIS_KEY_PREFIX", "trashalert:")
)
