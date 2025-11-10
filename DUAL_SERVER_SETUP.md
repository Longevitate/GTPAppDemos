# Dual MCP Server Setup

This repository now hosts **two separate MCP servers** on the same web app instance:

1. **Main MCP Server** (UI-enabled) at `/mcp`
2. **Text-Only MCP Server** (markdown output) at `/textOnly/mcp`

## 🏗️ Architecture Overview

```
Providence Care MCP Application
│
├─ Master App (master_app.py)
│   ├─ Routes both MCP servers
│   ├─ Serves shared API endpoints
│   └─ Handles static file serving
│
├─ Main MCP Server (/mcp)
│   ├─ Custom React UI widgets
│   ├─ Interactive booking
│   ├─ Real-time timeslots
│   └─ Emergency detection
│
├─ Text-Only MCP Server (/textOnly/mcp)
│   ├─ Markdown formatted text
│   ├─ No custom UI
│   ├─ Same backend logic
│   └─ Emergency detection
│
└─ Shared Utilities
    ├─ Location data & caching
    ├─ Emergency detection (ER red flags)
    ├─ Service filtering
    └─ Geocoding & distance calculations
```

## 📍 Server Endpoints

### Main MCP Server (UI-Enabled)

**Base URL:** `https://provgpt.azurewebsites.net/mcp`

- **Features:**
  - Full custom UI with React components
  - Interactive map and location cards
  - Real-time appointment booking
  - Timeslot display and booking
  - Emergency warning banners
  
- **Tool:** `care-locations`
- **Output:** Custom React UI widget with location cards, booking buttons, and timeslots

### Text-Only MCP Server

**Base URL:** `https://provgpt.azurewebsites.net/textOnly/mcp`

- **Features:**
  - Markdown-formatted text output
  - No custom UI rendering
  - Same backend logic and filtering
  - Emergency detection and warnings
  - Accessibility-focused
  
- **Tool:** `care-locations-text`
- **Output:** Formatted markdown text with location details

## 🔄 Shared Functionality

Both servers share the following capabilities:

### 1. Emergency Detection
- Detects life-threatening symptoms (chest pain, difficulty breathing, stroke, etc.)
- Returns immediate warnings to call 911
- Mental health crisis detection (988 Suicide & Crisis Lifeline)

### 2. Location Filtering
- Filter by user's reason for visit
- Service matching (X-ray, labs, procedures)
- Distance-based sorting when ZIP code provided
- Open/closed status checking

### 3. Geocoding
- ZIP code to coordinates conversion
- Haversine distance calculations
- Cached location data for fast responses

## 📝 Usage Examples

### ChatGPT Integration

#### Using the Main Server (UI)
1. Go to ChatGPT Settings > Connectors
2. Add connector: `https://provgpt.azurewebsites.net/mcp`
3. In chat, say: "Show me urgent care near 97202"
4. Result: Interactive UI with booking buttons

#### Using the Text-Only Server
1. Go to ChatGPT Settings > Connectors
2. Add connector: `https://provgpt.azurewebsites.net/textOnly/mcp`
3. In chat, say: "Show me urgent care near 97202"
4. Result: Formatted text list with location details

### API Endpoints (Shared)

Both servers can use these shared endpoints:

```bash
# Get care locations
GET https://provgpt.azurewebsites.net/api/care-locations?location=97202&reason=flu

# Get timeslots for booking
GET https://provgpt.azurewebsites.net/api/timeslots?location_code=providence-express-care-hollywood

# Health check
GET https://provgpt.azurewebsites.net/health
```

## 🚀 Deployment

The application is deployed as a single Docker container that hosts both servers:

```dockerfile
# Dockerfile uses master_app.py as entry point
CMD uvicorn pizzaz_server_python.master_app:app --host 0.0.0.0 --port $PORT
```

### Environment Variables

```bash
PORT=8080                                    # Azure Web App port
BASE_URL=https://provgpt.azurewebsites.net  # Base URL for widget assets
API_BASE_URL=https://provgpt.azurewebsites.net  # API endpoint base
```

