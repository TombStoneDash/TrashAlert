"""Middleware for request logging and metrics collection."""
import time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import Callable

from app.logging_config import access_logger, error_logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all API requests with timing information.

    Logs:
    - Request method and path
    - Response status code
    - Response time in milliseconds
    - Client IP address
    - User agent
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log details."""
        # Start timing
        start_time = time.time()

        # Extract request details
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")

        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code

            # Calculate response time
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000

            # Log successful request
            access_logger.info(
                f"{method} {path} - Status: {status_code} - "
                f"Time: {response_time_ms:.2f}ms - IP: {client_ip}"
            )

            # Add custom header with response time
            response.headers["X-Response-Time"] = f"{response_time_ms:.2f}ms"

            return response

        except Exception as e:
            # Calculate response time even for errors
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000

            # Log error
            error_logger.error(
                f"{method} {path} - ERROR after {response_time_ms:.2f}ms - "
                f"IP: {client_ip} - Error: {str(e)}",
                exc_info=True
            )

            # Re-raise the exception to be handled by FastAPI
            raise
