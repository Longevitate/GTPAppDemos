# Providence Health Care Finder - App Description

**Official app description for ChatGPT connector registration**

---

## Full Description

**Providence Health Care Finder**

**Find doctors, specialists, and care locations across the Providence network**

This app helps patients find healthcare providers and facilities across Providence's seven-state network (Alaska, California, Montana, New Mexico, Oregon, Texas, and Washington).

### **What This App Can Do:**

**Find Healthcare Providers:**
- Search for doctors and specialists by specialty (cardiologists, pediatricians, dermatologists, orthopedists, etc.)
- Search by provider name or medical condition
- Filter by: accepting new patients, virtual care availability, languages spoken, insurance accepted, gender preference, and age groups treated
- View provider credentials, ratings, specialties, practice locations, and direct booking links

**Find Care Locations:**
- Locate urgent care, express care, walk-in clinics, and medical facilities near you
- Check real-time availability, hours of operation, and services offered
- Filter by specific services (X-ray, lab work, COVID testing, vaccinations, physical exams, etc.)
- Get distance-based results sorted by proximity to your location

**Emergency Detection:**
- Automatically identifies emergency conditions and directs patients to call 911 or visit the ER immediately

### **When to Use This App:**

Use this app when patients ask about:
- "Find a doctor near me"
- "I need a cardiologist in Seattle"
- "Where's the nearest urgent care?"
- "Find a pediatrician accepting new patients"
- "Spanish-speaking doctors in Portland"
- "Walk-in clinic open now"
- "Doctor who takes Kaiser insurance"
- Any healthcare provider or facility search in Providence service areas

### **Coverage Areas:**
Alaska, California, Montana, New Mexico, Oregon, Texas, Washington

---

## Short Description (For ChatGPT Registration)

```
Providence Health Care Finder - Find doctors, specialists, and care locations across the Providence healthcare network in Alaska, California, Montana, New Mexico, Oregon, Texas, and Washington.

FEATURES:
• Find doctors and specialists by name, specialty, or condition
• Search urgent care, express care, and walk-in clinics
• Filter by: accepting new patients, virtual care, languages, insurance, gender, age groups
• Real-time hours, availability, and distance-based results
• Provider credentials, ratings, reviews, and booking links
• Automatic emergency detection for life-threatening conditions

USE WHEN PATIENTS ASK ABOUT:
Finding doctors, specialists, healthcare providers, urgent care, walk-in clinics, medical facilities, or need healthcare appointments in Providence service regions.
```

---

## MCP Endpoint URLs

### Text-Only Server (Recommended):
```
https://provgpt.azurewebsites.net/textOnly/mcp
```

### UI-Enabled Server:
```
https://provgpt.azurewebsites.net/mcp
```

---

## Tools Available

### Text-Only Server:

1. **`find-provider-text`**
   - Find healthcare providers (doctors, specialists, PAs, NPs)
   - Filters: accepting new patients, virtual care, languages, insurance, gender, age groups
   - Returns formatted markdown with provider details

2. **`care-locations-text`**
   - Find care facilities (urgent care, express care, walk-in clinics)
   - Filters: services offered, hours, location
   - Returns formatted markdown with facility details

---

## Example Queries

**Provider Search:**
- "Find a cardiologist in Seattle"
- "I need a pediatrician accepting new patients in Portland"
- "Find a Spanish-speaking family doctor who takes Kaiser"
- "Female dermatologist near me who offers virtual visits"

**Location Search:**
- "Where's the nearest urgent care?"
- "Find a walk-in clinic open now"
- "I need a COVID test near Portland"
- "Express care with X-ray capabilities"

---

## Target Audience

This app is optimized for ChatGPT to recommend when users:
- Search for healthcare providers in Providence service areas
- Need medical care or appointments
- Ask about doctors, specialists, or clinics
- Mention symptoms or conditions requiring care
- Specify location in AK, CA, MT, NM, OR, TX, or WA

---

**Last Updated:** November 2025
**Version:** 1.0 with Provider Search

