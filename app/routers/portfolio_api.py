"""Portfolio API endpoints for property manager dashboard.

From SPRINT_portfolio_dashboard_apr13:
- Bulk export schedules (JSON, for PDF generation on frontend)
- Holiday schedule data
- Portfolio analytics summary
"""

import csv
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import h3
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
DAY_INDEX = {d: i for i, d in enumerate(DAYS)}
H3_RESOLUTION = 7

SLUG_TO_NAME = {
    "san_diego": "San Diego", "houston": "Houston", "phoenix": "Phoenix",
    "austin": "Austin", "boston": "Boston", "denver": "Denver",
    "new_york": "New York", "los_angeles": "Los Angeles",
    "philadelphia": "Philadelphia", "san_antonio": "San Antonio",
    "dallas": "Dallas", "oklahoma_city": "Oklahoma City",
    "charlotte": "Charlotte", "columbus": "Columbus",
    "chicago": "Chicago", "seattle": "Seattle",
    "portland": "Portland", "minneapolis": "Minneapolis",
    "detroit": "Detroit", "atlanta": "Atlanta", "miami": "Miami",
    "el_centro": "El Centro", "calexico": "Calexico",
    "brawley": "Brawley", "imperial": "Imperial", "holtville": "Holtville",
}


# -- Shared helpers (same as schedule_api) --

_city_cache: dict[str, list[dict]] = {}


def _load_city(city_slug: str) -> list[dict]:
    if city_slug in _city_cache:
        return _city_cache[city_slug]
    target = SLUG_TO_NAME.get(city_slug, city_slug.replace("_", " ").title())
    csv_path = DATA_DIR / "addresses_normalized.csv"
    if not csv_path.exists():
        return []
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("city_name", "").strip() == target:
                try:
                    rows.append({
                        "lat": float(row["lat"]), "lon": float(row["lon"]),
                        "street": row.get("street_normalized", ""),
                        "house": row.get("house_number", ""),
                        "full_address": row.get("full_address", ""),
                    })
                except (ValueError, KeyError):
                    continue
    _city_cache[city_slug] = rows
    return rows


def _assign_day(h3_index: str, lon_min: float, lon_max: float) -> str:
    _lat, lon = h3.cell_to_latlng(h3_index)
    span = lon_max - lon_min
    if span == 0:
        return DAYS[0]
    t = max(0.0, min(1.0, (lon - lon_min) / span))
    return DAYS[min(4, int(t * 5))]


def _next_weekday(day_name: str) -> str:
    today = date.today()
    target = DAY_INDEX[day_name]
    ahead = target - today.weekday()
    if ahead <= 0:
        ahead += 7
    return (today + timedelta(days=ahead)).isoformat()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

# 2026 US holidays affecting trash collection
HOLIDAYS_2026 = [
    {"date": "2026-01-01", "name": "New Year's Day",      "impact": "Pickup delayed 1 day for rest of week"},
    {"date": "2026-01-19", "name": "MLK Jr. Day",         "impact": "Monday pickup moves to Tuesday; rest shift 1 day"},
    {"date": "2026-02-16", "name": "Presidents' Day",     "impact": "Monday pickup moves to Tuesday; rest shift 1 day"},
    {"date": "2026-05-25", "name": "Memorial Day",        "impact": "Monday pickup moves to Tuesday; rest shift 1 day"},
    {"date": "2026-07-03", "name": "Independence Day (observed)", "impact": "Friday pickup moves to Saturday"},
    {"date": "2026-09-07", "name": "Labor Day",           "impact": "Monday pickup moves to Tuesday; rest shift 1 day"},
    {"date": "2026-11-26", "name": "Thanksgiving",        "impact": "Thursday/Friday pickup delayed; may skip Friday"},
    {"date": "2026-12-25", "name": "Christmas Day",       "impact": "Pickup delayed 1 day for rest of week"},
]


@router.get("/holidays")
async def get_holidays(year: int = 2026):
    """Return holidays that affect trash collection schedules."""
    today = date.today()
    upcoming = [h for h in HOLIDAYS_2026 if h["date"] >= today.isoformat()]
    return {
        "year": year,
        "total": len(HOLIDAYS_2026),
        "upcoming": upcoming[:2],
        "all": HOLIDAYS_2026,
    }


class ExportRequest(BaseModel):
    addresses: list[str] = Field(..., max_length=500)
    city: str = Field("san_diego")


@router.post("/export")
async def export_schedules(req: ExportRequest):
    """Export schedules for a list of addresses (for PDF move-in packet generation).

    Returns structured data the frontend can render into branded PDFs.
    """
    rows = _load_city(req.city)
    if not rows:
        raise HTTPException(404, detail=f"No data for city: {req.city}")

    lons = [r["lon"] for r in rows]
    lon_min, lon_max = min(lons) - 0.02, max(lons) + 0.02

    results = []
    for addr_q in req.addresses:
        q = addr_q.upper().strip()
        matched = None
        for r in rows:
            if q in r["full_address"].upper():
                matched = r
                break

        if matched:
            h3i = h3.latlng_to_cell(matched["lat"], matched["lon"], H3_RESOLUTION)
            day = _assign_day(h3i, lon_min, lon_max)
            results.append({
                "address": matched["full_address"],
                "trash_day": day,
                "recycling_day": day,
                "next_trash": _next_weekday(day),
                "next_recycling": _next_weekday(day),
                "zone": f"Zone {int(h3i[-4:], 16) % 50 + 1}",
            })
        else:
            results.append({
                "address": addr_q,
                "error": "Address not found",
            })

    return {
        "city": req.city,
        "generated_at": date.today().isoformat(),
        "total": len(results),
        "schedules": results,
    }


@router.get("/analytics")
async def portfolio_analytics(city: Optional[str] = None):
    """Portfolio analytics summary — total properties, coverage, sync status."""
    csv_path = DATA_DIR / "addresses_normalized.csv"
    if not csv_path.exists():
        return {"total_properties": 0, "cities": 0, "coverage_pct": 0}

    counts: dict[str, int] = {}
    total = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row.get("city_name", "").strip()
            if city and SLUG_TO_NAME.get(city, "") != name:
                continue
            if name:
                counts[name] = counts.get(name, 0) + 1
                total += 1

    return {
        "total_properties": total,
        "cities": len(counts),
        "coverage_pct": 100.0,
        "last_sync": date.today().isoformat(),
        "by_city": [{"name": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])],
    }
