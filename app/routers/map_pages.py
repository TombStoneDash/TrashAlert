"""Serve the zone map HTML pages (/map, /map/embed) and embed widget."""

import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

router = APIRouter(tags=["map"])

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
MAP_DIR = FRONTEND_DIR / "map"

MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "")


def _inject_token(html: str) -> str:
    """Replace the {{MAPBOX_TOKEN}} placeholder with the real token."""
    return html.replace("{{MAPBOX_TOKEN}}", MAPBOX_TOKEN)


@router.get("/map", response_class=HTMLResponse)
async def zone_map():
    """Serve the interactive zone map page.

    Uses Mapbox GL if MAPBOX_TOKEN is set, otherwise falls back to
    Leaflet + OSM tiles (no API key required).
    """
    if MAPBOX_TOKEN:
        return _inject_token((MAP_DIR / "index.html").read_text(encoding="utf-8"))
    return (MAP_DIR / "leaflet.html").read_text(encoding="utf-8")


@router.get("/map/embed", response_class=HTMLResponse)
async def zone_map_embed():
    """Serve the embeddable zone map (iframe-friendly)."""
    embed_path = MAP_DIR / "embed.html"
    if embed_path.exists():
        return _inject_token(embed_path.read_text(encoding="utf-8"))
    return _inject_token((MAP_DIR / "index.html").read_text(encoding="utf-8"))


@router.get("/embed.js", response_class=Response)
async def embed_js():
    """Serve the embeddable widget JavaScript."""
    js = (FRONTEND_DIR / "embed.js").read_text(encoding="utf-8")
    return Response(content=js, media_type="application/javascript")


@router.get("/embed", response_class=HTMLResponse)
async def embed_page():
    """Serve the embed widget documentation / preview page."""
    return (FRONTEND_DIR / "embed-page.html").read_text(encoding="utf-8")
