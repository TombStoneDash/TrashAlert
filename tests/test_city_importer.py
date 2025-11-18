"""
Tests for city_importer.py - Nationwide Mode

Tests the quick onboarding workflow for new cities.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
import yaml
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy.sql import func

# Create test-specific models to avoid conflicts with existing schema
TestBase = declarative_base()

class City(TestBase):
    """Test City model."""
    __tablename__ = "cities"
    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    state = Column(String, index=True)
    county = Column(String)
    region = Column(String)
    timezone = Column(String, default="America/Los_Angeles")
    enabled = Column(Boolean, default=True, index=True)
    extra_metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    pickup_zones = relationship("PickupZone", back_populates="city")

class PickupZone(TestBase):
    """Test PickupZone model."""
    __tablename__ = "pickup_zones"
    id = Column(Integer, primary_key=True, index=True)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    external_ref = Column(String)
    extra_metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    city = relationship("City", back_populates="pickup_zones")

class Schedule(TestBase):
    """Test Schedule model."""
    __tablename__ = "schedules"
    id = Column(Integer, primary_key=True, index=True)
    city_id = Column(Integer, ForeignKey("cities.id"), nullable=False, index=True)
    pickup_zone_id = Column(Integer, ForeignKey("pickup_zones.id"), nullable=True, index=True)
    trash_day_of_week = Column(String)
    recycling_day_of_week = Column(String)
    green_day_of_week = Column(String)
    source = Column(String, default="OFFICIAL")
    extra_metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# Patch the models module before importing city_importer
import sys
import types

# Create a mock models module
mock_models = types.ModuleType('app.models')
mock_models.City = City
mock_models.PickupZone = PickupZone
mock_models.Schedule = Schedule
sys.modules['app.models'] = mock_models

# Import after defining test models and patching
from scripts.city_importer import CityImporter


@pytest.fixture
def temp_config():
    """Create temporary cities.yaml for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        config = {
            'cities': [
                {
                    'city_id': 'ca_test_city',
                    'name': 'Test City',
                    'state': 'California',
                    'state_abbr': 'CA',
                    'country': 'USA',
                    'has_official_pickup_zones': False,
                    'pickup_zone_data_source': 'Test',
                    'notes': 'Test city'
                }
            ]
        }
        yaml.dump(config, f)
        config_path = f.name

    yield config_path

    # Cleanup
    if os.path.exists(config_path):
        os.unlink(config_path)


@pytest.fixture
def temp_db():
    """Create temporary in-memory database for testing."""
    engine = create_engine('sqlite:///:memory:')
    TestBase.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    yield SessionLocal()

    TestBase.metadata.drop_all(engine)


