"""
Caching system for AI classification responses.

Provides in-memory and database-backed caching to reduce API calls
for common schedule phrases.
"""

import hashlib
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, DateTime, Text, Float

from app.models import Base

logger = logging.getLogger(__name__)


class AIClassificationCache(Base):
    """Database model for caching AI classification results."""

    __tablename__ = "ai_classification_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    text_hash = Column(String(64), unique=True, index=True, nullable=False)
    original_text = Column(Text, nullable=False)
    classification_result = Column(Text, nullable=False)  # JSON string
    hit_count = Column(Integer, default=1)
    confidence_avg = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<AIClassificationCache(text='{self.original_text[:50]}...', hits={self.hit_count})>"


class InMemoryCache:
    """In-memory LRU cache for fast lookups."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """
        Initialize in-memory cache.

        Args:
            max_size: Maximum number of entries to keep in memory
            ttl_seconds: Time-to-live for cache entries in seconds
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.access_times: Dict[str, datetime] = {}

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get value from cache if it exists and hasn't expired."""
        if key not in self.cache:
            return None

        # Check if expired
        if key in self.access_times:
            age = (datetime.utcnow() - self.access_times[key]).total_seconds()
            if age > self.ttl_seconds:
                # Expired, remove from cache
                del self.cache[key]
                del self.access_times[key]
                return None

        # Update access time
        self.access_times[key] = datetime.utcnow()
        return self.cache[key]

    def set(self, key: str, value: Dict[str, Any]) -> None:
        """Set value in cache, evicting old entries if necessary."""
        # Check if cache is full
        if len(self.cache) >= self.max_size and key not in self.cache:
            # Evict oldest entry
            oldest_key = min(self.access_times, key=self.access_times.get)
            del self.cache[oldest_key]
            del self.access_times[oldest_key]
            logger.debug(f"Evicted cache entry: {oldest_key}")

        self.cache[key] = value
        self.access_times[key] = datetime.utcnow()

    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()
        self.access_times.clear()

    def size(self) -> int:
        """Get current cache size."""
        return len(self.cache)


