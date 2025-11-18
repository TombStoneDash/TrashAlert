"""Unit tests for AI classification cache."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from app.ai_cache import (
    InMemoryCache,
    AIClassificationCacheManager,
    AIClassificationCache,
)


class TestInMemoryCache:
    """Test suite for in-memory cache."""

    def test_set_and_get(self):
        """Test basic set and get operations."""
        cache = InMemoryCache(max_size=10, ttl_seconds=60)

        cache.set("key1", {"data": "value1"})
        result = cache.get("key1")

        assert result is not None
        assert result["data"] == "value1"

    def test_get_nonexistent_key(self):
        """Test getting non-existent key returns None."""
        cache = InMemoryCache(max_size=10, ttl_seconds=60)

        result = cache.get("nonexistent")
        assert result is None

    def test_ttl_expiration(self):
        """Test that entries expire after TTL."""
        cache = InMemoryCache(max_size=10, ttl_seconds=0)  # Immediate expiration

        cache.set("key1", {"data": "value1"})

        # Should be expired
        result = cache.get("key1")
        assert result is None

    def test_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = InMemoryCache(max_size=3, ttl_seconds=60)

        # Fill cache
        cache.set("key1", {"data": "value1"})
        cache.set("key2", {"data": "value2"})
        cache.set("key3", {"data": "value3"})

        # Access key1 to make it more recent
        cache.get("key1")

        # Add key4, should evict key2 (oldest)
        cache.set("key4", {"data": "value4"})

        assert cache.get("key1") is not None
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") is not None
        assert cache.get("key4") is not None

    def test_update_existing_key(self):
        """Test updating an existing key."""
        cache = InMemoryCache(max_size=10, ttl_seconds=60)

        cache.set("key1", {"data": "value1"})
        cache.set("key1", {"data": "value2"})

        result = cache.get("key1")
        assert result["data"] == "value2"

    def test_clear(self):
        """Test clearing all cache entries."""
        cache = InMemoryCache(max_size=10, ttl_seconds=60)

        cache.set("key1", {"data": "value1"})
        cache.set("key2", {"data": "value2"})

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.size() == 0

    def test_size(self):
        """Test cache size tracking."""
        cache = InMemoryCache(max_size=10, ttl_seconds=60)

        assert cache.size() == 0

        cache.set("key1", {"data": "value1"})
        assert cache.size() == 1

        cache.set("key2", {"data": "value2"})
        assert cache.size() == 2

        cache.clear()
        assert cache.size() == 0


class TestAIClassificationCacheManager:
    """Test suite for AI classification cache manager."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = Mock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        db.commit = Mock()
        db.rollback = Mock()
        return db

    def test_hash_text_normalization(self):
        """Test that text hashing normalizes input."""
        manager = AIClassificationCacheManager()

        hash1 = manager._hash_text("trash pickup monday")
        hash2 = manager._hash_text("TRASH PICKUP MONDAY")
        hash3 = manager._hash_text("  trash   pickup   monday  ")

        # All should produce same hash
        assert hash1 == hash2
        assert hash2 == hash3

    def test_memory_cache_hit(self, mock_db):
        """Test memory cache hit."""
        manager = AIClassificationCacheManager()

        schedules = [{"collection_type": "trash", "pickup_day": "MON"}]

        # Store in cache
        manager.set("trash pickup monday", schedules, mock_db)

        # Get from cache
        result = manager.get("trash pickup monday")

        assert result is not None
        assert result == schedules
        assert manager.stats["memory_hits"] == 1
        assert manager.stats["db_hits"] == 0

    def test_cache_miss(self, mock_db):
        """Test cache miss."""
        manager = AIClassificationCacheManager()

        result = manager.get("nonexistent text", mock_db)

        assert result is None
        assert manager.stats["misses"] == 1

    def test_db_cache_hit(self, mock_db):
        """Test database cache hit."""
        manager = AIClassificationCacheManager()

        # Mock database result
        cached_entry = Mock()
        cached_entry.text_hash = manager._hash_text("trash pickup monday")
        cached_entry.classification_result = '{"schedules": [{"collection_type": "trash"}]}'
        cached_entry.hit_count = 1

        mock_db.query.return_value.filter_by.return_value.first.return_value = cached_entry

        result = manager.get("trash pickup monday", mock_db)

        assert result is not None
        assert len(result) == 1
        assert result[0]["collection_type"] == "trash"
        assert manager.stats["db_hits"] == 1

    def test_get_stats(self):
        """Test getting cache statistics."""
        manager = AIClassificationCacheManager()

        stats = manager.get_stats()

        assert "memory_hits" in stats
        assert "db_hits" in stats
        assert "misses" in stats
        assert "total_requests" in stats
        assert "hit_rate" in stats
        assert "memory_cache_size" in stats

    def test_hit_rate_calculation(self, mock_db):
        """Test hit rate calculation."""
        manager = AIClassificationCacheManager()

        schedules = [{"collection_type": "trash", "pickup_day": "MON"}]

        # Cache text
        manager.set("text1", schedules, mock_db)

        # 2 hits, 1 miss
        manager.get("text1")  # Memory hit
        manager.get("text1")  # Memory hit
        manager.get("text2")  # Miss

        stats = manager.get_stats()

        assert stats["memory_hits"] == 2
        assert stats["misses"] == 1
        assert stats["total_requests"] == 3
        assert stats["hit_rate"] == pytest.approx(0.667, rel=0.01)

    def test_clear_memory_cache(self):
        """Test clearing memory cache."""
        manager = AIClassificationCacheManager()

        schedules = [{"collection_type": "trash"}]
        manager.set("text1", schedules, None)

        # Verify it's cached
        assert manager.get("text1") is not None

        # Clear cache
        manager.clear_memory_cache()

        # Should be gone
        assert manager.get("text1") is None

    def test_case_insensitive_lookup(self, mock_db):
        """Test that cache lookups are case-insensitive."""
        manager = AIClassificationCacheManager()

        schedules = [{"collection_type": "trash"}]
        manager.set("Trash Pickup Monday", schedules, mock_db)

        # Should find with different case
        result = manager.get("trash pickup monday")
        assert result is not None

        result = manager.get("TRASH PICKUP MONDAY")
        assert result is not None

    def test_whitespace_normalization(self, mock_db):
        """Test that extra whitespace is normalized."""
        manager = AIClassificationCacheManager()

        schedules = [{"collection_type": "trash"}]
        manager.set("trash  pickup   monday", schedules, mock_db)

        # Should find with different whitespace
        result = manager.get("trash pickup monday")
        assert result is not None

        result = manager.get("  trash pickup monday  ")
        assert result is not None


class TestAIClassificationCacheModel:
    """Test the database model for AI cache."""

    def test_model_creation(self):
        """Test creating an AIClassificationCache model."""
        cache_entry = AIClassificationCache(
            text_hash="abc123",
            original_text="trash pickup monday",
            classification_result='{"schedules": []}',
            confidence_avg=0.95,
            hit_count=1
        )

        assert cache_entry.text_hash == "abc123"
        assert cache_entry.original_text == "trash pickup monday"
        assert cache_entry.confidence_avg == 0.95
        assert cache_entry.hit_count == 1

    def test_model_repr(self):
        """Test model string representation."""
        cache_entry = AIClassificationCache(
            text_hash="abc123",
            original_text="trash pickup monday every week throughout the year",
            classification_result='{"schedules": []}',
            hit_count=5
        )

        repr_str = repr(cache_entry)
        assert "trash pickup monday every week throughout the" in repr_str
        assert "hits=5" in repr_str
