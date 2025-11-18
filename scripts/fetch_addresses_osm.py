#!/usr/bin/env python3
"""
Fetch addresses from OpenStreetMap for configured cities.
Uses Overpass API to query address data within city boundaries.
"""

import requests
import pandas as pd
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config_loader import get_config_loader, get_city_display_name


class OverpassAPIClient:
    """Client for interacting with Overpass API with retry logic and rate limiting."""

    def __init__(self, config_loader, logger):
        """
        Initialize the Overpass API client.

        Args:
            config_loader: ConfigLoader instance
            logger: Logger instance
        """
        self.config = config_loader
        self.logger = logger

        # Load Overpass API settings from config
        overpass_config = self.config.pipeline_config['overpass_api']
        self.url = overpass_config['url']
        self.timeout = overpass_config['timeout_seconds']
        self.rate_limit_delay = overpass_config['rate_limit_delay_seconds']

        # Retry settings
        retry_config = overpass_config['retry']
        self.max_retries = retry_config['max_attempts']
        self.initial_delay = retry_config['initial_delay_seconds']
        self.backoff_multiplier = retry_config['backoff_multiplier']
        self.max_delay = retry_config['max_delay_seconds']

    def query(self, overpass_query: str) -> Optional[Dict]:
        """
        Execute an Overpass API query with retry logic.

        Args:
            overpass_query: The Overpass QL query string

        Returns:
            JSON response dict, or None if all retries failed
        """
        delay = self.initial_delay

        for attempt in range(self.max_retries):
            try:
                self.logger.debug(f"Querying Overpass API (attempt {attempt + 1}/{self.max_retries})...")

                response = requests.post(
                    self.url,
                    data={'data': overpass_query},
                    timeout=self.timeout
                )
                response.raise_for_status()

                return response.json()

            except requests.exceptions.Timeout:
                self.logger.warning(f"Request timed out (attempt {attempt + 1}/{self.max_retries})")

                if attempt < self.max_retries - 1:
                    self.logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                    delay = min(delay * self.backoff_multiplier, self.max_delay)

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Too Many Requests
                    self.logger.warning(f"Rate limited by Overpass API (attempt {attempt + 1}/{self.max_retries})")

                    if attempt < self.max_retries - 1:
                        # Use longer delay for rate limiting
                        rate_limit_delay = max(delay * 2, 10)
                        self.logger.info(f"Waiting {rate_limit_delay} seconds before retry...")
                        time.sleep(rate_limit_delay)
                        delay = min(delay * self.backoff_multiplier, self.max_delay)
                else:
                    self.logger.error(f"HTTP error: {e}")
                    if attempt < self.max_retries - 1:
                        self.logger.info(f"Retrying in {delay} seconds...")
                        time.sleep(delay)
                        delay = min(delay * self.backoff_multiplier, self.max_delay)

            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request failed: {e}")

                if attempt < self.max_retries - 1:
                    self.logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                    delay = min(delay * self.backoff_multiplier, self.max_delay)

        self.logger.error(f"All {self.max_retries} retry attempts failed")
        return None

    def rate_limit(self):
        """Apply rate limiting delay between requests."""
        if self.rate_limit_delay > 0:
            time.sleep(self.rate_limit_delay)


def fetch_addresses_for_city(
    city: Dict,
    api_client: OverpassAPIClient,
    subdivisions_dir: Optional[Path] = None,
    logger = None
) -> List[Dict]:
    """
    Fetch addresses from OSM for a specific city.

    Args:
        city: City dictionary from config
        api_client: OverpassAPIClient instance
        subdivisions_dir: Directory containing subdivision data
        logger: Logger instance

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

    # Execute query with retry logic
    data = api_client.query(query)

    if data is None:
        logger.error(f"  Failed to fetch addresses for {display_name}")
        return []

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


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Fetch addresses from OpenStreetMap for configured cities'
    )

    # City selection (mutually exclusive)
    city_group = parser.add_mutually_exclusive_group()
    city_group.add_argument(
        '--all',
        action='store_true',
        help='Process all cities in config'
    )
    city_group.add_argument(
        '--city-id',
        help='Process only specific city by ID (e.g., "ca_el_centro")'
    )
    city_group.add_argument(
        '--city',
        help='Process only specific city by name (e.g., "El Centro" or "El Centro, CA")'
    )
    city_group.add_argument(
        '--state',
        help='Process only cities in specific state (e.g., "CA" or "California")'
    )

    parser.add_argument(
        '--output',
        type=Path,
        help='Output CSV file (default from config: addresses_osm_raw)'
    )
    parser.add_argument(
        '--subdivisions-dir',
        type=Path,
        help='Directory with subdivision data (default from config: subdivisions)'
    )

    args = parser.parse_args()

    # Load configuration
    config = get_config_loader()
    logger = config.setup_logging(__name__)

    # Set up paths
    output_file = args.output or config.get_path('addresses_osm_raw')
    subdivisions_dir = args.subdivisions_dir or config.get_path('subdivisions', create_if_missing=False)

    # Determine which cities to process
    if not any([args.all, args.city_id, args.city, args.state]):
        # Default to all cities if no filter specified
        cities = config.filter_cities(all_cities=True)
    else:
        cities = config.filter_cities(
            city_id=args.city_id,
            city_name=args.city,
            state=args.state,
            all_cities=args.all
        )

    if not cities:
        logger.error("No cities match the specified filters")
        return 1

    logger.info(f"Processing {len(cities)} cities")

    # Create Overpass API client
    api_client = OverpassAPIClient(config, logger)

    # Fetch addresses for all cities
    all_addresses = []
    success_count = 0
    failed_count = 0

    for i, city in enumerate(cities):
        # Rate limiting between cities
        if i > 0:
            api_client.rate_limit()

        addresses = fetch_addresses_for_city(city, api_client, subdivisions_dir, logger)
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
    sys.exit(main())