class AIClassificationCacheManager:
    """
    Manager for AI classification caching with two-tier architecture:
    1. In-memory LRU cache for fast lookups
    2. Database cache for persistence
    """

    def __init__(self, memory_cache_size: int = 1000, memory_ttl_seconds: int = 3600):
        """
        Initialize cache manager.

        Args:
            memory_cache_size: Size of in-memory cache
            memory_ttl_seconds: TTL for in-memory cache entries
        """
        self.memory_cache = InMemoryCache(max_size=memory_cache_size, ttl_seconds=memory_ttl_seconds)
        self.stats = {
            "memory_hits": 0,
            "db_hits": 0,
            "misses": 0,
            "total_requests": 0
        }

    @staticmethod
    def _hash_text(text: str) -> str:
        """Generate hash for text (case-insensitive, whitespace-normalized)."""
        # Normalize text: lowercase, strip, collapse whitespace
        normalized = " ".join(text.lower().strip().split())
        return hashlib.sha256(normalized.encode()).hexdigest()

    def get(self, text: str, db: Optional[Session] = None) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached classification result.

        Args:
            text: Original schedule text
            db: Database session (optional, for DB cache)

        Returns:
            Cached classification result or None
        """
        self.stats["total_requests"] += 1
        text_hash = self._hash_text(text)

        # Try in-memory cache first
        memory_result = self.memory_cache.get(text_hash)
        if memory_result:
            self.stats["memory_hits"] += 1
            logger.debug(f"Memory cache hit for: {text[:50]}...")
            return memory_result["schedules"]

        # Try database cache
        if db:
            try:
                cached = db.query(AIClassificationCache).filter_by(text_hash=text_hash).first()
                if cached:
                    self.stats["db_hits"] += 1

                    # Update hit count and last accessed time
                    cached.hit_count += 1
                    cached.last_accessed_at = datetime.utcnow()
                    db.commit()

                    # Parse result
                    result = json.loads(cached.classification_result)

                    # Store in memory cache
                    self.memory_cache.set(text_hash, result)

                    logger.debug(f"DB cache hit for: {text[:50]}... (hits: {cached.hit_count})")
                    return result["schedules"]
            except Exception as e:
                logger.error(f"Error reading from cache: {e}")
                db.rollback()

        # Cache miss
        self.stats["misses"] += 1
        logger.debug(f"Cache miss for: {text[:50]}...")
        return None

    def set(self, text: str, schedules: List[Dict[str, Any]], db: Optional[Session] = None) -> None:
        """
        Store classification result in cache.

        Args:
            text: Original schedule text
            schedules: Classified schedules
            db: Database session (optional, for DB cache)
        """
        text_hash = self._hash_text(text)

        # Calculate average confidence
        confidences = [s.get("confidence", 0.0) for s in schedules]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

        result = {
            "schedules": schedules,
            "cached_at": datetime.utcnow().isoformat()
        }

        # Store in memory cache
        self.memory_cache.set(text_hash, result)

        # Store in database cache
        if db:
            try:
                # Check if already exists
                existing = db.query(AIClassificationCache).filter_by(text_hash=text_hash).first()
                if existing:
                    # Update existing entry
                    existing.classification_result = json.dumps(result)
                    existing.confidence_avg = avg_confidence
                    existing.last_accessed_at = datetime.utcnow()
                else:
                    # Create new entry
                    cached = AIClassificationCache(
                        text_hash=text_hash,
                        original_text=text,
                        classification_result=json.dumps(result),
                        confidence_avg=avg_confidence,
                        hit_count=1
                    )
                    db.add(cached)

                db.commit()
                logger.debug(f"Stored in cache: {text[:50]}...")
            except Exception as e:
                logger.error(f"Error writing to cache: {e}")
                db.rollback()

    def clear_memory_cache(self) -> None:
        """Clear in-memory cache."""
        self.memory_cache.clear()
        logger.info("Memory cache cleared")

    def clear_db_cache(self, db: Session) -> None:
        """Clear database cache."""
        try:
            db.query(AIClassificationCache).delete()
            db.commit()
            logger.info("Database cache cleared")
        except Exception as e:
            logger.error(f"Error clearing database cache: {e}")
            db.rollback()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self.stats["total_requests"]
        if total == 0:
            hit_rate = 0.0
        else:
            hit_rate = (self.stats["memory_hits"] + self.stats["db_hits"]) / total

        return {
            **self.stats,
            "hit_rate": round(hit_rate, 3),
            "memory_cache_size": self.memory_cache.size()
        }

    def get_popular_phrases(self, db: Session, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most popular cached phrases.

        Args:
            db: Database session
            limit: Maximum number of phrases to return

        Returns:
            List of popular phrases with statistics
        """
        try:
            results = (
                db.query(AIClassificationCache)
                .order_by(AIClassificationCache.hit_count.desc())
                .limit(limit)
                .all()
            )

            return [
                {
                    "text": r.original_text,
                    "hit_count": r.hit_count,
                    "confidence_avg": r.confidence_avg,
                    "created_at": r.created_at.isoformat(),
                    "last_accessed_at": r.last_accessed_at.isoformat()
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"Error getting popular phrases: {e}")
            return []

    def cleanup_old_entries(self, db: Session, days: int = 30) -> int:
        """
        Remove cache entries that haven't been accessed in X days.

        Args:
            db: Database session
            days: Number of days of inactivity before removal

        Returns:
            Number of entries removed
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            result = (
                db.query(AIClassificationCache)
                .filter(AIClassificationCache.last_accessed_at < cutoff_date)
                .delete()
            )
            db.commit()
            logger.info(f"Cleaned up {result} old cache entries")
            return result
        except Exception as e:
            logger.error(f"Error cleaning up cache: {e}")
            db.rollback()
            return 0


# Global cache manager instance
_cache_manager: Optional[AIClassificationCacheManager] = None


def get_cache_manager() -> AIClassificationCacheManager:
    """Get or create the global cache manager instance."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = AIClassificationCacheManager()
    return _cache_manager
