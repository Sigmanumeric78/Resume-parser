import React from "react";
// eslint-disable-next-line no-unused-vars
import { motion, AnimatePresence } from "framer-motion";

export default function ScoreGauge({ score = 0, size = 56, strokeWidth = 5 }) {
  // Ensure score is clamped between 0 and 100
  const clampedScore = Math.max(0, Math.min(100, score));

  const center = size / 2;
  const radius = center - strokeWidth;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (clampedScore / 100) * circumference;

  return (
    <div
      className="relative flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="transform -rotate-90"
      >
        <defs>
          <linearGradient id="goldGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#996515" />
            <stop offset="45%" stopColor="#D4AF37" />
            <stop offset="50%" stopColor="#F4DF4E" />
            <stop offset="55%" stopColor="#D4AF37" />
            <stop offset="100%" stopColor="#996515" />
          </linearGradient>

          <filter id="goldGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Background Track */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="transparent"
          strokeWidth={strokeWidth}
          className="stroke-zinc-200 dark:stroke-zinc-800"
        />

        {/* Animated Progress Gauge */}
        <motion.circle
          cx={center}
          cy={center}
          r={radius}
          fill="transparent"
          strokeWidth={strokeWidth}
          stroke="url(#goldGradient)"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset }}
          transition={{
            duration: 1.5,
            ease: "easeOut",
            type: "spring",
            bounce: 0.2,
          }}
          className="drop-shadow-none dark:drop-shadow-[0_0_8px_rgba(212,175,55,0.6)]"
        />
      </svg>

      {/* Score Text */}
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-sm font-black text-zinc-900 dark:text-stone-100">
          {Math.round(clampedScore)}
        </span>
      </div>

      {/* Golden Sparkles for High Scores */}
      <AnimatePresence>
        {clampedScore > 90 && (
          <>
            {[...Array(4)].map((_, i) => (
              <motion.span
                key={i}
                className="absolute rounded-full z-50"
                style={{
                  width: 6,
                  height: 6,
                  top: "50%",
                  left: "50%",
                  marginTop: -3,
                  marginLeft: -3,
                  backgroundColor: "var(--color-gold-light)",
                  boxShadow: "0 0 10px 2px var(--color-gold-light)",
                }}
                initial={{ opacity: 0, scale: 0, x: 0, y: 0 }}
                animate={{
                  opacity: [0, 1, 0],
                  scale: [0, 1.5, 0.5],
                  x: Math.cos((i * Math.PI) / 2) * (size / 1.5),
                  y: Math.sin((i * Math.PI) / 2) * (size / 1.5),
                }}
                transition={{
                  duration: 1.2,
                  delay: 1.2,
                  ease: "easeOut",
                  times: [0, 0.2, 1],
                }}
              />
            ))}
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
