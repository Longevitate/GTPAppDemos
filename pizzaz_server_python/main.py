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


# ZIP code to lat/lon lookup for common WA, OR, CA areas
ZIP_TO_COORDS: Dict[str, tuple[float, float]] = {
    # Washington
    "98229": (48.7519, -122.4787),  # Bellingham
    "98101": (47.6080, -122.3350),  # Seattle Downtown
    "98112": (47.6239, -122.3190),  # Seattle Capitol Hill
    "98004": (47.6214, -122.2079),  # Bellevue
    "98201": (47.9790, -122.2021),  # Everett
    "98516": (47.0379, -122.8132),  # Lacey/Olympia
    "99201": (47.6588, -117.4260),  # Spokane
    # Oregon
    "97203": (45.5898, -122.7375),  # Portland North
    "97211": (45.5698, -122.6501),  # Portland NE
    "97086": (45.4312, -122.7637),  # Happy Valley
    "97013": (45.2629, -122.6774),  # Canby
    "97301": (44.9429, -123.0351),  # Salem
    "97401": (44.0521, -123.0868),  # Eugene
    # California
    "92868": (33.7879, -117.8531),  # Orange
    "92629": (33.6095, -117.7288),  # Dana Point
    "92677": (33.5272, -117.7132),  # Laguna Niguel
    "90001": (33.9731, -118.2479),  # Los Angeles
    "94102": (37.7799, -122.4193),  # San Francisco
}


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
    """Convert a ZIP code to lat/lon coordinates."""
    # Clean the ZIP code (remove any extra characters)
    clean_zip = zip_code.strip().split('-')[0][:5]
    return ZIP_TO_COORDS.get(clean_zip)


async def fetch_providence_locations() -> List[Dict[str, Any]]:
    """Fetch all Providence care locations from the API."""
    url = "https://providencekyruus.azurewebsites.net/api/searchlocationsbyservices"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            return data.get("locations", [])
    except Exception as e:
        print(f"Error fetching Providence locations: {e}")
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
        default=None,
        description="Reason for seeking care (optional).",
    )
    location: str | None = Field(
        default=None,
        description="User location or ZIP code (optional).",
    )

    model_config = ConfigDict(populate_by_name=True, extra="forbid")


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
        if payload.location:
            user_coords = zip_to_coords(payload.location)
        
        # If we have user coordinates, calculate distances and sort
        processed_locations = []
        if user_coords and all_locations:
            user_lat, user_lon = user_coords
            
            for loc in all_locations:
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

    # For care-locations, inject the data into the HTML
    if widget.identifier == "care-locations" and "locations" in structured_content:
        import json
        data_script = f"""
        <script>
        window.__WIDGET_DATA__ = {json.dumps(structured_content)};
        </script>
        """
        modified_html = widget.html.replace("</head>", f"{data_script}</head>")
        
        # Create a modified widget resource with injected data
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
