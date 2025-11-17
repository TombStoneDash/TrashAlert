"""
Address normalization utilities.
Provides consistent address normalization for lookup and matching.
"""

from typing import Tuple
import re


def normalize_address(address: str) -> str:
    """
    Normalize an address string for consistent matching.

    Args:
        address: Full address string (e.g., "1122 Palmview Ave, El Centro, CA")

    Returns:
        Normalized address string

    Examples:
        >>> normalize_address("1122 Palmview Avenue, El Centro, CA")
        '1122 palmview ave el centro'
        >>> normalize_address("123 Main Street, San Diego, California")
        '123 main st san diego'
    """
    # Convert to lowercase
    normalized = address.lower()

    # Remove state abbreviations and zip codes
    normalized = re.sub(r'\b(ca|california)\b', '', normalized)
    normalized = re.sub(r'\b\d{5}(-\d{4})?\b', '', normalized)  # ZIP codes

    # Standardize street suffixes
    suffix_map = {
        'avenue': 'ave',
        'street': 'st',
        'boulevard': 'blvd',
        'road': 'rd',
        'drive': 'dr',
        'court': 'ct',
        'lane': 'ln',
        'way': 'way',
        'circle': 'cir',
        'place': 'pl',
        'terrace': 'ter',
    }

    for long_form, short_form in suffix_map.items():
        normalized = re.sub(rf'\b{long_form}\b', short_form, normalized)

    # Remove common punctuation
    normalized = re.sub(r'[,\.#]', ' ', normalized)

    # Remove extra whitespace
    normalized = ' '.join(normalized.split())

    return normalized


def parse_address_components(address: str) -> Tuple[str, str, str]:
    """
    Parse an address into components (house number, street, city).

    Args:
        address: Full address string

    Returns:
        Tuple of (house_number, street, city_name)

    Examples:
        >>> parse_address_components("1122 Palmview Ave, El Centro, CA")
        ('1122', 'palmview ave', 'el centro')
    """
    # Normalize first
    normalized = normalize_address(address)

    # Try to split by comma (most common format)
    parts = [p.strip() for p in normalized.split(',')]

    if len(parts) >= 2:
        # Format: "1122 Palmview Ave, El Centro"
        street_part = parts[0]
        city_name = parts[1]
    else:
        # No comma, try to extract city from common patterns
        # This is a simple heuristic - in production, use a proper geocoding service
        words = normalized.split()

        # Common Imperial Valley cities
        city_keywords = {
            'el centro', 'san diego', 'calexico', 'brawley',
            'imperial', 'holtville', 'imperial beach'
        }

        city_name = None
        for i in range(len(words)):
            # Check for two-word cities
            if i < len(words) - 1:
                two_word = f"{words[i]} {words[i+1]}"
                if two_word in city_keywords:
                    city_name = two_word
                    street_part = ' '.join(words[:i])
                    break

            # Check for one-word cities
            if words[i] in city_keywords:
                city_name = words[i]
                street_part = ' '.join(words[:i])
                break

        if not city_name:
            # Fallback: assume last word is city (rough heuristic)
            street_part = ' '.join(words[:-1])
            city_name = words[-1] if words else ''

    # Extract house number from street part
    street_words = street_part.split()
    if street_words and street_words[0].replace('-', '').isdigit():
        house_number = street_words[0]
        street = ' '.join(street_words[1:])
    else:
        house_number = ''
        street = street_part

    return house_number, street, city_name


def normalize_components(house_number: str, street: str, city: str) -> str:
    """
    Normalize individual address components into a single normalized string.

    Args:
        house_number: House/building number
        street: Street name
        city: City name

    Returns:
        Normalized address string
    """
    parts = [house_number.strip(), street.strip(), city.strip()]
    combined = ' '.join(parts)
    return normalize_address(combined)
