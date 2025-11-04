# Widget Data Passing Issue

## Current Status

### ✅ What's Working
- **Server-side sorting**: Correctly calculates distances and sorts locations (Everett at 49.8 mi first for ZIP 98229)
- **MCP Response**: Returns correct data in `structuredContent`
- **Cache system**: 76 locations and 41K ZIP codes cached and working
- **No-args error**: Fixed (empty args no longer throw error)

### ❌ What's NOT Working
- **Widget data injection**: Widget shows fallback `locations.json` instead of server data
- **Console shows**: `window.__WIDGET_DATA__: undefined`
- **UI shows**: Portland locations (from fallback) instead of sorted Everett locations

---

## Root Cause

**ChatGPT's widget architecture loads widgets from static asset URLs**, not from the modified HTML we return in the MCP response.

**The Flow:**
1. ✅ Server returns MCP response with `structuredContent: {locations: [...]}`
2. ✅ Server modifies HTML to inject `window.__WIDGET_DATA__`
3. ❌ ChatGPT **ignores modified HTML**, fetches widget from `http://localhost:4444/care-list-2d2b.html`
4. ❌ Widget loads **WITHOUT** injected data
5. ❌ Widget falls back to hardcoded `locations.json`

**The widget iframe is sandboxed and has no access to the MCP response's `structuredContent`.**

---

## Attempted Solutions

### 1. HTML Injection ❌
**Tried:** Injecting `<script>window.__WIDGET_DATA__ = {...}</script>` into HTML  
**Result:** HTML modifications ignored by ChatGPT  
**Why failed:** ChatGPT fetches widget from assets URL directly

### 2. URL Parameters ❌ (Probably)
**Tried:** Encoding data as base64 in widget URI query params  
**Result:** TBD after deployment  
**Likelihood:** Low - ChatGPT probably doesn't pass URI params to widget

### 3. PostMessage ❌ (Probably)
**Tried:** Widget sends `widget-ready`, listens for parent response  
**Result:** TBD after deployment  
**Likelihood:** Low - ChatGPT's parent window likely doesn't relay MCP data

---

## Proposed Solutions

### Solution A: API Endpoint (Most Reliable)

**Create an endpoint that serves the data:**

```python
# Store session data server-side
session_data = {}

@app.get("/widget-data/{session_id}")
async def get_widget_data(session_id: str):
    return session_data.get(session_id, {"locations": []})

# In tool handler:
session_id = str(uuid.uuid4())
session_data[session_id] = structured_content
widget_uri_with_session = f"{widget.template_uri}?session={session_id}"
```

**Widget fetches on load:**
```javascript
const params = new URLSearchParams(window.location.search);
const sessionId = params.get('session');
fetch(`/widget-data/${sessionId}`)
  .then(r => r.json())
  .then(data => setLocations(data.locations));
```

**Pros:**
- ✅ Reliable - not dependent on ChatGPT's widget system
- ✅ Works with any data size
- ✅ Standard REST pattern

**Cons:**
- Need session management
- Need cleanup/expiry
- Extra network request

---

### Solution B: Static HTML with JavaScript (Simpler)

**Return complete HTML instead of using template URI:**

Instead of returning a `templateUri`, return the full HTML with data embedded in the MCP response.

**Changes needed:**
1. Don't use `outputTemplate` metadata
2. Return full HTML in response content
3. Embed data directly in HTML

**Pros:**
- ✅ No session management
- ✅ No extra endpoints
- ✅ Data guaranteed to be in HTML

**Cons:**
- Might not work with ChatGPT's widget system
- Large response size
- Need to test if ChatGPT supports this

---

### Solution C: Ask OpenAI for Guidance

**The ChatGPT Apps SDK might have a standard way to pass dynamic data to widgets that we're missing.**

Consult:
- ChatGPT Apps SDK documentation
- MCP specification for widget metadata
- OpenAI developer forums/support

---

## Recommendation

**Implement Solution A (API Endpoint)** because:

1. **It will definitely work** - not dependent on ChatGPT internals
2. **Clean separation** - server provides data, widget fetches it
3. **Scalable** - can add features like real-time updates later
4. **Standard pattern** - familiar to web developers

---

## Implementation Plan for Solution A

### Step 1: Add Session Storage
```python
import uuid
from datetime import datetime, timedelta

# Simple in-memory store (use Redis in production)
widget_sessions = {}

def store_widget_data(data: dict, ttl_minutes: int = 10) -> str:
    session_id = str(uuid.uuid4())
    expires = datetime.now() + timedelta(minutes=ttl_minutes)
    widget_sessions[session_id] = {
        "data": data,
        "expires": expires
    }
    return session_id

def get_widget_data(session_id: str) -> dict | None:
    session = widget_sessions.get(session_id)
    if session and session["expires"] > datetime.now():
        return session["data"]
    return None
```

### Step 2: Add API Endpoint
```python
@app.get("/api/widget-data/{session_id}")
async def widget_data_endpoint(session_id: str):
    data = get_widget_data(session_id)
    if data:
        return data
    return {"error": "Session not found or expired"}, 404
```

### Step 3: Modify Tool Handler
```python
if widget.identifier == "care-locations":
    # Store data with session ID
    session_id = store_widget_data(structured_content)
    
    # Modify widget URI to include session
    widget_uri_with_session = f"{widget.template_uri}?session={session_id}"
    
    # Use modified URI
    widget_resource = types.EmbeddedResource(...)
```

### Step 4: Update Widget to Fetch
```javascript
useEffect(() => {
  const params = new URLSearchParams(window.location.search);
  const sessionId = params.get('session');
  
  if (sessionId) {
    fetch(`/api/widget-data/${sessionId}`)
      .then(r => r.json())
      .then(data => {
        if (data.locations) {
          console.log('[Care Widget] Fetched locations from API');
          setLocations(data.locations);
        }
      })
      .catch(err => {
        console.error('[Care Widget] Failed to fetch data:', err);
        setLocations(locationsData.locations);  // Fallback
      });
  } else {
    setLocations(locationsData.locations);  // No session, use fallback
  }
}, []);
```

---

## Next Steps

1. **Deploy current changes** - Test if URL params or postMessage works
2. **Check logs** - See what's actually happening
3. **If still not working** - Implement Solution A (API endpoint)
4. **Test** - Verify sorted locations appear in UI

---

## Testing Checklist

After implementing solution:

- [ ] Widget loads without errors
- [ ] Console shows data fetch/receive
- [ ] First location is Everett (not Portland)
- [ ] Distances show in UI (49.8 mi, etc.)
- [ ] Locations sorted by distance
- [ ] Works with different ZIP codes
- [ ] Fallback works if no ZIP provided

---

**Current Commit:** `30da0c9`  
**Status:** Debugging data passing, server logic confirmed working

