#!/usr/bin/env python3
"""
Fetch OpenStreetMap data for configured cities.

This script queries the Overpass API to download street networks,
addresses, and other relevant geographic data for trash collection routing.
"""

import argparse
import json
import time
from pathlib import Path
import sys
import requests

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config_loader import ConfigLoader
from utils.logging_setup import setup_logging_from_config


class OSMDataFetcher:
    """Fetch OpenStreetMap data via Overpass API"""

    def __init__(self, config_loader: ConfigLoader, logger):
        self.config_loader = config_loader
        self.logger = logger
        self.overpass_config = config_loader.get_overpass_config()
        self.timeout = self.overpass_config.get('timeout_seconds', 180)
        self.max_retries = self.overpass_config.get('max_retries', 3)
        self.rate_limit_delay = self.overpass_config.get('rate_limit_delay', 2.0)

    def build_overpass_query(self, city: dict) -> str:
        """
        Build Overpass QL query for a city.

        Args:
            city: City configuration dictionary

        Returns:
            Overpass QL query string
        """
        bbox = city['bbox']
        bbox_str = f"{bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']}"

        # Query for roads, addresses, and administrative boundaries
        query = f"""
[out:json][timeout:{self.timeout}][bbox:{bbox_str}];
(
  // Roads and streets
  way["highway"]["highway"!~"path|footway|cycleway|bridleway|steps|corridor|track"]
      ({bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']});

  // Buildings with addresses
  way["building"]["addr:housenumber"]
      ({bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']});
  node["addr:housenumber"]
      ({bbox['south']},{bbox['west']},{bbox['north']},{bbox['east']});

  // Administrative boundaries
  relation["boundary"="administrative"]["name"="{city['name']}"];
);
out body;
>;
out skel qt;
"""
        return query

    def fetch_city_data(self, city: dict, output_dir: Path) -> bool:
        """
        Fetch OSM data for a single city.

        Args:
            city: City configuration dictionary
            output_dir: Directory to save the data

        Returns:
            True if successful, False otherwise
        """
        city_id = city['id']
        city_name = city['name']

        self.logger.info(f"Fetching OSM data for {city_name} ({city_id})...")

        # Get Overpass API URL
        data_sources = city.get('data_sources', [])
        overpass_url = None
        for source in data_sources:
            if source.get('type') == 'overpass':
                overpass_url = source.get('url')
                break

        if not overpass_url:
            self.logger.warning(f"No Overpass API URL configured for {city_name}")
            return False

        # Build query
        query = self.build_overpass_query(city)

        # Fetch with retries
        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.debug(f"Attempt {attempt}/{self.max_retries}")

                response = requests.post(
                    overpass_url,
                    data={'data': query},
                    timeout=self.timeout
                )
                response.raise_for_status()

                data = response.json()

                # Save to file
                output_file = output_dir / f"{city_id}_osm.json"
                with open(output_file, 'w') as f:
                    json.dump(data, f, indent=2)

                element_count = len(data.get('elements', []))
                self.logger.info(
                    f"Successfully fetched {element_count} elements for {city_name}"
                )
                self.logger.info(f"Saved to {output_file}")

                # Rate limiting
                time.sleep(self.rate_limit_delay)

                return True

            except requests.exceptions.Timeout:
                self.logger.warning(
                    f"Timeout on attempt {attempt}/{self.max_retries} for {city_name}"
                )
                if attempt < self.max_retries:
                    time.sleep(self.rate_limit_delay * attempt)

            except requests.exceptions.RequestException as e:
                self.logger.error(f"Error fetching data for {city_name}: {e}")
                if attempt < self.max_retries:
                    time.sleep(self.rate_limit_delay * attempt)

            except Exception as e:
                self.logger.error(f"Unexpected error for {city_name}: {e}")
                return False

        self.logger.error(f"Failed to fetch data for {city_name} after {self.max_retries} attempts")
        return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Fetch OpenStreetMap data for configured cities"
    )
    parser.add_argument(
        '--city',
        type=str,
        help='Specific city ID to fetch (e.g., imperial_brawley). If not specified, fetches all enabled cities.'
    )
    parser.add_argument(
        '--region',
        type=str,
        help='Fetch all cities in a specific region (e.g., "Imperial Valley")'
    )
    parser.add_argument(
        '--county',
        type=str,
        help='Fetch all cities in a specific county (e.g., "Imperial")'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/raw',
        help='Output directory for downloaded data (default: data/raw)'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config/cities.yaml',
        help='Path to cities configuration file (default: config/cities.yaml)'
    )
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logging level (default: INFO)'
    )

    args = parser.parse_args()

    # Load configuration
    config_loader = ConfigLoader(args.config)

    # Setup logging
    with open(args.config, 'r') as f:
        import yaml
        config = yaml.safe_load(f)

    logger = setup_logging_from_config(config, 'fetch_osm_data')
    logger.setLevel(args.log_level)

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine which cities to fetch
    if args.city:
        cities = [config_loader.get_city_by_id(args.city)]
        if cities[0] is None:
            logger.error(f"City not found: {args.city}")
            sys.exit(1)
    elif args.region:
        cities = config_loader.get_cities_by_region(args.region)
        if not cities:
            logger.error(f"No cities found in region: {args.region}")
            sys.exit(1)
    elif args.county:
        cities = config_loader.get_cities_by_county(args.county)
        if not cities:
            logger.error(f"No cities found in county: {args.county}")
            sys.exit(1)
    else:
        cities = config_loader.get_enabled_cities()

    logger.info(f"Fetching data for {len(cities)} cities")

    # Fetch data
    fetcher = OSMDataFetcher(config_loader, logger)
    success_count = 0
    fail_count = 0

    for city in cities:
        if fetcher.fetch_city_data(city, output_dir):
            success_count += 1
        else:
            fail_count += 1

    # Summary
    logger.info("=" * 60)
    logger.info(f"Fetch complete: {success_count} succeeded, {fail_count} failed")
    logger.info("=" * 60)

    if fail_count > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
