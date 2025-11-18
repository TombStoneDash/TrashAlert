#!/usr/bin/env python3
"""
City configuration module for TrashAlert.
Loads and exposes the 6 pilot cities from cities.yaml.
"""

import yaml
from pathlib import Path
from typing import List, Dict, Optional


# Path to cities configuration
CONFIG_PATH = Path(__file__).parent / 'cities.yaml'


def load_cities() -> List[Dict]:
    """
    Load all cities from the configuration file.

    Returns:
        List of city dictionaries containing name, state, and metadata
    """
    with open(CONFIG_PATH, 'r') as f:
        config = yaml.safe_load(f)

    return config.get('cities', [])


def get_pilot_cities() -> List[Dict]:
    """
    Get the 6 primary pilot cities for TrashAlert.

    Returns:
        List of 6 pilot city dictionaries:
        - El Centro, CA
        - Imperial, CA
        - Brawley, CA
        - Holtville, CA
        - Calexico, CA
        - San Diego, CA
    """
    cities = load_cities()

    # Define the pilot city names
    pilot_city_names = {
        'El Centro',
        'Imperial',
        'Brawley',
        'Holtville',
        'Calexico',
        'San Diego'
    }

    # Filter to only pilot cities
    pilot_cities = [c for c in cities if c['name'] in pilot_city_names]

    return pilot_cities


def get_city_by_name(city_name: str, state: Optional[str] = None) -> Optional[Dict]:
    """
    Get a specific city by name and optionally state.

    Args:
        city_name: Name of the city
        state: Optional state name or abbreviation

    Returns:
        City dictionary if found, None otherwise
    """
    cities = load_cities()

    for city in cities:
        name_match = city['name'].lower() == city_name.lower()

        if state:
            state_match = (
                city['state'].lower() == state.lower() or
                city.get('state_abbr', '').upper() == state.upper()
            )
            if name_match and state_match:
                return city
        elif name_match:
            return city

    return None


def get_city_display_name(city: Dict) -> str:
    """
    Get display name for a city.

    Args:
        city: City dictionary

    Returns:
        Display name like "San Diego, CA"
    """
    return f"{city['name']}, {city.get('state_abbr', city['state'])}"


def get_cities_by_state(state: str) -> List[Dict]:
    """
    Get all cities in a specific state.

    Args:
        state: State name or abbreviation (e.g., "California" or "CA")

    Returns:
        List of city dictionaries in that state
    """
    cities = load_cities()

    return [
        c for c in cities
        if c['state'].lower() == state.lower() or
        c.get('state_abbr', '').upper() == state.upper()
    ]


# Export commonly used constants
PILOT_CITIES = get_pilot_cities()
ALL_CITIES = load_cities()


if __name__ == '__main__':
    # Print pilot cities for verification
    print("TrashAlert Pilot Cities:")
    print("=" * 60)

    for city in PILOT_CITIES:
        print(f"  • {get_city_display_name(city)}")
        print(f"    Has official zones: {city.get('has_official_pickup_zones', False)}")
        print()

    print(f"\nTotal pilot cities: {len(PILOT_CITIES)}")
