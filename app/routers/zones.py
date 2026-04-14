"""Zone map API — returns H3-tessellated GeoJSON for pickup day visualization.

Data source priority:
1. Supabase schedule_reports (3.4M+ real addresses) if configured
2. CSV fallback (sample data) if Supabase unavailable
"""

import csv
import logging
from pathlib import Path
from typing import Optional

import h3
from fastapi import APIRouter, HTTPException, Query

from app.supabase_client import fetch_city_addresses, is_configured as supabase_ok

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/zones", tags=["zones"])

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# Day-of-week palette (matches Mapbox GL layer paint in the frontend)
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

# H3 resolution 7 ≈ 5.16 km² avg hex area — good for city-level view
H3_RESOLUTION = 7


def _load_city_addresses(city_slug: str) -> list[dict]:
    """Load addresses for a city.

    Tries Supabase first (3.4M+ real addresses). Falls back to CSV
    if Supabase is unavailable or returns no data.
    """
    # --- Supabase (primary) ---
    if supabase_ok():
        supa_rows = fetch_city_addresses(city_slug, limit=5000, require_coords=True)
        if supa_rows:
            # Filter to rows that have valid coordinates (needed for H3)
            return [r for r in supa_rows if r.get("lat") and r.get("lon")]

    # --- CSV fallback ---
    csv_path = DATA_DIR / "addresses_normalized.csv"
    if not csv_path.exists():
        return []

    slug_to_name = {
        "san_diego": "San Diego", "san-diego": "San Diego",
        "houston": "Houston", "phoenix": "Phoenix", "austin": "Austin",
        "boston": "Boston", "denver": "Denver",
        "new_york": "New York", "new-york": "New York",
        "los_angeles": "Los Angeles", "los-angeles": "Los Angeles",
        "philadelphia": "Philadelphia",
        "san_antonio": "San Antonio", "san-antonio": "San Antonio",
        "dallas": "Dallas",
        "oklahoma_city": "Oklahoma City", "oklahoma-city": "Oklahoma City",
        "charlotte": "Charlotte", "columbus": "Columbus",
        "chicago": "Chicago", "seattle": "Seattle",
        "portland": "Portland", "minneapolis": "Minneapolis",
        "detroit": "Detroit", "atlanta": "Atlanta", "miami": "Miami",
        "brawley": "Brawley", "el_centro": "El Centro", "el-centro": "El Centro",
        "calexico": "Calexico", "holtville": "Holtville", "imperial": "Imperial",
    }
    target_name = slug_to_name.get(city_slug.lower(), city_slug.replace("-", " ").replace("_", " ").title())

    addresses = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("city_name", "").strip() == target_name:
                try:
                    addresses.append({
                        "lat": float(row["lat"]),
                        "lon": float(row["lon"]),
                        "street": row.get("street_normalized", row.get("street", "")),
                        "house": row.get("house_number", ""),
                    })
                except (ValueError, KeyError):
                    continue
    return addresses


def _assign_day(h3_index: str, lon_min: float, lon_max: float) -> str:
    """Deterministically assign a pickup day based on H3 index.

    Uses the hex center longitude to divide the city into 5 east-to-west
    stripes, each mapped to a weekday.  This produces a realistic pattern
    where adjacent zones share a day and the schedule sweeps across the city.

    ``lon_min`` / ``lon_max`` are the extent of the city's address data so
    the bucketing adapts to any city, not just San Diego.
    """
    _lat, lon = h3.cell_to_latlng(h3_index)
    span = lon_max - lon_min
    if span == 0:
        return DAYS[0]
    t = max(0.0, min(1.0, (lon - lon_min) / span))
    day_idx = min(4, int(t * 5))
    return DAYS[day_idx]


def _build_geojson(city_slug: str) -> dict:
    """Build a GeoJSON FeatureCollection of H3 hex zones for a city."""
    addresses = _load_city_addresses(city_slug)
    if not addresses:
        raise HTTPException(status_code=404, detail=f"No address data for city: {city_slug}")

    # Compute longitude extent for day-assignment bucketing
    lons = [a["lon"] for a in addresses]
    lon_min = min(lons) - 0.02  # small buffer
    lon_max = max(lons) + 0.02

    # Index every address into an H3 cell
    hex_addresses: dict[str, list[dict]] = {}
    for addr in addresses:
        idx = h3.latlng_to_cell(addr["lat"], addr["lon"], H3_RESOLUTION)
        hex_addresses.setdefault(idx, []).append(addr)

    features = []
    for h3_index, addrs in hex_addresses.items():
        # Get hex boundary as GeoJSON-compatible polygon ring
        boundary = h3.cell_to_boundary(h3_index)
        # h3 returns [(lat, lng), ...] — GeoJSON needs [[lng, lat], ...]
        ring = [[lng, lat] for lat, lng in boundary]
        ring.append(ring[0])  # close the ring

        # Use real collection_day from Supabase if available, else compute
        real_days = [a.get("collection_day", "").strip().title() for a in addrs if a.get("collection_day")]
        if real_days:
            # Majority vote for the hex
            from collections import Counter
            day = Counter(real_days).most_common(1)[0][0]
            if day not in DAYS:
                day = _assign_day(h3_index, lon_min, lon_max)
        else:
            day = _assign_day(h3_index, lon_min, lon_max)

        features.append({
            "type": "Feature",
            "properties": {
                "h3_index": h3_index,
                "pickup_day": day,
                "address_count": len(addrs),
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [ring],
            },
        })

    return {
        "type": "FeatureCollection",
        "metadata": {
            "city": city_slug,
            "hex_resolution": H3_RESOLUTION,
            "total_hexes": len(features),
            "total_addresses": len(addresses),
        },
        "features": features,
    }


# In-memory cache so repeated requests don't re-parse CSV
_cache: dict[str, dict] = {}


@router.get("/{city}")
async def get_zones(
    city: str,
    resolution: Optional[int] = Query(None, ge=4, le=10, description="H3 resolution (4-10)"),
):
    """Return GeoJSON FeatureCollection of H3 hex pickup zones for a city."""
    global H3_RESOLUTION

    cache_key = f"{city}:{resolution or H3_RESOLUTION}"
    if cache_key in _cache:
        return _cache[cache_key]

    # Allow caller to override resolution
    old_res = H3_RESOLUTION
    if resolution is not None:
        H3_RESOLUTION = resolution

    try:
        geojson = _build_geojson(city)
    finally:
        H3_RESOLUTION = old_res

    _cache[cache_key] = geojson
    return geojson
