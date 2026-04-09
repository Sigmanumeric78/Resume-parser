from __future__ import annotations

import sys
from typing import Any, Iterable, List

from backend.services.search_service import search_service

QUERIES = [
    ("Direct Match", "Media Activities Specialist"),
    ("Skill Match", "Azure and Python and Active Directory"),
    ("Semantic/Conceptual", "Aerospace quality control professional"),
]


def _get(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _tokenize(text: str) -> List[str]:
    return [t for t in (text or "").lower().split() if t]


def _check_evidence_relevance(query: str, highlights: Iterable[str]) -> bool:
    tokens = _tokenize(query)
    if not tokens:
        return False
    for snippet in highlights:
        lower = (snippet or "").lower()
        if any(t in lower for t in tokens):
            return True
    return False


def run_query(label: str, query: str) -> None:
    print(f"\n=== {label} ===")
    print(f"Query: {query}")

    results = search_service.search(query, top_n=10)
    if not results:
        print("No results returned.")
        return

    top5 = results[:5]
    ids = [_get(r, "candidate_id", "") for r in top5]
    unique_ids = set(ids)

    if len(unique_ids) != len(ids):
        print("WARNING: Top 5 results contain duplicate candidate_id values.")
    else:
        print("Top 5 candidates are unique.")

    for idx, item in enumerate(top5, start=1):
        candidate_id = _get(item, "candidate_id", "")
        display_name = _get(item, "display_name", "")
        match_score = _get(item, "match_score", 0.0)
        highlights = _get(item, "highlights", []) or []

        if not display_name:
            print(f"WARNING: Missing display_name for {candidate_id}")

        print(f"\n#{idx} {candidate_id} | {display_name} | score={match_score:.2f}")
        for h_idx, h in enumerate(highlights, start=1):
            preview = h.replace("\n", " ")[:200]
            print(f"  - Highlight {h_idx}: {preview}")

        if not _check_evidence_relevance(query, highlights):
            print("  WARNING: Highlights may not relate to the query.")


def main() -> int:
    for label, query in QUERIES:
        run_query(label, query)
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
