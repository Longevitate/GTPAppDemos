import React, { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import locationsData from "./locations.json";
import { MapPin, Star, Clock, Navigation, ChevronLeft, ChevronRight, Calendar } from "lucide-react";
import { useOpenAiGlobal } from "../use-openai-global";

// Widget version for cache busting
const WIDGET_VERSION = "4.0.0-timeslot-booking";

// TimeSlots component for displaying and booking available slots
function TimeSlots({ location }) {
  const [dates, setDates] = useState([]);
  const [selectedDateIndex, setSelectedDateIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (location.booking_wheelhouse) {
      fetchTimeslots();
    }
  }, [location.booking_wheelhouse]);

  const fetchTimeslots = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Get API base URL from current location or use localhost for dev
      const apiBase = window.location.hostname === 'localhost' 
        ? 'http://localhost:8000' 
        : window.location.origin;
      
      const response = await fetch(
        `${apiBase}/api/timeslots?location_code=${encodeURIComponent(location.booking_wheelhouse)}`
      );
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      
      if (!data.success) {
        throw new Error(data.error || 'Failed to fetch timeslots');
      }
      
      setDates(data.dates || []);
      
      // Find first date with slots
      const firstDateWithSlots = (data.dates || []).findIndex(d => d.num_times > 0);
      if (firstDateWithSlots !== -1) {
        setSelectedDateIndex(firstDateWithSlots);
      }
      
    } catch (err) {
      console.error('Error fetching timeslots:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSlotClick = (slot) => {
    // Deep link to Providence booking page
    const bookingUrl = `https://scheduling.care.psjhealth.org/retail?timeSlot=${slot.encoded_timeslot}&departmentUrlName=${encodeURIComponent(location.booking_wheelhouse)}&brand=providence`;
    window.open(bookingUrl, '_blank');
  };

  const goToPrevDate = () => {
    if (selectedDateIndex > 0) {
      setSelectedDateIndex(selectedDateIndex - 1);
    }
  };

  const goToNextDate = () => {
    if (selectedDateIndex < dates.length - 1) {
      setSelectedDateIndex(selectedDateIndex + 1);
    }
  };

  if (loading) {
    return (
      <div className="p-4 text-center">
        <div className="animate-pulse flex flex-col gap-2">
          <div className="h-8 bg-gray-200 rounded w-2/3 mx-auto"></div>
          <div className="grid grid-cols-3 gap-2 mt-4">
            {[...Array(9)].map((_, i) => (
              <div key={i} className="h-10 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-center text-red-600">
        <p className="mb-2">Unable to load available time slots.</p>
        <p className="text-sm text-gray-600">Please call {location.phone || 'the location'} to book.</p>
      </div>
    );
  }

  if (!dates || dates.length === 0) {
    return (
      <div className="p-4 text-center text-gray-600">
        <p className="mb-2">No available time slots found.</p>
        <p className="text-sm">Please call {location.phone || 'the location'} to book an appointment.</p>
      </div>
    );
  }

  const selectedDate = dates[selectedDateIndex];
  const availableSlots = selectedDate?.times || [];

  return (
    <div className="border-t border-gray-200 bg-gray-50 p-4">
      <div className="mb-4">
        <h3 className="text-sm font-semibold mb-3">Select a time slot</h3>
        
        {/* Date Navigation */}
        <div className="flex items-center justify-between gap-2 mb-4">
          <button
            onClick={goToPrevDate}
            disabled={selectedDateIndex === 0}
            className="p-2 rounded-lg hover:bg-gray-200 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          
          <div className="flex items-center gap-2 text-center">
            <Calendar className="w-4 h-4 text-gray-600" />
            <span className="font-medium">{selectedDate?.formatted_date}</span>
          </div>
          
          <button
            onClick={goToNextDate}
            disabled={selectedDateIndex === dates.length - 1}
            className="p-2 rounded-lg hover:bg-gray-200 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>

        {/* Time Slots Grid */}
        {availableSlots.length > 0 ? (
          <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
            {availableSlots.map((slot, idx) => (
              <button
                key={idx}
                onClick={() => handleSlotClick(slot)}
                className="px-3 py-2 text-sm rounded-lg border border-blue-300 bg-white text-blue-700 hover:bg-blue-50 hover:border-blue-500 transition-colors font-medium"
              >
                {slot.formatted_time}
              </button>
            ))}
          </div>
        ) : (
          <div className="text-center text-gray-600 py-4">
            <p className="text-sm">No slots available for this date.</p>
            <p className="text-xs mt-1">Try selecting a different date.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function App() {
  // Use the official React hook to get toolOutput!
  const toolOutput = useOpenAiGlobal('toolOutput');
  
  // Initialize with empty array to avoid showing fallback data
  const [locations, setLocations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [expandedLocationId, setExpandedLocationId] = useState(null);
  
  useEffect(() => {
    console.log(`[Care Widget v${WIDGET_VERSION}] Initializing...`);
    console.log('[Care Widget] toolOutput from hook:', toolOutput);
    
    if (toolOutput && toolOutput.locations && toolOutput.locations.length > 0) {
      console.log(`[Care Widget] ✅ Received ${toolOutput.locations.length} locations from toolOutput`);
      console.log('[Care Widget] First location:', toolOutput.locations[0].name, '@', toolOutput.locations[0].distance, 'mi');
      console.log('[Care Widget] User location:', toolOutput.location);
      console.log('[Care Widget] User coords:', toolOutput.user_coords);
      setLocations(toolOutput.locations);
      setIsLoading(false);
    }
  }, [toolOutput]);

  return (
    <div className="antialiased w-full text-black px-4 pb-2 border border-black/10 rounded-2xl sm:rounded-3xl overflow-hidden bg-white">
      <div className="max-w-full">
        <div className="flex flex-row items-center gap-4 sm:gap-4 border-b border-black/5 py-4">
          <div className="sm:w-18 w-16 aspect-square rounded-xl bg-white flex items-center justify-center p-2">
            <img
              src="https://provgpt.azurewebsites.net/static/Prov.png"
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
        {/* Emergency Warning Banner */}
        {toolOutput?.is_emergency && (
          <div className="bg-red-50 border-2 border-red-500 rounded-xl p-4 my-4">
            <div className="flex items-start gap-3">
              <div className="text-red-600 text-2xl font-bold">⚠️</div>
              <div className="flex-1">
                <div className="text-red-900 font-bold text-lg mb-1">
                  EMERGENCY - CALL 911 IMMEDIATELY
                </div>
                <div className="text-red-800 text-sm mb-3">
                  {toolOutput.emergency_warning}
                </div>
                <div className="flex flex-col sm:flex-row gap-2">
                  <button
                    className="px-4 py-2 bg-red-600 text-white rounded-lg font-semibold hover:bg-red-700"
                    onClick={() => window.location.href = 'tel:911'}
                  >
                    📞 Call 911
                  </button>
                  <button
                    className="px-4 py-2 bg-red-100 text-red-800 rounded-lg font-medium hover:bg-red-200"
                    onClick={() => window.location.href = 'tel:988'}
                  >
                    988 - Crisis Lifeline
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
        <div className="min-w-full text-sm flex flex-col">
          {locations.slice(0, 7).map((location, i) => {
            const isExpanded = expandedLocationId === location.id;
            
            return (
            <div
              key={location.id}
              className="px-3 -mx-2 rounded-2xl hover:bg-black/5"
            >
              <div
                style={{
                  borderBottom:
                    i === 7 - 1 && !isExpanded ? "none" : "1px solid rgba(0, 0, 0, 0.05)",
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
                      <div className="mt-2 sm:mt-2 flex items-center gap-3 text-black/70 text-sm">
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
                              className={`h-3 w-3 ${location.is_open_now ? 'text-green-600' : 'text-gray-400'}`}
                            />
                            <span className="text-xs">
                              {location.is_open_now ? (
                                <span className="text-green-700 font-medium">{location.open_status}</span>
                              ) : (
                                <span className="text-gray-600">{location.open_status || `${location.hours_today.start} - ${location.hours_today.end}`}</span>
                              )}
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
                <div className="py-2 whitespace-nowrap flex justify-end gap-2">
                  {location.booking_wheelhouse ? (
                    <button
                      className={`px-3 py-1.5 text-xs rounded-full transition-colors ${
                        isExpanded 
                          ? 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                          : 'bg-green-600 text-white hover:bg-green-700'
                      }`}
                      onClick={() => setExpandedLocationId(isExpanded ? null : location.id)}
                    >
                      {isExpanded ? 'Close' : 'Book Now'}
                    </button>
                  ) : (
                    location.url && (
                      <button
                        className="px-3 py-1.5 text-xs rounded-full bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                        onClick={() => window.open(location.url, "_blank")}
                      >
                        Reserve Spot
                      </button>
                    )
                  )}
                  <button
                    className="px-3 py-1.5 text-xs rounded-full bg-[#0066cc] text-white hover:bg-[#0052a3] transition-colors"
                    onClick={() => {
                      if (location.url) {
                        window.open(location.url, "_blank");
                      }
                    }}
                  >
                    View Details
                  </button>
                </div>
              </div>
              
              {/* Timeslots Section */}
              {isExpanded && location.booking_wheelhouse && (
                <TimeSlots location={location} />
              )}
            </div>
            );
          })}
          {locations.length === 0 && (
            <div className="py-6 text-center text-black/60">
              {isLoading ? "Loading locations..." : "No care locations found."}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

createRoot(document.getElementById("care-list-root")).render(<App />);

