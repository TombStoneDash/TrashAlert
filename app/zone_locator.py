"""
Geofencing and boundary-matching engine for TrashAlert.

This module provides fast point-in-polygon (PIP) operations to determine
which service zone or city boundary contains a given geographic point.

Features:
- In-memory caching of boundary polygons for fast lookups
- Support for both city boundaries and pickup zones
- Optimized with shapely's prepared geometries
- Thread-safe lazy loading
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from functools import lru_cache
from threading import Lock

from shapely.geometry import Point, shape, Polygon, MultiPolygon
from shapely.prepared import prep
from sqlalchemy.orm import Session

from app.models import Address, City, PickupZone
from app.utils import load_cities_config

logger = logging.getLogger(__name__)


class BoundaryCache:
    """
    Thread-safe cache for city boundaries and pickup zones.

    Loads GeoJSON files from disk and maintains prepared shapely geometries
    for fast point-in-polygon operations.
    """

    def __init__(self):
        self._city_boundaries: Dict[str, Dict] = {}
        self._pickup_zones: Dict[str, List[Dict]] = {}
        self._lock = Lock()
        self._initialized = False

    def initialize(self):
        """Load all boundary data into memory cache."""
        with self._lock:
            if self._initialized:
                return

            logger.info("Initializing boundary cache...")
            self._load_city_boundaries()
            self._load_pickup_zones()
            self._initialized = True
            logger.info(
                f"Boundary cache initialized: {len(self._city_boundaries)} cities, "
                f"{sum(len(zones) for zones in self._pickup_zones.values())} pickup zones"
            )

    def _load_city_boundaries(self):
        """Load city boundary polygons from GeoJSON files."""
        boundaries_dir = Path(__file__).parent.parent / "data" / "boundaries"

        if not boundaries_dir.exists():
            logger.warning(f"Boundaries directory not found: {boundaries_dir}")
            return

        for geojson_file in boundaries_dir.glob("*_boundary.geojson"):
            try:
                with open(geojson_file, 'r') as f:
                    feature = json.load(f)

                # Extract city name from filename (e.g., "brawley_boundary.geojson" -> "brawley")
                city_slug = geojson_file.stem.replace("_boundary", "")

                # Convert GeoJSON geometry to shapely geometry
                geom = shape(feature['geometry'])

                # Prepare geometry for fast containment checks
                prepared_geom = prep(geom)

                self._city_boundaries[city_slug] = {
                    'geometry': geom,
                    'prepared': prepared_geom,
                    'properties': feature.get('properties', {}),
                    'bounds': geom.bounds  # (minx, miny, maxx, maxy)
                }

                logger.debug(f"Loaded city boundary: {city_slug}")

            except Exception as e:
                logger.error(f"Error loading city boundary {geojson_file}: {e}")

    def _load_pickup_zones(self):
        """Load pickup zone polygons from GeoJSON files."""
        gis_dir = Path(__file__).parent.parent / "data" / "gis"

        if not gis_dir.exists():
            logger.warning(f"GIS directory not found: {gis_dir}")
            return

        # Search for pickup zone GeoJSON files in city subdirectories
        for geojson_file in gis_dir.rglob("pickup_zones_*.geojson"):
            try:
                with open(geojson_file, 'r') as f:
                    feature_collection = json.load(f)

                # Extract city name from filename (e.g., "pickup_zones_brawley.geojson" -> "brawley")
                city_slug = geojson_file.stem.replace("pickup_zones_", "")

                zones = []
                for feature in feature_collection.get('features', []):
                    geom = shape(feature['geometry'])
                    prepared_geom = prep(geom)

                    zone_data = {
                        'geometry': geom,
                        'prepared': prepared_geom,
                        'properties': feature.get('properties', {}),
                        'bounds': geom.bounds,
                        'zone_id': feature['properties'].get('zone_id'),
                        'zone_name': feature['properties'].get('zone_name'),
                    }
                    zones.append(zone_data)

                self._pickup_zones[city_slug] = zones
                logger.debug(f"Loaded {len(zones)} pickup zones for {city_slug}")

            except Exception as e:
                logger.error(f"Error loading pickup zones {geojson_file}: {e}")

    def get_city_boundary(self, city_slug: str) -> Optional[Dict]:
        """
        Get cached city boundary data.

        Args:
            city_slug: City identifier (e.g., "brawley", "san_diego")

        Returns:
            Dictionary with geometry, prepared geometry, properties, and bounds
        """
        if not self._initialized:
            self.initialize()
        return self._city_boundaries.get(city_slug)

    def get_pickup_zones(self, city_slug: str) -> List[Dict]:
        """
        Get cached pickup zones for a city.

        Args:
            city_slug: City identifier (e.g., "brawley")

        Returns:
            List of zone dictionaries with geometry and properties
        """
        if not self._initialized:
            self.initialize()
        return self._pickup_zones.get(city_slug, [])

    def get_all_city_slugs(self) -> List[str]:
        """Get list of all cached city slugs."""
        if not self._initialized:
            self.initialize()
        return list(self._city_boundaries.keys())

    def get_all_zones_flat(self) -> List[Dict]:
        """Get all pickup zones across all cities as a flat list."""
        if not self._initialized:
            self.initialize()

        all_zones = []
        for city_slug, zones in self._pickup_zones.items():
            for zone in zones:
                zone_copy = zone.copy()
                zone_copy['city_slug'] = city_slug
                all_zones.append(zone_copy)
        return all_zones


# Global boundary cache instance
_boundary_cache = BoundaryCache()


def get_boundary_cache() -> BoundaryCache:
    """Get the global boundary cache instance."""
    return _boundary_cache


def find_zone(lat: float, lon: float, city_slug: Optional[str] = None) -> Optional[Dict]:
    """
    Find the pickup zone containing a geographic point.

    Uses fast point-in-polygon operations with prepared geometries.
    If city_slug is provided, only searches zones in that city.
    Otherwise, searches all cities.

    Args:
        lat: Latitude (decimal degrees)
        lon: Longitude (decimal degrees)
        city_slug: Optional city identifier to narrow search

    Returns:
        Dictionary with zone information:
        {
            'zone_id': str,
            'zone_name': str,
            'city_slug': str,
            'properties': dict,
            'trash_day': str (if available),
            'recycling_day': str (if available),
            'green_waste_day': str (if available)
        }
        Returns None if no zone found.
    """
    cache = get_boundary_cache()
    point = Point(lon, lat)  # Shapely uses (x, y) = (lon, lat)

    # Determine which cities to search
    if city_slug:
        cities_to_search = [city_slug] if cache.get_pickup_zones(city_slug) else []
    else:
        cities_to_search = list(cache._pickup_zones.keys())

    # Search each city's zones
    for city in cities_to_search:
        zones = cache.get_pickup_zones(city)

        for zone in zones:
            # Quick bounding box check first (fast)
            minx, miny, maxx, maxy = zone['bounds']
            if not (minx <= lon <= maxx and miny <= lat <= maxy):
                continue

            # Precise containment check using prepared geometry (still fast)
            if zone['prepared'].contains(point):
                return {
                    'zone_id': zone['zone_id'],
                    'zone_name': zone['zone_name'],
                    'city_slug': city,
                    'properties': zone['properties'],
                    'trash_day': zone['properties'].get('trash_day'),
                    'recycling_day': zone['properties'].get('recycling_day'),
                    'green_waste_day': zone['properties'].get('green_waste_day'),
                }

    return None


def find_city(lat: float, lon: float) -> Optional[Dict]:
    """
    Find the city boundary containing a geographic point.

    Args:
        lat: Latitude (decimal degrees)
        lon: Longitude (decimal degrees)

    Returns:
        Dictionary with city information:
        {
            'city_slug': str,
            'properties': dict (name, state, etc.)
        }
        Returns None if no city found.
    """
    cache = get_boundary_cache()
    point = Point(lon, lat)

    for city_slug in cache.get_all_city_slugs():
        boundary = cache.get_city_boundary(city_slug)
        if not boundary:
            continue

        # Quick bounding box check
        minx, miny, maxx, maxy = boundary['bounds']
        if not (minx <= lon <= maxx and miny <= lat <= maxy):
            continue

        # Precise containment check
        if boundary['prepared'].contains(point):
            return {
                'city_slug': city_slug,
                'properties': boundary['properties']
            }

    return None


def find_zone_for_address(address_id: int, db: Session) -> Optional[Dict]:
    """
    Find the pickup zone for a given address ID.

    Looks up the address coordinates from the database and performs
    point-in-polygon lookup.

    Args:
        address_id: Database ID of the address
        db: SQLAlchemy database session

    Returns:
        Zone information dictionary (same as find_zone) or None
    """
    # Query address from database
    address = db.query(Address).filter(Address.id == address_id).first()

    if not address:
        logger.warning(f"Address not found: {address_id}")
        return None

    if not address.lat or not address.lon:
        logger.warning(f"Address {address_id} has no coordinates")
        return None

    # Get city information
    city = db.query(City).filter(City.id == address.city_id).first()
    city_slug = None
    if city:
        # Extract city slug from city.slug or city.name
        city_slug = city.slug if hasattr(city, 'slug') and city.slug else None
        if not city_slug and city.name:
            # Convert name to slug format (e.g., "San Diego" -> "san_diego")
            city_slug = city.name.lower().replace(' ', '_')

    # Perform zone lookup
    return find_zone(address.lat, address.lon, city_slug=city_slug)


def validate_coordinates(lat: float, lon: float) -> Tuple[bool, Optional[str]]:
    """
    Validate latitude and longitude values.

    Args:
        lat: Latitude to validate
        lon: Longitude to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        return False, "Coordinates must be numeric values"

    if not (-90 <= lat <= 90):
        return False, "Latitude must be between -90 and 90"

    if not (-180 <= lon <= 180):
        return False, "Longitude must be between -180 and 180"

    return True, None


def get_zone_statistics() -> Dict:
    """
    Get statistics about loaded boundaries and zones.

    Returns:
        Dictionary with cache statistics
    """
    cache = get_boundary_cache()

    zones_by_city = {
        city: len(zones)
        for city, zones in cache._pickup_zones.items()
    }

    return {
        'cities_loaded': len(cache._city_boundaries),
        'total_pickup_zones': sum(zones_by_city.values()),
        'zones_by_city': zones_by_city,
        'city_slugs': cache.get_all_city_slugs(),
    }


# Initialize cache on module import for faster first request
_boundary_cache.initialize()
