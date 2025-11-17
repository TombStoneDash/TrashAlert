"""
Base parser interface for trash schedule extraction.

All city-specific parsers should inherit from BaseScheduleParser.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class CollectionType(Enum):
    """Types of waste collection."""
    TRASH = "trash"
    RECYCLING = "recycling"
    GREEN_WASTE = "green_waste"
    BULK = "bulk"


class DayOfWeek(Enum):
    """Days of the week."""
    MONDAY = "MON"
    TUESDAY = "TUE"
    WEDNESDAY = "WED"
    THURSDAY = "THU"
    FRIDAY = "FRI"
    SATURDAY = "SAT"
    SUNDAY = "SUN"


class Recurrence(Enum):
    """Collection recurrence patterns."""
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


@dataclass
class ScheduleData:
    """Normalized schedule data from parser."""
    address: str  # Full normalized address
    day_of_week: str  # MON, TUE, WED, THU, FRI, SAT, SUN
    collection_type: str  # trash, recycling, green_waste, bulk
    zone: Optional[str] = None  # Pickup zone if applicable
    recurrence: str = "weekly"  # weekly, biweekly, monthly
    confidence: float = 1.0  # 0.0 - 1.0
    effective_date: Optional[datetime] = None
    next_pickup_date: Optional[datetime] = None  # Calculated next pickup


@dataclass
class ExceptionData:
    """Holiday or exception data from parser."""
    exception_date: datetime  # The holiday/exception date
    rescheduled_date: Optional[datetime] = None  # New pickup date
    is_cancelled: bool = False  # True if cancelled, not rescheduled
    reason: str = ""  # e.g., "Christmas", "Thanksgiving"
    notes: str = ""


@dataclass
class ParseResult:
    """Result of parsing operation."""
    schedules: List[ScheduleData] = field(default_factory=list)
    exceptions: List[ExceptionData] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class BaseScheduleParser(ABC):
    """
    Base class for all schedule parsers.

    Each city should implement its own parser by inheriting from this class.
    """

    def __init__(self, city: str, source_url: Optional[str] = None):
        """
        Initialize parser.

        Args:
            city: City name
            source_url: URL or path to data source
        """
        self.city = city
        self.source_url = source_url
        self.parser_name = self.__class__.__name__
        self.parser_version = "1.0.0"

    @abstractmethod
    def fetch_raw_data(self) -> Any:
        """
        Fetch raw data from source (PDF, HTML, API, etc.).

        Returns:
            Raw data in format specific to parser

        Raises:
            Exception: If fetch fails
        """
        pass

    @abstractmethod
    def parse_raw_data(self, raw_data: Any) -> ParseResult:
        """
        Parse raw data into normalized schedule format.

        Args:
            raw_data: Raw data from fetch_raw_data()

        Returns:
            ParseResult with schedules, exceptions, metadata
        """
        pass

    def normalize_day(self, day: str) -> str:
        """
        Normalize day string to standard format (MON, TUE, etc.).

        Args:
            day: Day string (various formats)

        Returns:
            Normalized day (MON, TUE, WED, THU, FRI, SAT, SUN)

        Raises:
            ValueError: If day cannot be normalized
        """
        day_upper = day.strip().upper()

        # Map full names and common variations
        day_map = {
            "MONDAY": "MON",
            "TUESDAY": "TUE",
            "WEDNESDAY": "WED",
            "THURSDAY": "THU",
            "FRIDAY": "FRI",
            "SATURDAY": "SAT",
            "SUNDAY": "SUN",
            "MON": "MON",
            "TUES": "TUE",
            "TUE": "TUE",
            "WED": "WED",
            "THUR": "THU",
            "THURS": "THU",
            "THU": "THU",
            "FRI": "FRI",
            "SAT": "SAT",
            "SUN": "SUN",
        }

        if day_upper in day_map:
            return day_map[day_upper]

        raise ValueError(f"Cannot normalize day: {day}")

    def normalize_collection_type(self, collection_type: str) -> str:
        """
        Normalize collection type to standard format.

        Args:
            collection_type: Collection type string

        Returns:
            Normalized type (trash, recycling, green_waste, bulk)

        Raises:
            ValueError: If type cannot be normalized
        """
        type_upper = collection_type.strip().upper()

        # Map common variations
        type_map = {
            "TRASH": "trash",
            "GARBAGE": "trash",
            "WASTE": "trash",
            "RECYCLING": "recycling",
            "RECYCLE": "recycling",
            "GREEN WASTE": "green_waste",
            "GREEN": "green_waste",
            "YARD WASTE": "green_waste",
            "YARD": "green_waste",
            "BULK": "bulk",
            "BULK PICKUP": "bulk",
        }

        if type_upper in type_map:
            return type_map[type_upper]

        raise ValueError(f"Cannot normalize collection type: {collection_type}")

    def calculate_next_pickup(self, day_of_week: str, reference_date: Optional[datetime] = None) -> datetime:
        """
        Calculate next pickup date based on day of week.

        Args:
            day_of_week: Day (MON, TUE, WED, etc.)
            reference_date: Reference date (default: today)

        Returns:
            Next pickup datetime
        """
        if reference_date is None:
            reference_date = datetime.now()

        # Map day abbreviation to weekday number (0=Monday, 6=Sunday)
        day_map = {
            "MON": 0, "TUE": 1, "WED": 2, "THU": 3,
            "FRI": 4, "SAT": 5, "SUN": 6
        }

        target_weekday = day_map.get(day_of_week)
        if target_weekday is None:
            raise ValueError(f"Invalid day_of_week: {day_of_week}")

        current_weekday = reference_date.weekday()
        days_ahead = (target_weekday - current_weekday) % 7

        # If it's the same day, get next week's occurrence
        if days_ahead == 0:
            days_ahead = 7

        from datetime import timedelta
        next_pickup = reference_date + timedelta(days=days_ahead)
        return next_pickup.replace(hour=0, minute=0, second=0, microsecond=0)

    def run(self) -> ParseResult:
        """
        Execute full parsing pipeline: fetch → parse → normalize.

        Returns:
            ParseResult with all extracted data
        """
        result = ParseResult()

        try:
            # Fetch raw data
            raw_data = self.fetch_raw_data()
            result.metadata['fetch_success'] = True
            result.metadata['fetch_timestamp'] = datetime.now().isoformat()

            # Parse data
            parse_result = self.parse_raw_data(raw_data)

            # Merge results
            result.schedules = parse_result.schedules
            result.exceptions = parse_result.exceptions
            result.errors = parse_result.errors
            result.warnings = parse_result.warnings
            result.metadata.update(parse_result.metadata)

            # Add parser metadata
            result.metadata['parser_name'] = self.parser_name
            result.metadata['parser_version'] = self.parser_version
            result.metadata['city'] = self.city
            result.metadata['source_url'] = self.source_url

        except Exception as e:
            result.errors.append(f"Parser execution failed: {str(e)}")
            result.metadata['fetch_success'] = False

        return result
