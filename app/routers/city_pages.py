"""Dynamic city pages — serves /{city_slug} for every city with address data."""

import csv
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["city-pages"])

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
TEMPLATE_PATH = Path(__file__).resolve().parent.parent.parent / "frontend" / "city_page.html"

# City metadata: slug -> {name, state, state_abbr, center_lat, center_lng, zoom, sample}
CITY_META = {
    "san_diego":  {"name": "San Diego",  "state": "California",    "state_abbr": "CA", "center_lat": "32.72", "center_lng": "-117.16", "zoom": "11", "sample": "1016 Park Blvd"},
    "houston":    {"name": "Houston",    "state": "Texas",          "state_abbr": "TX", "center_lat": "29.76", "center_lng": "-95.37",  "zoom": "11", "sample": "1200 Main St"},
    "phoenix":    {"name": "Phoenix",    "state": "Arizona",        "state_abbr": "AZ", "center_lat": "33.45", "center_lng": "-112.07", "zoom": "11", "sample": "2400 Central Ave"},
    "austin":     {"name": "Austin",     "state": "Texas",          "state_abbr": "TX", "center_lat": "30.27", "center_lng": "-97.74",  "zoom": "11", "sample": "500 Congress Ave"},
    "boston":      {"name": "Boston",     "state": "Massachusetts",  "state_abbr": "MA", "center_lat": "42.36", "center_lng": "-71.06",  "zoom": "12", "sample": "100 Beacon St"},
    "denver":     {"name": "Denver",     "state": "Colorado",       "state_abbr": "CO", "center_lat": "39.74", "center_lng": "-104.99", "zoom": "11", "sample": "1500 Colfax Ave"},
    "el_centro":  {"name": "El Centro",  "state": "California",    "state_abbr": "CA", "center_lat": "32.79", "center_lng": "-115.56", "zoom": "13", "sample": "200 Main St"},
    "calexico":   {"name": "Calexico",   "state": "California",    "state_abbr": "CA", "center_lat": "32.68", "center_lng": "-115.50", "zoom": "13", "sample": "100 1st St"},
    "brawley":    {"name": "Brawley",    "state": "California",    "state_abbr": "CA", "center_lat": "32.98", "center_lng": "-115.53", "zoom": "13", "sample": "1115 Imperial Ave"},
    "imperial":   {"name": "Imperial",   "state": "California",    "state_abbr": "CA", "center_lat": "32.85", "center_lng": "-115.57", "zoom": "13", "sample": "200 Imperial Ave"},
    "holtville":  {"name": "Holtville",  "state": "California",    "state_abbr": "CA", "center_lat": "32.81", "center_lng": "-115.38", "zoom": "14", "sample": "100 5th St"},
    "new_york":       {"name": "New York",       "state": "New York",       "state_abbr": "NY", "center_lat": "40.71", "center_lng": "-73.99", "zoom": "11", "sample": "350 5th Ave"},
    "los_angeles":    {"name": "Los Angeles",    "state": "California",     "state_abbr": "CA", "center_lat": "34.05", "center_lng": "-118.24", "zoom": "11", "sample": "600 Wilshire Blvd"},
    "philadelphia":   {"name": "Philadelphia",   "state": "Pennsylvania",   "state_abbr": "PA", "center_lat": "39.95", "center_lng": "-75.17", "zoom": "12", "sample": "1500 Market St"},
    "san_antonio":    {"name": "San Antonio",    "state": "Texas",          "state_abbr": "TX", "center_lat": "29.42", "center_lng": "-98.49", "zoom": "11", "sample": "300 Alamo St"},
    "dallas":         {"name": "Dallas",         "state": "Texas",          "state_abbr": "TX", "center_lat": "32.78", "center_lng": "-96.80", "zoom": "11", "sample": "500 Main St"},
    "oklahoma_city":  {"name": "Oklahoma City",  "state": "Oklahoma",       "state_abbr": "OK", "center_lat": "35.47", "center_lng": "-97.52", "zoom": "11", "sample": "200 Robinson Ave"},
    "charlotte":      {"name": "Charlotte",      "state": "North Carolina", "state_abbr": "NC", "center_lat": "35.23", "center_lng": "-80.84", "zoom": "11", "sample": "100 Tryon St"},
    "columbus":       {"name": "Columbus",       "state": "Ohio",           "state_abbr": "OH", "center_lat": "39.96", "center_lng": "-82.99", "zoom": "12", "sample": "100 High St"},
    "chicago":        {"name": "Chicago",        "state": "Illinois",       "state_abbr": "IL", "center_lat": "41.88", "center_lng": "-87.63", "zoom": "11", "sample": "233 Michigan Ave"},
    "seattle":        {"name": "Seattle",        "state": "Washington",     "state_abbr": "WA", "center_lat": "47.61", "center_lng": "-122.33", "zoom": "12", "sample": "400 Pike St"},
}


def _count_addresses(city_name: str) -> int:
    """Count addresses for a city in the normalized CSV."""
    csv_path = DATA_DIR / "addresses_normalized.csv"
    if not csv_path.exists():
        return 0
    count = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("city_name", "").strip() == city_name:
                count += 1
    return count


# Cache template once
_template_cache: str | None = None


def _get_template() -> str:
    global _template_cache
    if _template_cache is None:
        _template_cache = TEMPLATE_PATH.read_text(encoding="utf-8")
    return _template_cache


@router.get("/{city_slug}", response_class=HTMLResponse)
async def city_page(city_slug: str):
    """Serve a dynamic city page with zone map and address lookup."""
    # Normalize slug
    slug = city_slug.lower().replace("-", "_")

    if slug not in CITY_META:
        raise HTTPException(status_code=404, detail=f"City not found: {city_slug}")

    meta = CITY_META[slug]
    addr_count = _count_addresses(meta["name"])

    if addr_count == 0:
        raise HTTPException(status_code=404, detail=f"No address data for: {meta['name']}")

    html = _get_template()
    html = (
        html
        .replace("{{CITY_NAME}}", meta["name"])
        .replace("{{STATE}}", meta["state"])
        .replace("{{STATE_ABBR}}", meta["state_abbr"])
        .replace("{{CITY_SLUG}}", slug)
        .replace("{{ADDRESS_COUNT}}", str(addr_count))
        .replace("{{CENTER_LAT}}", meta["center_lat"])
        .replace("{{CENTER_LNG}}", meta["center_lng"])
        .replace("{{ZOOM}}", meta["zoom"])
        .replace("{{SAMPLE_ADDRESS}}", meta["sample"])
    )
    return html
