#!/usr/bin/env python
"""Test all the queries the user tried to see what's working locally."""

import sys
import asyncio
sys.path.insert(0, "pizzaz_server_python")

from pizzaz_server_python.shared.locations import fetch_providence_locations, location_matches_reason
from pizzaz_server_python.shared.geocoding import zip_to_coords, haversine_distance

async def test_query(reason, location):
    """Test a single query."""
    print("=" * 80)
    print(f"TESTING: '{reason}' in '{location}'")
    print("=" * 80)
    
    # Step 1: Geocode
    user_coords = zip_to_coords(location)
    print(f"Step 1 - Geocoding '{location}': {user_coords}")
    
    if not user_coords:
        print("❌ FAILED: Could not geocode location")
        print()
        return
    
    # Step 2: Load locations
    all_locations = await fetch_providence_locations()
    print(f"Step 2 - Loaded {len(all_locations)} locations")
    
    # Step 3: Filter by reason
    matched = []
    for loc in all_locations:
        matches, match_desc = location_matches_reason(loc, reason)
        if matches:
            coords = loc.get("coordinates")
            if coords and coords.get("lat") and coords.get("lng"):
                distance = haversine_distance(
                    user_coords[0], user_coords[1],
                    coords["lat"], coords["lng"]
                )
                matched.append((loc, distance))
    
    print(f"Step 3 - Filtered to {len(matched)} matching locations")
    
    # Step 4: Sort by distance
    matched.sort(key=lambda x: x[1])
    
    print(f"Step 4 - Sorted by distance")
    print()
    print("TOP 5 RESULTS:")
    print("-" * 80)
    
    for i, (loc, dist) in enumerate(matched[:5], 1):
        name = loc.get("name", "Unknown")
        address = loc.get("address_plain", "Unknown")
        state = "CA" if ", CA " in address else ("WA" if ", WA " in address else ("OR" if ", OR " in address else "??"))
        print(f"{i}. [{state}] {name}")
        print(f"   {address}")
        print(f"   Distance: {dist:.1f} miles")
        print()
    
    # Check if top result is in the right state
    if matched:
        top_address = matched[0][0].get("address_plain", "")
        if ", CA " in top_address and (", WA " in location.upper() or ", OR " in location.upper() or location in ["97202", "Seattle", "Portland", "Everett"]):
            print("⚠️ WARNING: Top result is in CA but query was for WA/OR!")
            print()

async def main():
    """Run all test queries."""
    test_cases = [
        ("urgent care", "97202"),
        ("urgent care", "Seattle"),
        ("urgent care", "Everett"),
        ("urgent care", "Portland"),
        ("covid test", "Portland"),
        ("urgent care", "Seattle WA"),
    ]
    
    for reason, location in test_cases:
        await test_query(reason, location)

if __name__ == "__main__":
    asyncio.run(main())

