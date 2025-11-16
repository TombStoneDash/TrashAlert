#!/usr/bin/env python3
"""
Build subdivision (neighborhood/district) GeoJSON for each city.
- San Diego: Attempts to fetch official Community Planning Areas, falls back to grid
- Imperial Valley cities: Grid-based synthetic subdivisions
"""

import json
import requests
import sys
from typing import Dict, List, Any, Tuple

def load_city_boundaries(path: str = "data/city_boundaries.geojson") -> Dict[str, Any]:
    """Load the city boundaries GeoJSON."""
    print(f"Loading city boundaries from {path}...")
    with open(path, 'r') as f:
        data = json.load(f)
    print(f"  ✓ Loaded {len(data['features'])} cities")
    return data

def get_polygon_bounds(coordinates: List) -> Tuple[float, float, float, float]:
    """
    Get bounding box of a polygon.
    Returns (min_lon, min_lat, max_lon, max_lat)
    """
    # Handle both Polygon and MultiPolygon
    if isinstance(coordinates[0][0][0], list):
        # MultiPolygon
        all_coords = []
        for polygon in coordinates:
            for ring in polygon:
                all_coords.extend(ring)
    else:
        # Polygon
        all_coords = []
        for ring in coordinates:
            all_coords.extend(ring)

    lons = [coord[0] for coord in all_coords]
    lats = [coord[1] for coord in all_coords]

    return min(lons), min(lats), max(lons), max(lats)

def create_grid_subdivisions(city_id: str, city_name: str, geometry: Dict,
                             grid_size: int) -> List[Dict[str, Any]]:
    """
    Create grid-based subdivisions for a city.

    Args:
        city_id: City identifier (e.g., "EL_CENTRO")
        city_name: City name (e.g., "El Centro")
        geometry: GeoJSON geometry of the city
        grid_size: Number of grid cells per side (3 or 4)

    Returns:
        List of subdivision features
    """
    print(f"  Creating {grid_size}x{grid_size} grid for {city_name}...")

    # Get bounds of the city polygon
    coords = geometry['coordinates']
    min_lon, min_lat, max_lon, max_lat = get_polygon_bounds(coords)

    # Calculate grid cell dimensions
    lon_step = (max_lon - min_lon) / grid_size
    lat_step = (max_lat - min_lat) / grid_size

    subdivisions = []
    cell_num = 1

    for row in range(grid_size):
        for col in range(grid_size):
            # Calculate cell bounds
            cell_min_lon = min_lon + (col * lon_step)
            cell_max_lon = min_lon + ((col + 1) * lon_step)
            cell_min_lat = min_lat + (row * lat_step)
            cell_max_lat = min_lat + ((row + 1) * lat_step)

            # Create cell polygon
            cell_coords = [
                [cell_min_lon, cell_min_lat],  # SW
                [cell_max_lon, cell_min_lat],  # SE
                [cell_max_lon, cell_max_lat],  # NE
                [cell_min_lon, cell_max_lat],  # NW
                [cell_min_lon, cell_min_lat],  # Close ring
            ]

            subdivision_id = f"{city_id}_G{cell_num}"
            subdivision_name = f"{city_name} Grid {cell_num}"

            subdivisions.append({
                "type": "Feature",
                "properties": {
                    "subdivision_id": subdivision_id,
                    "name": subdivision_name,
                    "city_id": city_id,
                    "city_name": city_name,
                    "grid_row": row + 1,
                    "grid_col": col + 1,
                    "type": "grid"
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [cell_coords]
                }
            })

            cell_num += 1

    print(f"    ✓ Created {len(subdivisions)} grid cells")
    return subdivisions

def fetch_san_diego_subdivisions(city_geometry: Dict) -> List[Dict[str, Any]]:
    """
    Attempt to fetch San Diego Community Planning Areas from official sources.
    Falls back to grid-based subdivisions if fetch fails.
    """
    print("Fetching San Diego subdivisions...")

    # Try official San Diego Community Planning Areas
    cpd_urls = [
        "https://seshat.datasd.org/sde/cpd_districts/cpd_districts_datasd.geojson",
        "https://seshat.datasd.org/sde/community_plan/community_plan_datasd.geojson",
        "https://seshat.datasd.org/sde/pd_cpd_dist/pd_cpd_dist_datasd.geojson",
    ]

    for url in cpd_urls:
        try:
            print(f"  Trying {url.split('/')[-1]}...")
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get("type") == "FeatureCollection" and data.get("features"):
                    print(f"  ✓ Successfully fetched official subdivisions")

                    # Transform to our format
                    subdivisions = []
                    for idx, feature in enumerate(data["features"], 1):
                        props = feature.get("properties", {})

                        # Try to extract name from various possible fields
                        name = (props.get("name") or
                               props.get("cpname") or
                               props.get("community") or
                               props.get("district") or
                               f"District {idx}")

                        subdivision_id = f"SD_CPD_{idx:03d}"

                        subdivisions.append({
                            "type": "Feature",
                            "properties": {
                                "subdivision_id": subdivision_id,
                                "name": name,
                                "city_id": "SAN_DIEGO",
                                "city_name": "San Diego",
                                "type": "community_planning_area",
                                "original_properties": props
                            },
                            "geometry": feature["geometry"]
                        })

                    print(f"  ✓ Processed {len(subdivisions)} subdivisions")
                    return subdivisions

        except Exception as e:
            print(f"  Failed: {e}")
            continue

    # Fallback to grid
    print("  Falling back to grid-based subdivisions...")
    return create_grid_subdivisions("SAN_DIEGO", "San Diego", city_geometry, grid_size=4)

