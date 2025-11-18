"""Text-only MCP server for Providence care locations.

This server provides the same care location functionality as the main server,
but returns formatted markdown text instead of custom widgets.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List

import mcp.types as types
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .shared import (
    detect_er_red_flags,
    detect_service_requirements,
    fetch_providence_locations,
    format_provider_location,
    get_all_available_services,
    get_provider_booking_url,
    haversine_distance,
    is_location_open_now,
    location_has_service,
    location_matches_reason,
    location_offers_services,
    search_providers,
    zip_to_coords,
)


class CareLocationInput(BaseModel):
    """Schema for care location tools."""

    reason: str | None = Field(
        default="",
        description="Reason for seeking care (optional). Used for general matching when specific services aren't specified.",
    )
    location: str | None = Field(
        default="",
        description="User location as ZIP code (e.g., '97202') or city name (e.g., 'Everett WA', 'Portland OR'). Optional.",
    )
    filter_services: List[str] | None = Field(
        default=None,
        description="Optional list of specific services to filter by. If provided, only locations offering ALL specified services will be returned.",
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ProviderSearchInput(BaseModel):
    """Schema for provider search tools."""

    search: str = Field(
        ...,
        description="Provider name, specialty, or condition to search for. Examples: 'cardiologist', 'Dr. Smith', 'pediatrician', 'heart disease specialist'",
    )
    location: str | None = Field(
        default=None,
        description="User location as city/state (e.g., 'Seattle WA', 'Portland OR') or ZIP code (e.g., '97202'). Optional.",
    )
    accepting_new_patients: bool | None = Field(
        default=None,
        description="Filter to only show providers accepting new patients. Set to true to filter.",
    )
    virtual_care: bool | None = Field(
        default=None,
        description="Filter to only show providers offering virtual/telemedicine visits. Set to true to filter.",
    )
    languages: List[str] | None = Field(
        default=None,
        description="Filter by languages spoken. Examples: ['Spanish'], ['Chinese', 'English']",
    )
    insurance: str | None = Field(
        default=None,
        description="Filter by insurance accepted. Examples: 'Kaiser', 'Premera', 'Aetna', 'Providence Health Plan'",
    )
    gender: str | None = Field(
        default=None,
        description="Filter by provider gender. Use 'Male' or 'Female'.",
    )
    age_group: str | None = Field(
        default=None,
        description="Filter by age groups seen. Options: 'Pediatrics', 'Teenagers', 'Adult', 'Geriatrics'",
    )
    limit: int = Field(
        default=5,
        description="Number of results to return (default: 5, max: 20)",
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")


CARE_LOCATION_INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "reason": {
            "type": "string",
            "description": "Reason for seeking care (optional). Used for general matching when specific services aren't specified.",
        },
        "location": {
            "type": "string",
            "description": "User location as ZIP code (e.g., '97202') or city name (e.g., 'Everett WA', 'Portland OR'). Optional.",
        },
        "filter_services": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Optional list of specific services to filter by. Read the providence://services/catalog-text resource to see available services, then match user needs to exact service names. If provided, only locations offering ALL specified services will be returned.",
        }
    },
    "required": [],
    "additionalProperties": False,
}

PROVIDER_SEARCH_INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "search": {
            "type": "string",
            "description": "Provider name, specialty, or condition to search for. Examples: 'cardiologist', 'Dr. Smith', 'pediatrician', 'heart disease specialist'",
        },
        "location": {
            "type": "string",
            "description": "User location as city/state (e.g., 'Seattle WA', 'Portland OR') or ZIP code (e.g., '97202'). Optional.",
        },
        "accepting_new_patients": {
            "type": "boolean",
            "description": "Filter to only show providers accepting new patients. Set to true to filter.",
        },
        "virtual_care": {
            "type": "boolean",
            "description": "Filter to only show providers offering virtual/telemedicine visits. Set to true to filter.",
        },
        "languages": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Filter by languages spoken. Examples: ['Spanish'], ['Chinese', 'English']",
        },
        "insurance": {
            "type": "string",
            "description": "Filter by insurance accepted. Examples: 'Kaiser', 'Premera', 'Aetna', 'Providence Health Plan'",
        },
        "gender": {
            "type": "string",
            "description": "Filter by provider gender. Use 'Male' or 'Female'.",
        },
        "age_group": {
            "type": "string",
            "description": "Filter by age groups seen. Options: 'Pediatrics', 'Teenagers', 'Adult', 'Geriatrics'",
        },
        "limit": {
            "type": "integer",
            "description": "Number of results to return (default: 5, max: 20)",
        },
    },
    "required": ["search"],
    "additionalProperties": False,
}


def format_location_text(
    locations: List[Dict[str, Any]], 
    reason: str | None, 
    location: str | None, 
    is_emergency: bool = False, 
    emergency_warning: str | None = None
) -> str:
    """
    Format locations as readable markdown text.
    
    Args:
        locations: List of location dictionaries
        reason: User's reason for seeking care
        location: User's location/ZIP code
        is_emergency: Whether emergency was detected
        emergency_warning: Emergency warning message
    
    Returns:
        Formatted markdown string
    """
    if is_emergency:
        # Emergency response
        output = "# ⚠️ EMERGENCY - CALL 911 IMMEDIATELY\n\n"
        output += f"**{emergency_warning}**\n\n"
        output += "🚨 **DO NOT go to urgent care for this condition.**\n\n"
        output += "**Call 911 or go to the nearest Emergency Room immediately.**\n\n"
        output += "For mental health crises, you can also call:\n"
        output += "- 📞 **988** - Suicide & Crisis Lifeline\n"
        output += "- 📞 **911** - Emergency Services\n"
        return output
    
    # Build header
    output = "# 🏥 Providence Care Locations\n\n"
    
    if not locations:
        output += "No care locations found matching your criteria.\n\n"
        if reason:
            output += f"*Searched for: {reason}*\n"
        return output
    
    # Add context about the search
    context_parts = []
    if reason:
        context_parts.append(f"**Reason:** {reason}")
    if location:
        context_parts.append(f"**Near:** {location}")
    
    if context_parts:
        output += " | ".join(context_parts) + "\n\n"
    
    output += f"Found **{len(locations)}** care location{'s' if len(locations) != 1 else ''}:\n\n"
    output += "---\n\n"
    
    # Format each location
    for idx, loc in enumerate(locations, 1):
        # Location name and type
        output += f"## {idx}. {loc.get('name', 'Unknown Location')}\n\n"
        
        # Type badge
        if loc.get('is_express_care'):
            output += "**ExpressCare Clinic** 🏃‍♂️\n\n"
        elif loc.get('is_urgent_care'):
            output += "**Urgent Care Clinic** 🏥\n\n"
        
        # Distance (if available)
        if loc.get('distance') is not None:
            output += f"📍 **{loc['distance']} miles away**\n\n"
        
        # Address
        address = loc.get('address_plain', '')
        if address:
            # Remove trailing state/country
            address_clean = ", ".join(address.split(",")[:-1]) if "," in address else address
            output += f"📫 {address_clean}\n\n"
        
        # Hours
        hours_today = loc.get('hours_today')
        is_open, open_status = is_location_open_now(loc)
        if hours_today:
            if is_open:
                output += f"✅ **{open_status}** - {hours_today.get('start', '')} to {hours_today.get('end', '')}\n\n"
            else:
                output += f"🕐 **{open_status}**\n\n"
        
        # Rating
        rating_value = loc.get('rating_value')
        rating_count = loc.get('rating_count')
        if rating_value and rating_count:
            stars = "⭐" * int(float(rating_value))
            output += f"{stars} **{rating_value}** ({rating_count} reviews)\n\n"
        
        # Phone
        phone = loc.get('phone')
        if phone:
            output += f"📞 **Phone:** {phone}\n\n"
        
        # Booking link
        url = loc.get('url')
        if url:
            output += f"🔗 [Book Appointment]({url})\n\n"
        
        # Add separator between locations (except last one)
        if idx < len(locations):
            output += "---\n\n"
    
    # Add footer
    output += "\n**Need help?** Call any location directly or book online through the links above.\n"
    
    return output


def format_providers_text(
    providers: List[Dict[str, Any]],
    search_query: str,
    location: str | None,
    total_count: int,
    filtered_count: int,
) -> str:
    """
    Format providers as readable markdown text.
    
    Args:
        providers: List of provider dictionaries from OmniSearch
        search_query: User's search query
        location: User's location (if provided)
        total_count: Total providers found before filtering
        filtered_count: Number of providers after filtering
    
    Returns:
        Formatted markdown string
    """
    # Build header
    output = "# 👨‍⚕️ Providence Provider Search Results\n\n"
    
    if not providers:
        output += "No providers found matching your criteria.\n\n"
        output += f"*Searched for: {search_query}*\n"
        if location:
            output += f"*Location: {location}*\n"
        return output
    
    # Add context about the search
    context_parts = []
    context_parts.append(f"**Search:** {search_query}")
    if location:
        context_parts.append(f"**Location:** {location}")
    
    output += " | ".join(context_parts) + "\n\n"
    
    if filtered_count < total_count:
        output += f"Showing **{filtered_count}** of **{total_count}** providers (filtered by your criteria):\n\n"
    else:
        output += f"Found **{filtered_count}** provider{'s' if filtered_count != 1 else ''}:\n\n"
    
    output += "---\n\n"
    
    # Format each provider
    for idx, provider in enumerate(providers, 1):
        # Provider name and credentials
        name = provider.get('Name', 'Unknown Provider')
        degrees = provider.get('Degrees', [])
        degree_str = ", ".join(degrees) if degrees else ""
        
        output += f"## {idx}. {name}"
        if degree_str:
            output += f", {degree_str}"
        output += "\n\n"
        
        # Gender (optional emoji)
        gender = provider.get('Gender', '')
        if gender:
            gender_emoji = "👨" if gender.lower() == 'male' else "👩" if gender.lower() == 'female' else ""
            output += f"{gender_emoji} **{gender}**\n\n"
        
        # Specialties
        primary_specialties = provider.get('PrimarySpecialties', [])
        sub_specialties = provider.get('SubSpecialties', [])
        
        if primary_specialties:
            output += f"🩺 **Specialty:** {', '.join(primary_specialties)}\n\n"
        if sub_specialties and sub_specialties != primary_specialties:
            output += f"📋 **Sub-specialties:** {', '.join(sub_specialties)}\n\n"
        
        # Distance (if available)
        distance = provider.get('distance')
        if distance is not None:
            output += f"📍 **{distance:.1f} miles away**\n\n"
        
        # Accepting new patients & virtual care
        accepting = provider.get('AcceptingNewPatients', 0)
        virtual = provider.get('VirtualCare', 0)
        
        badges = []
        if accepting == 1:
            badges.append("✅ Accepting New Patients")
        else:
            badges.append("⏸️ Not Accepting New Patients")
        
        if virtual == 1:
            badges.append("💻 Offers Virtual Care")
        
        output += " | ".join(badges) + "\n\n"
        
        # Rating
        rating_value = provider.get('Rating', 0) or provider.get('rating_value', 0)
        rating_count = provider.get('RatingCount', 0) or provider.get('rating_count', 0)
        
        if rating_value and rating_count:
            stars = "⭐" * int(float(rating_value))
            output += f"{stars} **{rating_value}** ({rating_count} reviews)\n\n"
        
        # Languages
        languages = provider.get('Languages', [])
        if languages:
            output += f"🗣️ **Languages:** {', '.join(languages)}\n\n"
        
        # Ages seen
        ages_seen = provider.get('AgesSeen', [])
        if ages_seen:
            output += f"👥 **Ages Seen:** {', '.join(ages_seen)}\n\n"
        
        # Practice locations
        location_names = provider.get('LocationNames', [])
        addresses = provider.get('Addresses', [])
        
        if location_names:
            output += f"🏥 **Practice Location{'s' if len(location_names) > 1 else ''}:**\n\n"
            # Show first location with address
            if addresses:
                output += f"  - **{location_names[0]}**\n"
                output += f"    {addresses[0]}\n\n"
            else:
                output += f"  - {location_names[0]}\n\n"
            
            # Show additional locations
            if len(location_names) > 1:
                output += f"  *Also practices at {len(location_names) - 1} other location(s)*\n\n"
        
        # Phone
        phones = provider.get('Phones', [])
        if phones:
            output += f"📞 **Phone:** {phones[0]}\n\n"
        
        # Professional statement (truncated)
        statement = provider.get('ProfessionalStatement', '')
        if statement:
            # Remove HTML tags
            import re
            statement_clean = re.sub('<[^<]+?>', ' ', statement)
            statement_clean = ' '.join(statement_clean.split())  # Normalize whitespace
            
            # Truncate to ~200 characters
            if len(statement_clean) > 200:
                statement_clean = statement_clean[:197] + "..."
            
            output += f"*{statement_clean}*\n\n"
        
        # Booking link
        booking_url = get_provider_booking_url(provider)
        if booking_url:
            # Handle relative URLs
            if booking_url.startswith('/'):
                booking_url = f"https://www.providence.org{booking_url}"
            output += f"🔗 [View Profile & Book Appointment]({booking_url})\n\n"
        
        # Add separator between providers (except last one)
        if idx < len(providers):
            output += "---\n\n"
    
    # Add footer
    output += "\n**Need to book an appointment?** Click the profile links above or call the provider directly.\n"
    
    return output


def create_text_only_app():
    """Factory function to create the text-only MCP app."""
    
    mcp = FastMCP(
        name="providence-care-text-only",
        stateless_http=True,
    )

    # MCP Resource: Expose available healthcare services to ChatGPT
    @mcp.resource("providence://services/catalog-text")
    def service_catalog_text() -> str:
        """
        Complete catalog of healthcare services available at Providence locations.
        
        Use this resource to understand what services are offered, then intelligently
        match user queries to specific services when calling the care-locations-text tool.
        """
        services = get_all_available_services()
        
        # Format as a readable catalog
        catalog = "# Providence Healthcare Services Catalog (Text Output)\n\n"
        catalog += f"Total services available: {len(services)}\n\n"
        catalog += "## Available Services:\n\n"
        
        for service in services:
            catalog += f"- {service}\n"
        
        return catalog

    @mcp._mcp_server.list_tools()
    async def _list_tools() -> List[types.Tool]:
        """List available tools."""
        return [
            types.Tool(
                name="care-locations-text",
                title="Find Providence Care Locations (Text)",
                description="""Find Providence healthcare locations and check appointment availability.

