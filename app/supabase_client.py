"""Supabase REST client for querying schedule_reports.

Uses the PostgREST API directly (no SDK needed). Requires:
  SUPABASE_URL  — e.g. https://qsuzfemakaaroeakyick.supabase.co
  SUPABASE_KEY  — service_role or anon key

The schedule_reports table schema:
  id, address, city, state, zip_code, neighborhood,
  collection_day, recycling_week, source, hauler, lat, lng
"""

import logging
import os
from typing import Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv(
    "SUPABASE_URL",
    os.getenv("NEXT_PUBLIC_SUPABASE_URL", "https://qsuzfemakaaroeakyick.supabase.co"),
)
SUPABASE_KEY = os.getenv(
    "SUPABASE_KEY",
    os.getenv("SUPABASE_SERVICE_KEY", os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")),
)

REST_BASE = f"{SUPABASE_URL}/rest/v1"

# City slug → Supabase city column value.
# Supabase uses lowercase hyphenated slugs for most cities.
SLUG_TO_SUPA = {
    "san_diego": "san-diego",
    "san-diego": "san-diego",
    "houston": "houston",
    "phoenix": "phoenix",
    "austin": "austin",
    "boston": "boston",
    "denver": "denver",
    "new_york": "new-york",
    "new-york": "new-york",
    "los_angeles": "los-angeles",
    "los-angeles": "los-angeles",
    "philadelphia": "philadelphia",
    "san_antonio": "san-antonio",
    "san-antonio": "san-antonio",
    "dallas": "dallas",
    "oklahoma_city": "oklahoma-city",
    "oklahoma-city": "oklahoma-city",
    "charlotte": "charlotte",
    "columbus": "columbus",
    "chicago": "chicago",
    "seattle": "seattle",
    "portland": "portland",
    "minneapolis": "minneapolis",
    "detroit": "detroit",
    "atlanta": "atlanta",
    "miami": "miami",
    "san_francisco": "san-francisco",
    "san-francisco": "san-francisco",
}


def _headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }


def is_configured() -> bool:
    """Return True if Supabase credentials are set."""
    return bool(SUPABASE_URL and SUPABASE_KEY)


def fetch_city_addresses(
    city_slug: str,
    limit: int = 5000,
    require_coords: bool = False,
) -> list[dict]:
    """Fetch addresses for a city from Supabase schedule_reports.

    Returns list of dicts with keys: address, city, lat, lon,
    collection_day, neighborhood, zip_code.
    """
    supa_city = SLUG_TO_SUPA.get(city_slug.lower().replace("-", "_"), city_slug.lower())

    select = "address,city,lat,lng,collection_day,neighborhood,zip_code"
    url = f"{REST_BASE}/schedule_reports?city=eq.{quote(supa_city)}&select={select}&limit={limit}"

    if require_coords:
        url += "&lat=not.is.null&lng=not.is.null"

    try:
        resp = requests.get(url, headers=_headers(), timeout=10)
        resp.raise_for_status()
        rows = resp.json()
    except Exception as e:
        logger.error(f"Supabase query failed for {city_slug}: {e}")
        return []

    # Normalize to the format our routers expect
    result = []
    for row in rows:
        try:
            lat = float(row["lat"]) if row.get("lat") else None
            lon = float(row["lng"]) if row.get("lng") else None

            # Parse address into house number + street
            addr_parts = (row.get("address") or "").split(",")[0].strip()
            tokens = addr_parts.split(" ", 1)
            house = tokens[0] if tokens[0].isdigit() else ""
            street = tokens[1] if len(tokens) > 1 else addr_parts

            result.append({
                "lat": lat,
                "lon": lon,
                "street": street.upper(),
                "house": house,
                "city_name": row.get("city", supa_city),
                "full_address": row.get("address", ""),
                "collection_day": row.get("collection_day", ""),
                "neighborhood": row.get("neighborhood", ""),
                "zip_code": row.get("zip_code", ""),
            })
        except (ValueError, TypeError, IndexError):
            continue

    return result


def fetch_city_count(city_slug: str) -> int:
    """Get the exact address count for a city (fast — uses Prefer: count=exact)."""
    supa_city = SLUG_TO_SUPA.get(city_slug.lower().replace("-", "_"), city_slug.lower())

    url = f"{REST_BASE}/schedule_reports?city=eq.{quote(supa_city)}&select=id"
    headers = {**_headers(), "Prefer": "count=exact", "Range": "0-0"}

    try:
        resp = requests.head(url, headers=headers, timeout=10)
        content_range = resp.headers.get("content-range", "")
        # Format: "0-0/12345"
        if "/" in content_range:
            return int(content_range.split("/")[1])
    except Exception as e:
        logger.error(f"Supabase count failed for {city_slug}: {e}")

    return 0


def fetch_total_count() -> int:
    """Get total address count across all cities."""
    url = f"{REST_BASE}/schedule_reports?select=id"
    headers = {**_headers(), "Prefer": "count=exact", "Range": "0-0"}

    try:
        resp = requests.head(url, headers=headers, timeout=10)
        content_range = resp.headers.get("content-range", "")
        if "/" in content_range:
            return int(content_range.split("/")[1])
    except Exception as e:
        logger.error(f"Supabase total count failed: {e}")

    return 0


def fetch_all_city_counts() -> dict[str, int]:
    """Get address counts for all known cities.

    Returns dict of {slug: count}. Uses individual queries since
    Supabase doesn't support GROUP BY via REST.
    """
    counts = {}
    for slug in set(SLUG_TO_SUPA.values()):
        count = fetch_city_count(slug)
        if count > 0:
            counts[slug] = count
    return counts
