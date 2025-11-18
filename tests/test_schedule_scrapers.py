"""
Tests for schedule scrapers with mocked HTML responses.

This test suite validates all Imperial Valley city scrapers using
mocked HTML content to ensure reliable, repeatable testing without
requiring live website access.
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.data_collection.schedule_parsers.el_centro_parser import ElCentroParser
from scripts.data_collection.schedule_parsers.imperial_parser import ImperialParser
from scripts.data_collection.schedule_parsers.holtville_parser import HoltvilleParser
from scripts.data_collection.schedule_parsers.brawley_parser import BrawleyParser
from scripts.data_collection.schedule_parsers.calexico_parser import CalexicoParser
from scripts.data_collection.schedule_parsers.base_parser import ParseResult


# Mock HTML fixtures
MOCK_EL_CENTRO_HTML = """
<html>
<body>
    <div class="schedule-container">
        <h2>El Centro Trash Collection Zones</h2>
        <div class="zone-info">
            <h3>Zone A</h3>
            <p>Trash: Monday, Recycling: Wednesday, Green Waste: Friday</p>
        </div>
        <div class="zone-info">
            <h3>Zone B</h3>
            <p>Trash: Tuesday, Recycling: Thursday, Green Waste: Monday</p>
        </div>
    </div>
</body>
</html>
"""

MOCK_IMPERIAL_HTML = """
<html>
<body>
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
        </tbody>
    </table>
</body>
</html>
"""

MOCK_HOLTVILLE_HTML = """
<html>
<body>
    <div class="schedule-info">
        <h2>Holtville Trash Collection</h2>
        <ul>
            <li>Trash Collection: Tuesday (Weekly)</li>
            <li>Recycling Collection: Friday (Biweekly)</li>
            <li>Green Waste Collection: Tuesday (Weekly)</li>
        </ul>
    </div>
</body>
</html>
"""

MOCK_BRAWLEY_HTML = """
<html>
<body>
    <div class="schedule-container">
        <div class="zone-info">
            <h3>Zone 1 - North Brawley</h3>
            <p>Trash: Monday, Recycling: Thursday, Green Waste: Monday</p>
        </div>
        <div class="zone-info">
            <h3>Zone 2 - East Brawley</h3>
            <p>Trash: Tuesday, Recycling: Friday, Green Waste: Tuesday</p>
        </div>
    </div>
</body>
</html>
"""

MOCK_CALEXICO_HTML = """
<html>
<body>
    <div class="solid-waste-info">
        <h2>Calexico Collection Schedule</h2>
        <div class="zone">
            <h4>Zone A - Downtown</h4>
            <p>Trash: Monday, Recycling: Wednesday, Green Waste: Monday</p>
        </div>
        <div class="zone">
            <h4>Zone B - Northeast</h4>
            <p>Trash: Tuesday, Recycling: Thursday, Green Waste: Tuesday</p>
        </div>
    </div>
</body>
</html>
"""


class TestElCentroParser:
    """Tests for El Centro schedule parser."""

    @patch('requests.get')
    def test_fetch_raw_data_success(self, mock_get):
        """Test successful data fetch from El Centro source."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = MOCK_EL_CENTRO_HTML
        mock_get.return_value = mock_response

        parser = ElCentroParser()
        raw_data = parser.fetch_raw_data()

        assert raw_data is not None
        assert 'zones' in raw_data
        assert 'holidays' in raw_data
        assert len(raw_data['zones']) == 4  # 4 zones

    @patch('requests.get')
    def test_fetch_raw_data_failure_uses_fallback(self, mock_get):
        """Test that parser uses fallback data when fetch fails."""
        mock_get.side_effect = Exception("Network error")

        parser = ElCentroParser()
        raw_data = parser.fetch_raw_data()

        assert raw_data is not None
        assert 'zones' in raw_data
        # Should still have zone data from fallback

    def test_parse_raw_data(self):
        """Test parsing of El Centro zone data."""
        parser = ElCentroParser()
        raw_data = {
            'zones': parser.zones,
            'holidays': [
                {'date': '2025-12-25', 'name': 'Christmas', 'rescheduled': '2025-12-26'}
            ]
        }

        result = parser.parse_raw_data(raw_data)

        assert isinstance(result, ParseResult)
        assert len(result.schedules) > 0
        assert len(result.exceptions) == 1
        assert result.exceptions[0].reason == "Christmas"
        assert len(result.errors) == 0

    def test_zone_matching(self):
        """Test address to zone matching logic."""
        parser = ElCentroParser()

        # Test various addresses
        assert parser.match_address_to_zone("123 Main St") == "ZONE_A"
        assert parser.match_address_to_zone("456 State St") == "ZONE_B"
        assert parser.match_address_to_zone("789 Ross Ave") == "ZONE_C"
        assert parser.match_address_to_zone("999 Unknown St") == "ZONE_D"

    def test_get_schedule_for_address(self):
        """Test getting schedule for specific address."""
        parser = ElCentroParser()
        schedules = parser.get_schedule_for_address("123 Main St, El Centro, CA")

        assert len(schedules) == 3  # trash, recycling, green_waste
        assert all(s.zone == "ZONE_A" for s in schedules)


