#!/usr/bin/env python3
"""
Admin/debug dashboard for inspecting crowd-sourced trash pickup data.

This script provides insights into:
- Hotspots: addresses with the most crowd reports
- Low agreement areas: addresses where users disagree on pickup days
- Per-city statistics: coverage and consensus metrics
"""

import sqlite3
import argparse
from pathlib import Path
from typing import Optional


def connect_db(db_path: Path) -> sqlite3.Connection:
    """Connect to the database."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn


def print_top_hotspots(conn: sqlite3.Connection, city: Optional[str] = None, limit: int = 10):
    """Print top addresses with the most crowd reports."""
    cursor = conn.cursor()

    print("\n" + "=" * 100)
    print(f"TOP {limit} ADDRESSES WITH MOST CROWD REPORTS")
    print("=" * 100)

    city_filter = ""
    params = [limit]

    if city:
        city_filter = "WHERE city_name = ?"
        params = [city, limit]

    query = f"""
    SELECT
        city_name,
        house_number || ' ' || street as address,
        reports_count,
        consensus_pickup_day,
        ROUND(agreement_ratio * 100, 1) as agreement_pct,
        verified_crowd_consensus,
        has_official_info
    FROM crowd_consensus
    {city_filter}
    ORDER BY reports_count DESC
    LIMIT ?
    """

    rows = cursor.execute(query, params).fetchall()

    if not rows:
        print("No crowd reports found" + (f" for city: {city}" if city else ""))
        return

    # Print table header
    print(f"\n{'City':<20} {'Address':<35} {'Reports':<8} {'Consensus Day':<15} {'Agreement':<12} {'Verified':<10} {'Official':<10}")
    print("-" * 100)

    # Print rows
    for row in rows:
        verified = "✓" if row['verified_crowd_consensus'] else "-"
        official = "✓" if row['has_official_info'] else "-"

        print(
            f"{row['city_name']:<20} "
            f"{row['address']:<35} "
            f"{row['reports_count']:<8} "
            f"{row['consensus_pickup_day'] or 'N/A':<15} "
            f"{row['agreement_pct'] or 0:.1f}%{'':<8} "
            f"{verified:<10} "
            f"{official:<10}"
        )


def print_low_agreement_addresses(
    conn: sqlite3.Connection,
    city: Optional[str] = None,
    limit: int = 10,
    min_reports: int = 3,
    max_agreement: float = 0.7
):
    """Print addresses with low agreement (disagreements)."""
    cursor = conn.cursor()

    print("\n" + "=" * 100)
    print(f"TOP {limit} ADDRESSES WITH LOW AGREEMENT (< {max_agreement*100:.0f}% agreement, ≥ {min_reports} reports)")
    print("=" * 100)

    city_filter = ""
    params = [min_reports, max_agreement, limit]

    if city:
        city_filter = "AND city_name = ?"
        params = [city, min_reports, max_agreement, limit]

    query = f"""
    SELECT
        city_name,
        house_number || ' ' || street as address,
        reports_count,
        consensus_pickup_day,
        consensus_count,
        ROUND(agreement_ratio * 100, 1) as agreement_pct
    FROM crowd_consensus
    WHERE reports_count >= ?
        AND agreement_ratio < ?
        {city_filter}
    ORDER BY agreement_ratio ASC, reports_count DESC
    LIMIT ?
    """

    if city:
        rows = cursor.execute(query, params).fetchall()
    else:
        rows = cursor.execute(query, [min_reports, max_agreement, limit]).fetchall()

    if not rows:
        print(f"No addresses found with low agreement" + (f" in city: {city}" if city else ""))
        return

    # Print table header
    print(f"\n{'City':<20} {'Address':<40} {'Total Reports':<15} {'Top Pick':<15} {'Top Votes':<12} {'Agreement':<12}")
    print("-" * 100)

    # Print rows
    for row in rows:
        print(
            f"{row['city_name']:<20} "
            f"{row['address']:<40} "
            f"{row['reports_count']:<15} "
            f"{row['consensus_pickup_day'] or 'N/A':<15} "
            f"{row['consensus_count']:<12} "
            f"{row['agreement_pct'] or 0:.1f}%"
        )


def print_disagreement_details(conn: sqlite3.Connection, city: Optional[str] = None):
    """Print detailed breakdown of disagreements by day for low-agreement addresses."""
    cursor = conn.cursor()

    print("\n" + "=" * 100)
    print("DETAILED DISAGREEMENT BREAKDOWN")
    print("=" * 100)

    city_filter = ""
    params = []

    if city:
        city_filter = "AND cc.city_name = ?"
        params = [city]

    # Get low agreement addresses
    query = f"""
    SELECT
        cc.address_id,
        cc.city_name,
        cc.house_number || ' ' || cc.street as address,
        cc.reports_count,
        ROUND(cc.agreement_ratio * 100, 1) as agreement_pct
    FROM crowd_consensus cc
    WHERE cc.reports_count >= 3
        AND cc.agreement_ratio < 0.7
        {city_filter}
    ORDER BY cc.agreement_ratio ASC
    LIMIT 5
    """

    addresses = cursor.execute(query, params).fetchall()

    if not addresses:
        print("No addresses found with significant disagreements" + (f" in city: {city}" if city else ""))
        return

    for addr in addresses:
        print(f"\n{addr['city_name']}: {addr['address']}")
        print(f"  Total reports: {addr['reports_count']}, Agreement: {addr['agreement_pct']}%")
        print(f"  Breakdown by day:")

        # Get report breakdown by day for this address
        day_breakdown = cursor.execute("""
        SELECT
            reported_pickup_day,
            COUNT(*) as count,
            ROUND(COUNT(*) * 100.0 / ?, 1) as percentage
        FROM crowd_reports
        WHERE address_id = ?
        GROUP BY reported_pickup_day
        ORDER BY count DESC
        """, [addr['reports_count'], addr['address_id']]).fetchall()

        for day_row in day_breakdown:
            bar = "█" * int(day_row['percentage'] / 5)  # Scale bar to fit
            print(f"    {day_row['reported_pickup_day']:<12} {day_row['count']:3d} reports ({day_row['percentage']:5.1f}%) {bar}")


def print_city_statistics(conn: sqlite3.Connection, city: Optional[str] = None):
    """Print per-city statistics."""
    cursor = conn.cursor()

    print("\n" + "=" * 100)
    print("PER-CITY STATISTICS")
    print("=" * 100)

    city_filter = ""
    params = []

    if city:
        city_filter = "WHERE city_name = ?"
        params = [city]

    query = f"""
    SELECT
        city_name,
        COUNT(*) as total_addresses,
        SUM(has_official_info) as addresses_with_official_info,
        SUM(verified_crowd_consensus) as addresses_with_verified_consensus,
        SUM(CASE WHEN id IN (SELECT DISTINCT address_id FROM crowd_reports) THEN 1 ELSE 0 END) as addresses_with_reports
    FROM addresses
    {city_filter}
    GROUP BY city_name
    ORDER BY total_addresses DESC
    """

    rows = cursor.execute(query, params).fetchall()

    if not rows:
        print(f"No data found" + (f" for city: {city}" if city else ""))
        return

    # Print table header
    print(f"\n{'City':<20} {'Total Addrs':<15} {'w/ Official':<15} {'w/ Consensus':<15} {'w/ Reports':<15} {'Coverage %':<15}")
    print("-" * 100)

    # Print rows
    for row in rows:
        coverage = (row['addresses_with_reports'] / row['total_addresses'] * 100) if row['total_addresses'] > 0 else 0

        print(
            f"{row['city_name']:<20} "
            f"{row['total_addresses']:<15} "
            f"{row['addresses_with_official_info']:<15} "
            f"{row['addresses_with_verified_consensus']:<15} "
            f"{row['addresses_with_reports']:<15} "
            f"{coverage:.1f}%"
        )

    # Print overall summary if not filtered by city
    if not city:
        totals = cursor.execute("""
        SELECT
            COUNT(*) as total_addresses,
            SUM(has_official_info) as total_official,
            SUM(verified_crowd_consensus) as total_consensus,
            SUM(CASE WHEN id IN (SELECT DISTINCT address_id FROM crowd_reports) THEN 1 ELSE 0 END) as total_with_reports
        FROM addresses
        """).fetchone()

        print("-" * 100)
        coverage = (totals['total_with_reports'] / totals['total_addresses'] * 100) if totals['total_addresses'] > 0 else 0
        print(
            f"{'TOTAL':<20} "
            f"{totals['total_addresses']:<15} "
            f"{totals['total_official']:<15} "
            f"{totals['total_consensus']:<15} "
            f"{totals['total_with_reports']:<15} "
            f"{coverage:.1f}%"
        )


def print_database_overview(conn: sqlite3.Connection):
    """Print high-level database overview."""
    cursor = conn.cursor()

    print("\n" + "=" * 100)
    print("DATABASE OVERVIEW")
    print("=" * 100)

    # Get basic counts
    stats = cursor.execute("""
    SELECT
        (SELECT COUNT(*) FROM addresses) as total_addresses,
        (SELECT COUNT(*) FROM crowd_reports) as total_reports,
        (SELECT COUNT(DISTINCT user_id) FROM crowd_reports) as unique_users,
        (SELECT COUNT(*) FROM addresses WHERE has_official_info = 1) as addresses_with_official,
        (SELECT COUNT(*) FROM addresses WHERE verified_crowd_consensus = 1) as addresses_with_consensus,
        (SELECT COUNT(DISTINCT city_name) FROM addresses) as total_cities
    """).fetchone()

    print(f"\n  Total addresses:                {stats['total_addresses']:>6}")
    print(f"  Total crowd reports:            {stats['total_reports']:>6}")
    print(f"  Unique users reporting:         {stats['unique_users']:>6}")
    print(f"  Cities covered:                 {stats['total_cities']:>6}")
    print(f"  Addresses with official info:  {stats['addresses_with_official']:>6}")
    print(f"  Addresses with consensus:       {stats['addresses_with_consensus']:>6}")

    # Average reports per address
    avg_reports = cursor.execute("""
    SELECT AVG(report_count) as avg
    FROM (
        SELECT COUNT(*) as report_count
        FROM crowd_reports
        GROUP BY address_id
    )
    """).fetchone()

    if avg_reports['avg']:
        print(f"  Avg reports per address:        {avg_reports['avg']:>6.1f}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Admin/debug dashboard for crowd-sourced trash pickup data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show all statistics
  python scripts/admin_inspect_crowd_data.py

  # Filter by city
  python scripts/admin_inspect_crowd_data.py --city "El Centro"

  # Show detailed disagreements
  python scripts/admin_inspect_crowd_data.py --show-disagreements

  # City-specific with disagreements
  python scripts/admin_inspect_crowd_data.py --city "San Diego" --show-disagreements
        """
    )

    parser.add_argument(
        '--city',
        type=str,
        help='Filter results by city name (e.g., "El Centro", "San Diego")'
    )

    parser.add_argument(
        '--show-disagreements',
        action='store_true',
        help='Show detailed breakdown of disagreements for low-agreement addresses'
    )

    parser.add_argument(
        '--db',
        type=Path,
        default=Path(__file__).parent.parent / 'trashpilot.db',
        help='Path to database file (default: ../trashpilot.db)'
    )

    args = parser.parse_args()

    # Connect to database
    try:
        conn = connect_db(args.db)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nPlease run 'python scripts/init_sample_database.py' first to create the database.")
        return 1

    try:
        # Print overview
        print_database_overview(conn)

        # Print hotspots
        print_top_hotspots(conn, city=args.city)

        # Print low agreement addresses
        print_low_agreement_addresses(conn, city=args.city)

        # Print detailed disagreements if requested
        if args.show_disagreements:
            print_disagreement_details(conn, city=args.city)

        # Print city statistics
        print_city_statistics(conn, city=args.city)

        print("\n" + "=" * 100)
        print()

    finally:
        conn.close()

    return 0


if __name__ == '__main__':
    exit(main())
