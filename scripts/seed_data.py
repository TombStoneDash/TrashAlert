"""
Seed realistic pilot data using actual street names and coordinates
This module contains real street names from each city gathered from official sources
"""
import random
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# Real city data with approximate boundaries (from public records and maps)
CITY_DATA = {
    "El Centro": {
        "state": "California",
        "county": "Imperial County",
        "center_lat": 32.7915,
        "center_lon": -115.5631,
        "postal_code": "92243",
        "bbox": {
            "north": 32.82,
            "south": 32.76,
            "east": -115.53,
            "west": -115.60
        },
        # Real streets from city records
        "streets": [
            "Main Street", "State Street", "Imperial Avenue", "Broadway",
            "Commercial Avenue", "Orange Avenue", "Vine Street", "Adams Avenue",
            "Hamilton Avenue", "Heil Avenue", "Heber Avenue", "Danenberg Drive",
            "Wake Avenue", "Ross Avenue", "Lincoln Avenue", "Sandalwood Drive",
            "Smoketree Drive", "Ocotillo Drive", "Pepper Drive"
        ]
    },
    "Brawley": {
        "state": "California",
        "county": "Imperial County",
        "center_lat": 32.9786,
        "center_lon": -115.5303,
        "postal_code": "92227",
        "bbox": {
            "north": 33.00,
            "south": 32.96,
            "east": -115.50,
            "west": -115.56
        },
        "streets": [
            "Main Street", "Imperial Avenue", "Western Avenue", "Brawley Avenue",
            "Plaza Street", "Highway 111", "Highway 78", "A Street", "B Street",
            "C Street", "D Street", "E Street", "F Street", "G Street",
            "First Street", "Second Street", "Third Street", "Fourth Street"
        ]
    },
    "Imperial": {
        "state": "California",
        "county": "Imperial County",
        "center_lat": 32.8476,
        "center_lon": -115.5694,
        "postal_code": "92251",
        "bbox": {
            "north": 32.87,
            "south": 32.82,
            "east": -115.55,
            "west": -115.59
        },
        "streets": [
            "Imperial Avenue", "Aten Road", "Barioni Boulevard", "Austin Road",
            "La Brucherie Road", "Dogwood Road", "Getty Street", "Magnolia Street",
            "Villa Avenue", "Worthington Road", "Hanlon Road", "Zenos Way",
            "Tiger Lily Lane", "Dahlia Court", "Jasmine Way"
        ]
    },
    "Calexico": {
        "state": "California",
        "county": "Imperial County",
        "center_lat": 32.6790,
        "center_lon": -115.4989,
        "postal_code": "92231",
        "bbox": {
            "north": 32.72,
            "south": 32.67,
            "east": -115.48,
            "west": -115.52
        },
        "streets": [
            "Imperial Avenue", "Heffernan Avenue", "Birch Street", "Cole Road",
            "Second Street", "Third Street", "Fourth Street", "Fifth Street",
            "Sixth Street", "Seventh Street", "Paulin Avenue", "Rockwood Avenue",
            "George Avenue", "Heber Avenue", "Andrade Avenue", "Carr Road"
        ]
    },
    "Holtville": {
        "state": "California",
        "county": "Imperial County",
        "center_lat": 32.8116,
        "center_lon": -115.3803,
        "postal_code": "92250",
        "bbox": {
            "north": 32.83,
            "south": 32.79,
            "east": -115.36,
            "west": -115.40
        },
        "streets": [
            "Fifth Street", "Holt Avenue", "Sixth Street", "Seventh Street",
            "Eighth Street", "Fourth Street", "Third Street", "Cedar Avenue",
            "Olive Avenue", "Orange Avenue", "Grape Avenue", "Fig Avenue",
            "Elm Avenue", "Beale Avenue", "Fern Avenue", "Pine Avenue"
        ]
    },
    "San Diego": {
        "state": "California",
        "county": "San Diego County",
        "center_lat": 32.7157,
        "center_lon": -117.1611,
        # San Diego has multiple postal codes, using a central one
        "postal_code": "92101",
        "bbox": {
            "north": 33.11,
            "south": 32.53,
            "east": -116.91,
            "west": -117.28
        },
        # Sample of major streets in downtown/central San Diego
        "streets": [
            "Broadway", "Market Street", "Island Avenue", "G Street", "F Street",
            "E Street", "C Street", "B Street", "A Street", "Ash Street",
            "Beech Street", "Cedar Street", "Date Street", "Elm Street",
            "Front Street", "First Avenue", "Second Avenue", "Third Avenue",
            "Fourth Avenue", "Fifth Avenue", "Sixth Avenue", "Seventh Avenue",
            "Park Boulevard", "University Avenue", "El Cajon Boulevard"
        ]
    }
}


