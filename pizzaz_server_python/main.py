"""Pizzaz demo MCP server implemented with the Python FastMCP helper.

The server mirrors the Node example in this repository and exposes
widget-backed tools that render the Pizzaz UI bundle. Each handler returns the
HTML shell via an MCP resource and echoes the selected topping as structured
content so the ChatGPT client can hydrate the widget. The module also wires the
handlers into an HTTP/SSE stack so you can run the server with uvicorn on port
8000, matching the Node transport behavior."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List
import math
import httpx
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import mcp.types as types
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.staticfiles import StaticFiles

# Import shared utilities
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


@dataclass(frozen=True)
class PizzazWidget:
    identifier: str
    title: str
    template_uri: str
    invoking: str
    invoked: str
    html: str
    response_text: str


ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


@lru_cache(maxsize=None)
def _load_widget_html(component_name: str) -> str:
    html_path = ASSETS_DIR / f"{component_name}.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf8")

    fallback_candidates = sorted(ASSETS_DIR.glob(f"{component_name}-*.html"))
    if fallback_candidates:
        return fallback_candidates[-1].read_text(encoding="utf8")

    raise FileNotFoundError(
        f'Widget HTML for "{component_name}" not found in {ASSETS_DIR}. '
        "Run `pnpm run build` to generate the assets before starting the server."
    )


widgets: List[PizzazWidget] = [
    PizzazWidget(
        identifier="pizza-map",
        title="Show Pizza Map",
        template_uri="ui://widget/pizza-map.html",
        invoking="Hand-tossing a map",
        invoked="Served a fresh map",
        html=_load_widget_html("pizzaz"),
        response_text="Rendered a pizza map!",
    ),
    PizzazWidget(
        identifier="pizza-carousel",
        title="Show Pizza Carousel",
        template_uri="ui://widget/pizza-carousel.html",
        invoking="Carousel some spots",
        invoked="Served a fresh carousel",
        html=_load_widget_html("pizzaz-carousel"),
        response_text="Rendered a pizza carousel!",
    ),
    PizzazWidget(
        identifier="pizza-albums",
        title="Show Pizza Album",
        template_uri="ui://widget/pizza-albums.html",
        invoking="Hand-tossing an album",
        invoked="Served a fresh album",
        html=_load_widget_html("pizzaz-albums"),
        response_text="Rendered a pizza album!",
    ),
    PizzazWidget(
        identifier="pizza-list",
        title="Show Pizza List",
        template_uri="ui://widget/pizza-list.html",
        invoking="Hand-tossing a list",
        invoked="Served a fresh list",
        html=_load_widget_html("pizzaz-list"),
        response_text="Rendered a pizza list!",
    ),
    PizzazWidget(
        identifier="care-locations",
        title="Show Care Locations",
        template_uri="ui://widget/care-list.html",
        invoking="Finding care locations",
        invoked="Found care locations",
        html=_load_widget_html("care-list"),
        response_text="Showing Providence care locations!",
    ),
]


MIME_TYPE = "text/html+skybridge"


WIDGETS_BY_ID: Dict[str, PizzazWidget] = {
    widget.identifier: widget for widget in widgets
}
WIDGETS_BY_URI: Dict[str, PizzazWidget] = {
    widget.template_uri: widget for widget in widgets
}


# Load cached ZIP codes
_ZIP_COORDS_CACHE: Dict[str, tuple[float, float]] | None = None

def _load_zip_coords() -> Dict[str, tuple[float, float]]:
    """Load ZIP code coordinates from cache file."""
    global _ZIP_COORDS_CACHE
    if _ZIP_COORDS_CACHE is None:
        cache_file = Path(__file__).parent / "zip_coords_cache.json"
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Convert lists to tuples
                _ZIP_COORDS_CACHE = {k: tuple(v) for k, v in data.items()}
        else:
            print(f"Warning: ZIP coords cache not found at {cache_file}")
            _ZIP_COORDS_CACHE = {}
    return _ZIP_COORDS_CACHE


# Load cached Providence locations
_PROVIDENCE_LOCATIONS_CACHE: List[Dict[str, Any]] | None = None

def _load_providence_locations() -> List[Dict[str, Any]]:
    """Load Providence locations from cache file."""
    global _PROVIDENCE_LOCATIONS_CACHE
    if _PROVIDENCE_LOCATIONS_CACHE is None:
        cache_file = Path(__file__).parent / "providence_locations_cache.json"
        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                _PROVIDENCE_LOCATIONS_CACHE = data.get("locations", [])
                print(f"Loaded {len(_PROVIDENCE_LOCATIONS_CACHE)} Providence locations from cache")
        else:
            print(f"Warning: Providence locations cache not found at {cache_file}")
            _PROVIDENCE_LOCATIONS_CACHE = []
    return _PROVIDENCE_LOCATIONS_CACHE

# Duplicate functions removed - now importing from shared.locations and shared.geocoding


class PizzaInput(BaseModel):
    """Schema for pizza tools."""

    pizza_topping: str = Field(
        ...,
        alias="pizzaTopping",
        description="Topping to mention when rendering the widget.",
    )

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


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


# No session storage needed - stateless architecture!
# Widget will call API with arguments passed via meta tags

mcp = FastMCP(
    name="pizzaz-python",
    stateless_http=True,
)


# MCP Resource: Expose available healthcare services to ChatGPT
@mcp.resource("providence://services/catalog")
def service_catalog() -> str:
    """
    Complete catalog of healthcare services available at Providence locations.
    
    Use this resource to understand what services are offered, then intelligently
    match user queries to specific services when calling the care-locations tool.
    """
    services = get_all_available_services()
    
    # Format as a readable catalog
    catalog = "# Providence Healthcare Services Catalog\n\n"
    catalog += f"Total services available: {len(services)}\n\n"
    catalog += "## Available Services:\n\n"
    
    for service in services:
        catalog += f"- {service}\n"
    
    return catalog


TOOL_INPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "pizzaTopping": {
            "type": "string",
            "description": "Topping to mention when rendering the widget.",
        }
    },
    "required": ["pizzaTopping"],
    "additionalProperties": False,
}

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
            "description": "Optional list of specific services to filter by. Read the providence://services/catalog resource to see available services, then match user needs to exact service names. If provided, only locations offering ALL specified services will be returned.",
        }
    },
    "required": [],
    "additionalProperties": False,
}


def _resource_description(widget: PizzazWidget) -> str:
    return f"{widget.title} widget markup"


def _tool_meta(widget: PizzazWidget) -> Dict[str, Any]:
    return {
        "openai/outputTemplate": widget.template_uri,
        "openai/toolInvocation/invoking": widget.invoking,
        "openai/toolInvocation/invoked": widget.invoked,
        "openai/widgetAccessible": True,
        "openai/resultCanProduceWidget": True,
    }


def _embedded_widget_resource(widget: PizzazWidget) -> types.EmbeddedResource:
    return types.EmbeddedResource(
        type="resource",
        resource=types.TextResourceContents(
            uri=widget.template_uri,
            mimeType=MIME_TYPE,
            text=widget.html,
            title=widget.title,
        ),
    )


def _get_tool_description(widget: PizzazWidget) -> str:
    """Get enhanced description for a tool based on widget type."""
    if widget.identifier == "care-locations":
        return """Find Providence healthcare locations and check appointment availability.

