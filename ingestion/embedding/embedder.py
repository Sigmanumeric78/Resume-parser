"""
Sentence-transformer embedding utilities.

Provides:
- Embedder: simple wrapper around sentence-transformers
- embed_chunks: helper to attach embeddings to chunk dicts
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - environment dependent
    SentenceTransformer = None


class Embedder:
    """
    Lightweight embedding wrapper using sentence-transformers.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: Optional[str] = None,
        normalize_embeddings: bool = True,
        batch_size: int = 32,
    ) -> None:
        if SentenceTransformer is None:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Install it to enable embedding."
            )

        self.model_name = model_name
        self.device = device
        self.normalize_embeddings = normalize_embeddings
        self.batch_size = batch_size
        self._model = SentenceTransformer(model_name, device=device)

    def _embed_texts(self, texts: Iterable[str]) -> List[List[float]]:
        """
        Embed a list of texts and return list of embedding vectors.
        """
        text_list = [t for t in texts]
        if not text_list:
            return []
        embeddings = self._model.encode(
            text_list,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=False,
            batch_size=self.batch_size,
        )
        return [list(map(float, emb)) for emb in embeddings]


def embed_chunks(
    chunks: List[Dict[str, Any]],
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    device: Optional[str] = None,
    normalize_embeddings: bool = True,
    batch_size: int = 32,
) -> List[Dict[str, Any]]:
    """
    Attach embeddings to chunk dicts.

    Expects each chunk to contain a "text" field.
    Returns the same list with an "embedding" field added where possible.
    """
    if not chunks:
        return []

    embedder = Embedder(
        model_name=model_name,
        device=device,
        normalize_embeddings=normalize_embeddings,
        batch_size=batch_size,
    )

    texts: List[str] = [(chunk.get("text") or "").strip() for chunk in chunks]
    embeddings = embedder._embed_texts(texts)

    for chunk, emb in zip(chunks, embeddings):
        if isinstance(emb, list):
            chunk["embedding"] = emb

    return chunks
