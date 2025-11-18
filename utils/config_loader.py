#!/usr/bin/env python3
"""
Unified configuration loader for TrashAlert pipeline.
Loads both pipeline config and city config from YAML files.
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any


class ConfigLoader:
    """
    Central configuration loader for the TrashAlert pipeline.

    Loads and provides access to:
    - Pipeline configuration (Overpass API, paths, logging, etc.)
    - City configuration (list of cities with metadata)
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the config loader.

        Args:
            config_dir: Path to config directory. If None, uses default location.
        """
        if config_dir is None:
            # Find config directory relative to this file
            config_dir = Path(__file__).parent.parent / 'config'

        self.config_dir = config_dir
        self._pipeline_config = None
        self._cities_config = None

    @property
    def pipeline_config(self) -> Dict[str, Any]:
        """
        Get pipeline configuration.

        Returns:
            Dictionary with pipeline settings
        """
        if self._pipeline_config is None:
            config_path = self.config_dir / 'config.yaml'
            with open(config_path, 'r') as f:
                self._pipeline_config = yaml.safe_load(f)

        return self._pipeline_config

    @property
    def cities(self) -> List[Dict[str, Any]]:
        """
        Get list of all cities.

        Returns:
            List of city dictionaries
        """
        if self._cities_config is None:
            cities_path = self.config_dir / 'cities.yaml'
            with open(cities_path, 'r') as f:
                data = yaml.safe_load(f)
                self._cities_config = data.get('cities', [])

        return self._cities_config

    def get_city_by_id(self, city_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a city by its ID.

        Args:
            city_id: City ID (e.g., "ca_el_centro")

        Returns:
            City dictionary if found, None otherwise
        """
        for city in self.cities:
            if city.get('city_id') == city_id:
                return city
        return None

    def get_city_by_name(self, city_name: str, state: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get a city by name and optionally state.

        Args:
            city_name: Name of the city
            state: Optional state name or abbreviation

        Returns:
            City dictionary if found, None otherwise
        """
        for city in self.cities:
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

    def filter_cities(
        self,
        city_id: Optional[str] = None,
        city_name: Optional[str] = None,
        state: Optional[str] = None,
        all_cities: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Filter cities based on criteria.

        Args:
            city_id: Filter by city ID
            city_name: Filter by city name (supports "Name, State" format)
            state: Filter by state abbreviation or full name
            all_cities: If True, return all cities (overrides other filters)

        Returns:
            Filtered list of city dictionaries
        """
        if all_cities:
            return self.cities.copy()

        # Filter by city_id first (most specific)
        if city_id:
            city = self.get_city_by_id(city_id)
            return [city] if city else []

        # Filter by city_name (may include state like "San Diego, CA")
        if city_name:
            parts = [p.strip() for p in city_name.split(',')]
            if len(parts) == 2:
                name_part, state_part = parts
                city = self.get_city_by_name(name_part, state_part)
            else:
                city = self.get_city_by_name(city_name)

            return [city] if city else []

        # Filter by state
        if state:
            state_upper = state.upper()
            return [
                c for c in self.cities
                if c['state'].lower() == state.lower() or
                c.get('state_abbr', '').upper() == state_upper
            ]

        # No filter specified, return empty list
        return []

    def get_path(self, path_key: str, create_if_missing: bool = True) -> Path:
        """
        Get a path from the pipeline config.

        Args:
            path_key: Key in the paths configuration (e.g., "data_root", "raw")
            create_if_missing: If True, create the directory if it doesn't exist

        Returns:
            Path object
        """
        # Get base directory (project root)
        base_dir = self.config_dir.parent

        # Get path from config
        path_str = self.pipeline_config['paths'].get(path_key)
        if path_str is None:
            raise KeyError(f"Path key '{path_key}' not found in config")

        path = base_dir / path_str

        # Create directory if needed and it's a directory path (not a file)
        if create_if_missing and not path_key.endswith('_csv') and 'database' not in path_key:
            path.mkdir(parents=True, exist_ok=True)
        elif create_if_missing and (path_key.endswith('_csv') or 'database' in path_key):
            # For file paths, create parent directory
            path.parent.mkdir(parents=True, exist_ok=True)

        return path

    def setup_logging(self, logger_name: Optional[str] = None) -> logging.Logger:
        """
        Set up logging based on pipeline config.

        Args:
            logger_name: Name of the logger. If None, uses root logger.

        Returns:
            Configured logger
        """
        log_config = self.pipeline_config['logging']

        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_config['level']),
            format=log_config['format'],
            datefmt=log_config.get('date_format', '%Y-%m-%d %H:%M:%S')
        )

        if logger_name:
            return logging.getLogger(logger_name)
        else:
            return logging.getLogger()


def get_city_display_name(city: Dict[str, Any]) -> str:
    """
    Get display name for a city.

    Args:
        city: City dictionary

    Returns:
        Display name like "San Diego, CA"
    """
    return f"{city['name']}, {city.get('state_abbr', city['state'])}"


# Global singleton instance
_config_loader = None


def get_config_loader(config_dir: Optional[Path] = None) -> ConfigLoader:
    """
    Get the global config loader instance.

    Args:
        config_dir: Optional config directory path

    Returns:
        ConfigLoader instance
    """
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader(config_dir)
    return _config_loader
