"""Serve NARPM landing and print pages (/narpm, /narpm/print)."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["narpm"])

NARPM_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "narpm"


@router.get("/narpm", response_class=HTMLResponse)
async def narpm_landing():
    """NARPM property-manager landing page."""
    return (NARPM_DIR / "index.html").read_text(encoding="utf-8")


@router.get("/narpm/print", response_class=HTMLResponse)
async def narpm_print():
    """Printable one-page leave-behind for NARPM meeting."""
    return (NARPM_DIR / "print.html").read_text(encoding="utf-8")
