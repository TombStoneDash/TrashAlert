#!/usr/bin/env python3
"""
Assign pickup zones and schedules to addresses.

For any city with zone data:
1. Loads city boundaries, subdivisions, pickup_zones, addresses, and schedules
2. For each address, determines associated pickup_zone_id (via point-in-polygon)
3. Looks up trash_day_of_week and any recycling/green waste days
4. Inserts or updates address_pickup_info table

Constraints:
- Handle cases where no zone is found → leave pickup_zone_id NULL but don't crash
- Keep geometry operations efficient; don't re-load and re-parse large GeoJSON files
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from shapely.geometry import shape, Point
from shapely.prepared import prep
import sys

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ZoneScheduleAssigner:
    """Assigns pickup zones and schedules to addresses."""

    def __init__(self, db_path: Path):
        """
        Initialize the assigner.

        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.conn = None
        self.zones_cache = {}  # Cache loaded zones by city

    def __enter__(self):
        """Connect to database."""
        self.conn = sqlite3.connect(self.db_path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def load_pickup_zones(self, geojson_path: Path, city_name: str) -> List[Dict]:
        """
        Load pickup zones from GeoJSON file with caching.

        Args:
            geojson_path: Path to pickup zones GeoJSON file
            city_name: Name of the city (for caching)

        Returns:
            List of zone dictionaries with geometry and properties
        """
        # Check cache first
        if city_name in self.zones_cache:
            logger.debug(f"Using cached zones for {city_name}")
            return self.zones_cache[city_name]

        logger.info(f"Loading pickup zones from {geojson_path}")

        if not geojson_path.exists():
            logger.warning(f"GeoJSON file not found: {geojson_path}")
            return []

        try:
            with open(geojson_path, 'r') as f:
                geojson = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GeoJSON file {geojson_path}: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to read GeoJSON file {geojson_path}: {e}")
            return []

        zones = []
        for feature in geojson.get('features', []):
            try:
                zone = {
                    'geometry': shape(feature['geometry']),
                    'zone_id': feature['properties'].get('zone_id', 'UNKNOWN'),
                    'zone_name': feature['properties'].get('zone_name', ''),
                    'trash_day': feature['properties'].get('trash_day'),
                    'recycling_day': feature['properties'].get('recycling_day'),
                    'green_waste_day': feature['properties'].get('green_waste_day'),
                }
                # Prepare geometry for faster point-in-polygon tests
                zone['prepared_geometry'] = prep(zone['geometry'])
                zones.append(zone)
            except Exception as e:
                logger.warning(f"Failed to process zone feature: {e}")
                continue

        logger.info(f"Loaded {len(zones)} pickup zones for {city_name}")

        # Cache the zones
        self.zones_cache[city_name] = zones

        return zones

    def get_city_addresses(self, city_name: str) -> List[Dict]:
        """
        Get all addresses for a city from the database.

        Args:
            city_name: Name of the city

        Returns:
            List of address dictionaries
        """
        cursor = self.conn.cursor()

        # Query addresses - support both schema types
        cursor.execute("""
            SELECT a.address_id, a.city_id, a.house_number, a.street,
                   a.lat, a.lon, c.city_name
            FROM addresses a
            JOIN cities c ON a.city_id = c.city_id
            WHERE c.city_name = ?
        """, (city_name,))

        addresses = []
        for row in cursor.fetchall():
            addresses.append({
                'address_id': row[0],
                'city_id': row[1],
                'house_number': row[2],
                'street': row[3],
                'lat': row[4],
                'lon': row[5],
                'city_name': row[6],
                'point': Point(row[5], row[4])  # lon, lat
            })

        if not addresses:
            logger.debug(f"No addresses found for {city_name} in addresses table")

        logger.info(f"Retrieved {len(addresses)} addresses for {city_name}")
        return addresses

    def find_zone_for_address(self, address: Dict, zones: List[Dict]) -> Optional[Dict]:
        """
        Find which zone contains the given address using point-in-polygon.

        Args:
            address: Address dictionary with 'point' geometry
            zones: List of zone dictionaries

        Returns:
            Zone dictionary if found, None otherwise
        """
        for zone in zones:
            try:
                if zone['prepared_geometry'].contains(address['point']):
                    return zone
            except Exception as e:
                logger.debug(f"Error checking zone {zone.get('zone_id')}: {e}")
                continue

        return None

    def assign_zones_to_addresses(
        self,
        addresses: List[Dict],
        zones: List[Dict],
        source: str = 'CITY_GIS'
    ) -> Tuple[int, int]:
        """
        Assign pickup zones and schedules to addresses.

        Args:
            addresses: List of address dictionaries
            zones: List of zone dictionaries
            source: Source of the zone data (default: 'CITY_GIS')

        Returns:
            Tuple of (matched_count, unmatched_count)
        """
        logger.info(f"Assigning zones to {len(addresses)} addresses using {len(zones)} zones")

        if not zones:
            logger.warning("No zones provided, skipping assignment")
            return 0, len(addresses)

        cursor = self.conn.cursor()
        matched = 0
        unmatched = 0

        for addr in addresses:
            zone_found = self.find_zone_for_address(addr, zones)

            if zone_found:
                # Insert or update pickup info
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO address_pickup_info (
                            address_id, city_id, pickup_zone_id,
                            trash_day_of_week, recycling_day_of_week,
                            green_waste_day_of_week, source
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        addr['address_id'],
                        addr['city_id'],
                        zone_found['zone_id'],
                        zone_found['trash_day'],
                        zone_found['recycling_day'],
                        zone_found['green_waste_day'],
                        source
                    ))
                    matched += 1
                except Exception as e:
                    logger.error(f"Failed to insert pickup info for address {addr['address_id']}: {e}")
                    unmatched += 1
            else:
                # No zone found - log but don't crash
                unmatched += 1
                logger.debug(
                    f"No zone found for address: {addr.get('house_number')} "
                    f"{addr.get('street')} at ({addr['lat']}, {addr['lon']})"
                )

        self.conn.commit()
        logger.info(f"✓ Matched {matched} addresses, {unmatched} unmatched")
        return matched, unmatched

    def get_city_stats(self, city_name: str) -> Dict:
        """
        Get statistics for a specific city.

        Args:
            city_name: Name of the city

        Returns:
            Dictionary with city statistics
        """
        cursor = self.conn.cursor()

        # Total addresses in city
        cursor.execute("""
            SELECT COUNT(*)
            FROM addresses a
            JOIN cities c ON a.city_id = c.city_id
            WHERE c.city_name = ?
        """, (city_name,))
        total_addresses = cursor.fetchone()[0]

        # Addresses with pickup info
        cursor.execute("""
            SELECT COUNT(*)
            FROM address_pickup_info api
            JOIN cities c ON api.city_id = c.city_id
            WHERE c.city_name = ?
        """, (city_name,))
        with_pickup_info = cursor.fetchone()[0]

        # By pickup zone
        cursor.execute("""
            SELECT pickup_zone_id, COUNT(*) as count
            FROM address_pickup_info api
            JOIN cities c ON api.city_id = c.city_id
            WHERE c.city_name = ?
            GROUP BY pickup_zone_id
            ORDER BY count DESC
        """, (city_name,))
        by_zone = cursor.fetchall()

        # By trash day
        cursor.execute("""
            SELECT trash_day_of_week, COUNT(*) as count
            FROM address_pickup_info api
            JOIN cities c ON api.city_id = c.city_id
            WHERE c.city_name = ? AND trash_day_of_week IS NOT NULL
            GROUP BY trash_day_of_week
            ORDER BY count DESC
        """, (city_name,))
        by_day = cursor.fetchall()

        return {
            'city_name': city_name,
            'total_addresses': total_addresses,
            'with_pickup_info': with_pickup_info,
            'by_zone': by_zone,
            'by_day': by_day
        }

    def get_overall_stats(self) -> Dict:
        """
        Get overall statistics across all cities.

        Returns:
            Dictionary with overall statistics
        """
        cursor = self.conn.cursor()

        # Total addresses
        cursor.execute("SELECT COUNT(*) FROM addresses")
        total_addresses = cursor.fetchone()[0]

        # Total with pickup info
        cursor.execute("SELECT COUNT(*) FROM address_pickup_info")
        total_with_info = cursor.fetchone()[0]

        # By city
        cursor.execute("""
            SELECT c.city_name, COUNT(*) as count
            FROM address_pickup_info api
            JOIN cities c ON api.city_id = c.city_id
            GROUP BY c.city_name
            ORDER BY count DESC
        """)
        by_city = cursor.fetchall()

        return {
            'total_addresses': total_addresses,
            'total_with_info': total_with_info,
            'by_city': by_city
        }

    def get_sample_pickup_info(self, city_name: Optional[str] = None, limit: int = 5) -> List[Dict]:
        """
        Get sample address pickup info rows.

        Args:
            city_name: Optional city name to filter by
            limit: Number of samples to retrieve

        Returns:
            List of sample dictionaries
        """
        cursor = self.conn.cursor()

        if city_name:
            cursor.execute("""
                SELECT
                    a.address_id,
                    c.city_name,
                    a.house_number,
                    a.street,
                    api.pickup_zone_id,
                    api.trash_day_of_week,
                    api.recycling_day_of_week,
                    api.green_waste_day_of_week,
                    api.source
                FROM address_pickup_info api
                JOIN addresses a ON api.address_id = a.address_id
                JOIN cities c ON api.city_id = c.city_id
                WHERE c.city_name = ?
                LIMIT ?
            """, (city_name, limit))
        else:
            cursor.execute("""
                SELECT
                    a.address_id,
                    c.city_name,
                    a.house_number,
                    a.street,
                    api.pickup_zone_id,
                    api.trash_day_of_week,
                    api.recycling_day_of_week,
                    api.green_waste_day_of_week,
                    api.source
                FROM address_pickup_info api
                JOIN addresses a ON api.address_id = a.address_id
                JOIN cities c ON api.city_id = c.city_id
                LIMIT ?
            """, (limit,))

        samples = []
        for row in cursor.fetchall():
            samples.append({
                'address_id': row[0],
                'city_name': row[1],
                'house_number': row[2],
                'street': row[3],
                'pickup_zone_id': row[4],
                'trash_day_of_week': row[5],
                'recycling_day_of_week': row[6],
                'green_waste_day_of_week': row[7],
                'source': row[8]
            })

        return samples


