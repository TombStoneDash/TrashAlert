"""
Imperial trash schedule parser.

Extracts trash collection schedules for Imperial, CA.
Data source: HTML table from city website
"""
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

        For pilot version, return simulated HTML table data.
        In production, this would make an actual HTTP request.
        """
        logger.info(f"Fetching data from {self.source_url}")

        # Simulated HTML table from city website
        # In production: response = requests.get(self.source_url)
        html_content = """
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

        return {
            "html": html_content,
            "citywide_schedule": True,
            "holidays": [
                {"date": "2025-11-27", "name": "Thanksgiving", "rescheduled": "2025-11-28"},
                {"date": "2025-12-25", "name": "Christmas", "rescheduled": "2025-12-26"},
            ]
        }

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
