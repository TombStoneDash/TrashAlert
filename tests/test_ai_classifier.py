"""Unit tests for AI schedule classifier."""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.ai_classifier import (
    AIScheduleClassifier,
    ClassifiedSchedule,
    ScheduleException,
    PickupDay,
    Frequency,
    CollectionType,
    classify_schedule_text,
)


class TestAIScheduleClassifier:
    """Test suite for AI schedule classifier."""

    @pytest.fixture
    def mock_openai_response(self):
        """Create a mock OpenAI response."""
        def create_response(schedules):
            mock_choice = Mock()
            mock_choice.message.content = json.dumps({"schedules": schedules})

            mock_response = Mock()
            mock_response.choices = [mock_choice]

            return mock_response

        return create_response

    def test_simple_weekly_trash(self, mock_openai_response):
        """Test classification of simple weekly trash schedule."""
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            mock_client.chat.completions.create.return_value = mock_openai_response([
                {
                    "collection_type": "trash",
                    "pickup_day": "MON",
                    "frequency": "weekly",
                    "exceptions": [],
                    "confidence": 0.95
                }
            ])

            classifier = AIScheduleClassifier(api_key="test-key")
            results = classifier.classify("Trash pickup is every Monday")

            assert len(results) == 1
            schedule = results[0]
            assert schedule.collection_type == "trash"
            assert schedule.pickup_day == "MON"
            assert schedule.frequency == "weekly"
            assert len(schedule.exceptions) == 0
            assert schedule.confidence == 0.95

    def test_biweekly_recycling(self, mock_openai_response):
        """Test classification of biweekly recycling schedule."""
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            mock_client.chat.completions.create.return_value = mock_openai_response([
                {
                    "collection_type": "recycling",
                    "pickup_day": "WED",
                    "frequency": "biweekly",
                    "exceptions": [],
                    "confidence": 0.92
                }
            ])

            classifier = AIScheduleClassifier(api_key="test-key")
            results = classifier.classify("Recycling on Wednesdays every other week")

            assert len(results) == 1
            schedule = results[0]
            assert schedule.collection_type == "recycling"
            assert schedule.pickup_day == "WED"
            assert schedule.frequency == "biweekly"

    def test_multiple_collection_types(self, mock_openai_response):
        """Test classification of multiple collection types."""
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            mock_client.chat.completions.create.return_value = mock_openai_response([
                {
                    "collection_type": "trash",
                    "pickup_day": "TUE",
                    "frequency": "weekly",
                    "exceptions": [],
                    "confidence": 0.93
                },
                {
                    "collection_type": "recycling",
                    "pickup_day": "FRI",
                    "frequency": "biweekly",
                    "exceptions": [],
                    "confidence": 0.90
                }
            ])

            classifier = AIScheduleClassifier(api_key="test-key")
            results = classifier.classify(
                "Trash pickup is Tuesday, recycling is Friday every other week"
            )

            assert len(results) == 2

            trash_schedule = results[0]
            assert trash_schedule.collection_type == "trash"
            assert trash_schedule.pickup_day == "TUE"

            recycling_schedule = results[1]
            assert recycling_schedule.collection_type == "recycling"
            assert recycling_schedule.pickup_day == "FRI"
            assert recycling_schedule.frequency == "biweekly"

    def test_schedule_with_holiday_exception(self, mock_openai_response):
        """Test classification with holiday exception."""
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            mock_client.chat.completions.create.return_value = mock_openai_response([
                {
                    "collection_type": "trash",
                    "pickup_day": "THU",
                    "frequency": "weekly",
                    "exceptions": [
                        {
                            "exception_date": "2025-12-25",
                            "rescheduled_date": "2025-12-26",
                            "is_cancelled": False,
                            "reason": "Christmas",
                            "notes": "Moved to Friday"
                        }
                    ],
                    "confidence": 0.88
                }
            ])

            classifier = AIScheduleClassifier(api_key="test-key")
            results = classifier.classify(
                "Garbage collection Thursday mornings, no pickup on Christmas, moved to Friday"
            )

            assert len(results) == 1
            schedule = results[0]
            assert schedule.collection_type == "trash"
            assert schedule.pickup_day == "THU"
            assert len(schedule.exceptions) == 1

            exception = schedule.exceptions[0]
            assert exception.exception_date == "2025-12-25"
            assert exception.rescheduled_date == "2025-12-26"
            assert exception.is_cancelled is False
            assert exception.reason == "Christmas"

    def test_cancelled_pickup(self, mock_openai_response):
        """Test classification with cancelled pickup."""
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            mock_client.chat.completions.create.return_value = mock_openai_response([
                {
                    "collection_type": "trash",
                    "pickup_day": "FRI",
                    "frequency": "weekly",
                    "exceptions": [
                        {
                            "exception_date": "2025-07-04",
                            "rescheduled_date": None,
                            "is_cancelled": True,
                            "reason": "Independence Day",
                            "notes": "No pickup on holiday"
                        }
                    ],
                    "confidence": 0.85
                }
            ])

            classifier = AIScheduleClassifier(api_key="test-key")
            results = classifier.classify(
                "Trash is Friday, no pickup on Independence Day"
            )

            assert len(results) == 1
            schedule = results[0]
            assert len(schedule.exceptions) == 1

            exception = schedule.exceptions[0]
            assert exception.is_cancelled is True
            assert exception.rescheduled_date is None

    def test_uncertain_classification(self, mock_openai_response):
        """Test classification with low confidence."""
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            mock_client.chat.completions.create.return_value = mock_openai_response([
                {
                    "collection_type": "trash",
                    "pickup_day": "TUE",
                    "frequency": "weekly",
                    "exceptions": [],
                    "confidence": 0.4
                }
            ])

            classifier = AIScheduleClassifier(api_key="test-key")
            results = classifier.classify(
                "I think it's Tuesday or Wednesday for trash, not really sure"
            )

            assert len(results) == 1
            schedule = results[0]
            assert schedule.confidence < 0.5
            assert schedule.pickup_day == "TUE"

    def test_green_waste_collection(self, mock_openai_response):
        """Test classification of green waste collection."""
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            mock_client.chat.completions.create.return_value = mock_openai_response([
                {
                    "collection_type": "green_waste",
                    "pickup_day": "WED",
                    "frequency": "weekly",
                    "exceptions": [],
                    "confidence": 0.90
                }
            ])

            classifier = AIScheduleClassifier(api_key="test-key")
            results = classifier.classify("Yard waste pickup every Wednesday")

            assert len(results) == 1
            schedule = results[0]
            assert schedule.collection_type == "green_waste"
            assert schedule.pickup_day == "WED"

    def test_to_dict_conversion(self):
        """Test conversion of ClassifiedSchedule to dictionary."""
        exception = ScheduleException(
            exception_date="2025-12-25",
            rescheduled_date="2025-12-26",
            is_cancelled=False,
            reason="Christmas",
            notes="Moved to Friday"
        )

        schedule = ClassifiedSchedule(
            collection_type="trash",
            pickup_day="MON",
            frequency="weekly",
            exceptions=[exception],
            confidence=0.95,
            raw_text="Trash pickup is every Monday, except Christmas"
        )

        schedule_dict = schedule.to_dict()

        assert schedule_dict["collection_type"] == "trash"
        assert schedule_dict["pickup_day"] == "MON"
        assert schedule_dict["frequency"] == "weekly"
        assert schedule_dict["confidence"] == 0.95
        assert len(schedule_dict["exceptions"]) == 1
        assert schedule_dict["exceptions"][0]["reason"] == "Christmas"

    def test_no_api_key_raises_error(self):
        """Test that missing API key raises error."""
        with patch.dict('os.environ', {}, clear=True):
            classifier = AIScheduleClassifier()

            with pytest.raises(ValueError, match="OpenAI API key not configured"):
                classifier.classify("Trash pickup is Monday")

    def test_invalid_json_response(self, mock_openai_response):
        """Test handling of invalid JSON response."""
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            # Create invalid JSON response
            mock_choice = Mock()
            mock_choice.message.content = "Not valid JSON"
            mock_response = Mock()
            mock_response.choices = [mock_choice]

            mock_client.chat.completions.create.return_value = mock_response

            classifier = AIScheduleClassifier(api_key="test-key")

            with pytest.raises(Exception, match="Invalid JSON response"):
                classifier.classify("Trash pickup is Monday")

    def test_context_passed_to_api(self, mock_openai_response):
        """Test that context is properly passed to API."""
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            mock_client.chat.completions.create.return_value = mock_openai_response([
                {
                    "collection_type": "trash",
                    "pickup_day": "MON",
                    "frequency": "weekly",
                    "exceptions": [],
                    "confidence": 0.95
                }
            ])

            classifier = AIScheduleClassifier(api_key="test-key")
            context = {"city": "San Diego", "year": 2025}
            results = classifier.classify("Trash pickup is Monday", context=context)

            # Check that API was called with context in message
            call_args = mock_client.chat.completions.create.call_args
            messages = call_args.kwargs["messages"]
            user_message = messages[1]["content"]

            assert "San Diego" in user_message
            assert "2025" in user_message

    def test_classification_patterns(self, mock_openai_response):
        """Test various common schedule description patterns."""
        test_cases = [
            {
                "input": "Every Monday morning",
                "expected": {
                    "collection_type": "trash",
                    "pickup_day": "MON",
                    "frequency": "weekly"
                }
            },
            {
                "input": "Bi-weekly on Thursdays",
                "expected": {
                    "collection_type": "trash",
                    "pickup_day": "THU",
                    "frequency": "biweekly"
                }
            },
            {
                "input": "Tuesdays and Fridays",
                "expected_count": 2
            },
            {
                "input": "First Monday of the month",
                "expected": {
                    "collection_type": "trash",
                    "pickup_day": "MON",
                    "frequency": "monthly"
                }
            }
        ]

        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            classifier = AIScheduleClassifier(api_key="test-key")

            for case in test_cases:
                if "expected_count" in case:
                    # Mock multiple schedules
                    mock_client.chat.completions.create.return_value = mock_openai_response([
                        {
                            "collection_type": "trash",
                            "pickup_day": "TUE",
                            "frequency": "weekly",
                            "exceptions": [],
                            "confidence": 0.9
                        },
                        {
                            "collection_type": "trash",
                            "pickup_day": "FRI",
                            "frequency": "weekly",
                            "exceptions": [],
                            "confidence": 0.9
                        }
                    ])
                    results = classifier.classify(case["input"])
                    assert len(results) == case["expected_count"]
                else:
                    # Mock single schedule
                    expected = case["expected"]
                    mock_client.chat.completions.create.return_value = mock_openai_response([
                        {
                            **expected,
                            "exceptions": [],
                            "confidence": 0.9
                        }
                    ])
                    results = classifier.classify(case["input"])
                    assert len(results) >= 1
                    assert results[0].collection_type == expected["collection_type"]
                    assert results[0].pickup_day == expected["pickup_day"]
                    assert results[0].frequency == expected["frequency"]


