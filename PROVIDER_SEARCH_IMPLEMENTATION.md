# Provider Search Implementation Summary

## ✅ Implementation Complete

Provider search functionality has been successfully added to the **Providence TEXT-only app**.

---

## 📁 Files Created/Modified

### New Files:
1. **`pizzaz_server_python/shared/provider_search.py`**
   - Core provider search logic
   - OmniSearch API integration
   - Client-side filtering
   - Unique CID generation per request
   - Chrome user-agent spoofing

### Modified Files:
1. **`pizzaz_server_python/shared/__init__.py`**
   - Added exports for provider search functions

2. **`pizzaz_server_python/text_only_server.py`**
   - Added `ProviderSearchInput` model
   - Added `PROVIDER_SEARCH_INPUT_SCHEMA`
   - Added `format_providers_text()` function
   - Added `find-provider-text` tool registration
   - Added provider search handler in `_call_tool()`

---

## 🎯 New MCP Tool: `find-provider-text`

### Tool Name
`find-provider-text`

### Description
Find Providence healthcare providers (doctors, specialists, physicians, PAs, NPs) with extensive filtering options.

### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `search` | string | ✅ Yes | Provider name, specialty, or condition (e.g., 'cardiologist', 'Dr. Smith') |
| `location` | string | No | City/state or ZIP code (e.g., 'Seattle WA', '97202') |
| `accepting_new_patients` | boolean | No | Filter to providers accepting new patients |
| `virtual_care` | boolean | No | Filter to providers offering telemedicine |
| `languages` | array[string] | No | Filter by languages spoken |
| `insurance` | string | No | Filter by insurance accepted |
| `gender` | string | No | Filter by provider gender ('Male' or 'Female') |
| `age_group` | string | No | Filter by age groups ('Pediatrics', 'Teenagers', 'Adult', 'Geriatrics') |
| `limit` | integer | No | Number of results (default: 5, max: 20) |

### Example Queries
- "Find a cardiologist in Seattle"
- "Find a pediatrician accepting new patients in Portland"
- "Find a Spanish-speaking family doctor near me"
- "Find a female dermatologist who takes Kaiser insurance"

---

## 🔧 Technical Implementation

### OmniSearch API Integration

**Base URL:** `https://providenceomni.azurewebsites.net/api/OmniSearch`

**Key Parameters:**
- `type=search` - Operation type
- `brand=providence` - Fixed brand
- `IsClinic=false` - Returns providers, not clinics
- `cid` - Unique client ID (generated with `uuid.uuid4()` per request)
- `search` - Search query
- `location` / `userLocation` - Geographic filters
- `top` / `skip` - Pagination

**User Agent:**
```
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
```

### Response Format

The API returns a `results` array (not `providers`) containing provider objects with:

**Essential Fields:**
- `Name` - Full provider name
- `Degrees` - [MD, DO, PA, NP, etc.]
- `PrimarySpecialties` - Primary specialty
- `SubSpecialties` - Sub-specialties
- `Gender` - Male/Female
- `Rating` / `RatingCount` / `ReviewCount` - Provider ratings
- `AcceptingNewPatients` - 1 = yes, 0 = no
- `VirtualCare` - 1 = offers telemedicine, 0 = no

**Location Info:**
- `LocationNames` - Array of facility names
- `Addresses` - Array of full addresses
- `Phones` - Array of phone numbers
- `distance` - Miles from user location (when location provided)

**Professional Info:**
- `ProfessionalStatement` - Biography
- `Languages` - Languages spoken
- `AgesSeen` - Age groups treated
- `InsuranceAccepted` - Insurance plans accepted
- `Education` / `Training` / `Certifications` - Professional background

**Booking:**
- `ProviderUniqueUrlOnesite` - Full Providence.org profile URL
- `ProfileUrl` - Relative profile URL

---

## 📊 Client-Side Filtering

Since the OmniSearch API doesn't support all filter parameters, we implement client-side filtering for:

1. **Accepting New Patients** - Filters `AcceptingNewPatients == 1`
2. **Virtual Care** - Filters `VirtualCare == 1`
3. **Languages** - Filters by languages in `Languages` array
4. **Insurance** - Case-insensitive partial match in `InsuranceAccepted` array
5. **Gender** - Exact match on `Gender` field
6. **Age Group** - Checks if age group exists in `AgesSeen` array

