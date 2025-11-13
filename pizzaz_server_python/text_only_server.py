"""Text-only MCP server for Providence care locations.

This server provides the same care location functionality as the main server,
but returns formatted markdown text instead of custom widgets.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import mcp.types as types
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .shared import (
    detect_er_red_flags,
    detect_service_requirements,
    fetch_providence_locations,
    get_all_available_services,
    haversine_distance,
    is_location_open_now,
    location_has_service,
    location_matches_reason,
    location_offers_services,
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


def create_text_only_app():
    """Factory function to create the text-only MCP app."""
    
    mcp = FastMCP(
        name="providence-care-text-only",
        description="""
        Providence Healthcare Appointment & Location Finder (Text Output)
        
        🌎 SERVICE AREAS:
        Washington: Seattle, Everett, Tacoma, Olympia, Spokane, Bellingham, Vancouver, Yakima, Kennewick
        Oregon: Portland, Salem, Eugene, Bend, Medford, Corvallis, Lake Oswego, Tigard, Beaverton
        California: Los Angeles, Torrance, Carson, Santa Rosa, Petaluma
        
        💉 SERVICES OFFERED (77+ total):
        • Urgent Care & Walk-In: Same-day care, minor injuries, illnesses
        • COVID-19: Testing, treatment, vaccinations
        • Lab Services: Blood tests, urinalysis, strep/flu tests, cholesterol screening
        • Imaging: X-rays, diagnostic imaging (on-site at many locations)
        • Injuries: Sprains, strains, fractures, cuts, burns, abscesses
        • Common Illnesses: Cold/flu, fever, cough, allergies, infections, sore throat
        • Preventive: Physical exams, vaccinations, health screenings
        • Specialty Services: IV hydration, IV antibiotics, procedure rooms
        (Read providence://services/catalog-text for complete list)
        
        ⚡ WHEN TO USE THIS APP:
        - User in WA, OR, or CA needs healthcare
        - Finding doctors, clinics, or medical facilities
        - Appointments (urgent, same-day, evening, weekend)
        - Specific times ("6pm", "tonight", "open now")
        - Medical services (lab, X-ray, COVID test, vaccinations)
        - Symptoms or injuries (fever, sprain, illness)
        - Location-based care (city names, ZIP codes, "near me")
        
        📋 FEATURES:
        - 76+ Providence locations
        - Real-time hours and availability
        - Distance-based sorting
        - Evening and weekend hours
        - Formatted Markdown text output
        - Direct booking links
        
        🎯 HOW TO USE:
        1. Read providence://services/catalog-text for all 77+ services
        2. Match user needs to specific services
        3. Call care-locations-text tool with location + services/reason
        4. Returns formatted text with locations, hours, and booking
        """,
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
- Finding doctors, clinics, or medical facilities
- Healthcare appointments (urgent care, primary care, express care, walk-in)
- Checking availability (evening hours, weekend, same-day, "open now", specific times like "6pm")
- Specific medical services (lab work, X-ray, COVID test, physical exams, vaccinations, etc.)
- Location-based care ("near me", city names, ZIP codes, specific addresses)
- Symptoms or medical needs requiring care (fever, injury, illness, etc.)

Returns formatted Markdown text with nearby Providence locations, hours, ratings, and booking links.

IMPORTANT: Before calling this tool, read the providence://services/catalog-text resource to see all 77+ available services, then use the filter_services parameter to match user needs intelligently.""",
                inputSchema=CARE_LOCATION_INPUT_SCHEMA,
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
        if name != "care-locations-text":
            raise ValueError(f"Unknown tool: {name}")
        
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

