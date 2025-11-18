"""Utility functions for address processing and consensus calculation."""
import re
import yaml
from pathlib import Path
from typing import Optional, Tuple, Dict, List
from collections import Counter
from sqlalchemy.orm import Session
from sqlalchemy import func
from geopy.distance import geodesic

from app.models import Address, CrowdReport, CrowdConsensus


# Cache for cities config
_cities_config = None


def load_cities_config() -> Dict:
    """
    Load cities configuration from cities.yaml.

    Returns:
        Dictionary with cities configuration
    """
    global _cities_config
    if _cities_config is not None:
        return _cities_config

    config_path = Path(__file__).parent.parent / "config" / "cities.yaml"
    with open(config_path, 'r') as f:
        _cities_config = yaml.safe_load(f)

    return _cities_config


def get_city_id_from_name(city_name: str) -> Optional[str]:
    """
    Convert city name to city_id (normalized slug).

    Args:
        city_name: City name (e.g., "San Diego", "El Centro")

    Returns:
        City ID slug (e.g., "san_diego", "el_centro") or None if not found
    """
    if not city_name:
        return None

    # Normalize: lowercase, replace spaces with underscores
    city_id = city_name.strip().lower().replace(' ', '_')
    return city_id


def get_city_name_from_id(city_id: str) -> Optional[str]:
    """
    Get full city name from city_id.

    Args:
        city_id: City ID slug (e.g., "san_diego")

    Returns:
        Full city name (e.g., "San Diego") or None if not found
    """
    try:
        config = load_cities_config()
        cities = config.get('cities', [])

        for city in cities:
            if get_city_id_from_name(city['name']) == city_id:
                return city['name']

        return None
    except Exception:
        return None


def normalize_address(address: str) -> Dict[str, Optional[str]]:
    """
    Normalize an address string into components.

    This is a simple implementation. In production, you'd use a geocoding service
    like Google Maps API, Nominatim, or similar.

    Args:
        address: Raw address string

    Returns:
        Dictionary with normalized components
    """
    # Simple normalization: uppercase, remove extra spaces
    normalized = re.sub(r'\s+', ' ', address.strip().upper())

    # Try to extract components (very basic pattern matching)
    parts = {
        'normalized_address': normalized,
        'house_number': None,
        'street': None,
        'city': None,
        'state': None,
        'zip_code': None
    }

    # Extract house number (digits at the start)
    house_match = re.match(r'^(\d+)\s+(.+)', normalized)
    if house_match:
        parts['house_number'] = house_match.group(1)
        rest = house_match.group(2)
    else:
        rest = normalized

    # Extract state and zip from end (basic pattern)
    state_zip_match = re.search(r',\s*([A-Z]{2})\s*(\d{5})?$', rest)
    if state_zip_match:
        parts['state'] = state_zip_match.group(1)
        parts['zip_code'] = state_zip_match.group(2)
        rest = rest[:state_zip_match.start()]

    # Extract city (last component before state)
    city_match = re.search(r',\s*([^,]+)$', rest)
    if city_match:
        parts['city'] = city_match.group(1).strip()
        rest = rest[:city_match.start()]

    # What's left is the street
    parts['street'] = rest.strip()

    return parts


def find_or_create_address(db: Session, address_str: str,
                           lat: Optional[float] = None,
                           lon: Optional[float] = None) -> Address:
    """
    Find existing address or create new one.

    Args:
        db: Database session
        address_str: Raw address string
        lat: Optional latitude
        lon: Optional longitude

    Returns:
        Address object (existing or newly created)
    """
    # Normalize the address
    parts = normalize_address(address_str)
    normalized = parts['normalized_address']

    # Try to find existing address by normalized string
    existing = db.query(Address).filter(
        Address.normalized_address == normalized
    ).first()

    if existing:
        return existing

    # If coordinates provided, try to find nearby address (within 50 meters)
    # Use bounding box query to limit database results (approximately 100m box)
    if lat and lon:
        # Calculate rough bounding box (0.001 degrees ≈ 111 meters)
        lat_delta = 0.001
        lon_delta = 0.001

        nearby = db.query(Address).filter(
            Address.lat.isnot(None),
            Address.lon.isnot(None),
            Address.lat.between(lat - lat_delta, lat + lat_delta),
            Address.lon.between(lon - lon_delta, lon + lon_delta)
        ).limit(50).all()  # Limit to 50 nearby candidates

        for addr in nearby:
            distance = geodesic((lat, lon), (addr.lat, addr.lon)).meters
            if distance < 50:  # Within 50 meters
                return addr

    # Create new address
    new_address = Address(
        normalized_address=normalized,
        house_number=parts['house_number'],
        street=parts['street'],
        city=parts['city'],
        state=parts['state'],
        zip_code=parts['zip_code'],
        lat=lat,
        lon=lon
    )
    db.add(new_address)
    db.commit()
    db.refresh(new_address)

    return new_address


