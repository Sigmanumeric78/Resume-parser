import React, { useState } from "react";
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, ChevronUp, FileText } from "lucide-react";
import ScoreGauge from "./ScoreGauge";
import { HighlightedText } from "../utils/highlighter";

export default function CandidateCard({
  candidate,
  onClickViewResume,
  query = "",
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  const {
    display_name = "Unknown Candidate",
    score,
    match_score,
    skills = [],
    highlights = [],
    role = "Professional",
  } = candidate;

  // Use 'score' (new backend format) or fallback to 'match_score', default 0.
  // Do NOT multiply by 100 as the backend now returns an absolute 0-100 float.
  const rawScore = score ?? match_score ?? 0;
  const scorePercentage = Math.round(rawScore);

  return (
    <div className="candidate-result-card bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-200 dark:border-zinc-800 shadow-sm transition-all overflow-hidden">
      <div
        className="p-6 cursor-pointer flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <h3 className="text-xl font-bold text-zinc-900 dark:text-stone-100">
              {display_name}
            </h3>
            <span className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
              {role}
            </span>
          </div>

          <div className="flex flex-wrap gap-2 mt-3">
            {skills.slice(0, 4).map((skill, idx) => (
              <span
                key={idx}
                className="px-2.5 py-1 text-xs font-medium rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700"
              >
                {skill}
              </span>
            ))}
            {skills.length > 4 && (
              <span className="px-2.5 py-1 text-xs font-medium rounded-full bg-zinc-50 dark:bg-zinc-950 text-zinc-500 dark:text-zinc-400 border border-zinc-200 dark:border-zinc-800">
                +{skills.length - 4}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-4 w-full sm:w-auto justify-between sm:justify-end mt-4 sm:mt-0 pt-4 sm:pt-0 border-t border-zinc-100 dark:border-zinc-800/50 sm:border-0">
          <ScoreGauge score={scorePercentage} size={48} strokeWidth={4} />
          <button
            className="p-2 text-zinc-400 hover:text-gold dark:hover:text-gold transition-colors rounded-full bg-white dark:bg-zinc-900 border-2 border-zinc-200 dark:border-zinc-800 raised-hover"
            aria-label={isExpanded ? "Collapse details" : "Expand details"}
          >
            {isExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="overflow-hidden border-t border-zinc-100 dark:border-zinc-800/50 bg-stone-50/50 dark:bg-zinc-950/50"
          >
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-sm font-semibold text-zinc-900 dark:text-stone-200 uppercase tracking-wider">
                  Match Evidence
                </h4>
                {onClickViewResume && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onClickViewResume(candidate);
                    }}
                    className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-white dark:bg-zinc-900 text-gold-dark dark:text-gold border-2 border-zinc-200 dark:border-zinc-800 transition-colors raised-hover"
                  >
                    <FileText size={16} />
                    View Full Resume
                  </button>
                )}
              </div>

              <div className="space-y-3">
                {highlights.length > 0 ? (
                  highlights.map((highlight, idx) => (
                    <motion.div
                      key={idx}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.1 }}
                      className="pl-4 border-l-2 border-gold/50 dark:border-gold-dark/50"
                    >
                      <p className="text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed italic">
                        "<HighlightedText text={highlight} query={query} />"
                      </p>
                    </motion.div>
                  ))
                ) : (
                  <p className="text-sm text-zinc-500 dark:text-zinc-500 italic">
                    No specific highlights found for this match.
                  </p>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
