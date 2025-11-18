#!/usr/bin/env python3
"""
Fetch addresses from OpenStreetMap for configured cities using Overpass API.

This script:
1. Queries OpenStreetMap (via Overpass) for address nodes/ways inside each pilot city boundary
2. Extracts: house_number, street, lat, lon
3. Stores raw OSM results under data/raw/osm/{city}.json
4. Normalizes into a unified CSV under data/processed/addresses_raw.csv

Respects Overpass API acceptable use policy:
- Rate limiting: 3 seconds between requests
- Timeout: 90 seconds per query
- Retry logic: Exponential backoff for transient failures
- User-Agent: Identifies the application

See: https://wiki.openstreetmap.org/wiki/Overpass_API#Acceptable_Use_Policy
"""

import requests
import pandas as pd
import logging
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from config_utils import load_cities_config, filter_cities, get_city_display_name

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Overpass API configuration
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
REQUEST_TIMEOUT = 120  # seconds
QUERY_TIMEOUT = 90  # seconds (in Overpass query)
RATE_LIMIT_DELAY = 3  # seconds between requests
MAX_RETRIES = 3
RETRY_DELAYS = [5, 10, 20]  # exponential backoff in seconds

# Fallback bounding boxes for pilot cities (south, west, north, east)
# These can be used when Nominatim is unavailable
CITY_BBOXES = {
    'Imperial': (32.8284, -115.5898, 32.8684, -115.5498),  # Imperial, CA
    'El Centro': (32.7690, -115.5859, 32.8090, -115.5459),  # El Centro, CA
    'Calexico': (32.6584, -115.5234, 32.6984, -115.4834),  # Calexico, CA
    'Brawley': (32.9586, -115.5520, 32.9986, -115.5120),  # Brawley, CA
    'San Diego': (32.5343, -117.2913, 33.1143, -116.9113),  # San Diego, CA (larger area)
    'Holtville': (32.7984, -115.3934, 32.8384, -115.3534),  # Holtville, CA
}


