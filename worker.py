#!/usr/bin/env python3
"""
TrashAlert Background Worker Service

This script runs the background job scheduler as a standalone service.
It schedules and executes:
- OSM pipeline (nightly at 2:00 AM)
- Crowd consensus refresh (daily at 3:00 AM)
- Zone/address linkage recalculation (weekly on Sunday at 4:00 AM)

All jobs log to logs/cron.log with execution metrics.
"""

import sys
import time
import signal
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.scheduler import start_scheduler, shutdown_scheduler, cron_logger


def main():
    """Main entry point for the worker service."""

    # Handle shutdown signals gracefully
    def signal_handler(sig, frame):
        cron_logger.info(f"Received signal {sig}, initiating graceful shutdown...")
        shutdown_scheduler(wait=True)
        cron_logger.info("Worker service stopped")
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start the scheduler
    cron_logger.info("=" * 60)
    cron_logger.info("TrashAlert Background Worker Service Starting")
    cron_logger.info("=" * 60)

    try:
        scheduler = start_scheduler()

        # Log all scheduled jobs
        cron_logger.info("Scheduled jobs:")
        for job_info in scheduler.get_job_status():
            cron_logger.info(
                f"  - {job_info['name']} (ID: {job_info['id']})"
            )
            cron_logger.info(f"    Next run: {job_info['next_run_time']}")
            cron_logger.info(f"    Trigger: {job_info['trigger']}")

        cron_logger.info("=" * 60)
        cron_logger.info("Worker service is running. Press Ctrl+C to stop.")
        cron_logger.info("=" * 60)

        # Keep the process running
        while True:
            time.sleep(60)  # Sleep for 1 minute between checks

    except KeyboardInterrupt:
        cron_logger.info("Keyboard interrupt received")
        shutdown_scheduler(wait=True)
    except Exception as e:
        cron_logger.error(f"Unexpected error in worker service: {e}", exc_info=True)
        shutdown_scheduler(wait=False)
        sys.exit(1)


if __name__ == "__main__":
    main()
