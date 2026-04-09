"""
Search service implementing Reciprocal Rank Fusion (RRF) over ChromaDB and BM25.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, cast

from ingestion.bm25.bm25_builder import load_bm25_index
from ingestion.db.chroma_builder import get_collection
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
        self._collection = None
        self._embedder: Optional[Embedder] = None
        self._model_name = model_name
        self._loaded = False

    def load_indices(self) -> None:
        self._bm25_data = load_bm25_index()
        self._collection = get_collection()
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
        if self._collection is None or self._embedder is None:
            return []

        query_embeddings = self._embedder._embed_texts([query])
        if not query_embeddings:
            return []

        try:
            result = self._collection.query(
                query_embeddings=cast(Any, query_embeddings),
                n_results=top_k,
                include=cast(Any, ["documents", "metadatas", "distances"]),
            )
        except Exception:
            return []

        if result is None or not isinstance(result, dict):
            return []
        # Use explicit unpacking to satisfy Pyright
        docs_raw = result.get("documents")
        docs = docs_raw[0] if docs_raw and len(docs_raw) > 0 else []

        metas_raw = result.get("metadatas")
        metas = metas_raw[0] if metas_raw and len(metas_raw) > 0 else []

        results: List[Dict[str, Any]] = []
        for idx, meta in enumerate(metas):
            if not isinstance(meta, dict):
                continue
            candidate_id = meta.get("candidate_id", "")
            text = docs[idx] if idx < len(docs) else ""
            if candidate_id:
                results.append(
                    {
                        "candidate_id": candidate_id,
                        "text": text,
                        "metadata": meta,
                    }
                )
        return results

    def search(
        self, query: str, top_n: int = 20, rrf_k: int = 60
    ) -> List[SearchResult]:
        self._ensure_loaded()
        query = (query or "").strip()
        if not query:
            return []

        query_tokens = _tokenize(query)

        semantic_results = self._search_chroma(query, top_k=50)
        bm25_results = self._search_bm25(query, top_k=50)

        rrf_scores: Dict[str, float] = {}
        best_meta: Dict[str, Dict[str, Any]] = {}
        evidence_map: Dict[str, List[Evidence]] = {}

        # RRF from semantic results
        for rank, item in enumerate(semantic_results, start=1):
            cand_id = item["candidate_id"]
            rrf_scores[cand_id] = rrf_scores.get(cand_id, 0.0) + 1.0 / (rrf_k + rank)
            meta = item.get("metadata") or {}
            if cand_id not in best_meta:
                best_meta[cand_id] = meta
            text = _safe_str(item.get("text"))
            section = _safe_str(meta.get("section"))
            if text:
                evidence_map.setdefault(cand_id, []).append(
                    Evidence(text=text, section=section, source="semantic")
                )

        # RRF from BM25 results
        for rank, item in enumerate(bm25_results, start=1):
            cand_id = item["candidate_id"]
            rrf_scores[cand_id] = rrf_scores.get(cand_id, 0.0) + 1.0 / (rrf_k + rank)
            text = _safe_str(item.get("text"))
            if text:
                evidence_map.setdefault(cand_id, []).append(
                    Evidence(text=text, section="", source="bm25")
                )

        # Build results
        combined = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        output: List[SearchResult] = []
        max_score = max(rrf_scores.values()) if rrf_scores else 0.0

        for cand_id, score in combined[: max(1, top_n)]:
            meta = best_meta.get(cand_id, {})
            display_name = _safe_str(meta.get("name")) or _safe_str(
                meta.get("candidate_name")
            )
            skills = _normalize_skills(meta.get("skills"))
            evidence = evidence_map.get(cand_id, [])
            highlights = _select_highlights(query_tokens, evidence, max_items=3)

            match_score = (score / max_score * 100.0) if max_score > 0 else 0.0

            output.append(
                SearchResult(
                    candidate_id=cand_id,
                    display_name=display_name,
                    match_score=match_score,
                    skills=skills,
                    highlights=highlights,
                    evidence=evidence,
                )
            )

        return output


search_service = SearchService()
