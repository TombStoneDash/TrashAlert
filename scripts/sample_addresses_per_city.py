#!/usr/bin/env python3
"""
Sample up to 50 addresses per city from raw OSM address data.
Tries to spread samples across subdivisions when available.
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def sample_addresses_per_city(
    input_csv: Path,
    output_csv: Path,
    max_per_city: int = 50
) -> pd.DataFrame:
    """
    Sample up to max_per_city addresses from each city.

    Args:
        input_csv: Path to raw addresses CSV
        output_csv: Path to write sampled addresses
        max_per_city: Maximum addresses per city (default 50)

    Returns:
        Sampled DataFrame
    """
    logger.info(f"Loading raw addresses from {input_csv}")
    df = pd.read_csv(input_csv)

    logger.info(f"Loaded {len(df)} addresses from {df['city_name'].nunique()} cities")

    # Sanity check: Remove rows with null coordinates
    initial_count = len(df)
    df = df.dropna(subset=['lat', 'lon'])
    if len(df) < initial_count:
        logger.warning(f"Removed {initial_count - len(df)} rows with null coordinates")

    # Sanity check: Remove exact duplicates (city, house_number, street)
    initial_count = len(df)
    df = df.drop_duplicates(subset=['city_name', 'house_number', 'street'], keep='first')
    if len(df) < initial_count:
        logger.warning(f"Removed {initial_count - len(df)} duplicate address combinations")

    sampled_rows = []

    # Process each city
    for city_name, city_df in df.groupby('city_name'):
        city_count = len(city_df)

        if city_count <= max_per_city:
            # Take all addresses if fewer than max
            logger.info(f"{city_name}: {city_count} addresses (taking all)")
            sampled_rows.append(city_df)
        else:
            # Sample across subdivisions if available
            if 'subdivision_id' in city_df.columns and city_df['subdivision_id'].notna().any():
                sampled = sample_across_subdivisions(city_df, max_per_city, city_name)
            else:
                # Random sample if no subdivisions
                sampled = city_df.sample(n=max_per_city, random_state=42)
                logger.info(f"{city_name}: sampled {max_per_city} from {city_count} addresses (no subdivisions)")

            sampled_rows.append(sampled)

    # Combine all sampled data
    result = pd.concat(sampled_rows, ignore_index=True)

    # Final sanity checks
    logger.info("\n=== Final Sanity Checks ===")

    # Check for null coordinates
    null_coords = result[result['lat'].isna() | result['lon'].isna()]
    if len(null_coords) > 0:
        logger.error(f"FAILED: Found {len(null_coords)} rows with null coordinates!")
    else:
        logger.info("✓ No null coordinates")

    # Check for duplicates
    duplicates = result[result.duplicated(subset=['city_name', 'house_number', 'street'], keep=False)]
    if len(duplicates) > 0:
        logger.error(f"FAILED: Found {len(duplicates)} duplicate address combinations!")
        logger.error(duplicates[['city_name', 'house_number', 'street']].head(10))
    else:
        logger.info("✓ No duplicate (city, house_number, street) combinations")

    # Save to CSV
    logger.info(f"\nWriting {len(result)} sampled addresses to {output_csv}")
    result.to_csv(output_csv, index=False)

    return result


def sample_across_subdivisions(city_df: pd.DataFrame, max_per_city: int, city_name: str) -> pd.DataFrame:
    """
    Sample addresses trying to spread them across subdivisions.

    Args:
        city_df: DataFrame for a single city
        max_per_city: Maximum addresses to sample
        city_name: Name of the city (for logging)

    Returns:
        Sampled DataFrame
    """
    # Separate rows with and without subdivisions
    has_subdivision = city_df['subdivision_id'].notna()
    with_subdivisions = city_df[has_subdivision]
    without_subdivisions = city_df[~has_subdivision]

    sampled_parts = []

    # If we have subdivisions, group by them
    if len(with_subdivisions) > 0:
        subdivisions = list(with_subdivisions.groupby('subdivision_id'))

        # Add the "no subdivision" group if it exists
        if len(without_subdivisions) > 0:
            subdivisions.append(('No subdivision', without_subdivisions))

        num_subdivisions = len(subdivisions)

        # Calculate target per subdivision (trying to spread evenly)
        base_per_subdivision = max_per_city // num_subdivisions
        remainder = max_per_city % num_subdivisions

        for i, (subdivision_id, sub_df) in enumerate(subdivisions):
            # Give some subdivisions one extra to distribute the remainder
            target = base_per_subdivision + (1 if i < remainder else 0)

            # Take up to target, but not more than available
            n_to_sample = min(target, len(sub_df))

            if n_to_sample > 0:
                sampled = sub_df.sample(n=n_to_sample, random_state=42)
                sampled_parts.append(sampled)

        result = pd.concat(sampled_parts, ignore_index=True)

        logger.info(
            f"{city_name}: sampled {len(result)} from {len(city_df)} addresses "
            f"across {num_subdivisions} subdivisions"
        )
    else:
        # No subdivisions at all, just random sample
        result = city_df.sample(n=max_per_city, random_state=42)
        logger.info(f"{city_name}: sampled {max_per_city} from {len(city_df)} addresses (no subdivisions)")

    return result


def print_statistics(df: pd.DataFrame):
    """Print statistics about the sampled dataset."""
    print("\n" + "=" * 80)
    print("SAMPLED DATASET STATISTICS")
    print("=" * 80)

    # Addresses per city
    city_counts = df.groupby('city_name').size().sort_values(ascending=False)
    print("\nAddresses per city:")
    print("-" * 80)
    for city, count in city_counts.items():
        print(f"  {city:40s} {count:4d}")

    print(f"\nTotal cities: {len(city_counts)}")
    print(f"Total addresses: {len(df)}")

    # Example rows for San Diego
    print("\n" + "=" * 80)
    print("5 EXAMPLE ROWS FOR SAN DIEGO")
    print("=" * 80)
    san_diego = df[df['city_name'] == 'San Diego'].head(5)
    if len(san_diego) > 0:
        print(san_diego.to_string(index=False))
    else:
        print("No San Diego addresses found")

    # Example rows for Imperial Valley city
    print("\n" + "=" * 80)
    print("5 EXAMPLE ROWS FOR IMPERIAL VALLEY CITY")
    print("=" * 80)

    # Common Imperial Valley cities
    imperial_cities = ['El Centro', 'Calexico', 'Imperial', 'Brawley', 'Holtville']
    imperial_sample = None

    for city in imperial_cities:
        city_data = df[df['city_name'] == city]
        if len(city_data) > 0:
            print(f"\nShowing {city}:")
            print(city_data.head(5).to_string(index=False))
            imperial_sample = city_data
            break

    if imperial_sample is None:
        # Try to find any city that might be in Imperial Valley
        print("\nNo common Imperial Valley cities found. Showing first non-San Diego city:")
        other_cities = df[df['city_name'] != 'San Diego']
        if len(other_cities) > 0:
            first_city = other_cities.iloc[0]['city_name']
            print(f"\nShowing {first_city}:")
            print(df[df['city_name'] == first_city].head(5).to_string(index=False))


def main():
    """Main entry point."""
    # Define paths
    base_dir = Path(__file__).parent.parent
    input_csv = base_dir / 'data' / 'addresses_osm_raw.csv'
    output_csv = base_dir / 'data' / 'addresses_sampled_50_per_city.csv'

    # Check if input exists
    if not input_csv.exists():
        logger.error(f"Input file not found: {input_csv}")
        logger.error("Please ensure data/addresses_osm_raw.csv exists before running this script.")
        return 1

    # Sample addresses
    sampled_df = sample_addresses_per_city(input_csv, output_csv, max_per_city=50)

    # Print statistics
    print_statistics(sampled_df)

    logger.info(f"\n✓ Done! Sampled dataset saved to {output_csv}")
    return 0


if __name__ == '__main__':
    exit(main())