def process_city(
    assigner: ZoneScheduleAssigner,
    city_name: str,
    zone_geojson_path: Path
) -> Tuple[int, int]:
    """
    Process a single city: assign addresses to pickup zones and schedules.

    Args:
        assigner: ZoneScheduleAssigner instance
        city_name: Name of the city to process
        zone_geojson_path: Path to pickup zones GeoJSON

    Returns:
        Tuple of (matched_count, unmatched_count)
    """
    logger.info(f"\n{'=' * 80}")
    logger.info(f"Processing city: {city_name}")
    logger.info(f"{'=' * 80}")

    # Load pickup zones
    zones = assigner.load_pickup_zones(zone_geojson_path, city_name)

    # Get addresses for this city
    addresses = assigner.get_city_addresses(city_name)

    if not addresses:
        logger.warning(f"No addresses found for {city_name}")
        return 0, 0

    # Assign zones and schedules to addresses
    matched, unmatched = assigner.assign_zones_to_addresses(addresses, zones)

    # Get and display city statistics
    stats = assigner.get_city_stats(city_name)
    logger.info(f"\n📊 Statistics for {city_name}:")
    logger.info(f"   Total addresses: {stats['total_addresses']}")
    logger.info(f"   With pickup info: {stats['with_pickup_info']}")

    if stats['by_zone']:
        logger.info(f"   By zone:")
        for zone_id, count in stats['by_zone']:
            logger.info(f"      {zone_id}: {count} addresses")

    if stats['by_day']:
        logger.info(f"   By trash day:")
        for day, count in stats['by_day']:
            logger.info(f"      {day}: {count} addresses")

    # Show sample assignments
    samples = assigner.get_sample_pickup_info(city_name, limit=3)
    if samples:
        logger.info(f"\n📋 Sample assignments:")
        for sample in samples:
            logger.info(
                f"   {sample['house_number']} {sample['street']} → "
                f"Zone {sample['pickup_zone_id']}, "
                f"Trash: {sample['trash_day_of_week']}"
            )

    return matched, unmatched


