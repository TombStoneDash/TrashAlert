"""
Generate sample city boundaries for testing and development.

This script creates sample polygon boundaries for the pilot cities
when OSM API access is not available. These are approximate boundaries
for development and testing purposes.

For production use, run fetch_city_boundaries.py instead.
"""

import logging
import sys
from pathlib import Path
import json

import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon

# Add the scripts directory to the path so we can import cities_config
sys.path.insert(0, str(Path(__file__).parent))
from cities_config import PILOT_CITIES

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Approximate center coordinates and sizes for each city
CITY_COORDINATES = {
    "San Francisco": {
        "lat": 37.7749,
        "lon": -122.4194,
        "size": 0.15  # degrees (roughly 10-15 km)
    },
    "Seattle": {
        "lat": 47.6062,
        "lon": -122.3321,
        "size": 0.20
    },
    "Austin": {
        "lat": 30.2672,
        "lon": -97.7431,
        "size": 0.25
    },
    "Portland": {
        "lat": 45.5152,
        "lon": -122.6784,
        "size": 0.18
    },
    "Denver": {
        "lat": 39.7392,
        "lon": -104.9903,
        "size": 0.22
    },
    "Boston": {
        "lat": 42.3601,
        "lon": -71.0589,
        "size": 0.16
    }
}


def create_city_polygon(lat, lon, size):
    """
    Create a polygon representing an approximate city boundary.

    Args:
        lat (float): Latitude of city center
        lon (float): Longitude of city center
        size (float): Approximate size in degrees

    Returns:
        Polygon: Shapely polygon representing the city boundary
    """
    # Create a roughly rectangular boundary with some irregularity
    # to simulate a more realistic city shape
    half_size = size / 2

    # Create an irregular polygon by adding some variation to the corners
    import random
    random.seed(int(lat * 1000))  # Consistent randomness for each city

    points = []
    num_points = 12  # Create a 12-sided polygon for more realistic shape

    for i in range(num_points):
        angle = (2 * 3.14159 * i) / num_points
        # Add some randomness to the radius
        radius = half_size * (0.8 + 0.4 * random.random())
        point_lat = lat + radius * (0.6 + 0.4 * random.random()) * (1 if i < num_points/2 else -1)
        point_lon = lon + radius * (0.6 + 0.4 * random.random()) * (1 if i % 2 == 0 else -1)
        points.append((point_lon, point_lat))

    # Close the polygon
    points.append(points[0])

    return Polygon(points)


def generate_sample_boundaries(cities):
    """
    Generate sample boundaries for all cities.

    Args:
        cities (list): List of city dictionaries

    Returns:
        gpd.GeoDataFrame: GeoDataFrame with sample city boundaries
    """
    features = []

    for city in cities:
        city_name = city['name']

        if city_name not in CITY_COORDINATES:
            logger.warning(f"No coordinates defined for {city_name}, skipping")
            continue

        coords = CITY_COORDINATES[city_name]
        polygon = create_city_polygon(coords['lat'], coords['lon'], coords['size'])

        feature = {
            'city_name': city_name,
            'state': city['state'],
            'country': city['country'],
            'geometry': polygon,
            'display_name': f"{city_name}, {city['state']}, {city['country']}",
            'osm_type': 'sample',
            'osm_id': None,
            'lat': coords['lat'],
            'lon': coords['lon'],
            'note': 'Sample boundary for development/testing'
        }

        features.append(feature)
        logger.info(f"Generated sample boundary for {city_name}")

    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(features, crs='EPSG:4326')
    return gdf


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
        logger.info("=" * 60)
        logger.info("Generating sample city boundaries")
        logger.info("NOTE: These are approximate boundaries for development/testing")
        logger.info("For production, use fetch_city_boundaries.py with OSM access")
        logger.info("=" * 60)

        logger.info(f"Generating boundaries for {len(PILOT_CITIES)} cities")

        # Generate sample boundaries
        boundaries_gdf = generate_sample_boundaries(PILOT_CITIES)

        # Define output path
        output_path = Path(__file__).parent.parent / "data" / "city_boundaries.geojson"

        # Save to GeoJSON
        save_to_geojson(boundaries_gdf, output_path)

        logger.info("=" * 60)
        logger.info("SUCCESS: Sample city boundaries generated and saved")
        logger.info(f"Output file: {output_path}")
        logger.info(f"Total cities: {len(boundaries_gdf)}")
        logger.info("=" * 60)

        # Print summary statistics
        logger.info("\nBoundary Summary:")
        for idx, row in boundaries_gdf.iterrows():
            area = row.geometry.area  # in square degrees
            logger.info(f"  {row['city_name']}: ~{area:.4f} sq degrees")

        return 0

    except Exception as e:
        logger.error(f"Fatal error in main execution: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
