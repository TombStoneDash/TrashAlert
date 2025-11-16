#!/usr/bin/env python3
"""
Example script demonstrating how to use TrashAlert utilities.

This script shows how to:
1. Load configuration from cities.yaml
2. Set up logging
3. Iterate through cities
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config_loader import ConfigLoader, load_cities
from utils.logging_setup import setup_logging, quick_setup


def example_1_basic_config():
    """Example 1: Load and display city configuration"""
    print("\n=== Example 1: Basic Configuration Loading ===\n")

    # Load all enabled cities
    cities = load_cities()

    print(f"Found {len(cities)} enabled cities:\n")

    for city in cities:
        print(f"  - {city['name']}, {city['state']} (ID: {city['id']})")
        print(f"    Region: {city['region']}")
        print(f"    Population: {city.get('population', 'N/A'):,}")
        print()


def example_2_filter_cities():
    """Example 2: Filter cities by region and county"""
    print("\n=== Example 2: Filtering Cities ===\n")

    config = ConfigLoader()

    # Get cities by region
    imperial_cities = config.get_cities_by_region("Imperial Valley")
    print(f"Imperial Valley cities: {len(imperial_cities)}")
    for city in imperial_cities:
        print(f"  - {city['name']}")

    # Get cities by county
    sd_cities = config.get_cities_by_county("San Diego")
    print(f"\nSan Diego County cities: {len(sd_cities)}")
    for city in sd_cities:
        print(f"  - {city['name']}")


def example_3_logging():
    """Example 3: Set up and use logging"""
    print("\n=== Example 3: Logging Setup ===\n")

    # Quick logging setup
    logger = quick_setup(__file__, level="DEBUG")

    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

    print("\nLogs are saved to logs/example_usage.log")


def example_4_city_details():
    """Example 4: Access detailed city information"""
    print("\n=== Example 4: City Details ===\n")

    config = ConfigLoader()

    # Get a specific city
    brawley = config.get_city_by_id("imperial_brawley")

    if brawley:
        print(f"City: {brawley['name']}")
        print(f"Bounding Box:")
        print(f"  South: {brawley['bbox']['south']}")
        print(f"  West: {brawley['bbox']['west']}")
        print(f"  North: {brawley['bbox']['north']}")
        print(f"  East: {brawley['bbox']['east']}")

        print(f"\nData Sources:")
        for source in brawley.get('data_sources', []):
            print(f"  - {source['name']} ({source['type']})")
            print(f"    URL: {source['url']}")


def example_5_processing_config():
    """Example 5: Access processing configuration"""
    print("\n=== Example 5: Processing Configuration ===\n")

    config = ConfigLoader()

    # Get Overpass API configuration
    overpass_config = config.get_overpass_config()

    print("Overpass API Configuration:")
    print(f"  Timeout: {overpass_config.get('timeout_seconds')} seconds")
    print(f"  Max Retries: {overpass_config.get('max_retries')}")
    print(f"  Rate Limit Delay: {overpass_config.get('rate_limit_delay')} seconds")

    # Get logging configuration
    log_config = config.get_logging_config()

    print("\nLogging Configuration:")
    print(f"  Level: {log_config.get('level')}")
    print(f"  Directory: {log_config.get('log_dir')}")
    print(f"  Max Bytes: {log_config.get('max_bytes'):,}")


def main():
    """Run all examples"""
    print("=" * 60)
    print("TrashAlert Configuration and Logging Examples")
    print("=" * 60)

    example_1_basic_config()
    example_2_filter_cities()
    example_3_logging()
    example_4_city_details()
    example_5_processing_config()

    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)


if __name__ == '__main__':
    main()
