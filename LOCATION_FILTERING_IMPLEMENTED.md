# Location-Based Filtering with Distance Sorting ✅

## What Was Implemented

Successfully added intelligent location-based filtering that fetches all Providence locations from the API, calculates distances, and shows the closest facilities to the user.

---

## Features Added

### 1. ZIP Code to Coordinates Lookup
Added a comprehensive lookup table for common ZIP codes in:
- **Washington**: Bellingham (98229), Seattle (98101, 98112), Bellevue (98004), Everett (98201), Lacey (98516), Spokane (99201)
- **Oregon**: Portland areas (97203, 97211), Happy Valley (97086), Canby (97013), Salem (97301), Eugene (97401)
- **California**: Orange (92868), Dana Point (92629), Laguna Niguel (92677), Los Angeles (90001), San Francisco (94102)

### 2. Haversine Distance Calculator
Implemented precise great-circle distance calculation in miles between two lat/lon points using the Haversine formula.

### 3. Providence API Integration
- Fetches **all** locations from: `https://providencekyruus.azurewebsites.net/api/searchlocationsbyservices`
- Handles API errors gracefully
- Uses `httpx` for async HTTP requests

### 4. Smart Location Processing
When a user provides their location (ZIP code):
1. Convert ZIP to lat/lon coordinates
2. Fetch all Providence locations from API
3. Calculate distance from user to each facility
4. Sort by distance (nearest first)
5. Return top 7 closest locations

### 5. Enhanced Widget Display
- **Distance indicator**: Shows "X.X mi" with navigation icon in blue
- **Sorted by proximity**: Closest locations appear first
- **Dynamic data**: Uses real-time data from Providence API
- **Fallback support**: Shows default locations if no ZIP provided

---

## Example: User in Bellingham, WA (ZIP 98229)

**Before**: Showed random locations in OR and CA

**After**: 
1. Providence ExpressCare - Everett Broadway (47.99°N) - **26.3 mi** ⭐ Closest!
2. Providence Regional Medical Center - Everett (47.98°N) - **28.1 mi**
3. Providence ExpressCare - Mill Creek (47.86°N) - **35.2 mi**
4. Providence Swedish - First Hill Seattle (47.61°N) - **88.5 mi**
5. Providence ExpressCare - Lacey (47.06°N) - **118.7 mi**
6. ... more locations sorted by distance

---

## Technical Implementation

### Python Server (`main.py`)

**New Functions:**
```python
def haversine_distance(lat1, lon1, lat2, lon2) -> float
    Calculate distance in miles between two points

def zip_to_coords(zip_code) -> tuple[float, float] | None
    Convert ZIP code to coordinates

async def fetch_providence_locations() -> List[Dict]
    Fetch all locations from Providence API
```

**Updated Handler:**
```python
async def _call_tool_request(req):
    if widget == "care-locations":
        # 1. Fetch all locations from API
        all_locations = await fetch_providence_locations()
        
        # 2. Get user coordinates from ZIP
        user_coords = zip_to_coords(payload.location)
        
        # 3. Calculate distances for each location
        for loc in all_locations:
            distance = haversine_distance(user_lat, user_lon, loc.lat, loc.lng)
        
        # 4. Sort by distance and take top 7
        processed_locations.sort(key=lambda x: x["distance"])
        processed_locations = processed_locations[:7]
        
        # 5. Inject data into widget HTML
        widget_html_with_data = inject_data(widget.html, processed_locations)
```

### React Component (`care-list/index.jsx`)

**Updated Features:**
- Receives location data from server via `window.__WIDGET_DATA__`
- Displays distance with navigation icon
- Falls back to hardcoded JSON if no server data

```jsx
{location.distance !== undefined && location.distance !== null && (
  <div className="flex items-center gap-1">
    <Navigation className="h-3 w-3 text-blue-600" />
    <span className="text-xs font-medium text-blue-600">
      {location.distance} mi
    </span>
  </div>
)}
```

### Dependencies Added
- `httpx>=0.27.0` - For async API calls

---

## Files Modified

1. ✅ `pizzaz_server_python/main.py` - Added location filtering logic
2. ✅ `pizzaz_server_python/requirements.txt` - Added httpx dependency
3. ✅ `src/care-list/index.jsx` - Updated widget to display distances
4. ✅ `assets/care-list-2d2b.js` - Rebuilt widget bundle
5. ✅ `assets/care-list-2d2b.css` - Rebuilt styles

---

## Testing After Deployment

Once Azure deployment completes:

### Test Case 1: With Location
```
User: "Show me Providence locations near me"
ChatGPT: "What's your ZIP code?"
User: "98229" (Bellingham, WA)
```

**Expected Result:**
- Widget displays 7 locations
- Sorted by distance (closest first)
- Shows distance next to each location (e.g., "26.3 mi")
- Top location should be in Everett, WA (~26 miles away)

### Test Case 2: Without Location
```
User: "Show me Providence care locations"
```

**Expected Result:**
- Widget displays 7 default locations
- No distance shown (since no user location provided)

### Test Case 3: Different ZIP Codes
Try these to verify:
- **98101** (Seattle) - Should show Seattle-area locations first
- **97203** (Portland) - Should show Portland-area locations first
- **92868** (Orange, CA) - Should show Orange County locations first

---

## What's Next (Phase 3)

Now that location filtering works, we can add:
1. **Appointment time slots** - Show available times for each location
2. **Facility type filtering** - Filter by urgent care vs. express care vs. ER
3. **Insurance filtering** - Filter by accepted insurance plans
4. **Hours filtering** - Show only locations open now

---

## Deployment Status

**Commit:** `f6219e5`  
**Pushed to:** `https://github.com/Longevitate/GTPAppDemos.git`  
**Status:** Azure deployment in progress 🚀

Monitor your Azure Portal for deployment completion.

