"""Vercel serverless handler — lightweight FastAPI app for city pages and API.

This is a self-contained handler that serves city pages, the lookup
API, and the cities list WITHOUT importing the full app.main (which
pulls in heavy GIS/ML deps that exceed Vercel's 250 MB limit).

It reads directly from addresses_normalized.csv and the HTML templates.
"""

import csv
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import h3
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse, Response

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="TrashAlert", version="2.0.0")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
FRONTEND_DIR = PROJECT_ROOT / "frontend"

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
DAY_INDEX = {d: i for i, d in enumerate(DAYS)}
H3_RESOLUTION = 7

# ---------------------------------------------------------------------------
# City registry
# ---------------------------------------------------------------------------

CITY_META = {
    "san_diego":      {"name": "San Diego",      "state": "California",     "abbr": "CA", "lat": "32.72",  "lng": "-117.16", "zoom": "11", "sample": "1016 Park Blvd"},
    "houston":        {"name": "Houston",         "state": "Texas",          "abbr": "TX", "lat": "29.76",  "lng": "-95.37",  "zoom": "11", "sample": "1200 Main St"},
    "phoenix":        {"name": "Phoenix",         "state": "Arizona",        "abbr": "AZ", "lat": "33.45",  "lng": "-112.07", "zoom": "11", "sample": "2400 Central Ave"},
    "austin":         {"name": "Austin",          "state": "Texas",          "abbr": "TX", "lat": "30.27",  "lng": "-97.74",  "zoom": "11", "sample": "500 Congress Ave"},
    "boston":          {"name": "Boston",          "state": "Massachusetts",  "abbr": "MA", "lat": "42.36",  "lng": "-71.06",  "zoom": "12", "sample": "100 Beacon St"},
    "denver":         {"name": "Denver",          "state": "Colorado",       "abbr": "CO", "lat": "39.74",  "lng": "-104.99", "zoom": "11", "sample": "1500 Colfax Ave"},
    "new_york":       {"name": "New York",        "state": "New York",       "abbr": "NY", "lat": "40.71",  "lng": "-73.99",  "zoom": "11", "sample": "350 5th Ave"},
    "los_angeles":    {"name": "Los Angeles",     "state": "California",     "abbr": "CA", "lat": "34.05",  "lng": "-118.24", "zoom": "11", "sample": "600 Wilshire Blvd"},
    "philadelphia":   {"name": "Philadelphia",    "state": "Pennsylvania",   "abbr": "PA", "lat": "39.95",  "lng": "-75.17",  "zoom": "12", "sample": "1500 Market St"},
    "san_antonio":    {"name": "San Antonio",     "state": "Texas",          "abbr": "TX", "lat": "29.42",  "lng": "-98.49",  "zoom": "11", "sample": "300 Alamo St"},
    "dallas":         {"name": "Dallas",          "state": "Texas",          "abbr": "TX", "lat": "32.78",  "lng": "-96.80",  "zoom": "11", "sample": "500 Main St"},
    "oklahoma_city":  {"name": "Oklahoma City",   "state": "Oklahoma",       "abbr": "OK", "lat": "35.47",  "lng": "-97.52",  "zoom": "11", "sample": "200 Robinson Ave"},
    "charlotte":      {"name": "Charlotte",       "state": "North Carolina", "abbr": "NC", "lat": "35.23",  "lng": "-80.84",  "zoom": "11", "sample": "100 Tryon St"},
    "columbus":       {"name": "Columbus",        "state": "Ohio",           "abbr": "OH", "lat": "39.96",  "lng": "-82.99",  "zoom": "12", "sample": "100 High St"},
    "chicago":        {"name": "Chicago",         "state": "Illinois",       "abbr": "IL", "lat": "41.88",  "lng": "-87.63",  "zoom": "11", "sample": "233 Michigan Ave"},
    "seattle":        {"name": "Seattle",         "state": "Washington",     "abbr": "WA", "lat": "47.61",  "lng": "-122.33", "zoom": "12", "sample": "400 Pike St"},
    "el_centro":      {"name": "El Centro",       "state": "California",     "abbr": "CA", "lat": "32.79",  "lng": "-115.56", "zoom": "13", "sample": "200 Main St"},
    "calexico":       {"name": "Calexico",        "state": "California",     "abbr": "CA", "lat": "32.68",  "lng": "-115.50", "zoom": "13", "sample": "100 1st St"},
    "brawley":        {"name": "Brawley",         "state": "California",     "abbr": "CA", "lat": "32.98",  "lng": "-115.53", "zoom": "13", "sample": "1115 Imperial Ave"},
    "imperial":       {"name": "Imperial",        "state": "California",     "abbr": "CA", "lat": "32.85",  "lng": "-115.57", "zoom": "13", "sample": "200 Imperial Ave"},
    "holtville":      {"name": "Holtville",       "state": "California",     "abbr": "CA", "lat": "32.81",  "lng": "-115.38", "zoom": "14", "sample": "100 5th St"},
}