USE THIS TOOL FOR ANY QUERIES ABOUT:
- Finding doctors, clinics, or medical facilities
- Healthcare appointments (urgent care, primary care, express care, walk-in)
- Checking availability (evening hours, weekend, same-day, "open now", specific times like "6pm")
- Specific medical services (lab work, X-ray, COVID test, physical exams, vaccinations, etc.)
- Location-based care ("near me", city names, ZIP codes, specific addresses)
- Symptoms or medical needs requiring care (fever, injury, illness, etc.)

Returns an interactive map widget showing nearby Providence locations with hours and booking links.

IMPORTANT: Before calling this tool, read the providence://services/catalog resource to see all 77+ available services, then use the filter_services parameter to match user needs intelligently."""
    return widget.title


@mcp._mcp_server.list_tools()
async def _list_tools() -> List[types.Tool]:
    return [
        types.Tool(
            name=widget.identifier,
            title=widget.title,
            description=_get_tool_description(widget),
            inputSchema=deepcopy(
                CARE_LOCATION_INPUT_SCHEMA 
                if widget.identifier == "care-locations" 
                else TOOL_INPUT_SCHEMA
            ),
            _meta=_tool_meta(widget),
            # To disable the approval prompt for the tools
            annotations={
                "destructiveHint": False,
                "openWorldHint": False,
                "readOnlyHint": True,
            },
        )
        for widget in widgets
    ]


