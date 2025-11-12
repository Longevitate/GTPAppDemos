"""Text-only MCP server for Providence care locations.

This server provides the same care location functionality as the main server,
but returns formatted text output instead of custom widgets. This is useful for:
- Text-only interfaces
- API integrations
- Testing and debugging
- Accessibility-focused applications
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

import mcp.types as types
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from shared import (
    detect_er_red_flags,
    detect_service_requirements,
    fetch_providence_locations,
    haversine_distance,
    is_location_open_now,
    location_has_service,
    location_matches_reason,
    zip_to_coords,
)

# MCP server instance
mcp = FastMCP(
    name="providence-care-text-only",
    stateless_http=True,
)


class CareLocationInput(BaseModel):
    """Schema for care location tools."""

    reason: str | None = Field(
        default="",
        description="Reason for seeking care (optional).",
    )
    location: str | None = Field(
        default="",
        description="User location or ZIP code (optional).",
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")


CARE_LOCATION_INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "reason": {
            "type": "string",
            "description": "Reason for seeking care (optional).",
        },
        "location": {
            "type": "string",
            "description": "User location or ZIP code (optional).",
        }
    },
    "required": [],
    "additionalProperties": False,
}


def format_location_text(locations: List[Dict[str, Any]], reason: str | None, location: str | None, is_emergency: bool = False, emergency_warning: str | None = None) -> str:
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


@mcp._mcp_server.list_tools()
async def _list_tools() -> List[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="care-locations-text",
            title="Find Providence Care Locations (Text)",
            description="Search for Providence urgent care and express care locations. Returns formatted text output.",
            inputSchema=CARE_LOCATION_INPUT_SCHEMA,
            # Disable approval prompts
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
        
        # Track seen location IDs to avoid duplicates
        seen_ids = set()
        
        for loc in all_locations:
            # Skip duplicates
            loc_id = loc.get("id")
            if loc_id in seen_ids:
                continue
            seen_ids.add(loc_id)
            
            # Check if location matches the reason for visit
            matches_reason, match_description = location_matches_reason(loc, payload.reason)
            if payload.reason and payload.reason.strip() and not matches_reason:
                continue
            
            # Check if location has required services
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
        
        # Debug log
        if processed_locations:
            if payload.reason and payload.reason.strip():
                print(f"✅ Found {len(processed_locations)} locations matching '{payload.reason}'")
            print(f"Top 3 closest locations:")
            for loc in processed_locations[:3]:
                print(f"  - {loc['name']}: {loc['distance']} mi")
    else:
        # No location provided - filter by reason and take first matches
        for loc in all_locations:
            matches_reason, match_description = location_matches_reason(loc, payload.reason)
            if payload.reason and payload.reason.strip() and not matches_reason:
                continue
            
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


# Create the ASGI app
app = mcp.streamable_http_app()

# Add CORS middleware
try:
    from starlette.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )
except Exception:
    pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("text_only_server:app", host="0.0.0.0", port=8001)