def get_city_bbox(city_name: str, state: str, use_fallback: bool = True) -> Optional[tuple]:
    """
    Get bounding box for a city using Nominatim API, with fallback to hardcoded values.

    Args:
        city_name: Name of the city
        state: State name
        use_fallback: If True, use hardcoded bounding boxes when Nominatim fails

    Returns:
        Tuple of (south, west, north, east) or None if not found
    """
    # Try fallback first if enabled and city is in our list
    if use_fallback and city_name in CITY_BBOXES:
        logger.info(f"  Using fallback bounding box for {city_name}")
        return CITY_BBOXES[city_name]

    # Try Nominatim API
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': f"{city_name}, {state}, USA",
        'format': 'json',
        'limit': 1
    }
    headers = {
        'User-Agent': 'TrashAlert/1.0 (https://github.com/TombStoneDash/TrashAlert)'
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data and len(data) > 0:
            bbox = data[0].get('boundingbox')
            if bbox and len(bbox) == 4:
                # Nominatim returns [south, north, west, east]
                # We need [south, west, north, east] for Overpass
                return (float(bbox[0]), float(bbox[2]), float(bbox[1]), float(bbox[3]))

    except requests.RequestException as e:
        logger.warning(f"  Failed to get bbox from Nominatim: {e}")

        # Try fallback if enabled
        if use_fallback and city_name in CITY_BBOXES:
            logger.info(f"  Using fallback bounding box for {city_name}")
            return CITY_BBOXES[city_name]

    return None


def build_overpass_query(bbox: tuple) -> str:
    """
    Build Overpass API query to fetch addresses within a bounding box.

    Args:
        bbox: Tuple of (south, west, north, east)

    Returns:
        Overpass QL query string
    """
    south, west, north, east = bbox

    # Query for all nodes and ways with addr:housenumber and addr:street
    # Uses bounding box which is more reliable
    query = f"""
[out:json][timeout:{QUERY_TIMEOUT}];
(
  node["addr:housenumber"]["addr:street"]({south},{west},{north},{east});
  way["addr:housenumber"]["addr:street"]({south},{west},{north},{east});
);
out center;
"""
    return query


def fetch_osm_data_with_retry(query: str, city_display_name: str) -> Optional[Dict]:
    """
    Fetch data from Overpass API with retry logic.

    Args:
        query: Overpass QL query
        city_display_name: City display name for logging

    Returns:
        JSON response from Overpass API, or None if all retries failed
    """
    headers = {
        'User-Agent': 'TrashAlert/1.0 (https://github.com/TombStoneDash/TrashAlert)'
    }

    for attempt in range(MAX_RETRIES):
        try:
            logger.info(f"  Querying Overpass API (attempt {attempt + 1}/{MAX_RETRIES})...")
            response = requests.post(
                OVERPASS_URL,
                data={'data': query},
                headers=headers,
                timeout=REQUEST_TIMEOUT
            )

            # Check for rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]))
                logger.warning(f"  Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                continue

            # Check for gateway timeout or server errors
            if response.status_code in [502, 503, 504]:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                    logger.warning(f"  Server error {response.status_code}. Retrying in {delay}s...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"  Server error {response.status_code} after {MAX_RETRIES} attempts")
                    return None

            # Raise for other HTTP errors
            response.raise_for_status()

            # Parse and return JSON
            return response.json()

        except requests.Timeout:
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                logger.warning(f"  Request timeout. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"  Request timeout after {MAX_RETRIES} attempts")
                return None

        except requests.RequestException as e:
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                logger.warning(f"  Network error: {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"  Failed after {MAX_RETRIES} attempts: {e}")
                return None

        except json.JSONDecodeError as e:
            logger.error(f"  Invalid JSON response: {e}")
            return None

    return None


def extract_addresses_from_osm_data(data: Dict, city_name: str, state_abbr: str) -> List[Dict]:
    """
    Extract address information from Overpass API response.

    Args:
        data: JSON response from Overpass API
        city_name: Name of the city
        state_abbr: State abbreviation

    Returns:
        List of address dictionaries
    """
    addresses = []

    for element in data.get('elements', []):
        tags = element.get('tags', {})

        # Extract required fields
        house_number = tags.get('addr:housenumber')
        street = tags.get('addr:street')

        if not house_number or not street:
            continue

        # Get coordinates (nodes have lat/lon directly, ways have center)
        if 'lat' in element and 'lon' in element:
            lat = element['lat']
            lon = element['lon']
        elif 'center' in element:
            lat = element['center']['lat']
            lon = element['center']['lon']
        else:
            continue

        # Build address record
        address = {
            'city_name': city_name,
            'house_number': house_number,
            'street': street,
            'lat': lat,
            'lon': lon,
            'source': 'OSM'
        }

        # Add optional fields for enrichment
        if 'addr:city' in tags:
            address['osm_addr_city'] = tags['addr:city']
        if 'addr:postcode' in tags:
            address['postcode'] = tags['addr:postcode']
        if 'addr:unit' in tags:
            address['unit'] = tags['addr:unit']

        # Add OSM metadata
        address['osm_id'] = f"{element['type']}/{element['id']}"
        address['osm_type'] = element['type']

        addresses.append(address)

    return addresses


def save_raw_json(data: Dict, output_file: Path) -> None:
    """
    Save raw Overpass API response to JSON file.

    Args:
        data: JSON response from Overpass API
        output_file: Path to output file
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    logger.info(f"  Saved raw OSM data to {output_file}")


def fetch_addresses_for_city(city: Dict, raw_dir: Path) -> Optional[List[Dict]]:
    """
    Fetch addresses from OSM for a specific city.

    Args:
        city: City dictionary from config
        raw_dir: Directory to save raw JSON files

    Returns:
        List of address dictionaries, or None if failed
    """
    city_name = city['name']
    state = city['state']
    state_abbr = city['state_abbr']
    display_name = get_city_display_name(city)

    logger.info(f"\nFetching addresses for {display_name}...")

    # Get bounding box from Nominatim
    logger.info(f"  Getting city bounding box from Nominatim...")
    bbox = get_city_bbox(city_name, state)

    if bbox is None:
        logger.error(f"  Failed to get bounding box for {display_name}")
        return None

    south, west, north, east = bbox
    logger.info(f"  Bounding box: ({south:.4f}, {west:.4f}, {north:.4f}, {east:.4f})")

    # Build query with bounding box
    query = build_overpass_query(bbox)

    # Fetch data with retry logic
    data = fetch_osm_data_with_retry(query, display_name)

    if data is None:
        logger.error(f"  Failed to fetch data for {display_name}")
        return None

    # Save raw JSON
    city_slug = city_name.lower().replace(' ', '_')
    raw_file = raw_dir / f"{city_slug}.json"
    save_raw_json(data, raw_file)

    # Extract addresses
    addresses = extract_addresses_from_osm_data(data, city_name, state_abbr)
    logger.info(f"  Extracted {len(addresses)} addresses")

    return addresses


def save_unified_csv(all_addresses: List[Dict], output_file: Path) -> None:
    """
    Save all addresses to a unified CSV file.

    Args:
        all_addresses: List of all address dictionaries
        output_file: Path to output CSV file
    """
    if not all_addresses:
        logger.warning("No addresses to save")
        return

    # Create DataFrame
    df = pd.DataFrame(all_addresses)

    # Ensure columns are in consistent order
    core_columns = ['city_name', 'house_number', 'street', 'lat', 'lon', 'source']
    other_columns = [col for col in df.columns if col not in core_columns]
    column_order = core_columns + sorted(other_columns)
    df = df[column_order]

    # Save to CSV
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False)
    logger.info(f"\nSaved {len(all_addresses)} addresses to {output_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Fetch addresses from OpenStreetMap for configured cities',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch addresses for all cities
  %(prog)s

  # Fetch addresses for a specific city
  %(prog)s --only "San Diego"

  # Fetch addresses for all cities in California
  %(prog)s --state CA

  # Custom output paths
  %(prog)s --raw-dir ./custom/raw --csv ./custom/addresses.csv
        """
    )
    parser.add_argument(
        '--only',
        help='Process only specific city (e.g., "San Diego")'
    )
    parser.add_argument(
        '--state',
        help='Process only cities in specific state (e.g., "CA" or "California")'
    )
    parser.add_argument(
        '--raw-dir',
        type=Path,
        help='Output directory for raw JSON files (default: data/raw/osm)'
    )
    parser.add_argument(
        '--csv',
        type=Path,
        help='Output CSV file (default: data/processed/addresses_raw.csv)'
    )

    args = parser.parse_args()

    # Set up paths
    base_dir = Path(__file__).parent.parent.parent
    raw_dir = args.raw_dir or (base_dir / 'data' / 'raw' / 'osm')
    csv_file = args.csv or (base_dir / 'data' / 'processed' / 'addresses_raw.csv')

    # Load and filter cities
    logger.info("Loading cities from config...")
    cities = load_cities_config()
    cities = filter_cities(cities, only=args.only, state=args.state)

    if not cities:
        logger.error("No cities match the specified filters")
        return 1

    logger.info(f"Processing {len(cities)} cities")
    logger.info(f"Raw JSON output: {raw_dir}")
    logger.info(f"CSV output: {csv_file}")

    # Fetch addresses for all cities
    all_addresses = []
    success_count = 0
    failed_cities = []

    for i, city in enumerate(cities):
        # Rate limiting for Nominatim (1s) and Overpass API (3s total)
        if i > 0:
            logger.info(f"\nRate limit delay: {RATE_LIMIT_DELAY}s...")
            time.sleep(RATE_LIMIT_DELAY)

        addresses = fetch_addresses_for_city(city, raw_dir)

        # Additional delay after Nominatim request (included in fetch_addresses_for_city)
        if i < len(cities) - 1:
            time.sleep(1)  # Nominatim requires 1s between requests

        if addresses is not None:
            all_addresses.extend(addresses)
            success_count += 1
        else:
            failed_cities.append(get_city_display_name(city))

    # Save unified CSV
    save_unified_csv(all_addresses, csv_file)

    # Summary
    logger.info(f"\n{'='*80}")
    logger.info(f"SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"Cities processed successfully: {success_count}/{len(cities)}")
    logger.info(f"Total addresses extracted: {len(all_addresses)}")

    if all_addresses:
        # Show breakdown by city
        df = pd.DataFrame(all_addresses)
        city_counts = df.groupby('city_name').size().sort_values(ascending=False)
        logger.info(f"\nAddresses per city:")
        for city_name, count in city_counts.items():
            logger.info(f"  {city_name:30s} {count:6d}")

    if failed_cities:
        logger.warning(f"\nFailed cities ({len(failed_cities)}):")
        for city in failed_cities:
            logger.warning(f"  - {city}")

    logger.info(f"\n{'='*80}")

    # Return exit code
    if failed_cities:
        return 1
    return 0


if __name__ == '__main__':
    exit(main())
