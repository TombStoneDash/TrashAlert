"""
Fetch city boundaries from OpenStreetMap using OSMnx.

This script retrieves administrative boundary polygons for the pilot cities
and saves them as a GeoJSON file for use in the TrashAlert system.
"""

import logging
import sys
from pathlib import Path

import osmnx as ox
import geopandas as gpd
from shapely.geometry import mapping

# Add the scripts directory to the path so we can import cities_config
sys.path.insert(0, str(Path(__file__).parent))
from cities_config import PILOT_CITIES

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configure OSMnx settings
ox.settings.log_console = True
ox.settings.use_cache = True
# Set user agent for Nominatim API (required by OSM usage policy)
ox.settings.nominatim_user_agent = "TrashAlert_CityBoundary_Fetcher/1.0"


def fetch_city_boundary(city_name, state, country):
    """
    Fetch the administrative boundary for a city from OpenStreetMap.

    Args:
        city_name (str): Name of the city
        state (str): State/province name
        country (str): Country name

    Returns:
        gpd.GeoDataFrame: GeoDataFrame containing the city boundary
    """
    try:
        # Construct query string for OSM Nominatim
        query = f"{city_name}, {state}, {country}"
        logger.info(f"Fetching boundary for: {query}")

        # Get the city boundary from OSM
        # which_result=1 gets the first result (usually the administrative boundary)
        gdf = ox.geocode_to_gdf(query, which_result=1)

        # Add city metadata
        gdf['city_name'] = city_name
        gdf['state'] = state
        gdf['country'] = country

        logger.info(f"Successfully fetched boundary for {city_name}")
        return gdf

    except Exception as e:
        logger.error(f"Error fetching boundary for {city_name}, {state}: {str(e)}")
        raise


def fetch_all_city_boundaries(cities):
    """
    Fetch boundaries for all cities in the list.

    Args:
        cities (list): List of city dictionaries

    Returns:
        gpd.GeoDataFrame: Combined GeoDataFrame with all city boundaries
    """
    all_boundaries = []

    for city in cities:
        try:
            gdf = fetch_city_boundary(
                city['name'],
                city['state'],
                city['country']
            )
            all_boundaries.append(gdf)
        except Exception as e:
            logger.warning(f"Skipping {city['name']} due to error: {str(e)}")
            continue

    if not all_boundaries:
        raise ValueError("No city boundaries were successfully fetched")

    # Combine all boundaries into a single GeoDataFrame
    combined_gdf = gpd.GeoDataFrame(
        pd.concat(all_boundaries, ignore_index=True)
    )

    return combined_gdf


def save_to_geojson(gdf, output_path):
    """
    Save GeoDataFrame to GeoJSON file.

    Args:
        gdf (gpd.GeoDataFrame): GeoDataFrame to save
        output_path (Path): Output file path
    """
    try:
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save to GeoJSON
        gdf.to_file(output_path, driver='GeoJSON')
        logger.info(f"Successfully saved boundaries to {output_path}")
        logger.info(f"Saved {len(gdf)} city boundaries")

    except Exception as e:
        logger.error(f"Error saving to GeoJSON: {str(e)}")
        raise


def main():
    """Main execution function."""
    try:
        logger.info("Starting city boundary fetch process")
        logger.info(f"Fetching boundaries for {len(PILOT_CITIES)} cities")

        # Fetch all city boundaries
        boundaries_gdf = fetch_all_city_boundaries(PILOT_CITIES)

        # Define output path
        output_path = Path(__file__).parent.parent / "data" / "city_boundaries.geojson"

        # Save to GeoJSON
        save_to_geojson(boundaries_gdf, output_path)

        logger.info("=" * 60)
        logger.info("SUCCESS: City boundaries fetched and saved")
        logger.info(f"Output file: {output_path}")
        logger.info(f"Total cities: {len(boundaries_gdf)}")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.error(f"Fatal error in main execution: {str(e)}")
        return 1


if __name__ == "__main__":
    import pandas as pd  # Import here to avoid issues if not installed
    sys.exit(main())
