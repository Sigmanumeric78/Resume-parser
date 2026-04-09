import React, { useState, useEffect } from "react";
import { Search, Loader2, Sun, Moon, SlidersHorizontal } from "lucide-react";
// eslint-disable-next-line no-unused-vars
import { motion } from "framer-motion";
import { clsx } from "clsx";
import { useTheme } from "../hooks/useTheme";

export default function SearchHeader({
  query,
  setQuery,
  isSearching,
  topN,
  setTopN,
}) {
  const { theme, toggleTheme } = useTheme();
  const [isAnimating, setIsAnimating] = useState(false);

  useEffect(() => {
    let timeout;
    if (isSearching) {
      timeout = setTimeout(() => setIsAnimating(true), 0);
    } else {
      timeout = setTimeout(() => setIsAnimating(false), 500);
    }
    return () => clearTimeout(timeout);
  }, [isSearching]);

  return (
    <header className="sticky top-0 z-50 backdrop-blur-xl bg-transparent transition-colors duration-500">
      <div className="flex items-center justify-between w-full max-w-7xl mx-auto px-6 py-4 gap-8">
        {/* Left: Branding */}
        <div className="flex items-center gap-3 flex-shrink-0">
          <motion.div
            whileHover={{ rotate: 5, scale: 1.1 }}
            whileTap={{ scale: 0.95 }}
          >
            <img
              src="/logo.png"
              alt="resumeRES-Q Logo"
              className="w-10 h-10 object-contain"
            />
          </motion.div>
          <h1 className="hidden sm:block text-xl font-bold text-gold tracking-tight">
            resumeRES-Q
          </h1>
        </div>

        {/* Center: Search Input */}
        <div className="relative group flex-grow max-w-2xl">
          {/* Animated Glow Background behind the input when searching */}
          {isSearching && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute -inset-1 bg-gradient-to-r from-gold-light via-gold to-gold-dark rounded-3xl blur opacity-30 animate-pulse"
            />
          )}

          <div className="relative flex items-center w-full">
            <Search
              className="absolute left-4 text-zinc-400 group-focus-within:text-gold transition-colors"
              size={24}
            />

            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by skills, roles, or experience... (e.g. 'Senior Python React')"
              className={clsx(
                "w-full pl-14 pr-14 py-3 text-lg rounded-2xl bg-white dark:bg-zinc-900/50 border-2 border-zinc-200/50 dark:border-zinc-700/50 focus:border-gold focus:shadow-[0_0_15px_rgba(212,175,55,0.2)] transition-all outline-none text-[var(--color-text-main)] placeholder-[var(--color-text-muted)]",
                isAnimating && "animate-pulse-gold",
              )}
            />

            <div className="absolute right-4 flex items-center justify-center w-8 h-8">
              {isSearching ? (
                <Loader2 className="animate-spin text-gold" size={24} />
              ) : (
                <kbd className="hidden sm:inline-block px-2 py-1 text-xs font-semibold text-zinc-400 bg-zinc-100 dark:bg-zinc-800 rounded-md border border-zinc-200 dark:border-zinc-700 shadow-sm">
                  /
                </kbd>
              )}
            </div>
          </div>
        </div>

        {/* Right: Controls Row */}
        <div className="flex items-center gap-6 flex-shrink-0">
          <div className="hidden lg:flex items-center gap-4 text-sm text-[var(--color-text-muted)]">
            <div className="flex items-center gap-2">
              <SlidersHorizontal size={16} />
              <span className="font-medium">Top {topN} Results</span>
            </div>
            <input
              type="range"
              min="1"
              max="20"
              value={topN}
              onChange={(e) => setTopN(parseInt(e.target.value))}
              className="w-32 accent-gold hover:accent-gold-light transition-all cursor-pointer"
            />
          </div>

          <button
            onClick={toggleTheme}
            className="p-2 rounded-full bg-white dark:bg-zinc-900 border-2 border-zinc-200 dark:border-zinc-800 transition-colors text-[var(--color-text-muted)] hover:text-gold dark:hover:text-gold raised-hover"
            aria-label="Toggle Theme"
          >
            {theme === "dark" ? <Sun size={20} /> : <Moon size={20} />}
          </button>
        </div>
      </div>
    </header>
  );
}
