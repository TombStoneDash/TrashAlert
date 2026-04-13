"""Generate sitemap.xml dynamically from available city pages."""

from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter(tags=["sitemap"])

BASE_URL = "https://trashalert.io"

# All known city slugs
CITY_SLUGS = [
    "san_diego", "houston", "phoenix", "austin", "boston", "denver",
    "el_centro", "calexico", "brawley", "imperial", "holtville",
    "new_york", "los_angeles", "philadelphia", "san_antonio", "dallas",
    "oklahoma_city", "charlotte", "columbus", "chicago", "seattle",
    "portland", "minneapolis", "detroit", "atlanta", "miami",
]

# Static pages
STATIC_PAGES = [
    "/",
    "/map",
    "/narpm",
    "/narpm/print",
    "/pricing",
    "/about",
    "/for/property-managers",
    "/for/municipalities",
    "/embed",
]


def _build_sitemap() -> str:
    urls = []
    for page in STATIC_PAGES:
        priority = "1.0" if page == "/" else "0.8"
        urls.append(
            f"  <url>\n"
            f"    <loc>{BASE_URL}{page}</loc>\n"
            f"    <changefreq>weekly</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>"
        )

    for slug in CITY_SLUGS:
        # Use hyphenated form matching production URL pattern: /schedule/{city}
        hyphenated = slug.replace("_", "-")
        urls.append(
            f"  <url>\n"
            f"    <loc>{BASE_URL}/schedule/{hyphenated}</loc>\n"
            f"    <changefreq>weekly</changefreq>\n"
            f"    <priority>0.7</priority>\n"
            f"  </url>"
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls) + "\n"
        "</urlset>\n"
    )


@router.get("/sitemap.xml", response_class=Response)
async def sitemap():
    """Serve sitemap.xml with all static and city pages."""
    return Response(
        content=_build_sitemap(),
        media_type="application/xml",
    )