def build_subdivisions():
    """
    Main function to build subdivision GeoJSON files.
    """
    print("Building subdivision GeoJSON files...")
    print("=" * 60)

    # Load city boundaries
    boundaries = load_city_boundaries()

    # Create lookup of cities by ID
    cities = {}
    for feature in boundaries["features"]:
        city_id = feature["properties"]["city_id"]
        cities[city_id] = feature

    print()

    # Process San Diego
    san_diego_subdivisions = fetch_san_diego_subdivisions(cities["SAN_DIEGO"]["geometry"])

    # Save San Diego subdivisions
    san_diego_output = {
        "type": "FeatureCollection",
        "features": san_diego_subdivisions
    }

    san_diego_path = "data/san_diego_subdivisions.geojson"
    with open(san_diego_path, "w") as f:
        json.dump(san_diego_output, f, indent=2)

    print(f"\n✓ Saved {san_diego_path}")
    print(f"  Subdivisions: {len(san_diego_subdivisions)}")

    print("\n" + "=" * 60)

    # Process Imperial Valley cities
    print("\nProcessing Imperial Valley cities...")
    imperial_subdivisions = []

    imperial_cities = [
        ("EL_CENTRO", "El Centro", 4),
        ("BRAWLEY", "Brawley", 3),
        ("IMPERIAL", "Imperial", 3),
        ("CALEXICO", "Calexico", 3),
        ("HOLTVILLE", "Holtville", 3),
    ]

    for city_id, city_name, grid_size in imperial_cities:
        if city_id in cities:
            subs = create_grid_subdivisions(
                city_id,
                city_name,
                cities[city_id]["geometry"],
                grid_size
            )
            imperial_subdivisions.extend(subs)

    # Save Imperial Valley subdivisions
    imperial_output = {
        "type": "FeatureCollection",
        "features": imperial_subdivisions
    }

    imperial_path = "data/imperial_valley_subdivisions.geojson"
    with open(imperial_path, "w") as f:
        json.dump(imperial_output, f, indent=2)

    print(f"\n✓ Saved {imperial_path}")
    print(f"  Subdivisions: {len(imperial_subdivisions)}")

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("\nOutput files:")
    print(f"  1. {san_diego_path}")
    print(f"  2. {imperial_path}")

    print("\nSubdivisions per city:")

    # Count San Diego
    print(f"  San Diego:          {len(san_diego_subdivisions):3d} subdivisions")

    # Count Imperial Valley by city
    for city_id, city_name, grid_size in imperial_cities:
        city_subs = [s for s in imperial_subdivisions
                    if s["properties"]["city_id"] == city_id]
        print(f"  {city_name:18} {len(city_subs):3d} subdivisions")

    print(f"\n  TOTAL:              {len(san_diego_subdivisions) + len(imperial_subdivisions):3d} subdivisions")

    # Print sample attributes (no geometry)
    print("\n" + "=" * 60)
    print("SAMPLE SUBDIVISION ATTRIBUTES")
    print("=" * 60)

    print("\nSan Diego (first 3):")
    for sub in san_diego_subdivisions[:3]:
        props = sub["properties"]
        # Print without original_properties to keep it clean
        display_props = {k: v for k, v in props.items() if k != "original_properties"}
        print(f"  {json.dumps(display_props, indent=4)}")

    print("\nImperial Valley (first 3 from each city):")
    for city_id, city_name, _ in imperial_cities[:2]:  # Just show first 2 cities
        city_subs = [s for s in imperial_subdivisions
                    if s["properties"]["city_id"] == city_id]
        print(f"\n  {city_name}:")
        for sub in city_subs[:2]:  # Show 2 per city
            props = sub["properties"]
            print(f"    {json.dumps(props, indent=6)}")

    print("\n" + "=" * 60)
    print("✓ All subdivisions generated successfully!")
    print("=" * 60)

if __name__ == "__main__":
    try:
        build_subdivisions()
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
