#!/usr/bin/env python3
"""
Generate approximate city boundaries when Nominatim is unavailable.
Creates circular approximations based on city center coordinates and typical city sizes.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List
import math

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.cities_config import get_pilot_cities, get_city_display_name

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Approximate city centers and radii (in km)
CITY_DATA = {
    'San Diego': {
        'lat': 32.7157,
        'lon': -117.1611,
        'radius_km': 15,  # Large city
    },
    'El Centro': {
        'lat': 32.7920,
        'lon': -115.5630,
        'radius_km': 4,  # County seat, moderate size
    },
    'Calexico': {
        'lat': 32.6789,
        'lon': -115.4989,
        'radius_km': 3,  # Border city
    },
    'Brawley': {
        'lat': 32.9786,
        'lon': -115.5303,
        'radius_km': 3,  # Agricultural city
    },
    'Imperial': {
        'lat': 32.8473,
        'lon': -115.5694,
        'radius_km': 2,  # Small city
    },
    'Holtville': {
        'lat': 32.8117,
        'lon': -115.3803,
        'radius_km': 2,  # Small town
    },
}


def create_circular_polygon(lat: float, lon: float, radius_km: float, num_points: int = 32) -> List[List[float]]:
    """
    Create a circular polygon approximation.

    Args:
        lat: Center latitude
        lon: Center longitude
        radius_km: Radius in kilometers
        num_points: Number of points in the circle

    Returns:
        List of [lon, lat] coordinate pairs forming a closed polygon
    """
    # Earth's radius in km
    earth_radius = 6371.0

    # Convert radius from km to degrees (approximate)
    radius_lat = radius_km / 111.0  # 1 degree latitude ≈ 111 km
    radius_lon = radius_km / (111.0 * math.cos(math.radians(lat)))

    coordinates = []

    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        point_lat = lat + radius_lat * math.sin(angle)
        point_lon = lon + radius_lon * math.cos(angle)
        coordinates.append([point_lon, point_lat])

    # Close the polygon
    coordinates.append(coordinates[0])

    return coordinates


def create_city_boundary_geojson(city_name: str, data: Dict) -> Dict:
    """
    Create a GeoJSON feature for a city boundary.

    Args:
        city_name: Name of the city
        data: Dictionary with lat, lon, and radius_km

    Returns:
        GeoJSON feature dictionary
    """
    coordinates = create_circular_polygon(
        data['lat'],
        data['lon'],
        data['radius_km']
    )

    return {
        "type": "Feature",
        "properties": {
            "name": city_name,
            "display_name": f"{city_name}, California, USA",
            "type": "city",
            "generated": "fallback_circular_approximation",
            "center_lat": data['lat'],
            "center_lon": data['lon'],
            "approx_radius_km": data['radius_km']
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [coordinates]
        }
    }


def generate_individual_boundaries(output_dir: Path) -> int:
    """
    Generate individual boundary files for each city.

    Args:
        output_dir: Directory to save boundary files

    Returns:
        Number of boundaries successfully generated
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    success_count = 0

    for city_name, data in CITY_DATA.items():
        feature = create_city_boundary_geojson(city_name, data)

        output_file = output_dir / f"{city_name.lower().replace(' ', '_')}_boundary.geojson"

        with open(output_file, 'w') as f:
            json.dump(feature, f, indent=2)

        logger.info(f"  Created boundary for {city_name} -> {output_file}")
        success_count += 1

    return success_count


def generate_consolidated_boundaries(output_file: Path) -> int:
    """
    Generate a single GeoJSON FeatureCollection with all city boundaries.

    Args:
        output_file: Path to output GeoJSON file

    Returns:
        Number of features in the collection
    """
    features = []

    for city_name, data in CITY_DATA.items():
        feature = create_city_boundary_geojson(city_name, data)
        features.append(feature)

    feature_collection = {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "generated_by": "generate_city_boundaries_fallback.py",
            "description": "Approximate city boundaries for TrashAlert pilot cities",
            "note": "These are circular approximations and not official boundaries",
            "total_cities": len(features)
        }
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        json.dump(feature_collection, f, indent=2)

    logger.info(f"\nCreated consolidated boundaries file: {output_file}")
    return len(features)


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent

    logger.info("Generating fallback city boundaries...")
    logger.info("=" * 80)

    # Generate individual boundary files
    boundaries_dir = base_dir / 'data' / 'boundaries'
    count = generate_individual_boundaries(boundaries_dir)
    logger.info(f"\nGenerated {count} individual boundary files in {boundaries_dir}")

    # Generate consolidated file
    consolidated_file = base_dir / 'data' / 'processed' / 'city_boundaries.geojson'
    feature_count = generate_consolidated_boundaries(consolidated_file)

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total cities: {feature_count}")
    logger.info(f"Individual boundaries: {boundaries_dir}")
    logger.info(f"Consolidated file: {consolidated_file}")
    logger.info("=" * 80)
    logger.info("\nNOTE: These are circular approximations, not official boundaries.")
    logger.info("For production use, obtain official GIS boundary data from:")
    logger.info("  - City/County GIS departments")
    logger.info("  - US Census TIGER/Line files")
    logger.info("  - OpenStreetMap (when API is accessible)")

    return 0


if __name__ == '__main__':
    exit(main())
