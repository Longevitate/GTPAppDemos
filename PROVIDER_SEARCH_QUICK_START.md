# Provider Search - Quick Start Guide

## 🚀 What Was Added

A new MCP tool **`find-provider-text`** that searches for healthcare providers (doctors, specialists, PAs, NPs) using the Providence OmniSearch API.

---

## ⚡ Quick Test

### Start the Text-Only Server:
```bash
cd openai-apps-sdk-examples/pizzaz_server_python
python -m pizzaz_server_python.text_only_server
```

The server will start on **http://localhost:8001/mcp**

### Test in ChatGPT:
Once connected, try these queries:
- "Find a cardiologist in Seattle"
- "Find a pediatrician accepting new patients in Portland"
- "Find a Spanish-speaking doctor near me"
- "Find a female dermatologist who takes Kaiser insurance"

---

## 🎯 Tool Capabilities

### Search Types:
✅ By specialty (cardiologist, pediatrician, dermatologist, etc.)
✅ By name (Dr. Smith, Dr. Johnson, etc.)
✅ By condition (heart disease, diabetes, cancer, etc.)

### Filters Available:
✅ Accepting new patients
✅ Virtual/telemedicine available
✅ Languages spoken
✅ Insurance accepted
✅ Provider gender
✅ Age groups treated (Pediatrics, Teenagers, Adult, Geriatrics)
✅ Distance from user location

---

## 📊 Example Output

When ChatGPT calls the tool, users get formatted markdown with:
- Provider name & credentials (MD, DO, PA, NP)
- Specialty & subspecialties
- Distance from user location
- Accepting new patients status
- Virtual care availability
- Star rating & review count
- Languages spoken
- Practice locations with addresses
- Phone number
- Direct booking link

---

## 🔧 Technical Details

### Files Modified:
1. `pizzaz_server_python/shared/provider_search.py` - NEW
2. `pizzaz_server_python/shared/__init__.py` - Updated exports
3. `pizzaz_server_python/text_only_server.py` - Added tool & handler

### API Integration:
- **Endpoint:** `https://providenceomni.azurewebsites.net/api/OmniSearch`
- **Unique CID:** Generated per request using UUID
- **User Agent:** Chrome browser (spoofed for API compatibility)
- **Timeout:** 30 seconds
- **Max Results:** 20 per request (default: 5)

### Key Features:
✅ No authentication required
✅ Real-time search results
✅ Distance-based sorting (when location provided)
✅ Comprehensive error handling
✅ Client-side filtering for advanced criteria

---

## 📋 Tool Parameters

```json
{
  "search": "cardiologist",              // REQUIRED
  "location": "Seattle WA",              // Optional
  "accepting_new_patients": true,        // Optional
  "virtual_care": true,                  // Optional
  "languages": ["Spanish", "English"],   // Optional
  "insurance": "Kaiser",                 // Optional
  "gender": "Female",                    // Optional
  "age_group": "Pediatrics",            // Optional
  "limit": 5                            // Optional (default: 5, max: 20)
}
```

---

## ✅ Testing Completed

- ✅ Basic search (specialty + location)
- ✅ Filtered search (accepting new patients)
- ✅ Distance sorting
- ✅ API error handling
- ✅ Text formatting
- ✅ All filters functional

---

## 🎉 Ready to Use!

The provider search tool is now fully integrated into the **Providence TEXT-only app** and ready for testing with ChatGPT.

For detailed implementation info, see `PROVIDER_SEARCH_IMPLEMENTATION.md`


