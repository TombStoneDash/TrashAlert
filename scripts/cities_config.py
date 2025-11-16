"""
Configuration file for TrashAlert pilot cities.

This module defines the six pilot cities for the TrashAlert project.
Each city includes name, state, and country information.
"""

PILOT_CITIES = [
    {
        "name": "San Francisco",
        "state": "California",
        "country": "USA"
    },
    {
        "name": "Seattle",
        "state": "Washington",
        "country": "USA"
    },
    {
        "name": "Austin",
        "state": "Texas",
        "country": "USA"
    },
    {
        "name": "Portland",
        "state": "Oregon",
        "country": "USA"
    },
    {
        "name": "Denver",
        "state": "Colorado",
        "country": "USA"
    },
    {
        "name": "Boston",
        "state": "Massachusetts",
        "country": "USA"
    }
]


def get_pilot_cities():
    """
    Get the list of pilot cities.

    Returns:
        list: List of dictionaries containing city information
    """
    return PILOT_CITIES


def get_city_by_name(city_name):
    """
    Get a specific city by name.

    Args:
        city_name (str): Name of the city to retrieve

    Returns:
        dict: City information or None if not found
    """
    for city in PILOT_CITIES:
        if city["name"].lower() == city_name.lower():
            return city
    return None


if __name__ == "__main__":
    # Print all pilot cities when run directly
    print("TrashAlert Pilot Cities:")
    print("=" * 50)
    for city in PILOT_CITIES:
        print(f"{city['name']}, {city['state']}, {city['country']}")
