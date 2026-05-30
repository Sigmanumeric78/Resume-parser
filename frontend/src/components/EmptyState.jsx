import React, { useMemo } from "react";
// eslint-disable-next-line no-unused-vars
import { motion } from "framer-motion";
import { SearchX, Sparkles } from "lucide-react";

const SUGGESTION_POOL = [
  "Senior React Developer",
  "Python Machine Learning",
  "AWS Infrastructure",
  "Product Manager B2B",
  "Data Engineer Spark",
  "Frontend TypeScript Lead",
  "DevOps Kubernetes",
  "Cybersecurity Analyst",
  "Cloud Solutions Architect",
  "Backend FastAPI Engineer",
  "Mobile React Native",
  "AI Research Engineer",
  "Salesforce Administrator",
  "UX Product Designer",
  "Java Spring Boot",
  "Healthcare Data Analyst",
];

function getRandomSuggestions(count = 4) {
  return [...SUGGESTION_POOL].sort(() => Math.random() - 0.5).slice(0, count);
}

export default function EmptyState({ query, isSearching, onSelectSuggestion }) {
  const suggestions = useMemo(() => getRandomSuggestions(), []);

  if (isSearching) return null;

  const isInitial = !query || query.trim().length === 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="flex flex-col items-center justify-center py-24 px-4 text-center"
    >
      <motion.div
        initial={{ scale: 0.8, rotate: isInitial ? -10 : 0 }}
        animate={{ scale: 1, rotate: 0 }}
        transition={{ type: "spring", stiffness: 200, damping: 20 }}
        className="w-24 h-24 mb-8 rounded-full bg-gradient-to-br from-gold-light/20 via-gold/10 to-transparent dark:from-gold-dark/30 dark:to-transparent flex items-center justify-center text-gold shadow-[0_0_40px_-10px_rgba(212,175,55,0.3)]"
      >
        {isInitial ? (
          <Sparkles size={48} strokeWidth={1.5} />
        ) : (
          <SearchX size={48} strokeWidth={1.5} />
        )}
      </motion.div>

      <h3 className="text-3xl font-extrabold text-[var(--color-text-main)] mb-4 tracking-tighter">
        {isInitial ? "Discover Exceptional Talent" : "No Candidates Found"}
      </h3>

      <p className="text-lg text-zinc-600 dark:text-zinc-400 max-w-lg mx-auto leading-relaxed">
        {isInitial
          ? "Type skills, job titles, or specific project experience to instantly match with the highest-scoring resumes in your database."
          : `We couldn't find any strong matches for "${query}". Try using fewer words or broader skill categories.`}
      </p>

      {isInitial && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.2 }}
          className="mt-10"
        >
          <p className="text-sm font-semibold text-zinc-500 dark:text-zinc-500 uppercase tracking-widest mb-4">
            Suggested Searches
          </p>
          <div className="flex flex-wrap justify-center gap-3 max-w-xl mx-auto">
            {suggestions.map((suggestion, idx) => (
              <motion.button
                key={idx}
                type="button"
                onClick={() => onSelectSuggestion?.(suggestion)}
                whileHover={{ scale: 1.05 }}
                className="px-5 py-2.5 text-sm font-medium rounded-full bg-white text-zinc-900 border-2 border-zinc-200 shadow-sm hover:border-gold hover:text-gold dark:bg-zinc-900 dark:text-stone-200 dark:border-zinc-800 dark:hover:border-gold-light transition-all cursor-pointer raised-hover"
              >
                {suggestion}
              </motion.button>
            ))}
          </div>
        </motion.div>
      )}
    </motion.div>
  );
}