@pytest.fixture
def temp_shapefile():
    """Create temporary GeoJSON for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.geojson', delete=False) as f:
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [-118.5, 34.0],
                            [-118.4, 34.0],
                            [-118.4, 34.1],
                            [-118.5, 34.1],
                            [-118.5, 34.0]
                        ]]
                    },
                    "properties": {
                        "zone_name": "Test Zone 1",
                        "zone_id": "TZ1",
                        "trash_day": "Monday",
                        "recycling_day": "Thursday"
                    }
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [-118.4, 34.0],
                            [-118.3, 34.0],
                            [-118.3, 34.1],
                            [-118.4, 34.1],
                            [-118.4, 34.0]
                        ]]
                    },
                    "properties": {
                        "zone_name": "Test Zone 2",
                        "zone_id": "TZ2",
                        "trash_day": "Tuesday"
                    }
                }
            ]
        }
        json.dump(geojson, f)
        shapefile_path = f.name

    yield shapefile_path

    # Cleanup
    if os.path.exists(shapefile_path):
        os.unlink(shapefile_path)


class TestCityImporter:
    """Test CityImporter class."""

    def test_generate_city_id(self, temp_config):
        """Test city ID generation."""
        importer = CityImporter(temp_config)

        assert importer.generate_city_id("Los Angeles", "CA") == "ca_los_angeles"
        assert importer.generate_city_id("New York", "NY") == "ny_new_york"
        assert importer.generate_city_id("San Francisco", "CA") == "ca_san_francisco"
        assert importer.generate_city_id("El Paso", "TX") == "tx_el_paso"

    @patch('requests.get')
    def test_fetch_bounding_box_success(self, mock_get, temp_config):
        """Test successful bounding box fetch from Nominatim."""
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "boundingbox": ["34.0", "34.5", "-118.5", "-118.0"]
            }
        ]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        importer = CityImporter(temp_config)
        bbox = importer.fetch_bounding_box("Los Angeles", "California")

        assert bbox == [-118.5, 34.0, -118.0, 34.5]
        mock_get.assert_called_once()

    @patch('requests.get')
    def test_fetch_bounding_box_no_results(self, mock_get, temp_config):
        """Test bounding box fetch with no results."""
        mock_response = Mock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        importer = CityImporter(temp_config)
        bbox = importer.fetch_bounding_box("NonexistentCity", "California")

        assert bbox is None

    @patch('requests.get')
    def test_fetch_bounding_box_error(self, mock_get, temp_config):
        """Test bounding box fetch with API error."""
        mock_get.side_effect = Exception("API Error")

        importer = CityImporter(temp_config)
        bbox = importer.fetch_bounding_box("Los Angeles", "California")

        assert bbox is None

    def test_add_city_to_yaml(self, temp_config):
        """Test adding a new city to YAML config."""
        importer = CityImporter(temp_config)

        with patch.object(importer, 'fetch_bounding_box', return_value=[-118.5, 34.0, -118.0, 34.5]):
            city_id = importer.add_city_to_yaml(
                city_name="Los Angeles",
                state="California",
                state_abbr="CA",
                population=3898747,
                region="Southern California",
                notes="Test city"
            )

        assert city_id == "ca_los_angeles"

        # Verify city was added to config
        cities = importer.cities_data['cities']
        la_city = next((c for c in cities if c['city_id'] == 'ca_los_angeles'), None)

        assert la_city is not None
        assert la_city['name'] == "Los Angeles"
        assert la_city['state'] == "California"
        assert la_city['state_abbr'] == "CA"
        assert la_city['population'] == 3898747
        assert la_city['region'] == "Southern California"
        assert la_city['bounding_box'] == [-118.5, 34.0, -118.0, 34.5]
        assert la_city['onboarding_status'] == "IN_PROGRESS"

    def test_add_duplicate_city_to_yaml(self, temp_config):
        """Test adding duplicate city to YAML."""
        importer = CityImporter(temp_config)

        # Add city twice
        with patch.object(importer, 'fetch_bounding_box', return_value=None):
            city_id_1 = importer.add_city_to_yaml("Test City", "California", "CA")
            city_id_2 = importer.add_city_to_yaml("Test City", "California", "CA")

        # Should return same ID and not duplicate
        assert city_id_1 == city_id_2
        cities_with_id = [c for c in importer.cities_data['cities'] if c['city_id'] == city_id_1]
        assert len(cities_with_id) == 1  # Original one from fixture

    def test_add_city_to_database(self, temp_config, temp_db):
        """Test adding city to database."""
        importer = CityImporter(temp_config)

        # Add to YAML first
        with patch.object(importer, 'fetch_bounding_box', return_value=[-118.5, 34.0, -118.0, 34.5]):
            city_id = importer.add_city_to_yaml(
                city_name="Los Angeles",
                state="California",
                state_abbr="CA",
                population=3898747
            )

        # Add to database
        city = importer.add_city_to_database(city_id, temp_db)

        assert city.slug == "ca_los_angeles"
        assert city.name == "Los Angeles"
        assert city.state == "California"
        assert city.enabled is True
        assert city.extra_metadata['population'] == 3898747
        assert city.extra_metadata['bounding_box'] == [-118.5, 34.0, -118.0, 34.5]

    def test_import_shapefile(self, temp_config, temp_db, temp_shapefile):
        """Test importing pickup zones from shapefile."""
        importer = CityImporter(temp_config)

        # Create a city first
        with patch.object(importer, 'fetch_bounding_box', return_value=None):
            city_id = importer.add_city_to_yaml("Test City", "California", "CA")
        city = importer.add_city_to_database(city_id, temp_db)

        # Import shapefile
        zones = importer.import_shapefile(temp_shapefile, city.id, temp_db)

        assert len(zones) == 2
        assert zones[0].name == "Test Zone 1"
        assert zones[0].external_ref == "TZ1"
        assert zones[0].city_id == city.id
        assert zones[1].name == "Test Zone 2"
        assert zones[1].external_ref == "TZ2"

        # Verify zones in database
        db_zones = temp_db.query(PickupZone).filter_by(city_id=city.id).all()
        assert len(db_zones) == 2

    def test_import_shapefile_not_found(self, temp_config, temp_db):
        """Test importing non-existent shapefile."""
        importer = CityImporter(temp_config)

        with pytest.raises(FileNotFoundError):
            importer.import_shapefile("/nonexistent/file.geojson", 1, temp_db)

    def test_apply_template_alternating_week(self, temp_config, temp_db):
        """Test applying alternating week template."""
        importer = CityImporter(temp_config)

        # Create a city
        with patch.object(importer, 'fetch_bounding_box', return_value=None):
            city_id = importer.add_city_to_yaml("Test City", "California", "CA")
        city = importer.add_city_to_database(city_id, temp_db)

        # Apply template
        importer.apply_template("alternating_week", city.id, [], temp_db)

        # Verify zones created
        zones = temp_db.query(PickupZone).filter_by(city_id=city.id).all()
        assert len(zones) == 5

        # Verify schedules created
        schedules = temp_db.query(Schedule).filter_by(city_id=city.id).all()
        assert len(schedules) == 5

        # Check first schedule
        schedule = schedules[0]
        assert schedule.trash_day_of_week == "MON"
        assert schedule.recycling_day_of_week == "MON"
        assert schedule.green_day_of_week == "THU"
        assert schedule.source == "TEMPLATE"

    def test_apply_template_weekly_same_day(self, temp_config, temp_db):
        """Test applying weekly same day template."""
        importer = CityImporter(temp_config)

        # Create a city
        with patch.object(importer, 'fetch_bounding_box', return_value=None):
            city_id = importer.add_city_to_yaml("Test City", "California", "CA")
        city = importer.add_city_to_database(city_id, temp_db)

        # Apply template
        importer.apply_template("weekly_same_day", city.id, [], temp_db)

        # Verify zones and schedules
        zones = temp_db.query(PickupZone).filter_by(city_id=city.id).all()
        schedules = temp_db.query(Schedule).filter_by(city_id=city.id).all()

        assert len(zones) == 5
        assert len(schedules) == 5

        # Check Monday zone
        monday_zone = next(z for z in zones if "Monday" in z.name)
        monday_schedule = temp_db.query(Schedule).filter_by(pickup_zone_id=monday_zone.id).first()
        assert monday_schedule.trash_day_of_week == "MON"
        assert monday_schedule.recycling_day_of_week == "MON"
        assert monday_schedule.green_day_of_week == "MON"

    def test_apply_template_invalid(self, temp_config, temp_db):
        """Test applying invalid template."""
        importer = CityImporter(temp_config)

        with pytest.raises(ValueError):
            importer.apply_template("invalid_template", 1, [], temp_db)

    def test_apply_template_zone_based(self, temp_config, temp_db, temp_shapefile):
        """Test applying zone-based template with existing zones."""
        importer = CityImporter(temp_config)

        # Create a city
        with patch.object(importer, 'fetch_bounding_box', return_value=None):
            city_id = importer.add_city_to_yaml("Test City", "California", "CA")
        city = importer.add_city_to_database(city_id, temp_db)

        # Import zones from shapefile
        zones = importer.import_shapefile(temp_shapefile, city.id, temp_db)

        # Apply zone-based template (should not create new zones)
        importer.apply_template("zone_based", city.id, zones, temp_db)

        # Verify no additional zones created
        db_zones = temp_db.query(PickupZone).filter_by(city_id=city.id).all()
        assert len(db_zones) == 2

    def test_templates_available(self, temp_config):
        """Test that templates are properly defined."""
        importer = CityImporter(temp_config)

        assert "alternating_week" in importer.TEMPLATES
        assert "weekly_same_day" in importer.TEMPLATES
        assert "zone_based" in importer.TEMPLATES
        assert "manual" in importer.TEMPLATES

        # Check template structure
        alternating = importer.TEMPLATES["alternating_week"]
        assert "name" in alternating
        assert "description" in alternating
        assert "zones" in alternating
        assert len(alternating["zones"]) == 5


class TestCityImporterIntegration:
    """Integration tests for complete onboarding workflow."""

    @patch('scripts.city_importer.get_db')
    @patch.object(CityImporter, 'fetch_bounding_box')
    def test_full_onboarding_with_template(self, mock_bbox, mock_get_db, temp_config, temp_db):
        """Test complete onboarding workflow with template."""
        mock_bbox.return_value = [-118.5, 34.0, -118.0, 34.5]
        mock_get_db.return_value = iter([temp_db])

        importer = CityImporter(temp_config)

        city_id, city = importer.onboard_city(
            city_name="Los Angeles",
            state="California",
            state_abbr="CA",
            pickup_rule_template="alternating_week",
            population=3898747,
            region="Southern California"
        )

        # Verify YAML entry
        la_config = next((c for c in importer.cities_data['cities'] if c['city_id'] == city_id), None)
        assert la_config is not None
        assert la_config['name'] == "Los Angeles"
        assert la_config['onboarding_status'] == "COMPLETE"

        # Verify database entry
        assert city.slug == "ca_los_angeles"
        assert city.name == "Los Angeles"

        # Verify zones and schedules created from template
        zones = temp_db.query(PickupZone).filter_by(city_id=city.id).all()
        schedules = temp_db.query(Schedule).filter_by(city_id=city.id).all()
        assert len(zones) == 5
        assert len(schedules) == 5

    @patch('scripts.city_importer.get_db')
    @patch.object(CityImporter, 'fetch_bounding_box')
    def test_full_onboarding_with_shapefile(self, mock_bbox, mock_get_db, temp_config, temp_db, temp_shapefile):
        """Test complete onboarding workflow with shapefile."""
        mock_bbox.return_value = [-118.5, 34.0, -118.0, 34.5]
        mock_get_db.return_value = iter([temp_db])

        importer = CityImporter(temp_config)

        city_id, city = importer.onboard_city(
            city_name="Los Angeles",
            state="California",
            state_abbr="CA",
            shapefile_path=temp_shapefile,
            pickup_rule_template="zone_based",
            population=3898747
        )

        # Verify zones imported from shapefile
        zones = temp_db.query(PickupZone).filter_by(city_id=city.id).all()
        assert len(zones) == 2
        assert zones[0].name == "Test Zone 1"
        assert zones[1].name == "Test Zone 2"

    @patch('scripts.city_importer.get_db')
    @patch.object(CityImporter, 'fetch_bounding_box')
    def test_onboarding_time_under_10_minutes(self, mock_bbox, mock_get_db, temp_config, temp_db):
        """Test that onboarding completes quickly (simulated)."""
        import time

        mock_bbox.return_value = [-118.5, 34.0, -118.0, 34.5]
        mock_get_db.return_value = iter([temp_db])

        importer = CityImporter(temp_config)

        start_time = time.time()

        city_id, city = importer.onboard_city(
            city_name="Los Angeles",
            state="California",
            state_abbr="CA",
            pickup_rule_template="alternating_week",
            population=3898747
        )

        elapsed_time = time.time() - start_time

        # In test environment, should complete in seconds (not minutes)
        # In production with network calls, target is <10 minutes
        assert elapsed_time < 10.0  # 10 seconds for test
        assert city_id == "ca_los_angeles"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