@mcp._mcp_server.list_resources()
async def _list_resources() -> List[types.Resource]:
    return [
        types.Resource(
            name=widget.title,
            title=widget.title,
            uri=widget.template_uri,
            description=_resource_description(widget),
            mimeType=MIME_TYPE,
            _meta=_tool_meta(widget),
        )
        for widget in widgets
    ]


@mcp._mcp_server.list_resource_templates()
async def _list_resource_templates() -> List[types.ResourceTemplate]:
    return [
        types.ResourceTemplate(
            name=widget.title,
            title=widget.title,
            uriTemplate=widget.template_uri,
            description=_resource_description(widget),
            mimeType=MIME_TYPE,
            _meta=_tool_meta(widget),
        )
        for widget in widgets
    ]


async def _handle_read_resource(req: types.ReadResourceRequest) -> types.ServerResult:
    widget = WIDGETS_BY_URI.get(str(req.params.uri))
    if widget is None:
        return types.ServerResult(
            types.ReadResourceResult(
                contents=[],
                _meta={"error": f"Unknown resource: {req.params.uri}"},
            )
        )

    contents = [
        types.TextResourceContents(
            uri=widget.template_uri,
            mimeType=MIME_TYPE,
            text=widget.html,
            _meta=_tool_meta(widget),
        )
    ]

    return types.ServerResult(types.ReadResourceResult(contents=contents))


