#!/usr/bin/env python3
"""
Generate internal subdivisions for each pilot city to spread addresses geographically.

For San Diego: Attempts to use official neighborhoods if available.
For smaller cities: Creates a grid-based subdivision (3x3 or 4x4).

Outputs: data/processed/subdivisions.geojson
"""

import json
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.config_utils import load_cities_config, get_city_display_name

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Approximate center coordinates for each city (lat, lon)
CITY_CENTERS = {
    'San Diego': (32.7157, -117.1611),
    'El Centro': (32.7920, -115.5631),
    'Brawley': (32.9787, -115.5303),
    'Imperial': (32.8473, -115.5694),
    'Calexico': (32.6789, -115.4989),
    'Holtville': (32.8112, -115.3803),
}

# Approximate city sizes in degrees (roughly km-scale)
CITY_SIZES = {
    'San Diego': 0.30,      # Large city
    'El Centro': 0.05,      # Small city
    'Brawley': 0.04,        # Small city
    'Imperial': 0.03,       # Small city
    'Calexico': 0.04,       # Small city
    'Holtville': 0.03,      # Small city
}


def create_grid_subdivisions(
    city_name: str,
    center_lat: float,
    center_lon: float,
    size_deg: float,
    grid_size: int = 3
) -> List[Dict]:
    """
    Create a grid of subdivision polygons for a city.

    Args:
        city_name: Name of the city
        center_lat: Latitude of city center
        center_lon: Longitude of city center
        size_deg: Approximate size of city in degrees
        grid_size: Number of grid cells per side (3 = 3x3 grid, 4 = 4x4 grid)

    Returns:
        List of GeoJSON features representing subdivisions
    """
    # Create bounding box around city center
    half_size = size_deg / 2
    min_lat = center_lat - half_size
    max_lat = center_lat + half_size
    min_lon = center_lon - half_size
    max_lon = center_lon + half_size

    # Calculate cell dimensions
    lat_step = (max_lat - min_lat) / grid_size
    lon_step = (max_lon - min_lon) / grid_size

    subdivisions = []
    city_id = city_name.upper().replace(' ', '_')

    for row in range(grid_size):
        for col in range(grid_size):
            # Calculate cell bounds
            cell_min_lat = min_lat + (row * lat_step)
            cell_max_lat = cell_min_lat + lat_step
            cell_min_lon = min_lon + (col * lon_step)
            cell_max_lon = cell_min_lon + lon_step

            # Create polygon coordinates (counter-clockwise)
            coordinates = [[
                [cell_min_lon, cell_min_lat],  # Bottom-left
                [cell_max_lon, cell_min_lat],  # Bottom-right
                [cell_max_lon, cell_max_lat],  # Top-right
                [cell_min_lon, cell_max_lat],  # Top-left
                [cell_min_lon, cell_min_lat],  # Close polygon
            ]]

            # Create subdivision ID and name
            subdivision_id = f"{city_id}_G{row * grid_size + col + 1}"
            subdivision_name = f"Grid {row + 1}-{col + 1}"

            # Create GeoJSON feature
            feature = {
                "type": "Feature",
                "properties": {
                    "subdivision_id": subdivision_id,
                    "city_id": city_id,
                    "city_name": city_name,
                    "name": subdivision_name,
                    "grid_row": row,
                    "grid_col": col,
                    "grid_size": grid_size,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": coordinates
                }
            }

            subdivisions.append(feature)

    logger.info(f"  Created {len(subdivisions)} grid subdivisions ({grid_size}x{grid_size})")
    return subdivisions


