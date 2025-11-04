# Fix: Added care-locations to Python MCP Server

## Problem
The `care-locations` tool was only added to the Node.js MCP server, but Azure deploys the **Python MCP server**. This is why you only saw the 4 pizza tools (pizza-map, pizza-list, pizza-carousel, pizza-albums) and the care-locations tool was missing.

## Root Cause
The Dockerfile (line 46) runs the Python server:
```dockerfile
uvicorn pizzaz_server_python.main:app --host 0.0.0.0 --port $PORT
```

We had modified `pizzaz_server_node/src/server.ts` but Azure never ran it!

## Solution Applied

Updated `pizzaz_server_python/main.py` with the following changes:

### 1. Added care-locations widget (line 91-99)
```python
PizzazWidget(
    identifier="care-locations",
    title="Show Care Locations",
    template_uri="ui://widget/care-list.html",
    invoking="Finding care locations",
    invoked="Found care locations",
    html=_load_widget_html("care-list"),
    response_text="Showing Providence care locations!",
),
```

### 2. Created CareLocationInput model (line 126-138)
```python
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
```

### 3. Added care location input schema (line 159-173)
```python
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
```

### 4. Updated tool list generation (line 202-223)
Modified `_list_tools()` to use the correct schema based on widget type:
```python
inputSchema=deepcopy(
    CARE_LOCATION_INPUT_SCHEMA 
    if widget.identifier == "care-locations" 
    else TOOL_INPUT_SCHEMA
)
```

### 5. Updated tool call handler (line 278-356)
Modified `_call_tool_request()` to handle both tool types:
- Uses `CareLocationInput` validator for care-locations
- Uses `PizzaInput` validator for pizza tools
- Returns appropriate structured content for each type

## What's Deployed

**Commit:** `17bbd65`  
**Pushed to:** `https://github.com/Longevitate/GTPAppDemos.git`

The Azure deployment pipeline should now be building and deploying the updated Python server.

## Testing After Deployment

Once Azure deployment completes:

1. **Refresh your ChatGPT connector** (may need to disconnect and reconnect)

2. **Check available tools** - You should now see **5 tools**:
   - pizza-map
   - pizza-carousel
   - pizza-albums
   - pizza-list
   - **care-locations** ✨ (NEW!)

3. **Test the care-locations tool:**
   - "Show me Providence care locations"
   - "Find Providence urgent care"
   - "Display care locations near me"

4. **Expected result:**
   - Widget displays with 5 Providence facilities
   - Shows ratings, hours, addresses
   - View buttons link to Providence.org

## Files Changed

- ✅ `pizzaz_server_python/main.py` - Added care-locations widget support

## What's Next

Once you confirm the tool is working in ChatGPT, we can proceed to **Phase 2**:
- Add location filtering by ZIP/lat-lon
- Calculate distances from user
- Sort by nearest facilities
- Filter by facility type

---

**Status:** Changes committed and pushed. Azure deployment in progress. 🚀