def print_overall_statistics(assigner: ZoneScheduleAssigner):
    """
    Print overall statistics about the pickup info data.

    Args:
        assigner: ZoneScheduleAssigner instance
    """
    stats = assigner.get_overall_stats()

    print("\n" + "=" * 80)
    print("OVERALL STATISTICS")
    print("=" * 80)

    print(f"\nTotal addresses in database: {stats['total_addresses']}")
    print(f"Total addresses with pickup info: {stats['total_with_info']}")

    if stats['total_addresses'] > 0:
        coverage = (stats['total_with_info'] / stats['total_addresses']) * 100
        print(f"Coverage: {coverage:.1f}%")

    if stats['by_city']:
        print("\nAddresses with pickup info by city:")
        print("-" * 80)
        for city_name, count in stats['by_city']:
            print(f"  {city_name:40s} {count:4d} addresses")

    print("\n" + "=" * 80)


def discover_zone_files(gis_dir: Path) -> List[Tuple[str, Path]]:
    """
    Discover all pickup zone GeoJSON files in the GIS directory.

    Args:
        gis_dir: Path to the GIS data directory

    Returns:
        List of tuples (city_name, geojson_path)
    """
    zone_files = []

    if not gis_dir.exists():
        logger.warning(f"GIS directory not found: {gis_dir}")
        return zone_files

    # Find all pickup zone GeoJSON files
    for geojson_file in gis_dir.glob('**/pickup_zones_*.geojson'):
        # Extract city name from filename
        # Expected format: pickup_zones_cityname.geojson
        filename = geojson_file.stem  # e.g., "pickup_zones_brawley"
        city_name_raw = filename.replace('pickup_zones_', '').replace('_', ' ')
        city_name = city_name_raw.title()  # Capitalize properly

        zone_files.append((city_name, geojson_file))

    return zone_files


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent.parent
    db_path = base_dir / 'data' / 'trashalert.db'
    gis_dir = base_dir / 'data' / 'gis'

    logger.info("=" * 80)
    logger.info("ASSIGN ZONES AND SCHEDULES TO ADDRESSES")
    logger.info("=" * 80)
    logger.info(f"Database: {db_path}")
    logger.info(f"GIS directory: {gis_dir}")

    # Check if database exists
    if not db_path.exists():
        logger.error(f"❌ Database not found: {db_path}")
        logger.error("Please run scripts/init_database.py first")
        return 1

    # Discover zone files
    zone_files = discover_zone_files(gis_dir)

    if not zone_files:
        logger.error("❌ No pickup zone GeoJSON files found in data/gis/")
        logger.error("Expected files like: data/gis/cityname/pickup_zones_cityname.geojson")
        return 1

    logger.info(f"\n✓ Found {len(zone_files)} city/cities with zone data:")
    for city_name, geojson_path in zone_files:
        logger.info(f"   - {city_name}: {geojson_path}")

    # Process all cities
    with ZoneScheduleAssigner(db_path) as assigner:
        total_matched = 0
        total_unmatched = 0
        cities_processed = 0

        for city_name, zone_geojson_path in zone_files:
            try:
                matched, unmatched = process_city(assigner, city_name, zone_geojson_path)
                total_matched += matched
                total_unmatched += unmatched
                cities_processed += 1
            except Exception as e:
                logger.error(f"❌ Error processing {city_name}: {e}", exc_info=True)
                continue

        # Print overall results
        logger.info(f"\n{'=' * 80}")
        logger.info("PROCESSING COMPLETE")
        logger.info(f"{'=' * 80}")
        logger.info(f"Cities processed: {cities_processed}")
        logger.info(f"Total addresses matched: {total_matched}")
        logger.info(f"Total addresses unmatched: {total_unmatched}")

        if total_matched + total_unmatched > 0:
            success_rate = (total_matched / (total_matched + total_unmatched)) * 100
            logger.info(f"Success rate: {success_rate:.1f}%")

        # Print overall statistics
        print_overall_statistics(assigner)

    logger.info(f"\n✅ Done! Address pickup info saved to database")
    logger.info(f"Database location: {db_path}")

    return 0


if __name__ == '__main__':
    exit(main())
