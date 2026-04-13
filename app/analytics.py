"""Plausible analytics injection middleware.

Injects the Plausible script tag into all HTML responses so every page
gets tracking without manually editing each template.
"""

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

PLAUSIBLE_DOMAIN = os.getenv("PLAUSIBLE_DOMAIN", "trashalert.io")

PLAUSIBLE_SCRIPT = (
    f'<script defer data-domain="{PLAUSIBLE_DOMAIN}" '
    f'src="https://plausible.io/js/script.js"></script>'
)


class PlausibleMiddleware(BaseHTTPMiddleware):
    """Inject Plausible analytics script into HTML responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Only inject into HTML responses
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type:
            return response

        # Read the body
        body = b""
        async for chunk in response.body_iterator:
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")
            body += chunk

        # Inject before </head>
        html = body.decode("utf-8")
        if "</head>" in html:
            html = html.replace("</head>", PLAUSIBLE_SCRIPT + "\n</head>", 1)

        return Response(
            content=html,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type="text/html",
        )
