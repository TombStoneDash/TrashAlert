"""Vercel serverless handler — lightweight FastAPI app for city pages and API.

This is a self-contained handler that serves city pages, the lookup
API, and the cities list WITHOUT importing the full app.main (which
pulls in heavy GIS/ML deps that exceed Vercel's 250 MB limit).

It reads directly from addresses_normalized.csv and the HTML templates.
"""

import csv
import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import h3
from fastapi import FastAPI, HTTPException, Query, Request
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

def _load_subs() -> dict:
    if SUBS_PATH.exists():
        return json.loads(SUBS_PATH.read_text(encoding="utf-8"))
    return {}

def _save_subs(subs: dict):
    SUBS_PATH.write_text(json.dumps(subs, indent=2), encoding="utf-8")


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


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
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
        subs[cid] = {"subscription_id": obj.get("subscription", ""), "email": obj.get("customer_email", ""),
                      "plan": obj.get("metadata", {}).get("plan", ""), "status": "active",
                      "updated_at": datetime.utcnow().isoformat()}
        _save_subs(subs)
    elif etype == "customer.subscription.deleted":
        cid = obj.get("customer", "")
        if cid in subs:
            subs[cid]["status"] = "canceled"
            subs[cid]["updated_at"] = datetime.utcnow().isoformat()
            _save_subs(subs)

    return JSONResponse({"received": True})


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
