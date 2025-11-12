"""ZIP code geocoding and distance calculations."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict

# Load cached ZIP codes
_ZIP_COORDS_CACHE: Dict[str, tuple[float, float]] | None = None


def _load_zip_coords() -> Dict[str, tuple[float, float]]:
    """Load ZIP code coordinates from cache file."""
    global _ZIP_COORDS_CACHE
    if _ZIP_COORDS_CACHE is None:
        cache_file = Path(__file__).parent.parent / "zip_coords_cache.json"
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Convert lists to tuples
                _ZIP_COORDS_CACHE = {k: tuple(v) for k, v in data.items()}
        else:
            print(f"Warning: ZIP coords cache not found at {cache_file}")
            _ZIP_COORDS_CACHE = {}
    return _ZIP_COORDS_CACHE


def zip_to_coords(zip_code: str) -> tuple[float, float] | None:
    """
    Convert a ZIP code to lat/lon coordinates using cached data.
    
    Args:
        zip_code: ZIP code string (e.g., "97202" or "97202-1234")
    
    Returns:
        (latitude, longitude) tuple or None if not found
    """
    clean_zip = zip_code.strip().split('-')[0][:5]
    zip_coords = _load_zip_coords()
    return zip_coords.get(clean_zip)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance in miles between two points on Earth.
    
    Args:
        lat1: Latitude of first point
        lon1: Longitude of first point
        lat2: Latitude of second point
        lon2: Longitude of second point
    
    Returns:
        Distance in miles
    """
    # Convert to radians
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    
    # Haversine formula
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of Earth in miles
    radius_miles = 3959.0
    return c * radius_miles

