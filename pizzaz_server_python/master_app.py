"""Master application that hosts multiple MCP servers.

This app routes requests to different MCP servers based on the path:
- /mcp -> Main MCP server (UI-enabled with custom widgets)
- /textOnly/mcp -> Text-only MCP server (markdown output)

Both servers share API endpoints and static files from the root level.
"""

from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles


async def health_check(request):
    """Health check endpoint for Azure."""
    return JSONResponse({
        "status": "healthy",
        "servers": {
            "main_mcp": "/mcp",
            "text_only_mcp": "/textOnly/mcp"
        },
        "version": "2.0.0"
    })


async def root_info(request):
    """Root endpoint with information about available servers."""
    return JSONResponse({
        "message": "Providence Care MCP Servers",
        "version": "2.0.0",
        "servers": [
            {
                "name": "Main MCP Server (UI-enabled)",
                "path": "/mcp",
                "description": "Full-featured server with custom UI widgets",
                "tool": "care-locations"
            },
            {
                "name": "Text-Only MCP Server",
                "path": "/textOnly/mcp",
                "description": "Text-only server with markdown output",
                "tool": "care-locations-text"
            }
        ],
        "api_endpoints": [
            "/api/care-locations",
            "/api/timeslots",
            "/health"
        ]
    })


# Import API endpoints from main server (these are just functions, safe to import)
def get_api_endpoints():
    """Lazy import of API endpoints to avoid circular imports."""
    from .main import get_care_locations_endpoint, get_timeslots_endpoint
    return get_care_locations_endpoint, get_timeslots_endpoint


# Lazy-loaded app references
_main_app = None
_text_only_app = None


def get_main_app():
    """Get the main MCP app (with UI widgets) - lazy loaded."""
    global _main_app
    if _main_app is None:
        from .main import app
        _main_app = app
    return _main_app


def get_text_only_app():
    """Get the text-only MCP app - lazy loaded."""
    global _text_only_app
    if _text_only_app is None:
        from .text_only_server import app
        _text_only_app = app
    return _text_only_app


# Wrapper apps that lazily load the real apps
class LazyMainApp:
    """Wrapper that lazily loads the main app on first request."""
    
    async def __call__(self, scope, receive, send):
        app = get_main_app()
        await app(scope, receive, send)


class LazyTextOnlyApp:
    """Wrapper that lazily loads the text-only app on first request."""
    
    async def __call__(self, scope, receive, send):
        app = get_text_only_app()
        await app(scope, receive, send)


# Define paths for static files
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# Get API endpoints
care_locations_endpoint, timeslots_endpoint = get_api_endpoints()

# Create routes list
routes = [
    # Root info endpoint
    Route("/", root_info),
    
    # Health check
    Route("/health", health_check),
    
    # API endpoints (shared by both servers)
    Route("/api/care-locations", care_locations_endpoint),
    Route("/api/timeslots", timeslots_endpoint),
    
    # Static file serving
    Mount("/assets", app=StaticFiles(directory=str(ASSETS_DIR)), name="assets"),
]

# Add static files mount if directory exists
if STATIC_DIR.exists():
    routes.append(
        Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static")
    )

# Mount the MCP servers with lazy loading wrappers
routes.extend([
    Mount("/mcp", app=LazyMainApp()),
    Mount("/textOnly/mcp", app=LazyTextOnlyApp()),
])

# Create the master application
app = Starlette(
    debug=False,
    routes=routes,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("🚀 Providence Care MCP Servers")
    print("=" * 60)
    print("📍 Main Server (UI):      http://localhost:8000/mcp")
    print("📍 Text-Only Server:      http://localhost:8000/textOnly/mcp")
    print("=" * 60)
    print("🔧 API Endpoints:")
    print("   - /api/care-locations")
    print("   - /api/timeslots")
    print("   - /health")
    print("=" * 60)
    
    uvicorn.run("pizzaz_server_python.master_app:app", host="0.0.0.0", port=8000, reload=True)

