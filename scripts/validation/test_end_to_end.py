#!/usr/bin/env python3
"""
Manual end-to-end test for the validation pipeline.

This script creates test data with issues, runs the validation pipeline,
and verifies that issues were detected and corrections were applied.
"""

import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import SessionLocal
from app.models import City, Address, Schedule, PickupZone, ScheduleException
from scripts.validation.pipeline import ValidationPipeline, PipelineConfig
from scripts.validation.agents import AgentStatus
from datetime import datetime, timedelta
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cleanup_test_data(db):
    """Remove any existing test data."""
    logger.info("Cleaning up existing test data...")
    existing_city = db.query(City).filter(City.slug == "e2e-test-city").first()
    if existing_city:
        db.query(ScheduleException).filter(
            ScheduleException.city_id == existing_city.id
        ).delete()
        db.query(Schedule).filter(Schedule.city_id == existing_city.id).delete()
        db.query(Address).filter(Address.city_id == existing_city.id).delete()
        db.query(PickupZone).filter(PickupZone.city_id == existing_city.id).delete()
        db.query(City).filter(City.id == existing_city.id).delete()
        db.commit()


def create_test_data(db):
    """Create test data with intentional issues."""
    logger.info("Creating test data with issues...")

    # Create test city
    city = City(
        name="E2E Test City",
        slug="e2e-test-city",
        state="CA",
        timezone="America/Los_Angeles"
    )
    db.add(city)
    db.flush()

    # Create pickup zones
    zone1 = PickupZone(
        city_id=city.id,
        zone_name="Test Zone A",
        external_zone_id="ZONE_A"
    )
    db.add(zone1)

    # Zone with missing name (issue)
    zone2 = PickupZone(
        city_id=city.id,
        zone_name=None,  # ISSUE
        external_zone_id="ZONE_B"
    )
    db.add(zone2)
    db.flush()

    # Schedule with invalid day (issue)
    schedule1 = Schedule(
        city_id=city.id,
        pickup_zone_id=zone1.id,
        trash_day_of_week=9,  # ISSUE: Invalid day
        recycling_day_of_week=1
    )
    db.add(schedule1)

    # Schedule with string day (issue)
    schedule2 = Schedule(
        city_id=city.id,
        pickup_zone_id=zone1.id,
        trash_day_of_week="Tuesday",  # ISSUE: Should be int
        recycling_day_of_week=4
    )
    db.add(schedule2)

    # Address with invalid coordinates (issue)
    address1 = Address(
        street_number="123",
        street_name="Test Street",
        city_id=city.id,
        latitude=999.0,  # ISSUE: Invalid
        longitude=-118.0
    )
    db.add(address1)

    # Address with incomplete coordinates (issue)
    address2 = Address(
        street_number="456",
        street_name="Test Avenue",
        city_id=city.id,
        latitude=34.0,
        longitude=None  # ISSUE: Incomplete
    )
    db.add(address2)

    # Old schedule exception (issue)
    old_exception = ScheduleException(
        city_id=city.id,
        exception_date=datetime.now().date() - timedelta(days=60),  # ISSUE: Old
        reason="Past Holiday"
    )
    db.add(old_exception)

    db.commit()

    logger.info(f"Created test city (ID: {city.id}) with problematic data")
    return city


def run_validation_pipeline(db, city_id, dry_run=False):
    """Run the validation pipeline."""
    logger.info(f"Running validation pipeline (dry_run={dry_run})...")

    config = PipelineConfig(
        city_id=city_id,
        dry_run=dry_run,
        auto_apply_corrections=True,
        save_report=True
    )

    pipeline = ValidationPipeline(config)
    result = pipeline.run(db)

    return result


def verify_results(result, expected_issues_min=5):
    """Verify pipeline results."""
    logger.info("\nVerifying results...")

    # Check pipeline status
    assert result.status == AgentStatus.SUCCESS, \
        f"Pipeline failed: {result.error_message}"
    logger.info("✓ Pipeline completed successfully")

    # Check that issues were detected
    assert result.total_issues >= expected_issues_min, \
        f"Expected at least {expected_issues_min} issues, found {result.total_issues}"
    logger.info(f"✓ Detected {result.total_issues} issues")

    # Check that corrections were proposed
    assert result.total_corrections_proposed > 0, \
        "No corrections proposed"
    logger.info(f"✓ Proposed {result.total_corrections_proposed} corrections")

    # Check that corrections were applied (if not dry run)
    if not any("dry_run" in r.metadata and r.metadata["dry_run"]
               for r in result.agent_results):
        assert result.total_corrections_applied > 0, \
            "No corrections applied"
        logger.info(f"✓ Applied {result.total_corrections_applied} corrections")

    # Check all agents ran
    agent_names = [r.agent_name for r in result.agent_results]
    assert "ImporterAgent" in agent_names, "ImporterAgent did not run"
    assert "ValidatorAgent" in agent_names, "ValidatorAgent did not run"
    assert "CorrectionAgent" in agent_names, "CorrectionAgent did not run"
    logger.info("✓ All expected agents ran")

    logger.info("\n✓ All verifications passed!")


