#!/usr/bin/env python3
"""
Link addresses to pickup zones and days using GIS data.

For any city where we have pickup zone GeoJSON data:
1. Loads city boundary, subdivision polygons, pickup zone polygons
2. Loads addresses from CSV or database
3. Performs point-in-polygon join from addresses to pickup zones
4. Extracts pickup zone info and pickup days
5. Stores results in address_pickup_info table
"""

import sqlite3
import json
import pandas as pd
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from shapely.geometry import shape, Point
from shapely.prepared import prep

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AddressZoneLinker:
    """Links addresses to pickup zones using GIS data."""

    def __init__(self, db_path: Path):
        """
        Initialize the linker.

        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = db_path
        self.conn = None

    def __enter__(self):
        """Connect to database."""
        self.conn = sqlite3.connect(self.db_path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def load_pickup_zones(self, geojson_path: Path) -> List[Dict]:
        """
        Load pickup zones from GeoJSON file.

        Args:
            geojson_path: Path to pickup zones GeoJSON file

        Returns:
            List of zone dictionaries with geometry and properties
        """
        logger.info(f"Loading pickup zones from {geojson_path}")

        with open(geojson_path, 'r') as f:
            geojson = json.load(f)

        zones = []
        for feature in geojson['features']:
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

        logger.info(f"Loaded {len(zones)} pickup zones")
        return zones

    def import_addresses_from_csv(self, csv_path: Path) -> int:
        """
        Import addresses from CSV into the database.

        Args:
            csv_path: Path to addresses CSV file

        Returns:
            Number of addresses imported
        """
        logger.info(f"Importing addresses from {csv_path}")

        df = pd.read_csv(csv_path)
        cursor = self.conn.cursor()

        # First, ensure cities exist
        cities = df['city_name'].unique()
        for city_name in cities:
            cursor.execute("""
                INSERT OR IGNORE INTO cities (city_name, state)
                VALUES (?, ?)
            """, (city_name, 'CA'))  # Assuming California for now

        self.conn.commit()

        # Get city_id mapping
        cursor.execute("SELECT city_id, city_name FROM cities")
        city_map = {name: cid for cid, name in cursor.fetchall()}

        # Import addresses
        imported = 0
        for _, row in df.iterrows():
            city_id = city_map[row['city_name']]

            # Check if address already exists (by coordinates and city)
            cursor.execute("""
                SELECT address_id FROM addresses
                WHERE city_id = ? AND lat = ? AND lon = ?
            """, (city_id, row['lat'], row['lon']))

            if cursor.fetchone() is None:
                cursor.execute("""
                    INSERT INTO addresses (
                        city_id, house_number, street, lat, lon, osm_id
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    city_id,
                    row.get('house_number', ''),
                    row.get('street', ''),
                    row['lat'],
                    row['lon'],
                    row.get('osm_id', '')
                ))
                imported += 1

        self.conn.commit()
        logger.info(f"Imported {imported} new addresses")
        return imported

    def get_city_addresses(self, city_name: str) -> List[Dict]:
        """
        Get all addresses for a city from the database.

        Args:
            city_name: Name of the city

        Returns:
            List of address dictionaries
        """
        cursor = self.conn.cursor()

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

        logger.info(f"Retrieved {len(addresses)} addresses for {city_name}")
        return addresses

    def link_addresses_to_zones(
        self,
        addresses: List[Dict],
        zones: List[Dict],
        source: str = 'CITY_GIS'
    ) -> Tuple[int, int]:
        """
        Link addresses to pickup zones using point-in-polygon.

        Args:
            addresses: List of address dictionaries
            zones: List of zone dictionaries
            source: Source of the zone data (default: 'CITY_GIS')

        Returns:
            Tuple of (matched_count, unmatched_count)
        """
        logger.info(f"Linking {len(addresses)} addresses to {len(zones)} zones")

        cursor = self.conn.cursor()
        matched = 0
        unmatched = 0

        for addr in addresses:
            zone_found = None

            # Try to find which zone contains this address point
            for zone in zones:
                if zone['prepared_geometry'].contains(addr['point']):
                    zone_found = zone
                    break

            if zone_found:
                # Insert or update pickup info
                cursor.execute("""
                    INSERT OR REPLACE INTO address_pickup_info (
                        address_id, city_id, pickup_zone_id,
                        trash_day_of_week, recycling_day_of_week,
                        green_waste_day_of_week, source, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
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
            else:
                unmatched += 1
                logger.debug(
                    f"No zone found for address: {addr['house_number']} "
                    f"{addr['street']} at ({addr['lat']}, {addr['lon']})"
                )

        self.conn.commit()
        logger.info(f"Matched {matched} addresses, {unmatched} unmatched")
        return matched, unmatched

    def get_pickup_info_stats(self) -> Dict:
        """
        Get statistics about address pickup info.

        Returns:
            Dictionary with statistics
        """
        cursor = self.conn.cursor()

        # Total addresses with pickup info
        cursor.execute("SELECT COUNT(*) FROM address_pickup_info")
        total = cursor.fetchone()[0]

        # By city
        cursor.execute("""
            SELECT c.city_name, COUNT(*) as count
            FROM address_pickup_info api
            JOIN cities c ON api.city_id = c.city_id
            GROUP BY c.city_name
            ORDER BY count DESC
        """)
        by_city = cursor.fetchall()

        # By day of week
        cursor.execute("""
            SELECT trash_day_of_week, COUNT(*) as count
            FROM address_pickup_info
            WHERE trash_day_of_week IS NOT NULL
            GROUP BY trash_day_of_week
            ORDER BY count DESC
        """)
        by_day = cursor.fetchall()

        # By zone
        cursor.execute("""
            SELECT pickup_zone_id, COUNT(*) as count
            FROM address_pickup_info
            GROUP BY pickup_zone_id
            ORDER BY count DESC
        """)
        by_zone = cursor.fetchall()

        return {
            'total': total,
            'by_city': by_city,
            'by_day': by_day,
            'by_zone': by_zone
        }

    def get_sample_pickup_info(self, limit: int = 5) -> List[Dict]:
        """
        Get sample address pickup info rows.

        Args:
            limit: Number of samples to retrieve

        Returns:
            List of sample dictionaries
        """
        cursor = self.conn.cursor()

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
    linker: AddressZoneLinker,
    city_name: str,
    zone_geojson_path: Path
) -> Tuple[int, int]:
    """
    Process a single city: link addresses to pickup zones.

    Args:
        linker: AddressZoneLinker instance
        city_name: Name of the city to process
        zone_geojson_path: Path to pickup zones GeoJSON

    Returns:
        Tuple of (matched_count, unmatched_count)
    """
    logger.info(f"\n{'=' * 80}")
    logger.info(f"Processing city: {city_name}")
    logger.info(f"{'=' * 80}")

    # Load pickup zones
    zones = linker.load_pickup_zones(zone_geojson_path)

    # Get addresses for this city
    addresses = linker.get_city_addresses(city_name)

    if not addresses:
        logger.warning(f"No addresses found for {city_name}")
        return 0, 0

    # Link addresses to zones
    matched, unmatched = linker.link_addresses_to_zones(addresses, zones)

    return matched, unmatched


def print_statistics(linker: AddressZoneLinker):
    """
    Print statistics about the pickup info data.

    Args:
        linker: AddressZoneLinker instance
    """
    stats = linker.get_pickup_info_stats()

    print("\n" + "=" * 80)
    print("ADDRESS PICKUP INFO STATISTICS")
    print("=" * 80)

    print(f"\nTotal addresses with pickup info: {stats['total']}")

    print("\nAddresses by city:")
    print("-" * 80)
    for city_name, count in stats['by_city']:
        print(f"  {city_name:40s} {count:4d}")

    print("\nAddresses by trash day:")
    print("-" * 80)
    for day, count in stats['by_day']:
        print(f"  {day:40s} {count:4d}")

    print("\nAddresses by pickup zone:")
    print("-" * 80)
    for zone_id, count in stats['by_zone']:
        print(f"  {zone_id:40s} {count:4d}")

    print("\n" + "=" * 80)
    print("SAMPLE ADDRESS PICKUP INFO ROWS")
    print("=" * 80)

    samples = linker.get_sample_pickup_info(limit=10)
    for i, sample in enumerate(samples, 1):
        print(f"\n{i}. {sample['house_number']} {sample['street']}, {sample['city_name']}")
        print(f"   Zone: {sample['pickup_zone_id']}")
        print(f"   Trash: {sample['trash_day_of_week']}")
        print(f"   Recycling: {sample['recycling_day_of_week']}")
        print(f"   Green Waste: {sample['green_waste_day_of_week']}")
        print(f"   Source: {sample['source']}")


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent
    db_path = base_dir / 'data' / 'trashalert.db'
    addresses_csv = base_dir / 'data' / 'addresses_sampled_50_per_city.csv'

    # Check if database exists
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        logger.error("Please run scripts/init_database.py first")
        return 1

    # Check if addresses CSV exists
    if not addresses_csv.exists():
        logger.error(f"Addresses CSV not found: {addresses_csv}")
        return 1

    with AddressZoneLinker(db_path) as linker:
        # Import addresses from CSV
        linker.import_addresses_from_csv(addresses_csv)

        # Process cities where we have pickup zone GIS data
        gis_dir = base_dir / 'data' / 'gis'

        if not gis_dir.exists():
            logger.error(f"GIS directory not found: {gis_dir}")
            return 1

        # Find all pickup zone GeoJSON files
        zone_files = list(gis_dir.glob('**/pickup_zones_*.geojson'))

        if not zone_files:
            logger.error("No pickup zone GeoJSON files found in data/gis/")
            logger.error("Expected files like: data/gis/cityname/pickup_zones_cityname.geojson")
            return 1

        logger.info(f"Found {len(zone_files)} pickup zone file(s)")

        total_matched = 0
        total_unmatched = 0

        for zone_file in zone_files:
            # Extract city name from filename
            # Expected format: pickup_zones_cityname.geojson
            filename = zone_file.stem  # e.g., "pickup_zones_brawley"
            city_name = filename.replace('pickup_zones_', '').replace('_', ' ').title()

            try:
                matched, unmatched = process_city(linker, city_name, zone_file)
                total_matched += matched
                total_unmatched += unmatched
            except Exception as e:
                logger.error(f"Error processing {city_name}: {e}")
                continue

        logger.info(f"\n{'=' * 80}")
        logger.info("OVERALL RESULTS")
        logger.info(f"{'=' * 80}")
        logger.info(f"Total matched: {total_matched}")
        logger.info(f"Total unmatched: {total_unmatched}")
        logger.info(f"Success rate: {total_matched / (total_matched + total_unmatched) * 100:.1f}%")

        # Print detailed statistics
        print_statistics(linker)

    logger.info(f"\n✓ Done! Address pickup info saved to database")
    return 0


if __name__ == '__main__':
    exit(main())
