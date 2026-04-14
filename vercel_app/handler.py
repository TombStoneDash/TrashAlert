"""Vercel serverless handler — lightweight FastAPI app for city pages and API.

This is a self-contained handler that serves city pages, the lookup
API, and the cities list WITHOUT importing the full app.main (which
pulls in heavy GIS/ML deps that exceed Vercel's 250 MB limit).

It reads directly from addresses_normalized.csv and the HTML templates.
"""

import csv
import hashlib
import json
import logging
import os
import secrets
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import h3
from fastapi import FastAPI, HTTPException, Header, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

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
    "portland":       {"name": "Portland",        "state": "Oregon",         "abbr": "OR", "lat": "45.52",  "lng": "-122.68", "zoom": "12", "sample": "500 Burnside St"},
    "minneapolis":    {"name": "Minneapolis",     "state": "Minnesota",      "abbr": "MN", "lat": "44.98",  "lng": "-93.27",  "zoom": "12", "sample": "300 Hennepin Ave"},
    "detroit":        {"name": "Detroit",          "state": "Michigan",       "abbr": "MI", "lat": "42.33",  "lng": "-83.05",  "zoom": "12", "sample": "1000 Woodward Ave"},
    "atlanta":        {"name": "Atlanta",          "state": "Georgia",        "abbr": "GA", "lat": "33.75",  "lng": "-84.39",  "zoom": "12", "sample": "200 Peachtree St"},
    "miami":          {"name": "Miami",            "state": "Florida",        "abbr": "FL", "lat": "25.76",  "lng": "-80.19",  "zoom": "12", "sample": "100 Biscayne Blvd"},
}

NAME_TO_SLUG = {m["name"]: slug for slug, m in CITY_META.items()}

# Supabase city slug mapping (Supabase uses hyphenated lowercase)
SLUG_TO_SUPA = {k: k.replace("_", "-") for k in CITY_META}

# ---------------------------------------------------------------------------
# Supabase client (inline — no external deps beyond requests)
# ---------------------------------------------------------------------------

