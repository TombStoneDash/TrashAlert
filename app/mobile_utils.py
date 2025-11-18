"""Utility functions for mobile endpoints."""
from typing import Optional
from datetime import datetime, timedelta


# Day code mappings for mobile
DAY_TO_MOBILE = {
    'MON': 'M', 'MONDAY': 'M',
    'TUE': 'T', 'TUESDAY': 'T',
    'WED': 'W', 'WEDNESDAY': 'W',
    'THU': 'R', 'THURSDAY': 'R',
    'FRI': 'F', 'FRIDAY': 'F',
    'SAT': 'S', 'SATURDAY': 'S',
    'SUN': 'U', 'SUNDAY': 'U'
}

MOBILE_TO_DAY = {
    'M': 'MON', 'T': 'TUE', 'W': 'WED', 'R': 'THU',
    'F': 'FRI', 'S': 'SAT', 'U': 'SUN'
}

# Source code mappings
SOURCE_TO_MOBILE = {
    'CROWD_VERIFIED': 'V',
    'OFFICIAL': 'O',
    'CROWD_UNVERIFIED': 'U',
    'UNKNOWN': 'X'
}


def day_to_mobile_code(day: Optional[str]) -> Optional[str]:
    """Convert day abbreviation or full name to single-letter mobile code.

    Args:
        day: Day string (MON, MONDAY, TUE, etc.) or None

    Returns:
        Single letter code (M, T, W, R, F, S, U) or None
    """
    if not day:
        return None
    day_upper = day.strip().upper()
    return DAY_TO_MOBILE.get(day_upper)


def mobile_code_to_day(code: Optional[str]) -> Optional[str]:
    """Convert single-letter mobile code to day abbreviation.

    Args:
        code: Single letter (M, T, W, R, F, S, U) or None

    Returns:
        Day abbreviation (MON, TUE, etc.) or None
    """
    if not code:
        return None
    code_upper = code.strip().upper()

    # If already a full abbreviation, return as-is
    if code_upper in ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']:
        return code_upper

    return MOBILE_TO_DAY.get(code_upper)


def source_to_mobile_code(source: str) -> str:
    """Convert data source to single-letter mobile code.

    Args:
        source: Source string (CROWD_VERIFIED, OFFICIAL, etc.)

    Returns:
        Single letter code (V, O, U, X)
    """
    return SOURCE_TO_MOBILE.get(source, 'X')


def get_next_weekday(current_date: datetime, target_day: str) -> str:
    """Get the next occurrence of a target weekday.

    Args:
        current_date: Starting date
        target_day: Target day (MON, TUE, WED, etc.)

    Returns:
        Date string in YYYYMMDD format
    """
    # Map day abbreviations to weekday numbers (0=Monday, 6=Sunday)
    day_map = {
        'MON': 0, 'TUE': 1, 'WED': 2, 'THU': 3,
        'FRI': 4, 'SAT': 5, 'SUN': 6
    }

    target_weekday = day_map.get(target_day.upper())
    if target_weekday is None:
        return None

    current_weekday = current_date.weekday()

    # Calculate days until next occurrence
    days_ahead = target_weekday - current_weekday
    if days_ahead <= 0:  # Target day already passed this week
        days_ahead += 7

    next_date = current_date + timedelta(days=days_ahead)
    return next_date.strftime('%Y%m%d')


def is_pickup_today(pickup_day: Optional[str], today: datetime) -> bool:
    """Check if pickup happens today.

    Args:
        pickup_day: Day abbreviation (MON, TUE, etc.)
        today: Date to check against

    Returns:
        True if pickup is today, False otherwise
    """
    if not pickup_day:
        return False

    day_map = {
        'MON': 0, 'TUE': 1, 'WED': 2, 'THU': 3,
        'FRI': 4, 'SAT': 5, 'SUN': 6
    }

    pickup_weekday = day_map.get(pickup_day.upper())
    if pickup_weekday is None:
        return False

    return today.weekday() == pickup_weekday
