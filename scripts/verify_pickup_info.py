#!/usr/bin/env python3
"""Quick verification script to check address_pickup_info table."""

import sqlite3
from pathlib import Path

db_path = Path(__file__).parent.parent / 'data' / 'trashalert.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 80)
print("DATABASE VERIFICATION")
print("=" * 80)

# Total addresses
cursor.execute("SELECT COUNT(*) FROM addresses")
total_addresses = cursor.fetchone()[0]
print(f"\nTotal addresses in database: {total_addresses}")

# Addresses with pickup info
cursor.execute("SELECT COUNT(*) FROM address_pickup_info")
total_with_info = cursor.fetchone()[0]
print(f"Addresses with pickup info: {total_with_info}")
print(f"Coverage: {total_with_info / total_addresses * 100:.1f}%")

# Sample rows with full details
print("\n" + "=" * 80)
print("DETAILED SAMPLE ROWS (showing all fields)")
print("=" * 80)

cursor.execute("""
    SELECT
        a.address_id,
        c.city_name,
        a.house_number || ' ' || a.street as full_address,
        a.lat,
        a.lon,
        api.pickup_zone_id,
        api.trash_day_of_week,
        api.recycling_day_of_week,
        api.green_waste_day_of_week,
        api.source,
        api.created_at
    FROM address_pickup_info api
    JOIN addresses a ON api.address_id = a.address_id
    JOIN cities c ON api.city_id = c.city_id
    LIMIT 5
""")

for row in cursor.fetchall():
    print(f"\nAddress ID: {row[0]}")
    print(f"  Location: {row[2]}, {row[1]}")
    print(f"  Coordinates: ({row[3]:.6f}, {row[4]:.6f})")
    print(f"  Pickup Zone: {row[5]}")
    print(f"  Trash Day: {row[6]}")
    print(f"  Recycling Day: {row[7]}")
    print(f"  Green Waste Day: {row[8]}")
    print(f"  Source: {row[9]}")
    print(f"  Created: {row[10]}")

conn.close()
print("\n" + "=" * 80)
