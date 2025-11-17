#!/usr/bin/env python3
"""
Initialize sample database with crowd-sourced trash pickup data.
This creates trashpilot.db with realistic test data.
"""

import sqlite3
import random
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

# Set seed for reproducibility
random.seed(42)

def create_schema(conn):
    """Create database schema."""
    cursor = conn.cursor()

    # Addresses table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS addresses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        city_name TEXT NOT NULL,
        subdivision_id TEXT,
        house_number TEXT NOT NULL,
        street TEXT NOT NULL,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        osm_id TEXT,
        official_pickup_day TEXT,
        official_pickup_time TEXT,
        has_official_info BOOLEAN DEFAULT 0,
        verified_crowd_consensus BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(city_name, house_number, street)
    )
    """)

    # Crowd reports table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS crowd_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        address_id INTEGER NOT NULL,
        user_id TEXT NOT NULL,
        reported_pickup_day TEXT NOT NULL,
        reported_pickup_time TEXT,
        confidence TEXT CHECK(confidence IN ('low', 'medium', 'high')),
        reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (address_id) REFERENCES addresses(id)
    )
    """)

    # Aggregated crowd data view
    cursor.execute("""
    CREATE VIEW IF NOT EXISTS crowd_consensus AS
    SELECT
        a.id as address_id,
        a.city_name,
        a.subdivision_id,
        a.house_number,
        a.street,
        a.lat,
        a.lon,
        a.has_official_info,
        a.verified_crowd_consensus,
        a.official_pickup_day,
        COUNT(cr.id) as reports_count,
        cr_majority.reported_pickup_day as consensus_pickup_day,
        cr_majority.report_count as consensus_count,
        CAST(cr_majority.report_count AS REAL) / COUNT(cr.id) as agreement_ratio
    FROM addresses a
    LEFT JOIN crowd_reports cr ON a.id = cr.address_id
    LEFT JOIN (
        SELECT
            address_id,
            reported_pickup_day,
            COUNT(*) as report_count
        FROM crowd_reports
        GROUP BY address_id, reported_pickup_day
        HAVING COUNT(*) = (
            SELECT MAX(cnt)
            FROM (
                SELECT COUNT(*) as cnt
                FROM crowd_reports cr2
                WHERE cr2.address_id = crowd_reports.address_id
                GROUP BY reported_pickup_day
            )
        )
    ) cr_majority ON a.id = cr_majority.address_id
    WHERE cr.id IS NOT NULL
    GROUP BY a.id
    """)

    conn.commit()
    print("✓ Database schema created")


