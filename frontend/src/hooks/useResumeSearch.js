import { useState, useEffect } from "react";
import axios from "axios";

export function useResumeSearch() {
  const [query, setQuery] = useState("");
  const [topN, setTopN] = useState(5);
  const [results, setResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    // Clear results if query is empty
    if (!query.trim()) {
      setResults([]);
      setIsSearching(false);
      setError(null);
      return;
    }

    // Set a debounce timer for 300ms
    const debounceTimer = setTimeout(async () => {
      setIsSearching(true);
      setError(null);

      try {
        // Fetch results from the verified backend
        const response = await axios.post(
          `${import.meta.env.VITE_API_URL}/api/search`,
          {
            query,
            top_n: topN,
          },
        );

        // Handle various potential response formats flexibly
        const searchResults = response.data.results || response.data || [];
        setResults(searchResults);
      } catch (err) {
        console.error("Search API Error:", err);
        setError(
          err.response?.data?.detail ||
            err.message ||
            "An error occurred while searching.",
        );
        setResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 300);

    // Cleanup the timer on consecutive key presses (debounce logic)
    return () => clearTimeout(debounceTimer);
  }, [query, topN, refreshKey]);

  const refreshResults = () => {
    setRefreshKey((value) => value + 1);
  };

  return {
    query,
    setQuery,
    results,
    isSearching,
    error,
    topN,
    setTopN,
    refreshResults,
  };
}
