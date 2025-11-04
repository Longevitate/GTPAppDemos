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


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance in miles between two points on Earth."""
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


def zip_to_coords(zip_code: str) -> tuple[float, float] | None:
    """Convert a ZIP code to lat/lon coordinates using cached data."""
    clean_zip = zip_code.strip().split('-')[0][:5]
    zip_coords = _load_zip_coords()
    return zip_coords.get(clean_zip)


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
        description="Reason for seeking care (optional).",
    )
    location: str | None = Field(
        default="",
        description="User location or ZIP code (optional).",
    )

    model_config = ConfigDict(populate_by_name=True, extra="allow")


# No session storage needed - stateless architecture!
# Widget will call API with arguments passed via meta tags

mcp = FastMCP(
    name="pizzaz-python",
    stateless_http=True,
)


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


@mcp._mcp_server.list_tools()
async def _list_tools() -> List[types.Tool]:
    return [
        types.Tool(
            name=widget.identifier,
            title=widget.title,
            description=widget.title,
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
        
        # Fetch all locations from Providence API
        all_locations = await fetch_providence_locations()
        
        # Process location parameter
        user_coords = None
        if payload.location and payload.location.strip():
            user_coords = zip_to_coords(payload.location)
            if user_coords:
                print(f"Geocoded ZIP {payload.location} to coords: {user_coords}")
            else:
                print(f"Warning: Could not geocode ZIP {payload.location}")
        
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
                    }
                    processed_locations.append(processed_loc)
            
            # Sort by distance
            processed_locations.sort(key=lambda x: x["distance"])
            
            # Take top 7 closest
            processed_locations = processed_locations[:7]
            
            # Debug: log top 3 locations
            if processed_locations:
                print(f"Top 3 closest locations:")
                for loc in processed_locations[:3]:
                    print(f"  - {loc['name']}: {loc['distance']} mi")
        else:
            # No location provided or couldn't geocode - use first 7 locations as-is
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
        
        structured_content = {
            "reason": payload.reason or "general care",
            "location": payload.location or "unspecified",
            "user_coords": user_coords,
            "locations": processed_locations,
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

    # For care-locations, inject arguments as meta tags so widget can fetch fresh data
    widget_uri_for_template = widget.template_uri  # Default to base URI
    
    if widget.identifier == "care-locations":
        print(f"[Widget] Injecting arguments into widget HTML")
        
        # Get the user's location and reason from the processed data
        user_location = structured_content.get("location", "")
        user_reason = structured_content.get("reason", "")
        
        print(f"[Widget] User location: {user_location}, reason: {user_reason}")
        
        # Inject arguments as meta tags so widget can call API
        meta_tags = []
        if user_location:
            meta_tags.append(f'<meta name="care-location" content="{user_location}">')
        if user_reason:
            meta_tags.append(f'<meta name="care-reason" content="{user_reason}">')
        
        modified_html = widget.html.replace(
            '<head>',
            f'<head>\n{chr(10).join(meta_tags)}'
        )
        
        print(f"[Widget] Injected {len(meta_tags)} meta tags into HTML")
        
        # Create widget resource with modified HTML
        widget_resource = types.EmbeddedResource(
            type="resource",
            resource=types.TextResourceContents(
                uri=widget.template_uri,
                mimeType=MIME_TYPE,
                text=modified_html,
                title=widget.title,
            ),
        )
    else:
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

# Add the route to the app
app.routes.insert(0, Route('/api/care-locations', get_care_locations_endpoint))

# Mount static files for widget assets
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

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
