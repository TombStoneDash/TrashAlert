"""
Tests for schedules_importer module.

Tests duplicate detection, re-import functionality, and data integrity.
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models import Base, Schedule, ScheduleException, SourceMetadata, City, PickupZone
from scripts.data_collection.schedules_importer import SchedulesImporter
from scripts.data_collection.schedule_parsers.base_parser import ParseResult, ScheduleData, ExceptionData


@pytest.fixture(scope="function")
def temp_db():
    """Create temporary in-memory database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def sample_parse_result():
    """Create sample parse result for testing."""
    result = ParseResult()

    # Add some schedules
    result.schedules.append(ScheduleData(
        address="El Centro, ZONE_A",
        day_of_week="MON",
        collection_type="trash",
        zone="ZONE_A",
        recurrence="weekly",
        confidence=0.95,
        effective_date=datetime(2025, 1, 1),
        next_pickup_date=datetime(2025, 1, 6)
    ))

    result.schedules.append(ScheduleData(
        address="El Centro, ZONE_A",
        day_of_week="WED",
        collection_type="recycling",
        zone="ZONE_A",
        recurrence="biweekly",
        confidence=0.95,
        effective_date=datetime(2025, 1, 1),
        next_pickup_date=datetime(2025, 1, 8)
    ))

    # Add an exception
    result.exceptions.append(ExceptionData(
        exception_date=datetime(2025, 12, 25),
        rescheduled_date=datetime(2025, 12, 26),
        is_cancelled=False,
        reason="Christmas",
        notes="Holiday schedule change"
    ))

    result.metadata = {
        "source_format": "scraper",
        "parser_version": "1.0.0",
        "parser_name": "TestParser"
    }

    return result