NAME_TO_SLUG = {m["name"]: slug for slug, m in CITY_META.items()}

# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------

_csv_rows: list[dict] | None = None


def _load_csv() -> list[dict]:
    global _csv_rows
    if _csv_rows is not None:
        return _csv_rows
    csv_path = DATA_DIR / "addresses_normalized.csv"
    if not csv_path.exists():
        _csv_rows = []
        return _csv_rows
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                rows.append({
                    "city_name": row.get("city_name", "").strip(),
                    "lat": float(row["lat"]),
                    "lon": float(row["lon"]),
                    "street": row.get("street_normalized", ""),
                    "house": row.get("house_number", ""),
                    "full_address": row.get("full_address", ""),
                })
            except (ValueError, KeyError):
                continue
    _csv_rows = rows
    return _csv_rows


def _city_rows(city_name: str) -> list[dict]:
    return [r for r in _load_csv() if r["city_name"] == city_name]


def _city_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in _load_csv():
        n = r["city_name"]
        counts[n] = counts.get(n, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assign_day(h3_index: str, lon_min: float, lon_max: float) -> str:
    _lat, lon = h3.cell_to_latlng(h3_index)
    span = lon_max - lon_min
    if span == 0:
        return DAYS[0]
    t = max(0.0, min(1.0, (lon - lon_min) / span))
    return DAYS[min(4, int(t * 5))]


def _zone_label(h3_index: str) -> str:
    return f"Zone {int(h3_index[-4:], 16) % 50 + 1}"


def _next_pickup(day_name: str) -> str:
    today = date.today()
    target = DAY_INDEX[day_name]
    ahead = target - today.weekday()
    if ahead <= 0:
        ahead += 7
    return (today + timedelta(days=ahead)).isoformat()


def _match_address(query: str, rows: list[dict]) -> Optional[dict]:
    q = query.upper().strip()
    for r in rows:
        if q in r["full_address"].upper():
            return r
    parts = q.split()
    house = next((p for p in parts if p.isdigit()), None)
    tokens = [p for p in parts if not p.isdigit() and p not in
              {"ST", "AVE", "DR", "RD", "LN", "BLVD", "CT", "PL", "WAY", "CA", "TX", "NY", "USA"}]
    for r in rows:
        if house and r["house"] != house:
            continue
        if all(t in r["street"].upper() for t in tokens):
            return r
    return None


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_tpl_cache: dict[str, str] = {}


def _template(name: str) -> str:
    if name not in _tpl_cache:
        _tpl_cache[name] = (FRONTEND_DIR / name).read_text(encoding="utf-8")
    return _tpl_cache[name]


# ---------------------------------------------------------------------------
# Routes — City pages
# ---------------------------------------------------------------------------
# Production URL pattern: /schedule/{city-slug} (hyphenated)
# Also support: /{city_slug} → 301 redirect to /schedule/{city-slug}


def _render_city(slug: str) -> str:
    """Render a city page from the template."""
    meta = CITY_META[slug]
    counts = _city_counts()
    addr_count = counts.get(meta["name"], 0)
    html = _template("city_page.html")
    return (
        html
        .replace("{{CITY_NAME}}", meta["name"])
        .replace("{{STATE}}", meta["state"])
        .replace("{{STATE_ABBR}}", meta["abbr"])
        .replace("{{CITY_SLUG}}", slug)
        .replace("{{ADDRESS_COUNT}}", str(addr_count))
        .replace("{{CENTER_LAT}}", meta["lat"])
        .replace("{{CENTER_LNG}}", meta["lng"])
        .replace("{{ZOOM}}", meta["zoom"])
        .replace("{{SAMPLE_ADDRESS}}", meta["sample"])
    )


def _normalize_slug(raw: str) -> str | None:
    """Normalize a city slug (hyphens or underscores) and return the canonical form."""
    slug = raw.lower().replace("-", "_")
    if slug in CITY_META:
        return slug
    return None


@app.get("/schedule/{city_slug}", response_class=HTMLResponse)
async def schedule_city_page(city_slug: str):
    """Primary city page route — matches production /schedule/{city} URL pattern."""
    slug = _normalize_slug(city_slug)
    if slug is None:
        raise HTTPException(status_code=404, detail=f"City not found: {city_slug}")
    return _render_city(slug)


# NOTE: /{city_slug} catch-all is registered LAST in this file (after all
# explicit routes like /narpm, /pricing, /about, /api/*, etc.) to avoid
# shadowing them.  See bottom of file.


# ---------------------------------------------------------------------------
# Routes — API
# ---------------------------------------------------------------------------

@app.get("/api/lookup")
async def api_lookup(
    address: str = Query(...),
    city: str = Query("san_diego"),
):
    slug = city.lower().replace("-", "_")
    city_name = CITY_META.get(slug, {}).get("name") or city.replace("_", " ").title()
    rows = _city_rows(city_name)
    if not rows:
        raise HTTPException(404, detail=f"No data for city: {city}")
    matched = _match_address(address, rows)
    if not matched:
        raise HTTPException(404, detail=f"Address not found: {address}")
    lons = [r["lon"] for r in rows]
    lon_min, lon_max = min(lons) - 0.02, max(lons) + 0.02
    h3i = h3.latlng_to_cell(matched["lat"], matched["lon"], H3_RESOLUTION)
    day = _assign_day(h3i, lon_min, lon_max)
    return {
        "address": matched["full_address"],
        "pickup_day": day,
        "zone": _zone_label(h3i),
        "next_pickup": _next_pickup(day),
    }


@app.get("/api/cities")
async def list_cities():
    counts = _city_counts()
    cities = []
    for slug, meta in CITY_META.items():
        cnt = counts.get(meta["name"], 0)
        if cnt > 0:
            cities.append({
                "slug": slug,
                "name": meta["name"],
                "state": meta["abbr"],
                "address_count": cnt,
                "addressCount": cnt,
                "providers": ["Municipal"],
            })
    cities.sort(key=lambda c: c["address_count"], reverse=True)
    return {"total_cities": len(cities), "total_addresses": sum(c["address_count"] for c in cities), "cities": cities}


# ---------------------------------------------------------------------------
# Routes — Marketing pages
# ---------------------------------------------------------------------------

@app.get("/narpm", response_class=HTMLResponse)
async def narpm():
    return _template("narpm/index.html")

@app.get("/narpm/print", response_class=HTMLResponse)
async def narpm_print():
    return _template("narpm/print.html")

@app.get("/pricing", response_class=HTMLResponse)
async def pricing():
    return _template("pricing.html")

@app.get("/about", response_class=HTMLResponse)
async def about():
    return _template("about.html")

@app.get("/for/property-managers", response_class=HTMLResponse)
async def for_pms():
    return _template("for-property-managers.html")

@app.get("/for/municipalities", response_class=HTMLResponse)
async def for_munis():
    return _template("for-municipalities.html")

@app.get("/embed", response_class=HTMLResponse)
async def embed_page():
    return _template("embed-page.html")

@app.get("/embed.js")
async def embed_js():
    return Response(content=_template("embed.js"), media_type="application/javascript")


# ---------------------------------------------------------------------------
# Routes — Map (inject Mapbox token)
# ---------------------------------------------------------------------------

MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "")

