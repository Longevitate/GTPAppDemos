"""Providence care locations management and filtering."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import httpx

# Try to import semantic matching (optional)
try:
    from .semantic_matching import hybrid_location_match
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False


# Load cached Providence locations
_PROVIDENCE_LOCATIONS_CACHE: List[Dict[str, Any]] | None = None


def _load_providence_locations() -> List[Dict[str, Any]]:
    """Load Providence locations from cache file."""
    global _PROVIDENCE_LOCATIONS_CACHE
    if _PROVIDENCE_LOCATIONS_CACHE is None:
        cache_file = Path(__file__).parent.parent / "providence_locations_cache.json"
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                _PROVIDENCE_LOCATIONS_CACHE = data.get("locations", [])
                print(f"Loaded {len(_PROVIDENCE_LOCATIONS_CACHE)} Providence locations from cache")
        else:
            print(f"Warning: Providence locations cache not found at {cache_file}")
            _PROVIDENCE_LOCATIONS_CACHE = []
    return _PROVIDENCE_LOCATIONS_CACHE


def get_all_available_services() -> List[str]:
    """Extract all unique service values from Providence locations."""
    locations = _load_providence_locations()
    services_set = set()
    
    for location in locations:
        services = location.get("services", [])
        for service_category in services:
            values = service_category.get("values", [])
            for service_item in values:
                service_val = service_item.get("val", "").strip()
                if service_val:
                    services_set.add(service_val)
    
    return sorted(list(services_set))


async def fetch_providence_locations() -> List[Dict[str, Any]]:
    """Get Providence care locations from cache (with API fallback)."""
    # Try cache first
    cached_locations = _load_providence_locations()
    if cached_locations:
        return cached_locations
    
    # Fallback to API if cache is empty
    print("Cache empty, fetching from API...")
    url = "https://providencekyruus.azurewebsites.net/api/searchlocationsbyservices"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get("locations", [])
    except Exception as e:
        print(f"Error fetching Providence locations from API: {e}")
        return []


def is_location_open_now(location: Dict[str, Any]) -> tuple[bool, str]:
    """
    Check if a location is currently open.
    
    Args:
        location: Location dictionary with hours_today field
    
    Returns:
        (is_open, status_text): True with status if open, False with reason if closed
    """
    hours_today = location.get("hours_today")
    if not hours_today:
        return (False, "Hours unavailable")
    
    # Check if it's 24 hours
    if hours_today.get("is24hours"):
        return (True, "Open 24 hours")
    
    start_time = hours_today.get("start")
    end_time = hours_today.get("end")
    
    if not start_time or not end_time:
        return (False, "Hours unavailable")
    
    # Parse times (format: "8:00 am" or "8:00 pm")
    try:
        now = datetime.now()
        current_time = now.time()
        
        # Simple time parsing
        def parse_time(time_str):
            time_str = time_str.strip().lower()
            parts = time_str.replace("am", "").replace("pm", "").strip().split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            
            # Convert to 24-hour format
            if "pm" in time_str and hour != 12:
                hour += 12
            elif "am" in time_str and hour == 12:
                hour = 0
            
            return hour, minute
        
        start_hour, start_min = parse_time(start_time)
        end_hour, end_min = parse_time(end_time)
        
        start = datetime.now().replace(hour=start_hour, minute=start_min, second=0)
        end = datetime.now().replace(hour=end_hour, minute=end_min, second=0)
        
        # Handle overnight hours (e.g., 8pm - 2am)
        if end < start:
            if current_time >= start.time() or current_time <= end.time():
                return (True, "Open now")
        else:
            if start.time() <= current_time <= end.time():
                return (True, "Open now")
        
        # Check if opens soon (within 1 hour)
        if current_time < start.time():
            time_diff = (start - datetime.now()).total_seconds() / 60
            if time_diff <= 60:
                return (False, f"Opens at {start_time}")
        
        return (False, f"Closed - Opens {start_time}")
        
    except Exception as e:
        print(f"Error parsing hours: {e}")
        return (False, "Hours unavailable")


def location_has_service(location: Dict[str, Any], service_type: str) -> bool:
    """
    Check if a location has a specific service (x-ray, lab, procedure room).
    
    Args:
        location: Location dictionary
        service_type: Type of service ('x-ray', 'lab', 'procedure')
    
    Returns:
        True if location has the service
    """
    services = location.get("services", [])
    
    service_type_lower = service_type.lower()
    
    # Check in services array
    for service_cat in services:
        if service_cat.get("name", "").lower() == "other":
            for item in service_cat.get("values", []):
                item_val = item.get("val", "").lower()
                if service_type_lower == "x-ray" and "x-ray" in item_val:
                    return True
                if service_type_lower == "lab" and ("lab" in item_val or "laboratory" in item_val):
                    return True
                if service_type_lower == "procedure" and ("procedure" in item_val or "minor injuries" in item_val):
                    return True
    
    return False


def _keyword_location_match(location: Dict[str, Any], reason: str) -> tuple[bool, str | None]:
    """
    Keyword-based matching with synonyms and partial word matching.
    
    This is the core matching logic that uses expanded synonyms and fuzzy string matching.
    """
    if not reason or not reason.strip():
        # No reason provided, all locations match
        return (True, None)
    
    reason_lower = reason.lower().strip()
    
    # SPECIAL CASE: Very common queries should match ALL locations
    # This prevents over-filtering on generic healthcare requests
    very_general_queries = [
        "urgent care",
        "urgent",
        "walk-in",
        "walk in",
        "same day",
        "same-day",
        "express care",
        "immediate care",
        "covid test",
        "covid-19 test",
        "coronavirus test",
        "flu shot",
        "physical exam",
        "vaccination",
    ]
    if reason_lower in very_general_queries:
        # These are SO general that ANY healthcare location should match
        return (True, reason)
    
    services = location.get("services", [])
    
    # Medical term synonyms for better matching
    synonym_map = {
        "urgent": ["immediate", "acute", "emergency", "same-day", "walk-in", "same", "day", "access"],
        "emergency": ["urgent", "critical", "severe", "acute", "er", "life-threatening"],
        "primary": ["family", "general", "routine", "preventive", "wellness"],
        "lab": ["laboratory", "blood", "test", "diagnostic", "testing"],
        "imaging": ["x-ray", "ct", "mri", "scan", "radiology", "ultrasound"],
        "therapy": ["physical", "occupational", "rehab", "rehabilitation"],
        "mental": ["behavioral", "psychology", "psychiatry", "counseling"],
        "pediatric": ["children", "child", "kids", "infant", "adolescent"],
        "women": ["obstetric", "gynecology", "maternity", "pregnancy"],
        "senior": ["geriatric", "elderly", "aging"],
        "care": ["clinic", "facility", "location", "center", "same-day", "walk-in"],
        "covid": ["covid-19", "coronavirus", "covid19", "sars-cov-2", "pandemic"],
        "test": ["testing", "exam", "examination", "screening", "check"],
        "vaccination": ["vaccine", "shot", "immunization", "vaccinations"],
        "flu": ["influenza", "flu-like", "seasonal"],
    }
    
    # Expand reason with synonyms
    reason_words = set(reason_lower.split())
    expanded_reason_words = set(reason_words)
    for word in reason_words:
        if word in synonym_map:
            expanded_reason_words.update(synonym_map[word])
    
    # Check each service category
    for service_category in services:
        values = service_category.get("values", [])
        
        for service_item in values:
            service_val = service_item.get("val", "").lower()
            service_words = set(service_val.split())
            
            # 1. Check for word overlap (including synonyms)
            common_words = expanded_reason_words & service_words
            if common_words:
                return (True, reason)
            
            # 2. Check if reason is substring of service or vice versa
            if reason_lower in service_val or service_val in reason_lower:
                return (True, reason)
            
            # 3. Check for partial word matches (e.g., "urgent" matches "urgency")
            for reason_word in expanded_reason_words:
                if len(reason_word) >= 4:  # Only for words 4+ chars
                    for service_word in service_words:
                        if len(service_word) >= 4:
                            # Check if one is a prefix of the other
                            if reason_word.startswith(service_word[:4]) or service_word.startswith(reason_word[:4]):
                                return (True, reason)
    
    # Still no match - be very lenient and return True if it's a general query
    general_terms = ["care", "help", "medical", "health", "doctor", "clinic", "hospital"]
    if any(term in reason_lower for term in general_terms):
        return (True, reason)
    
    # FALLBACK: If location is marked as urgent/express care but has no service data,
    # match any non-emergency healthcare query (helps with locations that have incomplete data)
    if location.get("is_urgent_care") or location.get("is_express_care"):
        # Check if services list is empty or has no meaningful data
        has_service_data = False
        for service_category in services:
            if service_category.get("values"):
                has_service_data = True
                break
        
        if not has_service_data:
            # No service data but marked as urgent/express care - match most queries
            # Exclude emergency-specific queries (those are handled by detect_er_red_flags)
            emergency_keywords = ["chest pain", "heart attack", "stroke", "unconscious", "911"]
            if not any(kw in reason_lower for kw in emergency_keywords):
                return (True, f"urgent/express care (incomplete service data)")
    
    # No match found
    return (False, None)


def location_matches_reason(location: Dict[str, Any], reason: str) -> tuple[bool, str | None]:
    """
    Check if a location offers services matching the user's reason for visit.
    
    Uses hybrid matching: semantic AI-based matching when available (set USE_SEMANTIC_MATCHING=true),
    otherwise falls back to keyword matching with synonyms.
    
    Args:
        location: Location dictionary
        reason: User's reason for seeking care
    
    Returns:
        (matches, match_description): True if matches with description of what matched,
                                       False with None if no match
    """
    # Use semantic matching if enabled
    if SEMANTIC_AVAILABLE and os.getenv("USE_SEMANTIC_MATCHING", "false").lower() == "true":
        try:
            return hybrid_location_match(location, reason, _keyword_location_match)
        except Exception:
            # Fall back to keyword matching on any error
            pass
    
    # Use keyword matching
    return _keyword_location_match(location, reason)


def location_offers_services(location: Dict[str, Any], required_services: List[str]) -> bool:
    """
    Check if a location offers all of the required services using flexible keyword matching.
    
    Uses the same fuzzy matching logic as location_matches_reason to handle variations
    like "COVID-19 Test" matching "COVID-19 test" or "urgent care" matching 
    "We provide same-day care...".
    
    Args:
        location: Location dictionary
        required_services: List of service names/keywords that must all be present
    
    Returns:
        True if location offers ALL required services, False otherwise
    """
    if not required_services:
        return True
    
    # Use keyword matching for each required service
    # A location must match ALL required services to be included
    for required_service in required_services:
        # Use the same matching logic as location_matches_reason
        matches, _ = location_matches_reason(location, required_service)
        if not matches:
            return False
    
    return True