class DataSeeder:
    """Generate realistic pilot data using actual city information"""

    @staticmethod
    def generate_addresses_for_city(city_name: str, count: int = 100) -> List[Dict]:
        """
        Generate realistic addresses for a city using actual streets

        Args:
            city_name: Name of the city
            count: Number of addresses to generate

        Returns:
            List of address dicts with real street names and realistic coordinates
        """
        if city_name not in CITY_DATA:
            logger.error(f"City {city_name} not found in seed data")
            return []

        city_info = CITY_DATA[city_name]
        addresses = []

        for i in range(count):
            street = random.choice(city_info["streets"])

            # Generate realistic street number (1-9999)
            street_number = str(random.randint(1, 9999))

            # Add directional prefix sometimes (N, S, E, W)
            if random.random() < 0.3:
                direction = random.choice(["N", "S", "E", "W"])
                street_number = f"{direction} {street_number}"

            # Generate coordinates within city bounding box
            # Add some clustering around the center for realism
            if random.random() < 0.7:
                # 70% clustered near center
                lat = random.gauss(city_info["center_lat"], 0.01)
                lon = random.gauss(city_info["center_lon"], 0.01)
            else:
                # 30% distributed across bounding box
                lat = random.uniform(
                    city_info["bbox"]["south"],
                    city_info["bbox"]["north"]
                )
                lon = random.uniform(
                    city_info["bbox"]["west"],
                    city_info["bbox"]["east"]
                )

            # Clamp to bounding box
            lat = max(city_info["bbox"]["south"], min(city_info["bbox"]["north"], lat))
            lon = max(city_info["bbox"]["west"], min(city_info["bbox"]["east"], lon))

            # Occasional unit numbers for multi-unit buildings
            unit = None
            if random.random() < 0.15:  # 15% have unit numbers
                unit = f"#{random.randint(1, 24)}"

            # Building type based on street number patterns
            building_type = None
            if random.random() < 0.6:  # 60% are houses
                building_type = "house"
            elif random.random() < 0.8:  # 20% are apartments
                building_type = "apartments"
            elif random.random() < 0.95:  # 15% are commercial
                building_type = "commercial"
            # 5% are other/unknown

            address = {
                "street_number": street_number,
                "street_name": street,
                "unit": unit,
                "postal_code": city_info["postal_code"],
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "osm_id": f"seed_{city_name.lower().replace(' ', '_')}_{i}",
                "osm_type": "node",
                "building_type": building_type,
                "data_source": "seed_real_streets",
            }

            addresses.append(address)

        logger.info(f"Generated {len(addresses)} addresses for {city_name}")
        return addresses

    @staticmethod
    def get_city_boundary_info(city_name: str) -> Dict:
        """
        Get boundary information for a city

        Args:
            city_name: Name of the city

        Returns:
            Dict with city boundary info
        """
        if city_name not in CITY_DATA:
            return None

        city_info = CITY_DATA[city_name]

        return {
            "name": city_name,
            "state": city_info["state"],
            "county": city_info["county"],
            "bbox_north": city_info["bbox"]["north"],
            "bbox_south": city_info["bbox"]["south"],
            "bbox_east": city_info["bbox"]["east"],
            "bbox_west": city_info["bbox"]["west"],
            "osm_relation_id": None,  # Would come from OSM in production
            "boundary_geojson": None,  # Would come from OSM in production
        }


if __name__ == "__main__":
    # Test the seeder
    logging.basicConfig(level=logging.INFO)
    seeder = DataSeeder()

    # Generate sample data for Holtville
    addresses = seeder.generate_addresses_for_city("Holtville", count=50)

    print(f"\nSample addresses for Holtville:")
    for addr in addresses[:5]:
        print(f"  {addr['street_number']} {addr['street_name']}, {addr['postal_code']}")
        print(f"    ({addr['latitude']}, {addr['longitude']})")

    # Get boundary info
    boundary = seeder.get_city_boundary_info("Holtville")
    print(f"\nBoundary info: {boundary}")
