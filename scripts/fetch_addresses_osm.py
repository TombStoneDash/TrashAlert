#!/usr/bin/env python3
"""
Fetch residential addresses from OpenStreetMap using Overpass API.

This script queries OSM for addresses with housenumber and street tags
within city boundaries, filters for residential buildings, and exports
to CSV with subdivision assignment via point-in-polygon.
"""

import requests
import json
import csv
import time
import sys
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from shapely.geometry import Point, shape, Polygon
from shapely.ops import unary_union

# Cities to query (name, Overpass area ID suffix)
# Area IDs: search "CityName" on Nominatim, add 3600000000 to relation ID
CITIES = [
    {"name": "Pittsburgh", "area_id": 3600178723},
    {"name": "Philadelphia", "area_id": 3600188022},
    {"name": "Boston", "area_id": 3600125326},
    {"name": "Chicago", "area_id": 3600122604},
    {"name": "San Francisco", "area_id": 3600111968},
    {"name": "Seattle", "area_id": 3600237385},
]

# Overpass API endpoints (try multiple if one fails)
OVERPASS_URLS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# Rate limiting: 1 request per 10 seconds
RATE_LIMIT_SECONDS = 10

# HTTP headers for requests
HEADERS = {
    "User-Agent": "TrashAlert Address Fetcher/1.0 (https://github.com/TombStoneDash/TrashAlert)",
    "Accept": "application/json",
}

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds

# Residential building types
RESIDENTIAL_BUILDING_TYPES = [
    "house",
    "residential",
    "detached",
    "semidetached_house",
    "terrace",
    "apartments",
    "bungalow",
    "cabin",
    "farm",
    "ger",
    "static_caravan",
]


def build_overpass_query(city_name: str, area_id: int) -> str:
    """
    Build an Overpass QL query for residential addresses in a city.

    Args:
        city_name: Name of the city
        area_id: Overpass area ID for the city

    Returns:
        Overpass QL query string
    """
    # Build filter for residential building types
    building_filter = "|".join(RESIDENTIAL_BUILDING_TYPES)

    query = f"""
[out:json][timeout:180];
area({area_id})->.city;
(
  // Nodes with addresses
  node(area.city)["addr:housenumber"]["addr:street"]["building"~"^({building_filter})$"];

  // Ways (buildings) with addresses
  way(area.city)["addr:housenumber"]["addr:street"]["building"~"^({building_filter})$"];

  // Relations with addresses (less common)
  relation(area.city)["addr:housenumber"]["addr:street"]["building"~"^({building_filter})$"];
);
out center;
"""
    return query


def query_overpass(query: str, max_retries: int = MAX_RETRIES) -> Optional[Dict]:
    """
    Query the Overpass API with retry logic and multiple endpoints.

    Args:
        query: Overpass QL query string
        max_retries: Maximum number of retry attempts

    Returns:
        JSON response from Overpass API, or None if all retries fail
    """
    # Try each endpoint
    for url_idx, overpass_url in enumerate(OVERPASS_URLS):
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    overpass_url,
                    data={"data": query},
                    headers=HEADERS,
                    timeout=300,
                )
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                wait_time = RETRY_BACKOFF_BASE ** attempt
                is_last_attempt = (attempt == max_retries - 1) and (url_idx == len(OVERPASS_URLS) - 1)

                if not is_last_attempt:
                    endpoint_name = overpass_url.split("//")[1].split("/")[0]
                    print(f"  ⚠️  [{endpoint_name}] Request failed: {e}. Retrying in {wait_time}s...", file=sys.stderr)
                    time.sleep(wait_time)
                else:
                    print(f"  ❌ All endpoints failed after {max_retries} attempts: {e}", file=sys.stderr)
                    return None

        # If we get here, all retries for this endpoint failed, try next endpoint
        if url_idx < len(OVERPASS_URLS) - 1:
            print(f"  ⚠️  Trying alternative endpoint...", file=sys.stderr)

    return None


def extract_coordinates(element: Dict) -> Optional[Tuple[float, float]]:
    """
    Extract latitude and longitude from an OSM element.

    Args:
        element: OSM element (node, way, or relation)

    Returns:
        Tuple of (lat, lon) or None if coordinates cannot be extracted
    """
    if element["type"] == "node":
        return (element["lat"], element["lon"])
    elif "center" in element:
        return (element["center"]["lat"], element["center"]["lon"])
    return None


def load_subdivision_polygons() -> List[Dict]:
    """
    Load subdivision boundary polygons from GeoJSON.

    Returns:
        List of subdivision dictionaries with 'id' and 'geometry' (Shapely polygon)
    """
    subdivision_file = Path(__file__).parent.parent / "data" / "subdivisions.geojson"

    if not subdivision_file.exists():
        print(f"  ⚠️  Subdivision file not found: {subdivision_file}", file=sys.stderr)
        print(f"  ℹ️  Addresses will have null subdivision_id", file=sys.stderr)
        return []

    with open(subdivision_file) as f:
        geojson_data = json.load(f)

    subdivisions = []
    for feature in geojson_data.get("features", []):
        subdivision_id = feature.get("properties", {}).get("id") or feature.get("id")
        geometry = shape(feature["geometry"])
        subdivisions.append({
            "id": subdivision_id,
            "geometry": geometry,
        })

    return subdivisions


