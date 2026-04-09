import React, { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useResumeSearch } from "./hooks/useResumeSearch";
import SearchHeader from "./components/SearchHeader";
import CandidateCard from "./components/CandidateCard";
import ResumeDrawer from "./components/ResumeDrawer";
import EmptyState from "./components/EmptyState";

export default function App() {
  const { query, setQuery, results, isSearching, error, topN, setTopN } =
    useResumeSearch();

  const [selectedCandidate, setSelectedCandidate] = useState(null);

  const handleViewResume = (candidate) => {
    setSelectedCandidate(candidate);
  };

  const closeDrawer = () => {
    setSelectedCandidate(null);
  };

  return (
    <div className="min-h-screen font-sans transition-colors duration-500 bg-[var(--color-bg-primary)] text-[var(--color-text-main)]">
      <SearchHeader
        query={query}
        setQuery={setQuery}
        isSearching={isSearching}
        topN={topN}
        setTopN={setTopN}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-8 p-4 rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400">
            <p className="font-semibold">Error retrieving results</p>
            <p className="text-sm">{error}</p>
          </div>
        )}

        <AnimatePresence mode="popLayout">
          {results && results.length > 0 ? (
            <motion.div
              key="results"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="space-y-6"
            >
              {results.map((candidate, idx) => (
                <CandidateCard
                  key={candidate.candidate_id || idx}
                  candidate={candidate}
                  onClickViewResume={handleViewResume}
                  index={idx}
                  query={query}
                />
              ))}
            </motion.div>
          ) : (
            <EmptyState key="empty" query={query} isSearching={isSearching} />
          )}
        </AnimatePresence>
      </main>

      <ResumeDrawer
        isOpen={!!selectedCandidate}
        onClose={closeDrawer}
        candidate={selectedCandidate}
        query={query}
      />
    </div>
  );
}
