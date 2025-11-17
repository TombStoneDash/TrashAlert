"""Utility functions for address processing and consensus calculation."""
import re
from typing import Optional, Tuple, Dict
from collections import Counter
from sqlalchemy.orm import Session
from geopy.distance import geodesic

from app.models import Address, CrowdReport, CrowdConsensus


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
    if lat and lon:
        nearby = db.query(Address).filter(
            Address.lat.isnot(None),
            Address.lon.isnot(None)
        ).all()

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
