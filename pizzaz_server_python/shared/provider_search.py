"""Provider search utilities for OmniSearch API integration."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
import httpx


# OmniSearch API configuration
OMNISEARCH_BASE_URL = "https://providenceomni.azurewebsites.net/api/OmniSearch"
CHROME_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


async def search_providers(
    search: str,
    location: Optional[str] = None,
    accepting_new_patients: Optional[bool] = None,
    virtual_care: Optional[bool] = None,
    languages: Optional[List[str]] = None,
    insurance: Optional[str] = None,
    gender: Optional[str] = None,
    age_group: Optional[str] = None,
    top: int = 5,
    skip: int = 0,
) -> Dict[str, Any]:
    """
    Search for healthcare providers using the OmniSearch API.
    
    Args:
        search: Provider name, specialty, or condition (e.g., 'cardiologist', 'Dr. Smith')
        location: User location (city/state or ZIP code, e.g., 'Seattle WA', '97202')
        accepting_new_patients: Filter to only providers accepting new patients
        virtual_care: Filter to only providers offering telemedicine
        languages: Filter by languages spoken (e.g., ['Spanish', 'English'])
        insurance: Filter by insurance accepted (e.g., 'Kaiser', 'Premera')
        gender: Filter by provider gender ('Male' or 'Female')
        age_group: Filter by age groups seen (e.g., 'Pediatrics', 'Adult', 'Geriatrics')
        top: Number of results to return (default: 5, max: 50)
        skip: Pagination offset (default: 0)
    
    Returns:
        Dictionary containing provider results and metadata
    """
    # Generate unique client ID for this request
    cid = str(uuid.uuid4())
    
    # Build query parameters
    params = {
        "type": "search",
        "brand": "providence",
        "search": search,
        "top": min(top, 50),  # Cap at 50
        "skip": skip,
        "time": "any",
        "IsClinic": "false",  # Search for providers, not clinics
        "cid": cid,
    }
    
    # Add location parameters if provided
    if location:
        params["location"] = location
        params["userLocation"] = location
    
    # Build headers with Chrome user agent
    headers = {
        "User-Agent": CHROME_USER_AGENT,
        "Accept": "application/json",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                OMNISEARCH_BASE_URL,
                params=params,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract providers array (API returns them as 'results')
            providers = data.get("results", [])
            
            # Apply client-side filters if needed
            filtered_providers = []
            for provider in providers:
                # Filter by accepting new patients
                if accepting_new_patients is not None:
                    if provider.get("AcceptingNewPatients", 0) != (1 if accepting_new_patients else 0):
                        continue
                
                # Filter by virtual care
                if virtual_care is not None:
                    if provider.get("VirtualCare", 0) != (1 if virtual_care else 0):
                        continue
                
                # Filter by languages
                if languages:
                    provider_languages = provider.get("Languages", [])
                    if not any(lang in provider_languages for lang in languages):
                        continue
                
                # Filter by insurance
                if insurance:
                    accepted_insurance = provider.get("InsuranceAccepted", [])
                    # Case-insensitive partial match
                    if not any(insurance.lower() in ins.lower() for ins in accepted_insurance):
                        continue
                
                # Filter by gender
                if gender:
                    if provider.get("Gender", "").lower() != gender.lower():
                        continue
                
                # Filter by age group
                if age_group:
                    ages_seen = provider.get("AgesSeen", [])
                    if age_group not in ages_seen:
                        continue
                
                filtered_providers.append(provider)
            
            # Limit to requested number of results
            filtered_providers = filtered_providers[:top]
            
            return {
                "success": True,
                "providers": filtered_providers,
                "total_count": data.get("providersCount", len(providers)),
                "filtered_count": len(filtered_providers),
                "location_info": data.get("geoip", {}),
                "search_query": search,
                "request_cid": cid,
            }
    
    except httpx.HTTPStatusError as e:
        print(f"[OmniSearch] HTTP error: {e.response.status_code}")
        return {
            "success": False,
            "error": f"OmniSearch API returned error: {e.response.status_code}",
            "providers": [],
            "total_count": 0,
            "filtered_count": 0,
        }
    
    except httpx.TimeoutException:
        print("[OmniSearch] Request timed out")
        return {
            "success": False,
            "error": "Request to OmniSearch API timed out",
            "providers": [],
            "total_count": 0,
            "filtered_count": 0,
        }
    
    except Exception as e:
        print(f"[OmniSearch] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "providers": [],
            "total_count": 0,
            "filtered_count": 0,
        }


def format_provider_location(provider: Dict[str, Any], show_all: bool = False) -> str:
    """
    Format provider location information.
    
    Args:
        provider: Provider dictionary from OmniSearch
        show_all: If True, show all locations; if False, show primary location only
    
    Returns:
        Formatted location string
    """
    location_names = provider.get("LocationNames", [])
    addresses = provider.get("Addresses", [])
    
    if not location_names and not addresses:
        return "Location information not available"
    
    if show_all:
        # Show all locations
        locations = []
        for i, name in enumerate(location_names):
            addr = addresses[i] if i < len(addresses) else ""
            locations.append(f"  - {name}\n    {addr}")
        return "\n".join(locations)
    else:
        # Show primary location only
        primary_name = location_names[0] if location_names else "Unknown Location"
        primary_addr = addresses[0] if addresses else ""
        
        # If provider works at multiple locations
        if len(location_names) > 1:
            return f"{primary_name}\n{primary_addr}\n*(Also practices at {len(location_names) - 1} other location(s))*"
        else:
            return f"{primary_name}\n{primary_addr}"


def get_provider_booking_url(provider: Dict[str, Any]) -> Optional[str]:
    """
    Get the booking URL for a provider.
    
    Args:
        provider: Provider dictionary from OmniSearch
    
    Returns:
        Booking URL or None
    """
    return provider.get("ProviderUniqueUrlOnesite") or provider.get("ProfileUrl")

