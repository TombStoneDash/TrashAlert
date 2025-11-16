"""
OpenStreetMap / Overpass API client with rate limiting and caching
"""
import requests
import time
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import sys
sys.path.append('..')
from config import (
    OVERPASS_API_URL,
    OVERPASS_RATE_LIMIT_DELAY,
    OVERPASS_TIMEOUT,
    OVERPASS_MAX_RETRIES,
    RAW_DATA_DIR,
)

logger = logging.getLogger(__name__)


class OSMFetcher:
    """Fetch data from OpenStreetMap via Overpass API"""

    def __init__(self):
        self.api_url = OVERPASS_API_URL
        self.rate_limit_delay = OVERPASS_RATE_LIMIT_DELAY
        self.timeout = OVERPASS_TIMEOUT
        self.max_retries = OVERPASS_MAX_RETRIES
        self.last_request_time = 0
        self.raw_data_dir = Path(RAW_DATA_DIR)
        self.raw_data_dir.mkdir(parents=True, exist_ok=True)

    def _rate_limit(self):
        """Ensure we respect rate limits between API calls"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _execute_query(self, query: str) -> Optional[Dict]:
        """Execute an Overpass QL query with retries"""
        # List of alternative Overpass API endpoints
        endpoints = [
            "https://overpass.kumi.systems/api/interpreter",
            "https://overpass-api.de/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        ]

        for attempt in range(self.max_retries):
            # Rotate through endpoints
            endpoint = endpoints[attempt % len(endpoints)]

            try:
                self._rate_limit()
                logger.info(f"Executing Overpass query (attempt {attempt + 1}/{self.max_retries}) via {endpoint}")
                logger.debug(f"Query: {query[:200]}...")

                headers = {
                    'User-Agent': 'TrashDayLookup/1.0 (Data Collection for Public Service)',
                    'Accept': 'application/json',
                }

                response = requests.post(
                    endpoint,
                    data={"data": query},
                    headers=headers,
                    timeout=self.timeout
                )
                response.raise_for_status()

                data = response.json()
                logger.info(f"Query successful, returned {len(data.get('elements', []))} elements")
                return data

            except requests.exceptions.Timeout:
                logger.warning(f"Query timeout on attempt {attempt + 1}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # exponential backoff
                else:
                    logger.error("Max retries exceeded due to timeout")
                    return None

            except requests.exceptions.RequestException as e:
                logger.error(f"Request error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return None

            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                return None

        return None

    def fetch_city_boundary(self, city_name: str, osm_area_query: str) -> Optional[Dict]:
        """
        Fetch city boundary from OSM

        Args:
            city_name: Name of the city
            osm_area_query: Overpass QL area query fragment

        Returns:
            GeoJSON-like dict with boundary data, or None if failed
        """
        cache_file = self.raw_data_dir / f"{city_name.lower().replace(' ', '_')}_boundary.json"

        # Check cache first
        if cache_file.exists():
            logger.info(f"Loading cached boundary for {city_name}")
            with open(cache_file, 'r') as f:
                return json.load(f)

        # Build Overpass query for city boundary
        query = f"""
        [out:json][timeout:{self.timeout}];
        {osm_area_query}
        (
          relation(area)["boundary"="administrative"];
        );
        out geom;
        """

        logger.info(f"Fetching boundary for {city_name}")
        result = self._execute_query(query)

        if result and result.get('elements'):
            # Save to cache
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2)
            logger.info(f"Cached boundary data to {cache_file}")
            return result
        else:
            logger.warning(f"No boundary found for {city_name}")
            return None

    def fetch_addresses_in_area(self, city_name: str, osm_area_query: str,
                               batch_size: int = 5000) -> Optional[Dict]:
        """
        Fetch addresses/buildings within a city boundary

        Args:
            city_name: Name of the city
            osm_area_query: Overpass QL area query fragment
            batch_size: Maximum elements to fetch (to avoid timeout)

        Returns:
            Dict with OSM elements containing address data
        """
        cache_file = self.raw_data_dir / f"{city_name.lower().replace(' ', '_')}_addresses.json"

        # Check cache
        if cache_file.exists():
            logger.info(f"Loading cached addresses for {city_name}")
            with open(cache_file, 'r') as f:
                return json.load(f)

        # Query for nodes and ways with addresses
        query = f"""
        [out:json][timeout:{self.timeout}];
        {osm_area_query}
        (
          node(area)["addr:housenumber"]["addr:street"];
          way(area)["addr:housenumber"]["addr:street"];
        );
        out center;
        """

        logger.info(f"Fetching addresses for {city_name} (this may take a while)")
        result = self._execute_query(query)

        if result:
            # Save to cache
            with open(cache_file, 'w') as f:
                json.dump(result, f, indent=2)
            logger.info(f"Cached {len(result.get('elements', []))} addresses to {cache_file}")
            return result
        else:
            logger.warning(f"No addresses found for {city_name}")
            return None

    def get_bbox_from_boundary(self, boundary_data: Dict) -> Optional[Dict]:
        """
        Extract bounding box from boundary data

        Returns:
            Dict with north, south, east, west coordinates
        """
        if not boundary_data or 'elements' not in boundary_data:
            return None

        lats = []
        lons = []

        for element in boundary_data['elements']:
            if 'bounds' in element:
                bounds = element['bounds']
                lats.extend([bounds['minlat'], bounds['maxlat']])
                lons.extend([bounds['minlon'], bounds['maxlon']])
            elif 'geometry' in element:
                for point in element['geometry']:
                    lats.append(point['lat'])
                    lons.append(point['lon'])

        if lats and lons:
            return {
                'north': max(lats),
                'south': min(lats),
                'east': max(lons),
                'west': min(lons)
            }

        return None


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)
    fetcher = OSMFetcher()

    # Test with a small city
    test_query = 'area["name"="Holtville"]["admin_level"="8"];'
    boundary = fetcher.fetch_city_boundary("Holtville", test_query)

    if boundary:
        bbox = fetcher.get_bbox_from_boundary(boundary)
        print(f"Bounding box: {bbox}")