USE THIS TOOL FOR ANY QUERIES ABOUT:
- Finding clinics or medical facilities (urgent care, express care, walk-in clinics)
- Healthcare appointments at facilities (urgent care, primary care, express care, walk-in)
- Checking facility availability (evening hours, weekend, same-day, "open now", specific times like "6pm")
- Specific medical services at locations (lab work, X-ray, COVID test, physical exams, vaccinations, etc.)
- Location-based care ("near me", city names, ZIP codes, specific addresses)
- Symptoms or medical needs requiring care (fever, injury, illness, etc.)

Returns formatted Markdown text with nearby Providence locations, hours, ratings, and booking links.

IMPORTANT: Before calling this tool, read the providence://services/catalog-text resource to see all 77+ available services, then use the filter_services parameter to match user needs intelligently.

NOTE: For finding specific doctors/providers/specialists, use the find-provider-text tool instead.""",
                inputSchema=CARE_LOCATION_INPUT_SCHEMA,
                annotations={
                    "destructiveHint": False,
                    "openWorldHint": False,
                    "readOnlyHint": True,
                },
            ),
            types.Tool(
                name="find-provider-text",
                title="Find Healthcare Providers (Text)",
                description="""Find Providence healthcare providers (doctors, specialists, physicians, PAs, NPs).

