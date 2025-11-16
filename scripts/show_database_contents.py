#!/usr/bin/env python3
"""
Display the contents of crowd_reports and crowd_consensus tables.
"""

import sqlite3
from pathlib import Path
from datetime import datetime


def show_crowd_reports(db_path: Path):
    """Display all crowd reports."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n" + "=" * 100)
    print("CROWD_REPORTS TABLE")
    print("=" * 100)

    cursor.execute("""
        SELECT
            cr.id,
            cr.address_id,
            a.house_number || ' ' || a.street || ', ' || a.city_name as address,
            cr.reported_trash_day,
            cr.reported_recycling_day,
            cr.reported_green_day,
            cr.reported_at,
            cr.report_source,
            cr.user_hash
        FROM crowd_reports cr
        JOIN addresses a ON cr.address_id = a.id
        ORDER BY cr.address_id, cr.id
    """)

    reports = cursor.fetchall()

    if not reports:
        print("\nNo reports found")
    else:
        print(f"\nTotal reports: {len(reports)}\n")
        print(f"{'ID':<4} {'Addr':<5} {'Address':<35} {'Trash':<6} {'Recyc':<6} {'Green':<6} {'Source':<8} {'User':<12}")
        print("-" * 100)

        for row in reports:
            (id, addr_id, address, trash, recycling, green, reported_at, source, user_hash) = row
            recycling = recycling or ''
            green = green or ''
            print(f"{id:<4} {addr_id:<5} {address:<35} {trash:<6} {recycling:<6} {green:<6} {source:<8} {user_hash:<12}")

    conn.close()


def show_crowd_consensus(db_path: Path):
    """Display crowd consensus data."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n" + "=" * 100)
    print("CROWD_CONSENSUS TABLE")
    print("=" * 100)

    cursor.execute("""
        SELECT
            cc.address_id,
            a.house_number || ' ' || a.street || ', ' || a.city_name as address,
            cc.trash_day,
            cc.recycling_day,
            cc.green_day,
            cc.reports_count,
            cc.agreement_ratio,
            CASE
                WHEN cc.reports_count >= 3 AND cc.agreement_ratio >= 0.75 THEN 'VERIFIED'
                ELSE 'unverified'
            END as verification_status
        FROM crowd_consensus cc
        JOIN addresses a ON cc.address_id = a.id
        ORDER BY cc.address_id
    """)

    consensus_data = cursor.fetchall()

    if not consensus_data:
        print("\nNo consensus data found")
    else:
        print(f"\nTotal addresses with consensus: {len(consensus_data)}\n")
        print(f"{'Addr':<5} {'Address':<35} {'Trash':<6} {'Recyc':<6} {'Green':<6} {'#Rpts':<6} {'Agree%':<8} {'Status':<12}")
        print("-" * 100)

        verified_count = 0
        for row in consensus_data:
            (addr_id, address, trash, recycling, green, count, agreement, status) = row
            recycling = recycling or ''
            green = green or ''
            agree_pct = f"{agreement*100:.1f}%"

            if status == 'VERIFIED':
                verified_count += 1
                status_display = f"✓ {status}"
            else:
                status_display = f"  {status}"

            print(f"{addr_id:<5} {address:<35} {trash:<6} {recycling:<6} {green:<6} {count:<6} {agree_pct:<8} {status_display:<12}")

        print("\n" + "-" * 100)
        print(f"Summary: {verified_count} VERIFIED addresses (≥3 reports AND ≥75% agreement)")
        print(f"         {len(consensus_data) - verified_count} unverified addresses")

    conn.close()


def show_verification_rule():
    """Display the verification rule."""
    print("\n" + "=" * 100)
    print("VERIFICATION RULE")
    print("=" * 100)
    print("\nAn address is considered VERIFIED when:")
    print("  1. It has at least 3 crowd reports, AND")
    print("  2. The agreement ratio is ≥ 75% (i.e., at least 75% of reports agree on the same day)")
    print("\nExample:")
    print("  - 5 reports, all agree on MON → 100% agreement → VERIFIED ✓")
    print("  - 4 reports, 3 agree on TUE → 75% agreement → VERIFIED ✓")
    print("  - 3 reports, 2 agree on WED → 66.7% agreement → unverified (below 75% threshold)")
    print("  - 2 reports, both agree on THU → 100% agreement → unverified (less than 3 reports)")


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent
    db_path = base_dir / 'trashpilot.db'

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return 1

    show_verification_rule()
    show_crowd_reports(db_path)
    show_crowd_consensus(db_path)

    return 0


if __name__ == '__main__':
    exit(main())
