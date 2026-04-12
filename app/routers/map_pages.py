"""Serve the zone map HTML pages (/map and /map/embed)."""

import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["map"])

MAP_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "map"

MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "")


def _inject_token(html: str) -> str:
    """Replace the {{MAPBOX_TOKEN}} placeholder with the real token."""
    return html.replace("{{MAPBOX_TOKEN}}", MAPBOX_TOKEN)


@router.get("/map", response_class=HTMLResponse)
async def zone_map():
    """Serve the interactive zone map page."""
    return _inject_token((MAP_DIR / "index.html").read_text(encoding="utf-8"))


@router.get("/map/embed", response_class=HTMLResponse)
async def zone_map_embed():
    """Serve the embeddable zone map (iframe-friendly)."""
    embed_path = MAP_DIR / "embed.html"
    if embed_path.exists():
        return _inject_token(embed_path.read_text(encoding="utf-8"))
    return _inject_token((MAP_DIR / "index.html").read_text(encoding="utf-8"))