class TestScheduleDataClasses:
    """Test data classes."""

    def test_schedule_exception_creation(self):
        """Test creating a ScheduleException."""
        exception = ScheduleException(
            exception_date="2025-12-25",
            rescheduled_date="2025-12-26",
            is_cancelled=False,
            reason="Christmas",
            notes="Moved to Friday"
        )

        assert exception.exception_date == "2025-12-25"
        assert exception.rescheduled_date == "2025-12-26"
        assert exception.is_cancelled is False
        assert exception.reason == "Christmas"

    def test_classified_schedule_creation(self):
        """Test creating a ClassifiedSchedule."""
        schedule = ClassifiedSchedule(
            collection_type="trash",
            pickup_day="MON",
            frequency="weekly",
            exceptions=[],
            confidence=0.95,
            raw_text="Trash pickup is every Monday"
        )

        assert schedule.collection_type == "trash"
        assert schedule.pickup_day == "MON"
        assert schedule.frequency == "weekly"
        assert schedule.confidence == 0.95
        assert len(schedule.exceptions) == 0

    def test_enums(self):
        """Test enum values."""
        assert PickupDay.MONDAY.value == "MON"
        assert PickupDay.WEDNESDAY.value == "WED"
        assert Frequency.WEEKLY.value == "weekly"
        assert Frequency.BIWEEKLY.value == "biweekly"
        assert CollectionType.TRASH.value == "trash"
        assert CollectionType.RECYCLING.value == "recycling"
