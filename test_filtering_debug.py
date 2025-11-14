#!/usr/bin/env python
"""Debug the filtering issue with 97202 urgent care query."""

import sys
import asyncio
sys.path.insert(0, "pizzaz_server_python")

from pizzaz_server_python.shared.locations import fetch_providence_locations, location_matches_reason
from pizzaz_server_python.shared.geocoding import zip_to_coords, haversine_distance

async def debug_filtering():
    """Test exactly what the user is seeing."""
    
    print("=" * 80)
    print("DEBUG: Testing 'urgent care' near ZIP 97202")
    print("=" * 80)
    
    # Load locations
    locations = await fetch_providence_locations()
    print(f"\nTotal locations loaded: {len(locations)}")
    
    # Geocode 97202
    user_coords = zip_to_coords("97202")
    print(f"User coordinates for 97202: {user_coords}")
    
    if not user_coords:
        print("ERROR: Could not geocode 97202!")
        return
    
    # Test the filtering with "urgent care"
    reason = "urgent care"
    print(f"\nTesting reason: '{reason}'")
    
    matched_locations = []
    filtered_out = []
    
    for loc in locations:
        # Test if it matches
        matches, match_desc = location_matches_reason(loc, reason)
        
        coords = loc.get("coordinates")
        if coords and coords.get("lat") and coords.get("lng"):
            distance = haversine_distance(
                user_coords[0], user_coords[1],
                coords["lat"], coords["lng"]
            )
            
            if matches:
                matched_locations.append((loc, distance, match_desc))
            else:
                # Track what got filtered out
                filtered_out.append((loc, distance))
    
    print(f"\n✅ MATCHED: {len(matched_locations)} locations")
    print(f"❌ FILTERED OUT: {len(filtered_out)} locations")
    
    # Sort by distance
    matched_locations.sort(key=lambda x: x[1])
    filtered_out.sort(key=lambda x: x[1])
    
    print("\n" + "=" * 80)
    print("TOP 5 MATCHED LOCATIONS (what user sees):")
    print("=" * 80)
    for i, (loc, dist, match_desc) in enumerate(matched_locations[:5], 1):
        name = loc.get("name", "Unknown")
        address = loc.get("address_plain", "Unknown")
        print(f"{i}. {name}")
        print(f"   Address: {address}")
        print(f"   Distance: {dist:.1f} miles")
        print(f"   Match: {match_desc}")
        print()
    
    print("\n" + "=" * 80)
    print("TOP 5 FILTERED OUT LOCATIONS (closest ones we're missing):")
    print("=" * 80)
    for i, (loc, dist) in enumerate(filtered_out[:5], 1):
        name = loc.get("name", "Unknown")
        address = loc.get("address_plain", "Unknown")
        
        # Show what services they have
        services = loc.get("services", [])
        service_list = []
        for scat in services[:2]:  # First 2 categories
            for sval in scat.get("values", [])[:2]:  # First 2 values
                service_list.append(sval.get("val", ""))
        
        print(f"{i}. {name}")
        print(f"   Address: {address}")
        print(f"   Distance: {dist:.1f} miles")
        print(f"   Services (sample): {service_list[:2]}")
        print()
    
    # Check if Portland locations are in the filtered out list
    print("\n" + "=" * 80)
    print("CHECKING FOR PORTLAND LOCATIONS:")
    print("=" * 80)
    
    portland_in_matched = [loc for loc, dist, _ in matched_locations if ", OR " in loc.get("address_plain", "")]
    portland_filtered_out = [loc for loc, dist in filtered_out if ", OR " in loc.get("address_plain", "")]
    
    print(f"Portland locations MATCHED: {len(portland_in_matched)}")
    print(f"Portland locations FILTERED OUT: {len(portland_filtered_out)}")
    
    if portland_filtered_out:
        print("\n❌ PROBLEM: Portland locations are being filtered out!")
        print("First 3 Portland locations that got filtered:")
        for loc in portland_filtered_out[:3]:
            print(f"  - {loc.get('name')}: {loc.get('address_plain')}")

if __name__ == "__main__":
    asyncio.run(debug_filtering())

