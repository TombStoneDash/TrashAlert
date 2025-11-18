"""
Unit tests for validation pipeline agents.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, City, Address, Schedule, PickupZone, ScheduleException
from scripts.validation.agents import (
    ImporterAgent,
    ValidatorAgent,
    CorrectionAgent,
    UpdaterAgent,
    AgentStatus,
    IssueType,
    IssueSeverity
)


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
def test_zone(db_session, test_city):
    """Create a test pickup zone."""
    zone = PickupZone(
        city_id=test_city.id,
        zone_name="Zone A",
        external_zone_id="ZONE_A"
    )
    db_session.add(zone)
    db_session.commit()
    return zone


class TestImporterAgent:
    """Tests for ImporterAgent."""

    def test_import_empty_database(self, db_session):
        """Test importing from empty database."""
        agent = ImporterAgent()
        context = {"db_session": db_session}

        result = agent.run(context)

        assert result.status == AgentStatus.FAILED
        assert len(result.issues_detected) > 0
        assert result.metadata["cities_count"] == 0

    def test_import_with_city(self, db_session, test_city):
        """Test importing data with a city."""
        agent = ImporterAgent()
        context = {"db_session": db_session}

        result = agent.run(context)

        assert result.status == AgentStatus.SUCCESS
        assert result.metadata["cities_count"] == 1
        assert len(context["cities"]) == 1
        assert context["cities"][0].id == test_city.id

    def test_import_with_city_filter(self, db_session, test_city):
        """Test importing data filtered by city."""
        # Create another city
        city2 = City(name="City 2", slug="city-2", state="CA")
        db_session.add(city2)
        db_session.commit()

        agent = ImporterAgent()
        context = {"db_session": db_session, "city_id": test_city.id}

        result = agent.run(context)

        assert result.status == AgentStatus.SUCCESS
        assert result.metadata["cities_count"] == 1
        assert context["cities"][0].id == test_city.id

    def test_import_with_limit(self, db_session, test_city):
        """Test importing data with limit."""
        # Create multiple addresses
        for i in range(5):
            address = Address(
                street_number=str(100 + i),
                street_name="Test Street",
                city_id=test_city.id
            )
            db_session.add(address)
        db_session.commit()

        agent = ImporterAgent()
        context = {"db_session": db_session, "limit": 3}

        result = agent.run(context)

        assert result.status == AgentStatus.SUCCESS
        assert result.metadata["addresses_count"] <= 3

    def test_import_schedules_and_zones(self, db_session, test_city, test_zone):
        """Test importing schedules and zones."""
        # Create a schedule
        schedule = Schedule(
            city_id=test_city.id,
            pickup_zone_id=test_zone.id,
            trash_day_of_week=2,
            recycling_day_of_week=4
        )
        db_session.add(schedule)
        db_session.commit()

        agent = ImporterAgent()
        context = {"db_session": db_session}

        result = agent.run(context)

        assert result.status == AgentStatus.SUCCESS
        assert result.metadata["pickup_zones_count"] == 1
        assert result.metadata["schedules_count"] == 1


class TestValidatorAgent:
    """Tests for ValidatorAgent."""

    def test_validate_empty_data(self, db_session):
        """Test validating empty data."""
        agent = ValidatorAgent()
        context = {
            "addresses": [],
            "schedules": [],
            "pickup_zones": [],
            "cities": [],
            "address_pickup_info": [],
            "schedule_exceptions": []
        }

        result = agent.run(context)

        assert result.status == AgentStatus.SUCCESS
        assert len(result.issues_detected) == 0

    def test_validate_invalid_day_of_week(self, db_session, test_city, test_zone):
        """Test detection of invalid day of week."""
        schedule = Schedule(
            id=1,
            city_id=test_city.id,
            pickup_zone_id=test_zone.id,
            trash_day_of_week=9  # Invalid: must be 0-6
        )

        agent = ValidatorAgent()
        context = {
            "schedules": [schedule],
            "addresses": [],
            "pickup_zones": [],
            "address_pickup_info": [],
            "schedule_exceptions": []
        }

        result = agent.run(context)

        assert result.status == AgentStatus.SUCCESS
        assert len(result.issues_detected) > 0

        # Find the invalid day issue
        day_issues = [
            i for i in result.issues_detected
            if i.issue_type == IssueType.INVALID_FORMAT
            and 'day' in i.field_name.lower()
        ]
        assert len(day_issues) > 0
        assert day_issues[0].severity == IssueSeverity.HIGH

    def test_validate_missing_city_id(self, db_session):
        """Test detection of missing city_id."""
        address = Address(
            id=1,
            street_number="123",
            street_name="Main St",
            city_id=None  # Missing
        )

        agent = ValidatorAgent()
        context = {
            "addresses": [address],
            "schedules": [],
            "pickup_zones": [],
            "address_pickup_info": [],
            "schedule_exceptions": []
        }

        result = agent.run(context)

        assert result.status == AgentStatus.SUCCESS

        # Find the missing city_id issue
        missing_issues = [
            i for i in result.issues_detected
            if i.issue_type == IssueType.MISSING_DATA
            and i.field_name == "city_id"
        ]
        assert len(missing_issues) > 0
        assert missing_issues[0].severity == IssueSeverity.CRITICAL

    def test_validate_invalid_coordinates(self, db_session, test_city):
        """Test detection of invalid coordinates."""
        address = Address(
            id=1,
            street_number="123",
            street_name="Main St",
            city_id=test_city.id,
            latitude=999.0,  # Invalid
            longitude=-118.0
        )

        agent = ValidatorAgent()
        context = {
            "addresses": [address],
            "schedules": [],
            "pickup_zones": [],
            "address_pickup_info": [],
            "schedule_exceptions": []
        }

        result = agent.run(context)

        assert result.status == AgentStatus.SUCCESS

        coord_issues = [
            i for i in result.issues_detected
            if i.field_name in ["latitude", "longitude"]
        ]
        assert len(coord_issues) > 0

    def test_validate_duplicate_zone_names(self, db_session, test_city):
        """Test detection of duplicate zone names."""
        zone1 = PickupZone(
            id=1,
            city_id=test_city.id,
            zone_name="Zone A"
        )
        zone2 = PickupZone(
            id=2,
            city_id=test_city.id,
            zone_name="Zone A"  # Duplicate
        )

        agent = ValidatorAgent()
        context = {
            "pickup_zones": [zone1, zone2],
            "addresses": [],
            "schedules": [],
            "address_pickup_info": [],
            "schedule_exceptions": []
        }

        result = agent.run(context)

        assert result.status == AgentStatus.SUCCESS

        duplicate_issues = [
            i for i in result.issues_detected
            if i.issue_type == IssueType.DUPLICATE_DATA
        ]
        assert len(duplicate_issues) > 0

    def test_validate_schedule_inconsistency(self, db_session, test_city, test_zone):
        """Test detection of schedule inconsistencies."""
        schedule = Schedule(
            id=1,
            city_id=test_city.id,
            pickup_zone_id=test_zone.id,
            trash_day_of_week=2,
            recycling_day_of_week=2  # Same day as trash
        )

        agent = ValidatorAgent()
        context = {
            "schedules": [schedule],
            "addresses": [],
            "pickup_zones": [],
            "address_pickup_info": [],
            "schedule_exceptions": []
        }

        result = agent.run(context)

        assert result.status == AgentStatus.SUCCESS

        inconsistency_issues = [
            i for i in result.issues_detected
            if i.issue_type == IssueType.INCONSISTENT_SCHEDULE
        ]
        assert len(inconsistency_issues) > 0


class TestCorrectionAgent:
    """Tests for CorrectionAgent."""

    def test_correct_no_issues(self, db_session):
        """Test correction with no issues."""
        agent = CorrectionAgent()
        context = {"validation_issues": []}

        result = agent.run(context)

        assert result.status == AgentStatus.SUCCESS
        assert len(result.corrections_proposed) == 0

    def test_correct_invalid_day_format(self, db_session):
        """Test correction of invalid day format."""
        from scripts.validation.agents.base_agent import ValidationIssue

        issue = ValidationIssue(
            issue_type=IssueType.INVALID_FORMAT,
            severity=IssueSeverity.HIGH,
            message="Invalid day format",
            entity_type="Schedule",
            entity_id=1,
            field_name="trash_day_of_week",
            current_value="Monday"
        )

        agent = CorrectionAgent()
        context = {"validation_issues": [issue]}

        result = agent.run(context)

        assert result.status == AgentStatus.SUCCESS
        assert len(result.corrections_proposed) > 0

        correction = result.corrections_proposed[0]
        assert correction.action_type == "update"
        assert correction.changes["trash_day_of_week"] == 0  # Monday = 0

    def test_correct_invalid_coordinates(self, db_session):
        """Test correction of invalid coordinates."""
        from scripts.validation.agents.base_agent import ValidationIssue

        issue = ValidationIssue(
            issue_type=IssueType.INVALID_FORMAT,
            severity=IssueSeverity.HIGH,
            message="Invalid latitude",
            entity_type="Address",
            entity_id=1,
            field_name="latitude",
            current_value=999.0
        )

        agent = CorrectionAgent()
        context = {"validation_issues": [issue]}

        result = agent.run(context)

        assert result.status == AgentStatus.SUCCESS
        assert len(result.corrections_proposed) > 0

        correction = result.corrections_proposed[0]
        assert correction.action_type == "update"
        assert correction.changes["latitude"] is None

    def test_correct_duplicate_zone_name(self, db_session):
        """Test correction of duplicate zone name."""
        from scripts.validation.agents.base_agent import ValidationIssue

        issue = ValidationIssue(
            issue_type=IssueType.DUPLICATE_DATA,
            severity=IssueSeverity.MEDIUM,
            message="Duplicate zone name",
            entity_type="PickupZone",
            entity_id=2,
            field_name="zone_name",
            current_value="Zone A"
        )

        agent = CorrectionAgent()
        context = {"validation_issues": [issue]}

        result = agent.run(context)

        assert result.status == AgentStatus.SUCCESS
        assert len(result.corrections_proposed) > 0

        correction = result.corrections_proposed[0]
        assert correction.action_type == "update"
        assert "Zone A" in correction.changes["zone_name"]
        assert "_2" in correction.changes["zone_name"]

    def test_skip_non_correctable_issues(self, db_session):
        """Test that non-correctable issues are skipped."""
        from scripts.validation.agents.base_agent import ValidationIssue

        issue = ValidationIssue(
            issue_type=IssueType.MISSING_DATA,
            severity=IssueSeverity.CRITICAL,
            message="Critical issue",
            entity_type="Address",
            entity_id=1,
            field_name="city_id",
            current_value=None,
            correctable=False
        )

        agent = CorrectionAgent()
        context = {"validation_issues": [issue]}

        result = agent.run(context)

        assert result.status == AgentStatus.SUCCESS
        assert len(result.corrections_proposed) == 0


class TestUpdaterAgent:
    """Tests for UpdaterAgent."""

    def test_update_no_corrections(self, db_session):
        """Test update with no corrections."""
        agent = UpdaterAgent()
        context = {
            "db_session": db_session,
            "correction_actions": []
        }

        result = agent.run(context)

        assert result.status == AgentStatus.SUCCESS
        assert len(result.corrections_applied) == 0

    def test_update_dry_run(self, db_session, test_city, test_zone):
        """Test update in dry run mode."""
        from scripts.validation.agents.base_agent import (
            ValidationIssue, CorrectionAction
        )

        # Create a schedule with issue
        schedule = Schedule(
            city_id=test_city.id,
            pickup_zone_id=test_zone.id,
            trash_day_of_week=9  # Invalid
        )
        db_session.add(schedule)
        db_session.commit()

        issue = ValidationIssue(
            issue_type=IssueType.INVALID_FORMAT,
            severity=IssueSeverity.HIGH,
            message="Invalid day",
            entity_type="Schedule",
            entity_id=schedule.id,
            field_name="trash_day_of_week",
            current_value=9
        )

        correction = CorrectionAction(
            issue=issue,
            action_type="update",
            entity_type="Schedule",
            entity_id=schedule.id,
            changes={"trash_day_of_week": None}
        )

        agent = UpdaterAgent()
        context = {
            "db_session": db_session,
            "correction_actions": [correction],
            "dry_run": True
        }

        result = agent.run(context)

        assert result.status == AgentStatus.SUCCESS

        # Verify changes were rolled back
        db_session.expire_all()
        schedule_after = db_session.query(Schedule).get(schedule.id)
        assert schedule_after.trash_day_of_week == 9  # Unchanged

    def test_update_live_run(self, db_session, test_city, test_zone):
        """Test update in live mode."""
        from scripts.validation.agents.base_agent import (
            ValidationIssue, CorrectionAction
        )

        # Create a schedule with issue
        schedule = Schedule(
            city_id=test_city.id,
            pickup_zone_id=test_zone.id,
            trash_day_of_week=9  # Invalid
        )
        db_session.add(schedule)
        db_session.commit()

        issue = ValidationIssue(
            issue_type=IssueType.INVALID_FORMAT,
            severity=IssueSeverity.HIGH,
            message="Invalid day",
            entity_type="Schedule",
            entity_id=schedule.id,
            field_name="trash_day_of_week",
            current_value=9
        )

        correction = CorrectionAction(
            issue=issue,
            action_type="update",
            entity_type="Schedule",
            entity_id=schedule.id,
            changes={"trash_day_of_week": None}
        )

        agent = UpdaterAgent()
        context = {
            "db_session": db_session,
            "correction_actions": [correction],
            "dry_run": False
        }

        result = agent.run(context)

        assert result.status == AgentStatus.SUCCESS
        assert len(result.corrections_applied) == 1

        # Verify changes were applied
        db_session.expire_all()
        schedule_after = db_session.query(Schedule).get(schedule.id)
        assert schedule_after.trash_day_of_week is None

    def test_update_delete_action(self, db_session, test_city):
        """Test delete correction action."""
        from scripts.validation.agents.base_agent import (
            ValidationIssue, CorrectionAction
        )

        # Create an old exception
        exception = ScheduleException(
            city_id=test_city.id,
            exception_date=datetime.now().date() - timedelta(days=60)
        )
        db_session.add(exception)
        db_session.commit()
        exception_id = exception.id

        issue = ValidationIssue(
            issue_type=IssueType.DATA_QUALITY,
            severity=IssueSeverity.LOW,
            message="Old exception",
            entity_type="ScheduleException",
            entity_id=exception_id,
            field_name="exception_date"
        )

        correction = CorrectionAction(
            issue=issue,
            action_type="delete",
            entity_type="ScheduleException",
            entity_id=exception_id,
            changes={}
        )

        agent = UpdaterAgent()
        context = {
            "db_session": db_session,
            "correction_actions": [correction],
            "dry_run": False
        }

        result = agent.run(context)

        assert result.status == AgentStatus.SUCCESS
        assert len(result.corrections_applied) == 1

        # Verify entity was deleted
        deleted = db_session.query(ScheduleException).get(exception_id)
        assert deleted is None
