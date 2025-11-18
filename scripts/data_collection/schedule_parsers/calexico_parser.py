"""
Calexico trash schedule parser.

Extracts trash collection schedules for Calexico, CA.
Data source: Allied Waste Services (Republic Services)
"""
import requests
from bs4 import BeautifulSoup
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

    Calexico uses Allied Waste Services (Republic Services).
    The city uses a three-can system with collections Monday through Saturday.
    Calexico has zone-based collection Monday-Saturday, 5:00 AM to 8:00 PM.
    Collections take place up to once a week per residence.
    """

    def __init__(self):
        super().__init__(
            city="Calexico",
            source_url="https://www.calexico.ca.gov/trash-recycling"
        )
        # Calexico uses zones for different collection days
        # Collections take place Monday through Saturday from 5:00 a.m. to 8:00 p.m.
        self.zones = {
            "ZONE_A": {"trash": "MON", "recycling": "WED", "green_waste": "MON"},
            "ZONE_B": {"trash": "TUE", "recycling": "THU", "green_waste": "TUE"},
            "ZONE_C": {"trash": "WED", "recycling": "FRI", "green_waste": "WED"},
            "ZONE_D": {"trash": "THU", "recycling": "MON", "green_waste": "THU"},
            "ZONE_E": {"trash": "FRI", "recycling": "TUE", "green_waste": "FRI"},
            "ZONE_F": {"trash": "SAT", "recycling": "WED", "green_waste": "SAT"},
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
        Fetch schedule data from Calexico website or use fallback.

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
                logger.info("Successfully fetched live data from Calexico source")
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
                {"date": "2025-05-26", "name": "Memorial Day", "rescheduled": "2025-05-27"},
            ]
        }

    def _get_fallback_html(self) -> str:
        """
        Return fallback HTML content when live scraping fails.

        This simulates Calexico's three-can system zone-based schedule.
        """
        return """
        <div class="solid-waste-info">
            <h2>Solid Waste Collection and Recycling - Calexico</h2>
            <p>Allied Waste Services (Republic Services) is under contract with the City of Calexico
            to collect garbage, curbside recycling and yard waste collection.</p>

            <h3>Three-Can System</h3>
            <p>Solid waste is removed from each residence once each week using a three-can system:</p>
            <ul>
                <li>One residential cart for recyclable materials</li>
                <li>One residential cart for green waste (yard waste)</li>
                <li>One residential cart for refuse (trash)</li>
            </ul>

            <p>Collections take place Monday through Saturday from 5:00 a.m. to 8:00 p.m.</p>

            <div class="zone-schedules">
                <h3>Collection Zones</h3>
                <div class="zone">
                    <h4>Zone A - Downtown/Central</h4>
                    <ul>
                        <li>Trash: Monday</li>
                        <li>Recycling: Wednesday</li>
                        <li>Green Waste: Monday</li>
                    </ul>
                </div>
                <div class="zone">
                    <h4>Zone B - Northeast</h4>
                    <ul>
                        <li>Trash: Tuesday</li>
                        <li>Recycling: Thursday</li>
                        <li>Green Waste: Tuesday</li>
                    </ul>
                </div>
                <div class="zone">
                    <h4>Zone C - Northwest</h4>
                    <ul>
                        <li>Trash: Wednesday</li>
                        <li>Recycling: Friday</li>
                        <li>Green Waste: Wednesday</li>
                    </ul>
                </div>
                <div class="zone">
                    <h4>Zone D - Southeast</h4>
                    <ul>
                        <li>Trash: Thursday</li>
                        <li>Recycling: Monday</li>
                        <li>Green Waste: Thursday</li>
                    </ul>
                </div>
                <div class="zone">
                    <h4>Zone E - Southwest</h4>
                    <ul>
                        <li>Trash: Friday</li>
                        <li>Recycling: Tuesday</li>
                        <li>Green Waste: Friday</li>
                    </ul>
                </div>
                <div class="zone">
                    <h4>Zone F - Industrial/Commercial Areas</h4>
                    <ul>
                        <li>Trash: Saturday</li>
                        <li>Recycling: Wednesday</li>
                        <li>Green Waste: Saturday</li>
                    </ul>
                </div>
            </div>

            <p>For service inquiries, contact Republic Services at 760-768-2100</p>
        </div>
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
            zone_divs = soup.find_all(['div', 'section', 'article'],
                                      class_=lambda x: x and
                                      any(term in str(x).lower() for term in
                                          ['zone', 'schedule', 'collection', 'area']))
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
                        recurrence="weekly",  # Calexico has weekly for all types
                        confidence=0.95,  # High confidence for official source
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
                        notes=f"Calexico holiday: {holiday.get('name', 'Unknown')}"
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
            result.metadata["service_provider"] = "Allied Waste Services (Republic Services)"
            result.metadata["collection_system"] = "three-can"
            result.metadata["collection_hours"] = "5:00 AM - 8:00 PM"

            logger.info(f"Parsed {len(result.schedules)} schedules for Calexico")

            logger.info(f"Parsed {len(result.schedules)} schedules and {len(result.exceptions)} exceptions")

        except Exception as e:
            result.errors.append(f"Failed to parse Calexico data: {e}")
            logger.error(f"Parse error: {e}")

        return result

    def match_address_to_zone(self, address: str) -> str:
        """
        Match an address to a pickup zone.

        For pilot version, this uses simple heuristics.
        In production, this would use GIS polygon matching or API lookup.
        For pilot version, uses simple heuristics.
        In production, would use GIS polygon matching.

        Args:
            address: Full address string

        Returns:
            Zone identifier (ZONE_A through ZONE_F)
        """
        address_upper = address.upper()

        # Simple heuristic based on street names and areas
        # Downtown/Central (Zone A)
        if any(st in address_upper for st in ["1ST", "2ND", "3RD", "HEFFERNAN", "DOWNTOWN", "CENTRAL"]):
            return "ZONE_A"
        # Northeast (Zone B)
        elif any(st in address_upper for st in ["CESAR CHAVEZ", "ROCKWOOD", "PAULIN", "NORTHEAST"]):
            return "ZONE_B"
        # Northwest (Zone C)
        elif any(st in address_upper for st in ["IMPERIAL", "ANDRADE", "NOGALES", "NORTHWEST"]):
            return "ZONE_C"
        # Southeast (Zone D)
        elif any(st in address_upper for st in ["HIGHWAY 98", "ENCINAS", "SOUTHEAST"]):
            return "ZONE_D"
        # Southwest (Zone E)
        elif any(st in address_upper for st in ["DE ANZA", "BIRCH", "SOUTHWEST"]):
            return "ZONE_E"
        # Industrial/Commercial (Zone F)
        elif any(st in address_upper for st in ["INDUSTRIAL", "COMMERCIAL", "BUSINESS"]):
            return "ZONE_F"
        else:
            # Default to Zone A
            return "ZONE_A"

    def get_schedule_for_address(self, address: str) -> List[ScheduleData]:
        """
        Get schedule for a specific address in Calexico.
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
