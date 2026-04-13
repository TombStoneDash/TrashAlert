"""v1 Schedule & Bulk API — POST /api/v1/schedule, POST /api/v1/bulk."""

import csv
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import h3
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["v1"])

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
DAY_INDEX = {d: i for i, d in enumerate(DAYS)}
H3_RESOLUTION = 7

# Reuse the same slug map as lookup_api
SLUG_TO_NAME = {
    "san_diego": "San Diego", "houston": "Houston", "phoenix": "Phoenix",
    "austin": "Austin", "boston": "Boston", "denver": "Denver",
    "new_york": "New York", "los_angeles": "Los Angeles",
    "philadelphia": "Philadelphia", "san_antonio": "San Antonio",
    "dallas": "Dallas", "oklahoma_city": "Oklahoma City",
    "charlotte": "Charlotte", "columbus": "Columbus",
    "chicago": "Chicago", "seattle": "Seattle",
    "el_centro": "El Centro", "calexico": "Calexico",
    "brawley": "Brawley", "imperial": "Imperial", "holtville": "Holtville",
}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_city_cache: dict[str, list[dict]] = {}


def _load_city(city_slug: str) -> list[dict]:
    if city_slug in _city_cache:
        return _city_cache[city_slug]

    target = SLUG_TO_NAME.get(
        city_slug.lower(),
        city_slug.replace("-", " ").replace("_", " ").title(),
    )

    csv_path = DATA_DIR / "addresses_normalized.csv"
    if not csv_path.exists():
        return []

    addresses = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("city_name", "").strip() == target:
                try:
                    addresses.append({
                        "lat": float(row["lat"]),
                        "lon": float(row["lon"]),
                        "street": row.get("street_normalized", ""),
                        "house": row.get("house_number", ""),
                        "city_name": target,
                        "full_address": row.get("full_address", ""),
                    })
                except (ValueError, KeyError):
                    continue

    _city_cache[city_slug] = addresses
    return addresses


def _assign_day(h3_index: str, lon_min: float, lon_max: float) -> str:
    _lat, lon = h3.cell_to_latlng(h3_index)
    span = lon_max - lon_min
    if span == 0:
        return DAYS[0]
    t = max(0.0, min(1.0, (lon - lon_min) / span))
    return DAYS[min(4, int(t * 5))]


def _zone_label(h3_index: str) -> str:
    return f"Zone {int(h3_index[-4:], 16) % 50 + 1}"


def _next_weekday(day_name: str, after: Optional[date] = None) -> str:
    today = after or date.today()
    target = DAY_INDEX[day_name]
    days_ahead = target - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return (today + timedelta(days=days_ahead)).isoformat()


def _match_address(query: str, addresses: list[dict]) -> Optional[dict]:
    q = query.upper().strip()
    for addr in addresses:
        if q in addr["full_address"].upper():
            return addr
    parts = q.split()
    house_num = None
    street_tokens = []
    for p in parts:
        if p.isdigit() and house_num is None:
            house_num = p
        elif p not in {"ST", "AVE", "DR", "RD", "LN", "BLVD", "CT", "PL", "WAY", "CIR", "CA", "TX", "NY", "USA"}:
            street_tokens.append(p)
    for addr in addresses:
        if house_num and addr["house"] != house_num:
            continue
        if all(tok in addr["street"].upper() for tok in street_tokens):
            return addr
    if street_tokens:
        for addr in addresses:
            if all(tok in addr["street"].upper() for tok in street_tokens):
                return addr
    return None


def _build_schedule(matched: dict, addresses: list[dict]) -> dict:
    """Build full weekly schedule for a matched address."""
    lons = [a["lon"] for a in addresses]
    lon_min, lon_max = min(lons) - 0.02, max(lons) + 0.02

    h3_index = h3.latlng_to_cell(matched["lat"], matched["lon"], H3_RESOLUTION)
    trash_day = _assign_day(h3_index, lon_min, lon_max)
    trash_idx = DAY_INDEX[trash_day]

    # Recycling: same day as trash (common in most US cities)
    recycling_day = trash_day

    # Yard waste: day after trash, capped at Friday
    yard_idx = min(4, trash_idx + 1)
    yard_day = DAYS[yard_idx]

    # Bulk/large item: 1st and 3rd pickup day of month
    today = date.today()
    next_trash = date.fromisoformat(_next_weekday(trash_day))
    bulk_dates = []
    d = today.replace(day=1)
    while d.month == today.month:
        if d.weekday() == trash_idx:
            bulk_dates.append(d)
        d += timedelta(days=1)
    next_bulk = None
    for bd in bulk_dates[:2]:  # 1st and 3rd occurrence
        if bd >= today:
            next_bulk = bd.isoformat()
            break
    if bulk_dates and len(bulk_dates) >= 3:
        third = bulk_dates[2]
        if third >= today and (next_bulk is None or third < date.fromisoformat(next_bulk)):
            next_bulk = third.isoformat()

    return {
        "address": matched["full_address"],
        "zone": _zone_label(h3_index),
        "schedule": {
            "trash": {
                "day": trash_day,
                "next_pickup": _next_weekday(trash_day),
                "frequency": "weekly",
            },
            "recycling": {
                "day": recycling_day,
                "next_pickup": _next_weekday(recycling_day),
                "frequency": "weekly",
            },
            "yard_waste": {
                "day": yard_day,
                "next_pickup": _next_weekday(yard_day),
                "frequency": "weekly",
            },
            "bulk_items": {
                "day": trash_day,
                "next_pickup": next_bulk,
                "frequency": "1st and 3rd week of month",
            },
        },
    }


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ScheduleRequest(BaseModel):
    address: str = Field(..., description="Street address to look up")
    city: str = Field("san_diego", description="City slug")


class BulkRequest(BaseModel):
    addresses: list[str] = Field(..., description="List of addresses", max_length=500)
    city: str = Field("san_diego", description="City slug")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/schedule")
async def get_schedule(req: ScheduleRequest):
    """Return full weekly schedule for an address including recycling, yard waste, and bulk."""
    addresses = _load_city(req.city)
    if not addresses:
        raise HTTPException(status_code=404, detail=f"No data for city: {req.city}")

    matched = _match_address(req.address, addresses)
    if not matched:
        raise HTTPException(status_code=404, detail=f"Address not found: {req.address}")

    return _build_schedule(matched, addresses)


@router.post("/bulk")
async def bulk_lookup(req: BulkRequest):
    """Look up schedules for multiple addresses in one call.

    Accepts up to 500 addresses. Returns results and errors separately.
    """
    addresses = _load_city(req.city)
    if not addresses:
        raise HTTPException(status_code=404, detail=f"No data for city: {req.city}")

    results = []
    errors = []

    for addr_query in req.addresses:
        matched = _match_address(addr_query, addresses)
        if matched:
            results.append(_build_schedule(matched, addresses))
        else:
            errors.append({"address": addr_query, "error": "Not found"})

    return {
        "city": req.city,
        "total_requested": len(req.addresses),
        "total_found": len(results),
        "total_errors": len(errors),
        "results": results,
        "errors": errors,
    }
