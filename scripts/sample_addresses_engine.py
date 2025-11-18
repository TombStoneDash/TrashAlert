#!/usr/bin/env python3
"""
Automated Address Sampling Engine for TrashAlert

This script generates random sample points within city boundaries and reverse-geocodes
them to valid addresses using OpenStreetMap Nominatim API.

Features:
- Generates 50 random sample points per city
- Reverse-geocodes using Nominatim with 1 req/sec rate limiting
- Normalizes addresses to USPS format
- Implements retry logic with exponential backoff
- Caches results to avoid duplicate API calls
- Saves failed lookups separately for debugging

Output:
- data/processed/addresses/{city}.json - Valid addresses for each city
- data/processed/addresses/{city}_failed.json - Failed lookups
- data/processed/addresses/cache.json - Cache of reverse geocoding results
"""

import json
import logging
import time
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import hashlib

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import geopandas as gpd
from shapely.geometry import Point, Polygon, MultiPolygon, shape
from shapely.ops import unary_union
import random

from src.normalization import normalize_address
from scripts.config_utils import load_cities_config, filter_cities, get_city_display_name

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Address:
    """Structured address data"""
    lat: float
    lon: float
    house_number: Optional[str]
    street: Optional[str]
    city: Optional[str]
    state: Optional[str]
    postcode: Optional[str]
    country: Optional[str]
    display_name: str
    normalized_address: str
    osm_type: Optional[str] = None
    osm_id: Optional[int] = None


class RateLimiter:
    """Rate limiter for API calls (1 request per second for Nominatim)"""

    def __init__(self, min_interval: float = 1.0):
        """
        Args:
            min_interval: Minimum seconds between requests (default: 1.0 for Nominatim)
        """
        self.min_interval = min_interval
        self.last_request_time = 0

    def wait(self):
        """Wait if necessary to maintain rate limit"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)

        self.last_request_time = time.time()


class GeocodingCache:
    """Cache for reverse geocoding results to avoid duplicate API calls"""

    def __init__(self, cache_file: Path):
        """
        Args:
            cache_file: Path to cache JSON file
        """
        self.cache_file = cache_file
        self.cache: Dict[str, Dict] = {}
        self._load_cache()

    def _load_cache(self):
        """Load cache from disk"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    self.cache = json.load(f)
                logger.info(f"Loaded {len(self.cache)} cached entries")
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
                self.cache = {}

    def save(self):
        """Save cache to disk"""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
            logger.info(f"Saved cache with {len(self.cache)} entries")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def _get_key(self, lat: float, lon: float) -> str:
        """Generate cache key from coordinates (rounded to 6 decimal places)"""
        # Round to ~0.11m precision
        key = f"{lat:.6f},{lon:.6f}"
        return hashlib.md5(key.encode()).hexdigest()

    def get(self, lat: float, lon: float) -> Optional[Dict]:
        """Get cached result for coordinates"""
        key = self._get_key(lat, lon)
        return self.cache.get(key)

    def set(self, lat: float, lon: float, result: Dict):
        """Cache result for coordinates"""
        key = self._get_key(lat, lon)
        self.cache[key] = result


