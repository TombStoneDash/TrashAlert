#!/usr/bin/env python3
"""
Fetch city boundaries from OpenStreetMap using Nominatim API.
Saves boundaries as GeoJSON files.
"""

import requests
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, Optional
import time

from config_utils import load_cities_config, filter_cities, get_city_display_name

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_city_boundary(city: Dict, output_dir: Path) -> Optional[Path]:
    """
    Fetch city boundary from Nominatim and save as GeoJSON.

    Args:
        city: City dictionary from config
        output_dir: Directory to save boundary files

    Returns:
        Path to saved GeoJSON file, or None if failed
    """
    city_name = city['name']
    state = city['state']
    display_name = get_city_display_name(city)

    logger.info(f"Fetching boundary for {display_name}...")

    # Construct search query
    query = f"{city_name}, {state}, USA"

    # Nominatim API endpoint
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': query,
        'format': 'geojson',
        'polygon_geojson': 1,
        'limit': 1
    }

    headers = {
        'User-Agent': 'TrashAlert Pipeline/1.0'
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()

        if not data.get('features'):
            logger.warning(f"No boundary found for {display_name}")
            return None

        # Save the boundary
        output_file = output_dir / f"{city_name.lower().replace(' ', '_')}_boundary.geojson"
        with open(output_file, 'w') as f:
            json.dump(data['features'][0], f, indent=2)

        logger.info(f"  Saved boundary to {output_file}")
        return output_file

    except requests.RequestException as e:
        logger.error(f"  Failed to fetch boundary for {display_name}: {e}")
        return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Fetch city boundaries from OpenStreetMap'
    )
    parser.add_argument(
        '--only',
        help='Process only specific city (e.g., "San Diego, California")'
    )
    parser.add_argument(
        '--state',
        help='Process only cities in specific state (e.g., "CA" or "California")'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        help='Output directory for boundary files (default: data/boundaries)'
    )

    args = parser.parse_args()

    # Set up output directory
    base_dir = Path(__file__).parent.parent
    output_dir = args.output_dir or (base_dir / 'data' / 'boundaries')
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load and filter cities
    logger.info("Loading cities from config...")
    cities = load_cities_config()
    cities = filter_cities(cities, only=args.only, state=args.state)

    if not cities:
        logger.error("No cities match the specified filters")
        return 1

    logger.info(f"Processing {len(cities)} cities")

    # Fetch boundaries
    success_count = 0
    failed_count = 0

    for i, city in enumerate(cities):
        # Rate limiting: wait 1 second between requests (Nominatim requirement)
        if i > 0:
            time.sleep(1)

        result = fetch_city_boundary(city, output_dir)
        if result:
            success_count += 1
        else:
            failed_count += 1

    # Summary
    logger.info(f"\n{'='*80}")
    logger.info(f"SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"Successfully fetched: {success_count} cities")
    logger.info(f"Failed: {failed_count} cities")
    logger.info(f"Output directory: {output_dir}")

    return 0 if failed_count == 0 else 1


if __name__ == '__main__':
    exit(main())
