"""Vercel serverless entry point for the TrashAlert FastAPI app.

Vercel's @vercel/python runtime imports this module and serves the
ASGI `app` object.  All routes registered in app.main (city pages,
API endpoints, marketing pages) are available.
"""

from app.main import app  # noqa: F401 — Vercel detects the `app` ASGI object
