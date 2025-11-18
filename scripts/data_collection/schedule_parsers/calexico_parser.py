"""
Calexico trash schedule parser.

Extracts trash collection schedules for Calexico, CA.
Data source: City of Calexico Public Works Department
"""
from datetime import datetime
from typing import Any, List
import logging

from .base_parser import (
    BaseScheduleParser,
    ScheduleData,
    ExceptionData,
    ParseResult
)

logger = logging.getLogger(__name__)


class CalexicoParser(BaseScheduleParser):
    """
    Parser for Calexico trash schedules.

    Calexico has zone-based collection Monday-Saturday, 5:00 AM to 8:00 PM.
    Collections take place up to once a week per residence.
    """

    def __init__(self):
        super().__init__(
            city="Calexico",
            source_url="https://www.calexico.ca.gov/departments/public-works"
        )
        # Calexico zones - in production, these would be from city data
        self.zones = {
            "ZONE_A": {"trash": "MON", "recycling": "WED", "green_waste": "FRI"},
            "ZONE_B": {"trash": "TUE", "recycling": "THU", "green_waste": "MON"},
            "ZONE_C": {"trash": "WED", "recycling": "FRI", "green_waste": "TUE"},
            "ZONE_D": {"trash": "THU", "recycling": "MON", "green_waste": "WED"},
            "ZONE_E": {"trash": "FRI", "recycling": "TUE", "green_waste": "THU"},
            "ZONE_F": {"trash": "SAT", "recycling": "WED", "green_waste": "FRI"},
        }

    def fetch_raw_data(self) -> Any:
        """
        Fetch schedule data from Calexico sources.

        For pilot version, use hardcoded zone data.
        In production, this would scrape the city website or use an API.
        """
        logger.info(f"Fetching data from {self.source_url}")

        return {
            "zones": self.zones,
            "holidays": [
                {"date": "2025-01-01", "name": "New Year's Day", "delay_days": 1},
                {"date": "2025-05-26", "name": "Memorial Day", "delay_days": 1},
                {"date": "2025-07-04", "name": "Independence Day", "delay_days": 1},
                {"date": "2025-09-01", "name": "Labor Day", "delay_days": 1},
                {"date": "2025-11-27", "name": "Thanksgiving", "delay_days": 1},
                {"date": "2025-12-25", "name": "Christmas", "delay_days": 1},
            ]
        }

    def parse_raw_data(self, raw_data: Any) -> ParseResult:
        """
        Parse Calexico schedule data.

        Args:
            raw_data: Zone configuration and holiday data

        Returns:
            ParseResult with schedules and exceptions
        """
        result = ParseResult()

        try:
            zones = raw_data.get("zones", {})
            holidays = raw_data.get("holidays", [])

            # Parse zone schedules
            for zone_name, zone_schedule in zones.items():
                for collection_type, day in zone_schedule.items():
                    schedule = ScheduleData(
                        address=f"Calexico, {zone_name}",
                        day_of_week=day,
                        collection_type=collection_type,
                        zone=zone_name,
                        recurrence="weekly",
                        confidence=0.95,
                        effective_date=datetime(2025, 1, 1),
                        next_pickup_date=self.calculate_next_pickup(day)
                    )
                    result.schedules.append(schedule)

            # Parse holiday exceptions
            for holiday in holidays:
                try:
                    exception_date = datetime.strptime(holiday["date"], "%Y-%m-%d")
                    delay_days = holiday.get("delay_days", 0)

                    rescheduled_date = None
                    if delay_days > 0:
                        from datetime import timedelta
                        rescheduled_date = exception_date + timedelta(days=delay_days)

                    exception = ExceptionData(
                        exception_date=exception_date,
                        rescheduled_date=rescheduled_date,
                        is_cancelled=holiday.get("cancelled", False),
                        reason=holiday.get("name", "Holiday"),
                        notes=f"Calexico city holiday: {holiday.get('name', 'Unknown')}"
                    )
                    result.exceptions.append(exception)
                except Exception as e:
                    result.warnings.append(f"Failed to parse holiday {holiday}: {e}")

            # Add metadata
            result.metadata["total_zones"] = len(zones)
            result.metadata["total_schedules"] = len(result.schedules)
            result.metadata["total_exceptions"] = len(result.exceptions)

            logger.info(f"Parsed {len(result.schedules)} schedules and {len(result.exceptions)} exceptions")

        except Exception as e:
            result.errors.append(f"Failed to parse Calexico data: {e}")
            logger.error(f"Parse error: {e}")

        return result

    def match_address_to_zone(self, address: str) -> str:
        """
        Match an address to a pickup zone.

        For pilot version, uses simple heuristics.
        In production, would use GIS polygon matching.

        Args:
            address: Full address string

        Returns:
            Zone identifier (ZONE_A, ZONE_B, etc.)
        """
        address_upper = address.upper()

        # Simple heuristic based on street names
        if any(st in address_upper for st in ["IMPERIAL", "1ST", "FIRST"]):
            return "ZONE_A"
        elif any(st in address_upper for st in ["2ND", "SECOND", "3RD", "THIRD"]):
            return "ZONE_B"
        elif any(st in address_upper for st in ["4TH", "FOURTH", "5TH", "FIFTH"]):
            return "ZONE_C"
        elif any(st in address_upper for st in ["6TH", "SIXTH", "7TH", "SEVENTH"]):
            return "ZONE_D"
        elif any(st in address_upper for st in ["ROCKWOOD", "BORDER"]):
            return "ZONE_E"
        else:
            return "ZONE_F"

    def get_schedule_for_address(self, address: str) -> List[ScheduleData]:
        """
        Get schedule for a specific address.

        Args:
            address: Full address string

        Returns:
            List of ScheduleData for the address
        """
        zone = self.match_address_to_zone(address)
        zone_schedule = self.zones.get(zone, {})

        schedules = []
        for collection_type, day in zone_schedule.items():
            schedule = ScheduleData(
                address=address,
                day_of_week=day,
                collection_type=collection_type,
                zone=zone,
                recurrence="weekly",
                confidence=0.95,
                next_pickup_date=self.calculate_next_pickup(day)
            )
            schedules.append(schedule)

        return schedules