def find_address_by_coordinates(
    db: Session,
    lat: float,
    lon: float,
    max_distance_meters: float = 50,
    city_id: Optional[str] = None
) -> Optional[Address]:
    """
    Find the nearest address to given coordinates within max distance.

    Uses bounding box query for efficiency, then calculates actual distance.

    Args:
        db: Database session
        lat: Latitude
        lon: Longitude
        max_distance_meters: Maximum distance in meters (default 50m)
        city_id: Optional city_id to filter results

    Returns:
        Nearest Address object or None if none found within max distance
    """
    # Calculate bounding box (0.001 degrees ≈ 111 meters)
    # Use slightly larger box to ensure we catch addresses at the boundary
    lat_delta = max_distance_meters / 111000.0 * 1.5  # degrees
    lon_delta = max_distance_meters / (111000.0 * abs(float(lat))) * 1.5 if lat != 0 else lat_delta

    # Build query with bounding box
    query = db.query(Address).filter(
        Address.lat.isnot(None),
        Address.lon.isnot(None),
        Address.lat.between(lat - lat_delta, lat + lat_delta),
        Address.lon.between(lon - lon_delta, lon + lon_delta)
    )

    # Filter by city_id if provided
    if city_id:
        query = query.filter(Address.city_id == city_id)

    candidates = query.limit(100).all()

    if not candidates:
        return None

    # Calculate actual distances and find nearest
    nearest = None
    min_distance = float('inf')

    for addr in candidates:
        distance = geodesic((lat, lon), (addr.lat, addr.lon)).meters
        if distance < min_distance and distance <= max_distance_meters:
            min_distance = distance
            nearest = addr

    return nearest


def update_crowd_consensus(db: Session, address_id: int) -> CrowdConsensus:
    """
    Calculate and update consensus for an address based on all reports.

    Logic:
    - Aggregates all reports for the address
    - Calculates most common value for each day type
    - Calculates agreement ratios
    - Marks as verified if: total_reports >= 3 AND agreement_ratio >= 0.67

    Args:
        db: Database session
        address_id: Address ID to calculate consensus for

    Returns:
        Updated CrowdConsensus object
    """
    # Get all reports for this address
    reports = db.query(CrowdReport).filter(
        CrowdReport.address_id == address_id
    ).all()

    if not reports:
        # No reports, remove consensus if it exists
        existing = db.query(CrowdConsensus).filter(
            CrowdConsensus.address_id == address_id
        ).first()
        if existing:
            db.delete(existing)
            db.commit()
        return None

    # Aggregate reports
    trash_days = [r.trash_day for r in reports if r.trash_day]
    recycling_days = [r.recycling_day for r in reports if r.recycling_day]
    green_days = [r.green_day for r in reports if r.green_day]

    total_reports = len(reports)

    # Calculate consensus (most common value) and agreement ratios
    def get_consensus_and_ratio(values):
        if not values:
            return None, 0.0
        counter = Counter(values)
        most_common = counter.most_common(1)[0]
        return most_common[0], most_common[1] / len(values)

    trash_consensus, trash_ratio = get_consensus_and_ratio(trash_days)
    recycling_consensus, recycling_ratio = get_consensus_and_ratio(recycling_days)
    green_consensus, green_ratio = get_consensus_and_ratio(green_days)

    # Overall agreement ratio (average of available ratios)
    ratios = [r for r in [trash_ratio, recycling_ratio, green_ratio] if r > 0]
    avg_ratio = sum(ratios) / len(ratios) if ratios else 0.0

    # Verification threshold: >= 3 reports AND >= 75% agreement
    is_verified = total_reports >= 3 and avg_ratio >= 0.75

    # Update or create consensus
    consensus = db.query(CrowdConsensus).filter(
        CrowdConsensus.address_id == address_id
    ).first()

    if consensus:
        # Update existing
        consensus.consensus_trash_day = trash_consensus
        consensus.consensus_recycling_day = recycling_consensus
        consensus.consensus_green_day = green_consensus
        consensus.total_reports = total_reports
        consensus.trash_agreement_ratio = trash_ratio
        consensus.recycling_agreement_ratio = recycling_ratio
        consensus.green_agreement_ratio = green_ratio
        consensus.is_verified = is_verified
    else:
        # Create new
        consensus = CrowdConsensus(
            address_id=address_id,
            consensus_trash_day=trash_consensus,
            consensus_recycling_day=recycling_consensus,
            consensus_green_day=green_consensus,
            total_reports=total_reports,
            trash_agreement_ratio=trash_ratio,
            recycling_agreement_ratio=recycling_ratio,
            green_agreement_ratio=green_ratio,
            is_verified=is_verified
        )
        db.add(consensus)

    db.commit()
    db.refresh(consensus)

    return consensus


def validate_day(day: Optional[str]) -> Optional[str]:
    """Validate and normalize day of week."""
    if not day:
        return None

    day = day.strip().upper()
    valid_days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']

    # Also accept full names
    day_mapping = {
        'MONDAY': 'MON',
        'TUESDAY': 'TUE',
        'WEDNESDAY': 'WED',
        'THURSDAY': 'THU',
        'FRIDAY': 'FRI',
        'SATURDAY': 'SAT',
        'SUNDAY': 'SUN'
    }

    if day in valid_days:
        return day
    elif day in day_mapping:
        return day_mapping[day]
    else:
        return None


def day_abbrev_to_full(day: Optional[str]) -> Optional[str]:
    """
    Convert day abbreviation to full day name.

    Args:
        day: Day abbreviation (MON, TUE, etc.) or None

    Returns:
        Full day name (Monday, Tuesday, etc.) or None
    """
    if not day:
        return None

    day_map = {
        'MON': 'Monday',
        'TUE': 'Tuesday',
        'WED': 'Wednesday',
        'THU': 'Thursday',
        'FRI': 'Friday',
        'SAT': 'Saturday',
        'SUN': 'Sunday'
    }

    return day_map.get(day.upper())
