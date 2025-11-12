"""Master application that routes to multiple FastMCP servers.

This implements a custom router that manually rewrites paths before delegating
to the appropriate FastMCP app, avoiding Starlette Mount's trailing slash issues.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.staticfiles import StaticFiles


async def health_check(request):
    """Health check endpoint."""
    return JSONResponse({
        "status": "healthy",
        "servers": {
            "main_mcp": "/mcp",
            "text_only_mcp": "/textOnly/mcp"
        },
        "version": "2.0.0"
    })


async def root_info(request):
    """Root endpoint with server information."""
    return JSONResponse({
        "message": "Providence Care MCP Servers",
        "version": "2.0.0",
        "servers": [
            {
                "name": "Main MCP Server (UI-enabled)",
                "path": "/mcp",
                "tool": "care-locations"
            },
            {
                "name": "Text-Only MCP Server",
                "path": "/textOnly/mcp",
                "tool": "care-locations-text"
            }
        ]
    })


# Import API endpoints
def get_api_endpoints():
    """Lazy import of API endpoints."""
    from .main import get_care_locations_endpoint, get_timeslots_endpoint
    return get_care_locations_endpoint, get_timeslots_endpoint


# Static file paths
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


# Custom router for MCP apps
class MCPMultiRouter:
    """Routes requests to multiple FastMCP apps with path rewriting."""
    
    def __init__(self):
        self.main_app = None
        self.text_only_app = None
    
    def initialize_apps(self):
        """Initialize both MCP apps."""
        print("[Router] Initializing main MCP app...")
        from .main import app as main_app
        self.main_app = main_app
        
        print("[Router] Initializing text-only MCP app...")
        from .text_only_server import app as text_only_app
        self.text_only_app = text_only_app
        
        print("[Router] Both MCP apps initialized")
    
    async def __call__(self, scope, receive, send):
        """Route requests to appropriate MCP app with path rewriting."""
        
        # Handle lifespan events - pass to both apps
        if scope["type"] == "lifespan":
            # Let Starlette handle lifespan for the main app
            return
        
        if scope["type"] != "http":
            return
        
        path = scope["path"]
        
        # Route to text-only server: /textOnly/mcp -> rewrite to /mcp
        if path.startswith("/textOnly/mcp"):
            # Create new scope with rewritten path
            new_scope = dict(scope)
            # /textOnly/mcp → /mcp
            # /textOnly/mcp/messages → /mcp/messages
            new_path = "/mcp" + path[13:]  # len("/textOnly/mcp") = 13
            new_scope["path"] = new_path
            new_scope["raw_path"] = new_path.encode()
            
            await self.text_only_app(new_scope, receive, send)
            return
        
        # Route to main server: pass through as-is
        if path.startswith("/mcp"):
            await self.main_app(scope, receive, send)
            return
        
        # No match - 404
        await send({
            "type": "http.response.start",
            "status": 404,
            "headers": [[b"content-type", b"text/plain"]],
        })
        await send({
            "type": "http.response.body",
            "body": b"Not Found - Use /mcp or /textOnly/mcp",
        })


# Global router instance
mcp_router = MCPMultiRouter()


# Lifespan manager
@asynccontextmanager
async def lifespan(app):
    """Manage app lifecycle - initialize MCP apps and trigger their lifespans."""
    # Startup
    print("[Lifespan] Starting up...")
    mcp_router.initialize_apps()
    
    # Manually trigger lifespan startup for each MCP app
    print("[Lifespan] Triggering MCP app lifespans...")
    
    # Create fake lifespan scopes and trigger startup
    import anyio
    
    # Start main app lifespan
    main_startup_complete = anyio.Event()
    main_shutdown_complete = anyio.Event()
    
    async def main_app_lifespan():
        startup_sent = False
        
        async def receive():
            nonlocal startup_sent
            if not startup_sent:
                startup_sent = True
                return {"type": "lifespan.startup"}
            else:
                await main_startup_complete.wait()
                return {"type": "lifespan.shutdown"}
        
        async def send(message):
            if message["type"] == "lifespan.startup.complete":
                print("[Lifespan] Main app startup complete")
            elif message["type"] == "lifespan.shutdown.complete":
                main_shutdown_complete.set()
        
        await mcp_router.main_app({"type": "lifespan", "asgi": {"version": "3.0"}}, receive, send)
    
    # Start text-only app lifespan
    text_startup_complete = anyio.Event()
    text_shutdown_complete = anyio.Event()
    
    async def text_app_lifespan():
        startup_sent = False
        
        async def receive():
            nonlocal startup_sent
            if not startup_sent:
                startup_sent = True
                return {"type": "lifespan.startup"}
            else:
                await text_startup_complete.wait()
                return {"type": "lifespan.shutdown"}
        
        async def send(message):
            if message["type"] == "lifespan.startup.complete":
                print("[Lifespan] Text-only app startup complete")
            elif message["type"] == "lifespan.shutdown.complete":
                text_shutdown_complete.set()
        
        await mcp_router.text_only_app({"type": "lifespan", "asgi": {"version": "3.0"}}, receive, send)
    
    # Run both lifespans in the background
    async with anyio.create_task_group() as tg:
        tg.start_soon(main_app_lifespan)
        tg.start_soon(text_app_lifespan)
        
        # Wait a moment for startup
        await anyio.sleep(0.1)
        
        print("[Lifespan] Master startup complete")
        
        yield
        
        # Shutdown - trigger shutdown for both apps
        print("[Lifespan] Shutting down...")
        main_startup_complete.set()
        text_startup_complete.set()
        
        # Wait for both to complete shutdown
        await main_shutdown_complete.wait()
        await text_shutdown_complete.wait()


# Get API endpoints
care_locations_endpoint, timeslots_endpoint = get_api_endpoints()


# Create main Starlette app
app = Starlette(
    debug=False,
    lifespan=lifespan,
    routes=[
        Route("/", root_info),
        Route("/health", health_check),
        Route("/api/care-locations", care_locations_endpoint),
        Route("/api/timeslots", timeslots_endpoint),
    ],
)

# Add static files
if ASSETS_DIR.exists():
    from starlette.routing import Mount
    app.routes.append(Mount("/assets", app=StaticFiles(directory=str(ASSETS_DIR)), name="assets"))

if STATIC_DIR.exists():
    from starlette.routing import Mount
    app.routes.append(Mount("/static", app=StaticFiles(directory=str(STATIC_DIR)), name="static"))


# Wrap everything with the MCP router
class MasterApp:
    """Master ASGI app that routes between static content and MCP servers."""
    
    def __init__(self, static_app, mcp_router):
        self.static_app = static_app
        self.mcp_router = mcp_router
    
    async def __call__(self, scope, receive, send):
        """Route to MCP apps or static content."""
        
        # Pass lifespan events to static app
        if scope["type"] == "lifespan":
            await self.static_app(scope, receive, send)
            return
        
        path = scope.get("path", "")
        
        # Route MCP requests to MCP router
        if path.startswith("/mcp") or path.startswith("/textOnly/mcp"):
            await self.mcp_router(scope, receive, send)
        else:
            # Route everything else to static/API app
            await self.static_app(scope, receive, send)


# Create final app with CORS
master = MasterApp(app, mcp_router)

# Wrap with CORS
app = CORSMiddleware(
    master,
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
    
    uvicorn.run("pizzaz_server_python.master_app:app", host="0.0.0.0", port=8000, reload=False)
