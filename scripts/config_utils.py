#!/usr/bin/env python3
"""
Utilities for loading and filtering cities from config.
"""

import yaml
from pathlib import Path
from typing import List, Dict, Optional


def load_cities_config(config_path: Optional[Path] = None) -> List[Dict]:
    """
    Load cities configuration from YAML file.

    Args:
        config_path: Path to cities.yaml. If None, uses default location.

    Returns:
        List of city dictionaries
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent / 'config' / 'cities.yaml'

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    return config.get('cities', [])


def filter_cities(
    cities: List[Dict],
    only: Optional[str] = None,
    state: Optional[str] = None,
    city_name: Optional[str] = None
) -> List[Dict]:
    """
    Filter cities based on criteria.

    Args:
        cities: List of city dictionaries
        only: City name to filter to (e.g., "San Diego, California")
        state: State abbreviation or full name to filter (e.g., "CA" or "California")
        city_name: Exact city name to filter

    Returns:
        Filtered list of cities
    """
    filtered = cities.copy()

    # Filter by --only flag (e.g., "San Diego, California")
    if only:
        parts = [p.strip() for p in only.split(',')]
        if len(parts) == 2:
            city_part, state_part = parts
            filtered = [
                c for c in filtered
                if c['name'].lower() == city_part.lower() and
                (c['state'].lower() == state_part.lower() or
                 c.get('state_abbr', '').upper() == state_part.upper())
            ]
        else:
            # Just city name
            filtered = [c for c in filtered if c['name'].lower() == only.lower()]

    # Filter by state
    if state:
        state_upper = state.upper()
        filtered = [
            c for c in filtered
            if c['state'].lower() == state.lower() or
            c.get('state_abbr', '').upper() == state_upper
        ]

    # Filter by exact city name
    if city_name:
        filtered = [c for c in filtered if c['name'].lower() == city_name.lower()]

    return filtered


def get_city_display_name(city: Dict) -> str:
    """
    Get display name for a city.

    Args:
        city: City dictionary

    Returns:
        Display name like "San Diego, CA"
    """
    return f"{city['name']}, {city.get('state_abbr', city['state'])}"
