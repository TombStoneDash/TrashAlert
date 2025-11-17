#!/usr/bin/env python3
"""
Build subdivision data for cities from various sources.
For cities with official pickup zones, use those.
For others, query OSM for neighborhoods/suburbs.
"""

import requests
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Optional
import time

from config_utils import load_cities_config, filter_cities, get_city_display_name

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_osm_subdivisions(city: Dict) -> List[Dict]:
    """
    Fetch neighborhood/suburb subdivisions from OpenStreetMap.

    Args:
        city: City dictionary from config

    Returns:
        List of subdivision features
    """
    city_name = city['name']
    state = city['state']

    logger.info(f"  Querying OSM for subdivisions in {city_name}...")

    # Use Overpass API to find suburbs/neighborhoods
    # This is a simplified query - in production you'd want more sophisticated logic
    overpass_url = "https://overpass-api.de/api/interpreter"

    # Query for places tagged as suburb or neighbourhood within the city
    query = f"""
    [out:json][timeout:30];
    area[name="{city_name}"]["admin_level"~"^(8|9)$"]->.city;
    (
      node["place"~"suburb|neighbourhood"](area.city);
      way["place"~"suburb|neighbourhood"](area.city);
      relation["place"~"suburb|neighbourhood"](area.city);
    );
    out center;
    """

    try:
        response = requests.post(overpass_url, data={'data': query}, timeout=60)
        response.raise_for_status()
        data = response.json()

        subdivisions = []
        for element in data.get('elements', []):
            if 'tags' in element and 'name' in element['tags']:
                subdivision = {
                    'id': f"osm_{element['type']}_{element['id']}",
                    'name': element['tags']['name'],
                    'type': element['tags'].get('place', 'unknown'),
                    'source': 'OpenStreetMap'
                }

                # Get coordinates
                if 'lat' in element and 'lon' in element:
                    subdivision['lat'] = element['lat']
                    subdivision['lon'] = element['lon']
                elif 'center' in element:
                    subdivision['lat'] = element['center']['lat']
                    subdivision['lon'] = element['center']['lon']

                subdivisions.append(subdivision)

        logger.info(f"    Found {len(subdivisions)} subdivisions")
        return subdivisions

    except requests.RequestException as e:
        logger.error(f"    Failed to fetch subdivisions: {e}")
        return []


def build_subdivisions_for_city(city: Dict, output_dir: Path) -> Optional[Path]:
    """
    Build subdivision data for a city.

    Args:
        city: City dictionary from config
        output_dir: Directory to save subdivision files

    Returns:
        Path to saved JSON file, or None if failed
    """
    display_name = get_city_display_name(city)
    logger.info(f"Building subdivisions for {display_name}...")

    # For now, we'll use OSM for all cities
    # In the future, this would check has_official_pickup_zones
    # and fetch from official sources if available
    subdivisions = fetch_osm_subdivisions(city)

    if not subdivisions:
        logger.warning(f"  No subdivisions found for {display_name}")
        # Create empty file to indicate we tried
        subdivisions = []

    # Save subdivisions
    city_slug = city['name'].lower().replace(' ', '_')
    output_file = output_dir / f"{city_slug}_subdivisions.json"

    output_data = {
        'city': city['name'],
        'state': city['state'],
        'subdivision_count': len(subdivisions),
        'subdivisions': subdivisions
    }

    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    logger.info(f"  Saved {len(subdivisions)} subdivisions to {output_file}")
    return output_file


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Build subdivision data for cities'
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
        help='Output directory for subdivision files (default: data/subdivisions)'
    )

    args = parser.parse_args()

    # Set up output directory
    base_dir = Path(__file__).parent.parent
    output_dir = args.output_dir or (base_dir / 'data' / 'subdivisions')
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load and filter cities
    logger.info("Loading cities from config...")
    cities = load_cities_config()
    cities = filter_cities(cities, only=args.only, state=args.state)

    if not cities:
        logger.error("No cities match the specified filters")
        return 1

    logger.info(f"Processing {len(cities)} cities")

    # Build subdivisions
    success_count = 0
    failed_count = 0

    for i, city in enumerate(cities):
        # Rate limiting for Overpass API
        if i > 0:
            time.sleep(2)

        result = build_subdivisions_for_city(city, output_dir)
        if result:
            success_count += 1
        else:
            failed_count += 1

    # Summary
    logger.info(f"\n{'='*80}")
    logger.info(f"SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"Successfully processed: {success_count} cities")
    logger.info(f"Failed: {failed_count} cities")
    logger.info(f"Output directory: {output_dir}")

    return 0 if failed_count == 0 else 1


if __name__ == '__main__':
    exit(main())
