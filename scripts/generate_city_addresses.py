"""Generate realistic address data for new cities and append to addresses_normalized.csv.

Usage:
    python scripts/generate_city_addresses.py houston
    python scripts/generate_city_addresses.py phoenix
    python scripts/generate_city_addresses.py austin
    python scripts/generate_city_addresses.py boston
    python scripts/generate_city_addresses.py denver
"""

import csv
import random
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CSV_PATH = DATA_DIR / "addresses_normalized.csv"

# City definitions: id, name, state_abbr, center, bounds, streets
CITIES = {
    "houston": {
        "city_id": 7,
        "city_name": "Houston",
        "state_abbr": "TX",
        "lat_range": (29.62, 29.90),
        "lon_range": (-95.55, -95.20),
        "streets": [
            "MAIN ST", "WESTHEIMER RD", "RICHMOND AVE", "KIRBY DR",
            "MONTROSE BLVD", "WASHINGTON AVE", "HEIGHTS BLVD", "MEMORIAL DR",
            "POST OAK BLVD", "SHEPHERD DR", "FANNIN ST", "TRAVIS ST",
            "MILAM ST", "LOUISIANA ST", "SMITH ST", "WAUGH DR",
            "ALLEN PKWY", "DALLAS ST", "ELGIN ST", "ALABAMA ST",
            "BISSONNET ST", "BELLAIRE BLVD", "HOLCOMBE BLVD", "RICE BLVD",
            "UNIVERSITY BLVD", "DUNLAVY ST", "TAFT ST", "BRAZOS ST",
            "JACKSON ST", "CRAWFORD ST",
        ],
    },
    "phoenix": {
        "city_id": 8,
        "city_name": "Phoenix",
        "state_abbr": "AZ",
        "lat_range": (33.33, 33.60),
        "lon_range": (-112.25, -111.93),
        "streets": [
            "CENTRAL AVE", "CAMELBACK RD", "INDIAN SCHOOL RD", "THOMAS RD",
            "MCDOWELL RD", "VAN BUREN ST", "BETHANY HOME RD", "GLENDALE AVE",
            "NORTHERN AVE", "DUNLAP AVE", "PEORIA AVE", "CACTUS RD",
            "THUNDERBIRD RD", "BELL RD", "GREENWAY RD", "CAVE CREEK RD",
            "TATUM BLVD", "SCOTTSDALE RD", "7TH ST", "7TH AVE",
            "16TH ST", "24TH ST", "32ND ST", "40TH ST",
            "44TH ST", "48TH ST", "51ST AVE", "35TH AVE",
            "19TH AVE", "15TH AVE",
        ],
    },
    "austin": {
        "city_id": 9,
        "city_name": "Austin",
        "state_abbr": "TX",
        "lat_range": (30.15, 30.40),
        "lon_range": (-97.85, -97.62),
        "streets": [
            "CONGRESS AVE", "LAMAR BLVD", "GUADALUPE ST", "S 1ST ST",
            "BURNET RD", "MANOR RD", "CESAR CHAVEZ ST", "MLK BLVD",
            "RIVERSIDE DR", "BARTON SPRINGS RD", "S CONGRESS AVE", "E 6TH ST",
            "E 7TH ST", "RED RIVER ST", "BRAZOS ST", "COLORADO ST",
            "LAVACA ST", "NUECES ST", "SAN ANTONIO ST", "RIO GRANDE ST",
            "W 5TH ST", "W 6TH ST", "OLTORF ST", "BEN WHITE BLVD",
            "MANCHACA RD", "WILLIAM CANNON DR", "STASSNEY LN", "RUNDBERG LN",
            "ANDERSON LN", "RESEARCH BLVD",
        ],
    },
    "boston": {
        "city_id": 10,
        "city_name": "Boston",
        "state_abbr": "MA",
        "lat_range": (42.23, 42.40),
        "lon_range": (-71.18, -70.99),
        "streets": [
            "COMMONWEALTH AVE", "BEACON ST", "BOYLSTON ST", "TREMONT ST",
            "WASHINGTON ST", "NEWBURY ST", "HUNTINGTON AVE", "MASSACHUSETTS AVE",
            "ATLANTIC AVE", "CONGRESS ST", "STATE ST", "SUMMER ST",
            "CHARLES ST", "CAMBRIDGE ST", "HANOVER ST", "COMMERCIAL ST",
            "DORCHESTER AVE", "BROADWAY", "COLUMBIA RD", "BLUE HILL AVE",
            "CENTRE ST", "COLUMBUS AVE", "STUART ST", "ARLINGTON ST",
            "BERKELEY ST", "CLARENDON ST", "DARTMOUTH ST", "EXETER ST",
            "FAIRFIELD ST", "GLOUCESTER ST",
        ],
    },
    "denver": {
        "city_id": 11,
        "city_name": "Denver",
        "state_abbr": "CO",
        "lat_range": (39.63, 39.82),
        "lon_range": (-105.10, -104.85),
        "streets": [
            "COLFAX AVE", "BROADWAY", "COLORADO BLVD", "FEDERAL BLVD",
            "SPEER BLVD", "16TH ST", "17TH ST", "LARIMER ST",
            "BLAKE ST", "WAZEE ST", "CHAMPA ST", "STOUT ST",
            "CALIFORNIA ST", "WELTON ST", "GLENARM PL", "TREMONT PL",
            "MARKET ST", "ARAPAHOE ST", "LAWRENCE ST", "CURTIS ST",
            "YORK ST", "JOSEPHINE ST", "DOWNING ST", "WASHINGTON ST",
            "CLARKSON ST", "EMERSON ST", "OGDEN ST", "MARION ST",
            "PEARL ST", "PENNSYLVANIA ST",
        ],
    },
}

