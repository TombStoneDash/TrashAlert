"""
Data processor for cleaning and normalizing address data from OSM
"""
import json
import logging
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class DataProcessor:
    """Process and clean address data from various sources"""

    @staticmethod
    def extract_addresses_from_osm(osm_data: Dict, city_id: int) -> List[Dict]:
        """
        Extract and normalize address records from OSM data

        Args:
            osm_data: Raw OSM/Overpass API response
            city_id: Database city ID to associate with addresses

        Returns:
            List of normalized address dicts
        """
        if not osm_data or 'elements' not in osm_data:
            logger.warning("No elements found in OSM data")
            return []

        addresses = []
        elements = osm_data['elements']

        logger.info(f"Processing {len(elements)} OSM elements")

        for element in elements:
            try:
                addr = DataProcessor._process_osm_element(element, city_id)
                if addr:
                    addresses.append(addr)
            except Exception as e:
                logger.warning(f"Error processing element {element.get('id')}: {e}")
                continue

        logger.info(f"Extracted {len(addresses)} valid addresses from {len(elements)} elements")
        return addresses

    @staticmethod
    def _process_osm_element(element: Dict, city_id: int) -> Optional[Dict]:
        """
        Process a single OSM element into an address record

        Args:
            element: OSM element (node or way)
            city_id: Database city ID

        Returns:
            Normalized address dict or None if invalid
        """
        tags = element.get('tags', {})

        # Extract address components
        street_number = tags.get('addr:housenumber')
        street_name = tags.get('addr:street')

        # Must have at least house number and street
        if not street_number or not street_name:
            return None

        # Get coordinates
        lat, lon = DataProcessor._get_coordinates(element)
        if lat is None or lon is None:
            return None

        # Build address record
        address = {
            'city_id': city_id,
            'street_number': street_number,
            'street_name': street_name,
            'unit': tags.get('addr:unit'),
            'postal_code': tags.get('addr:postcode'),
            'latitude': lat,
            'longitude': lon,
            'osm_id': element.get('id'),
            'osm_type': element.get('type'),
            'building_type': tags.get('building'),
            'data_source': 'osm',
        }

        return address

    @staticmethod
    def _get_coordinates(element: Dict) -> tuple:
        """
        Extract latitude and longitude from OSM element

        Args:
            element: OSM element (node or way)

        Returns:
            Tuple of (lat, lon) or (None, None) if not found
        """
        # For nodes, coordinates are directly available
        if element['type'] == 'node':
            return element.get('lat'), element.get('lon')

        # For ways, use center coordinates if available
        if element['type'] == 'way' and 'center' in element:
            return element['center'].get('lat'), element['center'].get('lon')

        # Try to calculate center from geometry
        if 'geometry' in element and element['geometry']:
            geom = element['geometry']
            lats = [p['lat'] for p in geom]
            lons = [p['lon'] for p in geom]
            return sum(lats) / len(lats), sum(lons) / len(lons)

        return None, None

    @staticmethod
    def validate_addresses(addresses: List[Dict]) -> Dict:
        """
        Validate addresses and return quality metrics

        Args:
            addresses: List of address dicts

        Returns:
            Dict with validation statistics
        """
        stats = {
            'total': len(addresses),
            'with_postal_code': 0,
            'with_unit': 0,
            'with_building_type': 0,
            'missing_coordinates': 0,
            'missing_street_number': 0,
            'missing_street_name': 0,
        }

        for addr in addresses:
            if addr.get('postal_code'):
                stats['with_postal_code'] += 1
            if addr.get('unit'):
                stats['with_unit'] += 1
            if addr.get('building_type'):
                stats['with_building_type'] += 1
            if not addr.get('latitude') or not addr.get('longitude'):
                stats['missing_coordinates'] += 1
            if not addr.get('street_number'):
                stats['missing_street_number'] += 1
            if not addr.get('street_name'):
                stats['missing_street_name'] += 1

        stats['completeness_pct'] = (
            (stats['total'] - stats['missing_coordinates'] -
             stats['missing_street_number'] - stats['missing_street_name']) /
            stats['total'] * 100 if stats['total'] > 0 else 0
        )

        return stats

    @staticmethod
    def deduplicate_addresses(addresses: List[Dict]) -> List[Dict]:
        """
        Remove duplicate addresses based on OSM ID

        Args:
            addresses: List of address dicts

        Returns:
            Deduplicated list
        """
        seen = set()
        unique = []

        for addr in addresses:
            key = (addr.get('osm_id'), addr.get('osm_type'))
            if key not in seen:
                seen.add(key)
                unique.append(addr)

        removed = len(addresses) - len(unique)
        if removed > 0:
            logger.info(f"Removed {removed} duplicate addresses")

        return unique

    @staticmethod
    def save_processed_data(data: List[Dict], output_file: Path):
        """Save processed data to JSON file"""
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved {len(data)} records to {output_file}")

    @staticmethod
    def load_processed_data(input_file: Path) -> List[Dict]:
        """Load processed data from JSON file"""
        if not input_file.exists():
            logger.warning(f"File not found: {input_file}")
            return []

        with open(input_file, 'r') as f:
            data = json.load(f)
        logger.info(f"Loaded {len(data)} records from {input_file}")
        return data


if __name__ == "__main__":
    # Test data processing
    logging.basicConfig(level=logging.INFO)

    # Sample OSM data
    test_data = {
        'elements': [
            {
                'type': 'node',
                'id': 12345,
                'lat': 32.7915,
                'lon': -115.5631,
                'tags': {
                    'addr:housenumber': '123',
                    'addr:street': 'Main Street',
                    'addr:postcode': '92243',
                    'building': 'house'
                }
            }
        ]
    }

    processor = DataProcessor()
    addresses = processor.extract_addresses_from_osm(test_data, city_id=1)
    print(f"Extracted addresses: {addresses}")

    stats = processor.validate_addresses(addresses)
    print(f"Validation stats: {stats}")
