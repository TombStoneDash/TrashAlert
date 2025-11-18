#!/usr/bin/env python3
"""
Verify integrity of city configuration and boundaries.

Checks:
1. All cities in config have boundary files
2. All boundary files are valid GeoJSON
3. Boundaries have required properties (bbox, geometry)
4. No duplicate city names
"""

import json
import logging
from pathlib import Path
from typing import Dict, List
from config_utils import load_cities_config, get_city_display_name

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_boundary_file_exists(city: Dict, boundaries_dir: Path) -> bool:
    """Check if boundary file exists for a city."""
    city_name = city['name']
    expected_file = boundaries_dir / f"{city_name.lower().replace(' ', '_')}_boundary.geojson"
    return expected_file.exists(), expected_file


def validate_geojson_boundary(boundary_file: Path) -> tuple[bool, List[str]]:
    """
    Validate a GeoJSON boundary file.

    Returns:
        Tuple of (is_valid, list of issues)
    """
    issues = []

    try:
        with open(boundary_file, 'r') as f:
            data = json.load(f)

        # Check if it's a valid Feature
        if data.get('type') != 'Feature':
            issues.append("Missing or invalid 'type' field (should be 'Feature')")

        # Check for geometry
        if 'geometry' not in data:
            issues.append("Missing 'geometry' field")
        else:
            geometry = data['geometry']
            if 'type' not in geometry:
                issues.append("Missing 'geometry.type' field")
            if 'coordinates' not in geometry:
                issues.append("Missing 'geometry.coordinates' field")

        # Check for bbox
        if 'bbox' not in data:
            issues.append("Missing 'bbox' field")
        else:
            bbox = data['bbox']
            if not isinstance(bbox, list) or len(bbox) != 4:
                issues.append("Invalid bbox format (should be [west, south, east, north])")

        # Check properties
        if 'properties' not in data:
            issues.append("Missing 'properties' field")

    except json.JSONDecodeError as e:
        issues.append(f"Invalid JSON: {e}")
    except Exception as e:
        issues.append(f"Error reading file: {e}")

    return len(issues) == 0, issues


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent
    boundaries_dir = base_dir / 'data' / 'boundaries'

    logger.info("="*80)
    logger.info("CITY INTEGRITY CHECK")
    logger.info("="*80)

    # Load cities from config
    logger.info("\n1. Loading cities from config...")
    cities = load_cities_config()
    logger.info(f"   Found {len(cities)} cities in config")

    # Check for duplicate names
    logger.info("\n2. Checking for duplicate city names...")
    city_names = [c['name'] for c in cities]
    if len(city_names) != len(set(city_names)):
        duplicates = [name for name in city_names if city_names.count(name) > 1]
        logger.error(f"   ✗ Found duplicate city names: {set(duplicates)}")
        return 1
    else:
        logger.info("   ✓ No duplicate city names")

    # Check boundary files exist
    logger.info("\n3. Checking boundary files...")
    missing_boundaries = []
    existing_boundaries = []

    for city in cities:
        exists, filepath = check_boundary_file_exists(city, boundaries_dir)
        display_name = get_city_display_name(city)

        if exists:
            logger.info(f"   ✓ {display_name}: {filepath.name}")
            existing_boundaries.append((city, filepath))
        else:
            logger.error(f"   ✗ {display_name}: MISSING")
            missing_boundaries.append(city)

    # Validate GeoJSON structure
    logger.info("\n4. Validating GeoJSON boundaries...")
    invalid_boundaries = []

    for city, filepath in existing_boundaries:
        is_valid, issues = validate_geojson_boundary(filepath)
        display_name = get_city_display_name(city)

        if is_valid:
            logger.info(f"   ✓ {display_name}: Valid GeoJSON")
        else:
            logger.error(f"   ✗ {display_name}: Invalid GeoJSON")
            for issue in issues:
                logger.error(f"      - {issue}")
            invalid_boundaries.append((city, issues))

    # Summary
    logger.info("\n" + "="*80)
    logger.info("SUMMARY")
    logger.info("="*80)
    logger.info(f"Total cities in config: {len(cities)}")
    logger.info(f"Cities with boundaries: {len(existing_boundaries)}")
    logger.info(f"Missing boundaries: {len(missing_boundaries)}")
    logger.info(f"Invalid boundaries: {len(invalid_boundaries)}")

    if missing_boundaries:
        logger.warning("\nMissing boundary files for:")
        for city in missing_boundaries:
            logger.warning(f"  - {get_city_display_name(city)}")

    if invalid_boundaries:
        logger.warning("\nInvalid boundary files for:")
        for city, _ in invalid_boundaries:
            logger.warning(f"  - {get_city_display_name(city)}")

    # Return status
    if missing_boundaries or invalid_boundaries:
        logger.error("\n❌ INTEGRITY CHECK FAILED")
        return 1
    else:
        logger.info("\n✅ INTEGRITY CHECK PASSED")
        return 0


if __name__ == '__main__':
    exit(main())