## 🧪 Local Development

### Running Both Servers Locally

```bash
# Install dependencies
pnpm install
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r pizzaz_server_python/requirements.txt

# Build widget assets
pnpm run build

# Start both servers
cd pizzaz_server_python
python master_app.py
```

This will start both servers on `http://localhost:8000`:
- Main MCP: `http://localhost:8000/mcp`
- Text-Only MCP: `http://localhost:8000/textOnly/mcp`

### Testing with ngrok

```bash
# Expose local server to internet
ngrok http 8000

# Use ngrok URLs in ChatGPT:
# Main: https://your-id.ngrok-free.app/mcp
# Text-Only: https://your-id.ngrok-free.app/textOnly/mcp
```

## 📦 File Structure

```
pizzaz_server_python/
├── main.py                    # Main MCP server (UI-enabled)
├── text_only_server.py        # Text-only MCP server
├── master_app.py              # Master app that mounts both servers
├── shared/                    # Shared utilities
│   ├── __init__.py
│   ├── emergency_detection.py # ER red flag detection
│   ├── service_detection.py   # Service requirement detection
│   ├── locations.py           # Location management
│   └── geocoding.py           # ZIP code & distance utils
├── providence_locations_cache.json  # Cached location data
└── zip_coords_cache.json      # Cached ZIP coordinates
```

## 🔍 Key Differences Between Servers

| Feature | Main Server | Text-Only Server |
|---------|-------------|------------------|
| **Endpoint** | `/mcp` | `/textOnly/mcp` |
| **Tool Name** | `care-locations` | `care-locations-text` |
| **Output** | React UI Widget | Markdown Text |
| **Booking UI** | ✅ Interactive buttons | 🔗 Links only |
| **Timeslots** | ✅ Real-time display | 🔗 Link to book |
| **Emergency** | ✅ Banner UI | ⚠️ Text warning |
| **Accessibility** | Widget-dependent | ✅ Screen reader friendly |
| **Use Case** | Rich interactive UX | API integrations, accessibility |

## 🛠️ Maintenance

### Adding New Features

To add features that should be shared:
1. Add logic to `shared/` modules
2. Update both `main.py` and `text_only_server.py` to use it
3. Test both servers independently

### Updating Emergency Detection

Edit `shared/emergency_detection.py`:
```python
red_flags = [
    (["new symptom", "keyword"], "warning message"),
    ...
]
```

Both servers will automatically use the updated logic.

### Updating Location Filtering

Edit `shared/locations.py` to modify:
- `location_matches_reason()` - Service matching logic
- `is_location_open_now()` - Hours parsing
- `location_has_service()` - Service availability

## 🐛 Troubleshooting

### Issue: Only one server works

**Solution:** Check `master_app.py` mounts:
```python
Mount("/mcp", app=main_mcp_app),
Mount("/textOnly/mcp", app=text_only_mcp_app),
```

### Issue: Import errors from shared modules

**Solution:** Ensure you're running from the parent directory:
```bash
cd openai-apps-sdk-examples
python -m pizzaz_server_python.master_app
```

### Issue: Widgets not loading in main server

**Solution:** Rebuild assets:
```bash
pnpm run build
```

### Issue: Emergency detection not working

**Solution:** Check shared utilities import:
```python
from shared import detect_er_red_flags
```

## 📚 Additional Resources

- [Apps SDK Documentation](https://platform.openai.com/docs/guides/apps)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [Main README](./README.md)
- [Azure Deployment Guide](./AZURE_DEPLOYMENT.md)

## 🎯 Future Enhancements

Potential additions to the dual-server architecture:

- [ ] Add third server for JSON API responses
- [ ] Add WebSocket support for real-time updates
- [ ] Add authentication/authorization layer
- [ ] Add rate limiting per server
- [ ] Add separate caching strategies per server
- [ ] Add server-specific analytics