def create_san_diego_neighborhoods() -> List[Dict]:
    """
    Create neighborhood-based subdivisions for San Diego.

    For now, uses a simplified set of major neighborhoods with approximate boundaries.
    In production, this could load from official city data.

    Returns:
        List of GeoJSON features representing neighborhoods
    """
    # Simplified major San Diego neighborhoods with approximate centers and sizes
    neighborhoods = [
        {
            "name": "Downtown",
            "center": (32.7157, -117.1611),
            "size": 0.02,
        },
        {
            "name": "La Jolla",
            "center": (32.8328, -117.2713),
            "size": 0.03,
        },
        {
            "name": "Pacific Beach",
            "center": (32.7942, -117.2416),
            "size": 0.02,
        },
        {
            "name": "North Park",
            "center": (32.7442, -117.1294),
            "size": 0.025,
        },
        {
            "name": "Hillcrest",
            "center": (32.7489, -117.1661),
            "size": 0.015,
        },
        {
            "name": "Mission Valley",
            "center": (32.7740, -117.1662),
            "size": 0.03,
        },
        {
            "name": "Point Loma",
            "center": (32.7089, -117.2438),
            "size": 0.03,
        },
        {
            "name": "Chula Vista",
            "center": (32.6401, -117.0842),
            "size": 0.04,
        },
        {
            "name": "Clairemont",
            "center": (32.8175, -117.2033),
            "size": 0.025,
        },
    ]

    features = []
    for i, neighborhood in enumerate(neighborhoods):
        center_lat, center_lon = neighborhood["center"]
        size = neighborhood["size"]
        half_size = size / 2

        # Create rectangular boundary
        min_lat = center_lat - half_size
        max_lat = center_lat + half_size
        min_lon = center_lon - half_size
        max_lon = center_lon + half_size

        coordinates = [[
            [min_lon, min_lat],
            [max_lon, min_lat],
            [max_lon, max_lat],
            [min_lon, max_lat],
            [min_lon, min_lat],
        ]]

        subdivision_id = f"SD_{neighborhood['name'].upper().replace(' ', '_')}"

        feature = {
            "type": "Feature",
            "properties": {
                "subdivision_id": subdivision_id,
                "city_id": "SAN_DIEGO",
                "city_name": "San Diego",
                "name": neighborhood["name"],
                "type": "neighborhood",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": coordinates
            }
        }

        features.append(feature)

    logger.info(f"  Created {len(features)} neighborhood subdivisions")
    return features


def generate_subdivisions_for_city(city: Dict, use_neighborhoods: bool = True) -> List[Dict]:
    """
    Generate subdivisions for a given city.

    Args:
        city: City dictionary from config
        use_neighborhoods: If True, use neighborhoods for San Diego

    Returns:
        List of GeoJSON features
    """
    city_name = city['name']
    display_name = get_city_display_name(city)
    logger.info(f"Generating subdivisions for {display_name}...")

    # Special handling for San Diego
    if city_name == 'San Diego' and use_neighborhoods:
        return create_san_diego_neighborhoods()

    # Get city parameters
    if city_name not in CITY_CENTERS:
        logger.warning(f"  No center coordinates for {city_name}, skipping")
        return []

    center_lat, center_lon = CITY_CENTERS[city_name]
    size_deg = CITY_SIZES.get(city_name, 0.05)

    # Determine grid size based on city size
    # Larger cities get 4x4 grids, smaller get 3x3
    grid_size = 4 if size_deg > 0.1 else 3

    return create_grid_subdivisions(
        city_name,
        center_lat,
        center_lon,
        size_deg,
        grid_size
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate geographic subdivisions for pilot cities'
    )
    parser.add_argument(
        '--output',
        type=Path,
        help='Output GeoJSON file path (default: data/processed/subdivisions.geojson)'
    )
    parser.add_argument(
        '--grid-only',
        action='store_true',
        help='Use grid subdivisions for all cities (including San Diego)'
    )
    parser.add_argument(
        '--only',
        help='Process only specific city (e.g., "San Diego")'
    )

    args = parser.parse_args()

    # Set up output path
    base_dir = Path(__file__).parent.parent.parent
    output_file = args.output or (base_dir / 'data' / 'processed' / 'subdivisions.geojson')
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Load cities
    logger.info("Loading cities from config...")
    cities = load_cities_config()

    # Filter if requested
    if args.only:
        cities = [c for c in cities if c['name'].lower() == args.only.lower()]
        if not cities:
            logger.error(f"City '{args.only}' not found in config")
            return 1

    logger.info(f"Processing {len(cities)} cities")

    # Generate subdivisions for each city
    all_features = []
    for city in cities:
        features = generate_subdivisions_for_city(
            city,
            use_neighborhoods=not args.grid_only
        )
        all_features.extend(features)

    # Create GeoJSON FeatureCollection
    geojson = {
        "type": "FeatureCollection",
        "features": all_features,
        "properties": {
            "description": "City subdivisions for TrashAlert pilot cities",
            "generated_by": "generate_subdivisions.py",
            "city_count": len(cities),
            "subdivision_count": len(all_features),
        }
    }

    # Write output
    with open(output_file, 'w') as f:
        json.dump(geojson, f, indent=2)

    logger.info(f"\n{'='*80}")
    logger.info(f"SUCCESS")
    logger.info(f"{'='*80}")
    logger.info(f"Generated {len(all_features)} subdivisions for {len(cities)} cities")
    logger.info(f"Output: {output_file}")

    # Print summary by city
    logger.info("\nSubdivisions by city:")
    city_counts = {}
    for feature in all_features:
        city_name = feature['properties']['city_name']
        city_counts[city_name] = city_counts.get(city_name, 0) + 1

    for city_name, count in sorted(city_counts.items()):
        logger.info(f"  {city_name}: {count} subdivisions")

    return 0


if __name__ == '__main__':
    exit(main())
