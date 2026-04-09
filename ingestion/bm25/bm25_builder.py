"""
BM25 index builder for resume retrieval.

Builds a persistent BM25Okapi index for keyword-based retrieval.
"""

import os
import pickle
from typing import Any, Dict, List, Optional

try:
    from rank_bm25 import BM25Okapi
except ImportError:  # pragma: no cover - environment dependent
    BM25Okapi = None


_INDEX_DIR = os.path.join("data", "bm25_index")
_INDEX_FILE = os.path.join(_INDEX_DIR, "bm25.pkl")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _tokenize(text: str) -> List[str]:
    return text.lower().split()


def build_bm25_index(chunks: List[Dict[str, Any]]) -> None:
    """
    Build and persist BM25 index.

    Stores:
      - bm25 model
      - tokenized corpus
      - mapping index -> chunk_id
      - mapping index -> candidate_id
      - raw texts (for preview)
    """
    if BM25Okapi is None:
        print("WARNING: rank_bm25 not installed. Skipping BM25 build.")
        return

    if not chunks:
        print("WARNING: No chunks provided. Skipping BM25 build.")
        return

    corpus_tokens: List[List[str]] = []
    index_to_chunk_id: List[str] = []
    index_to_candidate_id: List[str] = []
    index_to_text: List[str] = []

    for chunk in chunks:
        text = (chunk.get("text") or "").strip()
        candidate_id = chunk.get("candidate_id")

        if not text:
            continue
        if not candidate_id:
            continue

        tokens = _tokenize(text)
        if not tokens:
            continue

        corpus_tokens.append(tokens)
        index_to_chunk_id.append(chunk.get("chunk_id", ""))
        index_to_candidate_id.append(candidate_id)
        index_to_text.append(text)

    if not corpus_tokens:
        print("WARNING: No valid chunks after filtering. Skipping BM25 build.")
        return

    bm25 = BM25Okapi(corpus_tokens)

    _ensure_dir(_INDEX_DIR)

    payload = {
        "bm25": bm25,
        "corpus_tokens": corpus_tokens,
        "index_to_chunk_id": index_to_chunk_id,
        "index_to_candidate_id": index_to_candidate_id,
        "index_to_text": index_to_text,
    }

    with open(_INDEX_FILE, "wb") as f:
        pickle.dump(payload, f)

    print(f"BM25 index saved to: {_INDEX_FILE}")
    print(f"Total documents indexed: {len(corpus_tokens)}")


def load_bm25_index() -> Optional[Dict[str, Any]]:
    """
    Load BM25 index from disk.

    Returns:
        Dictionary payload or None if missing.
    """
    if not os.path.isfile(_INDEX_FILE):
        print("WARNING: BM25 index file not found.")
        return None

    with open(_INDEX_FILE, "rb") as f:
        return pickle.load(f)


def validate_bm25_index() -> None:
    """
    Validate BM25 index by printing stats and sample entries.
    """
    data = load_bm25_index()
    if not data:
        print("WARNING: No BM25 index available for validation.")
        return

    corpus_tokens = data.get("corpus_tokens", [])
    index_to_chunk_id = data.get("index_to_chunk_id", [])
    index_to_candidate_id = data.get("index_to_candidate_id", [])
    index_to_text = data.get("index_to_text", [])

    total = len(corpus_tokens)
    print(f"Total documents: {total}")

    sample_count = min(2, total)
    for i in range(sample_count):
        chunk_id = index_to_chunk_id[i] if i < len(index_to_chunk_id) else ""
        candidate_id = (
            index_to_candidate_id[i] if i < len(index_to_candidate_id) else ""
        )
        text = index_to_text[i] if i < len(index_to_text) else ""
        preview = (text[:100] + "...") if len(text) > 100 else text

        print("\nSample Entry:")
        print(f"chunk_id: {chunk_id}")
        print(f"candidate_id: {candidate_id}")
        print(f"text preview: {preview}")


if __name__ == "__main__":
    print("Running BM25 validation...")
    validate_bm25_index()
