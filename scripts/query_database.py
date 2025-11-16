"""
Query tool for the trash day lookup database
Demonstrates various ways to query and use the pilot database
"""
import sys
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional

sys.path.append('..')
from config import DB_PATH


class AddressLookup:
    """Query addresses from the pilot database"""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def find_by_address(self, street_number: str, street_name: str,
                       city: Optional[str] = None) -> List[Dict]:
        """
        Find addresses matching street number and name

        Args:
            street_number: House/building number
            street_name: Street name
            city: Optional city name to narrow search

        Returns:
            List of matching address records
        """
        query = """
            SELECT
                a.address_id,
                a.street_number,
                a.street_name,
                a.unit,
                a.postal_code,
                a.latitude,
                a.longitude,
                a.building_type,
                c.name as city_name,
                c.state
            FROM addresses a
            JOIN cities c ON a.city_id = c.city_id
            WHERE a.street_number LIKE ?
            AND a.street_name LIKE ?
        """

        params = [f"%{street_number}%", f"%{street_name}%"]

        if city:
            query += " AND c.name LIKE ?"
            params.append(f"%{city}%")

        cursor = self.conn.cursor()
        cursor.execute(query, params)

        return [dict(row) for row in cursor.fetchall()]

    def find_by_coordinates(self, lat: float, lon: float,
                           radius_km: float = 1.0) -> List[Dict]:
        """
        Find addresses near a coordinate (approximate)

        Args:
            lat: Latitude
            lon: Longitude
            radius_km: Search radius in kilometers

        Returns:
            List of nearby addresses
        """
        # Simple bounding box search (good enough for pilot)
        # For production, use PostGIS or proper geodesic calculations
        deg_per_km = 1 / 111.0  # Approximate

        lat_range = radius_km * deg_per_km
        lon_range = radius_km * deg_per_km

        query = """
            SELECT
                a.address_id,
                a.street_number,
                a.street_name,
                a.unit,
                a.postal_code,
                a.latitude,
                a.longitude,
                a.building_type,
                c.name as city_name,
                c.state,
                -- Approximate distance
                ROUND(111.0 * SQRT(
                    (a.latitude - ?) * (a.latitude - ?) +
                    (a.longitude - ?) * (a.longitude - ?)
                ), 2) as distance_km
            FROM addresses a
            JOIN cities c ON a.city_id = c.city_id
            WHERE a.latitude BETWEEN ? AND ?
            AND a.longitude BETWEEN ? AND ?
            ORDER BY distance_km
            LIMIT 50
        """

        cursor = self.conn.cursor()
        cursor.execute(query, (
            lat, lat,
            lon, lon,
            lat - lat_range, lat + lat_range,
            lon - lon_range, lon + lon_range
        ))

        return [dict(row) for row in cursor.fetchall()]

    def find_by_postal_code(self, postal_code: str) -> List[Dict]:
        """Find all addresses in a postal code"""
        query = """
            SELECT
                a.address_id,
                a.street_number,
                a.street_name,
                a.unit,
                a.postal_code,
                c.name as city_name,
                c.state,
                COUNT(*) OVER() as total_count
            FROM addresses a
            JOIN cities c ON a.city_id = c.city_id
            WHERE a.postal_code = ?
            LIMIT 100
        """

        cursor = self.conn.cursor()
        cursor.execute(query, (postal_code,))

        return [dict(row) for row in cursor.fetchall()]

    def find_by_city(self, city_name: str, limit: int = 100) -> List[Dict]:
        """Get addresses from a specific city"""
        query = """
            SELECT
                a.address_id,
                a.street_number,
                a.street_name,
                a.unit,
                a.postal_code,
                a.latitude,
                a.longitude,
                c.name as city_name,
                c.state
            FROM addresses a
            JOIN cities c ON a.city_id = c.city_id
            WHERE c.name LIKE ?
            LIMIT ?
        """

        cursor = self.conn.cursor()
        cursor.execute(query, (f"%{city_name}%", limit))

        return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self) -> Dict:
        """Get database statistics"""
        cursor = self.conn.cursor()

        # Total addresses
        cursor.execute("SELECT COUNT(*) FROM addresses")
        total_addresses = cursor.fetchone()[0]

        # Addresses by city
        cursor.execute("""
            SELECT
                c.name,
                COUNT(a.address_id) as count
            FROM cities c
            LEFT JOIN addresses a ON c.city_id = a.city_id
            GROUP BY c.city_id
            ORDER BY c.name
        """)
        by_city = {row[0]: row[1] for row in cursor.fetchall()}

        # Building types
        cursor.execute("""
            SELECT
                building_type,
                COUNT(*) as count
            FROM addresses
            WHERE building_type IS NOT NULL
            GROUP BY building_type
            ORDER BY count DESC
        """)
        by_type = {row[0]: row[1] for row in cursor.fetchall()}

        return {
            'total_addresses': total_addresses,
            'by_city': by_city,
            'by_building_type': by_type
        }


