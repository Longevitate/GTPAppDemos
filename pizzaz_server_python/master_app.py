"""Master application that hosts multiple MCP servers.

This app mounts two separate MCP servers:
1. Main server (with custom UI widgets) at /mcp
2. Text-only server (markdown output) at /textOnly/mcp

Both servers share common utilities and can run simultaneously on the same port.
"""

from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

# Import the main MCP server app (with widgets)
from pizzaz_server_python.main import app as main_mcp_app
from pizzaz_server_python.main import (
    get_care_locations_endpoint,
    get_timeslots_endpoint,
)

# Import the text-only MCP server app
from pizzaz_server_python.text_only_server import app as text_only_mcp_app


async def health_check(request):
    """Health check endpoint for Azure."""
    return JSONResponse({
        "status": "healthy",
        "servers": {
            "main_mcp": "/mcp",
            "text_only_mcp": "/textOnly/mcp"
        }
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
                "description": "Full-featured server with custom UI widgets for care locations",
                "features": [
                    "Custom React UI components",
                    "Interactive booking",
                    "Real-time timeslots",
                    "Emergency detection",
                    "Location filtering"
                ]
            },
            {
                "name": "Text-Only MCP Server",
                "path": "/textOnly/mcp",
                "description": "Text-only server with markdown-formatted output",
                "features": [
                    "Markdown formatted text",
                    "No custom UI",
                    "Same backend logic",
                    "Emergency detection",
                    "Location filtering"
                ]
            }
        ],
        "api_endpoints": [
            "/api/care-locations",
            "/api/timeslots",
            "/health"
        ]
    })


# Define paths for static files
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# Create the master application
app = Starlette(
    debug=False,
    routes=[
        # Root info endpoint
        Route("/", root_info),
        
        # Health check
        Route("/health", health_check),
        
        # Shared API endpoints (used by both servers' widgets)
        Route("/api/care-locations", get_care_locations_endpoint),
        Route("/api/timeslots", get_timeslots_endpoint),
        
        # Mount main MCP server at /mcp
        Mount("/mcp", app=main_mcp_app),
        
        # Mount text-only MCP server at /textOnly/mcp
        Mount("/textOnly/mcp", app=text_only_mcp_app),
        
        # Static file serving
        Mount("/assets", app=StaticFiles(directory=str(ASSETS_DIR)), name="assets"),
    ],
)

# Add static files mount if directory exists
if STATIC_DIR.exists():
    app.routes.append(
        Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static")
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
    
    print("🚀 Starting Providence Care MCP Servers")
    print("=" * 60)
    print("📍 Main Server (UI):      http://localhost:8000/mcp")
    print("📍 Text-Only Server:      http://localhost:8000/textOnly/mcp")
    print("=" * 60)
    print("🔧 API Endpoints:")
    print("   - /api/care-locations")
    print("   - /api/timeslots")
    print("   - /health")
    print("=" * 60)
    
    uvicorn.run("master_app:app", host="0.0.0.0", port=8000, reload=True)