async def _call_tool_request(req: types.CallToolRequest) -> types.ServerResult:
    widget = WIDGETS_BY_ID.get(req.params.name)
    if widget is None:
        return types.ServerResult(
            types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"Unknown tool: {req.params.name}",
                    )
                ],
                isError=True,
            )
        )

    arguments = req.params.arguments or {}
    
    # 📊 LOG INCOMING REQUEST
    print(f"{'='*80}")
    print(f"📥 MCP TOOL CALL: {req.params.name}")
    print(f"⏰ Timestamp: {datetime.now().isoformat()}")
    print(f"📋 Arguments: {json.dumps(arguments, indent=2)}")
    print(f"{'='*80}")
    
    # Handle care-locations tool differently
    if widget.identifier == "care-locations":
        try:
            payload = CareLocationInput.model_validate(arguments)
        except ValidationError as exc:
            return types.ServerResult(
                types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"Input validation error: {exc.errors()}",
                        )
                    ],
                    isError=True,
                )
            )
        
        # 🚨 CRITICAL: Check for ER red flags first!
        is_emergency, emergency_warning = detect_er_red_flags(payload.reason)
        if is_emergency:
            print(f"🚨 EMERGENCY DETECTED: {emergency_warning}")
            # Return emergency response - don't show urgent care locations
            structured_content = {
                "is_emergency": True,
                "emergency_warning": emergency_warning,
                "reason": payload.reason or "emergency",
                "location": payload.location or "unspecified",
                "user_coords": None,
                "locations": [],
            }
            
            # Return with emergency content
            widget_resource = _embedded_widget_resource(widget)
            meta: Dict[str, Any] = {
                "openai.com/widget": widget_resource.model_dump(mode="json"),
                "openai/outputTemplate": widget.template_uri,
                "openai/toolInvocation/invoking": widget.invoking,
                "openai/toolInvocation/invoked": widget.invoked,
                "openai/widgetAccessible": True,
                "openai/resultCanProduceWidget": True,
            }
            
            return types.ServerResult(
                types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"⚠️ EMERGENCY: {emergency_warning}. Please call 911 or go to the nearest ER immediately.",
                        )
                    ],
                    structuredContent=structured_content,
                    _meta=meta,
                )
            )
        
        # Detect service requirements (X-ray, lab, procedure room)
        service_requirements = detect_service_requirements(payload.reason)
        if service_requirements:
            print(f"🔬 Detected service requirements: {', '.join(service_requirements)}")
        
        # Fetch all locations from Providence API
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
        
        # If we have user coordinates, calculate distances and sort
        processed_locations = []
        if user_coords and all_locations:
            print(f"Processing {len(all_locations)} locations for distance sorting...")
            user_lat, user_lon = user_coords
            
            # Track seen location IDs to avoid duplicates
            seen_ids = set()
            
            for loc in all_locations:
                # Skip duplicates (some locations appear multiple times in API)
                loc_id = loc.get("id")
                if loc_id in seen_ids:
                    continue
                seen_ids.add(loc_id)
                
                # Priority 1: Check for explicit service filters (ChatGPT-specified)
                if payload.filter_services:
                    if not location_offers_services(loc, payload.filter_services):
                        # Skip locations that don't offer all requested services
                        continue
                    # If we have explicit filters, use them as the match description
                    match_description = f"Offers: {', '.join(payload.filter_services)}"
                else:
                    # Priority 2: Check if location matches the reason for visit (keyword matching)
                    matches_reason, match_description = location_matches_reason(loc, payload.reason)
                    if payload.reason and payload.reason.strip() and not matches_reason:
                        # Skip locations that don't match the reason
                        continue
                
                # Priority 3: Check if location has detected service requirements (X-ray, lab, etc.)
                if service_requirements:
                    has_all_services = all(location_has_service(loc, req) for req in service_requirements)
                    if not has_all_services:
                        # Skip locations missing required services
                        continue
                
                # Check if location is open now
                is_open, open_status = is_location_open_now(loc)
                
                coords = loc.get("coordinates")
                if coords and coords.get("lat") and coords.get("lng"):
                    distance = haversine_distance(
                        user_lat, user_lon,
                        coords["lat"], coords["lng"]
                    )
                    
                    # Create a simplified location object
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
                        "match_reason": match_description,  # User's original reason
                        "is_open_now": is_open,
                        "open_status": open_status,
                        "booking_wheelhouse": loc.get("booking_wheelhouse"),
                        "booking_department_id": loc.get("booking_department_id"),
                    }
                    processed_locations.append(processed_loc)
            
            # Sort by distance
            processed_locations.sort(key=lambda x: x["distance"])
            
            # Deduplicate by name (some locations appear twice in Providence API)
            seen_names = set()
            unique_locations = []
            for loc in processed_locations:
                if loc["name"] not in seen_names:
                    seen_names.add(loc["name"])
                    unique_locations.append(loc)
            
            processed_locations = unique_locations
            
            # Take top 7 closest
            processed_locations = processed_locations[:7]
            
            # Debug: log top 3 locations
            if processed_locations:
                if payload.reason and payload.reason.strip():
                    print(f"✅ Found {len(processed_locations)} locations matching '{payload.reason}'")
                print(f"Top 3 closest locations:")
                for loc in processed_locations[:3]:
                    match_info = f" - matches: {loc.get('match_reason')}" if loc.get('match_reason') else ""
                    print(f"  - {loc['name']}: {loc['distance']} mi{match_info}")
        else:
            # No location provided or couldn't geocode - filter by reason/services and take first matches
            for loc in all_locations:
                # Priority 1: Check for explicit service filters (ChatGPT-specified)
                if payload.filter_services:
                    if not location_offers_services(loc, payload.filter_services):
                        # Skip locations that don't offer all requested services
                        continue
                    # If we have explicit filters, use them as the match description
                    match_description = f"Offers: {', '.join(payload.filter_services)}"
                else:
                    # Priority 2: Check if location matches the reason for visit (keyword matching)
                    matches_reason, match_description = location_matches_reason(loc, payload.reason)
                    if payload.reason and payload.reason.strip() and not matches_reason:
                        # Skip locations that don't match the reason
                        continue
                
                # Priority 3: Check if location has detected service requirements (X-ray, lab, etc.)
                if service_requirements:
                    has_all_services = all(location_has_service(loc, req) for req in service_requirements)
                    if not has_all_services:
                        # Skip locations missing required services
                        continue
                
                # Check if location is open now
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
                    "match_reason": match_description,  # User's original reason
                    "is_open_now": is_open,
                    "open_status": open_status,
                    "booking_wheelhouse": loc.get("booking_wheelhouse"),
                    "booking_department_id": loc.get("booking_department_id"),
                }
                processed_locations.append(processed_loc)
                
                # Take first 7 matches
                if len(processed_locations) >= 7:
                    break
            
            # Log results
            if payload.reason and payload.reason.strip():
                print(f"✅ Found {len(processed_locations)} locations matching '{payload.reason}'")
                if processed_locations and processed_locations[0].get('match_reason'):
                    print(f"Example match: {processed_locations[0].get('match_reason')}")
        
        # Determine API base URL for widget to use
        # In production (Azure), use the deployed URL
        # In development, use localhost
        import os
        api_base_url = os.environ.get("API_BASE_URL", "https://provgpt.azurewebsites.net")
        
        structured_content = {
            "api_base_url": api_base_url,
            "reason": payload.reason or "general care",
            "location": payload.location or "unspecified",
            "user_coords": user_coords,
            "locations": processed_locations,
            "filtered_by_reason": bool(payload.reason and payload.reason.strip()),
            "service_requirements": service_requirements,
            "is_emergency": False,
        }
    else:
        # Handle pizza tools
        try:
            payload = PizzaInput.model_validate(arguments)
        except ValidationError as exc:
            return types.ServerResult(
                types.CallToolResult(
                    content=[
                        types.TextContent(
                            type="text",
                            text=f"Input validation error: {exc.errors()}",
                        )
                    ],
                    isError=True,
                )
            )
        
        structured_content = {"pizzaTopping": payload.pizza_topping}

    # For care-locations, just use the standard widget resource
    # structuredContent is automatically passed to widget via window.openai.toolOutput
    widget_uri_for_template = widget.template_uri
    
    if widget.identifier == "care-locations":
        print(f"[Widget] Returning care-locations widget")
        print(f"[Widget] structuredContent will be available via window.openai.toolOutput")
        print(f"[Widget] Location: {structured_content.get('location')}, {len(structured_content.get('locations', []))} locations")
    
    widget_resource = _embedded_widget_resource(widget)
    
    meta: Dict[str, Any] = {
        "openai.com/widget": widget_resource.model_dump(mode="json"),
        "openai/outputTemplate": widget_uri_for_template,  # ✅ Use session URI for care-locations
        "openai/toolInvocation/invoking": widget.invoking,
        "openai/toolInvocation/invoked": widget.invoked,
        "openai/widgetAccessible": True,
        "openai/resultCanProduceWidget": True,
    }

    return types.ServerResult(
        types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=widget.response_text,
                )
            ],
            structuredContent=structured_content,
            _meta=meta,
        )
    )