def main():
    """Demonstration of database queries"""
    print("=" * 70)
    print("TRASH DAY LOOKUP DATABASE - QUERY DEMONSTRATION")
    print("=" * 70)

    lookup = AddressLookup()

    # Get statistics
    print("\n1. DATABASE STATISTICS")
    print("-" * 70)
    stats = lookup.get_statistics()
    print(f"Total Addresses: {stats['total_addresses']:,}")
    print(f"\nAddresses by City:")
    for city, count in stats['by_city'].items():
        print(f"  {city}: {count:,}")
    print(f"\nBuilding Types:")
    for btype, count in stats['by_building_type'].items():
        print(f"  {btype}: {count:,}")

    # Search by city
    print("\n2. SEARCH BY CITY: Holtville")
    print("-" * 70)
    holtville_addresses = lookup.find_by_city("Holtville", limit=5)
    for addr in holtville_addresses:
        addr_str = f"{addr['street_number']} {addr['street_name']}"
        if addr['unit']:
            addr_str += f" {addr['unit']}"
        print(f"  {addr_str}, {addr['city_name']}, {addr['state']} {addr['postal_code']}")
        print(f"    Location: ({addr['latitude']}, {addr['longitude']})")

    # Search by postal code
    print("\n3. SEARCH BY POSTAL CODE: 92243 (El Centro)")
    print("-" * 70)
    el_centro_addresses = lookup.find_by_postal_code("92243")
    total = el_centro_addresses[0]['total_count'] if el_centro_addresses else 0
    print(f"Found {total} addresses in postal code 92243")
    print("Sample addresses:")
    for addr in el_centro_addresses[:5]:
        addr_str = f"{addr['street_number']} {addr['street_name']}"
        if addr['unit']:
            addr_str += f" {addr['unit']}"
        print(f"  {addr_str}, {addr['postal_code']}")

    # Search by coordinates (near Holtville center)
    print("\n4. SEARCH BY COORDINATES: Near Holtville (32.8116, -115.3803)")
    print("-" * 70)
    nearby = lookup.find_by_coordinates(32.8116, -115.3803, radius_km=2.0)
    print(f"Found {len(nearby)} addresses within 2 km")
    print("Nearest addresses:")
    for addr in nearby[:5]:
        addr_str = f"{addr['street_number']} {addr['street_name']}"
        print(f"  {addr_str} - {addr['distance_km']} km away")

    # Search by address
    print("\n5. SEARCH BY STREET: 'Main Street'")
    print("-" * 70)
    main_streets = lookup.find_by_address("", "Main Street")
    print(f"Found {len(main_streets)} addresses on Main Street across all cities")
    # Group by city
    by_city = {}
    for addr in main_streets:
        city = addr['city_name']
        by_city[city] = by_city.get(city, 0) + 1
    for city, count in by_city.items():
        print(f"  {city}: {count} addresses")

    print("\n" + "=" * 70)
    print("Query demonstration complete!")
    print("=" * 70)

    lookup.close()


if __name__ == "__main__":
    main()
