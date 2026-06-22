"""
Database operations for TrashAlert API.
"""

import sqlite3
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from difflib import SequenceMatcher


DB_PATH = Path(__file__).parent.parent / 'data' / 'trashalert.db'


def get_db_connection() -> sqlite3.Connection:
    """Create a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    return conn


def calculate_similarity(str1: str, str2: str) -> float:
    """Calculate similarity ratio between two strings (0-1)."""
    return SequenceMatcher(None, str1, str2).ratio()


def find_closest_address(
    normalized_address: str,
    city_name: str,
    threshold: float = 0.6
) -> Optional[Dict[str, Any]]:
    """
    Find the closest matching address in the database.

    Args:
        normalized_address: Normalized full address string
        city_name: City name for filtering
        threshold: Minimum similarity score (0-1) to consider a match

    Returns:
        Dictionary with address and pickup info, or None if no match found
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # First, try exact match
        cursor.execute("""
            SELECT
                a.id,
                a.city_name,
                a.house_number,
                a.street,
                a.normalized_address,
                a.lat,
                a.lon,
                p.trash_day_of_week,
                p.recycling_day_of_week,
                p.green_waste_day_of_week
            FROM addresses_normalized a
            LEFT JOIN address_pickup_info p ON a.id = p.address_id
            WHERE a.normalized_address = ?
        """, (normalized_address,))

        row = cursor.fetchone()

        if row:
            return {
                'matched_address': f"{row['house_number']} {row['street']}",
                'city': row['city_name'],
                'trash_day_of_week': row['trash_day_of_week'],
                'recycling_day_of_week': row['recycling_day_of_week'],
                'green_waste_day_of_week': row['green_waste_day_of_week'],
                'confidence': 1.0,
                'lat': row['lat'],
                'lon': row['lon']
            }

        # No exact match, try fuzzy matching within the city
        city_pattern = f"%{city_name}%"
        cursor.execute("""
            SELECT
                a.id,
                a.city_name,
                a.house_number,
                a.street,
                a.normalized_address,
                a.lat,
                a.lon,
                p.trash_day_of_week,
                p.recycling_day_of_week,
                p.green_waste_day_of_week
            FROM addresses_normalized a
            LEFT JOIN address_pickup_info p ON a.id = p.address_id
            WHERE a.city_name LIKE ?
        """, (city_pattern,))

        rows = cursor.fetchall()

        if not rows:
            return None

        # Find best match using fuzzy matching
        best_match = None
        best_score = threshold

        for row in rows:
            score = calculate_similarity(normalized_address, row['normalized_address'])

            if score > best_score:
                best_score = score
                best_match = row

        if best_match:
            return {
                'matched_address': f"{best_match['house_number']} {best_match['street']}",
                'city': best_match['city_name'],
                'trash_day_of_week': best_match['trash_day_of_week'],
                'recycling_day_of_week': best_match['recycling_day_of_week'],
                'green_waste_day_of_week': best_match['green_waste_day_of_week'],
                'confidence': round(best_score, 2),
                'lat': best_match['lat'],
                'lon': best_match['lon']
            }

        return None

    finally:
        conn.close()


def get_all_cities() -> List[str]:
    """Get list of all cities in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT DISTINCT city_name FROM addresses_normalized ORDER BY city_name")
        return [row['city_name'] for row in cursor.fetchall()]
    finally:
        conn.close()


_STATS_CACHE: Dict[str, Any] = {}
_STATS_CACHE_TTL = 3600  # recompute at most once per hour


def get_stats() -> Dict[str, Any]:
    """Get database statistics. Cached for 1h to avoid full-scan latency on 50M-row table."""
    now = time.monotonic()
    if _STATS_CACHE.get('expires', 0) > now:
        return _STATS_CACHE['data']

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) as count FROM addresses_normalized")
        address_count = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(DISTINCT city_name) as count FROM addresses_normalized")
        city_count = cursor.fetchone()['count']

        result = {
            'total_addresses': address_count,
            'total_cities': city_count,
        }
        _STATS_CACHE['data'] = result
        _STATS_CACHE['expires'] = now + _STATS_CACHE_TTL
        return result
    finally:
        conn.close()