mcp._mcp_server.request_handlers[types.CallToolRequest] = _call_tool_request
mcp._mcp_server.request_handlers[types.ReadResourceRequest] = _handle_read_resource


app = mcp.streamable_http_app()

# Add API endpoint for widget data
from starlette.responses import JSONResponse
from starlette.routing import Route

async def get_care_locations_endpoint(request):
    """Stateless API endpoint to fetch care locations on-demand."""
    # Get query parameters
    location = request.query_params.get('location')
    reason = request.query_params.get('reason', 'general care')
    
    print(f"[API] Request for care locations - location: {location}, reason: {reason}")
    
    try:
        # Fetch all Providence locations from cache
        all_locations = await fetch_providence_locations()
        print(f"[API] Loaded {len(all_locations)} locations from cache")
        
        # Process location parameter to get coordinates
        user_coords = None
        if location and location.strip():
            user_coords = zip_to_coords(location)
            if user_coords:
                print(f"[API] Geocoded ZIP {location} to coords: {user_coords}")
            else:
                print(f"[API] Warning: Could not geocode location: {location}")
        
        # Calculate distances and sort if we have user coordinates
        processed_locations = []
        if user_coords and all_locations:
            print(f"[API] Processing {len(all_locations)} locations for distance sorting...")
            user_lat, user_lon = user_coords
            
            for loc in all_locations:
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
                    }
                    processed_locations.append(processed_loc)
            
            # Sort by distance
            processed_locations.sort(key=lambda x: x["distance"])
            
            # Take top 7 closest
            processed_locations = processed_locations[:7]
            
            # Debug: log top 3 locations
            if processed_locations:
                print(f"[API] Top 3 closest locations:")
                for loc in processed_locations[:3]:
                    print(f"  - {loc['name']}: {loc['distance']} mi")
        else:
            # No location provided - return first 7 without distances
            for loc in all_locations[:7]:
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
                }
                processed_locations.append(processed_loc)
        
        response_data = {
            "reason": reason,
            "location": location or "unspecified",
            "user_coords": user_coords,
            "locations": processed_locations,
        }
        
        print(f"[API] Returning {len(processed_locations)} locations")
        return JSONResponse(response_data)
        
    except Exception as e:
        print(f"[API] Error processing request: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            {"error": str(e), "locations": []},
            status_code=500
        )

