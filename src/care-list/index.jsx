import React, { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import locationsData from "./locations.json";
import { MapPin, Star, Clock, Navigation } from "lucide-react";
import { useOpenAiGlobal } from "../use-openai-global";

// Widget version for cache busting
const WIDGET_VERSION = "3.0.0-react-hook";

function App() {
  // Use the official React hook to get toolOutput!
  const toolOutput = useOpenAiGlobal('toolOutput');
  
  // Initialize with empty array to avoid showing fallback data
  const [locations, setLocations] = useState([]);
  
  useEffect(() => {
    console.log(`[Care Widget v${WIDGET_VERSION}] Initializing...`);
    console.log('[Care Widget] toolOutput from hook:', toolOutput);
    
    if (toolOutput && toolOutput.locations && toolOutput.locations.length > 0) {
      console.log(`[Care Widget] ✅ Received ${toolOutput.locations.length} locations from toolOutput`);
      console.log('[Care Widget] First location:', toolOutput.locations[0].name, '@', toolOutput.locations[0].distance, 'mi');
      console.log('[Care Widget] User location:', toolOutput.location);
      console.log('[Care Widget] User coords:', toolOutput.user_coords);
      setLocations(toolOutput.locations);
    }
    // Removed fallback - wait for real data from toolOutput
  }, [toolOutput]);

  return (
    <div className="antialiased w-full text-black px-4 pb-2 border border-black/10 rounded-2xl sm:rounded-3xl overflow-hidden bg-white">
      <div className="max-w-full">
        <div className="flex flex-row items-center gap-4 sm:gap-4 border-b border-black/5 py-4">
          <div className="sm:w-18 w-16 aspect-square rounded-xl bg-white flex items-center justify-center p-2">
            <img
              src="/static/Prov.png"
              alt="Providence Health"
              className="w-full h-full object-contain"
            />
          </div>
          <div>
            <div className="text-base sm:text-xl font-medium">
              Providence Care Locations
            </div>
            <div className="text-sm text-black/60">
              Find urgent care and express care near you
            </div>
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
                className="flex w-full items-start hover:border-black/0! gap-2"
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
                      {location.match_reason && (
                        <div className="mt-0.5 mb-1">
                          <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 text-blue-700">
                            Treats: {location.match_reason}
                          </span>
                        </div>
                      )}
                      <div className="mt-1 sm:mt-0.25 flex items-center gap-3 text-black/70 text-sm">
                        {location.rating_value && (
                          <div className="flex items-center gap-1">
                            <Star
                              strokeWidth={1.5}
                              className="h-3 w-3 text-yellow-500 fill-yellow-500"
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

