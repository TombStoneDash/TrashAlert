"""
AI-powered natural language schedule classifier.

This module provides functionality to classify messy natural language text
describing trash pickup schedules into structured schedule objects.
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

import openai
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PickupDay(str, Enum):
    """Valid pickup days."""
    MONDAY = "MON"
    TUESDAY = "TUE"
    WEDNESDAY = "WED"
    THURSDAY = "THU"
    FRIDAY = "FRI"
    SATURDAY = "SAT"
    SUNDAY = "SUN"


class Frequency(str, Enum):
    """Valid pickup frequencies."""
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


class CollectionType(str, Enum):
    """Valid collection types."""
    TRASH = "trash"
    RECYCLING = "recycling"
    GREEN_WASTE = "green_waste"
    BULK = "bulk"


@dataclass
class ScheduleException:
    """Represents an exception to the regular schedule."""
    exception_date: str  # ISO format date
    rescheduled_date: Optional[str] = None  # ISO format date
    is_cancelled: bool = False
    reason: str = ""
    notes: str = ""


@dataclass
class ClassifiedSchedule:
    """Structured schedule object extracted from natural language."""
    collection_type: str  # trash, recycling, green_waste, bulk
    pickup_day: str  # MON, TUE, WED, THU, FRI, SAT, SUN
    frequency: str  # weekly, biweekly, monthly
    exceptions: List[ScheduleException]
    confidence: float  # 0.0 to 1.0
    raw_text: str  # Original input text

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        result['exceptions'] = [asdict(exc) for exc in self.exceptions]
        return result


class AIClassifierRequest(BaseModel):
    """Request model for AI classification."""
    text: str = Field(..., min_length=1, max_length=2000, description="Natural language schedule description")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context (city, address, etc.)")


class AIClassifierResponse(BaseModel):
    """Response model for AI classification."""
    schedules: List[Dict[str, Any]] = Field(default_factory=list, description="List of classified schedules")
    success: bool = Field(..., description="Whether classification was successful")
    error: Optional[str] = Field(None, description="Error message if classification failed")
    cached: bool = Field(False, description="Whether result was returned from cache")


class AIScheduleClassifier:
    """
    AI-powered schedule classifier using OpenAI API.

    Extracts structured schedule information from natural language text.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        Initialize the classifier.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: OpenAI model to use (default: gpt-4o-mini for cost efficiency)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("No OpenAI API key provided. AI classification will not work.")

        self.model = model
        self.client = openai.OpenAI(api_key=self.api_key) if self.api_key else None

        # System prompt for the AI
        self.system_prompt = """You are a specialized AI assistant for classifying trash pickup schedules.

Your task is to extract structured schedule information from natural language text.

Extract the following information:
1. **Collection Type**: trash, recycling, green_waste, or bulk
2. **Pickup Day**: MON, TUE, WED, THU, FRI, SAT, SUN
3. **Frequency**: weekly, biweekly, or monthly
4. **Exceptions**: holidays or special dates when pickup is cancelled or rescheduled
5. **Confidence**: your confidence level (0.0 to 1.0) in the extraction

**Important Rules:**
- If multiple collection types are mentioned, create separate schedule entries for each
- Default frequency is "weekly" unless specified otherwise
- "Every other week" or "bi-weekly" means biweekly
- Common holidays: Thanksgiving, Christmas, New Year's Day, Independence Day, Memorial Day, Labor Day
- If pickup is moved due to holiday, capture both exception_date and rescheduled_date
- Be conservative with confidence: use 0.9+ only for very clear statements

**Response Format:**
Return a JSON object with this structure:
{
  "schedules": [
    {
      "collection_type": "trash",
      "pickup_day": "MON",
      "frequency": "weekly",
      "exceptions": [
        {
          "exception_date": "2025-12-25",
          "rescheduled_date": "2025-12-26",
          "is_cancelled": false,
          "reason": "Christmas",
          "notes": ""
        }
      ],
      "confidence": 0.95
    }
  ]
}

**Examples:**

Input: "Trash pickup is every Monday. Recycling is on Wednesdays every other week."
Output:
{
  "schedules": [
    {
      "collection_type": "trash",
      "pickup_day": "MON",
      "frequency": "weekly",
      "exceptions": [],
      "confidence": 0.95
    },
    {
      "collection_type": "recycling",
      "pickup_day": "WED",
      "frequency": "biweekly",
      "exceptions": [],
      "confidence": 0.95
    }
  ]
}

Input: "We have garbage collection on Thursday mornings, usually weekly. No pickup on Christmas, moved to Friday that week."
Output:
{
  "schedules": [
    {
      "collection_type": "trash",
      "pickup_day": "THU",
      "frequency": "weekly",
      "exceptions": [
        {
          "exception_date": "2025-12-25",
          "rescheduled_date": "2025-12-26",
          "is_cancelled": false,
          "reason": "Christmas",
          "notes": "Moved to Friday"
        }
      ],
      "confidence": 0.85
    }
  ]
}

Input: "I think it's Tuesday or Wednesday for trash, not really sure"
Output:
{
  "schedules": [
    {
      "collection_type": "trash",
      "pickup_day": "TUE",
      "frequency": "weekly",
      "exceptions": [],
      "confidence": 0.4
    }
  ]
}

Now classify the following schedule description:"""

    def classify(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[ClassifiedSchedule]:
        """
        Classify natural language text into structured schedule objects.

        Args:
            text: Natural language schedule description
            context: Optional context (city, address, current year, etc.)

        Returns:
            List of ClassifiedSchedule objects

        Raises:
            ValueError: If API key is not configured
            Exception: If API call fails
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY environment variable.")

        # Build user message with context
        user_message = text
        if context:
            user_message = f"Context: {json.dumps(context)}\n\nSchedule description: {text}"

        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.1,  # Low temperature for consistent extraction
                max_tokens=1000,
                response_format={"type": "json_object"}  # Force JSON response
            )

            # Parse response
            content = response.choices[0].message.content
            logger.debug(f"AI response: {content}")

            result = json.loads(content)
            schedules = []

            for schedule_data in result.get("schedules", []):
                # Parse exceptions
                exceptions = []
                for exc_data in schedule_data.get("exceptions", []):
                    exceptions.append(ScheduleException(
                        exception_date=exc_data.get("exception_date", ""),
                        rescheduled_date=exc_data.get("rescheduled_date"),
                        is_cancelled=exc_data.get("is_cancelled", False),
                        reason=exc_data.get("reason", ""),
                        notes=exc_data.get("notes", "")
                    ))

                # Create ClassifiedSchedule object
                schedule = ClassifiedSchedule(
                    collection_type=schedule_data.get("collection_type", "trash"),
                    pickup_day=schedule_data.get("pickup_day", "MON"),
                    frequency=schedule_data.get("frequency", "weekly"),
                    exceptions=exceptions,
                    confidence=schedule_data.get("confidence", 0.5),
                    raw_text=text
                )
                schedules.append(schedule)

            logger.info(f"Successfully classified {len(schedules)} schedules from text: {text[:100]}...")
            return schedules

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            raise Exception(f"Invalid JSON response from AI: {e}")
        except Exception as e:
            logger.error(f"AI classification failed: {e}")
            raise


# Global classifier instance
_classifier: Optional[AIScheduleClassifier] = None


def get_classifier() -> AIScheduleClassifier:
    """Get or create the global classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = AIScheduleClassifier()
    return _classifier


def classify_schedule_text(text: str, context: Optional[Dict[str, Any]] = None) -> List[ClassifiedSchedule]:
    """
    Convenience function to classify schedule text.

    Args:
        text: Natural language schedule description
        context: Optional context

    Returns:
        List of ClassifiedSchedule objects
    """
    classifier = get_classifier()
    return classifier.classify(text, context)