async def get_timeslots_endpoint(request):
    """Proxy endpoint to fetch available timeslots from Providence API."""
    location_code = request.query_params.get('location_code')
    date = request.query_params.get('date')  # Optional: YYYY-MM-DD format
    
    if not location_code:
        return JSONResponse(
            {"error": "location_code parameter is required", "timeslots": []},
            status_code=400
        )
    
    print(f"[Timeslots API] Fetching slots for location: {location_code}, date: {date or 'next 7 days'}")
    
    try:
        # Build Providence API URL
        url = f"https://providencekyruus.azurewebsites.net/api/getprovinnovatetimeslots?location_code={location_code}"
        
        # Add optional date parameters if provided
        if date:
            # Providence API might use start_date/end_date params
            url += f"&start_date={date}"
        
        # Fetch timeslots from Providence API
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Check if API returned error
            if not data.get("success", True):
                error_msg = data.get("error", "Unknown error")
                print(f"[Timeslots API] Providence API error: {error_msg}")
                return JSONResponse({
                    "success": False,
                    "error": error_msg,
                    "timeslots": [],
                    "location_code": location_code
                })
            
            # Extract timeslots data
            timeslots_data = data.get("timeslots", {})
            dates = timeslots_data.get("dates", [])
            
            print(f"[Timeslots API] Found {len(dates)} dates with available slots")
            
            # Return the full structure - frontend can work with dates directly
            return JSONResponse({
                "success": True,
                "location_code": location_code,
                "dates": dates,  # Array of date objects with times
                "num_dates": timeslots_data.get("num_dates", len(dates)),
                "phone_number": data.get("phone_number"),
                "phone_number_formatted": data.get("phone_number_formatted"),
            })
    
    except httpx.HTTPStatusError as e:
        print(f"[Timeslots API] HTTP error: {e.response.status_code}")
        return JSONResponse({
            "success": False,
            "error": f"Providence API returned error: {e.response.status_code}",
            "timeslots": [],
            "location_code": location_code
        }, status_code=e.response.status_code)
    
    except httpx.TimeoutException:
        print(f"[Timeslots API] Request timed out")
        return JSONResponse({
            "success": False,
            "error": "Request to Providence API timed out",
            "timeslots": [],
            "location_code": location_code
        }, status_code=504)
    
    except Exception as e:
        print(f"[Timeslots API] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({
            "success": False,
            "error": str(e),
            "timeslots": [],
            "location_code": location_code
        }, status_code=500)


# Add the routes to the app
app.routes.insert(0, Route('/api/care-locations', get_care_locations_endpoint))
app.routes.insert(0, Route('/api/timeslots', get_timeslots_endpoint))

# Mount static files for widget assets
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

# Mount static files (logos, images, etc.)
STATIC_DIR = Path(__file__).parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

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

    uvicorn.run("main:app", host="0.0.0.0", port=8000)
