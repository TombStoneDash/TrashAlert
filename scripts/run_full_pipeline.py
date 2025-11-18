#!/usr/bin/env python3
"""
Full pipeline orchestration script for TrashAlert.
Runs the complete data collection and processing pipeline for cities.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.config_loader import get_config_loader, get_city_display_name


class PipelineRunner:
    """Orchestrates the full data pipeline."""

    def __init__(self, city_id: str = None, city_name: str = None, state: str = None, all_cities: bool = False):
        """
        Initialize pipeline runner.

        Args:
            city_id: City ID filter (e.g., "ca_el_centro")
            city_name: City name filter (e.g., "El Centro, CA")
            state: State filter (e.g., "CA")
            all_cities: Process all cities
        """
        self.base_dir = Path(__file__).parent.parent
        self.scripts_dir = self.base_dir / 'scripts'

        # Load configuration
        self.config = get_config_loader()
        self.logger = self.config.setup_logging(__name__)

        # Ensure data directories exist
        self.config.get_path('data_root')
        self.config.get_path('raw')
        self.config.get_path('processed')

        # Load and filter cities
        self.cities = self.config.filter_cities(
            city_id=city_id,
            city_name=city_name,
            state=state,
            all_cities=all_cities
        )

        if not self.cities:
            raise ValueError("No cities match the specified filters")

        self.logger.info(f"Pipeline will process {len(self.cities)} cities:")
        for city in self.cities:
            self.logger.info(f"  - {get_city_display_name(city)} (id: {city['city_id']})")

        # Store filter arguments for passing to subcommands
        self.filter_args = self._build_filter_args(city_id, city_name, state, all_cities)

    def _build_filter_args(self, city_id, city_name, state, all_cities):
        """Build filter arguments to pass to subcommands."""
        if all_cities:
            return ['--all']
        elif city_id:
            return ['--city-id', city_id]
        elif city_name:
            return ['--city', city_name]
        elif state:
            return ['--state', state]
        return []

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
        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"STEP: {description}")
        self.logger.info(f"{'='*80}")

        script_path = self.scripts_dir / script_name
        cmd = [sys.executable, str(script_path)]

        # Add filter arguments
        cmd.extend(self.filter_args)

        # Add any additional arguments
        if additional_args:
            cmd.extend(additional_args)

        self.logger.info(f"Running: {' '.join(cmd)}")

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
                self.logger.error(f"Script failed with exit code {result.returncode}")
                return False

            self.logger.info(f"✓ {description} completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to run {script_name}: {e}")
            return False

    def run_full_pipeline(
        self,
        skip_boundaries: bool = False,
        skip_subdivisions: bool = False,
        skip_addresses: bool = False,
        skip_sampling: bool = False,
        skip_normalization: bool = False
    ) -> bool:
        """
        Run the full pipeline.

        Args:
            skip_boundaries: Skip boundary fetching
            skip_subdivisions: Skip subdivision building
            skip_addresses: Skip address fetching
            skip_sampling: Skip address sampling
            skip_normalization: Skip address normalization

        Returns:
            True if all steps succeeded, False otherwise
        """
        start_time = datetime.now()
        self.logger.info(f"\n{'#'*80}")
        self.logger.info(f"# STARTING FULL PIPELINE")
        self.logger.info(f"# Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"{'#'*80}\n")

        steps_completed = []
        steps_failed = []

        # Step 1: Fetch city boundaries (optional)
        if not skip_boundaries:
            if self.run_script('fetch_city_boundaries.py', 'Fetch city boundaries'):
                steps_completed.append('Fetch boundaries')
            else:
                steps_failed.append('Fetch boundaries')
                self.logger.warning("Boundary fetching failed, but continuing...")

        # Step 2: Build subdivisions (optional)
        if not skip_subdivisions:
            if self.run_script('build_subdivisions.py', 'Build subdivisions'):
                steps_completed.append('Build subdivisions')
            else:
                steps_failed.append('Build subdivisions')
                self.logger.warning("Subdivision building failed, but continuing...")

        # Step 3: Fetch addresses from OSM
        if not skip_addresses:
            if self.run_script('fetch_addresses_osm.py', 'Fetch addresses from OSM'):
                steps_completed.append('Fetch addresses')
            else:
                steps_failed.append('Fetch addresses')
                self.logger.error("Address fetching failed - cannot continue")
                return False

        # Step 4: Sample addresses
        if not skip_sampling:
            if self.run_script('sample_addresses_per_city.py', 'Sample addresses per city'):
                steps_completed.append('Sample addresses')
            else:
                steps_failed.append('Sample addresses')
                self.logger.error("Address sampling failed")
                return False

        # Step 5: Normalize addresses
        if not skip_normalization:
            if self.run_script('normalize_addresses.py', 'Normalize and deduplicate addresses'):
                steps_completed.append('Normalize addresses')
            else:
                steps_failed.append('Normalize addresses')
                self.logger.error("Address normalization failed")
                return False

        # Calculate elapsed time
        end_time = datetime.now()
        elapsed = end_time - start_time

        # Print summary
        self.print_summary(start_time, end_time, elapsed, steps_completed, steps_failed)

        return len(steps_failed) == 0

    def print_summary(self, start_time, end_time, elapsed, steps_completed, steps_failed):
        """Print pipeline summary statistics."""
        self.logger.info(f"\n{'#'*80}")
        self.logger.info(f"# PIPELINE SUMMARY")
        self.logger.info(f"{'#'*80}\n")

        self.logger.info(f"Started:  {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"Finished: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"Elapsed:  {elapsed}")

        self.logger.info(f"\nCities processed: {len(self.cities)}")
        for city in self.cities:
            self.logger.info(f"  - {get_city_display_name(city)} (id: {city['city_id']})")

        self.logger.info(f"\nSteps completed ({len(steps_completed)}):")
        for step in steps_completed:
            self.logger.info(f"  ✓ {step}")

        if steps_failed:
            self.logger.info(f"\nSteps failed ({len(steps_failed)}):")
            for step in steps_failed:
                self.logger.info(f"  ✗ {step}")

        # Show data statistics if available
        self.print_data_statistics()

    def print_data_statistics(self):
        """Print statistics about generated data."""
        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"DATA STATISTICS")
        self.logger.info(f"{'='*80}\n")

        # Check raw addresses
        raw_csv = self.config.get_path('addresses_osm_raw', create_if_missing=False)
        if raw_csv.exists():
            df = pd.read_csv(raw_csv)
            self.logger.info(f"Raw addresses: {len(df)} total")

            city_counts = df.groupby('city_name').size().sort_values(ascending=False)
            self.logger.info("Addresses per city (raw):")
            for city, count in city_counts.items():
                self.logger.info(f"  {city:30s} {count:6d}")
        else:
            self.logger.info("Raw addresses file not found")

        # Check sampled addresses
        sampled_csv = self.config.get_path('addresses_sampled', create_if_missing=False)
        if sampled_csv.exists():
            df = pd.read_csv(sampled_csv)
            self.logger.info(f"\nSampled addresses: {len(df)} total")

            city_counts = df.groupby('city_name').size().sort_values(ascending=False)
            self.logger.info("Addresses per city (sampled):")
            for city, count in city_counts.items():
                self.logger.info(f"  {city:30s} {count:6d}")
        else:
            self.logger.info("\nSampled addresses file not found")

        # Check normalized addresses
        normalized_csv = self.config.get_path('addresses_normalized_csv', create_if_missing=False)
        if normalized_csv.exists():
            df = pd.read_csv(normalized_csv)
            self.logger.info(f"\nNormalized addresses: {len(df)} total")

            city_counts = df.groupby('city_name').size().sort_values(ascending=False)
            self.logger.info("Addresses per city (normalized):")
            for city, count in city_counts.items():
                self.logger.info(f"  {city:30s} {count:6d}")
        else:
            self.logger.info("\nNormalized addresses file not found")

        # Check boundaries
        boundaries_dir = self.config.get_path('boundaries', create_if_missing=False)
        if boundaries_dir.exists():
            boundary_files = list(boundaries_dir.glob('*.geojson'))
            self.logger.info(f"\nBoundary files: {len(boundary_files)}")
        else:
            self.logger.info("\nBoundaries directory not found")

        # Check subdivisions
        subdivisions_dir = self.config.get_path('subdivisions', create_if_missing=False)
        if subdivisions_dir.exists():
            subdivision_files = list(subdivisions_dir.glob('*.json'))
            self.logger.info(f"Subdivision files: {len(subdivision_files)}")
        else:
            self.logger.info("Subdivisions directory not found")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Run the full TrashAlert data pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run pipeline for all cities
  python run_full_pipeline.py --all

  # Run pipeline for one city by ID
  python run_full_pipeline.py --city-id ca_el_centro

  # Run pipeline for one city by name
  python run_full_pipeline.py --city "Brawley, California"

  # Run pipeline for all California cities
  python run_full_pipeline.py --state CA

  # Skip certain steps
  python run_full_pipeline.py --city-id ca_brawley --skip-boundaries --skip-subdivisions
        """
    )

    # City selection (mutually exclusive)
    city_group = parser.add_mutually_exclusive_group(required=True)
    city_group.add_argument(
        '--all',
        action='store_true',
        help='Process all cities in config'
    )
    city_group.add_argument(
        '--city-id',
        help='Process specific city by ID (e.g., "ca_el_centro")'
    )
    city_group.add_argument(
        '--city',
        help='Process specific city by name (e.g., "Brawley, California" or just "Brawley")'
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
    parser.add_argument(
        '--skip-normalization',
        action='store_true',
        help='Skip address normalization'
    )

    args = parser.parse_args()

    try:
        # Initialize pipeline
        pipeline = PipelineRunner(
            city_id=args.city_id,
            city_name=args.city,
            state=args.state,
            all_cities=args.all
        )

        # Run pipeline
        success = pipeline.run_full_pipeline(
            skip_boundaries=args.skip_boundaries,
            skip_subdivisions=args.skip_subdivisions,
            skip_addresses=args.skip_addresses,
            skip_sampling=args.skip_sampling,
            skip_normalization=args.skip_normalization
        )

        if success:
            pipeline.logger.info("\n✓ Pipeline completed successfully!")
            return 0
        else:
            pipeline.logger.error("\n✗ Pipeline completed with errors")
            return 1

    except Exception as e:
        print(f"Pipeline failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