COUNT = 200  # addresses per city


def generate_addresses(city_key: str) -> list[dict]:
    """Generate realistic addresses for a city."""
    cfg = CITIES[city_key]
    rng = random.Random(cfg["city_id"] * 1000)  # deterministic seed per city

    addresses = []
    used = set()

    while len(addresses) < COUNT:
        street = rng.choice(cfg["streets"])
        house = rng.randint(100, 9999)
        key = f"{house}_{street}"
        if key in used:
            continue
        used.add(key)

        lat = rng.uniform(*cfg["lat_range"])
        lon = rng.uniform(*cfg["lon_range"])
        osm_id = f"node/{cfg['city_id']}{len(addresses):05d}"
        full_address = f"{house} {street}, {cfg['city_name']}, {cfg['state_abbr']}, USA"

        addresses.append({
            "city_id": cfg["city_id"],
            "city_name": cfg["city_name"],
            "house_number": house,
            "street_normalized": street,
            "full_address": full_address,
            "lat": f"{lat:.14f}",
            "lon": f"{lon:.14f}",
            "osm_id": osm_id,
        })

    return addresses


def append_to_csv(addresses: list[dict]):
    """Append addresses to the normalized CSV."""
    fieldnames = [
        "city_id", "city_name", "house_number", "street_normalized",
        "full_address", "lat", "lon", "osm_id",
    ]
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        for addr in addresses:
            writer.writerow(addr)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <city>")
        print(f"Available: {', '.join(CITIES.keys())}")
        sys.exit(1)

    city_key = sys.argv[1].lower()
    if city_key not in CITIES:
        print(f"Unknown city: {city_key}")
        print(f"Available: {', '.join(CITIES.keys())}")
        sys.exit(1)

    # Check if city already exists in CSV
    if CSV_PATH.exists():
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("city_name") == CITIES[city_key]["city_name"]:
                    print(f"City {CITIES[city_key]['city_name']} already has data in CSV. Skipping.")
                    sys.exit(0)

    addresses = generate_addresses(city_key)
    append_to_csv(addresses)
    print(f"Added {len(addresses)} addresses for {CITIES[city_key]['city_name']} to {CSV_PATH}")


if __name__ == "__main__":
    main()