@app.get("/map", response_class=HTMLResponse)
async def zone_map():
    return _template("map/index.html").replace("{{MAPBOX_TOKEN}}", MAPBOX_TOKEN)

@app.get("/map/embed", response_class=HTMLResponse)
async def zone_map_embed():
    return _template("map/embed.html").replace("{{MAPBOX_TOKEN}}", MAPBOX_TOKEN)


# ---------------------------------------------------------------------------
# Routes — SEO
# ---------------------------------------------------------------------------

CITY_SLUGS = list(CITY_META.keys())

@app.get("/sitemap.xml")
async def sitemap():
    base = "https://trashalert.io"
    urls = []
    for p in ["/", "/map", "/narpm", "/pricing", "/about", "/for/property-managers", "/for/municipalities", "/embed"]:
        urls.append(f'  <url><loc>{base}{p}</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>')
    for s in CITY_SLUGS:
        urls.append(f'  <url><loc>{base}/{s}</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>')
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>"
    return Response(content=xml, media_type="application/xml")

@app.get("/robots.txt")
async def robots():
    return Response(content="User-agent: *\nAllow: /\nSitemap: https://trashalert.io/sitemap.xml\n", media_type="text/plain")


# ---------------------------------------------------------------------------
# CATCH-ALL: /{city_slug} redirect — MUST be last route registered
# ---------------------------------------------------------------------------
# This must come after ALL explicit routes (/narpm, /pricing, /about,
# /api/*, /map, /embed, etc.) or it will shadow them and return 404.

@app.get("/{city_slug}", response_class=HTMLResponse)
async def city_page_redirect(city_slug: str):
    """Redirect bare /{city} to /schedule/{city} (canonical URL)."""
    slug = _normalize_slug(city_slug)
    if slug is None:
        raise HTTPException(status_code=404, detail=f"Not found: {city_slug}")
    hyphenated = slug.replace("_", "-")
    return RedirectResponse(url=f"/schedule/{hyphenated}", status_code=301)
