#!/usr/bin/env python3
"""
City Importer - Nationwide Mode

Quickly onboard a new city to TrashAlert in under 10 minutes.

Usage:
    # Add a new city from YAML
    python scripts/city_importer.py --city "Los Angeles" --state "CA"

    # Import from shapefile
    python scripts/city_importer.py --city "Los Angeles" --state "CA" --shapefile data/gis/la/zones.geojson

    # Use a pickup rule template
    python scripts/city_importer.py --city "Los Angeles" --state "CA" --template "alternating_week"

    # Full import with all options
    python scripts/city_importer.py --city "Los Angeles" --state "CA" \
        --shapefile data/gis/la/zones.geojson \
        --template "zone_based" \
        --bbox "-118.668,33.704,-118.155,34.337" \
        --population 3898747 \
        --region "Southern California"
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import geopandas as gpd
import requests
import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import get_db, engine
from app.models import City, PickupZone, Schedule
from utils.config_loader import ConfigLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CityImporter:
    """Handles importing new cities into TrashAlert."""

    # Pickup rule templates
    TEMPLATES = {
        "alternating_week": {
            "name": "Alternating Week Schedule",
            "description": "Trash weekly, recycling alternating weeks",
            "zones": [
                {"name": "Zone A", "trash": "MON", "recycling": "MON", "green": "THU"},
                {"name": "Zone B", "trash": "TUE", "recycling": "TUE", "green": "FRI"},
                {"name": "Zone C", "trash": "WED", "recycling": "WED", "green": "MON"},
                {"name": "Zone D", "trash": "THU", "recycling": "THU", "green": "TUE"},
                {"name": "Zone E", "trash": "FRI", "recycling": "FRI", "green": "WED"},
            ]
        },
        "weekly_same_day": {
            "name": "Weekly Same Day Schedule",
            "description": "All pickups on same day each week",
            "zones": [
                {"name": "Monday Zone", "trash": "MON", "recycling": "MON", "green": "MON"},
                {"name": "Tuesday Zone", "trash": "TUE", "recycling": "TUE", "green": "TUE"},
                {"name": "Wednesday Zone", "trash": "WED", "recycling": "WED", "green": "WED"},
                {"name": "Thursday Zone", "trash": "THU", "recycling": "THU", "green": "THU"},
                {"name": "Friday Zone", "trash": "FRI", "recycling": "FRI", "green": "FRI"},
            ]
        },
        "zone_based": {
            "name": "Zone-Based Schedule",
            "description": "Custom zones from GIS data, schedules assigned per zone",
            "zones": []  # Will be populated from shapefile
        },
        "manual": {
            "name": "Manual Configuration",
            "description": "No automatic schedule generation, manual entry required",
            "zones": []
        }
    }

    def __init__(self, config_path: str = "config/cities.yaml"):
        self.config_path = Path(config_path)
        self.config_loader = ConfigLoader()
        self.cities_data = self._load_cities_config()

    def _load_cities_config(self) -> Dict:
        """Load cities.yaml configuration."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def _save_cities_config(self):
        """Save updated cities.yaml configuration."""
        with open(self.config_path, 'w') as f:
            yaml.dump(self.cities_data, f, default_flow_style=False, sort_keys=False)
        logger.info(f"Updated {self.config_path}")

    def generate_city_id(self, city_name: str, state_abbr: str) -> str:
        """Generate city_id from name and state."""
        city_slug = city_name.lower().replace(' ', '_').replace('-', '_')
        state_slug = state_abbr.lower()
        return f"{state_slug}_{city_slug}"

    def fetch_bounding_box(self, city_name: str, state: str) -> Optional[List[float]]:
        """Fetch bounding box from Nominatim API."""
        logger.info(f"Fetching bounding box for {city_name}, {state}...")

        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                "q": f"{city_name}, {state}, USA",
                "format": "json",
                "limit": 1,
                "addressdetails": 1
            }
            headers = {"User-Agent": "TrashAlert/1.0"}

            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            results = response.json()
            if not results:
                logger.warning(f"No results found for {city_name}, {state}")
                return None

            bbox = results[0].get("boundingbox")
            if bbox:
                # Nominatim returns [min_lat, max_lat, min_lon, max_lon]
                # We need [min_lon, min_lat, max_lon, max_lat]
                min_lat, max_lat, min_lon, max_lon = map(float, bbox)
                return [min_lon, min_lat, max_lon, max_lat]

        except Exception as e:
            logger.error(f"Error fetching bounding box: {e}")
            return None

    def import_shapefile(self, shapefile_path: str, city_id: int, db: Session) -> List[PickupZone]:
        """Import pickup zones from shapefile/GeoJSON."""
        logger.info(f"Importing shapefile: {shapefile_path}")

        if not Path(shapefile_path).exists():
            raise FileNotFoundError(f"Shapefile not found: {shapefile_path}")

        # Read GeoJSON/Shapefile
        gdf = gpd.read_file(shapefile_path)
        logger.info(f"Loaded {len(gdf)} features from shapefile")

        zones = []
        for idx, row in gdf.iterrows():
            # Extract zone properties
            zone_name = row.get('name') or row.get('zone_name') or row.get('ZONE_NAME') or f"Zone {idx + 1}"
            external_ref = row.get('zone_id') or row.get('ZONE_ID') or str(idx + 1)

            # Store geometry and properties as JSON
            geometry_json = json.loads(gpd.GeoSeries([row.geometry]).to_json())

            extra_metadata = {
                "geometry": geometry_json["features"][0]["geometry"],
                "properties": {k: v for k, v in row.items() if k != 'geometry' and v is not None},
                "imported_from": shapefile_path
            }

            zone = PickupZone(
                city_id=city_id,
                name=zone_name,
                external_ref=external_ref,
                extra_metadata=extra_metadata
            )
            zones.append(zone)
            db.add(zone)

        db.commit()
        logger.info(f"Created {len(zones)} pickup zones")
        return zones

    def apply_template(self, template_name: str, city_id: int, zones: List[PickupZone], db: Session):
        """Apply pickup rule template to zones."""
        if template_name not in self.TEMPLATES:
            raise ValueError(f"Unknown template: {template_name}. Available: {list(self.TEMPLATES.keys())}")

        template = self.TEMPLATES[template_name]
        logger.info(f"Applying template: {template['name']}")

        if template_name in ["alternating_week", "weekly_same_day"]:
            # Create zones from template
            for zone_def in template["zones"]:
                # Check if zone already exists
                existing_zone = db.query(PickupZone).filter_by(
                    city_id=city_id,
                    name=zone_def["name"]
                ).first()

                if not existing_zone:
                    zone = PickupZone(
                        city_id=city_id,
                        name=zone_def["name"],
                        external_ref=zone_def["name"].upper().replace(" ", "_"),
                        extra_metadata={"template": template_name}
                    )
                    db.add(zone)
                    db.flush()
                else:
                    zone = existing_zone

                # Create schedule for this zone
                schedule = Schedule(
                    city_id=city_id,
                    pickup_zone_id=zone.id,
                    trash_day_of_week=zone_def["trash"],
                    recycling_day_of_week=zone_def.get("recycling"),
                    green_day_of_week=zone_def.get("green"),
                    source="TEMPLATE",
                    extra_metadata={"template": template_name}
                )
                db.add(schedule)

            db.commit()
            logger.info(f"Created {len(template['zones'])} zones with schedules")

        elif template_name == "zone_based":
            # Use existing zones from shapefile
            if not zones:
                logger.warning("No zones provided for zone_based template")
                return

            logger.info(f"Zone-based template: schedules must be configured manually for {len(zones)} zones")

        elif template_name == "manual":
            logger.info("Manual template: no automatic zones or schedules created")

    def add_city_to_yaml(
        self,
        city_name: str,
        state: str,
        state_abbr: str,
        bounding_box: Optional[List[float]] = None,
        shapefile_path: Optional[str] = None,
        pickup_rule_template: Optional[str] = None,
        population: Optional[int] = None,
        region: Optional[str] = None,
        timezone: str = "America/Los_Angeles",
        notes: str = ""
    ) -> str:
        """Add a new city to cities.yaml."""
        city_id = self.generate_city_id(city_name, state_abbr)

        # Check if city already exists
        existing_cities = [c for c in self.cities_data.get('cities', []) if c.get('city_id') == city_id]
        if existing_cities:
            logger.warning(f"City {city_id} already exists in YAML")
            return city_id

        # Auto-fetch bounding box if not provided
        if not bounding_box:
            bounding_box = self.fetch_bounding_box(city_name, state)

        # Build city entry
        city_entry = {
            "city_id": city_id,
            "name": city_name,
            "state": state,
            "state_abbr": state_abbr,
            "country": "USA",
            "has_official_pickup_zones": bool(shapefile_path),
            "pickup_zone_data_source": shapefile_path or "To be determined",
            "notes": notes or f"Added via city_importer.py"
        }

        # Add optional Nationwide Mode fields
        if bounding_box:
            city_entry["bounding_box"] = bounding_box
        if shapefile_path:
            city_entry["shapefile_path"] = shapefile_path
        if pickup_rule_template:
            city_entry["pickup_rule_template"] = pickup_rule_template
        if population:
            city_entry["population"] = population
        if region:
            city_entry["region"] = region
        if timezone:
            city_entry["timezone"] = timezone

        city_entry["onboarding_status"] = "IN_PROGRESS"

        # Add to config
        if 'cities' not in self.cities_data:
            self.cities_data['cities'] = []
        self.cities_data['cities'].append(city_entry)

        self._save_cities_config()
        logger.info(f"Added {city_name} ({city_id}) to cities.yaml")

        return city_id

    def add_city_to_database(self, city_id: str, db: Session) -> City:
        """Add city to database."""
        # Load city config from YAML
        city_config = next((c for c in self.cities_data.get('cities', []) if c['city_id'] == city_id), None)
        if not city_config:
            raise ValueError(f"City {city_id} not found in cities.yaml")

        # Check if city already exists in DB
        existing = db.query(City).filter_by(slug=city_id).first()
        if existing:
            logger.warning(f"City {city_id} already exists in database")
            return existing

        # Create city record
        city = City(
            slug=city_id,
            name=city_config['name'],
            state=city_config['state'],
            county=city_config.get('county'),
            region=city_config.get('region'),
            timezone=city_config.get('timezone', 'America/Los_Angeles'),
            enabled=True,
            extra_metadata={
                "state_abbr": city_config['state_abbr'],
                "country": city_config['country'],
                "bounding_box": city_config.get('bounding_box'),
                "population": city_config.get('population'),
                "onboarding_status": city_config.get('onboarding_status', 'PENDING'),
                "has_official_pickup_zones": city_config.get('has_official_pickup_zones', False),
                "pickup_zone_data_source": city_config.get('pickup_zone_data_source'),
                "notes": city_config.get('notes')
            }
        )

        db.add(city)
        db.commit()
        db.refresh(city)

        logger.info(f"Created city record in database: {city.name} (ID: {city.id})")
        return city

    def onboard_city(
        self,
        city_name: str,
        state: str,
        state_abbr: str,
        bounding_box: Optional[str] = None,
        shapefile_path: Optional[str] = None,
        pickup_rule_template: Optional[str] = None,
        population: Optional[int] = None,
        region: Optional[str] = None,
        timezone: str = "America/Los_Angeles",
        notes: str = ""
    ) -> Tuple[str, City]:
        """Complete onboarding workflow for a new city."""
        logger.info(f"=== Starting onboarding for {city_name}, {state} ===")

        # Parse bounding box if provided as string
        bbox_list = None
        if bounding_box:
            try:
                bbox_list = [float(x.strip()) for x in bounding_box.split(',')]
                if len(bbox_list) != 4:
                    raise ValueError("Bounding box must have 4 values")
            except Exception as e:
                logger.error(f"Invalid bounding box format: {e}")
                bbox_list = None

        # Step 1: Add to YAML
        city_id = self.add_city_to_yaml(
            city_name=city_name,
            state=state,
            state_abbr=state_abbr,
            bounding_box=bbox_list,
            shapefile_path=shapefile_path,
            pickup_rule_template=pickup_rule_template,
            population=population,
            region=region,
            timezone=timezone,
            notes=notes
        )

        # Step 2: Add to database
        db = next(get_db())
        try:
            city = self.add_city_to_database(city_id, db)

            # Step 3: Import shapefile if provided
            zones = []
            if shapefile_path:
                zones = self.import_shapefile(shapefile_path, city.id, db)

            # Step 4: Apply template if provided
            if pickup_rule_template:
                self.apply_template(pickup_rule_template, city.id, zones, db)

            # Step 5: Update onboarding status
            self._update_onboarding_status(city_id, "COMPLETE")

            logger.info(f"=== Successfully onboarded {city_name}! ===")
            logger.info(f"City ID: {city_id}")
            logger.info(f"Database ID: {city.id}")
            logger.info(f"Zones created: {len(zones)}")

            return city_id, city

        finally:
            db.close()

    def _update_onboarding_status(self, city_id: str, status: str):
        """Update onboarding status in YAML."""
        for city in self.cities_data.get('cities', []):
            if city.get('city_id') == city_id:
                city['onboarding_status'] = status
                break
        self._save_cities_config()