def populate_addresses(conn):
    """Load addresses from CSV and insert into database."""
    cursor = conn.cursor()

    # Load sampled addresses
    csv_path = Path(__file__).parent.parent / 'data' / 'addresses_sampled_50_per_city.csv'

    if not csv_path.exists():
        print(f"Warning: {csv_path} not found, using raw data instead")
        csv_path = Path(__file__).parent.parent / 'data' / 'addresses_osm_raw.csv'

    df = pd.read_csv(csv_path)

    # Insert addresses
    for _, row in df.iterrows():
        cursor.execute("""
        INSERT OR IGNORE INTO addresses
        (city_name, subdivision_id, house_number, street, lat, lon, osm_id, has_official_info)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row['city_name'],
            row.get('subdivision_id') if pd.notna(row.get('subdivision_id')) else None,
            row['house_number'],
            row['street'],
            row['lat'],
            row['lon'],
            row.get('osm_id'),
            random.random() < 0.3  # 30% have official info
        ))

    conn.commit()
    count = cursor.execute("SELECT COUNT(*) FROM addresses").fetchone()[0]
    print(f"✓ Inserted {count} addresses")

    # Add official pickup info for addresses that have it
    cursor.execute("""
    UPDATE addresses
    SET official_pickup_day = (
        CASE (id % 5)
            WHEN 0 THEN 'Monday'
            WHEN 1 THEN 'Tuesday'
            WHEN 2 THEN 'Wednesday'
            WHEN 3 THEN 'Thursday'
            WHEN 4 THEN 'Friday'
        END
    ),
    official_pickup_time = '07:00'
    WHERE has_official_info = 1
    """)

    conn.commit()


def generate_crowd_reports(conn):
    """Generate realistic crowd reports with varying agreement levels."""
    cursor = conn.cursor()

    # Get all addresses
    addresses = cursor.execute("SELECT id, city_name FROM addresses").fetchall()

    pickup_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    confidence_levels = ['low', 'medium', 'high']

    # Different report patterns:
    # 1. High agreement (70-100% agree)
    # 2. Moderate agreement (40-69% agree)
    # 3. Low agreement (< 40% agree)
    # 4. No reports yet

    for addr_id, city in addresses:
        # 20% of addresses have no reports
        if random.random() < 0.2:
            continue

        # Determine number of reports (more for popular areas)
        if city == 'San Diego':
            num_reports = random.randint(3, 15)
        elif city in ['El Centro', 'Calexico']:
            num_reports = random.randint(2, 10)
        else:
            num_reports = random.randint(1, 6)

        # Determine agreement level
        agreement_type = random.choice(['high', 'high', 'moderate', 'low'])

        if agreement_type == 'high':
            # 80-100% agree on the same day
            consensus_day = random.choice(pickup_days)
            agree_count = int(num_reports * random.uniform(0.8, 1.0))
            disagree_count = num_reports - agree_count

            # Generate agreeing reports
            for _ in range(agree_count):
                user_id = f"user_{random.randint(1000, 9999)}"
                confidence = random.choice(['medium', 'high', 'high'])
                reported_at = datetime.now() - timedelta(days=random.randint(1, 90))

                cursor.execute("""
                INSERT INTO crowd_reports
                (address_id, user_id, reported_pickup_day, confidence, reported_at)
                VALUES (?, ?, ?, ?, ?)
                """, (addr_id, user_id, consensus_day, confidence, reported_at))

            # Generate disagreeing reports
            for _ in range(disagree_count):
                user_id = f"user_{random.randint(1000, 9999)}"
                other_day = random.choice([d for d in pickup_days if d != consensus_day])
                confidence = random.choice(['low', 'medium'])
                reported_at = datetime.now() - timedelta(days=random.randint(1, 90))

                cursor.execute("""
                INSERT INTO crowd_reports
                (address_id, user_id, reported_pickup_day, confidence, reported_at)
                VALUES (?, ?, ?, ?, ?)
                """, (addr_id, user_id, other_day, confidence, reported_at))

        elif agreement_type == 'moderate':
            # 50-70% agree on the same day
            consensus_day = random.choice(pickup_days)
            agree_count = int(num_reports * random.uniform(0.5, 0.7))
            disagree_count = num_reports - agree_count

            for _ in range(agree_count):
                user_id = f"user_{random.randint(1000, 9999)}"
                confidence = random.choice(confidence_levels)
                reported_at = datetime.now() - timedelta(days=random.randint(1, 90))

                cursor.execute("""
                INSERT INTO crowd_reports
                (address_id, user_id, reported_pickup_day, confidence, reported_at)
                VALUES (?, ?, ?, ?, ?)
                """, (addr_id, user_id, consensus_day, confidence, reported_at))

            for _ in range(disagree_count):
                user_id = f"user_{random.randint(1000, 9999)}"
                other_day = random.choice([d for d in pickup_days if d != consensus_day])
                confidence = random.choice(confidence_levels)
                reported_at = datetime.now() - timedelta(days=random.randint(1, 90))

                cursor.execute("""
                INSERT INTO crowd_reports
                (address_id, user_id, reported_pickup_day, confidence, reported_at)
                VALUES (?, ?, ?, ?, ?)
                """, (addr_id, user_id, other_day, confidence, reported_at))

        else:  # low agreement
            # Reports are spread across multiple days
            for _ in range(num_reports):
                user_id = f"user_{random.randint(1000, 9999)}"
                day = random.choice(pickup_days)
                confidence = random.choice(confidence_levels)
                reported_at = datetime.now() - timedelta(days=random.randint(1, 90))

                cursor.execute("""
                INSERT INTO crowd_reports
                (address_id, user_id, reported_pickup_day, confidence, reported_at)
                VALUES (?, ?, ?, ?, ?)
                """, (addr_id, user_id, day, confidence, reported_at))

    conn.commit()
    count = cursor.execute("SELECT COUNT(*) FROM crowd_reports").fetchone()[0]
    print(f"✓ Generated {count} crowd reports")

    # Mark addresses with high agreement as verified
    cursor.execute("""
    UPDATE addresses
    SET verified_crowd_consensus = 1
    WHERE id IN (
        SELECT address_id
        FROM crowd_consensus
        WHERE agreement_ratio >= 0.75 AND reports_count >= 5
    )
    """)

    conn.commit()
    verified_count = cursor.execute(
        "SELECT COUNT(*) FROM addresses WHERE verified_crowd_consensus = 1"
    ).fetchone()[0]
    print(f"✓ Marked {verified_count} addresses with verified crowd consensus")


def print_summary(conn):
    """Print database summary."""
    cursor = conn.cursor()

    print("\n" + "=" * 80)
    print("DATABASE SUMMARY")
    print("=" * 80)

    # Total stats
    total_addresses = cursor.execute("SELECT COUNT(*) FROM addresses").fetchone()[0]
    total_reports = cursor.execute("SELECT COUNT(*) FROM crowd_reports").fetchone()[0]

    print(f"\nTotal addresses: {total_addresses}")
    print(f"Total crowd reports: {total_reports}")

    # Per-city breakdown
    print("\nPer-city breakdown:")
    print("-" * 80)

    cities = cursor.execute("""
    SELECT
        city_name,
        COUNT(*) as total_addresses,
        SUM(has_official_info) as with_official_info,
        SUM(verified_crowd_consensus) as with_consensus
    FROM addresses
    GROUP BY city_name
    ORDER BY total_addresses DESC
    """).fetchall()

    for city, total, official, consensus in cities:
        print(f"  {city:20s} | Total: {total:3d} | Official: {official:3d} | Consensus: {consensus:3d}")

    print("\n✓ Database initialized successfully!")


def main():
    """Initialize the database."""
    db_path = Path(__file__).parent.parent / 'trashpilot.db'

    # Remove existing database
    if db_path.exists():
        db_path.unlink()
        print(f"Removed existing database: {db_path}")

    # Create new database
    print(f"\nCreating database: {db_path}")
    conn = sqlite3.connect(db_path)

    try:
        create_schema(conn)
        populate_addresses(conn)
        generate_crowd_reports(conn)
        print_summary(conn)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