class TestSchedulesImporter:
    """Tests for SchedulesImporter class."""

    def test_import_from_parser_success(self, temp_db, sample_parse_result):
        """Test successful import from parser result."""
        importer = SchedulesImporter(temp_db)

        stats = importer.import_from_parser(
            city_name="El Centro",
            parse_result=sample_parse_result,
            source_url="https://example.com"
        )

        assert stats['schedules_created'] == 2
        assert stats['schedules_updated'] == 0
        assert stats['schedules_skipped'] == 0
        assert stats['exceptions_created'] == 1
        assert len(stats['errors']) == 0

        # Verify database state
        schedules = temp_db.query(Schedule).all()
        assert len(schedules) == 2

        exceptions = temp_db.query(ScheduleException).all()
        assert len(exceptions) == 1

        source_metadata = temp_db.query(SourceMetadata).all()
        assert len(source_metadata) == 1

    def test_reimport_prevents_duplicates(self, temp_db, sample_parse_result):
        """Test that re-importing the same data doesn't create duplicates."""
        importer = SchedulesImporter(temp_db, allow_duplicates=False)

        # First import
        stats1 = importer.import_from_parser(
            city_name="El Centro",
            parse_result=sample_parse_result
        )

        assert stats1['schedules_created'] == 2
        assert stats1['exceptions_created'] == 1

        # Second import of same data
        stats2 = importer.import_from_parser(
            city_name="El Centro",
            parse_result=sample_parse_result
        )

        # Should skip duplicates
        assert stats2['schedules_created'] == 0
        assert stats2['schedules_skipped'] == 2

        # Verify no duplicate schedules in database
        schedules = temp_db.query(Schedule).all()
        assert len(schedules) == 2  # Still only 2, not 4

        # Exceptions should also not duplicate
        exceptions = temp_db.query(ScheduleException).all()
        assert len(exceptions) == 1  # Still only 1

    def test_reimport_updates_when_confidence_higher(self, temp_db, sample_parse_result):
        """Test that re-import updates schedules when new data has higher confidence."""
        importer = SchedulesImporter(temp_db, allow_duplicates=False)

        # First import with 0.95 confidence
        stats1 = importer.import_from_parser(
            city_name="El Centro",
            parse_result=sample_parse_result
        )

        assert stats1['schedules_created'] == 2

        # Modify parse result to have higher confidence
        for schedule in sample_parse_result.schedules:
            schedule.confidence = 0.99

        # Second import with higher confidence
        stats2 = importer.import_from_parser(
            city_name="El Centro",
            parse_result=sample_parse_result
        )

        # Should update existing schedules
        assert stats2['schedules_updated'] == 2
        assert stats2['schedules_created'] == 0

        # Verify database state
        schedules = temp_db.query(Schedule).all()
        assert len(schedules) == 2

        # Check that confidence was updated
        for schedule in schedules:
            if schedule.extra_metadata:
                assert schedule.extra_metadata.get('confidence') == 0.99

    def test_allow_duplicates_flag(self, temp_db, sample_parse_result):
        """Test that allow_duplicates flag allows duplicate schedules."""
        importer = SchedulesImporter(temp_db, allow_duplicates=True)

        # First import
        stats1 = importer.import_from_parser(
            city_name="El Centro",
            parse_result=sample_parse_result
        )

        # Second import with allow_duplicates=True
        stats2 = importer.import_from_parser(
            city_name="El Centro",
            parse_result=sample_parse_result
        )

        # Should create duplicates
        assert stats2['schedules_created'] == 2

        # Verify database has duplicates
        schedules = temp_db.query(Schedule).all()
        assert len(schedules) == 4  # 2 from first import + 2 from second

    def test_city_creation(self, temp_db, sample_parse_result):
        """Test that importer creates city if it doesn't exist."""
        importer = SchedulesImporter(temp_db)

        # Verify no cities exist initially
        cities = temp_db.query(City).all()
        assert len(cities) == 0

        # Import schedules
        importer.import_from_parser(
            city_name="El Centro",
            parse_result=sample_parse_result
        )

        # Verify city was created
        cities = temp_db.query(City).all()
        assert len(cities) == 1
        assert cities[0].name == "El Centro"

    def test_zone_creation(self, temp_db, sample_parse_result):
        """Test that importer creates zones if they don't exist."""
        importer = SchedulesImporter(temp_db)

        # Verify no zones exist initially
        zones = temp_db.query(PickupZone).all()
        assert len(zones) == 0

        # Import schedules
        importer.import_from_parser(
            city_name="El Centro",
            parse_result=sample_parse_result
        )

        # Verify zone was created
        zones = temp_db.query(PickupZone).all()
        assert len(zones) == 1
        assert zones[0].name == "ZONE_A"

    def test_multiple_cities_import(self, temp_db):
        """Test importing schedules for multiple cities."""
        importer = SchedulesImporter(temp_db)

        cities = ["El Centro", "Imperial", "Holtville"]

        for city in cities:
            result = ParseResult()
            result.schedules.append(ScheduleData(
                address=f"{city}, CA",
                day_of_week="TUE",
                collection_type="trash",
                zone=None,
                recurrence="weekly",
                confidence=0.9
            ))
            result.metadata = {"source_format": "test"}

            importer.import_from_parser(city, result)

        # Verify all cities were created
        db_cities = temp_db.query(City).all()
        assert len(db_cities) == 3

        # Verify schedules for each city
        schedules = temp_db.query(Schedule).all()
        assert len(schedules) == 3

    def test_exception_handling_on_import_error(self, temp_db):
        """Test that import errors are handled gracefully."""
        importer = SchedulesImporter(temp_db)

        # Create invalid parse result (missing required fields)
        result = ParseResult()
        result.schedules.append(ScheduleData(
            address="Test",
            day_of_week=None,  # Invalid: None
            collection_type="trash",
            zone=None,
            recurrence="weekly",
            confidence=0.9
        ))
        result.metadata = {}

        # Import should raise an exception but be caught
        with pytest.raises(Exception):
            importer.import_from_parser("Test City", result)

        # Database should be rolled back (no partial data)
        schedules = temp_db.query(Schedule).all()
        assert len(schedules) == 0

    def test_source_metadata_tracking(self, temp_db, sample_parse_result):
        """Test that source metadata is properly tracked."""
        importer = SchedulesImporter(temp_db)

        stats = importer.import_from_parser(
            city_name="El Centro",
            parse_result=sample_parse_result,
            source_url="https://example.com/schedules"
        )

        # Verify source metadata was created
        source = temp_db.query(SourceMetadata).first()
        assert source is not None
        assert source.city == "El Centro"
        assert source.source_url == "https://example.com/schedules"
        assert source.total_records_extracted == 2
        assert source.successful_records == 2
        assert source.failed_records == 0

    def test_reimport_multiple_times(self, temp_db, sample_parse_result):
        """Test that multiple re-imports work correctly."""
        importer = SchedulesImporter(temp_db, allow_duplicates=False)

        # Import 3 times
        for i in range(3):
            stats = importer.import_from_parser(
                city_name="El Centro",
                parse_result=sample_parse_result
            )

            if i == 0:
                # First import creates schedules
                assert stats['schedules_created'] == 2
            else:
                # Subsequent imports skip duplicates
                assert stats['schedules_skipped'] == 2

        # Verify still only 2 schedules
        schedules = temp_db.query(Schedule).all()
        assert len(schedules) == 2

        # But should have 3 source metadata records (one per import)
        sources = temp_db.query(SourceMetadata).all()
        assert len(sources) == 3