class AddressSamplingEngine:
    """Main engine for generating and geocoding random address samples"""

    def __init__(self, output_dir: Path, cache_dir: Path):
        """
        Args:
            output_dir: Directory to save address results
            cache_dir: Directory for cache files
        """
        self.output_dir = output_dir
        self.cache_dir = cache_dir
        self.rate_limiter = RateLimiter(min_interval=1.0)
        self.cache = GeocodingCache(cache_dir / 'reverse_geocoding_cache.json')

        # Nominatim API configuration
        self.nominatim_url = "https://nominatim.openstreetmap.org/reverse"
        self.user_agent = "TrashAlert/1.0 (+https://github.com/TombStoneDash/TrashAlert; contact@trashalert.app)"

    def fetch_city_boundary_overpass(self, city: Dict) -> Optional[Polygon]:
        """
        Fetch city boundary from Overpass API (OSM).

        Args:
            city: City dictionary from config

        Returns:
            Shapely Polygon/MultiPolygon or None if failed
        """
        city_name = city['name']
        state = city['state']
        display_name = get_city_display_name(city)

        logger.info(f"Fetching boundary for {display_name} from Overpass API...")

        # Overpass API query for city boundary
        query = f"""
        [out:json][timeout:25];
        area["name"="{city_name}"]["admin_level"="8"]["place"="city"]->.searchArea;
        (
          relation["boundary"="administrative"](area.searchArea);
        );
        out geom;
        """

        overpass_url = "https://overpass-api.de/api/interpreter"

        try:
            self.rate_limiter.wait()
            response = requests.post(overpass_url, data={'data': query}, timeout=30)
            response.raise_for_status()

            data = response.json()

            if not data.get('elements'):
                logger.warning(f"No boundary found in Overpass, trying simplified query...")
                # Try simpler query
                query2 = f"""
                [out:json][timeout:25];
                (
                  relation["name"="{city_name}"]["boundary"="administrative"];
                );
                out geom;
                """
                response = requests.post(overpass_url, data={'data': query2}, timeout=30)
                response.raise_for_status()
                data = response.json()

            if not data.get('elements'):
                logger.error(f"No boundary found for {display_name}")
                return None

            # Convert Overpass result to GeoJSON
            element = data['elements'][0]

            if element['type'] == 'relation' and 'members' in element:
                # Extract coordinates from way members
                coords = []
                for member in element['members']:
                    if member['type'] == 'way' and 'geometry' in member:
                        way_coords = [(node['lon'], node['lat']) for node in member['geometry']]
                        coords.extend(way_coords)

                if coords:
                    return Polygon(coords)

            return None

        except Exception as e:
            logger.error(f"Failed to fetch boundary from Overpass: {e}")
            return None

    def fetch_city_boundary(self, city: Dict) -> Optional[Polygon]:
        """
        Fetch city boundary from cache or OSM.

        Args:
            city: City dictionary from config

        Returns:
            Shapely Polygon/MultiPolygon or None if failed
        """
        city_name = city['name']
        state = city['state']
        display_name = get_city_display_name(city)

        # Check for existing boundary file in cache
        boundary_file = self.cache_dir / f"{city_name.lower().replace(' ', '_')}_boundary.geojson"

        if boundary_file.exists():
            logger.info(f"Loading cached boundary for {display_name}")
            try:
                gdf = gpd.read_file(boundary_file)
                if len(gdf) > 0:
                    geom = gdf.iloc[0].geometry
                    # Handle MultiPolygon by merging
                    if isinstance(geom, MultiPolygon):
                        return unary_union(geom)
                    return geom
            except Exception as e:
                logger.warning(f"Failed to load cached boundary: {e}")

        # Try Overpass API
        boundary = self.fetch_city_boundary_overpass(city)

        if boundary:
            # Save for future use
            boundary_file.parent.mkdir(parents=True, exist_ok=True)
            gdf = gpd.GeoDataFrame([{'geometry': boundary}], crs='EPSG:4326')
            gdf.to_file(boundary_file, driver='GeoJSON')
            logger.info(f"Saved boundary to cache: {boundary_file}")

        return boundary

    def generate_random_points(self, polygon: Polygon, num_points: int = 50,
                              max_attempts: int = 1000) -> List[Tuple[float, float]]:
        """
        Generate random points within a polygon using rejection sampling.

        Args:
            polygon: Shapely Polygon to sample from
            num_points: Number of points to generate (default: 50)
            max_attempts: Maximum attempts to prevent infinite loops

        Returns:
            List of (lat, lon) tuples
        """
        points = []
        bounds = polygon.bounds  # (minx, miny, maxx, maxy)
        minx, miny, maxx, maxy = bounds

        attempts = 0
        while len(points) < num_points and attempts < max_attempts:
            # Generate random point in bounding box
            x = random.uniform(minx, maxx)
            y = random.uniform(miny, maxy)
            point = Point(x, y)

            # Check if point is within polygon
            if polygon.contains(point):
                points.append((y, x))  # Return as (lat, lon)

            attempts += 1

        if len(points) < num_points:
            logger.warning(f"Only generated {len(points)}/{num_points} points after {attempts} attempts")

        return points

    def reverse_geocode(self, lat: float, lon: float, max_retries: int = 3) -> Optional[Dict]:
        """
        Reverse geocode coordinates to address using Nominatim with retry logic.

        Args:
            lat: Latitude
            lon: Longitude
            max_retries: Maximum number of retry attempts

        Returns:
            Address data dictionary or None if failed
        """
        # Check Redis cache first (if available)
        try:
            from app.redis_cache import redis_cache
            cache_key = f"reverse_geocode:{lat:.6f},{lon:.6f}"
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Redis cache hit for ({lat:.6f}, {lon:.6f})")
                return cached
        except ImportError:
            pass  # Redis not available in this context

        # Check file cache
        cached = self.cache.get(lat, lon)
        if cached is not None:
            logger.debug(f"File cache hit for ({lat:.6f}, {lon:.6f})")
            return cached

        # Make API request with retry logic
        params = {
            'lat': lat,
            'lon': lon,
            'format': 'json',
            'addressdetails': 1,
            'zoom': 18  # Building level detail
        }
        headers = {'User-Agent': self.user_agent}

        for attempt in range(max_retries):
            try:
                self.rate_limiter.wait()
                response = requests.get(
                    self.nominatim_url,
                    params=params,
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()

                data = response.json()

                # Validate response has address data
                if 'error' in data:
                    logger.warning(f"Nominatim error: {data['error']}")
                    result = None
                else:
                    result = data

                # Cache result in file cache (even if None to avoid repeated failures)
                self.cache.set(lat, lon, result)

                # Also cache in Redis (if available) with 1 hour TTL
                try:
                    from app.redis_cache import redis_cache
                    cache_key = f"reverse_geocode:{lat:.6f},{lon:.6f}"
                    redis_cache.set(cache_key, result, ttl=3600)
                except ImportError:
                    pass  # Redis not available in this context

                return result

            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}")

                if attempt < max_retries - 1:
                    # Exponential backoff: 2s, 4s, 8s
                    backoff = 2 ** (attempt + 1)
                    logger.info(f"Retrying in {backoff}s...")
                    time.sleep(backoff)
                else:
                    logger.error(f"Failed to geocode ({lat:.6f}, {lon:.6f}) after {max_retries} attempts")
                    # Cache failure
                    self.cache.set(lat, lon, None)
                    return None

        return None

    def parse_address(self, geocode_result: Dict, lat: float, lon: float) -> Optional[Address]:
        """
        Parse Nominatim result into structured Address object.

        Args:
            geocode_result: Raw Nominatim response
            lat: Original latitude
            lon: Original longitude

        Returns:
            Address object or None if parsing failed
        """
        if not geocode_result or 'address' not in geocode_result:
            return None

        addr = geocode_result.get('address', {})

        # Extract components
        house_number = addr.get('house_number')
        street = addr.get('road')
        city = addr.get('city') or addr.get('town') or addr.get('village')
        state = addr.get('state')
        postcode = addr.get('postcode')
        country = addr.get('country')
        display_name = geocode_result.get('display_name', '')

        # Require at least street or house number
        if not street and not house_number:
            return None

        # Build normalized address
        if house_number and street:
            full_address = f"{house_number} {street}"
        elif street:
            full_address = street
        else:
            return None

        normalized = normalize_address(full_address)

        return Address(
            lat=lat,
            lon=lon,
            house_number=house_number,
            street=street,
            city=city,
            state=state,
            postcode=postcode,
            country=country,
            display_name=display_name,
            normalized_address=normalized,
            osm_type=geocode_result.get('osm_type'),
            osm_id=geocode_result.get('osm_id')
        )

    def sample_city_addresses(self, city: Dict, num_samples: int = 50) -> Tuple[List[Address], List[Dict]]:
        """
        Generate address samples for a city.

        Args:
            city: City dictionary from config
            num_samples: Number of addresses to generate (default: 50)

        Returns:
            Tuple of (successful_addresses, failed_attempts)
        """
        display_name = get_city_display_name(city)
        logger.info(f"\n{'='*80}")
        logger.info(f"Sampling addresses for {display_name}")
        logger.info(f"{'='*80}")

        # Step 1: Get city boundary
        boundary = self.fetch_city_boundary(city)
        if boundary is None:
            logger.error(f"Cannot sample without city boundary")
            return [], []

        logger.info(f"✓ City boundary loaded")

        # Step 2: Generate random points
        logger.info(f"Generating {num_samples} random sample points...")
        points = self.generate_random_points(boundary, num_samples)
        logger.info(f"✓ Generated {len(points)} points")

        # Step 3: Reverse geocode each point
        logger.info(f"Reverse geocoding {len(points)} points...")
        addresses = []
        failed = []

        for i, (lat, lon) in enumerate(points, 1):
            logger.info(f"  [{i}/{len(points)}] Geocoding ({lat:.6f}, {lon:.6f})...")

            geocode_result = self.reverse_geocode(lat, lon)

            if geocode_result:
                address = self.parse_address(geocode_result, lat, lon)
                if address:
                    logger.info(f"    ✓ {address.normalized_address}")
                    addresses.append(address)
                else:
                    logger.warning(f"    ✗ Failed to parse address")
                    failed.append({
                        'lat': lat,
                        'lon': lon,
                        'reason': 'parse_failed',
                        'raw_result': geocode_result
                    })
            else:
                logger.warning(f"    ✗ Geocoding failed")
                failed.append({
                    'lat': lat,
                    'lon': lon,
                    'reason': 'geocoding_failed'
                })

        logger.info(f"\n{'='*80}")
        logger.info(f"RESULTS for {display_name}")
        logger.info(f"{'='*80}")
        logger.info(f"✓ Successful: {len(addresses)}/{num_samples}")
        logger.info(f"✗ Failed: {len(failed)}/{num_samples}")

        return addresses, failed

    def save_results(self, city: Dict, addresses: List[Address], failed: List[Dict]):
        """
        Save address results to JSON files.

        Args:
            city: City dictionary from config
            addresses: List of successful Address objects
            failed: List of failed attempt dictionaries
        """
        city_name = city['name'].lower().replace(' ', '_')

        # Save successful addresses
        output_file = self.output_dir / f"{city_name}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(
                {
                    'city': city['name'],
                    'state': city['state'],
                    'count': len(addresses),
                    'addresses': [asdict(addr) for addr in addresses]
                },
                f,
                indent=2
            )
        logger.info(f"✓ Saved {len(addresses)} addresses to {output_file}")

        # Save failed lookups if any
        if failed:
            failed_file = self.output_dir / f"{city_name}_failed.json"
            with open(failed_file, 'w') as f:
                json.dump(
                    {
                        'city': city['name'],
                        'state': city['state'],
                        'count': len(failed),
                        'failed_attempts': failed
                    },
                    f,
                    indent=2
                )
            logger.info(f"✓ Saved {len(failed)} failed attempts to {failed_file}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Automated Address Sampling Engine using OSM + Nominatim',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sample all configured cities
  python scripts/sample_addresses_engine.py

  # Sample specific city
  python scripts/sample_addresses_engine.py --only "Brawley, California"

  # Sample cities in specific state
  python scripts/sample_addresses_engine.py --state CA

  # Custom number of samples per city
  python scripts/sample_addresses_engine.py --samples 100
        """
    )
    parser.add_argument(
        '--only',
        help='Process only specific city (e.g., "Brawley, California")'
    )
    parser.add_argument(
        '--state',
        help='Process only cities in specific state (e.g., "CA" or "California")'
    )
    parser.add_argument(
        '--samples',
        type=int,
        default=50,
        help='Number of address samples per city (default: 50)'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        help='Output directory for address files (default: data/processed/addresses)'
    )
    parser.add_argument(
        '--cache-dir',
        type=Path,
        help='Cache directory for boundaries and geocoding (default: data/cache)'
    )

    args = parser.parse_args()

    # Set up directories
    base_dir = Path(__file__).parent.parent
    output_dir = args.output_dir or (base_dir / 'data' / 'processed' / 'addresses')
    cache_dir = args.cache_dir or (base_dir / 'data' / 'cache')

    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Load cities
    logger.info("Loading cities from config...")
    cities = load_cities_config()
    cities = filter_cities(cities, only=args.only, state=args.state)

    if not cities:
        logger.error("No cities match the specified filters")
        return 1

    logger.info(f"Processing {len(cities)} cities with {args.samples} samples each")

    # Initialize engine
    engine = AddressSamplingEngine(output_dir, cache_dir)

    # Process each city
    total_success = 0
    total_failed = 0

    try:
        for city in cities:
            addresses, failed = engine.sample_city_addresses(city, args.samples)
            engine.save_results(city, addresses, failed)

            total_success += len(addresses)
            total_failed += len(failed)
    finally:
        # Always save cache before exiting
        engine.cache.save()

    # Final summary
    logger.info(f"\n{'='*80}")
    logger.info(f"FINAL SUMMARY")
    logger.info(f"{'='*80}")
    logger.info(f"Cities processed: {len(cities)}")
    logger.info(f"Total successful addresses: {total_success}")
    logger.info(f"Total failed attempts: {total_failed}")
    total_attempts = total_success + total_failed
    if total_attempts > 0:
        logger.info(f"Success rate: {total_success/total_attempts*100:.1f}%")
    else:
        logger.info(f"Success rate: N/A (no attempts made)")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Cache directory: {cache_dir}")

    return 0 if total_failed < (total_success + total_failed) else 1


if __name__ == '__main__':
    exit(main())