def main():
    parser = argparse.ArgumentParser(
        description="Import a new city into TrashAlert (Nationwide Mode)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument("--city", required=True, help="City name (e.g., 'Los Angeles')")
    parser.add_argument("--state", required=True, help="Full state name (e.g., 'California')")
    parser.add_argument("--state-abbr", help="State abbreviation (e.g., 'CA'). Auto-derived if not provided")
    parser.add_argument("--bbox", "--bounding-box", help="Bounding box as 'min_lon,min_lat,max_lon,max_lat'")
    parser.add_argument("--shapefile", help="Path to shapefile/GeoJSON for pickup zones")
    parser.add_argument("--template", choices=list(CityImporter.TEMPLATES.keys()),
                       help="Pickup rule template to apply")
    parser.add_argument("--population", type=int, help="City population")
    parser.add_argument("--region", help="Regional grouping (e.g., 'Southern California')")
    parser.add_argument("--timezone", default="America/Los_Angeles", help="IANA timezone")
    parser.add_argument("--notes", default="", help="Additional notes")

    args = parser.parse_args()

    # Auto-derive state abbreviation if not provided
    state_abbr = args.state_abbr
    if not state_abbr:
        # Simple mapping for common states (can be extended)
        state_abbr_map = {
            "california": "CA", "texas": "TX", "florida": "FL", "new york": "NY",
            "pennsylvania": "PA", "illinois": "IL", "ohio": "OH", "georgia": "GA",
            "north carolina": "NC", "michigan": "MI", "new jersey": "NJ",
            "virginia": "VA", "washington": "WA", "arizona": "AZ", "massachusetts": "MA",
            "tennessee": "TN", "indiana": "IN", "missouri": "MO", "maryland": "MD",
            "wisconsin": "WI", "colorado": "CO", "minnesota": "MN", "south carolina": "SC",
            "alabama": "AL", "louisiana": "LA", "kentucky": "KY", "oregon": "OR",
            "oklahoma": "OK", "connecticut": "CT", "utah": "UT", "iowa": "IA",
            "nevada": "NV", "arkansas": "AR", "mississippi": "MS", "kansas": "KS",
            "new mexico": "NM", "nebraska": "NE", "west virginia": "WV", "idaho": "ID",
            "hawaii": "HI", "new hampshire": "NH", "maine": "ME", "montana": "MT",
            "rhode island": "RI", "delaware": "DE", "south dakota": "SD",
            "north dakota": "ND", "alaska": "AK", "vermont": "VT", "wyoming": "WY"
        }
        state_abbr = state_abbr_map.get(args.state.lower())
        if not state_abbr:
            logger.error(f"Could not auto-derive state abbreviation for '{args.state}'. Please provide --state-abbr")
            sys.exit(1)
        logger.info(f"Auto-derived state abbreviation: {state_abbr}")

    # Create importer and run onboarding
    importer = CityImporter()

    try:
        city_id, city = importer.onboard_city(
            city_name=args.city,
            state=args.state,
            state_abbr=state_abbr,
            bounding_box=args.bbox,
            shapefile_path=args.shapefile,
            pickup_rule_template=args.template,
            population=args.population,
            region=args.region,
            timezone=args.timezone,
            notes=args.notes
        )

        print("\n" + "="*60)
        print(f"✓ Successfully onboarded {args.city}, {state_abbr}!")
        print("="*60)
        print(f"City ID: {city_id}")
        print(f"Database ID: {city.id}")
        print(f"\nNext steps:")
        print(f"1. Run address pipeline: python scripts/run_full_pipeline.py --city '{args.city}'")
        print(f"2. Verify data: python scripts/verify_city_integrity.py --city '{city_id}'")
        print(f"3. Test API: curl http://localhost:8000/lookup?address=123%20Main%20St&city={args.city}&state={state_abbr}")

    except Exception as e:
        logger.error(f"Onboarding failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
