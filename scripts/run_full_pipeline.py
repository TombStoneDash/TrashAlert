#!/usr/bin/env python3
"""
Full pipeline orchestration script for TrashAlert.
Runs the complete data collection and processing pipeline for cities.
"""

import argparse
import logging
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

from config_utils import load_cities_config, filter_cities, get_city_display_name

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PipelineRunner:
    """Orchestrates the full data pipeline."""

    def __init__(self, base_dir: Path, city_filter: str = None, state_filter: str = None):
        """
        Initialize pipeline runner.

        Args:
            base_dir: Project root directory
            city_filter: City filter for --only flag
            state_filter: State filter for --state flag
        """
        self.base_dir = base_dir
        self.scripts_dir = base_dir / 'scripts'
        self.data_dir = base_dir / 'data'
        self.city_filter = city_filter
        self.state_filter = state_filter

        # Ensure data directory exists
        self.data_dir.mkdir(exist_ok=True)

        # Load cities
        cities = load_cities_config()
        self.cities = filter_cities(cities, only=city_filter, state=state_filter)

        if not self.cities:
            raise ValueError("No cities match the specified filters")

        logger.info(f"Pipeline will process {len(self.cities)} cities:")
        for city in self.cities:
            logger.info(f"  - {get_city_display_name(city)}")

    def run_script(self, script_name: str, description: str, additional_args: list = None) -> bool:
        """
        Run a pipeline script.

        Args:
            script_name: Name of the script to run
            description: Human-readable description
            additional_args: Additional command-line arguments

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"STEP: {description}")
        logger.info(f"{'='*80}")

        script_path = self.scripts_dir / script_name
        cmd = [sys.executable, str(script_path)]

        # Add filter arguments
        if self.city_filter:
            cmd.extend(['--only', self.city_filter])
        elif self.state_filter:
            cmd.extend(['--state', self.state_filter])

        # Add any additional arguments
        if additional_args:
            cmd.extend(additional_args)

        logger.info(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                check=False
            )

            # Print output
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)

            if result.returncode != 0:
                logger.error(f"Script failed with exit code {result.returncode}")
                return False

            logger.info(f"✓ {description} completed successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to run {script_name}: {e}")
            return False

    def run_full_pipeline(self, skip_boundaries: bool = False, skip_subdivisions: bool = False,
                         skip_addresses: bool = False, skip_sampling: bool = False) -> bool:
        """
        Run the full pipeline.

        Args:
            skip_boundaries: Skip boundary fetching
            skip_subdivisions: Skip subdivision building
            skip_addresses: Skip address fetching
            skip_sampling: Skip address sampling

        Returns:
            True if all steps succeeded, False otherwise
        """
        start_time = datetime.now()
        logger.info(f"\n{'#'*80}")
        logger.info(f"# STARTING FULL PIPELINE")
        logger.info(f"# Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"{'#'*80}\n")

        steps_completed = []
        steps_failed = []

        # Step 1: Fetch city boundaries (optional)
        if not skip_boundaries:
            if self.run_script('fetch_city_boundaries.py', 'Fetch city boundaries'):
                steps_completed.append('Fetch boundaries')
            else:
                steps_failed.append('Fetch boundaries')
                logger.warning("Boundary fetching failed, but continuing...")

        # Step 2: Build subdivisions (optional)
        if not skip_subdivisions:
            if self.run_script('build_subdivisions.py', 'Build subdivisions'):
                steps_completed.append('Build subdivisions')
            else:
                steps_failed.append('Build subdivisions')
                logger.warning("Subdivision building failed, but continuing...")

        # Step 3: Fetch addresses from OSM
        if not skip_addresses:
            if self.run_script('fetch_addresses_osm.py', 'Fetch addresses from OSM'):
                steps_completed.append('Fetch addresses')
            else:
                steps_failed.append('Fetch addresses')
                logger.error("Address fetching failed - cannot continue")
                return False

        # Step 4: Sample addresses
        if not skip_sampling:
            if self.run_script('sample_addresses_per_city.py', 'Sample addresses per city'):
                steps_completed.append('Sample addresses')
            else:
                steps_failed.append('Sample addresses')
                logger.error("Address sampling failed")
                return False

        # TODO: Future steps (normalization, DB load) would go here

        # Calculate elapsed time
        end_time = datetime.now()
        elapsed = end_time - start_time

        # Print summary
        self.print_summary(start_time, end_time, elapsed, steps_completed, steps_failed)

        return len(steps_failed) == 0

    def print_summary(self, start_time, end_time, elapsed, steps_completed, steps_failed):
        """Print pipeline summary statistics."""
        logger.info(f"\n{'#'*80}")
        logger.info(f"# PIPELINE SUMMARY")
        logger.info(f"{'#'*80}\n")

        logger.info(f"Started:  {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Finished: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Elapsed:  {elapsed}")

        logger.info(f"\nCities processed: {len(self.cities)}")
        for city in self.cities:
            logger.info(f"  - {get_city_display_name(city)}")

        logger.info(f"\nSteps completed ({len(steps_completed)}):")
        for step in steps_completed:
            logger.info(f"  ✓ {step}")

        if steps_failed:
            logger.info(f"\nSteps failed ({len(steps_failed)}):")
            for step in steps_failed:
                logger.info(f"  ✗ {step}")

        # Show data statistics if available
        self.print_data_statistics()

    def print_data_statistics(self):
        """Print statistics about generated data."""
        logger.info(f"\n{'='*80}")
        logger.info(f"DATA STATISTICS")
        logger.info(f"{'='*80}\n")

        # Check raw addresses
        raw_csv = self.data_dir / 'addresses_osm_raw.csv'
        if raw_csv.exists():
            df = pd.read_csv(raw_csv)
            logger.info(f"Raw addresses: {len(df)} total")

            city_counts = df.groupby('city_name').size().sort_values(ascending=False)
            logger.info("Addresses per city (raw):")
            for city, count in city_counts.items():
                logger.info(f"  {city:30s} {count:6d}")
        else:
            logger.info("Raw addresses file not found")

        # Check sampled addresses
        sampled_csv = self.data_dir / 'addresses_sampled_50_per_city.csv'
        if sampled_csv.exists():
            df = pd.read_csv(sampled_csv)
            logger.info(f"\nSampled addresses: {len(df)} total")

            city_counts = df.groupby('city_name').size().sort_values(ascending=False)
            logger.info("Addresses per city (sampled):")
            for city, count in city_counts.items():
                logger.info(f"  {city:30s} {count:6d}")
        else:
            logger.info("\nSampled addresses file not found")

        # Check boundaries
        boundaries_dir = self.data_dir / 'boundaries'
        if boundaries_dir.exists():
            boundary_files = list(boundaries_dir.glob('*.geojson'))
            logger.info(f"\nBoundary files: {len(boundary_files)}")
        else:
            logger.info("\nBoundaries directory not found")

        # Check subdivisions
        subdivisions_dir = self.data_dir / 'subdivisions'
        if subdivisions_dir.exists():
            subdivision_files = list(subdivisions_dir.glob('*.json'))
            logger.info(f"Subdivision files: {len(subdivision_files)}")
        else:
            logger.info("Subdivisions directory not found")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Run the full TrashAlert data pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run pipeline for all cities
  python run_full_pipeline.py --all

  # Run pipeline for one city
  python run_full_pipeline.py --city "Brawley, California"

  # Run pipeline for all California cities
  python run_full_pipeline.py --state CA

  # Skip certain steps
  python run_full_pipeline.py --city "Brawley" --skip-boundaries --skip-subdivisions
        """
    )

    # City selection
    city_group = parser.add_mutually_exclusive_group(required=True)
    city_group.add_argument(
        '--all',
        action='store_true',
        help='Process all cities in config'
    )
    city_group.add_argument(
        '--city',
        help='Process specific city (e.g., "Brawley, California" or just "Brawley")'
    )
    city_group.add_argument(
        '--state',
        help='Process all cities in state (e.g., "CA" or "California")'
    )

    # Step control
    parser.add_argument(
        '--skip-boundaries',
        action='store_true',
        help='Skip fetching city boundaries'
    )
    parser.add_argument(
        '--skip-subdivisions',
        action='store_true',
        help='Skip building subdivisions'
    )
    parser.add_argument(
        '--skip-addresses',
        action='store_true',
        help='Skip fetching addresses from OSM'
    )
    parser.add_argument(
        '--skip-sampling',
        action='store_true',
        help='Skip address sampling'
    )

    args = parser.parse_args()

    # Determine filters
    city_filter = args.city if args.city else None
    state_filter = args.state if args.state else None

    # Initialize pipeline
    base_dir = Path(__file__).parent.parent

    try:
        pipeline = PipelineRunner(base_dir, city_filter=city_filter, state_filter=state_filter)

        # Run pipeline
        success = pipeline.run_full_pipeline(
            skip_boundaries=args.skip_boundaries,
            skip_subdivisions=args.skip_subdivisions,
            skip_addresses=args.skip_addresses,
            skip_sampling=args.skip_sampling
        )

        if success:
            logger.info("\n✓ Pipeline completed successfully!")
            return 0
        else:
            logger.error("\n✗ Pipeline completed with errors")
            return 1

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit(main())
