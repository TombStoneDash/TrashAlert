#!/usr/bin/env python3
"""
Process OSM data to extract and normalize address information.

This script reads raw OSM JSON files and extracts address data,
normalizing it for use in trash collection route planning.
"""

import argparse
import json
from pathlib import Path
import sys
import csv
from typing import List, Dict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config_loader import ConfigLoader
from utils.logging_setup import setup_logging_from_config


class AddressProcessor:
    """Process and normalize address data from OSM"""

    def __init__(self, logger):
        self.logger = logger

    def extract_address_from_tags(self, tags: dict) -> Dict[str, str]:
        """
        Extract address components from OSM tags.

        Args:
            tags: OSM element tags dictionary

        Returns:
            Dictionary with normalized address components
        """
        address = {}

        # Standard OSM address tags
        address_fields = {
            'housenumber': 'addr:housenumber',
            'street': 'addr:street',
            'city': 'addr:city',
            'postcode': 'addr:postcode',
            'state': 'addr:state',
            'unit': 'addr:unit',
        }

        for key, tag in address_fields.items():
            if tag in tags:
                address[key] = tags[tag]

        return address

    def process_osm_file(self, input_file: Path, city: dict) -> List[Dict]:
        """
        Process a single OSM JSON file and extract addresses.

        Args:
            input_file: Path to OSM JSON file
            city: City configuration dictionary

        Returns:
            List of address dictionaries
        """
        self.logger.info(f"Processing {input_file.name}...")

        with open(input_file, 'r') as f:
            data = json.load(f)

        addresses = []
        elements = data.get('elements', [])

        for element in elements:
            tags = element.get('tags', {})

            # Skip if no address information
            if 'addr:housenumber' not in tags:
                continue

            address = self.extract_address_from_tags(tags)

            # Add city information if not present
            if 'city' not in address:
                address['city'] = city['name']
            if 'state' not in address:
                address['state'] = city['state']

            # Add coordinates
            if element['type'] == 'node':
                address['lat'] = element.get('lat')
                address['lon'] = element.get('lon')
            elif element['type'] == 'way':
                # For ways, we'd need to calculate centroid from nodes
                # For now, skip ways or use first node
                continue

            # Add OSM metadata
            address['osm_id'] = element.get('id')
            address['osm_type'] = element.get('type')

            addresses.append(address)

        self.logger.info(f"Extracted {len(addresses)} addresses from {input_file.name}")
        return addresses

    def save_addresses_csv(self, addresses: List[Dict], output_file: Path):
        """
        Save addresses to CSV file.

        Args:
            addresses: List of address dictionaries
            output_file: Path to output CSV file
        """
        if not addresses:
            self.logger.warning("No addresses to save")
            return

        fieldnames = [
            'osm_id', 'osm_type', 'housenumber', 'street', 'unit',
            'city', 'state', 'postcode', 'lat', 'lon'
        ]

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(addresses)

        self.logger.info(f"Saved {len(addresses)} addresses to {output_file}")

    def save_addresses_json(self, addresses: List[Dict], output_file: Path):
        """
        Save addresses to JSON file.

        Args:
            addresses: List of address dictionaries
            output_file: Path to output JSON file
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(addresses, f, indent=2)

        self.logger.info(f"Saved {len(addresses)} addresses to {output_file}")

    def save_addresses_geojson(self, addresses: List[Dict], output_file: Path, city: dict):
        """
        Save addresses as GeoJSON FeatureCollection.

        Args:
            addresses: List of address dictionaries
            output_file: Path to output GeoJSON file
            city: City configuration dictionary
        """
        features = []

        for addr in addresses:
            if 'lat' not in addr or 'lon' not in addr:
                continue

            feature = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [addr['lon'], addr['lat']]
                },
                'properties': {
                    'osm_id': addr.get('osm_id'),
                    'housenumber': addr.get('housenumber'),
                    'street': addr.get('street'),
                    'unit': addr.get('unit'),
                    'city': addr.get('city'),
                    'state': addr.get('state'),
                    'postcode': addr.get('postcode'),
                    'full_address': self.format_address(addr)
                }
            }
            features.append(feature)

        geojson = {
            'type': 'FeatureCollection',
            'metadata': {
                'city': city['name'],
                'city_id': city['id'],
                'state': city['state'],
                'count': len(features)
            },
            'features': features
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, indent=2)

        self.logger.info(f"Saved {len(features)} addresses as GeoJSON to {output_file}")

    def format_address(self, addr: dict) -> str:
        """
        Format address as human-readable string.

        Args:
            addr: Address dictionary

        Returns:
            Formatted address string
        """
        parts = []

        housenumber = addr.get('housenumber', '')
        street = addr.get('street', '')
        unit = addr.get('unit', '')
        city = addr.get('city', '')
        state = addr.get('state', '')
        postcode = addr.get('postcode', '')

        if unit:
            parts.append(f"{housenumber} {street} #{unit}")
        elif housenumber and street:
            parts.append(f"{housenumber} {street}")

        if city:
            parts.append(city)

        if state and postcode:
            parts.append(f"{state} {postcode}")
        elif state:
            parts.append(state)

        return ', '.join(parts)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Process OSM data to extract address information"
    )
    parser.add_argument(
        '--input-dir',
        type=str,
        default='data/raw',
        help='Input directory with OSM JSON files (default: data/raw)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/processed',
        help='Output directory for processed data (default: data/processed)'
    )
    parser.add_argument(
        '--city',
        type=str,
        help='Specific city ID to process (e.g., imperial_brawley)'
    )
    parser.add_argument(
        '--format',
        type=str,
        choices=['csv', 'json', 'geojson', 'all'],
        default='all',
        help='Output format (default: all)'
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

    logger = setup_logging_from_config(config, 'process_addresses')
    logger.setLevel(args.log_level)

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get input directory
    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        sys.exit(1)

    # Determine which cities to process
    if args.city:
        cities = [config_loader.get_city_by_id(args.city)]
        if cities[0] is None:
            logger.error(f"City not found: {args.city}")
            sys.exit(1)
    else:
        cities = config_loader.get_enabled_cities()

    # Process each city
    processor = AddressProcessor(logger)
    total_addresses = 0

    for city in cities:
        city_id = city['id']
        input_file = input_dir / f"{city_id}_osm.json"

        if not input_file.exists():
            logger.warning(f"Input file not found: {input_file}, skipping {city['name']}")
            continue

        # Process the file
        addresses = processor.process_osm_file(input_file, city)
        total_addresses += len(addresses)

        # Save in requested formats
        if args.format in ['csv', 'all']:
            output_file = output_dir / f"{city_id}_addresses.csv"
            processor.save_addresses_csv(addresses, output_file)

        if args.format in ['json', 'all']:
            output_file = output_dir / f"{city_id}_addresses.json"
            processor.save_addresses_json(addresses, output_file)

        if args.format in ['geojson', 'all']:
            output_file = output_dir / f"{city_id}_addresses.geojson"
            processor.save_addresses_geojson(addresses, output_file, city)

    # Summary
    logger.info("=" * 60)
    logger.info(f"Processing complete: {total_addresses} total addresses extracted")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
