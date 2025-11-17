"""
Address normalization utilities for TrashAlert.

This module provides functions to normalize and standardize address strings
for consistent matching and deduplication.
"""

import re
from typing import Optional


# Street type abbreviations (USPS standard)
STREET_ABBREVIATIONS = {
    'ALLEY': 'ALY',
    'AVENUE': 'AVE',
    'BOULEVARD': 'BLVD',
    'CIRCLE': 'CIR',
    'COURT': 'CT',
    'DRIVE': 'DR',
    'LANE': 'LN',
    'PARKWAY': 'PKWY',
    'PLACE': 'PL',
    'ROAD': 'RD',
    'SQUARE': 'SQ',
    'STREET': 'ST',
    'TERRACE': 'TER',
    'TRAIL': 'TRL',
    'WAY': 'WAY',
}

# Directional abbreviations
DIRECTIONAL_ABBREVIATIONS = {
    'NORTH': 'N',
    'SOUTH': 'S',
    'EAST': 'E',
    'WEST': 'W',
    'NORTHEAST': 'NE',
    'NORTHWEST': 'NW',
    'SOUTHEAST': 'SE',
    'SOUTHWEST': 'SW',
}


def normalize_address(address: str) -> str:
    """
    Normalize an address string to a standard format.

    Steps:
    1. Convert to uppercase
    2. Remove extra whitespace
    3. Abbreviate street types
    4. Abbreviate directional indicators
    5. Remove trailing punctuation

    Args:
        address: Raw address string

    Returns:
        Normalized address string

    Examples:
        >>> normalize_address("123 main street")
        "123 MAIN ST"
        >>> normalize_address("45  elm   avenue")
        "45 ELM AVE"
        >>> normalize_address("100 North Park Boulevard")
        "100 N PARK BLVD"
    """
    if not address or not isinstance(address, str):
        return ""

    # Step 1: Convert to uppercase
    normalized = address.upper().strip()

    # Step 2: Remove extra whitespace (multiple spaces become single space)
    normalized = re.sub(r'\s+', ' ', normalized)

    # Step 3: Remove trailing punctuation
    normalized = re.sub(r'[.,;]+$', '', normalized)

    # Step 4: Split into tokens for abbreviation
    tokens = normalized.split()

    # Step 5: Apply abbreviations
    result_tokens = []
    for token in tokens:
        # Check for street type abbreviations
        if token in STREET_ABBREVIATIONS:
            result_tokens.append(STREET_ABBREVIATIONS[token])
        # Check for directional abbreviations
        elif token in DIRECTIONAL_ABBREVIATIONS:
            result_tokens.append(DIRECTIONAL_ABBREVIATIONS[token])
        else:
            result_tokens.append(token)

    return ' '.join(result_tokens)


def normalize_street_name(street: str, house_number: Optional[str] = None) -> str:
    """
    Normalize just the street name component of an address.

    Args:
        street: Street name to normalize
        house_number: Optional house number to prepend

    Returns:
        Normalized street name (with optional house number)

    Examples:
        >>> normalize_street_name("main street")
        "MAIN ST"
        >>> normalize_street_name("elm avenue", "45")
        "45 ELM AVE"
    """
    if not street:
        return ""

    # Normalize the street name
    normalized_street = normalize_address(street)

    # Optionally prepend house number
    if house_number:
        return f"{house_number} {normalized_street}"

    return normalized_street


def clean_whitespace(text: str) -> str:
    """
    Remove extra whitespace from a string.

    Args:
        text: String to clean

    Returns:
        String with single spaces only

    Examples:
        >>> clean_whitespace("hello    world")
        "hello world"
        >>> clean_whitespace("  test  ")
        "test"
    """
    if not text:
        return ""

    return re.sub(r'\s+', ' ', text.strip())
