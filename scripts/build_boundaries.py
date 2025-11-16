#!/usr/bin/env python3
"""
Build city boundaries GeoJSON for San Diego and Imperial Valley cities.
Uses simplified polygons based on approximate boundaries.
"""

import json
import sys

def create_approximate_polygon(center_lon: float, center_lat: float,
                              width: float, height: float) -> dict:
    """
    Create an approximate rectangular polygon around a center point.
    Width and height in degrees (approximately).
    """
    half_w = width / 2
    half_h = height / 2

    # Create a simple rectangle
    coords = [
        [center_lon - half_w, center_lat - half_h],  # SW
        [center_lon + half_w, center_lat - half_h],  # SE
        [center_lon + half_w, center_lat + half_h],  # NE
        [center_lon - half_w, center_lat + half_h],  # NW
        [center_lon - half_w, center_lat - half_h],  # Close the ring
    ]

    return {
        "type": "Polygon",
        "coordinates": [coords]
    }

def build_city_boundaries():
    """
    Build city_boundaries.geojson with approximate city boundaries.
    """
    print("Building city boundaries GeoJSON...")
    print("=" * 60)

    # City data: approximate centers and sizes (in degrees)
    # These are simplified for demonstration - real data would be more complex
    cities = [
        {
            "city_id": "SAN_DIEGO",
            "name": "San Diego",
            "state": "CA",
            "county": "San Diego",
            "center_lon": -117.1611,
            "center_lat": 32.7157,
            "width": 0.7,  # Approximate width in degrees
            "height": 0.5  # Approximate height in degrees
        },
        {
            "city_id": "EL_CENTRO",
            "name": "El Centro",
            "state": "CA",
            "county": "Imperial",
            "center_lon": -115.5631,
            "center_lat": 32.7920,
            "width": 0.12,
            "height": 0.10
        },
        {
            "city_id": "BRAWLEY",
            "name": "Brawley",
            "state": "CA",
            "county": "Imperial",
            "center_lon": -115.5303,
            "center_lat": 32.9787,
            "width": 0.08,
            "height": 0.08
        },
        {
            "city_id": "IMPERIAL",
            "name": "Imperial",
            "state": "CA",
            "county": "Imperial",
            "center_lon": -115.5694,
            "center_lat": 32.8473,
            "width": 0.06,
            "height": 0.06
        },
        {
            "city_id": "CALEXICO",
            "name": "Calexico",
            "state": "CA",
            "county": "Imperial",
            "center_lon": -115.4989,
            "center_lat": 32.6789,
            "width": 0.08,
            "height": 0.08
        },
        {
            "city_id": "HOLTVILLE",
            "name": "Holtville",
            "state": "CA",
            "county": "Imperial",
            "center_lon": -115.3803,
            "center_lat": 32.8112,
            "width": 0.05,
            "height": 0.05
        }
    ]

    features = []

    for city in cities:
        print(f"Creating boundary for {city['name']}...")
        geometry = create_approximate_polygon(
            city['center_lon'],
            city['center_lat'],
            city['width'],
            city['height']
        )

        features.append({
            "type": "Feature",
            "properties": {
                "city_id": city['city_id'],
                "name": city['name'],
                "state": city['state'],
                "county": city['county']
            },
            "geometry": geometry
        })

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    # Write to file
    output_path = "data/city_boundaries.geojson"
    with open(output_path, "w") as f:
        json.dump(geojson, f, indent=2)

    print("\n" + "=" * 60)
    print(f"✓ Successfully created {output_path}")
    print(f"  Total cities: {len(features)}")
    print("\nCities included:")
    for feature in features:
        props = feature["properties"]
        geom_type = feature["geometry"]["type"]
        print(f"  - {props['name']:15} (ID: {props['city_id']:12}, County: {props['county']:10}, Geom: {geom_type})")

    print("\nNote: These are simplified rectangular boundaries.")
    print("      In production, use actual city boundary data from official sources.")

    return output_path

if __name__ == "__main__":
    try:
        build_city_boundaries()
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
