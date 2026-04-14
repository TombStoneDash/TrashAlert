#!/usr/bin/env python3
"""
Build a static address index from the City of San Diego address points CSV.

Produces a JSON file used by /api/suggest for universal autocomplete.
Format: { street_name: { zips: ["92126"], community: "San Diego", numbers: [1000, 1002, ...] } }

For streets with many addresses, we store min/max range instead of all numbers.
"""

import csv
import json
import os
from collections import defaultdict

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'addrapn_datasd.csv')
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'src', 'data', 'sd-address-index.json')

def build_index():
    # street_key -> { zips: set, community: str, numbers: list }
    streets = defaultdict(lambda: {'zips': set(), 'communities': set(), 'numbers': set()})
    
    total = 0
    skipped = 0
    
    with open(CSV_PATH, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            num = row.get('addrnmbr', '').strip()
            if not num:
                skipped += 1
                continue
            try:
                num_int = int(float(num))
            except (ValueError, OverflowError):
                skipped += 1
                continue
            if num_int == 0:
                skipped += 1
                continue
            
            name = row.get('addrname', '').strip().upper()
            if not name:
                skipped += 1
                continue
            
            pdir = row.get('addrpdir', '').strip().upper()
            postd = row.get('addrpostd', '').strip().upper()
            sfx = row.get('addrsfx', '').strip().upper()
            zipcode = row.get('addrzip', '').strip()
            community = row.get('community', '').strip().title()
            
            # Build street key
            parts = []
            if pdir:
                parts.append(pdir)
            parts.append(name)
            if postd:
                parts.append(postd)
            if sfx:
                parts.append(sfx)
            street = ' '.join(parts)
            
            entry = streets[street]
            if zipcode:
                entry['zips'].add(zipcode)
            entry['communities'].add(community or 'San Diego')
            entry['numbers'].add(num_int)
    
    print(f"Processed {total} rows, skipped {skipped}")
    print(f"Unique streets: {len(streets)}")
    
    # Convert to serializable format
    # For each street, store:
    # - zips: list of ZIP codes
    # - community: most common community
    # - min/max: address number range
    # - count: how many addresses
    # For streets with < 50 addresses, store all numbers (for precise matching)
    # For streets with >= 50, store just min/max (range matching)
    
    index = {}
    total_entries = 0
    
    for street, data in sorted(streets.items()):
        numbers = sorted(data['numbers'])
        zips = sorted(data['zips'])
        communities = sorted(data['communities'])
        
        entry = {
            'z': zips,  # zips (abbreviated for size)
            'c': communities[0] if communities else 'San Diego',  # community
            'n': len(numbers),  # count
        }
        
        if len(numbers) <= 50:
            entry['a'] = numbers  # all address numbers
        else:
            entry['r'] = [numbers[0], numbers[-1]]  # range [min, max]
            # Also store a sample for autocomplete (every Nth)
            step = max(1, len(numbers) // 20)
            entry['s'] = numbers[::step][:20]  # sample of ~20 numbers
        
        index[street] = entry
        total_entries += 1
    
    # Write output
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(index, f, separators=(',', ':'))
    
    file_size = os.path.getsize(OUTPUT_PATH)
    print(f"\nWrote {total_entries} streets to {OUTPUT_PATH}")
    print(f"File size: {file_size:,} bytes ({file_size/1024/1024:.1f} MB)")
    
    # Also build a simpler "street names only" file for fast prefix search
    # This is a sorted list of street names for binary search
    names_path = OUTPUT_PATH.replace('.json', '-names.json')
    with open(names_path, 'w') as f:
        json.dump(sorted(index.keys()), f, separators=(',', ':'))
    
    names_size = os.path.getsize(names_path)
    print(f"Names index: {names_size:,} bytes ({names_size/1024:.0f} KB)")


if __name__ == '__main__':
    build_index()
