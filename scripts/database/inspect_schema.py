#!/usr/bin/env python3
"""
Inspect the TrashAlert database schema.
Displays all tables, their columns, and column details.
"""

import sqlite3
import logging
from pathlib import Path
from typing import List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_tables(cursor: sqlite3.Cursor) -> List[str]:
    """Get all table names from the database."""
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table'
        ORDER BY name
    """)
    return [row[0] for row in cursor.fetchall()]


def get_table_info(cursor: sqlite3.Cursor, table_name: str) -> List[Tuple]:
    """Get column information for a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return cursor.fetchall()


def get_foreign_keys(cursor: sqlite3.Cursor, table_name: str) -> List[Tuple]:
    """Get foreign key information for a table."""
    cursor.execute(f"PRAGMA foreign_key_list({table_name})")
    return cursor.fetchall()


def get_indexes(cursor: sqlite3.Cursor, table_name: str) -> List[str]:
    """Get indexes for a table."""
    cursor.execute(f"PRAGMA index_list({table_name})")
    return [row[1] for row in cursor.fetchall()]


def get_row_count(cursor: sqlite3.Cursor, table_name: str) -> int:
    """Get the number of rows in a table."""
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    return cursor.fetchone()[0]


def print_table_schema(cursor: sqlite3.Cursor, table_name: str, show_counts: bool = True):
    """Print detailed schema information for a table."""
    print(f"\n{'=' * 80}")
    print(f"TABLE: {table_name}")
    print('=' * 80)

    # Get column information
    columns = get_table_info(cursor, table_name)

    print("\nCOLUMNS:")
    print(f"  {'Name':<25} {'Type':<15} {'NotNull':<10} {'Default':<15} {'PK':<5}")
    print(f"  {'-' * 25} {'-' * 15} {'-' * 10} {'-' * 15} {'-' * 5}")

    for col in columns:
        cid, name, col_type, not_null, default_val, is_pk = col
        not_null_str = 'YES' if not_null else 'NO'
        default_str = str(default_val) if default_val is not None else ''
        pk_str = 'YES' if is_pk else ''
        print(f"  {name:<25} {col_type:<15} {not_null_str:<10} {default_str:<15} {pk_str:<5}")

    # Get foreign keys
    foreign_keys = get_foreign_keys(cursor, table_name)
    if foreign_keys:
        print("\nFOREIGN KEYS:")
        for fk in foreign_keys:
            fk_id, seq, ref_table, from_col, to_col, on_update, on_delete, match = fk
            print(f"  {from_col} -> {ref_table}({to_col})")
            if on_delete != 'NO ACTION':
                print(f"    ON DELETE: {on_delete}")

    # Get indexes
    indexes = get_indexes(cursor, table_name)
    if indexes:
        print("\nINDEXES:")
        for idx in indexes:
            print(f"  - {idx}")

    # Get row count
    if show_counts:
        try:
            count = get_row_count(cursor, table_name)
            print(f"\nROW COUNT: {count:,}")
        except Exception as e:
            print(f"\nROW COUNT: Unable to count ({e})")


def inspect_database(db_path: Path, show_counts: bool = True):
    """Inspect the database schema and print all information."""
    if not db_path.exists():
        logger.error(f"Database not found at {db_path}")
        logger.info("Run 'python scripts/database/init_db.py' to create the database")
        return 1

    logger.info(f"Inspecting database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Get all tables
        tables = get_tables(cursor)

        print("\n" + "=" * 80)
        print("DATABASE SCHEMA INSPECTION")
        print("=" * 80)
        print(f"\nDatabase: {db_path}")
        print(f"Total Tables: {len(tables)}")
        print(f"\nTable List: {', '.join(tables)}")

        # Print detailed info for each table
        for table in tables:
            print_table_schema(cursor, table, show_counts=show_counts)

        # Print summary
        print("\n" + "=" * 80)
        print("SCHEMA SUMMARY")
        print("=" * 80)

        if show_counts:
            print("\nTable Row Counts:")
            for table in tables:
                try:
                    count = get_row_count(cursor, table)
                    print(f"  {table:<30} {count:>10,} rows")
                except Exception as e:
                    print(f"  {table:<30} {'ERROR':>10}")

        # Get database file size
        file_size = db_path.stat().st_size
        size_mb = file_size / (1024 * 1024)
        print(f"\nDatabase Size: {size_mb:.2f} MB ({file_size:,} bytes)")

    except Exception as e:
        logger.error(f"Error inspecting database: {e}")
        return 1
    finally:
        conn.close()

    return 0


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Inspect TrashAlert database schema',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--db-path',
        type=Path,
        help='Path to the database file (default: trashalert.db in project root)'
    )
    parser.add_argument(
        '--no-counts',
        action='store_true',
        help='Skip row count queries (faster for large databases)'
    )

    args = parser.parse_args()

    # Determine database path
    if args.db_path:
        db_path = args.db_path
    else:
        base_dir = Path(__file__).parent.parent.parent
        db_path = base_dir / 'trashalert.db'

    return inspect_database(db_path, show_counts=not args.no_counts)


if __name__ == '__main__':
    exit(main())
