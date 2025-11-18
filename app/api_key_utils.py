"""Utilities for API key generation and management."""
import secrets
import hashlib
from datetime import datetime
from typing import Tuple


def generate_api_key() -> Tuple[str, str, str]:
    """
    Generate a new API key.

    Returns:
        Tuple of (full_key, key_hash, key_prefix)
        - full_key: The complete API key to show to the user (ONLY ONCE)
        - key_hash: SHA-256 hash to store in database
        - key_prefix: First 8 characters for identification
    """
    # Generate a secure random key (32 bytes = 64 hex chars)
    random_part = secrets.token_hex(32)

    # Create the full key with prefix
    full_key = f"ta_live_{random_part}"

    # Hash the key for storage
    key_hash = hash_api_key(full_key)

    # Extract prefix for display
    key_prefix = full_key[:8]

    return full_key, key_hash, key_prefix


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key using SHA-256.

    Args:
        api_key: The raw API key string

    Returns:
        Hexadecimal string of the hash
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    """
    Verify a provided API key against a stored hash.

    Args:
        provided_key: The API key provided by the user
        stored_hash: The hash stored in the database

    Returns:
        True if the key matches, False otherwise
    """
    return hash_api_key(provided_key) == stored_hash
