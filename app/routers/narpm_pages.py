"""Serve marketing pages: /narpm, /pricing, /about, /for/*."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["marketing"])

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
NARPM_DIR = FRONTEND_DIR / "narpm"


@router.get("/narpm", response_class=HTMLResponse)
async def narpm_landing():
    """NARPM property-manager landing page."""
    return (NARPM_DIR / "index.html").read_text(encoding="utf-8")


@router.get("/narpm/print", response_class=HTMLResponse)
async def narpm_print():
    """Printable one-page leave-behind for NARPM meeting."""
    return (NARPM_DIR / "print.html").read_text(encoding="utf-8")


@router.get("/pricing", response_class=HTMLResponse)
async def pricing():
    """Pricing page with Starter, Portfolio, Enterprise tiers."""
    return (FRONTEND_DIR / "pricing.html").read_text(encoding="utf-8")


@router.get("/about", response_class=HTMLResponse)
async def about():
    """About page with company info."""
    return (FRONTEND_DIR / "about.html").read_text(encoding="utf-8")


@router.get("/for/property-managers", response_class=HTMLResponse)
async def for_property_managers():
    """Landing page for property managers."""
    return (FRONTEND_DIR / "for-property-managers.html").read_text(encoding="utf-8")


@router.get("/for/municipalities", response_class=HTMLResponse)
async def for_municipalities():
    """Landing page for city waste departments."""
    return (FRONTEND_DIR / "for-municipalities.html").read_text(encoding="utf-8")


@router.get("/coverage", response_class=HTMLResponse)
async def coverage():
    """Coverage page showing all cities with live address counts."""
    return (FRONTEND_DIR / "coverage.html").read_text(encoding="utf-8")
