"""Dynamic city pages — serves /schedule/{city} and redirects /{city}."""

import csv
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

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
    "portland":       {"name": "Portland",       "state": "Oregon",         "state_abbr": "OR", "center_lat": "45.52", "center_lng": "-122.68", "zoom": "12", "sample": "500 Burnside St"},
    "minneapolis":    {"name": "Minneapolis",    "state": "Minnesota",      "state_abbr": "MN", "center_lat": "44.98", "center_lng": "-93.27", "zoom": "12", "sample": "300 Hennepin Ave"},
    "detroit":        {"name": "Detroit",         "state": "Michigan",       "state_abbr": "MI", "center_lat": "42.33", "center_lng": "-83.05", "zoom": "12", "sample": "1000 Woodward Ave"},
    "atlanta":        {"name": "Atlanta",         "state": "Georgia",        "state_abbr": "GA", "center_lat": "33.75", "center_lng": "-84.39", "zoom": "12", "sample": "200 Peachtree St"},
    "miami":          {"name": "Miami",           "state": "Florida",        "state_abbr": "FL", "center_lat": "25.76", "center_lng": "-80.19", "zoom": "12", "sample": "100 Biscayne Blvd"},
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


def _normalize_slug(raw: str) -> str | None:
    """Normalize a city slug and return the canonical underscore form."""
    slug = raw.lower().replace("-", "_")
    return slug if slug in CITY_META else None


def _render_city(slug: str) -> str:
    """Render a city page from the template."""
    meta = CITY_META[slug]
    addr_count = _count_addresses(meta["name"])
    html = _get_template()
    return (
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


@router.get("/schedule/{city_slug}", response_class=HTMLResponse)
async def schedule_city_page(city_slug: str):
    """Primary city page at /schedule/{city} — matches production URL pattern."""
    slug = _normalize_slug(city_slug)
    if slug is None:
        raise HTTPException(status_code=404, detail=f"City not found: {city_slug}")
    return _render_city(slug)


@router.get("/{city_slug}", response_class=HTMLResponse)
async def city_page_redirect(city_slug: str):
    """Redirect /{city} → /schedule/{city} (canonical URL)."""
    slug = _normalize_slug(city_slug)
    if slug is None:
        raise HTTPException(status_code=404, detail=f"City not found: {city_slug}")
    return RedirectResponse(url=f"/schedule/{slug.replace('_', '-')}", status_code=301)