class TestImperialParser:
    """Tests for Imperial schedule parser."""

    @patch('requests.get')
    def test_fetch_with_mock_html(self, mock_get):
        """Test fetching with mocked HTML response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = MOCK_IMPERIAL_HTML
        mock_get.return_value = mock_response

        parser = ImperialParser()
        raw_data = parser.fetch_raw_data()

        assert 'html' in raw_data
        assert 'citywide_schedule' in raw_data
        assert raw_data['citywide_schedule'] is True

    def test_parse_html_table(self):
        """Test parsing HTML table structure."""
        parser = ImperialParser()
        raw_data = {
            'html': MOCK_IMPERIAL_HTML,
            'citywide_schedule': True,
            'holidays': []
        }

        result = parser.parse_raw_data(raw_data)

        assert len(result.schedules) >= 2  # At least trash and recycling
        # Verify Tuesday trash pickup
        trash_schedule = next((s for s in result.schedules if s.collection_type == "trash"), None)
        assert trash_schedule is not None
        assert trash_schedule.day_of_week == "TUE"

    def test_citywide_schedule_applies_to_all(self):
        """Test that citywide schedule applies to any address."""
        parser = ImperialParser()

        # Should work for any address in Imperial
        schedules1 = parser.get_schedule_for_address("100 Main St, Imperial, CA")
        schedules2 = parser.get_schedule_for_address("200 Oak Ave, Imperial, CA")

        # Both should have the same schedule
        assert len(schedules1) == len(schedules2)
        for s1, s2 in zip(schedules1, schedules2):
            assert s1.day_of_week == s2.day_of_week
            assert s1.collection_type == s2.collection_type


class TestHoltvilleParser:
    """Tests for Holtville schedule parser."""

    @patch('requests.get')
    def test_fetch_raw_data(self, mock_get):
        """Test data fetching for Holtville."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = MOCK_HOLTVILLE_HTML
        mock_get.return_value = mock_response

        parser = HoltvilleParser()
        raw_data = parser.fetch_raw_data()

        assert raw_data is not None
        assert 'citywide_schedule' in raw_data

    def test_parse_schedule_data(self):
        """Test parsing Holtville schedule data."""
        parser = HoltvilleParser()
        raw_data = {
            'html': MOCK_HOLTVILLE_HTML,
            'citywide_schedule': parser.citywide_schedule,
            'holidays': []
        }

        result = parser.parse_raw_data(raw_data)

        assert len(result.schedules) == 3  # trash, recycling, green_waste
        assert all(s.address == "Holtville, CA (citywide)" for s in result.schedules)
        assert result.metadata.get('service_provider') == "CR&R Environmental Services"


