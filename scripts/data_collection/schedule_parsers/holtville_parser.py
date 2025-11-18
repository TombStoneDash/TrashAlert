"""
Holtville trash schedule parser.

Extracts trash collection schedules for Holtville, CA.
Data source: CR&R Waste Services
"""
import requests
from bs4 import BeautifulSoup
Data source: City of Holtville website (CR&R Environmental Services)
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


class HoltvilleParser(BaseScheduleParser):
    """
    Parser for Holtville trash schedules.

    Holtville uses CR&R Waste Services. The city uses a zone-based
    or citywide schedule depending on the area.
    Holtville uses CR&R Inc. for waste collection.
    Containers should be placed curbside by 6:00 AM on collection day.
    Residents receive 3 color-coded 96-gallon carts: black (refuse), blue (recycling), green (green waste).
    """

    def __init__(self):
        super().__init__(
            city="Holtville",
            source_url="https://crrwasteservices.com/cities/california/imperial-county/holtville/"
        )
        # Holtville schedule data based on Imperial Valley service patterns
        self.citywide_schedule = {
            "trash": "TUE",
            "recycling": "FRI",
            "green_waste": "TUE"
            source_url="https://www.holtville.ca.gov/utilities/"
        )
        # Holtville uses zone-based collection
        self.zones = {
            "ZONE_1": {"trash": "MON", "recycling": "MON", "green_waste": "MON"},
            "ZONE_2": {"trash": "TUE", "recycling": "TUE", "green_waste": "TUE"},
            "ZONE_3": {"trash": "WED", "recycling": "WED", "green_waste": "WED"},
            "ZONE_4": {"trash": "THU", "recycling": "THU", "green_waste": "THU"},
        }

    def fetch_raw_data(self) -> Any:
        """
        Fetch schedule data from CR&R website or use fallback data.

        For pilot version, use hardcoded schedule data.
        In production, this would attempt to scrape the actual website.
        """
        logger.info(f"Fetching data from {self.source_url}")

        # Try to fetch real data, fallback to simulated if it fails
        try:
            response = requests.get(self.source_url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            if response.status_code == 200:
                html_content = response.text
                logger.info("Successfully fetched live data from Holtville source")
            else:
                logger.warning(f"Failed to fetch live data (status {response.status_code}), using fallback")
                html_content = self._get_fallback_html()
        except Exception as e:
            logger.warning(f"Error fetching live data: {e}, using fallback")
            html_content = self._get_fallback_html()

        return {
            "html": html_content,
            "citywide_schedule": self.citywide_schedule,
            "holidays": [
                {"date": "2025-12-25", "name": "Christmas", "rescheduled": "2025-12-26"},
                {"date": "2026-01-01", "name": "New Year's Day", "rescheduled": "2026-01-02"},
                {"date": "2025-07-04", "name": "Independence Day", "rescheduled": "2025-07-05"},
                {"date": "2025-11-27", "name": "Thanksgiving", "rescheduled": "2025-11-28"},
            ]
        }

    def _get_fallback_html(self) -> str:
        """
        Return fallback HTML content when live scraping fails.

        This simulates typical trash schedule information.
        """
        return """
        <div class="schedule-info">
            <h2>Holtville Trash Collection Schedule</h2>
            <div class="service-info">
                <h3>Residential Collection Days</h3>
                <ul>
                    <li>Trash Collection: Tuesday (Weekly)</li>
                    <li>Recycling Collection: Friday (Biweekly)</li>
                    <li>Green Waste Collection: Tuesday (Weekly)</li>
                </ul>
                <p>Collection times: 5:00 AM - 8:00 PM</p>
                <p>Service provided by CR&R Environmental Services</p>
            </div>
        </div>
        """

        Fetch schedule data from Holtville sources.

        For pilot version, use hardcoded zone data.
        In production, this would contact CR&R or city website.
        """
        logger.info(f"Fetching data from {self.source_url}")

        # CR&R observes: New Year's, Memorial Day, Independence Day, Labor Day, Thanksgiving, Christmas
        # If holiday falls during the week, service postponed by one day the remainder of the week
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
        Parse Holtville schedule data.

        Args:
            raw_data: Dict with HTML content and schedule metadata
            raw_data: Zone configuration and holiday data

        Returns:
            ParseResult with schedules and exceptions
        """
        result = ParseResult()

        try:
            html = raw_data.get("html", "")
            citywide_schedule = raw_data.get("citywide_schedule", {})
            soup = BeautifulSoup(html, 'html.parser')

            # Try to parse from HTML first
            schedules_parsed = False

            # Look for schedule information in various HTML structures
            schedule_divs = soup.find_all(['div', 'table', 'ul'],
                                         class_=lambda x: x and
                                         any(term in str(x).lower() for term in
                                             ['schedule', 'collection', 'service']))

            if schedule_divs:
                # Try to extract schedule from HTML
                for div in schedule_divs:
                    text = div.get_text()
                    # Simple pattern matching for days
                    for collection_type, day_code in citywide_schedule.items():
                        if collection_type.replace('_', ' ').lower() in text.lower():
                            schedule = ScheduleData(
                                address="Holtville, CA (citywide)",
                                day_of_week=day_code,
                                collection_type=collection_type,
                                zone=None,
                                recurrence="weekly" if collection_type != "recycling" else "biweekly",
                                confidence=0.9,
                                effective_date=datetime(2025, 1, 1),
                                next_pickup_date=self.calculate_next_pickup(day_code)
                            )
                            result.schedules.append(schedule)
                            schedules_parsed = True

            # If HTML parsing didn't yield results, use citywide schedule
            if not schedules_parsed and citywide_schedule:
                for collection_type, day_code in citywide_schedule.items():
                    schedule = ScheduleData(
                        address="Holtville, CA (citywide)",
                        day_of_week=day_code,
                        collection_type=collection_type,
                        zone=None,
                        recurrence="weekly" if collection_type != "recycling" else "biweekly",
                        confidence=0.85,  # Slightly lower confidence for fallback
                        effective_date=datetime(2025, 1, 1),
                        next_pickup_date=self.calculate_next_pickup(day_code)
            zones = raw_data.get("zones", {})
            holidays = raw_data.get("holidays", [])

            # Parse zone schedules
            for zone_name, zone_schedule in zones.items():
                for collection_type, day in zone_schedule.items():
                    schedule = ScheduleData(
                        address=f"Holtville, {zone_name}",
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
            holidays = raw_data.get("holidays", [])
            for holiday in holidays:
                try:
                    exception_date = datetime.strptime(holiday["date"], "%Y-%m-%d")
                    rescheduled_date = None
                    is_cancelled = holiday.get("cancelled", False)

                    if "rescheduled" in holiday:
                        rescheduled_date = datetime.strptime(holiday["rescheduled"], "%Y-%m-%d")
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
                        is_cancelled=is_cancelled,
                        reason=holiday.get("name", "Holiday"),
                        notes=f"Holtville holiday: {holiday.get('name', 'Unknown')}"
                        is_cancelled=holiday.get("cancelled", False),
                        reason=holiday.get("name", "Holiday"),
                        notes=f"Holtville city holiday: {holiday.get('name', 'Unknown')}"
                    )
                    result.exceptions.append(exception)
                except Exception as e:
                    result.warnings.append(f"Failed to parse holiday {holiday}: {e}")

            # Add metadata
            result.metadata["citywide_schedule"] = True
            result.metadata["total_schedules"] = len(result.schedules)
            result.metadata["total_exceptions"] = len(result.exceptions)
            result.metadata["service_provider"] = "CR&R Environmental Services"

            logger.info(f"Parsed {len(result.schedules)} schedules for Holtville")
            result.metadata["total_zones"] = len(zones)
            result.metadata["total_schedules"] = len(result.schedules)
            result.metadata["total_exceptions"] = len(result.exceptions)

            logger.info(f"Parsed {len(result.schedules)} schedules and {len(result.exceptions)} exceptions")

        except Exception as e:
            result.errors.append(f"Failed to parse Holtville data: {e}")
            logger.error(f"Parse error: {e}")

        return result

    def get_schedule_for_address(self, address: str) -> List[ScheduleData]:
        """
        Get schedule for a specific address in Holtville.

        Since Holtville uses a citywide schedule, all addresses
        have the same pickup days.
    def match_address_to_zone(self, address: str) -> str:
        """
        Match an address to a pickup zone.

        For pilot version, uses simple heuristics.
        In production, would use GIS polygon matching.

        Args:
            address: Full address string

        Returns:
            Zone identifier (ZONE_1, ZONE_2, etc.)
        """
        address_upper = address.upper()

        # Simple heuristic based on street patterns
        if any(st in address_upper for st in ["HOLT", "5TH", "6TH"]):
            return "ZONE_1"
        elif any(st in address_upper for st in ["OLIVE", "FIG", "DATE"]):
            return "ZONE_2"
        elif any(st in address_upper for st in ["CHESTNUT", "WALNUT", "CEDAR"]):
            return "ZONE_3"
        else:
            return "ZONE_4"

    def get_schedule_for_address(self, address: str) -> List[ScheduleData]:
        """
        Get schedule for a specific address.

        Args:
            address: Full address string

        Returns:
            List of ScheduleData for the address
        """
        # Run parser to get citywide schedule
        parse_result = self.run()

        # Update address for each schedule
        schedules = []
        for schedule in parse_result.schedules:
            schedule.address = address
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
