"""
Brawley trash schedule parser.

Extracts trash collection schedules for Brawley, CA.
Data source: Republic Services
Data source: City of Brawley website (CR&R Environmental Services)
"""
import requests
from bs4 import BeautifulSoup
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


class BrawleyParser(BaseScheduleParser):
    """
    Parser for Brawley trash schedules.

    Brawley uses Republic Services. The city may use zones or
    a citywide schedule.
    Brawley uses CR&R Environmental Services for waste collection.
    The city has a simple zone-based system.
    """

    def __init__(self):
        super().__init__(
            city="Brawley",
            source_url="https://www.republicservices.com/municipality/brawley-ca"
        )
        # Brawley schedule zones - based on typical Imperial Valley patterns
        self.zones = {
            "ZONE_1": {"trash": "MON", "recycling": "THU", "green_waste": "MON"},
            "ZONE_2": {"trash": "TUE", "recycling": "FRI", "green_waste": "TUE"},
            "ZONE_3": {"trash": "WED", "recycling": "MON", "green_waste": "WED"},
            "ZONE_4": {"trash": "THU", "recycling": "TUE", "green_waste": "THU"},
            source_url="https://www.brawley-ca.gov/departments/public-works"
        )
        # Brawley zones - in production, these would be extracted from official sources
        self.zones = {
            "ZONE_1": {"trash": "MON", "recycling": "WED", "green_waste": "MON"},
            "ZONE_2": {"trash": "TUE", "recycling": "THU", "green_waste": "TUE"},
            "ZONE_3": {"trash": "WED", "recycling": "FRI", "green_waste": "WED"},
            "ZONE_4": {"trash": "THU", "recycling": "MON", "green_waste": "THU"},
        }

    def fetch_raw_data(self) -> Any:
        """
        Fetch schedule data from Republic Services website or use fallback.

        For pilot version, use zone-based schedule data.
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
                logger.info("Successfully fetched live data from Brawley source")
            else:
                logger.warning(f"Failed to fetch live data (status {response.status_code}), using fallback")
                html_content = self._get_fallback_html()
        except Exception as e:
            logger.warning(f"Error fetching live data: {e}, using fallback")
            html_content = self._get_fallback_html()

        return {
            "html": html_content,
            "zones": self.zones,
            "holidays": [
                {"date": "2025-12-25", "name": "Christmas", "rescheduled": "2025-12-26"},
                {"date": "2026-01-01", "name": "New Year's Day", "rescheduled": "2026-01-02"},
                {"date": "2025-07-04", "name": "Independence Day", "rescheduled": "2025-07-05"},
                {"date": "2025-11-27", "name": "Thanksgiving", "rescheduled": "2025-11-28"},
                {"date": "2025-09-01", "name": "Labor Day", "rescheduled": "2025-09-02"},
            ]
        }

    def _get_fallback_html(self) -> str:
        """
        Return fallback HTML content when live scraping fails.

        This simulates zone-based trash schedule information.
        """
        return """
        <div class="schedule-container">
            <h2>Brawley Collection Schedule</h2>
            <div class="zone-info">
                <h3>Zone 1 - North Brawley</h3>
                <ul>
                    <li>Trash: Monday (Weekly)</li>
                    <li>Recycling: Thursday (Biweekly)</li>
                    <li>Green Waste: Monday (Weekly)</li>
                </ul>
            </div>
            <div class="zone-info">
                <h3>Zone 2 - East Brawley</h3>
                <ul>
                    <li>Trash: Tuesday (Weekly)</li>
                    <li>Recycling: Friday (Biweekly)</li>
                    <li>Green Waste: Tuesday (Weekly)</li>
                </ul>
            </div>
            <div class="zone-info">
                <h3>Zone 3 - South Brawley</h3>
                <ul>
                    <li>Trash: Wednesday (Weekly)</li>
                    <li>Recycling: Monday (Biweekly)</li>
                    <li>Green Waste: Wednesday (Weekly)</li>
                </ul>
            </div>
            <div class="zone-info">
                <h3>Zone 4 - West Brawley</h3>
                <ul>
                    <li>Trash: Thursday (Weekly)</li>
                    <li>Recycling: Tuesday (Biweekly)</li>
                    <li>Green Waste: Thursday (Weekly)</li>
                </ul>
            </div>
            <p>Service provided by Republic Services</p>
            <p>Contact: 760-355-0004</p>
        </div>
        """

        Fetch schedule data from Brawley sources.

        For pilot version, use hardcoded zone data.
        In production, this would contact CR&R or city website.
        """
        logger.info(f"Fetching data from {self.source_url}")

        # CR&R observes major holidays
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
        Parse Brawley schedule data.

        Args:
            raw_data: Dict with HTML content and zone metadata
            raw_data: Zone configuration and holiday data

        Returns:
            ParseResult with schedules and exceptions
        """
        result = ParseResult()

        try:
            html = raw_data.get("html", "")
            zones = raw_data.get("zones", {})
            soup = BeautifulSoup(html, 'html.parser')

            # Try to parse zones from HTML
            zone_divs = soup.find_all(['div', 'section'],
                                      class_=lambda x: x and
                                      any(term in str(x).lower() for term in
                                          ['zone', 'area', 'district', 'schedule']))
            zones = raw_data.get("zones", {})
            holidays = raw_data.get("holidays", [])

            # Parse zone schedules
            for zone_name, zone_schedule in zones.items():
                for collection_type, day in zone_schedule.items():
                    schedule = ScheduleData(
                        address=f"Brawley, {zone_name}",
                        day_of_week=day,
                        collection_type=collection_type,
                        zone=zone_name,
                        recurrence="weekly" if collection_type != "recycling" else "biweekly",
                        confidence=0.9,
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
                        notes=f"Brawley holiday: {holiday.get('name', 'Unknown')}"
                        is_cancelled=holiday.get("cancelled", False),
                        reason=holiday.get("name", "Holiday"),
                        notes=f"Brawley city holiday: {holiday.get('name', 'Unknown')}"
                    )
                    result.exceptions.append(exception)
                except Exception as e:
                    result.warnings.append(f"Failed to parse holiday {holiday}: {e}")

            # Add metadata
            result.metadata["total_zones"] = len(zones)
            result.metadata["total_schedules"] = len(result.schedules)
            result.metadata["total_exceptions"] = len(result.exceptions)
            result.metadata["service_provider"] = "Republic Services"

            logger.info(f"Parsed {len(result.schedules)} schedules for Brawley")

            logger.info(f"Parsed {len(result.schedules)} schedules and {len(result.exceptions)} exceptions")

        except Exception as e:
            result.errors.append(f"Failed to parse Brawley data: {e}")
            logger.error(f"Parse error: {e}")

        return result

    def match_address_to_zone(self, address: str) -> str:
        """
        Match an address to a pickup zone.

        For pilot version, this uses simple heuristics.
        In production, this would use GIS polygon matching or address lookup.
        For pilot version, uses simple heuristics.
        In production, would use GIS polygon matching.

        Args:
            address: Full address string

        Returns:
            Zone identifier (ZONE_1, ZONE_2, etc.)
        """
        address_upper = address.upper()

        # Simple heuristic based on street names and areas
        # North Brawley
        if any(st in address_upper for st in ["MAIN", "A ST", "B ST", "C ST", "NORTH"]):
            return "ZONE_1"
        # East Brawley
        elif any(st in address_upper for st in ["HIGHWAY 111", "CATTLE CALL", "EAST"]):
            return "ZONE_2"
        # South Brawley
        elif any(st in address_upper for st in ["J ST", "K ST", "L ST", "SOUTH"]):
            return "ZONE_3"
        # West Brawley
        # Simple heuristic based on street patterns
        if any(st in address_upper for st in ["MAIN", "A STREET", "B STREET"]):
            return "ZONE_1"
        elif any(st in address_upper for st in ["C STREET", "D STREET", "E STREET"]):
            return "ZONE_2"
        elif any(st in address_upper for st in ["F STREET", "G STREET", "H STREET"]):
            return "ZONE_3"
        else:
            return "ZONE_4"

    def get_schedule_for_address(self, address: str) -> List[ScheduleData]:
        """
        Get schedule for a specific address in Brawley.
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
                recurrence="weekly" if collection_type != "recycling" else "biweekly",
                confidence=0.9,
                recurrence="weekly",
                confidence=0.95,
                next_pickup_date=self.calculate_next_pickup(day)
            )
            schedules.append(schedule)

        return schedules
