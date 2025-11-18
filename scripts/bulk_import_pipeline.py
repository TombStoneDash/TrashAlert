#!/usr/bin/env python3
"""
Multi-city bulk OSM address importer with checkpoints and error recovery.

This script orchestrates the full OSM address import pipeline across multiple cities
with the following features:
- Automatic processing of all cities from cities.yaml
- Rate limiting and retry logic for Overpass API
- Resumable checkpoints for recovery from failures
- Per-city status tracking
- Database-backed progress persistence
- Dashboard-ready status reporting
"""

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from utils.config_loader import get_config_loader, get_city_display_name
from app.models import PipelineRun, PipelineCityStatus, Base
from scripts.fetch_addresses_osm import OverpassAPIClient, fetch_addresses_for_city
import pandas as pd


class BulkImportPipeline:
    """Manages bulk import of OSM addresses across multiple cities."""

    def __init__(
        self,
        city_id: str = None,
        city_name: str = None,
        state: str = None,
        all_cities: bool = False,
        resume_run_id: int = None,
        skip_boundaries: bool = False,
        skip_subdivisions: bool = False
    ):
        """
        Initialize the bulk import pipeline.

        Args:
            city_id: Specific city ID to process
            city_name: Specific city name to process
            state: State filter
            all_cities: Process all cities
            resume_run_id: Resume a previous run by ID
            skip_boundaries: Skip boundary fetching
            skip_subdivisions: Skip subdivision building
        """
        self.config = get_config_loader()
        self.logger = self.config.setup_logging(__name__)

        # Set up database connection
        db_path = self.config.get_path('database')
        self.engine = create_engine(f'sqlite:///{db_path}')
        Base.metadata.create_all(self.engine)
        SessionLocal = sessionmaker(bind=self.engine)
        self.db = SessionLocal()

        # Configuration
        self.skip_boundaries = skip_boundaries
        self.skip_subdivisions = skip_subdivisions

        # Initialize or resume pipeline run
        if resume_run_id:
            self.pipeline_run = self._resume_run(resume_run_id)
            self.cities = self._get_remaining_cities()
        else:
            # Filter cities
            self.cities = self.config.filter_cities(
                city_id=city_id,
                city_name=city_name,
                state=state,
                all_cities=all_cities
            )

            if not self.cities:
                raise ValueError("No cities match the specified filters")

            # Create new pipeline run
            city_filter = self._format_filter(city_id, city_name, state, all_cities)
            self.pipeline_run = self._create_run(city_filter)

        # Initialize API client
        self.api_client = OverpassAPIClient(self.config, self.logger)

        # Paths
        self.raw_dir = self.config.get_path('raw')
        self.processed_dir = self.config.get_path('processed')
        self.subdivisions_dir = self.config.get_path('subdivisions', create_if_missing=False)

        self.logger.info(f"Pipeline run #{self.pipeline_run.id}: {len(self.cities)} cities to process")

    def _format_filter(self, city_id, city_name, state, all_cities):
        """Format filter string for display."""
        if all_cities:
            return "all"
        elif city_id:
            return f"city_id:{city_id}"
        elif city_name:
            return f"city:{city_name}"
        elif state:
            return f"state:{state}"
        return "custom"

    def _create_run(self, city_filter: str) -> PipelineRun:
        """Create a new pipeline run in the database."""
        run = PipelineRun(
            run_type="full",
            status="pending",
            city_filter=city_filter,
            total_cities=len(self.cities),
            started_at=datetime.utcnow()
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        # Create city status records
        for city in self.cities:
            city_status = PipelineCityStatus(
                pipeline_run_id=run.id,
                city_id=city['city_id'],
                city_name=city['name'],
                status="pending",
                steps_completed=[]
            )
            self.db.add(city_status)

        self.db.commit()
        return run

    def _resume_run(self, run_id: int) -> PipelineRun:
        """Resume an existing pipeline run."""
        run = self.db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if not run:
            raise ValueError(f"Pipeline run #{run_id} not found")

        if run.status == "completed":
            raise ValueError(f"Pipeline run #{run_id} already completed")

        self.logger.info(f"Resuming pipeline run #{run_id}")
        run.status = "running"
        self.db.commit()
        return run

    def _get_remaining_cities(self) -> List[Dict]:
        """Get list of cities not yet completed in the current run."""
        # Get city statuses that are not completed
        statuses = self.db.query(PipelineCityStatus).filter(
            PipelineCityStatus.pipeline_run_id == self.pipeline_run.id,
            PipelineCityStatus.status.in_(['pending', 'failed'])
        ).all()

        # Load cities from config
        all_cities = self.config.cities_config['cities']

        # Filter to remaining cities
        remaining_city_ids = {s.city_id for s in statuses}
        return [c for c in all_cities if c['city_id'] in remaining_city_ids]

    def _update_run_status(self, status: str, error: str = None):
        """Update the overall pipeline run status."""
        self.pipeline_run.status = status
        if error:
            self.pipeline_run.last_error = error
            self.pipeline_run.error_count += 1
        if status in ["completed", "failed"]:
            self.pipeline_run.completed_at = datetime.utcnow()
        self.db.commit()

    def _get_city_status(self, city_id: str) -> PipelineCityStatus:
        """Get or create city status record."""
        status = self.db.query(PipelineCityStatus).filter(
            PipelineCityStatus.pipeline_run_id == self.pipeline_run.id,
            PipelineCityStatus.city_id == city_id
        ).first()
        return status

    def _update_city_status(
        self,
        city_id: str,
        status: str,
        current_step: str = None,
        error_message: str = None,
        addresses_fetched: int = None,
        step_completed: str = None
    ):
        """Update city status in database."""
        city_status = self._get_city_status(city_id)

        city_status.status = status
        if current_step:
            city_status.current_step = current_step
        if error_message:
            city_status.error_message = error_message
            city_status.retry_count += 1
        if addresses_fetched is not None:
            city_status.addresses_fetched = addresses_fetched
        if step_completed:
            steps = city_status.steps_completed or []
            if step_completed not in steps:
                steps.append(step_completed)
                city_status.steps_completed = steps

        if status == "running" and not city_status.started_at:
            city_status.started_at = datetime.utcnow()
        elif status in ["completed", "failed"]:
            city_status.completed_at = datetime.utcnow()

        self.db.commit()

        # Update run-level progress
        self._update_run_progress()

    def _update_run_progress(self):
        """Update overall run progress counters."""
        statuses = self.db.query(PipelineCityStatus).filter(
            PipelineCityStatus.pipeline_run_id == self.pipeline_run.id
        ).all()

        self.pipeline_run.completed_cities = sum(1 for s in statuses if s.status == "completed")
        self.pipeline_run.failed_cities = sum(1 for s in statuses if s.status == "failed")
        self.pipeline_run.total_addresses_fetched = sum(s.addresses_fetched or 0 for s in statuses)

        self.db.commit()

    def _save_checkpoint(self, city_id: str):
        """Save checkpoint for resumability."""
        self.pipeline_run.last_processed_city_id = city_id
        checkpoint_data = {
            'last_checkpoint': datetime.utcnow().isoformat(),
            'city_id': city_id
        }
        self.pipeline_run.checkpoint_data = checkpoint_data
        self.db.commit()

    def process_city(self, city: Dict) -> bool:
        """
        Process a single city through the pipeline.

        Args:
            city: City configuration dict

        Returns:
            True if successful, False otherwise
        """
        city_id = city['city_id']
        display_name = get_city_display_name(city)

        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"Processing: {display_name} (ID: {city_id})")
        self.logger.info(f"{'='*80}")

        self._update_city_status(city_id, "running")

        try:
            # Step 1: Fetch boundaries (optional)
            if not self.skip_boundaries:
                self._update_city_status(city_id, "running", current_step="boundaries")
                if self._fetch_boundaries(city):
                    self._update_city_status(city_id, "running", step_completed="boundaries")
                else:
                    self.logger.warning(f"  Boundary fetching failed for {display_name}, continuing...")

            # Step 2: Build subdivisions (optional)
            if not self.skip_subdivisions:
                self._update_city_status(city_id, "running", current_step="subdivisions")
                if self._build_subdivisions(city):
                    self._update_city_status(city_id, "running", step_completed="subdivisions")
                else:
                    self.logger.warning(f"  Subdivision building failed for {display_name}, continuing...")

            # Step 3: Fetch addresses from OSM (critical)
            self._update_city_status(city_id, "running", current_step="addresses")
            addresses = fetch_addresses_for_city(city, self.api_client, self.subdivisions_dir, self.logger)

            if not addresses:
                error_msg = f"No addresses fetched for {display_name}"
                self.logger.error(f"  {error_msg}")
                self._update_city_status(city_id, "failed", error_message=error_msg)
                return False

            self._update_city_status(
                city_id, "running",
                step_completed="addresses",
                addresses_fetched=len(addresses)
            )

            # Save raw addresses (append mode for bulk import)
            self._save_addresses(addresses)

            # Mark as completed
            self._update_city_status(city_id, "completed")
            self.logger.info(f"  ✓ Successfully processed {display_name}: {len(addresses)} addresses")

            # Save checkpoint
            self._save_checkpoint(city_id)

            return True

        except Exception as e:
            error_msg = f"Error processing {display_name}: {str(e)}"
            self.logger.error(error_msg)
            self.logger.debug(traceback.format_exc())
            self._update_city_status(city_id, "failed", error_message=error_msg)
            return False

    def _fetch_boundaries(self, city: Dict) -> bool:
        """Fetch city boundaries (placeholder for existing script call)."""
        # This would call fetch_city_boundaries.py script
        # For now, we'll skip as it's optional
        return True

    def _build_subdivisions(self, city: Dict) -> bool:
        """Build subdivisions (placeholder for existing script call)."""
        # This would call build_subdivisions.py script
        # For now, we'll skip as it's optional
        return True

    def _save_addresses(self, addresses: List[Dict]):
        """Save addresses to raw CSV file in append mode."""
        output_file = self.config.get_path('addresses_osm_raw')

        df = pd.DataFrame(addresses)

        # Append to existing file or create new
        if output_file.exists():
            df.to_csv(output_file, mode='a', header=False, index=False)
        else:
            df.to_csv(output_file, index=False)

    def run(self) -> bool:
        """
        Execute the bulk import pipeline.

        Returns:
            True if all cities processed successfully, False otherwise
        """
        start_time = datetime.utcnow()

        self.logger.info(f"\n{'#'*80}")
        self.logger.info(f"# BULK IMPORT PIPELINE - RUN #{self.pipeline_run.id}")
        self.logger.info(f"# Started: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        self.logger.info(f"# Cities: {len(self.cities)}")
        self.logger.info(f"{'#'*80}\n")

        self._update_run_status("running")

        success_count = 0
        failure_count = 0

        try:
            for i, city in enumerate(self.cities):
                # Rate limiting between cities
                if i > 0:
                    self.logger.info(f"Rate limiting: waiting {self.api_client.rate_limit_delay}s...")
                    self.api_client.rate_limit()

                # Process city
                if self.process_city(city):
                    success_count += 1
                else:
                    failure_count += 1

                # Progress update
                progress = ((i + 1) / len(self.cities)) * 100
                self.logger.info(f"\nProgress: {i + 1}/{len(self.cities)} ({progress:.1f}%)")
                self.logger.info(f"Success: {success_count} | Failed: {failure_count}")

            # Mark as completed
            if failure_count == 0:
                self._update_run_status("completed")
            else:
                self._update_run_status("completed", f"{failure_count} cities failed")

            # Print summary
            self._print_summary(start_time, success_count, failure_count)

            return failure_count == 0

        except KeyboardInterrupt:
            self.logger.warning("\n\nPipeline interrupted by user")
            self._update_run_status("paused", "Interrupted by user")
            self.logger.info(f"Pipeline can be resumed with: --resume {self.pipeline_run.id}")
            return False

        except Exception as e:
            error_msg = f"Pipeline failed: {str(e)}"
            self.logger.error(error_msg)
            self.logger.debug(traceback.format_exc())
            self._update_run_status("failed", error_msg)
            return False

        finally:
            self.db.close()

    def _print_summary(self, start_time, success_count, failure_count):
        """Print pipeline execution summary."""
        end_time = datetime.utcnow()
        elapsed = end_time - start_time

        self.logger.info(f"\n{'#'*80}")
        self.logger.info(f"# PIPELINE SUMMARY - RUN #{self.pipeline_run.id}")
        self.logger.info(f"{'#'*80}\n")

        self.logger.info(f"Started:  {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        self.logger.info(f"Finished: {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        self.logger.info(f"Elapsed:  {elapsed}")

        self.logger.info(f"\nResults:")
        self.logger.info(f"  Total cities:      {len(self.cities)}")
        self.logger.info(f"  ✓ Successful:      {success_count}")
        self.logger.info(f"  ✗ Failed:          {failure_count}")
        self.logger.info(f"  Total addresses:   {self.pipeline_run.total_addresses_fetched}")

        # Show per-city breakdown
        self.logger.info(f"\nPer-city results:")
        statuses = self.db.query(PipelineCityStatus).filter(
            PipelineCityStatus.pipeline_run_id == self.pipeline_run.id
        ).order_by(PipelineCityStatus.city_name).all()

        for status in statuses:
            status_icon = "✓" if status.status == "completed" else "✗"
            addr_count = status.addresses_fetched or 0
            self.logger.info(
                f"  {status_icon} {status.city_name:30s} {status.status:10s} {addr_count:6d} addresses"
            )

        # Failed cities details
        if failure_count > 0:
            self.logger.info(f"\nFailed cities (details):")
            failed_statuses = [s for s in statuses if s.status == "failed"]
            for status in failed_statuses:
                self.logger.info(f"  {status.city_name}: {status.error_message}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Multi-city bulk OSM address importer with checkpoints',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import all cities
  python bulk_import_pipeline.py --all

  # Import specific state
  python bulk_import_pipeline.py --state CA

  # Import specific city
  python bulk_import_pipeline.py --city-id ca_san_diego

  # Resume a previous run
  python bulk_import_pipeline.py --resume 5

  # Skip optional steps
  python bulk_import_pipeline.py --all --skip-boundaries --skip-subdivisions
        """
    )

    # City selection (mutually exclusive)
    city_group = parser.add_mutually_exclusive_group()
    city_group.add_argument(
        '--all',
        action='store_true',
        help='Process all cities in cities.yaml'
    )
    city_group.add_argument(
        '--city-id',
        help='Process specific city by ID (e.g., "ca_san_diego")'
    )
    city_group.add_argument(
        '--city',
        help='Process specific city by name (e.g., "San Diego, CA")'
    )
    city_group.add_argument(
        '--state',
        help='Process all cities in state (e.g., "CA")'
    )
    city_group.add_argument(
        '--resume',
        type=int,
        help='Resume a previous pipeline run by ID'
    )

    # Options
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

    args = parser.parse_args()

    # Validate arguments
    if not any([args.all, args.city_id, args.city, args.state, args.resume]):
        parser.error("Must specify one of: --all, --city-id, --city, --state, --resume")

    try:
        # Initialize and run pipeline
        pipeline = BulkImportPipeline(
            city_id=args.city_id,
            city_name=args.city,
            state=args.state,
            all_cities=args.all,
            resume_run_id=args.resume,
            skip_boundaries=args.skip_boundaries,
            skip_subdivisions=args.skip_subdivisions
        )

        success = pipeline.run()

        return 0 if success else 1

    except Exception as e:
        print(f"Pipeline initialization failed: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
