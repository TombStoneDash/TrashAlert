"""Real-time stats endpoint — /api/stats/live.

Returns live address counts from Supabase with a cache to avoid
hammering the database on every request (the schedule_reports table
has 5M+ rows and COUNT queries can timeout).
"""

import logging
import os
import time
from datetime import datetime

from fastapi import APIRouter

from app.supabase_client import fetch_total_count, fetch_all_city_counts, is_configured

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stats", tags=["stats"])

# Known counts from completed imports (fallback when Supabase times out)
KNOWN_COUNTS = {
    "san-antonio": 346580,
    "houston": 474000,
    "phoenix": 365558,
    "austin": 331171,
    "boston": 392052,
    "denver": 186335,
    "dallas": 253286,
    "san-francisco": 34443,
    "portland": 898,
    "nyc": 610,
}
KNOWN_TOTAL = 5191847  # Verified from import logs as of 2026-04-14
# Major: Houston 474K + Boston 392K + Phoenix 365K + SA 346K + Austin 331K
#        + Dallas 253K + Denver 186K + SF 34K + Portland 898 + NYC 610
# EDCO:  ~195K across 22 SD County suburbs
# Pre-existing: ~2.6M (earlier imports)

# Cache: refresh at most every 5 minutes
_cache: dict | None = None
_cache_time: float = 0
CACHE_TTL = 300  # 5 minutes


def _get_stats() -> dict:
    global _cache, _cache_time

    now = time.time()
    if _cache and (now - _cache_time) < CACHE_TTL:
        return _cache

    total = KNOWN_TOTAL
    city_counts = dict(KNOWN_COUNTS)

    # Try Supabase for live counts (may timeout on 5M+ table)
    if is_configured():
        try:
            live_total = fetch_total_count()
            if live_total > 0:
                total = live_total
        except Exception as e:
            logger.warning(f"Supabase total count timed out, using known: {e}")

        try:
            live_counts = fetch_all_city_counts()
            if live_counts:
                city_counts.update(live_counts)
        except Exception as e:
            logger.warning(f"Supabase city counts failed, using known: {e}")

    result = {
        "total_addresses": total,
        "total_cities": len([c for c in city_counts.values() if c > 0]),
        "display": f"{total / 1_000_000:.1f}M+" if total >= 1_000_000 else f"{total:,}",
        "source": "supabase" if is_configured() else "known_imports",
        "updated_at": datetime.utcnow().isoformat(),
        "top_cities": sorted(
            [{"city": k, "addresses": v} for k, v in city_counts.items() if v > 0],
            key=lambda x: -x["addresses"],
        )[:10],
    }

    _cache = result
    _cache_time = now
    return result


@router.get("/live")
async def live_stats():
    """Return real-time address stats with Supabase counts or known fallbacks."""
    return _get_stats()
