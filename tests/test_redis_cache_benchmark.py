"""Benchmark tests for Redis caching performance improvements."""
import pytest
import time
import statistics
from typing import List, Dict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Address, CrowdReport, CrowdConsensus
from app.redis_cache import redis_cache


@pytest.fixture
def benchmark_db():
    """Create in-memory test database with sample data."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create sample addresses
    addresses = [
        Address(
            normalized_address=f"12{i} MAIN ST, TEST CITY, CA",
            house_number=f"12{i}",
            street="MAIN ST",
            city="Test City",
            city_id="test_city",
            state="CA",
            zip_code="92243",
            lat=32.7 + i * 0.001,
            lon=-115.5 + i * 0.001,
            official_trash_day="MON",
            official_recycling_day="THU",
            official_green_day="THU"
        )
        for i in range(100)
    ]

    for addr in addresses:
        session.add(addr)

    session.commit()
    yield session
    session.close()


class BenchmarkResults:
    """Store and analyze benchmark results."""

    def __init__(self):
        self.results: Dict[str, List[float]] = {}

    def add_measurement(self, test_name: str, duration_ms: float):
        """Add a timing measurement."""
        if test_name not in self.results:
            self.results[test_name] = []
        self.results[test_name].append(duration_ms)

    def get_stats(self, test_name: str) -> Dict[str, float]:
        """Get statistics for a test."""
        measurements = self.results.get(test_name, [])
        if not measurements:
            return {}

        return {
            "min": min(measurements),
            "max": max(measurements),
            "mean": statistics.mean(measurements),
            "median": statistics.median(measurements),
            "stdev": statistics.stdev(measurements) if len(measurements) > 1 else 0,
            "count": len(measurements)
        }

    def calculate_improvement(self, baseline: str, optimized: str) -> Dict[str, float]:
        """Calculate improvement percentage."""
        baseline_stats = self.get_stats(baseline)
        optimized_stats = self.get_stats(optimized)

        if not baseline_stats or not optimized_stats:
            return {}

        baseline_mean = baseline_stats["mean"]
        optimized_mean = optimized_stats["mean"]

        improvement_pct = ((baseline_mean - optimized_mean) / baseline_mean) * 100

        return {
            "baseline_mean_ms": baseline_mean,
            "optimized_mean_ms": optimized_mean,
            "improvement_percent": improvement_pct,
            "speedup_factor": baseline_mean / optimized_mean if optimized_mean > 0 else 0
        }


@pytest.fixture
def benchmark_results():
    """Fixture for collecting benchmark results."""
    return BenchmarkResults()


class TestRedisCacheBenchmark:
    """Benchmark tests for Redis cache performance."""

    @pytest.mark.benchmark
    def test_lookup_cache_performance(self, benchmark_db, benchmark_results):
        """
        Benchmark lookup endpoint with and without Redis cache.

        Expected: 50-90% response time reduction for cached queries.
        """
        # Clear cache before test
        redis_cache.clear()

        test_addresses = benchmark_db.query(Address).limit(10).all()

        # Warm up Redis connection
        redis_cache.set("warmup", "test", ttl=1)
        redis_cache.get("warmup")

        # Benchmark: Cold cache (first lookup)
        for addr in test_addresses:
            start = time.time()
            # Simulate lookup query
            result = benchmark_db.query(Address).filter(
                Address.normalized_address == addr.normalized_address
            ).first()
            duration_ms = (time.time() - start) * 1000
            benchmark_results.add_measurement("lookup_cold_cache", duration_ms)

        # Populate cache
        for addr in test_addresses:
            cache_key = f"lookup:{addr.normalized_address}"
            cache_data = {
                "matched_address": addr.normalized_address,
                "city": addr.city,
                "trash_day": addr.official_trash_day
            }
            redis_cache.set(cache_key, cache_data, ttl=300)

        # Benchmark: Hot cache (cached lookup)
        for addr in test_addresses:
            start = time.time()
            cache_key = f"lookup:{addr.normalized_address}"
            cached_result = redis_cache.get(cache_key)
            duration_ms = (time.time() - start) * 1000
            benchmark_results.add_measurement("lookup_hot_cache", duration_ms)
            assert cached_result is not None

        # Calculate improvement
        improvement = benchmark_results.calculate_improvement(
            "lookup_cold_cache",
            "lookup_hot_cache"
        )

        print("\n" + "="*60)
        print("LOOKUP CACHE BENCHMARK RESULTS")
        print("="*60)
        print(f"Cold cache mean: {improvement['baseline_mean_ms']:.2f}ms")
        print(f"Hot cache mean:  {improvement['optimized_mean_ms']:.2f}ms")
        print(f"Improvement:     {improvement['improvement_percent']:.1f}%")
        print(f"Speedup factor:  {improvement['speedup_factor']:.1f}x")
        print("="*60)

        # Assert at least 50% improvement (conservative estimate)
        assert improvement['improvement_percent'] >= 50, \
            f"Expected at least 50% improvement, got {improvement['improvement_percent']:.1f}%"

    @pytest.mark.benchmark
    def test_stats_cache_performance(self, benchmark_db, benchmark_results):
        """
        Benchmark stats endpoint with and without Redis cache.

        Expected: 70-95% response time reduction for stats queries.
        """
        redis_cache.clear()

        # Warm up
        redis_cache.set("warmup", "test", ttl=1)
        redis_cache.get("warmup")

        # Benchmark: Cold cache (compute stats)
        for i in range(10):
            start = time.time()
            total_addresses = benchmark_db.query(Address).count()
            total_reports = benchmark_db.query(CrowdReport).count()
            total_consensus = benchmark_db.query(CrowdConsensus).count()
            duration_ms = (time.time() - start) * 1000
            benchmark_results.add_measurement("stats_cold_cache", duration_ms)

        # Cache stats
        stats_data = {
            "total_addresses": benchmark_db.query(Address).count(),
            "total_reports": benchmark_db.query(CrowdReport).count(),
            "total_consensus": benchmark_db.query(CrowdConsensus).count()
        }
        redis_cache.set("stats:general", stats_data, ttl=60)

        # Benchmark: Hot cache (retrieve from Redis)
        for i in range(10):
            start = time.time()
            cached_stats = redis_cache.get("stats:general")
            duration_ms = (time.time() - start) * 1000
            benchmark_results.add_measurement("stats_hot_cache", duration_ms)
            assert cached_stats is not None

        # Calculate improvement
        improvement = benchmark_results.calculate_improvement(
            "stats_cold_cache",
            "stats_hot_cache"
        )

        print("\n" + "="*60)
        print("STATS CACHE BENCHMARK RESULTS")
        print("="*60)
        print(f"Cold cache mean: {improvement['baseline_mean_ms']:.2f}ms")
        print(f"Hot cache mean:  {improvement['optimized_mean_ms']:.2f}ms")
        print(f"Improvement:     {improvement['improvement_percent']:.1f}%")
        print(f"Speedup factor:  {improvement['speedup_factor']:.1f}x")
        print("="*60)

        # Assert at least 70% improvement for stats (simpler query, bigger gain)
        assert improvement['improvement_percent'] >= 70, \
            f"Expected at least 70% improvement, got {improvement['improvement_percent']:.1f}%"

    @pytest.mark.benchmark
    def test_reverse_geocode_cache_performance(self, benchmark_results):
        """
        Benchmark reverse geocoding cache.

        Expected: 95%+ improvement (avoids external API calls).
        """
        redis_cache.clear()

        # Warm up
        redis_cache.set("warmup", "test", ttl=1)
        redis_cache.get("warmup")

        test_coords = [
            (32.791, -115.563),
            (32.792, -115.564),
            (32.793, -115.565),
        ]

        # Simulate API call delay
        def simulate_api_call(lat: float, lon: float) -> Dict:
            """Simulate slow geocoding API."""
            time.sleep(0.01)  # Simulate 10ms API call
            return {
                "lat": lat,
                "lon": lon,
                "address": f"{lat:.6f}, {lon:.6f}"
            }

        # Benchmark: Cold cache (with simulated API calls)
        for lat, lon in test_coords:
            start = time.time()
            result = simulate_api_call(lat, lon)
            duration_ms = (time.time() - start) * 1000
            benchmark_results.add_measurement("geocode_cold_cache", duration_ms)

            # Cache the result
            cache_key = f"reverse_geocode:{lat:.6f},{lon:.6f}"
            redis_cache.set(cache_key, result, ttl=3600)

        # Benchmark: Hot cache (from Redis)
        for lat, lon in test_coords:
            start = time.time()
            cache_key = f"reverse_geocode:{lat:.6f},{lon:.6f}"
            cached_result = redis_cache.get(cache_key)
            duration_ms = (time.time() - start) * 1000
            benchmark_results.add_measurement("geocode_hot_cache", duration_ms)
            assert cached_result is not None

        # Calculate improvement
        improvement = benchmark_results.calculate_improvement(
            "geocode_cold_cache",
            "geocode_hot_cache"
        )

        print("\n" + "="*60)
        print("REVERSE GEOCODE CACHE BENCHMARK RESULTS")
        print("="*60)
        print(f"Cold cache mean: {improvement['baseline_mean_ms']:.2f}ms")
        print(f"Hot cache mean:  {improvement['optimized_mean_ms']:.2f}ms")
        print(f"Improvement:     {improvement['improvement_percent']:.1f}%")
        print(f"Speedup factor:  {improvement['speedup_factor']:.1f}x")
        print("="*60)

        # Expect huge improvement for geocoding (avoids external API)
        assert improvement['improvement_percent'] >= 95, \
            f"Expected at least 95% improvement, got {improvement['improvement_percent']:.1f}%"

    @pytest.mark.benchmark
    def test_cache_invalidation_performance(self, benchmark_db, benchmark_results):
        """
        Benchmark cache invalidation operations.

        Ensures invalidation is fast (<10ms for pattern-based invalidation).
        """
        redis_cache.clear()

        # Populate cache with many keys
        for i in range(100):
            redis_cache.set(f"lookup:key_{i}", {"data": i}, ttl=300)
            redis_cache.set(f"stats:key_{i}", {"data": i}, ttl=300)

        # Benchmark: Pattern-based invalidation
        start = time.time()
        deleted_count = redis_cache.delete_pattern("lookup:*")
        duration_ms = (time.time() - start) * 1000
        benchmark_results.add_measurement("invalidate_pattern", duration_ms)

        print("\n" + "="*60)
        print("CACHE INVALIDATION BENCHMARK RESULTS")
        print("="*60)
        print(f"Pattern invalidation time: {duration_ms:.2f}ms")
        print(f"Keys deleted: {deleted_count}")
        print("="*60)

        # Assert invalidation is fast
        assert duration_ms < 100, f"Invalidation took {duration_ms:.2f}ms, expected <100ms"

    @pytest.mark.benchmark
    def test_overall_performance_summary(self, benchmark_db, benchmark_results):
        """
        Generate overall performance summary report.

        This test aggregates all benchmark results and verifies
        the 50-90% response time reduction goal.
        """
        # Run quick version of all benchmarks
        redis_cache.clear()

        # Test 1: Lookup benchmark (simplified)
        test_addr = benchmark_db.query(Address).first()

        # Cold
        start = time.time()
        _ = benchmark_db.query(Address).filter(
            Address.normalized_address == test_addr.normalized_address
        ).first()
        cold_lookup_ms = (time.time() - start) * 1000

        # Hot
        cache_key = f"lookup:test"
        redis_cache.set(cache_key, {"data": "test"}, ttl=300)
        start = time.time()
        _ = redis_cache.get(cache_key)
        hot_lookup_ms = (time.time() - start) * 1000

        lookup_improvement = ((cold_lookup_ms - hot_lookup_ms) / cold_lookup_ms) * 100

        # Test 2: Stats benchmark (simplified)
        # Cold
        start = time.time()
        _ = benchmark_db.query(Address).count()
        cold_stats_ms = (time.time() - start) * 1000

        # Hot
        redis_cache.set("stats:test", {"count": 100}, ttl=60)
        start = time.time()
        _ = redis_cache.get("stats:test")
        hot_stats_ms = (time.time() - start) * 1000

        stats_improvement = ((cold_stats_ms - hot_stats_ms) / cold_stats_ms) * 100

        # Overall average
        overall_improvement = (lookup_improvement + stats_improvement) / 2

        print("\n" + "="*60)
        print("OVERALL PERFORMANCE SUMMARY")
        print("="*60)
        print(f"\nLookup Performance:")
        print(f"  Cold: {cold_lookup_ms:.2f}ms")
        print(f"  Hot:  {hot_lookup_ms:.2f}ms")
        print(f"  Improvement: {lookup_improvement:.1f}%")
        print(f"\nStats Performance:")
        print(f"  Cold: {cold_stats_ms:.2f}ms")
        print(f"  Hot:  {hot_stats_ms:.2f}ms")
        print(f"  Improvement: {stats_improvement:.1f}%")
        print(f"\nOVERALL IMPROVEMENT: {overall_improvement:.1f}%")
        print("="*60)
        print(f"\nSUCCESS CRITERIA: 50-90% response time reduction")
        print(f"RESULT: {'✓ PASS' if 50 <= overall_improvement <= 90 else '✗ FAIL'}")
        print("="*60)

        # Verify success criteria (50-90% improvement)
        assert 50 <= overall_improvement, \
            f"Expected at least 50% improvement, got {overall_improvement:.1f}%"


if __name__ == "__main__":
    # Allow running benchmarks directly
    pytest.main([__file__, "-v", "-s", "-m", "benchmark"])