def find_subdivision(lat: float, lon: float, subdivisions: List[Dict]) -> Optional[str]:
    """
    Find which subdivision contains the given point.

    Args:
        lat: Latitude
        lon: Longitude
        subdivisions: List of subdivision polygons

    Returns:
        Subdivision ID or None if point is not in any subdivision
    """
    if not subdivisions:
        return None

    point = Point(lon, lat)
    for subdivision in subdivisions:
        if subdivision["geometry"].contains(point):
            return subdivision["id"]

    return None


def generate_demo_data(city_name: str) -> List[Dict]:
    """Generate sample addresses for demo purposes."""
    import random

    # Sample street names for demo
    streets = ["Main St", "Oak Ave", "Elm St", "Washington Blvd", "Park Ave", "Maple Dr"]

    # Approximate city centers for demo (lat, lon)
    city_centers = {
        "Pittsburgh": (40.4406, -79.9959),
        "Philadelphia": (39.9526, -75.1652),
        "Boston": (42.3601, -71.0589),
        "Chicago": (41.8781, -87.6298),
        "San Francisco": (37.7749, -122.4194),
        "Seattle": (47.6062, -122.3321),
    }

    center = city_centers.get(city_name, (40.0, -75.0))
    num_addresses = random.randint(800, 1500)

    demo_addresses = []
    for _ in range(num_addresses):
        # Generate random offset around city center
        lat_offset = random.uniform(-0.05, 0.05)
        lon_offset = random.uniform(-0.05, 0.05)

        demo_addresses.append({
            "type": "node",
            "lat": center[0] + lat_offset,
            "lon": center[1] + lon_offset,
            "tags": {
                "addr:housenumber": str(random.randint(1, 9999)),
                "addr:street": random.choice(streets),
                "building": random.choice(["house", "residential", "detached", "apartments"]),
            }
        })

    return {"elements": demo_addresses}


def fetch_addresses_for_city(
    city: Dict,
    subdivisions: List[Dict],
    demo_mode: bool = False,
) -> List[Dict]:
    """
    Fetch residential addresses for a single city.

    Args:
        city: City dictionary with 'name' and 'area_id'
        subdivisions: List of subdivision polygons
        demo_mode: Use demo data instead of querying Overpass API

    Returns:
        List of address dictionaries
    """
    print(f"📍 Fetching addresses for {city['name']}...")

    if demo_mode:
        print(f"  ℹ️  Using demo mode (synthetic data)")
        data = generate_demo_data(city["name"])
    else:
        query = build_overpass_query(city["name"], city["area_id"])
        data = query_overpass(query)

        if not data:
            print(f"  ❌ Failed to fetch data for {city['name']}", file=sys.stderr)
            return []

    elements = data.get("elements", [])
    print(f"  ✓ Found {len(elements)} address elements")

    addresses = []
    for element in elements:
        tags = element.get("tags", {})
        coords = extract_coordinates(element)

        if not coords:
            continue

        lat, lon = coords
        house_number = tags.get("addr:housenumber")
        street = tags.get("addr:street")

        if not (house_number and street):
            continue

        subdivision_id = find_subdivision(lat, lon, subdivisions)

        addresses.append({
            "city_name": city["name"],
            "subdivision_id": subdivision_id or "",
            "house_number": house_number,
            "street": street,
            "lat": lat,
            "lon": lon,
            "source": "OSM",
        })

    print(f"  ✓ Extracted {len(addresses)} valid addresses")
    return addresses


def main():
    """Main execution function."""
    # Check for demo mode
    demo_mode = os.getenv("DEMO_MODE", "").lower() in ("1", "true", "yes")

    print("🗺️  OpenStreetMap Address Fetcher")
    print("=" * 50)

    if demo_mode:
        print("\n⚠️  DEMO MODE: Using synthetic data (Overpass API not accessible)")
        print("   To use real data, run from an environment with Overpass API access")
    else:
        print("\n📡 Using live Overpass API data")

    # Load subdivision polygons
    print("\n📦 Loading subdivision data...")
    subdivisions = load_subdivision_polygons()
    print(f"  ✓ Loaded {len(subdivisions)} subdivisions")

    # Fetch addresses for all cities
    all_addresses = []

    for i, city in enumerate(CITIES):
        if i > 0 and not demo_mode:
            print(f"\n⏳ Rate limiting: waiting {RATE_LIMIT_SECONDS} seconds...")
            time.sleep(RATE_LIMIT_SECONDS)
        elif i > 0:
            print()  # Just add spacing in demo mode

        city_addresses = fetch_addresses_for_city(city, subdivisions, demo_mode=demo_mode)
        all_addresses.extend(city_addresses)

    # Write to CSV
    output_file = Path(__file__).parent.parent / "data" / "addresses_osm_raw.csv"

    print(f"\n💾 Writing {len(all_addresses)} addresses to {output_file}...")

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        if all_addresses:
            fieldnames = [
                "city_name",
                "subdivision_id",
                "house_number",
                "street",
                "lat",
                "lon",
                "source",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_addresses)

    print(f"  ✓ Written to {output_file}")

    # Display sample
    print("\n📄 Sample output (first 10 rows):")
    print("-" * 80)

    with open(output_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for line in lines[:11]:  # Header + 10 rows
            print(line.rstrip())

    print("-" * 80)
    print(f"\n✅ Done! Total addresses: {len(all_addresses)}")


if __name__ == "__main__":
    main()