---

## 📝 Text Output Format

The `format_providers_text()` function creates markdown-formatted output with:

### Header
- Search query and location
- Total vs filtered provider count

### For Each Provider:
- **Name & Credentials** (e.g., "Dr. John Smith, MD")
- **Gender** (with emoji)
- **Specialties** (primary and sub-specialties)
- **Distance** (when location provided)
- **Status Badges** (accepting new patients, virtual care)
- **Rating** (stars and review count)
- **Languages Spoken**
- **Age Groups Treated**
- **Practice Locations** (primary + count of additional locations)
- **Phone Number**
- **Professional Statement** (truncated to ~200 chars)
- **Booking Link** (profile URL)

### Example Output:
```markdown
# 👨‍⚕️ Providence Provider Search Results

**Search:** cardiologist | **Location:** Seattle WA

Found **5** providers:

---

## 1. John L. Petersen, MD

👨 **Male**

🩺 **Specialty:** Cardiology

📍 **0.6 miles away**

✅ Accepting New Patients | 💻 Offers Virtual Care

⭐⭐⭐⭐⭐ **5.0** (204 reviews)

🗣️ **Languages:** English

👥 **Ages Seen:** Adult, Geriatrics

🏥 **Practice Location:**
  - **Swedish First Hill**
    Seattle, WA, 747 Broadway, 98122

📞 **Phone:** 206-320-2000

🔗 [View Profile & Book Appointment](https://www.providence.org/doctors/...)

---
```

---

## ✅ Testing Results

### Test 1: Basic Search
- **Query:** "cardiologist in Seattle"
- **Result:** ✅ 2 providers returned
- **Top result:** Dr. John L. Petersen (Cardiology, 0.57 miles)

### Test 2: Filtered Search
- **Query:** "pediatrician accepting new patients in Portland"
- **Result:** ✅ 1 provider returned
- **Top result:** Dr. Anna M. Meyers (Pediatrics, accepting new patients)

---

## 🚀 Usage in ChatGPT

The tool will automatically be available in ChatGPT when the text-only server is running.

### Example Conversations:

**User:** "I need a cardiologist in Seattle"
→ ChatGPT calls `find-provider-text` with `search="cardiologist"`, `location="Seattle WA"`

**User:** "Find me a Spanish-speaking pediatrician who accepts Kaiser insurance near Portland"
→ ChatGPT calls `find-provider-text` with:
- `search="pediatrician"`
- `location="Portland OR"`
- `languages=["Spanish"]`
- `insurance="Kaiser"`

---

## 📦 Dependencies

No new dependencies required! Uses existing packages:
- `httpx` - Already in requirements.txt
- `uuid` - Python standard library

---

## 🔒 Security & Privacy

1. **Unique Client ID:** Each request generates a unique UUID for the `cid` parameter
2. **User Agent Spoofing:** Uses standard Chrome user agent to appear as normal browser traffic
3. **No Authentication Required:** OmniSearch API is publicly accessible
4. **Timeout Protection:** 30-second timeout on all API requests
5. **Error Handling:** Graceful degradation with user-friendly error messages

---

## 🎉 Success Metrics

- ✅ API integration working
- ✅ All filters implemented
- ✅ Distance sorting functional
- ✅ Unique CID per request
- ✅ User agent spoofing
- ✅ Text formatting complete
- ✅ Error handling robust
- ✅ Tests passing

---

## 🔄 Next Steps (Optional)

1. **Caching:** Consider caching provider results to reduce API calls
2. **Pagination:** Add support for `skip` parameter for result pagination
3. **Enhanced Filtering:** Add more sophisticated insurance matching
4. **Analytics:** Track which searches/filters are most common
5. **Integration with Care Locations:** Cross-reference providers with facility locations

---

## 📞 Support

For issues or questions about the provider search implementation:
- Check OmniSearch API docs: https://developers.dexcarehealth.com/api/omnisearch/
- Review `pizzaz_server_python/shared/provider_search.py` for implementation details
- Test using the text-only server: `python -m pizzaz_server_python.text_only_server`

---

**Implementation Date:** November 18, 2025
**Status:** ✅ Complete and Tested

