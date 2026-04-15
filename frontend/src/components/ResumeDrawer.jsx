import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Briefcase } from "lucide-react";
import { HighlightedText } from "../utils/highlighter";

export default function ResumeDrawer({
  isOpen,
  onClose,
  candidate,
  query = "",
}) {
  React.useEffect(() => {
    if (isOpen) document.body.style.overflow = "hidden";
    else document.body.style.overflow = "unset";
    return () => {
      document.body.style.overflow = "unset";
    };
  }, [isOpen]);

  const pdfUrl = candidate.resume_url
    ? candidate.resume_url
    : `${import.meta.env.VITE_API_URL}/resume/${candidate.candidate_id}`;

  return (
    <AnimatePresence>
      {isOpen && candidate && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40 transition-opacity"
            aria-hidden="true"
          />

          <motion.div
            initial={{ x: "100%", boxShadow: "0 0 0 rgba(0,0,0,0)" }}
            animate={{ x: 0, boxShadow: "-20px 0 50px -10px rgba(0,0,0,0.3)" }}
            exit={{ x: "100%", boxShadow: "0 0 0 rgba(0,0,0,0)" }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            className="fixed top-0 right-0 h-full w-full sm:w-[600px] bg-white dark:bg-zinc-950 border-l border-zinc-200 dark:border-zinc-800 z-50 overflow-y-auto flex flex-col"
            role="dialog"
            aria-modal="true"
          >
            <div className="sticky top-0 bg-white/80 dark:bg-zinc-950/80 backdrop-blur-xl border-b border-zinc-200 dark:border-zinc-800 p-6 flex items-center justify-between z-10">
              <h2 className="text-lg font-bold text-zinc-900 dark:text-stone-100 uppercase tracking-widest">
                Candidate Profile
              </h2>
              <button
                onClick={onClose}
                className="p-2 rounded-full hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-500 dark:text-zinc-400 hover:text-gold transition-colors"
              >
                <X size={24} />
              </button>
            </div>

            <div className="p-6 space-y-8 flex-1">
              <div className="space-y-3">
                <h1 className="text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-gold-dark via-gold to-gold-light">
                  {candidate.display_name || "Unknown Candidate"}
                </h1>
                <p className="text-lg font-medium text-zinc-600 dark:text-zinc-400 flex items-center gap-2">
                  <Briefcase size={20} className="text-gold" />
                  {candidate.role || "Professional"}
                </p>
                <div className="inline-flex items-center gap-2 px-3 py-1 mt-2 rounded-full bg-zinc-100 dark:bg-zinc-800 border border-zinc-200 dark:border-zinc-700">
                  <span className="text-sm font-bold text-zinc-700 dark:text-zinc-300">
                    Match Score:
                  </span>
                  <span className="text-sm font-black text-gold">
                    {Math.round(candidate.score ?? candidate.match_score ?? 0)}%
                  </span>
                </div>
              </div>

              <div className="space-y-3">
                <h3 className="text-sm font-semibold uppercase tracking-widest text-gold-dark dark:text-gold">
                  Original Document
                </h3>
                <iframe
                  src={pdfUrl}
                  className="w-full h-[600px] rounded-xl border border-zinc-200 dark:border-zinc-800"
                  title="Resume PDF"
                />
              </div>

              {candidate.skills && candidate.skills.length > 0 && (
                <div className="space-y-4">
                  <h3 className="text-sm font-semibold uppercase tracking-widest text-zinc-500 dark:text-zinc-400">
                    Extracted Skills
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {candidate.skills.map((skill, idx) => (
                      <span
                        key={idx}
                        className="px-3 py-1.5 text-sm font-medium rounded-lg bg-stone-50 dark:bg-zinc-900 text-zinc-800 dark:text-zinc-200 border border-zinc-200 dark:border-zinc-800 shadow-sm"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {candidate.evidence && candidate.evidence.length > 0 && (
                <div className="space-y-4 pb-12">
                  <h3 className="text-sm font-semibold uppercase tracking-widest text-gold-dark dark:text-gold">
                    Relevance Evidence
                  </h3>
                  <div className="space-y-3">
                    {candidate.evidence.map((ev, idx) => (
                      <div
                        key={idx}
                        className="bg-white/50 dark:bg-zinc-900/50 backdrop-blur-md rounded-xl p-4 border border-zinc-200/50 dark:border-zinc-800/50 shadow-sm"
                      >
                        <p className="text-zinc-700 dark:text-zinc-300 whitespace-pre-wrap font-sans text-sm leading-relaxed">
                          <HighlightedText text={ev.text} query={query} />
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
