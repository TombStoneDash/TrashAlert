"""Public lookup API — GET /api/lookup for property manager integrations."""

import csv
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import h3
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["lookup"])

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
DAY_INDEX = {d: i for i, d in enumerate(DAYS)}

H3_RESOLUTION = 7


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_city_addresses(city_slug: str) -> list[dict]:
    """Load addresses for a city from the normalized CSV."""
    csv_path = DATA_DIR / "addresses_normalized.csv"
    if not csv_path.exists():
        return []

    slug_to_name = {
        "san_diego": "San Diego",
        "san-diego": "San Diego",
        "brawley": "Brawley",
        "el_centro": "El Centro",
        "el-centro": "El Centro",
        "calexico": "Calexico",
        "holtville": "Holtville",
        "imperial": "Imperial",
        "houston": "Houston",
        "phoenix": "Phoenix",
        "austin": "Austin",
        "boston": "Boston",
        "denver": "Denver",
    }
    target_name = slug_to_name.get(
        city_slug.lower(),
        city_slug.replace("-", " ").replace("_", " ").title(),
    )

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
                        "city_name": target_name,
                        "full_address": row.get("full_address", ""),
                    })
                except (ValueError, KeyError):
                    continue
    return addresses


def _assign_day(h3_index: str, lon_min: float, lon_max: float) -> str:
    """Deterministically assign a pickup day based on H3 index longitude."""
    _lat, lon = h3.cell_to_latlng(h3_index)
    span = lon_max - lon_min
    if span == 0:
        return DAYS[0]
    t = max(0.0, min(1.0, (lon - lon_min) / span))
    day_idx = min(4, int(t * 5))
    return DAYS[day_idx]


def _zone_label(h3_index: str) -> str:
    """Derive a human-readable zone label from the H3 index."""
    # Use last 4 hex digits to create a zone number (1-based, mod 50)
    num = int(h3_index[-4:], 16) % 50 + 1
    return f"Zone {num}"


def _next_pickup(day_name: str, after: Optional[date] = None) -> str:
    """Return the next occurrence of `day_name` as YYYY-MM-DD."""
    today = after or date.today()
    target = DAY_INDEX[day_name]  # 0=Mon … 4=Fri
    days_ahead = target - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return (today + timedelta(days=days_ahead)).isoformat()


def _match_address(query: str, addresses: list[dict]) -> Optional[dict]:
    """Find the best matching address from the list.

    Matching strategy:
    1. Try exact substring match on full_address
    2. Try matching house number + street name tokens
    """
    q = query.upper().strip()

    # Pass 1: exact substring on full_address
    for addr in addresses:
        if q in addr["full_address"].upper():
            return addr

    # Pass 2: extract numeric house number and street tokens from query
    parts = q.split()
    house_num = None
    street_tokens = []
    for p in parts:
        if p.isdigit() and house_num is None:
            house_num = p
        else:
            # Skip common suffixes and state/zip for matching
            if p not in {"ST", "AVE", "DR", "RD", "LN", "BLVD", "CT", "PL",
                         "WAY", "CIR", "CA", "USA"}:
                street_tokens.append(p)

    for addr in addresses:
        if house_num and addr["house"] != house_num:
            continue
        addr_street = addr["street"].upper()
        if all(tok in addr_street for tok in street_tokens):
            return addr

    # Pass 3: relaxed — just match street tokens ignoring house number
    if street_tokens:
        for addr in addresses:
            addr_street = addr["street"].upper()
            if all(tok in addr_street for tok in street_tokens):
                return addr

    return None


# In-memory cache
_city_cache: dict[str, list[dict]] = {}


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/lookup")
async def api_lookup(
    address: str = Query(..., description="Street address to look up"),
    city: str = Query("san_diego", description="City slug (e.g. san_diego)"),
):
    """Look up the trash pickup schedule for an address.

    Returns the matched address, pickup day, zone, and next pickup date.
    This is the core API for property-manager integrations.
    """
    # Load (and cache) city data
    if city not in _city_cache:
        _city_cache[city] = _load_city_addresses(city)

    addresses = _city_cache[city]
    if not addresses:
        raise HTTPException(status_code=404, detail=f"No data for city: {city}")

    matched = _match_address(address, addresses)
    if not matched:
        raise HTTPException(
            status_code=404,
            detail=f"Address not found: {address} in {city}",
        )

    # Compute city longitude extent for day bucketing
    lons = [a["lon"] for a in addresses]
    lon_min = min(lons) - 0.02
    lon_max = max(lons) + 0.02

    # Determine zone via H3
    h3_index = h3.latlng_to_cell(matched["lat"], matched["lon"], H3_RESOLUTION)
    day = _assign_day(h3_index, lon_min, lon_max)
    zone = _zone_label(h3_index)

    return {
        "address": matched["full_address"],
        "pickup_day": day,
        "zone": zone,
        "next_pickup": _next_pickup(day),
    }
