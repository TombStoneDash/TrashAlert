"""
TrashAlert API - Trash pickup schedule lookup service.

A minimal HTTP API for looking up trash, recycling, and green waste
pickup schedules by address.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
import logging

from .models import LookupResponse, ErrorResponse, HealthResponse
from .database import find_closest_address, get_stats
from .normalization import normalize_address, parse_address_components

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="TrashAlert API",
    description="Lookup trash, recycling, and green waste pickup schedules by address",
    version="0.1.0",
)


@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint - redirect to docs."""
    return {
        "message": "TrashAlert API",
        "docs": "/docs",
        "health": "/health"
    }


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Check if the API and database are operational"
)
async def health_check():
    """
    Health check endpoint.

    Returns the service status and basic database statistics.
    """
    try:
        stats = get_stats()

        return HealthResponse(
            status="ok",
            database="connected",
            total_addresses=stats['total_addresses'],
            total_cities=stats['total_cities']
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": "disconnected",
                "error": str(e)
            }
        )


@app.get(
    "/lookup",
    response_model=LookupResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Address not found"},
        400: {"model": ErrorResponse, "description": "Invalid request"}
    },
    summary="Look up pickup schedule",
    description="Look up trash, recycling, and green waste pickup schedules for a given address"
)
async def lookup_address(
    address: str = Query(
        ...,
        description="Full address to look up (e.g., '1122 Palmview Ave, El Centro, CA')",
        min_length=5,
        examples=["1122 Palmview Ave, El Centro, CA"]
    )
):
    """
    Look up trash pickup schedule for an address.

    The endpoint will:
    1. Normalize the input address
    2. Search for the closest match in the database
    3. Return pickup schedule information

    Args:
        address: Full address string

    Returns:
        Pickup schedule information including matched address and confidence score

    Raises:
        HTTPException: 404 if no matching address is found
        HTTPException: 400 if the request is invalid
    """
    logger.info(f"Lookup request: {address}")

    try:
        # Parse and normalize the address
        house_number, street, city = parse_address_components(address)
        normalized = normalize_address(address)

        logger.info(f"Parsed: house={house_number}, street={street}, city={city}")
        logger.info(f"Normalized: {normalized}")

        # Find closest match
        result = find_closest_address(normalized, city)

        if result is None:
            logger.warning(f"No match found for: {address}")
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Address not found",
                    "detail": f"No matching address found for '{address}' in {city}. "
                             f"Please verify the address and city name."
                }
            )

        logger.info(f"Match found: {result['matched_address']} (confidence: {result['confidence']})")

        # Remove lat/lon from response (internal use only)
        result.pop('lat', None)
        result.pop('lon', None)

        return LookupResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lookup error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "detail": str(e)
            }
        )


# Add CORS middleware for web clients (optional, but helpful for testing)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