SUPABASE_URL = os.getenv("SUPABASE_URL", os.getenv("NEXT_PUBLIC_SUPABASE_URL", "https://qsuzfemakaaroeakyick.supabase.co"))
SUPABASE_KEY = os.getenv("SUPABASE_KEY", os.getenv("SUPABASE_SERVICE_KEY", os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")))

_supa_headers = lambda: {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

def _supa_ok() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)

def _supa_fetch_city(city_slug: str, limit: int = 5000) -> list[dict]:
    """Fetch addresses from Supabase schedule_reports for a city."""
    if not _supa_ok():
        return []
    import requests as _req
    from urllib.parse import quote
    supa_city = SLUG_TO_SUPA.get(city_slug, city_slug.replace("_", "-"))
    url = f"{SUPABASE_URL}/rest/v1/schedule_reports?city=eq.{quote(supa_city)}&select=address,city,lat,lng,collection_day,neighborhood,zip_code&limit={limit}"
    try:
        resp = _req.get(url, headers=_supa_headers(), timeout=10)
        resp.raise_for_status()
        rows = resp.json()
    except Exception as e:
        logger.error(f"Supabase query failed for {city_slug}: {e}")
        return []
    result = []
    for r in rows:
        addr = (r.get("address") or "").split(",")[0].strip()
        tokens = addr.split(" ", 1)
        house = tokens[0] if tokens[0].isdigit() else ""
        street = tokens[1].upper() if len(tokens) > 1 else addr.upper()
        result.append({
            "lat": float(r["lat"]) if r.get("lat") else None,
            "lon": float(r["lng"]) if r.get("lng") else None,
            "street": street, "house": house,
            "city_name": r.get("city", supa_city),
            "full_address": r.get("address", ""),
            "collection_day": r.get("collection_day", ""),
            "neighborhood": r.get("neighborhood", ""),
        })
    return result

def _supa_city_count(city_slug: str) -> int:
    if not _supa_ok():
        return 0
    import requests as _req
    from urllib.parse import quote
    supa_city = SLUG_TO_SUPA.get(city_slug, city_slug.replace("_", "-"))
    url = f"{SUPABASE_URL}/rest/v1/schedule_reports?city=eq.{quote(supa_city)}&select=id"
    try:
        resp = _req.head(url, headers={**_supa_headers(), "Prefer": "count=exact", "Range": "0-0"}, timeout=10)
        cr = resp.headers.get("content-range", "")
        if "/" in cr:
            return int(cr.split("/")[1])
    except Exception:
        pass
    return 0

# ---------------------------------------------------------------------------
# Data loading (Supabase first, CSV fallback)
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
    """Get rows for a city — Supabase first, CSV fallback."""
    slug = NAME_TO_SLUG.get(city_name, city_name.lower().replace(" ", "_"))
    if _supa_ok():
        supa = _supa_fetch_city(slug)
        if supa:
            return supa
    return [r for r in _load_csv() if r["city_name"] == city_name]


def _city_counts() -> dict[str, int]:
    """Get per-city address counts — Supabase first, CSV fallback."""
    if _supa_ok():
        counts = {}
        for slug, meta in CITY_META.items():
            c = _supa_city_count(slug)
            if c > 0:
                counts[meta["name"]] = c
        if counts:
            return counts
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

@app.get("/coverage", response_class=HTMLResponse)
async def coverage():
    return _template("coverage.html")

@app.get("/embed.js")
async def embed_js():
    return Response(content=_template("embed.js"), media_type="application/javascript")


# ---------------------------------------------------------------------------
# Routes — Map
# ---------------------------------------------------------------------------

@app.get("/map", response_class=HTMLResponse)
async def zone_map():
    return _template("map/index.html")

@app.get("/map/embed", response_class=HTMLResponse)
async def zone_map_embed():
    return _template("map/embed.html")


# ---------------------------------------------------------------------------
# Routes — SEO
# ---------------------------------------------------------------------------

CITY_SLUGS = list(CITY_META.keys())

@app.get("/sitemap.xml")
async def sitemap():
    base = "https://trashalert.io"
    urls = []
    for p in ["/", "/map", "/narpm", "/pricing", "/about", "/for/property-managers", "/for/municipalities", "/embed", "/portfolio"]:
        urls.append(f'  <url><loc>{base}{p}</loc><changefreq>weekly</changefreq><priority>0.8</priority></url>')
    for s in CITY_SLUGS:
        urls.append(f'  <url><loc>{base}/{s}</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>')
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>"
    return Response(content=xml, media_type="application/xml")

@app.get("/robots.txt")
async def robots():
    return Response(content="User-agent: *\nAllow: /\nSitemap: https://trashalert.io/sitemap.xml\n", media_type="text/plain")


# ---------------------------------------------------------------------------
# Routes — Stripe Billing
# ---------------------------------------------------------------------------

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_BASE_URL = os.getenv("BASE_URL", "https://trashalert.io")

STRIPE_PLANS = {
    "starter": {
        "name": "Starter", "price_id": os.getenv("STRIPE_PRICE_STARTER", "price_starter_placeholder"),
        "amount": 2900, "display": "$29/mo", "properties": "1",
        "features": ["1 property", "Schedule lookup", "Weekly email reminders", "Zone map", "Basic API (100 req/day)"],
    },
    "portfolio": {
        "name": "Portfolio", "price_id": os.getenv("STRIPE_PRICE_PORTFOLIO", "price_portfolio_placeholder"),
        "amount": 9900, "display": "$99/mo", "properties": "Unlimited",
        "features": ["Unlimited properties", "Bulk CSV upload", "Embeddable widget", "REST API (10k req/day)", "Move-in packets", "Slack & email alerts"],
    },
}

SUBS_PATH = DATA_DIR / "stripe_subscriptions.json"
API_KEYS_PATH = DATA_DIR / "api_keys.json"
API_USAGE_PATH = DATA_DIR / "api_usage.json"

def _load_subs() -> dict:
    if SUBS_PATH.exists():
        return json.loads(SUBS_PATH.read_text(encoding="utf-8"))
    return {}

def _save_subs(subs: dict):
    SUBS_PATH.write_text(json.dumps(subs, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# API Key helpers (JSON-file backed, no database required)
# ---------------------------------------------------------------------------

def _load_api_keys() -> dict:
    if API_KEYS_PATH.exists():
        return json.loads(API_KEYS_PATH.read_text(encoding="utf-8"))
    return {}

def _save_api_keys(keys: dict):
    API_KEYS_PATH.write_text(json.dumps(keys, indent=2), encoding="utf-8")

def _load_usage() -> dict:
    if API_USAGE_PATH.exists():
        return json.loads(API_USAGE_PATH.read_text(encoding="utf-8"))
    return {}

def _save_usage(usage: dict):
    API_USAGE_PATH.write_text(json.dumps(usage, indent=2), encoding="utf-8")

def _generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.  Returns (full_key, key_hash, key_prefix)."""
    raw = secrets.token_urlsafe(32)
    full_key = f"ta_live_{raw}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    key_prefix = full_key[:16]
    return full_key, key_hash, key_prefix

def _hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()

def _validate_api_key(key: str) -> Optional[dict]:
    """Look up an API key by its hash. Returns the key record or None."""
    key_hash = _hash_api_key(key)
    keys = _load_api_keys()
    record = keys.get(key_hash)
    if not record:
        return None
    if not record.get("active", True):
        return None
    return record

def _record_usage(key_hash: str, endpoint: str, status_code: int):
    """Append a usage event for an API key."""
    usage = _load_usage()
    today = date.today().isoformat()
    if key_hash not in usage:
        usage[key_hash] = {"total": 0, "daily": {}}
    usage[key_hash]["total"] += 1
    usage[key_hash]["daily"].setdefault(today, 0)
    usage[key_hash]["daily"][today] += 1
    usage[key_hash]["last_used"] = datetime.utcnow().isoformat()
    usage[key_hash]["last_endpoint"] = endpoint
    _save_usage(usage)

def _check_rate_limit(key_hash: str, daily_limit: int = 10000) -> bool:
    """Return True if within rate limit, False if exceeded."""
    usage = _load_usage()
    today = date.today().isoformat()
    day_count = usage.get(key_hash, {}).get("daily", {}).get(today, 0)
    return day_count < daily_limit

def _provision_api_key_for_customer(customer_id: str, email: str, plan: str) -> Optional[str]:
    """Create an API key for a new Portfolio subscriber. Returns the full key or None if one already exists."""
    keys = _load_api_keys()
    # Check if customer already has a key
    for kh, rec in keys.items():
        if rec.get("customer_id") == customer_id:
            return None  # already provisioned
    full_key, key_hash, key_prefix = _generate_api_key()
    keys[key_hash] = {
        "customer_id": customer_id,
        "email": email,
        "plan": plan,
        "prefix": key_prefix,
        "active": True,
        "created_at": datetime.utcnow().isoformat(),
        "daily_limit": 10000 if plan == "portfolio" else 100,
    }
    _save_api_keys(keys)
    return full_key


class CheckoutReq(BaseModel):
    plan: str = Field(...)
    email: Optional[str] = None


@app.get("/api/stripe/plans")
async def stripe_plans():
    plans = [{"slug": k, "name": v["name"], "amount": v["amount"], "display_price": v["display"],
              "properties": v["properties"], "features": v["features"]} for k, v in STRIPE_PLANS.items()]
    return {"publishable_key": STRIPE_PUBLISHABLE_KEY, "plans": plans}


@app.post("/api/stripe/checkout")
async def stripe_checkout(req: CheckoutReq):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(503, detail="STRIPE_SECRET_KEY not configured")
    if req.plan not in STRIPE_PLANS:
        raise HTTPException(400, detail=f"Invalid plan: {req.plan}")
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{"price": STRIPE_PLANS[req.plan]["price_id"], "quantity": 1}],
            customer_email=req.email,
            success_url=f"{STRIPE_BASE_URL}/pricing?session_id={{CHECKOUT_SESSION_ID}}&status=success",
            cancel_url=f"{STRIPE_BASE_URL}/pricing?status=cancelled",
            metadata={"plan": req.plan, "product": "trashalert"},
            subscription_data={"metadata": {"plan": req.plan}},
        )
        return {"checkout_url": session.url, "session_id": session.id}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


# ---------------------------------------------------------------------------
# Routes — Direct checkout (GET redirects to Stripe)
# ---------------------------------------------------------------------------

@app.get("/checkout/{plan_slug}")
async def checkout_redirect(plan_slug: str, email: Optional[str] = None):
    """GET /checkout/portfolio — creates a Stripe Checkout Session and redirects
    the browser directly.  This is the primary checkout entry-point linked from
    the pricing page."""
    if not STRIPE_SECRET_KEY:
        raise HTTPException(503, detail="Stripe is not configured. Set STRIPE_SECRET_KEY.")
    if plan_slug not in STRIPE_PLANS:
        raise HTTPException(404, detail=f"Unknown plan: {plan_slug}")
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        params: dict = {
            "mode": "subscription",
            "payment_method_types": ["card"],
            "line_items": [{"price": STRIPE_PLANS[plan_slug]["price_id"], "quantity": 1}],
            "success_url": f"{STRIPE_BASE_URL}/pricing?session_id={{CHECKOUT_SESSION_ID}}&status=success",
            "cancel_url": f"{STRIPE_BASE_URL}/pricing?status=cancelled",
            "metadata": {"plan": plan_slug, "product": "trashalert"},
            "subscription_data": {"metadata": {"plan": plan_slug}},
        }
        if email:
            params["customer_email"] = email
        session = stripe.checkout.Session.create(**params)
        return RedirectResponse(session.url, status_code=303)
    except Exception as e:
        logger.error(f"Stripe checkout redirect failed: {e}")
        raise HTTPException(500, detail=str(e))


async def _handle_stripe_webhook(request: Request):
    """Shared webhook handler used by both /api/stripe/webhook and /api/webhooks/stripe."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    if STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET:
        try:
            import stripe
            stripe.api_key = STRIPE_SECRET_KEY
            event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
        except Exception as e:
            raise HTTPException(400, detail=f"Webhook error: {e}")
    else:
        event = json.loads(payload)

    etype = event.get("type", "")
    obj = event.get("data", {}).get("object", {})
    subs = _load_subs()

    if etype == "checkout.session.completed":
        cid = obj.get("customer", "")
        plan = obj.get("metadata", {}).get("plan", "")
        email = obj.get("customer_email", "")
        subs[cid] = {
            "subscription_id": obj.get("subscription", ""),
            "email": email,
            "plan": plan,
            "status": "active",
            "updated_at": datetime.utcnow().isoformat(),
        }
        _save_subs(subs)
        # Auto-provision an API key for Portfolio subscribers
        if plan in ("portfolio", "enterprise"):
            new_key = _provision_api_key_for_customer(cid, email, plan)
            if new_key:
                logger.info(f"Provisioned API key for customer {cid} (plan={plan})")

    elif etype == "customer.subscription.updated":
        cid = obj.get("customer", "")
        new_status = obj.get("status", "")  # active, past_due, unpaid, etc.
        plan = obj.get("metadata", {}).get("plan", "")
        if cid in subs:
            subs[cid]["status"] = new_status
            if plan:
                subs[cid]["plan"] = plan
            subs[cid]["updated_at"] = datetime.utcnow().isoformat()
            _save_subs(subs)
        # Deactivate API key if subscription is no longer active
        if new_status not in ("active", "trialing"):
            _deactivate_keys_for_customer(cid)

    elif etype == "customer.subscription.deleted":
        cid = obj.get("customer", "")
        if cid in subs:
            subs[cid]["status"] = "canceled"
            subs[cid]["updated_at"] = datetime.utcnow().isoformat()
            _save_subs(subs)
        # Deactivate API keys on cancellation
        _deactivate_keys_for_customer(cid)

    return JSONResponse({"received": True})


def _deactivate_keys_for_customer(customer_id: str):
    """Deactivate all API keys belonging to a customer."""
    keys = _load_api_keys()
    changed = False
    for kh, rec in keys.items():
        if rec.get("customer_id") == customer_id and rec.get("active"):
            rec["active"] = False
            rec["deactivated_at"] = datetime.utcnow().isoformat()
            changed = True
    if changed:
        _save_api_keys(keys)


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    return await _handle_stripe_webhook(request)


@app.post("/api/webhooks/stripe")
async def stripe_webhook_canonical(request: Request):
    """Canonical webhook path for Stripe dashboard configuration."""
    return await _handle_stripe_webhook(request)


@app.get("/api/stripe/portal")
async def stripe_portal(customer_id: str):
    if not STRIPE_SECRET_KEY:
        raise HTTPException(503, detail="STRIPE_SECRET_KEY not configured")
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        session = stripe.billing_portal.Session.create(customer=customer_id, return_url=f"{STRIPE_BASE_URL}/pricing")
        return {"portal_url": session.url}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.get("/api/stripe/status")
async def stripe_status(email: Optional[str] = None, customer_id: Optional[str] = None):
    subs = _load_subs()
    if customer_id and customer_id in subs:
        return subs[customer_id]
    if email:
        for cid, sub in subs.items():
            if sub.get("email", "").lower() == email.lower():
                return {"customer_id": cid, **sub}
    return {"status": "none"}


# ---------------------------------------------------------------------------
# Routes — Portfolio Dashboard
# ---------------------------------------------------------------------------

@app.get("/portfolio", response_class=HTMLResponse)
async def portfolio_dashboard():
    return _template("portfolio-dashboard.html")


@app.get("/api/portfolio/properties")
async def portfolio_properties():
    """Return all properties across cities for the portfolio dashboard.

    In production this would be scoped to the authenticated user's
    subscription.  For now it returns a representative sample from
    each city in the registry.
    """
    properties = []
    cities_with_data = set()
    total_with_schedule = 0
    sample_limit = 12  # addresses per city to keep response fast

    for slug, meta in CITY_META.items():
        city_name = meta["name"]
        rows = _city_rows(city_name)
        if not rows:
            continue

        cities_with_data.add(city_name)
        lons = [r["lon"] for r in rows if r.get("lon") is not None]
        lon_min = min(lons) - 0.02 if lons else -120
        lon_max = max(lons) + 0.02 if lons else -80

        for r in rows[:sample_limit]:
            lat = r.get("lat")
            lon = r.get("lon")
            if lat is None or lon is None:
                continue
            h3i = h3.latlng_to_cell(lat, lon, H3_RESOLUTION)
            day = r.get("collection_day") or _assign_day(h3i, lon_min, lon_max)
            neighborhood = r.get("neighborhood", "") or _zone_label(h3i)
            total_with_schedule += 1
            properties.append({
                "address": r.get("full_address") or f"{r.get('house', '')} {r.get('street', '')}".strip(),
                "city": city_name,
                "neighborhood": neighborhood,
                "pickup_day": day,
                "hauler": "Municipal",
                "status": "active",
            })

    total = len(properties)
    coverage = round(total_with_schedule / total * 100) if total else 0

    return {
        "total_properties": total,
        "coverage_pct": coverage,
        "last_sync": date.today().isoformat(),
        "properties": properties,
    }


@app.get("/api/portfolio/holidays")
async def portfolio_holidays():
    """Return upcoming holiday schedule changes."""
    holidays = [
        {"name": "New Year's Day",    "date": "2026-01-01", "note": "No collection Jan 1. Thursday/Friday routes delayed by 1 day."},
        {"name": "MLK Day",           "date": "2026-01-19", "note": "Monday routes moved to Tuesday. All other days shift +1."},
        {"name": "Presidents' Day",   "date": "2026-02-16", "note": "Monday routes moved to Tuesday. All other days shift +1."},
        {"name": "Memorial Day",      "date": "2026-05-25", "note": "Monday routes moved to Tuesday. All other days shift +1."},
        {"name": "Independence Day",  "date": "2026-07-04", "note": "Saturday collection. No change to weekday routes."},
        {"name": "Labor Day",         "date": "2026-09-07", "note": "Monday routes moved to Tuesday. All other days shift +1."},
        {"name": "Thanksgiving",      "date": "2026-11-26", "note": "Thursday routes moved to Wednesday. Friday routes delayed to Saturday."},
        {"name": "Christmas Day",     "date": "2026-12-25", "note": "Friday routes moved to Saturday. No collection Dec 25."},
    ]
    today = date.today()
    upcoming = []
    for h in holidays:
        hdate = date.fromisoformat(h["date"])
        diff = (hdate - today).days
        if -1 <= diff <= 30:
            upcoming.append({**h, "days_away": diff})
    return {"holidays": upcoming}


@app.get("/api/portfolio/export")
async def portfolio_export(fmt: str = Query("csv")):
    """Export portfolio schedules as CSV."""
    props_resp = await portfolio_properties()
    properties = props_resp["properties"]

    if fmt == "csv":
        lines = ["Address,City,Neighborhood,Hauler,Pickup Day,Next Pickup,Status"]
        for p in properties:
            day = p["pickup_day"]
            nxt = _next_pickup(day) if day in DAY_INDEX else ""
            addr = p["address"].replace('"', '""')
            lines.append(f'"{addr}","{p["city"]}","{p["neighborhood"]}","{p["hauler"]}",{day},{nxt},{p["status"]}')
        csv_content = "\n".join(lines)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=trashalert-portfolio-{date.today().isoformat()}.csv"},
        )

    return JSONResponse({"error": "Unsupported format. Use fmt=csv."}, status_code=400)


# ---------------------------------------------------------------------------
# Routes — API Key Management
# ---------------------------------------------------------------------------

class ApiKeyCreateReq(BaseModel):
    email: str = Field(..., description="Email of the subscriber")
    customer_id: Optional[str] = Field(None, description="Stripe customer ID (looked up from email if omitted)")


@app.post("/api/keys/generate")
async def generate_api_key_endpoint(req: ApiKeyCreateReq):
    """Generate an API key for a Portfolio subscriber.
    The full key is returned ONLY ONCE in this response."""
    # Verify the requester has an active portfolio subscription
    subs = _load_subs()
    customer_id = req.customer_id
    if not customer_id:
        for cid, sub in subs.items():
            if sub.get("email", "").lower() == req.email.lower():
                customer_id = cid
                break
    if not customer_id or customer_id not in subs:
        raise HTTPException(403, detail="No active subscription found for this email.")
    sub = subs[customer_id]
    if sub.get("status") not in ("active", "trialing"):
        raise HTTPException(403, detail="Subscription is not active.")
    if sub.get("plan") not in ("portfolio", "enterprise"):
        raise HTTPException(403, detail="API keys require a Portfolio or Enterprise plan.")

    # Check if key already exists
    keys = _load_api_keys()
    for kh, rec in keys.items():
        if rec.get("customer_id") == customer_id and rec.get("active"):
            raise HTTPException(409, detail="An active API key already exists. Revoke it first to generate a new one.")

    full_key = _provision_api_key_for_customer(customer_id, req.email, sub.get("plan", "portfolio"))
    if not full_key:
        raise HTTPException(409, detail="API key already exists for this customer.")

    return {
        "api_key": full_key,
        "message": "Save this key now. It will not be shown again.",
        "daily_limit": 10000,
        "usage_header": "X-API-Key",
    }


@app.post("/api/keys/revoke")
async def revoke_api_key(req: ApiKeyCreateReq):
    """Revoke all API keys for a customer so a new one can be generated."""
    subs = _load_subs()
    customer_id = req.customer_id
    if not customer_id:
        for cid, sub in subs.items():
            if sub.get("email", "").lower() == req.email.lower():
                customer_id = cid
                break
    if not customer_id:
        raise HTTPException(404, detail="Customer not found.")
    _deactivate_keys_for_customer(customer_id)
    return {"revoked": True}


@app.get("/api/keys/info")
async def api_key_info(x_api_key: Optional[str] = Header(None)):
    """Return metadata about the provided API key (passed via X-API-Key header)."""
    if not x_api_key:
        raise HTTPException(401, detail="Provide your API key in the X-API-Key header.")
    record = _validate_api_key(x_api_key)
    if not record:
        raise HTTPException(401, detail="Invalid or inactive API key.")
    key_hash = _hash_api_key(x_api_key)
    usage = _load_usage().get(key_hash, {})
    today = date.today().isoformat()
    return {
        "prefix": record.get("prefix"),
        "plan": record.get("plan"),
        "email": record.get("email"),
        "active": record.get("active"),
        "created_at": record.get("created_at"),
        "daily_limit": record.get("daily_limit", 10000),
        "usage_today": usage.get("daily", {}).get(today, 0),
        "usage_total": usage.get("total", 0),
        "last_used": usage.get("last_used"),
    }


# ---------------------------------------------------------------------------
# Routes — Authenticated API Lookup (API key required)
# ---------------------------------------------------------------------------

@app.get("/api/v1/lookup")
async def api_v1_lookup(
    request: Request,
    address: str = Query(...),
    city: str = Query("san_diego"),
    x_api_key: Optional[str] = Header(None),
):
    """Authenticated lookup endpoint for Portfolio subscribers.
    Requires a valid API key passed in the X-API-Key header.
    Rate-limited to the subscriber's daily quota."""
    if not x_api_key:
        raise HTTPException(401, detail="API key required. Pass X-API-Key header.")
    record = _validate_api_key(x_api_key)
    if not record:
        raise HTTPException(401, detail="Invalid or inactive API key.")
    key_hash = _hash_api_key(x_api_key)
    daily_limit = record.get("daily_limit", 10000)
    if not _check_rate_limit(key_hash, daily_limit):
        raise HTTPException(429, detail=f"Daily rate limit of {daily_limit} requests exceeded.")

    # Perform the lookup (same logic as /api/lookup)
    slug = city.lower().replace("-", "_")
    city_name = CITY_META.get(slug, {}).get("name") or city.replace("_", " ").title()
    rows = _city_rows(city_name)
    if not rows:
        _record_usage(key_hash, "/api/v1/lookup", 404)
        raise HTTPException(404, detail=f"No data for city: {city}")
    matched = _match_address(address, rows)
    if not matched:
        _record_usage(key_hash, "/api/v1/lookup", 404)
        raise HTTPException(404, detail=f"Address not found: {address}")
    lons = [r["lon"] for r in rows if r.get("lon") is not None]
    lon_min, lon_max = min(lons) - 0.02, max(lons) + 0.02
    h3i = h3.latlng_to_cell(matched["lat"], matched["lon"], H3_RESOLUTION)
    day = matched.get("collection_day") or _assign_day(h3i, lon_min, lon_max)
    _record_usage(key_hash, "/api/v1/lookup", 200)
    return {
        "address": matched["full_address"],
        "city": city_name,
        "pickup_day": day,
        "zone": _zone_label(h3i),
        "next_pickup": _next_pickup(day) if day in DAY_INDEX else None,
        "neighborhood": matched.get("neighborhood", ""),
    }


@app.get("/api/v1/bulk-lookup")
async def api_v1_bulk_lookup(
    request: Request,
    addresses: str = Query(..., description="Comma-separated addresses"),
    city: str = Query("san_diego"),
    x_api_key: Optional[str] = Header(None),
):
    """Bulk lookup endpoint for Portfolio subscribers. Pass comma-separated addresses."""
    if not x_api_key:
        raise HTTPException(401, detail="API key required. Pass X-API-Key header.")
    record = _validate_api_key(x_api_key)
    if not record:
        raise HTTPException(401, detail="Invalid or inactive API key.")
    key_hash = _hash_api_key(x_api_key)
    daily_limit = record.get("daily_limit", 10000)

    addr_list = [a.strip() for a in addresses.split(",") if a.strip()]
    if len(addr_list) > 100:
        raise HTTPException(400, detail="Maximum 100 addresses per bulk request.")
    if not _check_rate_limit(key_hash, daily_limit):
        raise HTTPException(429, detail=f"Daily rate limit of {daily_limit} requests exceeded.")

    slug = city.lower().replace("-", "_")
    city_name = CITY_META.get(slug, {}).get("name") or city.replace("_", " ").title()
    rows = _city_rows(city_name)
    results = []
    for addr in addr_list:
        matched = _match_address(addr, rows) if rows else None
        if matched:
            lons = [r["lon"] for r in rows if r.get("lon") is not None]
            lon_min, lon_max = min(lons) - 0.02, max(lons) + 0.02
            h3i = h3.latlng_to_cell(matched["lat"], matched["lon"], H3_RESOLUTION)
            day = matched.get("collection_day") or _assign_day(h3i, lon_min, lon_max)
            results.append({
                "query": addr, "found": True,
                "address": matched["full_address"], "city": city_name,
                "pickup_day": day, "zone": _zone_label(h3i),
                "next_pickup": _next_pickup(day) if day in DAY_INDEX else None,
            })
        else:
            results.append({"query": addr, "found": False})

    _record_usage(key_hash, "/api/v1/bulk-lookup", 200)
    return {"results": results, "total": len(results), "found": sum(1 for r in results if r["found"])}


@app.get("/api/v1/usage")
async def api_v1_usage(x_api_key: Optional[str] = Header(None)):
    """Return usage statistics for the authenticated API key."""
    if not x_api_key:
        raise HTTPException(401, detail="API key required.")
    record = _validate_api_key(x_api_key)
    if not record:
        raise HTTPException(401, detail="Invalid or inactive API key.")
    key_hash = _hash_api_key(x_api_key)
    usage = _load_usage().get(key_hash, {})
    today = date.today().isoformat()
    daily = usage.get("daily", {})
    # Return last 30 days of usage
    recent_days = sorted(daily.keys())[-30:] if daily else []
    return {
        "plan": record.get("plan"),
        "daily_limit": record.get("daily_limit", 10000),
        "usage_today": daily.get(today, 0),
        "usage_total": usage.get("total", 0),
        "last_used": usage.get("last_used"),
        "daily_breakdown": {d: daily[d] for d in recent_days},
    }


# ---------------------------------------------------------------------------
# CATCH-ALL: /{city_slug} redirect — MUST be last route registered
# ---------------------------------------------------------------------------
# This must come after ALL explicit routes (/narpm, /pricing, /about,
# /api/*, /map, /embed, etc.) or it will shadow them and return 404.

@app.get("/{city_slug}", response_class=HTMLResponse)
async def city_page_direct(city_slug: str):
    """Serve bare /{city} directly as a city landing page (no redirect)."""
    slug = _normalize_slug(city_slug)
    if slug is None:
        raise HTTPException(status_code=404, detail=f"Not found: {city_slug}")
    return _render_city(slug)
