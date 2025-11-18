"""
Background job scheduler for TrashAlert.

This module uses APScheduler to run background jobs:
- OSM pipeline (nightly)
- Crowd consensus refresh (daily)
- Zone/address linkage recalculation (weekly)

All jobs log metrics to logs/cron.log.
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

# Add project root to Python path for importing scripts
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# Configure cron-specific logger
def setup_cron_logger():
    """Set up dedicated logger for cron jobs."""
    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)

    cron_log_file = logs_dir / "cron.log"

    # Create logger
    logger = logging.getLogger("cron")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # Rotating file handler (10MB max, 5 backups)
    file_handler = RotatingFileHandler(
        cron_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)

    # Console handler for debugging
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


cron_logger = setup_cron_logger()


class BackgroundJobScheduler:
    """Manages scheduled background jobs for TrashAlert."""

    def __init__(self, db_path: str = None):
        """Initialize the scheduler.

        Args:
            db_path: Path to SQLite database. Defaults to ./data/trashalert.db
        """
        self.scheduler = BackgroundScheduler(
            job_defaults={
                'coalesce': True,  # Combine missed runs
                'max_instances': 1,  # One instance per job at a time
                'misfire_grace_time': 300  # 5 minutes grace period
            }
        )

        # Database path
        self.db_path = db_path or str(project_root / "data" / "trashalert.db")

        # Add event listeners for logging
        self.scheduler.add_listener(
            self._job_executed_listener,
            EVENT_JOB_EXECUTED
        )
        self.scheduler.add_listener(
            self._job_error_listener,
            EVENT_JOB_ERROR
        )

        cron_logger.info("BackgroundJobScheduler initialized")

    def _job_executed_listener(self, event):
        """Log successful job execution."""
        cron_logger.info(
            f"Job '{event.job_id}' executed successfully in "
            f"{event.retval.get('duration_seconds', 'N/A')}s"
        )

    def _job_error_listener(self, event):
        """Log job execution errors."""
        cron_logger.error(
            f"Job '{event.job_id}' failed with exception: {event.exception}",
            exc_info=event.exception
        )

    def run_osm_pipeline(self):
        """Run the OSM address fetching pipeline.

        This job fetches address data from OpenStreetMap for all enabled cities.
        Runs nightly at 2:00 AM.
        """
        start_time = datetime.now()
        cron_logger.info("=== Starting OSM Pipeline Job ===")

        try:
            # Import the OSM fetch script
            from scripts import fetch_addresses_osm

            # Run for all cities
            cron_logger.info("Fetching addresses from OpenStreetMap for all cities")

            # Call the main function with --all flag
            original_argv = sys.argv.copy()
            sys.argv = ['fetch_addresses_osm.py', '--all']

            try:
                fetch_addresses_osm.main()
                success = True
            except Exception as e:
                cron_logger.error(f"OSM fetch failed: {e}", exc_info=True)
                success = False
            finally:
                sys.argv = original_argv

            duration = (datetime.now() - start_time).total_seconds()

            if success:
                cron_logger.info(
                    f"OSM Pipeline completed successfully. "
                    f"Duration: {duration:.2f}s"
                )
            else:
                cron_logger.error(
                    f"OSM Pipeline failed. Duration: {duration:.2f}s"
                )

            return {
                "job": "osm_pipeline",
                "success": success,
                "duration_seconds": duration,
                "timestamp": start_time.isoformat()
            }

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            cron_logger.error(
                f"OSM Pipeline job crashed: {e}. Duration: {duration:.2f}s",
                exc_info=True
            )
            return {
                "job": "osm_pipeline",
                "success": False,
                "duration_seconds": duration,
                "error": str(e),
                "timestamp": start_time.isoformat()
            }

    def run_crowd_consensus_refresh(self):
        """Refresh crowd consensus for all addresses.

        This job recalculates consensus data based on crowd reports.
        Runs daily at 3:00 AM.
        """
        start_time = datetime.now()
        cron_logger.info("=== Starting Crowd Consensus Refresh Job ===")

        try:
            # Import the consensus update script
            from scripts.processing import update_crowd_consensus

            cron_logger.info("Recalculating crowd consensus for all addresses")

            # Run the consensus update
            try:
                update_crowd_consensus.update_consensus(
                    db_path=self.db_path,
                    verbose=True
                )
                success = True
            except Exception as e:
                cron_logger.error(
                    f"Consensus update failed: {e}",
                    exc_info=True
                )
                success = False

            duration = (datetime.now() - start_time).total_seconds()

            if success:
                cron_logger.info(
                    f"Crowd Consensus Refresh completed successfully. "
                    f"Duration: {duration:.2f}s"
                )
            else:
                cron_logger.error(
                    f"Crowd Consensus Refresh failed. Duration: {duration:.2f}s"
                )

            return {
                "job": "crowd_consensus_refresh",
                "success": success,
                "duration_seconds": duration,
                "timestamp": start_time.isoformat()
            }

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            cron_logger.error(
                f"Crowd Consensus Refresh job crashed: {e}. "
                f"Duration: {duration:.2f}s",
                exc_info=True
            )
            return {
                "job": "crowd_consensus_refresh",
                "success": False,
                "duration_seconds": duration,
                "error": str(e),
                "timestamp": start_time.isoformat()
            }

    def run_zone_linkage_recalculation(self):
        """Recalculate zone/address linkage.

        This job links addresses to pickup zones using GIS operations.
        Runs weekly on Sunday at 4:00 AM.
        """
        start_time = datetime.now()
        cron_logger.info("=== Starting Zone/Address Linkage Job ===")

        try:
            # Import the zone linkage script
            from scripts import link_addresses_to_pickup_zones

            cron_logger.info("Linking addresses to pickup zones")

            # Run the zone linkage
            original_argv = sys.argv.copy()
            sys.argv = ['link_addresses_to_pickup_zones.py']

            try:
                link_addresses_to_pickup_zones.main()
                success = True
            except Exception as e:
                cron_logger.error(
                    f"Zone linkage failed: {e}",
                    exc_info=True
                )
                success = False
            finally:
                sys.argv = original_argv

            duration = (datetime.now() - start_time).total_seconds()

            if success:
                cron_logger.info(
                    f"Zone/Address Linkage completed successfully. "
                    f"Duration: {duration:.2f}s"
                )
            else:
                cron_logger.error(
                    f"Zone/Address Linkage failed. Duration: {duration:.2f}s"
                )

            return {
                "job": "zone_linkage_recalculation",
                "success": success,
                "duration_seconds": duration,
                "timestamp": start_time.isoformat()
            }

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            cron_logger.error(
                f"Zone/Address Linkage job crashed: {e}. "
                f"Duration: {duration:.2f}s",
                exc_info=True
            )
            return {
                "job": "zone_linkage_recalculation",
                "success": False,
                "duration_seconds": duration,
                "error": str(e),
                "timestamp": start_time.isoformat()
            }

    def add_jobs(self):
        """Add all scheduled jobs to the scheduler."""

        # Job 1: OSM Pipeline - Nightly at 2:00 AM
        self.scheduler.add_job(
            func=self.run_osm_pipeline,
            trigger=CronTrigger(hour=2, minute=0),
            id='osm_pipeline',
            name='OSM Address Pipeline (Nightly)',
            replace_existing=True
        )
        cron_logger.info("Added job: OSM Pipeline (runs nightly at 2:00 AM)")

        # Job 2: Crowd Consensus Refresh - Daily at 3:00 AM
        self.scheduler.add_job(
            func=self.run_crowd_consensus_refresh,
            trigger=CronTrigger(hour=3, minute=0),
            id='crowd_consensus_refresh',
            name='Crowd Consensus Refresh (Daily)',
            replace_existing=True
        )
        cron_logger.info(
            "Added job: Crowd Consensus Refresh (runs daily at 3:00 AM)"
        )

        # Job 3: Zone/Address Linkage - Weekly on Sunday at 4:00 AM
        self.scheduler.add_job(
            func=self.run_zone_linkage_recalculation,
            trigger=CronTrigger(day_of_week='sun', hour=4, minute=0),
            id='zone_linkage_recalculation',
            name='Zone/Address Linkage (Weekly)',
            replace_existing=True
        )
        cron_logger.info(
            "Added job: Zone/Address Linkage "
            "(runs weekly on Sunday at 4:00 AM)"
        )

    def start(self):
        """Start the scheduler."""
        self.add_jobs()
        self.scheduler.start()
        cron_logger.info("Background job scheduler started")

        # Log next run times
        for job in self.scheduler.get_jobs():
            cron_logger.info(
                f"Job '{job.name}' (ID: {job.id}) - "
                f"Next run: {job.next_run_time}"
            )

    def shutdown(self, wait: bool = True):
        """Shutdown the scheduler.

        Args:
            wait: Whether to wait for running jobs to complete
        """
        cron_logger.info("Shutting down background job scheduler")
        self.scheduler.shutdown(wait=wait)
        cron_logger.info("Background job scheduler stopped")

    def get_job_status(self):
        """Get status of all scheduled jobs.

        Returns:
            List of job status dictionaries
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            # Get next run time (only available after scheduler is started)
            next_run = None
            if hasattr(job, 'next_run_time') and job.next_run_time:
                next_run = job.next_run_time.isoformat()

            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": next_run,
                "trigger": str(job.trigger)
            })
        return jobs


# Global scheduler instance
_scheduler_instance = None


def get_scheduler() -> BackgroundJobScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = BackgroundJobScheduler()
    return _scheduler_instance


def start_scheduler():
    """Start the global scheduler instance."""
    scheduler = get_scheduler()
    scheduler.start()
    return scheduler


def shutdown_scheduler(wait: bool = True):
    """Shutdown the global scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is not None:
        _scheduler_instance.shutdown(wait=wait)
        _scheduler_instance = None


if __name__ == "__main__":
    """Run scheduler as standalone service."""
    import time
    import signal

    # Handle shutdown signals
    def signal_handler(sig, frame):
        cron_logger.info(f"Received signal {sig}, shutting down...")
        shutdown_scheduler()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start scheduler
    cron_logger.info("Starting TrashAlert Background Job Scheduler")
    scheduler = start_scheduler()

    try:
        # Keep the process running
        cron_logger.info("Scheduler is running. Press Ctrl+C to exit.")
        while True:
            time.sleep(60)  # Sleep for 1 minute
    except KeyboardInterrupt:
        cron_logger.info("Keyboard interrupt received")
    finally:
        shutdown_scheduler()
