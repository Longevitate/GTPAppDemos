import React, { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { Heart, MapPin, Phone, Globe, Filter, X } from "lucide-react";
import { useOpenAiGlobal } from "../use-openai-global";

// Widget version for cache busting
const WIDGET_VERSION = "1.0.0-provider-search";

function ProviderCard({ provider, onClick }) {
  const {
    Name,
    Degrees = [],
    Gender,
    PrimarySpecialties = [],
    SubSpecialties = [],
    Rating,
    RatingCount,
    AcceptingNewPatients,
    VirtualCare,
    Languages = [],
    LocationNames = [],
    Addresses = [],
    Phones = [],
    ImageUrl,
    distance,
    ProviderUniqueUrlOnesite,
  } = provider;

  const rating = parseFloat(Rating || 0);
  const ratingCount = parseInt(RatingCount || 0);
  const hasRating = rating > 0 && ratingCount > 0;
  
  const primaryLocation = LocationNames[0] || "Location not specified";
  const primaryAddress = Addresses[0] || "";
  const primaryPhone = Phones[0] || "";
  
  const accepting = AcceptingNewPatients === 1;
  const virtual = VirtualCare === 1;
  
  const degreeString = Degrees.join(", ");
  const genderEmoji = Gender === "Male" ? "👨‍⚕️" : Gender === "Female" ? "👩‍⚕️" : "🧑‍⚕️";

  return (
    <div className="provider-card border border-gray-200 rounded-xl p-4 hover:shadow-lg transition-shadow bg-white">
      <div className="flex gap-6">
        {/* LEFT COLUMN: Photo + Rating */}
        <div className="flex-shrink-0 flex flex-col items-center gap-2">
          <div className="w-20 h-20 rounded-full overflow-hidden bg-gray-100 ring-2 ring-gray-200">
            {ImageUrl ? (
              <img
                src={ImageUrl}
                alt={Name}
                className="w-full h-full object-cover"
                onError={(e) => {
                  e.target.style.display = "none";
                  e.target.nextSibling.style.display = "flex";
                }}
              />
            ) : null}
            <div
              className="w-full h-full flex items-center justify-center text-3xl"
              style={{ display: ImageUrl ? "none" : "flex" }}
            >
              {genderEmoji}
            </div>
          </div>
          
          {/* Rating under photo */}
          {hasRating && (
            <div className="flex flex-col items-center gap-1">
              <div className="flex items-center gap-0.5">
                {[...Array(5)].map((_, idx) => (
                  <Heart
                    key={idx}
                    className={`h-3.5 w-3.5 ${
                      idx < Math.floor(rating)
                        ? "fill-yellow-400 text-yellow-400"
                        : "fill-gray-200 text-gray-200"
                    }`}
                  />
                ))}
              </div>
              <span className="text-xs font-semibold">{rating.toFixed(1)}</span>
              <span className="text-xs text-gray-500">({ratingCount})</span>
            </div>
          )}
        </div>

        {/* CENTER COLUMN: Details */}
        <div className="flex-1 min-w-0">
          {/* Name and Credentials */}
          <h3 className="text-lg font-semibold text-[#003da5] mb-2">
            {Name}
            {degreeString && <span className="text-gray-600 font-normal">, {degreeString}</span>}
          </h3>

          {/* Specialties */}
          {PrimarySpecialties.length > 0 && (
            <p className="text-sm font-medium text-gray-700 mb-2">
              🩺 {PrimarySpecialties.join(", ")}
            </p>
          )}

          {/* Distance */}
          {distance !== null && distance !== undefined && (
            <p className="text-sm text-gray-600 mb-2">
              <MapPin className="inline h-4 w-4 mr-1" />
              {distance.toFixed(1)} miles away
            </p>
          )}

          {/* Status Badges */}
          <div className="flex flex-wrap gap-2 mb-2">
            {accepting ? (
              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                ✅ Accepting New Patients
              </span>
            ) : (
              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                ⏸️ Not Accepting New Patients
              </span>
            )}
            
            {virtual && (
              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                💻 Virtual Care
              </span>
            )}
          </div>

          {/* Languages */}
          {Languages.length > 0 && (
            <p className="text-sm text-gray-600 mb-2">
              🗣️ {Languages.slice(0, 3).join(", ")}
              {Languages.length > 3 && ` +${Languages.length - 3} more`}
            </p>
          )}

          {/* Location */}
          <div className="text-sm text-gray-700">
            <p className="font-medium">{primaryLocation}</p>
            {primaryAddress && <p className="text-gray-500 text-xs">{primaryAddress}</p>}
          </div>
        </div>

        {/* RIGHT COLUMN: Actions */}
        <div className="flex-shrink-0 flex flex-col items-end justify-center gap-3 min-w-[160px]">
          {/* Phone */}
          {primaryPhone && (
            <a
              href={`tel:${primaryPhone}`}
              className="flex items-center gap-2 text-sm text-gray-700 hover:text-[#003da5] transition-colors"
            >
              <Phone className="h-4 w-4" />
              <span>{primaryPhone}</span>
            </a>
          )}

          {/* Book Button */}
          {ProviderUniqueUrlOnesite && (
            <button
              onClick={() => window.open(ProviderUniqueUrlOnesite, "_blank")}
              className="w-full px-4 py-2 bg-[#003da5] text-white rounded-lg text-sm font-semibold hover:bg-[#002b73] transition-colors flex items-center justify-center gap-2"
            >
              <Globe className="h-4 w-4" />
              View Profile & Book
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function FilterBar({ providers, onFilteredChange }) {
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState({
    acceptingNewPatients: false,
    virtualCare: false,
    gender: "all",
    language: "all",
    sortBy: "distance", // distance, rating, name
  });

  // Extract unique filter options
  const uniqueLanguages = [...new Set(providers.flatMap(p => p.Languages || []))].sort();
  const hasDistanceData = providers.some(p => p.distance !== null && p.distance !== undefined);

  useEffect(() => {
    applyFilters();
  }, [filters, providers]);

  const applyFilters = () => {
    let filtered = [...providers];

    // Apply accepting new patients filter
    if (filters.acceptingNewPatients) {
      filtered = filtered.filter(p => p.AcceptingNewPatients === 1);
    }

    // Apply virtual care filter
    if (filters.virtualCare) {
      filtered = filtered.filter(p => p.VirtualCare === 1);
    }

    // Apply gender filter
    if (filters.gender !== "all") {
      filtered = filtered.filter(p => p.Gender === filters.gender);
    }

    // Apply language filter
    if (filters.language !== "all") {
      filtered = filtered.filter(p => 
        (p.Languages || []).some(lang => lang === filters.language)
      );
    }

    // Apply sorting
    if (filters.sortBy === "distance" && hasDistanceData) {
      filtered.sort((a, b) => (a.distance || 999) - (b.distance || 999));
    } else if (filters.sortBy === "rating") {
      filtered.sort((a, b) => (parseFloat(b.Rating || 0)) - (parseFloat(a.Rating || 0)));
    } else if (filters.sortBy === "name") {
      filtered.sort((a, b) => (a.Name || "").localeCompare(b.Name || ""));
    }

    onFilteredChange(filtered);
  };

  const resetFilters = () => {
    setFilters({
      acceptingNewPatients: false,
      virtualCare: false,
      gender: "all",
      language: "all",
      sortBy: hasDistanceData ? "distance" : "name",
    });
  };

  const activeFilterCount = Object.values(filters).filter(v => 
    v !== false && v !== "all" && v !== (hasDistanceData ? "distance" : "name")
  ).length;

  return (
    <div className="mb-4">
      <div className="flex justify-end">
        <button
          onClick={() => setShowFilters(!showFilters)}
          className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
        >
          <Filter className="h-4 w-4" />
          Filters
          {activeFilterCount > 0 && (
            <span className="ml-1 px-2 py-0.5 bg-[#003da5] text-white rounded-full text-xs">
              {activeFilterCount}
            </span>
          )}
        </button>
      </div>

      {showFilters && (
        <div className="mt-3 p-4 border border-gray-200 rounded-lg bg-gray-50">
          <div className="flex justify-between items-center mb-3">
            <h4 className="font-semibold text-gray-900">Filter Providers</h4>
            <button
              onClick={resetFilters}
              className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
            >
              <X className="h-3 w-3" />
              Clear All
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Accepting New Patients */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={filters.acceptingNewPatients}
                onChange={(e) => setFilters(prev => ({ ...prev, acceptingNewPatients: e.target.checked }))}
                className="w-4 h-4 text-[#003da5] border-gray-300 rounded focus:ring-[#003da5]"
              />
              <span className="text-sm">Accepting New Patients</span>
            </label>

            {/* Virtual Care */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={filters.virtualCare}
                onChange={(e) => setFilters(prev => ({ ...prev, virtualCare: e.target.checked }))}
                className="w-4 h-4 text-[#003da5] border-gray-300 rounded focus:ring-[#003da5]"
              />
              <span className="text-sm">Offers Virtual Care</span>
            </label>

            {/* Gender Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Gender</label>
              <select
                value={filters.gender}
                onChange={(e) => setFilters(prev => ({ ...prev, gender: e.target.value }))}
                className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-[#003da5] focus:border-transparent"
              >
                <option value="all">All</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
              </select>
            </div>

            {/* Language Filter */}
            {uniqueLanguages.length > 1 && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Language</label>
                <select
                  value={filters.language}
                  onChange={(e) => setFilters(prev => ({ ...prev, language: e.target.value }))}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-[#003da5] focus:border-transparent"
                >
                  <option value="all">All Languages</option>
                  {uniqueLanguages.map(lang => (
                    <option key={lang} value={lang}>{lang}</option>
                  ))}
                </select>
              </div>
            )}

            {/* Sort By */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Sort By</label>
              <select
                value={filters.sortBy}
                onChange={(e) => setFilters(prev => ({ ...prev, sortBy: e.target.value }))}
                className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-[#003da5] focus:border-transparent"
              >
                {hasDistanceData && <option value="distance">Distance</option>}
                <option value="rating">Rating</option>
                <option value="name">Name (A-Z)</option>
              </select>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function App() {
  const toolOutput = useOpenAiGlobal("toolOutput");
  const [providers, setProviders] = useState([]);
  const [filteredProviders, setFilteredProviders] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    console.log(`[Provider List Widget v${WIDGET_VERSION}] Initializing...`);
    console.log("[Provider List] toolOutput from hook:", toolOutput);

    if (toolOutput && toolOutput.providers && toolOutput.providers.length > 0) {
      console.log(`[Provider List] ✅ Received ${toolOutput.providers.length} providers from toolOutput`);
      setProviders(toolOutput.providers);
      setFilteredProviders(toolOutput.providers);
      setIsLoading(false);
    } else if (toolOutput && toolOutput.providers && toolOutput.providers.length === 0) {
      console.log("[Provider List] No providers returned");
      setProviders([]);
      setFilteredProviders([]);
      setIsLoading(false);
    }
  }, [toolOutput]);

  return (
    <div className="antialiased w-full text-black px-4 pb-2 border border-black/10 rounded-2xl sm:rounded-3xl overflow-hidden bg-white">
      <div className="max-w-full">
        {/* Header */}
        <div className="flex flex-row items-center gap-4 sm:gap-4 border-b border-black/5 py-4">
          <div className="sm:w-18 w-16 aspect-square rounded-xl bg-white flex items-center justify-center p-2">
            <img
              src="https://provgpt.azurewebsites.net/static/Prov.png"
              alt="Providence Health"
              className="w-full h-full object-contain"
            />
          </div>
          <div className="flex-1">
            <div className="text-base sm:text-xl font-medium">
              {toolOutput?.search_query || "Provider Search Results"}
            </div>
            <div className="text-sm text-black/60">
              {toolOutput?.location ? `Near ${toolOutput.location}` : "Providence providers"}
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="min-w-full text-sm">
          {isLoading ? (
            <div className="py-8 text-center text-gray-500">
              <div className="animate-pulse">Loading providers...</div>
            </div>
          ) : providers.length === 0 ? (
            <div className="py-8 text-center text-gray-500">
              No providers found matching your criteria.
            </div>
          ) : (
            <>
              {/* Results Count and Filter Bar */}
              <div className="py-3">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm text-gray-600">
                    Showing {filteredProviders.length} of {providers.length} provider{providers.length !== 1 ? "s" : ""}
                  </div>
                </div>

                {/* Filter Bar */}
                <FilterBar
                  providers={providers}
                  onFilteredChange={setFilteredProviders}
                />
              </div>

              {/* Provider List */}
              <div className="space-y-4 mt-4">
                {filteredProviders.map((provider, idx) => (
                  <ProviderCard
                    key={provider.id || idx}
                    provider={provider}
                  />
                ))}
              </div>

              {filteredProviders.length === 0 && providers.length > 0 && (
                <div className="py-8 text-center text-gray-500">
                  No providers match the selected filters. Try adjusting your filters.
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

createRoot(document.getElementById("provider-list-root")).render(<App />);

