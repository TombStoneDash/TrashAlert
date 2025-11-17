#!/usr/bin/env python3
"""
Add test crowd reports to the database.

This creates a variety of scenarios:
- High consensus addresses (verified)
- Medium consensus addresses (unverified)
- Low consensus addresses (conflicting reports)
- Single-report addresses
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
import random

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

random.seed(42)


def add_test_reports(db_path: Path):
    """Add test crowd reports."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get some address IDs
    cursor.execute("SELECT id FROM addresses LIMIT 20")
    address_ids = [row[0] for row in cursor.fetchall()]

    if len(address_ids) < 10:
        logger.error("Not enough addresses in database. Need at least 10 addresses.")
        conn.close()
        return False

    logger.info(f"Adding test reports for {len(address_ids)} addresses")

    # Scenario 1: High consensus - 5 reports, all agree (VERIFIED)
    logger.info("\nScenario 1: High consensus (5 reports, 100% agreement) - VERIFIED")
    address_id = address_ids[0]
    for i in range(5):
        cursor.execute("""
            INSERT INTO crowd_reports
                (address_id, reported_trash_day, reported_recycling_day, reported_at, report_source, user_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            address_id,
            'MON',
            'THU',
            (datetime.now() - timedelta(days=10-i)).isoformat(),
            'web',
            f'user_{i+1}'
        ))
    logger.info(f"  Address {address_id}: 5 reports for MON/THU")

    # Scenario 2: Good consensus - 4 reports, 3 agree, 1 differs (VERIFIED at 75%)
    logger.info("\nScenario 2: Good consensus (4 reports, 75% agreement) - VERIFIED")
    address_id = address_ids[1]
    for i in range(3):
        cursor.execute("""
            INSERT INTO crowd_reports
                (address_id, reported_trash_day, reported_recycling_day, reported_at, report_source, user_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            address_id,
            'TUE',
            'FRI',
            (datetime.now() - timedelta(days=8-i)).isoformat(),
            'web',
            f'user_{10+i}'
        ))
    # Add one dissenting report
    cursor.execute("""
        INSERT INTO crowd_reports
            (address_id, reported_trash_day, reported_at, report_source, user_hash)
        VALUES (?, ?, ?, ?, ?)
    """, (
        address_id,
        'WED',
        (datetime.now() - timedelta(days=5)).isoformat(),
        'mobile',
        'user_13'
    ))
    logger.info(f"  Address {address_id}: 3 reports for TUE/FRI, 1 for WED (75% agreement)")

    # Scenario 3: Medium consensus - 3 reports, all agree (VERIFIED)
    logger.info("\nScenario 3: Medium consensus (3 reports, 100% agreement) - VERIFIED")
    address_id = address_ids[2]
    for i in range(3):
        cursor.execute("""
            INSERT INTO crowd_reports
                (address_id, reported_trash_day, reported_green_day, reported_at, report_source, user_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            address_id,
            'WED',
            'MON',
            (datetime.now() - timedelta(days=6-i)).isoformat(),
            'web',
            f'user_{20+i}'
        ))
    logger.info(f"  Address {address_id}: 3 reports for WED (with green waste on MON)")

    # Scenario 4: Low consensus - 4 reports, split evenly (unverified)
    logger.info("\nScenario 4: Low consensus (4 reports, 50% agreement) - unverified")
    address_id = address_ids[3]
    for i in range(2):
        cursor.execute("""
            INSERT INTO crowd_reports
                (address_id, reported_trash_day, reported_at, report_source, user_hash)
            VALUES (?, ?, ?, ?, ?)
        """, (
            address_id,
            'THU',
            (datetime.now() - timedelta(days=7-i)).isoformat(),
            'web',
            f'user_{30+i}'
        ))
    for i in range(2):
        cursor.execute("""
            INSERT INTO crowd_reports
                (address_id, reported_trash_day, reported_at, report_source, user_hash)
            VALUES (?, ?, ?, ?, ?)
        """, (
            address_id,
            'FRI',
            (datetime.now() - timedelta(days=5-i)).isoformat(),
            'mobile',
            f'user_{32+i}'
        ))
    logger.info(f"  Address {address_id}: 2 reports for THU, 2 for FRI (50% agreement)")

    # Scenario 5: Insufficient reports - only 2 reports (unverified)
    logger.info("\nScenario 5: Insufficient reports (2 reports, 100% agreement) - unverified")
    address_id = address_ids[4]
    for i in range(2):
        cursor.execute("""
            INSERT INTO crowd_reports
                (address_id, reported_trash_day, reported_recycling_day, reported_at, report_source, user_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            address_id,
            'FRI',
            'TUE',
            (datetime.now() - timedelta(days=4-i)).isoformat(),
            'web',
            f'user_{40+i}'
        ))
    logger.info(f"  Address {address_id}: 2 reports for FRI/TUE (needs 3+ for verification)")

    # Scenario 6: Single report (unverified)
    logger.info("\nScenario 6: Single report - unverified")
    address_id = address_ids[5]
    cursor.execute("""
        INSERT INTO crowd_reports
            (address_id, reported_trash_day, reported_at, report_source, user_hash)
        VALUES (?, ?, ?, ?, ?)
    """, (
        address_id,
        'SAT',
        (datetime.now() - timedelta(days=3)).isoformat(),
        'mobile',
        'user_50'
    ))
    logger.info(f"  Address {address_id}: 1 report for SAT")

    # Scenario 7: High volume, strong consensus - 8 reports, 7 agree (VERIFIED)
    logger.info("\nScenario 7: High volume consensus (8 reports, 87.5% agreement) - VERIFIED")
    address_id = address_ids[6]
    for i in range(7):
        cursor.execute("""
            INSERT INTO crowd_reports
                (address_id, reported_trash_day, reported_recycling_day, reported_at, report_source, user_hash)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            address_id,
            'MON',
            'WED',
            (datetime.now() - timedelta(days=14-i)).isoformat(),
            random.choice(['web', 'mobile', 'import']),
            f'user_{60+i}'
        ))
    # Add one dissenting report
    cursor.execute("""
        INSERT INTO crowd_reports
            (address_id, reported_trash_day, reported_at, report_source, user_hash)
        VALUES (?, ?, ?, ?, ?)
    """, (
        address_id,
        'TUE',
        (datetime.now() - timedelta(days=7)).isoformat(),
        'mobile',
        'user_67'
    ))
    logger.info(f"  Address {address_id}: 7 reports for MON/WED, 1 for TUE (87.5% agreement)")

    # Scenario 8: Borderline verification - 3 reports, 2 agree (unverified at 66.7%)
    logger.info("\nScenario 8: Borderline (3 reports, 66.7% agreement) - unverified")
    address_id = address_ids[7]
    for i in range(2):
        cursor.execute("""
            INSERT INTO crowd_reports
                (address_id, reported_trash_day, reported_at, report_source, user_hash)
            VALUES (?, ?, ?, ?, ?)
        """, (
            address_id,
            'TUE',
            (datetime.now() - timedelta(days=5-i)).isoformat(),
            'web',
            f'user_{70+i}'
        ))
    cursor.execute("""
        INSERT INTO crowd_reports
            (address_id, reported_trash_day, reported_at, report_source, user_hash)
        VALUES (?, ?, ?, ?, ?)
    """, (
        address_id,
        'WED',
        (datetime.now() - timedelta(days=3)).isoformat(),
        'mobile',
        'user_72'
    ))
    logger.info(f"  Address {address_id}: 2 reports for TUE, 1 for WED (66.7% < 75% threshold)")

    conn.commit()

    # Count total reports
    cursor.execute("SELECT COUNT(*) FROM crowd_reports")
    total_reports = cursor.fetchone()[0]

    conn.close()

    logger.info(f"\n✓ Added {total_reports} test crowd reports")
    return True


def show_test_data(db_path: Path):
    """Display the test data that was inserted."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n" + "=" * 80)
    print("CROWD REPORTS TEST DATA")
    print("=" * 80)

    cursor.execute("""
        SELECT
            cr.id,
            cr.address_id,
            a.city_name,
            a.house_number,
            a.street,
            cr.reported_trash_day,
            cr.reported_recycling_day,
            cr.reported_green_day,
            cr.report_source,
            cr.user_hash
        FROM crowd_reports cr
        JOIN addresses a ON cr.address_id = a.id
        ORDER BY cr.address_id, cr.id
    """)

    current_address = None
    for row in cursor.fetchall():
        (id, address_id, city, house_num, street, trash, recycling, green, source, user_hash) = row

        if address_id != current_address:
            print(f"\nAddress {address_id}: {house_num} {street}, {city}")
            print("-" * 80)
            current_address = address_id

        recycling_str = f", Recycling: {recycling}" if recycling else ""
        green_str = f", Green: {green}" if green else ""
        print(f"  Report {id}: Trash: {trash}{recycling_str}{green_str} [{source}] ({user_hash})")

    conn.close()


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent
    db_path = base_dir / 'trashpilot.db'

    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        logger.error("Please run create_database.py and load_addresses.py first")
        return 1

    if add_test_reports(db_path):
        show_test_data(db_path)
        return 0
    else:
        return 1


if __name__ == '__main__':
    exit(main())
