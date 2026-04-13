"""Serve robots.txt."""

from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter(tags=["seo"])

ROBOTS_TXT = """\
User-agent: *
Allow: /

Sitemap: https://trashalert.io/sitemap.xml

# Disallow admin and API internals
Disallow: /admin/
Disallow: /graphql
Disallow: /api/notifications/
Disallow: /docs
Disallow: /redoc
"""


@router.get("/robots.txt", response_class=Response)
async def robots():
    return Response(content=ROBOTS_TXT, media_type="text/plain")
