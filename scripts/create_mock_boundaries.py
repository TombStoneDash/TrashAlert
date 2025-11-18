#!/usr/bin/env python3
"""
Create mock boundary files for testing when Nominatim API is unavailable.
These are placeholder GeoJSON files with approximate bounding boxes.
"""

import json
import logging
from pathlib import Path
from config_utils import load_cities_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Approximate coordinates for each city (rough bounding boxes)
CITY_COORDINATES = {
    'San Diego': {
        'lat': 32.7157,
        'lon': -117.1611,
        'bbox': [-117.3, 32.5, -116.9, 33.0]  # [west, south, east, north]
    },
    'El Centro': {
        'lat': 32.7920,
        'lon': -115.5631,
        'bbox': [-115.6, 32.75, -115.5, 32.83]
    },
    'Calexico': {
        'lat': 32.6789,
        'lon': -115.4989,
        'bbox': [-115.55, 32.65, -115.45, 32.71]
    },
    'Brawley': {
        'lat': 32.9786,
        'lon': -115.5303,
        'bbox': [-115.58, 32.95, -115.48, 33.01]
    },
    'Imperial': {
        'lat': 32.8473,
        'lon': -115.5694,
        'bbox': [-115.6, 32.82, -115.54, 32.87]
    },
    'Holtville': {
        'lat': 32.8114,
        'lon': -115.3803,
        'bbox': [-115.42, 32.78, -115.34, 32.84]
    },
    'Fresno': {
        'lat': 36.7378,
        'lon': -119.7871,
        'bbox': [-120.0, 36.6, -119.6, 36.9]
    },
    'Riverside': {
        'lat': 33.9533,
        'lon': -117.3962,
        'bbox': [-117.5, 33.85, -117.3, 34.05]
    },
    'Sacramento': {
        'lat': 38.5816,
        'lon': -121.4944,
        'bbox': [-121.6, 38.4, -121.3, 38.7]
    },
    'Bakersfield': {
        'lat': 35.3733,
        'lon': -119.0187,
        'bbox': [-119.15, 35.25, -118.88, 35.5]
    }
}


def create_mock_boundary(city_name: str, coords: dict, output_dir: Path) -> Path:
    """
    Create a mock GeoJSON boundary file for a city.

    Args:
        city_name: Name of the city
        coords: Dictionary with lat, lon, and bbox
        output_dir: Directory to save the file

    Returns:
        Path to created file
    """
    # Create a simple polygon from the bounding box
    west, south, east, north = coords['bbox']

    # Create a rectangular polygon
    geojson = {
        "type": "Feature",
        "properties": {
            "name": city_name,
            "state": "California",
            "note": "Mock boundary for testing - replace with actual OSM data when available"
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [west, south],
                [east, south],
                [east, north],
                [west, north],
                [west, south]
            ]]
        },
        "bbox": coords['bbox']
    }

    output_file = output_dir / f"{city_name.lower().replace(' ', '_')}_boundary.geojson"
    with open(output_file, 'w') as f:
        json.dump(geojson, f, indent=2)

    logger.info(f"✓ Created mock boundary for {city_name} at {output_file}")
    return output_file


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent
    output_dir = base_dir / 'data' / 'boundaries'
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Creating mock boundary files...")

    # Load cities from config
    cities = load_cities_config()

    success_count = 0
    for city in cities:
        city_name = city['name']
        if city_name in CITY_COORDINATES:
            create_mock_boundary(city_name, CITY_COORDINATES[city_name], output_dir)
            success_count += 1
        else:
            logger.warning(f"No coordinates defined for {city_name}")

    logger.info(f"\n{'='*80}")
    logger.info(f"Created {success_count} mock boundary files")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"{'='*80}")
    logger.info("\nNOTE: These are mock boundaries for testing purposes.")
    logger.info("Replace with actual OSM data from Nominatim API when available.")

    return 0


if __name__ == '__main__':
    exit(main())
