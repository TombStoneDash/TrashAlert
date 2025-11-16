"""
Configuration for trash day lookup database pilot
"""

# Target cities with their OSM details
CITIES = [
    {
        "name": "El Centro",
        "state": "California",
        "county": "Imperial County",
        "osm_query": 'area["name"="El Centro"]["admin_level"="8"]["place"="city"];',
    },
    {
        "name": "Brawley",
        "state": "California",
        "county": "Imperial County",
        "osm_query": 'area["name"="Brawley"]["admin_level"="8"]["place"="city"];',
    },
    {
        "name": "Imperial",
        "state": "California",
        "county": "Imperial County",
        "osm_query": 'area["name"="Imperial"]["admin_level"="8"]["place"="city"];',
    },
    {
        "name": "Calexico",
        "state": "California",
        "county": "Imperial County",
        "osm_query": 'area["name"="Calexico"]["admin_level"="8"]["place"="city"];',
    },
    {
        "name": "Holtville",
        "state": "California",
        "county": "Imperial County",
        "osm_query": 'area["name"="Holtville"]["admin_level"="8"]["place"="city"];',
    },
    {
        "name": "San Diego",
        "state": "California",
        "county": "San Diego County",
        "osm_query": 'area["name"="San Diego"]["admin_level"="8"]["place"="city"];',
    },
]

# Overpass API settings
OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_RATE_LIMIT_DELAY = 2  # seconds between queries
OVERPASS_TIMEOUT = 180  # query timeout in seconds
OVERPASS_MAX_RETRIES = 3

# Database settings
DB_PATH = "data/trash_day_pilot.db"

# Data directories
RAW_DATA_DIR = "data/raw"
PROCESSED_DATA_DIR = "data/processed"
LOG_DIR = "logs"

# Logging
LOG_FILE = "logs/pipeline.log"
LOG_LEVEL = "INFO"