class TestBrawleyParser:
    """Tests for Brawley schedule parser."""

    @patch('requests.get')
    def test_fetch_raw_data(self, mock_get):
        """Test data fetching for Brawley."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = MOCK_BRAWLEY_HTML
        mock_get.return_value = mock_response

        parser = BrawleyParser()
        raw_data = parser.fetch_raw_data()

        assert raw_data is not None
        assert 'zones' in raw_data
        assert len(raw_data['zones']) == 4

    def test_parse_zone_schedules(self):
        """Test parsing Brawley zone-based schedules."""
        parser = BrawleyParser()
        raw_data = {
            'html': MOCK_BRAWLEY_HTML,
            'zones': parser.zones,
            'holidays': []
        }

        result = parser.parse_raw_data(raw_data)

        # 4 zones * 3 collection types = 12 schedules
        assert len(result.schedules) == 12
        assert result.metadata.get('total_zones') == 4
        assert result.metadata.get('service_provider') == "Republic Services"

    def test_zone_matching(self):
        """Test address to zone matching for Brawley."""
        parser = BrawleyParser()

        # Test zone matching
        assert parser.match_address_to_zone("123 Main St") == "ZONE_1"
        assert parser.match_address_to_zone("456 Highway 111") == "ZONE_2"
        assert parser.match_address_to_zone("789 J Street") == "ZONE_3"


class TestCalexicoParser:
    """Tests for Calexico schedule parser."""

    @patch('requests.get')
    def test_fetch_raw_data(self, mock_get):
        """Test data fetching for Calexico."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = MOCK_CALEXICO_HTML
        mock_get.return_value = mock_response

        parser = CalexicoParser()
        raw_data = parser.fetch_raw_data()

        assert raw_data is not None
        assert 'zones' in raw_data
        assert len(raw_data['zones']) == 6  # 6 zones

    def test_parse_zone_schedules(self):
        """Test parsing Calexico zone-based schedules."""
        parser = CalexicoParser()
        raw_data = {
            'html': MOCK_CALEXICO_HTML,
            'zones': parser.zones,
            'holidays': []
        }

        result = parser.parse_raw_data(raw_data)

        # 6 zones * 3 collection types = 18 schedules
        assert len(result.schedules) == 18
        assert result.metadata.get('total_zones') == 6
        assert result.metadata.get('service_provider') == "Allied Waste Services (Republic Services)"
        assert result.metadata.get('collection_system') == "three-can"

    def test_zone_matching(self):
        """Test address to zone matching for Calexico."""
        parser = CalexicoParser()

        # Test various addresses
        assert parser.match_address_to_zone("123 1st St") == "ZONE_A"
        assert parser.match_address_to_zone("456 Cesar Chavez Blvd") == "ZONE_B"
        assert parser.match_address_to_zone("789 Imperial Ave") == "ZONE_C"

    def test_three_can_system(self):
        """Test that Calexico correctly implements three-can system."""
        parser = CalexicoParser()
        schedules = parser.get_schedule_for_address("123 Main St, Calexico, CA")

        # Should have all three collection types
        collection_types = {s.collection_type for s in schedules}
        assert "trash" in collection_types
        assert "recycling" in collection_types
        assert "green_waste" in collection_types


class TestScheduleIntegration:
    """Integration tests for all parsers."""

    def test_all_parsers_return_valid_results(self):
        """Test that all parsers return valid ParseResult objects."""
        parsers = [
            ElCentroParser(),
            ImperialParser(),
            HoltvilleParser(),
            BrawleyParser(),
            CalexicoParser()
        ]

        for parser in parsers:
            with patch('requests.get') as mock_get:
                # Setup mock to use fallback data
                mock_get.side_effect = Exception("Use fallback")

                result = parser.run()

                assert isinstance(result, ParseResult)
                assert len(result.schedules) > 0, f"{parser.city} parser returned no schedules"
                assert all(s.day_of_week in ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
                          for s in result.schedules), f"{parser.city} has invalid day codes"
                assert all(s.collection_type in ['trash', 'recycling', 'green_waste']
                          for s in result.schedules), f"{parser.city} has invalid collection types"

    def test_all_parsers_handle_holidays(self):
        """Test that all parsers correctly parse holiday exceptions."""
        parsers = [
            ElCentroParser(),
            ImperialParser(),
            HoltvilleParser(),
            BrawleyParser(),
            CalexicoParser()
        ]

        for parser in parsers:
            with patch('requests.get') as mock_get:
                mock_get.side_effect = Exception("Use fallback")

                result = parser.run()

                # All parsers should have at least some holidays defined
                assert len(result.exceptions) > 0, f"{parser.city} has no holiday exceptions"

                # Verify exception structure
                for exception in result.exceptions:
                    assert exception.exception_date is not None
                    assert exception.reason is not None

    def test_parser_metadata(self):
        """Test that all parsers populate metadata correctly."""
        parsers = [
            ElCentroParser(),
            ImperialParser(),
            HoltvilleParser(),
            BrawleyParser(),
            CalexicoParser()
        ]

        for parser in parsers:
            with patch('requests.get') as mock_get:
                mock_get.side_effect = Exception("Use fallback")

                result = parser.run()

                assert 'total_schedules' in result.metadata
                assert 'total_exceptions' in result.metadata
                assert result.metadata['total_schedules'] == len(result.schedules)
                assert result.metadata['total_exceptions'] == len(result.exceptions)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
