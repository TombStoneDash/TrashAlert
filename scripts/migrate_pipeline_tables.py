#!/usr/bin/env python3
"""
Database migration to add pipeline tracking tables.

This script adds the following tables:
- pipeline_runs: Track overall pipeline execution
- pipeline_city_status: Track per-city progress

Run this script to upgrade your database schema before using the bulk importer.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, inspect
from app.database import Base
from app.models import PipelineRun, PipelineCityStatus
from utils.config_loader import get_config_loader


def check_table_exists(engine, table_name):
    """Check if a table exists in the database."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def main():
    """Run database migration."""
    print("="*80)
    print("TrashAlert Database Migration - Pipeline Tables")
    print("="*80)

    # Load configuration
    config = get_config_loader()
    logger = config.setup_logging(__name__)

    # Get database path
    db_path = config.get_path('database')
    logger.info(f"Database path: {db_path}")

    # Create engine
    engine = create_engine(f'sqlite:///{db_path}')

    # Check existing tables
    logger.info("\nChecking existing tables...")
    pipeline_runs_exists = check_table_exists(engine, 'pipeline_runs')
    pipeline_city_status_exists = check_table_exists(engine, 'pipeline_city_status')

    if pipeline_runs_exists and pipeline_city_status_exists:
        logger.info("✓ Pipeline tables already exist. No migration needed.")
        return 0

    # Run migration
    logger.info("\nCreating pipeline tables...")

    try:
        # Create all tables defined in Base
        # This will only create tables that don't exist
        Base.metadata.create_all(engine)

        # Verify tables were created
        pipeline_runs_exists = check_table_exists(engine, 'pipeline_runs')
        pipeline_city_status_exists = check_table_exists(engine, 'pipeline_city_status')

        if pipeline_runs_exists and pipeline_city_status_exists:
            logger.info("\n" + "="*80)
            logger.info("Migration completed successfully!")
            logger.info("="*80)
            logger.info("\nNew tables created:")
            logger.info("  ✓ pipeline_runs")
            logger.info("  ✓ pipeline_city_status")
            logger.info("\nYou can now use the bulk import pipeline:")
            logger.info("  python scripts/bulk_import_pipeline.py --all")
            return 0
        else:
            logger.error("\nMigration failed - tables were not created")
            return 1

    except Exception as e:
        logger.error(f"\nMigration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
