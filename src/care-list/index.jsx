import React, { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import locationsData from "./locations.json";
import { MapPin, Star, Clock, Navigation } from "lucide-react";

function App() {
  const [locations, setLocations] = useState([]);
  
  useEffect(() => {
    console.log('[Care Widget] Initializing...');
    console.log('[Care Widget] window.location.search:', window.location.search);
    console.log('[Care Widget] window.location.href:', window.location.href);
    
    // Read arguments from meta tags (injected by server)
    const locationMeta = document.querySelector('meta[name="care-location"]');
    const reasonMeta = document.querySelector('meta[name="care-reason"]');
    
    const location = locationMeta?.getAttribute('content') || '';
    const reason = reasonMeta?.getAttribute('content') || '';
    
    console.log(`[Care Widget] Arguments from meta tags:`);
    console.log(`  - location: ${location || '(none)'}`);
    console.log(`  - reason: ${reason || '(none)'}`);
    
    // Detect sandbox environment
    const sandboxMatch = window.location.hostname.match(/^connector_([a-f0-9]+)\.web-sandbox/);
    if (sandboxMatch) {
      console.log('[Care Widget] Detected sandbox environment');
    }
    
    // Build API URL with query parameters
    const params = new URLSearchParams();
    if (location) params.append('location', location);
    if (reason) params.append('reason', reason);
    
    const apiUrl = `/api/care-locations?${params.toString()}`;
    console.log(`[Care Widget] Fetching from: ${apiUrl}`);
    
    // Fetch fresh data from stateless API
    fetch(apiUrl)
      .then(response => {
        console.log(`[Care Widget] API response status: ${response.status}`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
      })
      .then(data => {
        if (data.locations && data.locations.length > 0) {
          console.log(`[Care Widget] ✅ Fetched ${data.locations.length} locations from API`);
          console.log('[Care Widget] First location:', data.locations[0].name, '@', data.locations[0].distance, 'mi');
          setLocations(data.locations);
        } else {
          console.log('[Care Widget] ⚠️ API returned no locations, using fallback');
          setLocations(locationsData?.locations || []);
        }
      })
      .catch(err => {
        console.error('[Care Widget] ❌ Failed to fetch data from API:', err);
        console.log('[Care Widget] Error details:', err.message);
        console.log('[Care Widget] Using fallback locations.json');
        setLocations(locationsData?.locations || []);
      });
  }, []);

  return (
    <div className="antialiased w-full text-black px-4 pb-2 border border-black/10 rounded-2xl sm:rounded-3xl overflow-hidden bg-white">
      <div className="max-w-full">
        <div className="flex flex-row items-center gap-4 sm:gap-4 border-b border-black/5 py-4">
          <div
            className="sm:w-18 w-16 aspect-square rounded-xl bg-cover bg-center flex items-center justify-center"
            style={{
              background: "linear-gradient(135deg, #0066cc 0%, #004c99 100%)",
            }}
          >
            <svg
              className="w-10 h-10 text-white"
              fill="currentColor"
              viewBox="0 0 24 24"
            >
              <path d="M19 3H5c-1.1 0-1.99.9-1.99 2L3 19c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-1 11h-4v4h-4v-4H6v-4h4V6h4v4h4v4z" />
            </svg>
          </div>
          <div>
            <div className="text-base sm:text-xl font-medium">
              Providence Care Locations
            </div>
            <div className="text-sm text-black/60">
              Find urgent care and express care near you
            </div>
          </div>
          <div className="flex-auto hidden sm:flex justify-end pr-2">
            <button
              type="button"
              className="cursor-pointer inline-flex items-center rounded-full bg-[#0066cc] text-white px-4 py-1.5 sm:text-md text-sm font-medium hover:opacity-90 active:opacity-100"
            >
              Find Nearby
            </button>
          </div>
        </div>
        <div className="min-w-full text-sm flex flex-col">
          {locations.slice(0, 7).map((location, i) => (
            <div
              key={location.id}
              className="px-3 -mx-2 rounded-2xl hover:bg-black/5"
            >
              <div
                style={{
                  borderBottom:
                    i === 7 - 1 ? "none" : "1px solid rgba(0, 0, 0, 0.05)",
                }}
                className="flex w-full items-center hover:border-black/0! gap-2"
              >
                <div className="py-3 pr-3 min-w-0 w-full sm:w-3/5">
                  <div className="flex items-center gap-3">
                    <img
                      src={location.image}
                      alt={location.name}
                      className="h-10 w-10 sm:h-11 sm:w-11 rounded-lg object-cover ring ring-black/5"
                    />
                    <div className="w-3 text-end sm:block hidden text-sm text-black/40">
                      {i + 1}
                    </div>
                    <div className="min-w-0 sm:pl-1 flex flex-col items-start h-full">
                      <div className="font-medium text-sm sm:text-md truncate max-w-[40ch]">
                        {location.name}
                      </div>
                      <div className="mt-1 sm:mt-0.25 flex items-center gap-3 text-black/70 text-sm">
                        {location.distance !== undefined && location.distance !== null && (
                          <div className="flex items-center gap-1">
                            <Navigation
                              strokeWidth={1.5}
                              className="h-3 w-3 text-blue-600"
                            />
                            <span className="text-xs font-medium text-blue-600">
                              {location.distance} mi
                            </span>
                          </div>
                        )}
                        {location.rating_value && (
                          <div className="flex items-center gap-1">
                            <Star
                              strokeWidth={1.5}
                              className="h-3 w-3 text-black"
                            />
                            <span>{location.rating_value}</span>
                            <span className="text-xs text-black/50">
                              ({location.rating_count})
                            </span>
                          </div>
                        )}
                        {location.hours_today && (
                          <div className="flex items-center gap-1">
                            <Clock
                              strokeWidth={1.5}
                              className="h-3 w-3 text-green-600"
                            />
                            <span className="text-xs">
                              {location.hours_today.start} - {location.hours_today.end}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
                <div className="hidden sm:flex items-center gap-3 text-end py-2 px-3 text-sm whitespace-nowrap flex-auto">
                  {location.distance !== undefined && location.distance !== null && (
                    <div className="flex items-center gap-1 text-blue-600 font-semibold">
                      <Navigation strokeWidth={2} className="h-4 w-4" />
                      <span>{location.distance} mi</span>
                    </div>
                  )}
                  <div className="flex items-center gap-1 text-black/60">
                    <MapPin strokeWidth={1.5} className="h-4 w-4" />
                    {location.address_plain.split(",").slice(-2).join(",")}
                  </div>
                </div>
                <div className="py-2 whitespace-nowrap flex justify-end">
                  <button
                    className="px-3 py-1.5 text-xs rounded-full bg-[#0066cc] text-white hover:bg-[#0052a3] transition-colors"
                    onClick={() => {
                      if (location.url) {
                        window.open(location.url, "_blank");
                      }
                    }}
                  >
                    View
                  </button>
                </div>
              </div>
            </div>
          ))}
          {locations.length === 0 && (
            <div className="py-6 text-center text-black/60">
              No care locations found.
            </div>
          )}
        </div>
        <div className="sm:hidden px-0 pt-2 pb-2">
          <button
            type="button"
            className="w-full cursor-pointer inline-flex items-center justify-center rounded-full bg-[#0066cc] text-white px-4 py-2 font-medium hover:opacity-90 active:opacity-100"
          >
            Find Nearby
          </button>
        </div>
      </div>
    </div>
  );
}

createRoot(document.getElementById("care-list-root")).render(<App />);

