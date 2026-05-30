import React, { useEffect, useRef, useState } from "react";
import * as anime from "animejs";

const STATUS_MESSAGES = [
  "Extracting Text...",
  "Generating 384-D Embeddings...",
  "Indexing in Supabase...",
];

export default function VectorProcessingLoader() {
  const loaderRef = useRef(null);
  const [statusIndex, setStatusIndex] = useState(0);

  useEffect(() => {
    const nodes = loaderRef.current?.querySelectorAll(".matrix-node");
    if (!nodes || nodes.length === 0) return undefined;

    const timeline = anime
      .createTimeline({
        loop: true,
        alternate: true,
      })
      .add(nodes, {
        scale: [0.3, 1],
        opacity: [0.2, 1],
        delay: anime.stagger(100, { grid: [4, 4], from: "center" }),
        duration: 700,
        ease: "inOutSine",
      });

    return () => {
      timeline.cancel?.();
    };
  }, []);

  useEffect(() => {
    const interval = window.setInterval(() => {
      setStatusIndex((current) => (current + 1) % STATUS_MESSAGES.length);
    }, 1400);

    return () => window.clearInterval(interval);
  }, []);

  return (
    <div ref={loaderRef} className="mt-7">
      <div className="grid grid-cols-4 gap-2 w-32 h-32 mx-auto">
        {Array.from({ length: 16 }).map((_, index) => (
          <div
            key={index}
            className="matrix-node w-full h-full bg-gold/20 rounded-md shadow-[0_0_10px_rgba(212,175,55,0.5)]"
          />
        ))}
      </div>
      <p className="mt-4 text-sm font-semibold tracking-wide text-gold-dark dark:text-gold">
        {STATUS_MESSAGES[statusIndex]}
      </p>
    </div>
  );
}
