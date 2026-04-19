"""
Search service implementing absolute scoring over ChromaDB and BM25.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from supabase import Client, create_client

from ingestion.bm25.bm25_builder import load_bm25_index
from ingestion.embedding.embedder import Embedder


@dataclass
class Evidence:
    text: str
    section: str
    source: str


@dataclass
class SearchResult:
    candidate_id: str
    display_name: str
    match_score: float
    skills: List[str]
    highlights: List[str]
    evidence: List[Evidence]
    resume_url: str


def _tokenize(text: str) -> List[str]:
    return (text or "").lower().split()


def _safe_str(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _normalize_skills(raw: Any) -> List[str]:
    if isinstance(raw, list):
        return [str(s).strip() for s in raw if str(s).strip()]
    if isinstance(raw, str):
        return [s.strip() for s in raw.split(",") if s.strip()]
    return []


def _select_highlights(
    query_tokens: List[str], evidence: List[Evidence], max_items: int = 3
) -> List[str]:
    if not evidence:
        return []

    tokens = [t for t in query_tokens if t]
    scored: List[tuple[int, str]] = []

    for ev in evidence:
        text = _safe_str(ev.text)
        if not text:
            continue
        lower = text.lower()
        hit_count = sum(1 for t in tokens if t in lower)
        scored.append((hit_count, text))

    scored.sort(key=lambda x: (x[0], len(x[1])), reverse=True)
    highlights = [text for _, text in scored[:max_items]]

    if not highlights:
        highlights = [_safe_str(ev.text) for ev in evidence if _safe_str(ev.text)][
            :max_items
        ]

    return highlights


class SearchService:
    """
    Hybrid retrieval using RRF over:
      - Semantic (ChromaDB)
      - Keyword (BM25)
    """

    def __init__(
        self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    ) -> None:
        self._bm25_data: Optional[Dict[str, Any]] = None
        self._embedder: Optional[Embedder] = None
        self._model_name = model_name
        self._loaded = False

        # Initialize Supabase
        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        self.supabase: Optional[Client] = None
        if supabase_url and supabase_key:
            self.supabase = create_client(supabase_url, supabase_key)

    def load_indices(self) -> None:
        self._bm25_data = load_bm25_index()
        try:
            self._embedder = Embedder(model_name=self._model_name)
        except Exception:
            self._embedder = None
        self._loaded = True

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load_indices()

    def _search_bm25(self, query: str, top_k: int = 50) -> List[Dict[str, Any]]:
        if not self._bm25_data:
            return []

        bm25 = self._bm25_data.get("bm25")
        corpus_tokens = self._bm25_data.get("corpus_tokens", [])
        index_to_candidate_id = self._bm25_data.get("index_to_candidate_id", [])
        index_to_text = self._bm25_data.get("index_to_text", [])

        if not bm25 or not corpus_tokens:
            return []

        query_tokens = _tokenize(query)
        if not query_tokens:
            return []
        scores = bm25.get_scores(query_tokens)
        if scores is None or len(scores) == 0:
            return []

        scored = list(enumerate(scores))
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_k]

        results: List[Dict[str, Any]] = []
        for idx, score in top:
            candidate_id = (
                index_to_candidate_id[idx] if idx < len(index_to_candidate_id) else ""
            )
            text = index_to_text[idx] if idx < len(index_to_text) else ""
            if candidate_id:
                results.append(
                    {
                        "candidate_id": candidate_id,
                        "score": float(score),
                        "text": text,
                    }
                )
        return results

    def _search_chroma(self, query: str, top_k: int = 50) -> List[Dict[str, Any]]:
        if self.supabase is None or self._embedder is None:
            return []

        query_embeddings = self._embedder._embed_texts([query])
        if not query_embeddings:
            return []

        query_embedding = query_embeddings[0]

        try:
            # Call the Supabase pgvector RPC function
            response = self.supabase.rpc(
                "match_resume_chunks",
                {
                    "query_embedding": query_embedding,
                    "match_threshold": 0.0,
                    "match_count": top_k,
                },
            ).execute()
            data = response.data
        except Exception as e:
            print(f"Supabase RPC error: {e}")
            return []

        if not data or not isinstance(data, list):
            return []

        results: List[Dict[str, Any]] = []
        for row in data:
            # 1. Reassure Pyright that this is a dictionary
            if not isinstance(row, dict):
                continue

            candidate_id = row.get("candidate_id", "")
            text = row.get("text", "")
            meta = row.get("metadata", {})

            # 2. Strict type guard for Pyright before casting to float
            raw_sim = row.get("similarity", 0.0)
            similarity = 0.0
            if isinstance(raw_sim, (int, float, str)):
                try:
                    similarity = float(raw_sim)
                except ValueError:
                    similarity = 0.0

            # Convert similarity to distance (1 - similarity)
            distance = 1.0 - similarity

            if candidate_id:
                results.append(
                    {
                        "candidate_id": candidate_id,
                        "text": text,
                        "metadata": meta,
                        "distance": float(distance),
                    }
                )
        return results

    def search(self, query: str, top_n: int = 20) -> List[SearchResult]:
        self._ensure_loaded()
        query = (query or "").strip()
        if not query:
            return []

        query_tokens = _tokenize(query)

        semantic_results = self._search_chroma(query, top_k=50)
        bm25_results = self._search_bm25(query, top_k=50)

        candidate_stats: Dict[str, Dict[str, float]] = {}
        best_meta: Dict[str, Dict[str, Any]] = {}
        evidence_map: Dict[str, List[Evidence]] = {}

        for item in semantic_results:
            cand_id = item["candidate_id"]
            stats = candidate_stats.setdefault(
                cand_id, {"min_distance": 999.0, "max_bm25": 0.0}
            )
            distance = float(item.get("distance", 999.0))
            stats["min_distance"] = min(stats.get("min_distance", 999.0), distance)

            meta = item.get("metadata") or {}
            if cand_id not in best_meta:
                best_meta[cand_id] = meta
            text = _safe_str(item.get("text"))
            section = _safe_str(meta.get("section"))
            if text:
                evidence_map.setdefault(cand_id, []).append(
                    Evidence(text=text, section=section, source="semantic")
                )

        for item in bm25_results:
            cand_id = item["candidate_id"]
            stats = candidate_stats.setdefault(
                cand_id, {"min_distance": 999.0, "max_bm25": 0.0}
            )
            score = float(item.get("score", 0.0))
            stats["max_bm25"] = max(stats.get("max_bm25", 0.0), score)

            text = _safe_str(item.get("text"))
            if text:
                evidence_map.setdefault(cand_id, []).append(
                    Evidence(text=text, section="", source="bm25")
                )

        scored_candidates: List[tuple[str, float]] = []
        for cand_id, stats in candidate_stats.items():
            min_distance = float(stats.get("min_distance", 999.0))
            max_bm25 = float(stats.get("max_bm25", 0.0))

            semantic_score = max(0.0, 100.0 - (min_distance * 50.0))
            keyword_score = min(100.0, max_bm25 * 5.0)
            blend = (semantic_score * 0.7) + (keyword_score * 0.3)
            final_score = min(99.0, blend * 1.15)

            scored_candidates.append((cand_id, final_score))

        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        output: List[SearchResult] = []
        for cand_id, final_score in scored_candidates[: max(1, top_n)]:
            meta = best_meta.get(cand_id, {})
            display_name = _safe_str(meta.get("name")) or _safe_str(
                meta.get("candidate_name")
            )
            skills = _normalize_skills(meta.get("skills"))
            evidence = evidence_map.get(cand_id, [])
            highlights = _select_highlights(query_tokens, evidence, max_items=3)
            url = _safe_str(meta.get("url"))

            output.append(
                SearchResult(
                    candidate_id=cand_id,
                    display_name=display_name,
                    match_score=round(final_score, 1),
                    skills=skills,
                    highlights=highlights,
                    evidence=evidence,
                    resume_url=url,
                )
            )

        return output


search_service = SearchService()
