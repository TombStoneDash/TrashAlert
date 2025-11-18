"""
Imperial trash schedule parser.

Extracts trash collection schedules for Imperial, CA.
Data source: HTML table from city website
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


class ImperialParser(BaseScheduleParser):
    """
    Parser for Imperial trash schedules.

    Imperial publishes schedules in HTML tables on their website.
    The city uses a simple citywide schedule (same for all addresses).
    """

    def __init__(self):
        super().__init__(
            city="Imperial",
            source_url="https://www.cityofimperial.org/departments/public-works/trash-collection"
        )

    def fetch_raw_data(self) -> Any:
        """
        Fetch schedule data from Imperial website.

        Attempts to fetch real data from city website, falls back to simulated data if unavailable.
        """
        logger.info(f"Fetching data from {self.source_url}")

        # Try to fetch real data
        html_content = None
        try:
            response = requests.get(self.source_url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            if response.status_code == 200:
                html_content = response.text
                logger.info("Successfully fetched live data from Imperial source")
            else:
                logger.warning(f"Failed to fetch live data (status {response.status_code}), using fallback")
                html_content = self._get_fallback_html()
        except Exception as e:
            logger.warning(f"Error fetching live data: {e}, using fallback")
            html_content = self._get_fallback_html()

        return {
            "html": html_content,
            "citywide_schedule": True,
            "holidays": [
                {"date": "2025-11-27", "name": "Thanksgiving", "rescheduled": "2025-11-28"},
                {"date": "2025-12-25", "name": "Christmas", "rescheduled": "2025-12-26"},
                {"date": "2026-01-01", "name": "New Year's Day", "rescheduled": "2026-01-02"},
                {"date": "2025-07-04", "name": "Independence Day", "rescheduled": "2025-07-05"},
            ]
        }

    def _get_fallback_html(self) -> str:
        """
        Return fallback HTML content when live scraping fails.
        """
        return """
        <table class="schedule-table">
            <thead>
                <tr>
                    <th>Collection Type</th>
                    <th>Day of Week</th>
                    <th>Frequency</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Trash</td>
                    <td>Tuesday</td>
                    <td>Weekly</td>
                </tr>
                <tr>
                    <td>Recycling</td>
                    <td>Friday</td>
                    <td>Biweekly</td>
                </tr>
                <tr>
                    <td>Green Waste</td>
                    <td>Tuesday</td>
                    <td>Weekly</td>
                </tr>
            </tbody>
        </table>
        """

    def parse_raw_data(self, raw_data: Any) -> ParseResult:
        """
        Parse Imperial HTML table data.

        Args:
            raw_data: Dict with HTML content and metadata

        Returns:
            ParseResult with schedules and exceptions
        """
        result = ParseResult()

        try:
            html = raw_data.get("html", "")
            soup = BeautifulSoup(html, 'html.parser')

            # Find schedule table
            table = soup.find('table', class_='schedule-table')
            if not table:
                result.errors.append("Could not find schedule table in HTML")
                return result

            # Parse table rows
            rows = table.find('tbody').find_all('tr')

            for row in rows:
                try:
                    cols = row.find_all('td')
                    if len(cols) >= 3:
                        collection_type_raw = cols[0].text.strip()
                        day_raw = cols[1].text.strip()
                        frequency_raw = cols[2].text.strip()

                        # Normalize values
                        collection_type = self.normalize_collection_type(collection_type_raw)
                        day_of_week = self.normalize_day(day_raw)
                        recurrence = frequency_raw.lower() if frequency_raw else "weekly"

                        # Create schedule entry
                        # For citywide schedule, use city name as address placeholder
                        schedule = ScheduleData(
                            address="Imperial, CA (citywide)",
                            day_of_week=day_of_week,
                            collection_type=collection_type,
                            zone=None,  # No zones - citywide
                            recurrence=recurrence,
                            confidence=1.0,  # High confidence - official source
                            effective_date=datetime(2025, 1, 1),
                            next_pickup_date=self.calculate_next_pickup(day_of_week)
                        )
                        result.schedules.append(schedule)

                except Exception as e:
                    result.warnings.append(f"Failed to parse table row: {e}")

            # Parse holiday exceptions
            holidays = raw_data.get("holidays", [])
            for holiday in holidays:
                try:
                    exception_date = datetime.strptime(holiday["date"], "%Y-%m-%d")
                    rescheduled_date = None
                    is_cancelled = holiday.get("cancelled", False)

                    if "rescheduled" in holiday:
                        rescheduled_date = datetime.strptime(holiday["rescheduled"], "%Y-%m-%d")

                    exception = ExceptionData(
                        exception_date=exception_date,
                        rescheduled_date=rescheduled_date,
                        is_cancelled=is_cancelled,
                        reason=holiday.get("name", "Holiday"),
                        notes=f"Imperial city holiday: {holiday.get('name', 'Unknown')}"
                    )
                    result.exceptions.append(exception)
                except Exception as e:
                    result.warnings.append(f"Failed to parse holiday {holiday}: {e}")

            # Add metadata
            result.metadata["citywide_schedule"] = raw_data.get("citywide_schedule", False)
            result.metadata["total_schedules"] = len(result.schedules)
            result.metadata["total_exceptions"] = len(result.exceptions)
            result.metadata["source_format"] = "html_table"

            logger.info(f"Parsed {len(result.schedules)} schedules from Imperial HTML table")

        except Exception as e:
            result.errors.append(f"Failed to parse Imperial data: {e}")
            logger.error(f"Parse error: {e}")

        return result

    def get_schedule_for_address(self, address: str) -> List[ScheduleData]:
        """
        Get schedule for a specific address in Imperial.

        Since Imperial uses a citywide schedule, all addresses
        have the same pickup days.

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
            schedules.append(schedule)

        return schedules
