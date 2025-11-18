"""
Integration tests for the validation pipeline.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, City, Address, Schedule, PickupZone, ScheduleException
from scripts.validation.pipeline import ValidationPipeline, PipelineConfig
from scripts.validation.agents import AgentStatus


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def test_city(db_session):
    """Create a test city."""
    city = City(
        name="Test City",
        slug="test-city",
        state="CA",
        timezone="America/Los_Angeles"
    )
    db_session.add(city)
    db_session.commit()
    return city


@pytest.fixture
def problematic_data(db_session, test_city):
    """Create test data with various issues."""
    # Zone with missing name
    zone1 = PickupZone(
        city_id=test_city.id,
        zone_name=None,  # Issue
        external_zone_id="ZONE_1"
    )
    db_session.add(zone1)

    # Valid zone
    zone2 = PickupZone(
        city_id=test_city.id,
        zone_name="Zone A",
        external_zone_id="ZONE_2"
    )
    db_session.add(zone2)
    db_session.flush()

    # Schedule with invalid day
    schedule1 = Schedule(
        city_id=test_city.id,
        pickup_zone_id=zone2.id,
        trash_day_of_week=9,  # Issue: invalid day
        recycling_day_of_week=1
    )
    db_session.add(schedule1)

    # Schedule with string day (should be converted to int)
    schedule2 = Schedule(
        city_id=test_city.id,
        pickup_zone_id=zone2.id,
        trash_day_of_week="Monday",  # Issue: should be int
        recycling_day_of_week=3
    )
    db_session.add(schedule2)

    # Address with invalid coordinates
    address1 = Address(
        street_number="123",
        street_name="Main St",
        city_id=test_city.id,
        latitude=999.0,  # Issue: invalid
        longitude=-118.0
    )
    db_session.add(address1)

    # Address with incomplete coordinates
    address2 = Address(
        street_number="456",
        street_name="Oak Ave",
        city_id=test_city.id,
        latitude=34.0,
        longitude=None  # Issue: incomplete
    )
    db_session.add(address2)

    # Old schedule exception (cleanup candidate)
    old_exception = ScheduleException(
        city_id=test_city.id,
        exception_date=datetime.now().date() - timedelta(days=60),  # Issue: old
        reason="Past Holiday"
    )
    db_session.add(old_exception)

    db_session.commit()

    return {
        "city": test_city,
        "zones": [zone1, zone2],
        "schedules": [schedule1, schedule2],
        "addresses": [address1, address2],
        "exceptions": [old_exception]
    }


class TestValidationPipeline:
    """Integration tests for ValidationPipeline."""

    def test_pipeline_with_no_data(self, db_session):
        """Test pipeline with empty database."""
        config = PipelineConfig(auto_apply_corrections=False)
        pipeline = ValidationPipeline(config)

        result = pipeline.run(db_session)

        # Should fail because no data was imported
        assert result.status == AgentStatus.FAILED
        assert result.total_issues >= 0

    def test_pipeline_with_clean_data(self, db_session, test_city):
        """Test pipeline with valid data."""
        # Create valid data
        zone = PickupZone(
            city_id=test_city.id,
            zone_name="Zone A",
            external_zone_id="ZONE_A"
        )
        db_session.add(zone)
        db_session.flush()

        schedule = Schedule(
            city_id=test_city.id,
            pickup_zone_id=zone.id,
            trash_day_of_week=2,
            recycling_day_of_week=4
        )
        db_session.add(schedule)

        address = Address(
            street_number="123",
            street_name="Main St",
            city_id=test_city.id,
            latitude=34.0522,
            longitude=-118.2437
        )
        db_session.add(address)
        db_session.commit()

        config = PipelineConfig(auto_apply_corrections=False)
        pipeline = ValidationPipeline(config)

        result = pipeline.run(db_session)

        assert result.status == AgentStatus.SUCCESS
        assert result.total_issues == 0
        assert result.total_corrections_proposed == 0

    def test_pipeline_detects_issues(self, db_session, problematic_data):
        """Test that pipeline detects issues in data."""
        config = PipelineConfig(
            city_id=problematic_data["city"].id,
            auto_apply_corrections=False
        )
        pipeline = ValidationPipeline(config)

        result = pipeline.run(db_session)

        assert result.status == AgentStatus.SUCCESS
        assert result.total_issues > 0
        assert result.total_corrections_proposed > 0

        # Should have detected multiple types of issues
        issues_by_type = pipeline.get_issues_by_type()
        assert len(issues_by_type) > 0

    def test_pipeline_dry_run(self, db_session, problematic_data):
        """Test pipeline in dry run mode."""
        config = PipelineConfig(
            city_id=problematic_data["city"].id,
            dry_run=True,
            auto_apply_corrections=True
        )
        pipeline = ValidationPipeline(config)

        # Get original values
        schedule_id = problematic_data["schedules"][0].id
        original_day = problematic_data["schedules"][0].trash_day_of_week

        result = pipeline.run(db_session)

        assert result.status == AgentStatus.SUCCESS
        assert result.total_issues > 0

        # Verify no changes were committed
        db_session.expire_all()
        schedule = db_session.query(Schedule).get(schedule_id)
        assert schedule.trash_day_of_week == original_day

    def test_pipeline_applies_corrections(self, db_session, problematic_data):
        """Test pipeline applies corrections in live mode."""
        config = PipelineConfig(
            city_id=problematic_data["city"].id,
            dry_run=False,
            auto_apply_corrections=True
        )
        pipeline = ValidationPipeline(config)

        # Get IDs to check after
        schedule_id = problematic_data["schedules"][0].id
        address_id = problematic_data["addresses"][0].id
        exception_id = problematic_data["exceptions"][0].id

        result = pipeline.run(db_session)

        assert result.status == AgentStatus.SUCCESS
        assert result.total_issues > 0
        assert result.total_corrections_applied > 0

        # Verify corrections were applied
        db_session.expire_all()

        # Schedule with invalid day should be corrected
        schedule = db_session.query(Schedule).get(schedule_id)
        assert schedule.trash_day_of_week is None or 0 <= schedule.trash_day_of_week <= 6

        # Address with invalid coordinates should be corrected
        address = db_session.query(Address).get(address_id)
        assert address.latitude is None or -90 <= address.latitude <= 90

        # Old exception should be deleted
        exception = db_session.query(ScheduleException).get(exception_id)
        assert exception is None

    def test_pipeline_with_city_filter(self, db_session, problematic_data):
        """Test pipeline with city filter."""
        # Create another city with data
        city2 = City(name="City 2", slug="city-2", state="CA")
        db_session.add(city2)
        db_session.flush()

        zone = PickupZone(city_id=city2.id, zone_name="Zone B")
        db_session.add(zone)
        db_session.commit()

        config = PipelineConfig(
            city_id=problematic_data["city"].id,
            auto_apply_corrections=False
        )
        pipeline = ValidationPipeline(config)

        result = pipeline.run(db_session)

        assert result.status == AgentStatus.SUCCESS

        # Should only process data from test_city
        importer_result = result.agent_results[0]  # Importer is first
        assert importer_result.metadata["cities_count"] == 1

    def test_pipeline_with_limit(self, db_session, test_city):
        """Test pipeline with record limit."""
        # Create multiple addresses
        for i in range(10):
            address = Address(
                street_number=str(100 + i),
                street_name="Test St",
                city_id=test_city.id,
                latitude=999.0  # Invalid
            )
            db_session.add(address)
        db_session.commit()

        config = PipelineConfig(
            city_id=test_city.id,
            limit=5,
            auto_apply_corrections=False
        )
        pipeline = ValidationPipeline(config)

        result = pipeline.run(db_session)

        assert result.status == AgentStatus.SUCCESS

        # Should only process limited records
        importer_result = result.agent_results[0]
        assert importer_result.metadata["addresses_count"] <= 5

    def test_pipeline_saves_report(self, db_session, test_city, tmp_path):
        """Test that pipeline saves report."""
        zone = PickupZone(city_id=test_city.id, zone_name="Zone A")
        db_session.add(zone)
        db_session.commit()

        config = PipelineConfig(
            city_id=test_city.id,
            save_report=True,
            report_output_dir=str(tmp_path)
        )
        pipeline = ValidationPipeline(config)

        result = pipeline.run(db_session)

        assert result.status == AgentStatus.SUCCESS
        assert result.report_path is not None

        # Verify report file exists
        from pathlib import Path
        report_file = Path(result.report_path)
        assert report_file.exists()
        assert report_file.suffix == ".json"

        # Verify report content
        import json
        with open(report_file) as f:
            report_data = json.load(f)

        assert "pipeline_name" in report_data
        assert "status" in report_data
        assert "agent_results" in report_data

    def test_pipeline_end_to_end(self, db_session, problematic_data):
        """Test complete end-to-end pipeline execution."""
        config = PipelineConfig(
            city_id=problematic_data["city"].id,
            dry_run=False,
            auto_apply_corrections=True
        )
        pipeline = ValidationPipeline(config)

        # Run pipeline
        result = pipeline.run(db_session)

        # Verify pipeline succeeded
        assert result.status == AgentStatus.SUCCESS
        assert result.total_issues > 0
        assert result.total_corrections_proposed > 0
        assert result.total_corrections_applied > 0
        assert result.duration is not None

        # Verify all agents ran
        assert len(result.agent_results) == 4  # Importer, Validator, Correction, Updater
        for agent_result in result.agent_results:
            assert agent_result.status in [AgentStatus.SUCCESS, AgentStatus.SKIPPED]

        # Run pipeline again to verify issues were fixed
        config2 = PipelineConfig(
            city_id=problematic_data["city"].id,
            auto_apply_corrections=False
        )
        pipeline2 = ValidationPipeline(config2)
        result2 = pipeline2.run(db_session)

        # Should have fewer issues now
        assert result2.total_issues < result.total_issues

    def test_pipeline_without_auto_apply(self, db_session, problematic_data):
        """Test pipeline without auto-applying corrections."""
        config = PipelineConfig(
            city_id=problematic_data["city"].id,
            auto_apply_corrections=False
        )
        pipeline = ValidationPipeline(config)

        result = pipeline.run(db_session)

        assert result.status == AgentStatus.SUCCESS
        assert result.total_issues > 0
        assert result.total_corrections_proposed > 0
        assert result.total_corrections_applied == 0  # Should not apply

        # Verify only 3 agents ran (no Updater)
        assert len(result.agent_results) == 3

    def test_pipeline_statistics(self, db_session, problematic_data):
        """Test pipeline statistics methods."""
        config = PipelineConfig(
            city_id=problematic_data["city"].id,
            auto_apply_corrections=False
        )
        pipeline = ValidationPipeline(config)

        result = pipeline.run(db_session)

        # Test get_issues_by_type
        issues_by_type = pipeline.get_issues_by_type()
        assert isinstance(issues_by_type, dict)
        assert len(issues_by_type) > 0

        # Test get_issues_by_severity
        issues_by_severity = pipeline.get_issues_by_severity()
        assert isinstance(issues_by_severity, dict)
        assert len(issues_by_severity) > 0

    def test_pipeline_result_to_dict(self, db_session, test_city):
        """Test pipeline result serialization."""
        zone = PickupZone(city_id=test_city.id, zone_name="Zone A")
        db_session.add(zone)
        db_session.commit()

        config = PipelineConfig(city_id=test_city.id)
        pipeline = ValidationPipeline(config)

        result = pipeline.run(db_session)

        # Test to_dict method
        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert "pipeline_name" in result_dict
        assert "status" in result_dict
        assert "agent_results" in result_dict
        assert "total_issues" in result_dict
        assert "duration" in result_dict
