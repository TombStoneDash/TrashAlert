#!/usr/bin/env python3
"""
Main script to run the multi-agent data validation pipeline.

Usage:
    python run_pipeline.py [options]

Examples:
    # Run with default settings
    python run_pipeline.py

    # Dry run (don't apply corrections)
    python run_pipeline.py --dry-run

    # Run for specific city
    python run_pipeline.py --city-id 1

    # Limit number of records
    python run_pipeline.py --limit 100

    # Don't auto-apply corrections (only detect issues)
    python run_pipeline.py --no-auto-apply
"""

import sys
import argparse
import logging
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import SessionLocal
from app.logging_config import configure_logging
from scripts.validation.pipeline import ValidationPipeline, PipelineConfig


def setup_logging(log_level: str = "INFO") -> None:
    """Set up logging for the pipeline."""
    # Use existing logging config
    configure_logging()

    # Set log level
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')

    logging.getLogger().setLevel(numeric_level)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run the multi-agent data validation pipeline"
    )

    parser.add_argument(
        '--city-id',
        type=int,
        help='Filter by specific city ID'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of records to process'
    )

    parser.add_argument(
        '--no-exceptions',
        action='store_true',
        help='Skip loading schedule exceptions'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without committing changes to database'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Number of updates per transaction (default: 100)'
    )

    parser.add_argument(
        '--no-auto-apply',
        action='store_true',
        help='Do not automatically apply corrections'
    )

    parser.add_argument(
        '--no-report',
        action='store_true',
        help='Do not save validation report'
    )

    parser.add_argument(
        '--report-dir',
        type=str,
        default='data/validation_reports',
        help='Directory to save validation reports (default: data/validation_reports)'
    )

    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Logging level (default: INFO)'
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    # Parse arguments
    args = parse_args()

    # Set up logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)

    logger.info("Starting validation pipeline")

    # Create pipeline configuration
    config = PipelineConfig(
        city_id=args.city_id,
        limit=args.limit,
        include_exceptions=not args.no_exceptions,
        dry_run=args.dry_run,
        batch_size=args.batch_size,
        auto_apply_corrections=not args.no_auto_apply,
        save_report=not args.no_report,
        report_output_dir=args.report_dir
    )

    # Log configuration
    logger.info("Pipeline Configuration:")
    logger.info(f"  City ID: {config.city_id or 'All'}")
    logger.info(f"  Limit: {config.limit or 'No limit'}")
    logger.info(f"  Include Exceptions: {config.include_exceptions}")
    logger.info(f"  Dry Run: {config.dry_run}")
    logger.info(f"  Batch Size: {config.batch_size}")
    logger.info(f"  Auto Apply Corrections: {config.auto_apply_corrections}")
    logger.info(f"  Save Report: {config.save_report}")

    # Create database session
    db = SessionLocal()

    try:
        # Create and run pipeline
        pipeline = ValidationPipeline(config)
        result = pipeline.run(db)

        # Exit with appropriate code
        if result.status.value == "success":
            logger.info("Pipeline completed successfully")
            sys.exit(0)
        else:
            logger.error("Pipeline failed")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user")
        sys.exit(130)

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    main()
