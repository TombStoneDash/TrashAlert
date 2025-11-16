#!/usr/bin/env python3
"""
Create sample raw OSM address data for testing the sampling script.
This generates realistic-looking addresses for San Diego and Imperial Valley cities.
"""

import pandas as pd
import random
from pathlib import Path

# Set seed for reproducibility
random.seed(42)

def generate_sample_data():
    """Generate sample address data."""
    addresses = []

    # San Diego - generate 200 addresses across multiple subdivisions
    san_diego_subdivisions = ['Downtown', 'La Jolla', 'Pacific Beach', 'North Park',
                               'Hillcrest', 'Mission Valley', 'Point Loma', 'Clairemont']
    san_diego_streets = ['Main St', 'Broadway', 'Market St', 'University Ave', 'El Cajon Blvd',
                         'Park Blvd', 'Adams Ave', 'Washington St', 'India St', 'Kettner Blvd']

    for i in range(200):
        subdivision = random.choice(san_diego_subdivisions)
        street = random.choice(san_diego_streets)
        house_number = random.randint(100, 9999)

        # Generate lat/lon roughly in San Diego area
        lat = 32.7157 + random.uniform(-0.15, 0.15)
        lon = -117.1611 + random.uniform(-0.15, 0.15)

        addresses.append({
            'city_name': 'San Diego',
            'subdivision_id': subdivision,
            'house_number': str(house_number),
            'street': street,
            'lat': lat,
            'lon': lon,
            'osm_id': f'node/{100000 + i}'
        })

    # El Centro - generate 80 addresses
    el_centro_subdivisions = ['Downtown', 'West', 'East', 'North']
    el_centro_streets = ['Main St', 'Imperial Ave', 'Broadway', 'State St', 'Commercial Ave']

    for i in range(80):
        subdivision = random.choice(el_centro_subdivisions) if random.random() > 0.3 else None
        street = random.choice(el_centro_streets)
        house_number = random.randint(100, 5999)

        lat = 32.7950 + random.uniform(-0.05, 0.05)
        lon = -115.5630 + random.uniform(-0.05, 0.05)

        addresses.append({
            'city_name': 'El Centro',
            'subdivision_id': subdivision,
            'house_number': str(house_number),
            'street': street,
            'lat': lat,
            'lon': lon,
            'osm_id': f'node/{200000 + i}'
        })

    # Calexico - generate 65 addresses
    calexico_streets = ['Imperial Ave', 'Heber Ave', 'Rockwood Ave', 'Birch St', 'Cedar St']

    for i in range(65):
        street = random.choice(calexico_streets)
        house_number = random.randint(100, 4999)

        lat = 32.6789 + random.uniform(-0.03, 0.03)
        lon = -115.4989 + random.uniform(-0.03, 0.03)

        addresses.append({
            'city_name': 'Calexico',
            'subdivision_id': None,
            'house_number': str(house_number),
            'street': street,
            'lat': lat,
            'lon': lon,
            'osm_id': f'node/{300000 + i}'
        })

    # Brawley - generate 45 addresses
    brawley_streets = ['Main St', 'Plaza Ave', 'Western Ave', 'Imperial Ave']

    for i in range(45):
        street = random.choice(brawley_streets)
        house_number = random.randint(100, 3999)

        lat = 32.9786 + random.uniform(-0.02, 0.02)
        lon = -115.5303 + random.uniform(-0.02, 0.02)

        addresses.append({
            'city_name': 'Brawley',
            'subdivision_id': None,
            'house_number': str(house_number),
            'street': street,
            'lat': lat,
            'lon': lon,
            'osm_id': f'node/{400000 + i}'
        })

    # Imperial - small city with only 30 addresses (less than 50)
    imperial_streets = ['Main St', 'Aten Rd', 'Highway 111', 'Worthington Rd']

    for i in range(30):
        street = random.choice(imperial_streets)
        house_number = random.randint(100, 2999)

        lat = 32.8473 + random.uniform(-0.02, 0.02)
        lon = -115.5694 + random.uniform(-0.02, 0.02)

        addresses.append({
            'city_name': 'Imperial',
            'subdivision_id': None,
            'house_number': str(house_number),
            'street': street,
            'lat': lat,
            'lon': lon,
            'osm_id': f'node/{500000 + i}'
        })

    # Holtville - small city with 25 addresses
    holtville_streets = ['Holt Ave', 'Fifth St', 'Sixth St', 'Pine Ave']

    for i in range(25):
        street = random.choice(holtville_streets)
        house_number = random.randint(100, 1999)

        lat = 32.8114 + random.uniform(-0.01, 0.01)
        lon = -115.3803 + random.uniform(-0.01, 0.01)

        addresses.append({
            'city_name': 'Holtville',
            'subdivision_id': None,
            'house_number': str(house_number),
            'street': street,
            'lat': lat,
            'lon': lon,
            'osm_id': f'node/{600000 + i}'
        })

    # Add a few duplicates to test deduplication
    addresses.append(addresses[0].copy())
    addresses.append(addresses[50].copy())

    # Add a few with null coordinates to test filtering
    null_address_1 = addresses[10].copy()
    null_address_1['lat'] = None
    addresses.append(null_address_1)

    null_address_2 = addresses[100].copy()
    null_address_2['lon'] = None
    addresses.append(null_address_2)

    return pd.DataFrame(addresses)


def main():
    """Generate and save sample data."""
    output_path = Path(__file__).parent.parent / 'data' / 'addresses_osm_raw.csv'

    print(f"Generating sample raw address data...")
    df = generate_sample_data()

    print(f"Generated {len(df)} addresses")
    print(f"Cities: {df['city_name'].value_counts().to_dict()}")

    df.to_csv(output_path, index=False)
    print(f"\nSaved to: {output_path}")


if __name__ == '__main__':
    main()