USE THIS TOOL FOR ANY QUERIES ABOUT:
- Finding doctors by specialty (cardiologist, pediatrician, dermatologist, orthopedist, etc.)
- Finding doctors by name (Dr. Smith, Dr. Johnson, etc.)
- Finding specialists for specific conditions (heart disease, diabetes, cancer, etc.)
- Provider availability (accepting new patients, virtual care, telemedicine)
- Provider preferences (gender, languages spoken, age groups treated)
- Insurance acceptance checks

FILTERS AVAILABLE:
- Accepting new patients
- Virtual/telemedicine visits
- Languages spoken
- Insurance accepted
- Provider gender
- Age groups treated (Pediatrics, Teenagers, Adult, Geriatrics)

Returns formatted Markdown text with provider profiles, specialties, ratings, locations, and booking links.

NOTE: For finding urgent care clinics or medical facilities, use the care-locations-text tool instead.""",
                inputSchema=PROVIDER_SEARCH_INPUT_SCHEMA,
                annotations={
                    "destructiveHint": False,
                    "openWorldHint": False,
                    "readOnlyHint": True,
                },
            )
        ]

    @mcp._mcp_server.call_tool()
    async def _call_tool(name: str, arguments: dict) -> List[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        """Handle tool calls."""
        # 📊 LOG INCOMING REQUEST
        print(f"{'='*80}")
        print(f"📥 TEXT-ONLY MCP TOOL CALL: {name}")
        print(f"⏰ Timestamp: {datetime.now().isoformat()}")
        print(f"📋 Arguments: {json.dumps(arguments, indent=2)}")
        print(f"{'='*80}")
        
        # Handle provider search tool
        if name == "find-provider-text":
            # Validate input
            try:
                payload = ProviderSearchInput.model_validate(arguments)
            except ValidationError as exc:
                return [
                    types.TextContent(
                        type="text",
                        text=f"❌ Input validation error: {exc.errors()}",
                    )
                ]
            
            print(f"🔍 Provider Search: '{payload.search}'")
            if payload.location:
                print(f"📍 Location: {payload.location}")
            if payload.accepting_new_patients:
                print(f"✅ Filter: Accepting new patients")
            if payload.virtual_care:
                print(f"💻 Filter: Virtual care")
            
            # Search for providers using OmniSearch API
            result = await search_providers(
                search=payload.search,
                location=payload.location,
                accepting_new_patients=payload.accepting_new_patients,
                virtual_care=payload.virtual_care,
                languages=payload.languages,
                insurance=payload.insurance,
                gender=payload.gender,
                age_group=payload.age_group,
                top=min(payload.limit, 20),  # Cap at 20
            )
            
            if not result.get("success", False):
                error_msg = result.get("error", "Unknown error occurred")
                print(f"❌ Provider search failed: {error_msg}")
                return [
                    types.TextContent(
                        type="text",
                        text=f"❌ Provider search failed: {error_msg}\n\nPlease try again or contact Providence directly.",
                    )
                ]
            
            providers = result.get("providers", [])
            total_count = result.get("total_count", 0)
            filtered_count = result.get("filtered_count", 0)
            
            print(f"✅ Found {filtered_count} providers (total: {total_count})")
            
            # Format as text
            output_text = format_providers_text(
                providers=providers,
                search_query=payload.search,
                location=payload.location,
                total_count=total_count,
                filtered_count=filtered_count,
            )
            
            return [
                types.TextContent(
                    type="text",
                    text=output_text,
                )
            ]
        
        # Handle care locations tool
        elif name == "care-locations-text":
            # Validate input
            try:
                payload = CareLocationInput.model_validate(arguments)
            except ValidationError as exc:
                return [
                    types.TextContent(
                        type="text",
                        text=f"❌ Input validation error: {exc.errors()}",
                    )
                ]
        else:
            raise ValueError(f"Unknown tool: {name}")
        
        # Check for emergency red flags first
        is_emergency, emergency_warning = detect_er_red_flags(payload.reason)
        if is_emergency:
            print(f"🚨 EMERGENCY DETECTED: {emergency_warning}")
            emergency_text = format_location_text(
                locations=[],
                reason=payload.reason,
                location=payload.location,
                is_emergency=True,
                emergency_warning=emergency_warning
            )
            return [
                types.TextContent(
                    type="text",
                    text=emergency_text,
                )
            ]
        
        # Detect service requirements
        service_requirements = detect_service_requirements(payload.reason)
        if service_requirements:
            print(f"🔬 Detected service requirements: {', '.join(service_requirements)}")
        
        # Fetch all locations
        all_locations = await fetch_providence_locations()
        
        # Log triage information
        if payload.reason and payload.reason.strip():
            print(f"🏥 Triage: Filtering for '{payload.reason}'")
        
        # Process location parameter
        user_coords = None
        if payload.location and payload.location.strip():
            user_coords = zip_to_coords(payload.location)
            if user_coords:
                print(f"📍 Geocoded ZIP {payload.location} to coords: {user_coords}")
            else:
                print(f"⚠️  Warning: Could not geocode ZIP {payload.location}")
        
        # Filter and process locations
        processed_locations = []
        
        if user_coords and all_locations:
            print(f"Processing {len(all_locations)} locations for distance sorting...")
            user_lat, user_lon = user_coords
            
            seen_ids = set()
            
            for loc in all_locations:
                # Skip duplicates
                loc_id = loc.get("id")
                if loc_id in seen_ids:
                    continue
                seen_ids.add(loc_id)
                
                # Priority 1: Check for explicit service filters (ChatGPT-specified)
                if payload.filter_services:
                    if not location_offers_services(loc, payload.filter_services):
                        continue
                    match_description = f"Offers: {', '.join(payload.filter_services)}"
                else:
                    # Priority 2: Check if location matches the reason for visit (keyword matching)
                    matches_reason, match_description = location_matches_reason(loc, payload.reason)
                    if payload.reason and payload.reason.strip() and not matches_reason:
                        continue
                
                # Priority 3: Check if location has detected service requirements (X-ray, lab, etc.)
                if service_requirements:
                    has_all_services = all(location_has_service(loc, req) for req in service_requirements)
                    if not has_all_services:
                        continue
                
                # Check if location is open now
                is_open, open_status = is_location_open_now(loc)
                
                coords = loc.get("coordinates")
                if coords and coords.get("lat") and coords.get("lng"):
                    distance = haversine_distance(
                        user_lat, user_lon,
                        coords["lat"], coords["lng"]
                    )
                    
                    processed_loc = {
                        "id": loc.get("id"),
                        "name": loc.get("name"),
                        "address_plain": loc.get("address_plain"),
                        "coordinates": coords,
                        "distance": round(distance, 1),
                        "image": loc.get("image"),
                        "phone": loc.get("phone"),
                        "url": loc.get("url"),
                        "rating_value": loc.get("rating_value"),
                        "rating_count": loc.get("rating_count"),
                        "hours_today": loc.get("hours_today"),
                        "is_express_care": loc.get("is_express_care"),
                        "is_urgent_care": loc.get("is_urgent_care"),
                        "services": loc.get("services", []),
                        "is_open_now": is_open,
                        "open_status": open_status,
                    }
                    processed_locations.append(processed_loc)
            
            # Sort by distance
            processed_locations.sort(key=lambda x: x["distance"])
            
            # Deduplicate by name
            seen_names = set()
            unique_locations = []
            for loc in processed_locations:
                if loc["name"] not in seen_names:
                    seen_names.add(loc["name"])
                    unique_locations.append(loc)
            
            processed_locations = unique_locations[:7]
            
            if processed_locations:
                if payload.reason and payload.reason.strip():
                    print(f"✅ Found {len(processed_locations)} locations matching '{payload.reason}'")
                print(f"Top 3 closest locations:")
                for loc in processed_locations[:3]:
                    print(f"  - {loc['name']}: {loc['distance']} mi")
        else:
            # No location provided - filter by reason/services and take first matches
            for loc in all_locations:
                # Priority 1: Check for explicit service filters (ChatGPT-specified)
                if payload.filter_services:
                    if not location_offers_services(loc, payload.filter_services):
                        continue
                    match_description = f"Offers: {', '.join(payload.filter_services)}"
                else:
                    # Priority 2: Check if location matches the reason for visit (keyword matching)
                    matches_reason, match_description = location_matches_reason(loc, payload.reason)
                    if payload.reason and payload.reason.strip() and not matches_reason:
                        continue
                
                # Priority 3: Check if location has detected service requirements (X-ray, lab, etc.)
                if service_requirements:
                    has_all_services = all(location_has_service(loc, req) for req in service_requirements)
                    if not has_all_services:
                        continue
                
                is_open, open_status = is_location_open_now(loc)
                
                processed_loc = {
                    "id": loc.get("id"),
                    "name": loc.get("name"),
                    "address_plain": loc.get("address_plain"),
                    "coordinates": loc.get("coordinates"),
                    "distance": None,
                    "image": loc.get("image"),
                    "phone": loc.get("phone"),
                    "url": loc.get("url"),
                    "rating_value": loc.get("rating_value"),
                    "rating_count": loc.get("rating_count"),
                    "hours_today": loc.get("hours_today"),
                    "is_express_care": loc.get("is_express_care"),
                    "is_urgent_care": loc.get("is_urgent_care"),
                    "services": loc.get("services", []),
                    "is_open_now": is_open,
                    "open_status": open_status,
                }
                processed_locations.append(processed_loc)
                
                if len(processed_locations) >= 7:
                    break
            
            if payload.reason and payload.reason.strip():
                print(f"✅ Found {len(processed_locations)} locations matching '{payload.reason}'")
        
        # Format as text
        output_text = format_location_text(
            locations=processed_locations,
            reason=payload.reason,
            location=payload.location,
        )
        
        return [
            types.TextContent(
                type="text",
                text=output_text,
            )
        ]

    return mcp.streamable_http_app()


# Lazy app creation to avoid import issues
_app = None

def get_app():
    """Get or create the app instance."""
    global _app
    if _app is None:
        _app = create_text_only_app()
        
        # Add CORS middleware
        try:
            from starlette.middleware.cors import CORSMiddleware
            _app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["*"],
                allow_headers=["*"],
                allow_credentials=False,
            )
        except Exception:
            pass
    
    return _app

# Create app for ASGI servers
app = get_app()


if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting Text-Only MCP Server")
    print("📍 http://localhost:8001/mcp")
    uvicorn.run("pizzaz_server_python.text_only_server:app", host="0.0.0.0", port=8001, reload=True)

