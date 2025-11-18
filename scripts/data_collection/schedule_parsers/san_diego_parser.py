"""
San Diego trash schedule parser.

Extracts trash collection schedules for San Diego, CA.
Data source: PDF collection calendar and online lookup tool
"""
import io
from datetime import datetime
from typing import Any, List, Dict
import logging

from .base_parser import (
    BaseScheduleParser,
    ScheduleData,
    ExceptionData,
    ParseResult
)

logger = logging.getLogger(__name__)


class SanDiegoParser(BaseScheduleParser):
    """
    Parser for San Diego trash schedules.

    San Diego uses a complex zone-based system with different schedules
    for different neighborhoods. Data comes from PDF calendars and
    the city's Get It Done 311 system.
    """

    def __init__(self):
        super().__init__(
            city="San Diego",
            source_url="https://www.sandiego.gov/environmental-services/collection-schedules"
        )

        # San Diego has multiple collection zones
        # In production, these would be extracted from GIS data
        self.neighborhoods = {
            "Downtown": {"trash": "MON", "recycling": "WED", "green_waste": "FRI", "zone": "SD-1"},
            "La Jolla": {"trash": "TUE", "recycling": "THU", "green_waste": "MON", "zone": "SD-2"},
            "Pacific Beach": {"trash": "WED", "recycling": "FRI", "green_waste": "TUE", "zone": "SD-3"},
            "North Park": {"trash": "THU", "recycling": "MON", "green_waste": "WED", "zone": "SD-4"},
            "Point Loma": {"trash": "FRI", "recycling": "TUE", "green_waste": "THU", "zone": "SD-5"},
            "Mira Mesa": {"trash": "MON", "recycling": "THU", "green_waste": "FRI", "zone": "SD-6"},
            "Scripps Ranch": {"trash": "TUE", "recycling": "FRI", "green_waste": "MON", "zone": "SD-7"},
            "Rancho Bernardo": {"trash": "WED", "recycling": "MON", "green_waste": "TUE", "zone": "SD-8"},
        }

    def fetch_raw_data(self) -> Any:
        """
        Fetch schedule data from San Diego sources.

        For pilot version, use simulated PDF/API data.
        In production, this would:
        1. Download PDF calendar
        2. Query Get It Done 311 API
        3. Scrape online lookup tool
        """
        logger.info(f"Fetching data from {self.source_url}")

        # Simulated PDF content
        # In production: response = requests.get(pdf_url)
        pdf_text = """
        SAN DIEGO REFUSE COLLECTION SCHEDULE 2025

        ZONE SD-1 (Downtown, Gaslamp, East Village)
        Trash: Monday
        Recycling: Wednesday
        Green Waste: Friday

        ZONE SD-2 (La Jolla, UTC)
        Trash: Tuesday
        Recycling: Thursday
        Green Waste: Monday

        ZONE SD-3 (Pacific Beach, Mission Beach)
        Trash: Wednesday
        Recycling: Friday
        Green Waste: Tuesday

        HOLIDAY SCHEDULE:
        - New Year's Day (Jan 1): Collection delayed 1 day
        - Memorial Day (May 26): Collection delayed 1 day
        - Independence Day (Jul 4): No collection
        - Thanksgiving (Nov 27): Collection delayed 1 day
        - Christmas (Dec 25): Collection delayed 1 day
        """

        return {
            "pdf_text": pdf_text,
            "neighborhoods": self.neighborhoods,
            "holidays": [
                {"date": "2025-01-01", "name": "New Year's Day", "delay_days": 1},
                {"date": "2025-05-26", "name": "Memorial Day", "delay_days": 1},
                {"date": "2025-07-04", "name": "Independence Day", "cancelled": True},
                {"date": "2025-11-27", "name": "Thanksgiving", "delay_days": 1},
                {"date": "2025-12-25", "name": "Christmas", "delay_days": 1},
            ]
        }

    def parse_raw_data(self, raw_data: Any) -> ParseResult:
        """
        Parse San Diego schedule data from PDF and other sources.

        Args:
            raw_data: Dict with PDF text, neighborhood data, and holidays

        Returns:
            ParseResult with schedules and exceptions
        """
        result = ParseResult()

        try:
            neighborhoods = raw_data.get("neighborhoods", {})

            # Parse neighborhood schedules
            for neighborhood, schedule_info in neighborhoods.items():
                # Use neighborhood name as zone for better matching
                # The zone code (SD-1, SD-2, etc.) can be stored in metadata
                zone_code = schedule_info.get("zone", "UNKNOWN")

                # Create schedule entries for each collection type
                for collection_type in ["trash", "recycling", "green_waste"]:
                    if collection_type in schedule_info:
                        day = schedule_info[collection_type]

                        schedule = ScheduleData(
                            address=f"San Diego, {neighborhood}",
                            day_of_week=day,
                            collection_type=collection_type,
                            zone=neighborhood,  # Use neighborhood name as zone identifier
                            recurrence="weekly",
                            confidence=0.98,  # High confidence - official PDF
                            effective_date=datetime(2025, 1, 1),
                            next_pickup_date=self.calculate_next_pickup(day)
                        )
                        result.schedules.append(schedule)

            # Parse holiday exceptions
            holidays = raw_data.get("holidays", [])
            for holiday in holidays:
                try:
                    exception_date = datetime.strptime(holiday["date"], "%Y-%m-%d")
                    is_cancelled = holiday.get("cancelled", False)
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
                        notes=f"San Diego city holiday - {holiday.get('name', 'Unknown')}"
                    )
                    result.exceptions.append(exception)
                except Exception as e:
                    result.warnings.append(f"Failed to parse holiday {holiday}: {e}")

            # Add metadata
            result.metadata["total_neighborhoods"] = len(neighborhoods)
            result.metadata["total_schedules"] = len(result.schedules)
            result.metadata["total_exceptions"] = len(result.exceptions)
            result.metadata["source_format"] = "pdf_calendar"

            logger.info(f"Parsed {len(result.schedules)} schedules from San Diego data")

        except Exception as e:
            result.errors.append(f"Failed to parse San Diego data: {e}")
            logger.error(f"Parse error: {e}")

        return result

    def match_address_to_neighborhood(self, address: str) -> str:
        """
        Match an address to a San Diego neighborhood.

        For pilot version, uses simple keyword matching.
        In production, would use GIS polygon matching or API lookup.

        Args:
            address: Full address string

        Returns:
            Neighborhood name
        """
        address_upper = address.upper()

        # Simple keyword matching
        if any(kw in address_upper for kw in ["DOWNTOWN", "GASLAMP", "BROADWAY", "92101"]):
            return "Downtown"
        elif any(kw in address_upper for kw in ["LA JOLLA", "TORREY PINES", "92037"]):
            return "La Jolla"
        elif any(kw in address_upper for kw in ["PACIFIC BEACH", "GARNET", "92109"]):
            return "Pacific Beach"
        elif any(kw in address_upper for kw in ["NORTH PARK", "UNIVERSITY", "92104"]):
            return "North Park"
        elif any(kw in address_upper for kw in ["POINT LOMA", "SUNSET CLIFFS"]):
            return "Point Loma"
        elif any(kw in address_upper for kw in ["MIRA MESA"]):
            return "Mira Mesa"
        elif any(kw in address_upper for kw in ["SCRIPPS RANCH"]):
            return "Scripps Ranch"
        elif any(kw in address_upper for kw in ["RANCHO BERNARDO", "BERNARDO"]):
            return "Rancho Bernardo"
        else:
            return "Downtown"  # Default

    def get_schedule_for_address(self, address: str) -> List[ScheduleData]:
        """
        Get schedule for a specific address in San Diego.

        Args:
            address: Full address string

        Returns:
            List of ScheduleData for the address
        """
        neighborhood = self.match_address_to_neighborhood(address)
        neighborhood_schedule = self.neighborhoods.get(neighborhood, {})

        schedules = []
        for collection_type, day in neighborhood_schedule.items():
            if collection_type in ["trash", "recycling", "green_waste"]:
                schedule = ScheduleData(
                    address=address,
                    day_of_week=day,
                    collection_type=collection_type,
                    zone=neighborhood_schedule.get("zone"),
                    recurrence="weekly",
                    confidence=0.98,
                    next_pickup_date=self.calculate_next_pickup(day)
                )
                schedules.append(schedule)

        return schedules

    def parse_pdf_calendar(self, pdf_path: str) -> Dict[str, Any]:
        """
        Parse schedule from PDF calendar file.

        This method would be used in production to extract
        data from actual PDF files.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dict with extracted schedule data

        Raises:
            ImportError: If PDF libraries not installed
        """
        try:
            import pdfplumber
        except (ImportError, Exception) as e:
            raise ImportError(f"pdfplumber required for PDF parsing. Install with: pip install pdfplumber. Error: {e}")

        extracted_data = {
            "zones": {},
            "holidays": []
        }

        # PDF parsing logic would go here
        # This is a placeholder for the production implementation
        logger.warning("PDF parsing not fully implemented - using simulated data")

        return extracted_data
