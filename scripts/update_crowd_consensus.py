#!/usr/bin/env python3
"""
Update crowd consensus based on crowd reports.

This script:
1. Groups crowd_reports by address_id
2. Computes the most common reported pickup days
3. Calculates agreement ratios
4. Upserts results into crowd_consensus
5. Applies verification rules (3+ reports AND 75%+ agreement)
"""

import sqlite3
import logging
from pathlib import Path
from collections import Counter
from datetime import datetime
from typing import Dict, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Verification thresholds
MIN_REPORTS_FOR_VERIFICATION = 3
MIN_AGREEMENT_RATIO = 0.75


def compute_consensus_for_day_type(reports: list) -> Tuple[Optional[str], float]:
    """
    Compute consensus for a single day type (trash, recycling, or green).

    Args:
        reports: List of reported days (may contain None values)

    Returns:
        Tuple of (most_common_day, agreement_ratio)
    """
    # Filter out None values
    valid_reports = [r for r in reports if r is not None]

    if not valid_reports:
        return None, 0.0

    # Count occurrences
    counter = Counter(valid_reports)
    most_common_day, count = counter.most_common(1)[0]

    # Calculate agreement ratio
    agreement_ratio = count / len(valid_reports)

    return most_common_day, agreement_ratio


def update_consensus(db_path: Path, verbose: bool = True):
    """
    Update crowd consensus based on all crowd reports.

    Args:
        db_path: Path to the database
        verbose: Whether to log detailed information
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all reports grouped by address_id
    cursor.execute("""
        SELECT
            address_id,
            reported_trash_day,
            reported_recycling_day,
            reported_green_day
        FROM crowd_reports
        ORDER BY address_id
    """)

    reports = cursor.fetchall()

    if not reports:
        logger.info("No crowd reports found")
        conn.close()
        return

    # Group reports by address_id
    address_reports: Dict[int, list] = {}
    for address_id, trash_day, recycling_day, green_day in reports:
        if address_id not in address_reports:
            address_reports[address_id] = {
                'trash': [],
                'recycling': [],
                'green': []
            }
        address_reports[address_id]['trash'].append(trash_day)
        address_reports[address_id]['recycling'].append(recycling_day)
        address_reports[address_id]['green'].append(green_day)

    logger.info(f"Processing consensus for {len(address_reports)} addresses")

    updated_count = 0
    verified_count = 0

    for address_id, days in address_reports.items():
        total_reports = len(days['trash'])

        # Compute consensus for each day type
        trash_consensus, trash_agreement = compute_consensus_for_day_type(days['trash'])
        recycling_consensus, recycling_agreement = compute_consensus_for_day_type(days['recycling'])
        green_consensus, green_agreement = compute_consensus_for_day_type(days['green'])

        # Overall agreement ratio is based on trash day (primary field)
        agreement_ratio = trash_agreement

        # Check if verified
        is_verified = (
            total_reports >= MIN_REPORTS_FOR_VERIFICATION and
            agreement_ratio >= MIN_AGREEMENT_RATIO
        )

        # Upsert into crowd_consensus
        cursor.execute("""
            INSERT INTO crowd_consensus
                (address_id, trash_day, recycling_day, green_day, reports_count, agreement_ratio, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(address_id) DO UPDATE SET
                trash_day = excluded.trash_day,
                recycling_day = excluded.recycling_day,
                green_day = excluded.green_day,
                reports_count = excluded.reports_count,
                agreement_ratio = excluded.agreement_ratio,
                last_updated = excluded.last_updated
        """, (
            address_id,
            trash_consensus,
            recycling_consensus,
            green_consensus,
            total_reports,
            agreement_ratio,
            datetime.now().isoformat()
        ))

        updated_count += 1
        if is_verified:
            verified_count += 1

        if verbose:
            status = "✓ VERIFIED" if is_verified else "  unverified"
            logger.info(
                f"{status} | Address {address_id}: {trash_consensus} "
                f"({total_reports} reports, {agreement_ratio:.1%} agreement)"
            )

    conn.commit()
    conn.close()

    logger.info(f"\n✓ Updated consensus for {updated_count} addresses")
    logger.info(f"  {verified_count} addresses are VERIFIED (≥{MIN_REPORTS_FOR_VERIFICATION} reports, "
                f"≥{MIN_AGREEMENT_RATIO:.0%} agreement)")
    logger.info(f"  {updated_count - verified_count} addresses are unverified")


def show_consensus_summary(db_path: Path):
    """Display a summary of the consensus data."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n" + "=" * 80)
    print("CROWD CONSENSUS SUMMARY")
    print("=" * 80)

    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN reports_count >= ? AND agreement_ratio >= ? THEN 1 ELSE 0 END) as verified,
            AVG(reports_count) as avg_reports,
            AVG(agreement_ratio) as avg_agreement
        FROM crowd_consensus
    """, (MIN_REPORTS_FOR_VERIFICATION, MIN_AGREEMENT_RATIO))

    total, verified, avg_reports, avg_agreement = cursor.fetchone()

    if total:
        print(f"\nTotal addresses with consensus: {total}")
        print(f"Verified addresses: {verified} ({verified/total*100:.1f}%)")
        print(f"Average reports per address: {avg_reports:.1f}")
        print(f"Average agreement ratio: {avg_agreement:.1%}")
    else:
        print("\nNo consensus data available")

    # Show distribution of trash days
    print("\n" + "-" * 80)
    print("TRASH DAY DISTRIBUTION")
    print("-" * 80)

    cursor.execute("""
        SELECT trash_day, COUNT(*) as count
        FROM crowd_consensus
        WHERE trash_day IS NOT NULL
        GROUP BY trash_day
        ORDER BY count DESC
    """)

    for day, count in cursor.fetchall():
        print(f"  {day}: {count} addresses")

    conn.close()


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent
    db_path = base_dir / 'trashpilot.db'

    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        logger.error("Please run create_database.py first")
        return 1

    update_consensus(db_path, verbose=True)
    show_consensus_summary(db_path)

    return 0


if __name__ == '__main__':
    exit(main())
