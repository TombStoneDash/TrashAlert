#!/usr/bin/env python3
"""
Fetch addresses from OpenStreetMap for configured cities.
Uses Overpass API to query address data within city boundaries.
"""

import requests
import pandas as pd
import logging
import argparse
import json
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


def fetch_addresses_for_city(city: Dict, subdivisions_dir: Optional[Path] = None) -> List[Dict]:
    """
    Fetch addresses from OSM for a specific city.

    Args:
        city: City dictionary from config
        subdivisions_dir: Directory containing subdivision data

    Returns:
        List of address dictionaries
    """
    city_name = city['name']
    state = city['state']
    display_name = get_city_display_name(city)

    logger.info(f"Fetching addresses for {display_name}...")

    # Load subdivisions if available
    subdivisions = {}
    if subdivisions_dir:
        city_slug = city_name.lower().replace(' ', '_')
        subdivisions_file = subdivisions_dir / f"{city_slug}_subdivisions.json"
        if subdivisions_file.exists():
            with open(subdivisions_file, 'r') as f:
                sub_data = json.load(f)
                for sub in sub_data.get('subdivisions', []):
                    subdivisions[sub['id']] = sub['name']
            logger.info(f"  Loaded {len(subdivisions)} subdivisions")

    # Query Overpass API for addresses
    overpass_url = "https://overpass-api.de/api/interpreter"

    # Query for all nodes with addr:housenumber in the city
    query = f"""
    [out:json][timeout:90];
    area[name="{city_name}"]["admin_level"~"^(8|9)$"]->.city;
    (
      node["addr:housenumber"](area.city);
      way["addr:housenumber"](area.city);
    );
    out center;
    """

    try:
        logger.info(f"  Querying Overpass API...")
        response = requests.post(overpass_url, data={'data': query}, timeout=120)
        response.raise_for_status()
        data = response.json()

        addresses = []
        for element in data.get('elements', []):
            tags = element.get('tags', {})

            # Extract address components
            house_number = tags.get('addr:housenumber')
            street = tags.get('addr:street')

            if not house_number or not street:
                continue

            # Get coordinates
            if 'lat' in element and 'lon' in element:
                lat = element['lat']
                lon = element['lon']
            elif 'center' in element:
                lat = element['center']['lat']
                lon = element['center']['lon']
            else:
                continue

            address = {
                'city_name': city_name,
                'state': state,
                'house_number': house_number,
                'street': street,
                'lat': lat,
                'lon': lon,
                'osm_id': f"{element['type']}/{element['id']}",
                'subdivision_id': None  # Will be populated later if available
            }

            # Add optional fields
            if 'addr:city' in tags:
                address['addr_city'] = tags['addr:city']
            if 'addr:postcode' in tags:
                address['postcode'] = tags['addr:postcode']

            addresses.append(address)

        logger.info(f"  Found {len(addresses)} addresses")
        return addresses

    except requests.RequestException as e:
        logger.error(f"  Failed to fetch addresses for {display_name}: {e}")
        return []


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Fetch addresses from OpenStreetMap for configured cities'
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
        '--output',
        type=Path,
        help='Output CSV file (default: data/addresses_osm_raw.csv)'
    )
    parser.add_argument(
        '--subdivisions-dir',
        type=Path,
        help='Directory with subdivision data (default: data/subdivisions)'
    )

    args = parser.parse_args()

    # Set up paths
    base_dir = Path(__file__).parent.parent
    output_file = args.output or (base_dir / 'data' / 'addresses_osm_raw.csv')
    subdivisions_dir = args.subdivisions_dir or (base_dir / 'data' / 'subdivisions')

    # Load and filter cities
    logger.info("Loading cities from config...")
    cities = load_cities_config()
    cities = filter_cities(cities, only=args.only, state=args.state)

    if not cities:
        logger.error("No cities match the specified filters")
        return 1

    logger.info(f"Processing {len(cities)} cities")

    # Fetch addresses for all cities
    all_addresses = []
    success_count = 0
    failed_count = 0

    for i, city in enumerate(cities):
        # Rate limiting for Overpass API
        if i > 0:
            time.sleep(3)

        addresses = fetch_addresses_for_city(city, subdivisions_dir)
        if addresses:
            all_addresses.extend(addresses)
            success_count += 1
        else:
            failed_count += 1

    # Save to CSV
    if all_addresses:
        df = pd.DataFrame(all_addresses)
        df.to_csv(output_file, index=False)
        logger.info(f"\nSaved {len(all_addresses)} addresses to {output_file}")
    else:
        logger.warning("No addresses were fetched")

    # Summary
    logger.info(f"\n{'='*80}")
    logger.info(f"SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"Cities processed successfully: {success_count}")
    logger.info(f"Cities failed: {failed_count}")
    logger.info(f"Total addresses: {len(all_addresses)}")

    if all_addresses:
        # Show breakdown by city
        df = pd.DataFrame(all_addresses)
        city_counts = df.groupby('city_name').size().sort_values(ascending=False)
        logger.info(f"\nAddresses per city:")
        for city_name, count in city_counts.items():
            logger.info(f"  {city_name:30s} {count:6d}")

    return 0 if failed_count == 0 else 1


if __name__ == '__main__':
    exit(main())
