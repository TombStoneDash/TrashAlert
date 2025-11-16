"""
Configuration loader for TrashAlert.

This module handles loading and parsing the cities.yaml configuration file.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional


class ConfigLoader:
    """Load and manage configuration from cities.yaml"""

    def __init__(self, config_path: str = "config/cities.yaml"):
        """
        Initialize the configuration loader.

        Args:
            config_path: Path to the cities.yaml configuration file
        """
        self.config_path = Path(config_path)
        self.config = None
        self._load_config()

    def _load_config(self):
        """Load the YAML configuration file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)

    def get_all_cities(self) -> List[Dict]:
        """
        Get all cities from configuration.

        Returns:
            List of city configuration dictionaries
        """
        return self.config.get('cities', [])

    def get_enabled_cities(self) -> List[Dict]:
        """
        Get only enabled cities.

        Returns:
            List of enabled city configuration dictionaries
        """
        return [city for city in self.get_all_cities() if city.get('enabled', True)]

    def get_city_by_id(self, city_id: str) -> Optional[Dict]:
        """
        Get a specific city by its ID.

        Args:
            city_id: City identifier (e.g., 'imperial_brawley')

        Returns:
            City configuration dictionary or None if not found
        """
        for city in self.get_all_cities():
            if city.get('id') == city_id:
                return city
        return None

    def get_cities_by_region(self, region: str) -> List[Dict]:
        """
        Get all cities in a specific region.

        Args:
            region: Region name (e.g., 'Imperial Valley')

        Returns:
            List of city configuration dictionaries
        """
        return [city for city in self.get_all_cities()
                if city.get('region') == region]

    def get_cities_by_county(self, county: str) -> List[Dict]:
        """
        Get all cities in a specific county.

        Args:
            county: County name (e.g., 'Imperial', 'San Diego')

        Returns:
            List of city configuration dictionaries
        """
        return [city for city in self.get_all_cities()
                if city.get('county') == county]

    def get_processing_config(self) -> Dict:
        """
        Get processing configuration.

        Returns:
            Processing configuration dictionary
        """
        return self.config.get('processing', {})

    def get_logging_config(self) -> Dict:
        """
        Get logging configuration.

        Returns:
            Logging configuration dictionary
        """
        return self.config.get('logging', {})

    def get_overpass_config(self) -> Dict:
        """
        Get Overpass API configuration.

        Returns:
            Overpass API configuration dictionary
        """
        processing = self.get_processing_config()
        return processing.get('overpass_api', {})


def load_cities(config_path: str = "config/cities.yaml") -> List[Dict]:
    """
    Convenience function to quickly load all enabled cities.

    Args:
        config_path: Path to the cities.yaml configuration file

    Returns:
        List of enabled city configuration dictionaries

    Example:
        >>> from utils.config_loader import load_cities
        >>> cities = load_cities()
        >>> for city in cities:
        >>>     print(f"Processing {city['name']}, {city['state']}")
    """
    loader = ConfigLoader(config_path)
    return loader.get_enabled_cities()
