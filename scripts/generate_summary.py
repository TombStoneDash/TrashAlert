"""
Generate a comprehensive summary report for the pilot database
"""
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

sys.path.append('..')
from config import DB_PATH


def generate_summary():
    """Generate detailed summary report"""

    db_path = Path(DB_PATH)
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    print("=" * 80)
    print(" " * 20 + "TRASH DAY LOOKUP PILOT DATABASE")
    print(" " * 28 + "SUMMARY REPORT")
    print("=" * 80)
    print(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Database: {db_path}")
    print(f"Size: {db_path.stat().st_size:,} bytes ({db_path.stat().st_size / 1024:.1f} KB)")

    # Overall statistics
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM cities")
    city_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM addresses")
    address_count = cursor.fetchone()[0]

    print(f"\n{'─' * 80}")
    print("OVERALL STATISTICS")
    print(f"{'─' * 80}")
    print(f"  Cities: {city_count}")
    print(f"  Addresses: {address_count:,}")
    print(f"  Average per city: {address_count // city_count:,}")

    # City-by-city breakdown
    print(f"\n{'─' * 80}")
    print("CITY-BY-CITY BREAKDOWN")
    print(f"{'─' * 80}")

    cursor.execute("""
        SELECT
            c.name,
            c.state,
            c.county,
            c.bbox_north,
            c.bbox_south,
            c.bbox_east,
            c.bbox_west,
            COUNT(a.address_id) as address_count,
            COUNT(DISTINCT a.postal_code) as postal_codes,
            COUNT(DISTINCT a.street_name) as unique_streets
        FROM cities c
        LEFT JOIN addresses a ON c.city_id = a.city_id
        GROUP BY c.city_id
        ORDER BY c.name
    """)

    cities = cursor.fetchall()

    for city in cities:
        print(f"\n  🏙️  {city['name']}, {city['state']}")
        print(f"      County: {city['county']}")
        print(f"      Addresses: {city['address_count']:,}")
        print(f"      Unique Streets: {city['unique_streets']}")
        print(f"      Postal Codes: {city['postal_codes']}")
        print(f"      Bounding Box:")
        print(f"        N: {city['bbox_north']:.4f}  S: {city['bbox_south']:.4f}")
        print(f"        E: {city['bbox_east']:.4f}   W: {city['bbox_west']:.4f}")

    # Building type distribution
    print(f"\n{'─' * 80}")
    print("BUILDING TYPE DISTRIBUTION")
    print(f"{'─' * 80}")

    cursor.execute("""
        SELECT
            COALESCE(building_type, 'Unknown') as type,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM addresses), 1) as percentage
        FROM addresses
        GROUP BY building_type
        ORDER BY count DESC
    """)

    for row in cursor.fetchall():
        bar_length = int(row['percentage'] / 2)  # Scale to fit
        bar = '█' * bar_length
        print(f"  {row['type']:15s} {row['count']:4d} ({row['percentage']:5.1f}%) {bar}")

    # Postal code distribution
    print(f"\n{'─' * 80}")
    print("POSTAL CODE DISTRIBUTION")
    print(f"{'─' * 80}")

    cursor.execute("""
        SELECT
            a.postal_code,
            c.name as city,
            COUNT(*) as count
        FROM addresses a
        JOIN cities c ON a.city_id = c.city_id
        GROUP BY a.postal_code, c.name
        ORDER BY c.name
    """)

    for row in cursor.fetchall():
        print(f"  {row['postal_code']}  ({row['city']:15s})  {row['count']:4d} addresses")

    # Top streets by address count
    print(f"\n{'─' * 80}")
    print("TOP 15 STREETS BY ADDRESS COUNT")
    print(f"{'─' * 80}")

    cursor.execute("""
        SELECT
            a.street_name,
            c.name as city,
            COUNT(*) as count
        FROM addresses a
        JOIN cities c ON a.city_id = c.city_id
        GROUP BY a.street_name, c.name
        ORDER BY count DESC, a.street_name
        LIMIT 15
    """)

    for row in cursor.fetchall():
        print(f"  {row['street_name']:25s} ({row['city']:15s})  {row['count']:3d} addresses")

    # Data quality metrics
    print(f"\n{'─' * 80}")
    print("DATA QUALITY METRICS")
    print(f"{'─' * 80}")

    cursor.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(postal_code) as with_postal,
            COUNT(unit) as with_unit,
            COUNT(building_type) as with_building_type,
            COUNT(latitude) as with_coords
        FROM addresses
    """)

    quality = cursor.fetchone()
    total = quality['total']

    print(f"  Total Records: {total:,}")
    print(f"  With Postal Code: {quality['with_postal']:,} ({quality['with_postal']/total*100:.1f}%)")
    print(f"  With Unit Number: {quality['with_unit']:,} ({quality['with_unit']/total*100:.1f}%)")
    print(f"  With Building Type: {quality['with_building_type']:,} ({quality['with_building_type']/total*100:.1f}%)")
    print(f"  With Coordinates: {quality['with_coords']:,} ({quality['with_coords']/total*100:.1f}%)")

    # Schema info
    print(f"\n{'─' * 80}")
    print("DATABASE SCHEMA")
    print(f"{'─' * 80}")

    cursor.execute("""
        SELECT name, sql
        FROM sqlite_master
        WHERE type='table'
        ORDER BY name
    """)

    for table in cursor.fetchall():
        print(f"\n  Table: {table['name']}")
        # Count rows
        cursor.execute(f"SELECT COUNT(*) FROM {table['name']}")
        count = cursor.fetchone()[0]
        print(f"  Rows: {count:,}")

    # Indexes
    cursor.execute("""
        SELECT name, tbl_name
        FROM sqlite_master
        WHERE type='index' AND sql IS NOT NULL
        ORDER BY tbl_name, name
    """)

    indexes = cursor.fetchall()
    if indexes:
        print(f"\n  Indexes:")
        for idx in indexes:
            print(f"    - {idx['name']} on {idx['tbl_name']}")

    print(f"\n{'=' * 80}")
    print(" " * 25 + "🎉 DATABASE READY FOR USE 🎉")
    print("=" * 80)
    print(f"\nNext steps:")
    print(f"  1. Query the database: python3 query_database.py")
    print(f"  2. Integrate into your app using db_manager.py")
    print(f"  3. Add trash collection schedules to trash_schedules table")
    print(f"  4. Extend to more cities by editing config.py")
    print()

    conn.close()


if __name__ == "__main__":
    generate_summary()
