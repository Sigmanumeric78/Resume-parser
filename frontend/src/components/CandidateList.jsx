import React, { useEffect, useRef } from "react";
import * as anime from "animejs";
import CandidateCard from "./CandidateCard";

export default function CandidateList({
  resultsArray = [],
  onClickViewResume,
  query,
}) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!resultsArray.length || !containerRef.current) return undefined;

    const cards = containerRef.current.querySelectorAll(".candidate-result-card");
    if (!cards.length) return undefined;

    anime.utils.remove(cards);
    anime.utils.set(cards, {
      translateX: 50,
      opacity: 0,
    });

    const animation = anime.animate(cards, {
      translateX: [50, 0],
      opacity: [0, 1],
      delay: anime.stagger(80),
      ease: "outBack",
      duration: 800,
    });

    return () => {
      animation.cancel?.();
    };
  }, [resultsArray]);

  if (!resultsArray.length) {
    return null;
  }

  return (
    <div ref={containerRef} className="grid gap-6">
      {resultsArray.map((candidate, idx) => (
        <CandidateCard
          key={candidate.candidate_id || idx}
          candidate={candidate}
          onClickViewResume={onClickViewResume}
          query={query}
        />
      ))}
    </div>
  );
}
