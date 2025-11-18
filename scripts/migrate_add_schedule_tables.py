#!/usr/bin/env python3
"""
Migration script to add schedule-related tables to the database.

This script adds:
- schedules: Official trash collection schedules
- schedule_exceptions: Holiday exceptions and special pickup dates
- source_metadata: Metadata about data sources

Usage:
    python scripts/migrate_add_schedule_tables.py
"""
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from app.database import SQLALCHEMY_DATABASE_URL
from app.models import Base, Schedule, ScheduleException, SourceMetadata


def run_migration():
    """Create new schedule-related tables."""
    print("=" * 60)
    print("Schedule Tables Migration")
    print("=" * 60)

    # Create engine
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False}  # SQLite only
    )

    print(f"\nConnecting to database: {SQLALCHEMY_DATABASE_URL}")

    # Create only the new tables (won't affect existing tables)
    print("\nCreating new tables:")
    print("  - schedules")
    print("  - schedule_exceptions")
    print("  - source_metadata")

    try:
        # This will create tables that don't exist yet
        Base.metadata.create_all(bind=engine, checkfirst=True)
        print("\n✓ Migration completed successfully!")

        # Verify tables were created
        from sqlalchemy import inspect
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()

        print("\nExisting tables in database:")
        for table in sorted(existing_tables):
            print(f"  - {table}")

        return True

    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