def verify_corrections_applied(db, city_id):
    """Verify that corrections were actually applied to the database."""
    logger.info("\nVerifying corrections were persisted to database...")

    # Check schedules
    schedules = db.query(Schedule).filter(Schedule.city_id == city_id).all()
    for schedule in schedules:
        # All day values should be valid (0-6) or None
        if schedule.trash_day_of_week is not None:
            assert 0 <= schedule.trash_day_of_week <= 6, \
                f"Invalid trash_day_of_week: {schedule.trash_day_of_week}"
        if schedule.recycling_day_of_week is not None:
            assert 0 <= schedule.recycling_day_of_week <= 6, \
                f"Invalid recycling_day_of_week: {schedule.recycling_day_of_week}"
    logger.info("✓ All schedule days are valid")

    # Check addresses
    addresses = db.query(Address).filter(Address.city_id == city_id).all()
    for address in addresses:
        # All coordinates should be valid or None
        if address.latitude is not None:
            assert -90 <= address.latitude <= 90, \
                f"Invalid latitude: {address.latitude}"
        if address.longitude is not None:
            assert -180 <= address.longitude <= 180, \
                f"Invalid longitude: {address.longitude}"
    logger.info("✓ All coordinates are valid or None")

    # Check old exceptions were deleted
    old_date = datetime.now().date() - timedelta(days=30)
    old_exceptions = db.query(ScheduleException).filter(
        ScheduleException.city_id == city_id,
        ScheduleException.exception_date < old_date - timedelta(days=30)
    ).count()
    assert old_exceptions == 0, f"Found {old_exceptions} old exceptions"
    logger.info("✓ Old exceptions were deleted")

    logger.info("\n✓ All corrections persisted correctly!")


def main():
    """Run end-to-end test."""
    logger.info("=" * 80)
    logger.info("STARTING END-TO-END VALIDATION PIPELINE TEST")
    logger.info("=" * 80)

    db = SessionLocal()

    try:
        # Step 1: Cleanup and create test data
        cleanup_test_data(db)
        city = create_test_data(db)

        # Step 2: Run pipeline in dry-run mode first
        logger.info("\n" + "=" * 80)
        logger.info("TEST 1: Dry Run Mode")
        logger.info("=" * 80)
        result_dry = run_validation_pipeline(db, city.id, dry_run=True)
        verify_results(result_dry)

        # Step 3: Run pipeline in live mode
        logger.info("\n" + "=" * 80)
        logger.info("TEST 2: Live Mode (Apply Corrections)")
        logger.info("=" * 80)
        result_live = run_validation_pipeline(db, city.id, dry_run=False)
        verify_results(result_live)

        # Step 4: Verify corrections were persisted
        verify_corrections_applied(db, city.id)

        # Step 5: Run pipeline again to verify fewer issues
        logger.info("\n" + "=" * 80)
        logger.info("TEST 3: Verify Issues Were Fixed")
        logger.info("=" * 80)
        result_verify = run_validation_pipeline(db, city.id, dry_run=False)

        logger.info(f"\nFirst run: {result_live.total_issues} issues")
        logger.info(f"Second run: {result_verify.total_issues} issues")

        # Should have fewer issues after corrections
        improvement = result_live.total_issues - result_verify.total_issues
        logger.info(f"Improvement: {improvement} issues fixed")

        if improvement > 0:
            logger.info("✓ Issues were successfully fixed!")
        else:
            logger.warning("⚠ No improvement in issue count")

        # Final cleanup
        logger.info("\nCleaning up test data...")
        cleanup_test_data(db)

        # Success!
        logger.info("\n" + "=" * 80)
        logger.info("✅ END-TO-END TEST PASSED!")
        logger.info("=" * 80)
        logger.info("\nSummary:")
        logger.info(f"  - Test 1 (Dry Run): {result_dry.total_issues} issues detected")
        logger.info(f"  - Test 2 (Live): {result_live.total_corrections_applied} corrections applied")
        logger.info(f"  - Test 3 (Verify): {improvement} issues fixed")
        logger.info(f"  - Duration: {result_live.duration:.2f}s")

        return 0

    except AssertionError as e:
        logger.error(f"\n❌ TEST FAILED: {str(e)}")
        return 1

    except Exception as e:
        logger.error(f"\n❌ UNEXPECTED ERROR: {str(e)}", exc_info=True)
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
