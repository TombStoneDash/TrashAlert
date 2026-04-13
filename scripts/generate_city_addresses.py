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
    "new_york": {
        "city_id": 12,
        "city_name": "New York",
        "state_abbr": "NY",
        "lat_range": (40.56, 40.88),
        "lon_range": (-74.05, -73.75),
        "streets": [
            "BROADWAY", "5TH AVE", "MADISON AVE", "PARK AVE",
            "LEXINGTON AVE", "3RD AVE", "2ND AVE", "1ST AVE",
            "AMSTERDAM AVE", "COLUMBUS AVE", "CENTRAL PARK W",
            "WEST END AVE", "RIVERSIDE DR", "BROADWAY", "7TH AVE",
            "8TH AVE", "9TH AVE", "10TH AVE", "ATLANTIC AVE",
            "FLATBUSH AVE", "FULTON ST", "COURT ST", "SMITH ST",
            "MYRTLE AVE", "DEKALB AVE", "NOSTRAND AVE", "BEDFORD AVE",
            "GRAND ST", "DELANCEY ST", "HOUSTON ST",
        ],
    },
    "los_angeles": {
        "city_id": 13,
        "city_name": "Los Angeles",
        "state_abbr": "CA",
        "lat_range": (33.90, 34.15),
        "lon_range": (-118.50, -118.15),
        "streets": [
            "SUNSET BLVD", "HOLLYWOOD BLVD", "WILSHIRE BLVD", "SANTA MONICA BLVD",
            "MELROSE AVE", "BEVERLY BLVD", "3RD ST", "6TH ST",
            "OLYMPIC BLVD", "PICO BLVD", "VENICE BLVD", "WASHINGTON BLVD",
            "LA BREA AVE", "FAIRFAX AVE", "LA CIENEGA BLVD", "ROBERTSON BLVD",
            "VERMONT AVE", "WESTERN AVE", "NORMANDIE AVE", "HOOVER ST",
            "FIGUEROA ST", "GRAND AVE", "SPRING ST", "MAIN ST",
            "SAN PEDRO ST", "ALAMEDA ST", "CENTRAL AVE", "BROADWAY",
            "HILL ST", "OLIVE ST",
        ],
    },
    "philadelphia": {
        "city_id": 14,
        "city_name": "Philadelphia",
        "state_abbr": "PA",
        "lat_range": (39.88, 40.08),
        "lon_range": (-75.25, -75.10),
        "streets": [
            "BROAD ST", "MARKET ST", "CHESTNUT ST", "WALNUT ST",
            "SPRUCE ST", "PINE ST", "SOUTH ST", "ARCH ST",
            "RACE ST", "VINE ST", "SPRING GARDEN ST", "FAIRMOUNT AVE",
            "GIRARD AVE", "COLUMBIA AVE", "CECIL B MOORE AVE", "LEHIGH AVE",
            "ALLEGHENY AVE", "ERIE AVE", "RISING SUN AVE", "GERMANTOWN AVE",
            "RIDGE AVE", "PASSYUNK AVE", "OREGON AVE", "SNYDER AVE",
            "FRONT ST", "2ND ST", "3RD ST", "4TH ST",
            "5TH ST", "6TH ST",
        ],
    },
    "san_antonio": {
        "city_id": 15,
        "city_name": "San Antonio",
        "state_abbr": "TX",
        "lat_range": (29.32, 29.58),
        "lon_range": (-98.60, -98.38),
        "streets": [
            "BROADWAY", "COMMERCE ST", "HOUSTON ST", "MARKET ST",
            "NAVARRO ST", "ST MARYS ST", "ALAMO ST", "FLORES ST",
            "SAN PEDRO AVE", "MCCULLOUGH AVE", "BROADWAY", "AUSTIN HWY",
            "FREDERICKSBURG RD", "BANDERA RD", "CULEBRA RD", "MILITARY DR",
            "NOGALITOS ST", "S PRESA ST", "S ALAMO ST", "DURANGO BLVD",
            "CESAR CHAVEZ BLVD", "MARTIN ST", "PECAN ST", "TRAVIS ST",
            "VILLITA ST", "NUEVA ST", "DOLOROSA ST", "LAREDO ST",
            "SANTA ROSA AVE", "FRIO ST",
        ],
    },
    "dallas": {
        "city_id": 16,
        "city_name": "Dallas",
        "state_abbr": "TX",
        "lat_range": (32.68, 32.92),
        "lon_range": (-96.90, -96.65),
        "streets": [
            "MAIN ST", "ELM ST", "COMMERCE ST", "JACKSON ST",
            "WOOD ST", "YOUNG ST", "MARILLA ST", "CANTON ST",
            "ROSS AVE", "BRYAN ST", "SWISS AVE", "LIVE OAK ST",
            "GASTON AVE", "FITZHUGH AVE", "LEMMON AVE", "MCKINNEY AVE",
            "CEDAR SPRINGS RD", "OAK LAWN AVE", "HARRY HINES BLVD", "STEMMONS FWY",
            "INDUSTRIAL BLVD", "RIVERFRONT BLVD", "LAMAR ST", "AUSTIN ST",
            "HARWOOD ST", "ST PAUL ST", "AKARD ST", "ERVAY ST",
            "GRIFFIN ST", "HOUSTON ST",
        ],
    },
    "oklahoma_city": {
        "city_id": 17,
        "city_name": "Oklahoma City",
        "state_abbr": "OK",
        "lat_range": (35.38, 35.58),
        "lon_range": (-97.62, -97.42),
        "streets": [
            "BROADWAY AVE", "ROBINSON AVE", "HARVEY AVE", "HUDSON AVE",
            "WALKER AVE", "DEWEY AVE", "LEE AVE", "SHARTEL AVE",
            "CLASSEN BLVD", "WESTERN AVE", "MAY AVE", "PENN AVE",
            "NW 23RD ST", "NW 36TH ST", "NW 39TH ST", "NW 50TH ST",
            "NW 63RD ST", "RENO AVE", "SHERIDAN AVE", "MAIN ST",
            "PARK AVE", "ROBERT S KERR AVE", "CALIFORNIA AVE", "DEAN A MCGEE AVE",
            "NE 23RD ST", "LINCOLN BLVD", "KELLEY AVE", "MLK AVE",
            "COTTAGE ST", "DURLAND AVE",
        ],
    },
    "charlotte": {
        "city_id": 18,
        "city_name": "Charlotte",
        "state_abbr": "NC",
        "lat_range": (35.15, 35.35),
        "lon_range": (-80.92, -80.75),
        "streets": [
            "TRYON ST", "TRADE ST", "COLLEGE ST", "CHURCH ST",
            "BREVARD ST", "DAVIDSON ST", "CALDWELL ST", "ALEXANDER ST",
            "INDEPENDENCE BLVD", "CENTRAL AVE", "THE PLAZA", "SHAMROCK DR",
            "EASTWAY DR", "ALBEMARLE RD", "SHARON AMITY RD", "RANDOLPH RD",
            "QUEENS RD", "SELWYN AVE", "PARK RD", "WOODLAWN RD",
            "SOUTH BLVD", "CAMDEN RD", "KENILWORTH AVE", "MOREHEAD ST",
            "STONEWALL ST", "HILL ST", "GRAHAM ST", "SUMMIT AVE",
            "STATESVILLE AVE", "BEATTIES FORD RD",
        ],
    },
    "columbus": {
        "city_id": 19,
        "city_name": "Columbus",
        "state_abbr": "OH",
        "lat_range": (39.90, 40.08),
        "lon_range": (-83.10, -82.87),
        "streets": [
            "HIGH ST", "BROAD ST", "MAIN ST", "STATE ST",
            "TOWN ST", "RICH ST", "LONG ST", "SPRING ST",
            "GAY ST", "ELM ST", "MOUND ST", "LIVINGSTON AVE",
            "PARSONS AVE", "CHAMPION AVE", "OHIO AVE", "GRANT AVE",
            "4TH ST", "3RD ST", "FRONT ST", "CIVIC CENTER DR",
            "NEIL AVE", "SUMMIT ST", "CLEVELAND AVE", "INDIANOLA AVE",
            "OLENTANGY RIVER RD", "KENNY RD", "KING AVE", "5TH AVE",
            "LANE AVE", "HENDERSON RD",
        ],
    },
    "chicago": {
        "city_id": 20,
        "city_name": "Chicago",
        "state_abbr": "IL",
        "lat_range": (41.72, 41.98),
        "lon_range": (-87.78, -87.58),
        "streets": [
            "STATE ST", "MICHIGAN AVE", "WABASH AVE", "CLARK ST",
            "LASALLE ST", "WELLS ST", "DEARBORN ST", "MADISON ST",
            "WASHINGTON ST", "RANDOLPH ST", "LAKE ST", "ADAMS ST",
            "JACKSON BLVD", "VAN BUREN ST", "CONGRESS PKWY", "HALSTED ST",
            "ASHLAND AVE", "WESTERN AVE", "CALIFORNIA AVE", "KEDZIE AVE",
            "PULASKI RD", "CICERO AVE", "BROADWAY", "CLARK ST",
            "LINCOLN AVE", "FULLERTON AVE", "DIVERSEY PKWY", "BELMONT AVE",
            "IRVING PARK RD", "ADDISON ST",
        ],
    },
    "seattle": {
        "city_id": 21,
        "city_name": "Seattle",
        "state_abbr": "WA",
        "lat_range": (47.50, 47.72),
        "lon_range": (-122.42, -122.25),
        "streets": [
            "1ST AVE", "2ND AVE", "3RD AVE", "4TH AVE",
            "5TH AVE", "PIKE ST", "PINE ST", "UNION ST",
            "UNIVERSITY ST", "SENECA ST", "SPRING ST", "MADISON ST",
            "MARION ST", "COLUMBIA ST", "CHERRY ST", "JAMES ST",
            "YESLER WAY", "JACKSON ST", "KING ST", "DENNY WAY",
            "MERCER ST", "ROY ST", "ALOHA ST", "BROADWAY",
            "RAINIER AVE", "MLK JR WAY", "23RD AVE", "15TH AVE",
            "AURORA AVE N", "FREMONT AVE N",
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
