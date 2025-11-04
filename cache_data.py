"""Script to cache Providence locations and ZIP codes locally."""
import httpx
import json
import csv
from pathlib import Path

print("Fetching Providence locations...")
try:
    response = httpx.get(
        "https://providencekyruus.azurewebsites.net/api/searchlocationsbyservices",
        timeout=30.0
    )
    response.raise_for_status()
    data = response.json()
    locations = data.get("locations", [])
    
    output_file = Path("pizzaz_server_python/providence_locations_cache.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    
    print(f"[OK] Cached {len(locations)} Providence locations to {output_file}")
except Exception as e:
    print(f"[ERROR] Error fetching Providence locations: {e}")

print("\nDownloading ZIP code data...")
try:
    response = httpx.get(
        "https://raw.githubusercontent.com/deepanshu88/Datasets/master/UploadedFiles2/zip_to_lat_lon_North%20America.csv",
        timeout=60.0
    )
    response.raise_for_status()
    
    # Parse CSV and extract US ZIP codes
    lines = response.text.strip().split('\n')
    reader = csv.DictReader(lines)
    
    zip_lookup = {}
    us_count = 0
    skipped = 0
    
    for row in reader:
        # Handle BOM in first column name
        country_code = row.get('country code', '').strip() or row.get('\ufeffcountry code', '').strip()
        if country_code == 'US':
            postal_code = row.get('postal code', '').strip()
            lat = row.get('latitude', '').strip()
            lon = row.get('longitude', '').strip()
            
            if postal_code and lat and lon:
                try:
                    zip_lookup[postal_code] = [float(lat), float(lon)]
                    us_count += 1
                except ValueError:
                    skipped += 1
                    continue
            else:
                skipped += 1
    
    print(f"  Processed {us_count} valid, {skipped} skipped")
    
    output_file = Path("pizzaz_server_python/zip_coords_cache.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(zip_lookup, f, indent=2)
    
    print(f"[OK] Cached {us_count} US ZIP codes to {output_file}")
except Exception as e:
    print(f"[ERROR] Error downloading ZIP codes: {e}")

print("\n[OK] Cache files created successfully!")