class TestImporterDuplicateDetection:
    """Specific tests for duplicate detection logic."""

    def test_duplicate_detection_same_zone_and_day(self, temp_db):
        """Test duplicate detection for same zone and collection day."""
        importer = SchedulesImporter(temp_db, allow_duplicates=False)

        # Create first schedule
        result1 = ParseResult()
        result1.schedules.append(ScheduleData(
            address="Test Address",
            day_of_week="MON",
            collection_type="trash",
            zone="ZONE_A",
            recurrence="weekly",
            confidence=0.9
        ))
        result1.metadata = {}

        stats1 = importer.import_from_parser("Test City", result1)
        assert stats1['schedules_created'] == 1

        # Try to import same schedule again
        result2 = ParseResult()
        result2.schedules.append(ScheduleData(
            address="Different Address",  # Different address
            day_of_week="MON",  # Same day
            collection_type="trash",  # Same type
            zone="ZONE_A",  # Same zone
            recurrence="weekly",
            confidence=0.9
        ))
        result2.metadata = {}

        stats2 = importer.import_from_parser("Test City", result2)
        assert stats2['schedules_skipped'] == 1

        # Should still have only 1 schedule
        schedules = temp_db.query(Schedule).all()
        assert len(schedules) == 1

    def test_no_duplicate_different_zones(self, temp_db):
        """Test that different zones don't cause duplicate detection."""
        importer = SchedulesImporter(temp_db, allow_duplicates=False)

        # Create schedule for ZONE_A
        result1 = ParseResult()
        result1.schedules.append(ScheduleData(
            address="Test",
            day_of_week="MON",
            collection_type="trash",
            zone="ZONE_A",
            recurrence="weekly",
            confidence=0.9
        ))
        result1.metadata = {}

        stats1 = importer.import_from_parser("Test City", result1)

        # Create schedule for ZONE_B (different zone, same day)
        result2 = ParseResult()
        result2.schedules.append(ScheduleData(
            address="Test",
            day_of_week="MON",
            collection_type="trash",
            zone="ZONE_B",  # Different zone
            recurrence="weekly",
            confidence=0.9
        ))
        result2.metadata = {}

        stats2 = importer.import_from_parser("Test City", result2)

        # Should create new schedule (different zone)
        assert stats2['schedules_created'] == 1

        # Should have 2 schedules
        schedules = temp_db.query(Schedule).all()
        assert len(schedules) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
