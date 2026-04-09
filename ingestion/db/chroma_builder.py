"""
ChromaDB builder for embedded resume chunks.

Stores chunks in a persistent ChromaDB collection with validation.
"""

import os
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

try:
    import chromadb
except ImportError:  # pragma: no cover - environment dependent
    chromadb = None

_COLLECTION_NAME = "resumes"
_PERSIST_DIR = os.path.join("data", "chroma_db")

_client = None
_collection = None


def _get_client():
    global _client
    if _client is not None:
        return _client

    if chromadb is None:
        print("WARNING: chromadb is not installed. DB operations will be skipped.")
        return None

    _client = chromadb.PersistentClient(path=_PERSIST_DIR)
    return _client


def get_collection():
    """
    Return an active ChromaDB collection (persistent).
    """
    global _collection
    if _collection is not None:
        return _collection

    client = _get_client()
    if client is None:
        return None

    _collection = client.get_or_create_collection(name=_COLLECTION_NAME)
    return _collection


def _is_valid_chunk(chunk: Dict[str, Any]) -> Tuple[bool, str]:
    if not isinstance(chunk, dict):
        return False, "chunk is not a dict"

    chunk_id = chunk.get("chunk_id")
    if not chunk_id or not isinstance(chunk_id, str):
        return False, "missing or invalid chunk_id"

    text = (chunk.get("text") or "").strip()
    if not text:
        return False, "empty text"

    embedding = chunk.get("embedding")
    if embedding is None or not isinstance(embedding, list):
        return False, "missing or invalid embedding"
    if embedding and isinstance(embedding[0], list):
        return False, "embedding must be a flat list"
    try:
        _ = [float(x) for x in embedding]
    except Exception:
        return False, "embedding contains non-numeric values"

    metadata = chunk.get("metadata")
    if not isinstance(metadata, dict):
        return False, "missing or invalid metadata"

    if "section" not in metadata:
        return False, "metadata missing section"

    candidate_id = chunk.get("candidate_id")
    if not candidate_id:
        return False, "missing candidate_id"

    return True, ""


def _filter_existing_ids(
    collection, ids: List[str], batch_size: int = 100
) -> List[str]:
    if not ids:
        return []

    existing: set = set()
    for start in range(0, len(ids), batch_size):
        batch_ids = ids[start : start + batch_size]
        try:
            result = collection.get(ids=batch_ids, include=cast(Any, []))
            if result is None or not isinstance(result, dict):
                continue
            returned_ids = result.get("ids", [])
            for rid in returned_ids:
                existing.add(rid)
        except Exception as exc:  # pragma: no cover
            print(f"WARNING: Failed to check existing IDs: {exc}")
            continue

    return list(existing)


def _sanitize_metadata_value(value: Any) -> Any:
    if isinstance(value, list):
        if len(value) == 0:
            return "unknown"
        return ", ".join(str(v) for v in value)
    if value is None:
        return value
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def build_chroma_db(chunks: List[Dict[str, Any]]) -> None:
    """
    Insert valid chunks into ChromaDB with persistence.

    Prints:
    - Inserted X chunks
    - Total collection size: Y
    """
    collection = get_collection()
    if collection is None:
        print("WARNING: Collection unavailable. Skipping DB build.")
        return

    if not chunks:
        print("Inserted 0 chunks")
        print(f"Total collection size: {collection.count()}")
        return

    ids: List[str] = []
    documents: List[str] = []
    embeddings: List[List[float]] = []
    metadatas: List[Dict[str, Any]] = []

    seen_ids: set = set()

    for chunk in chunks:
        is_valid, reason = _is_valid_chunk(chunk)
        if not is_valid:
            print(f"WARNING: Skipping invalid chunk: {reason}")
            continue

        chunk_id = chunk["chunk_id"]
        if chunk_id in seen_ids:
            print(f"WARNING: Duplicate chunk_id in input: {chunk_id}")
            continue
        seen_ids.add(chunk_id)

        # Build metadata ensuring candidate_id is included
        metadata = dict(chunk.get("metadata") or {})
        metadata["candidate_id"] = chunk.get("candidate_id")

        # Normalize skills list to avoid empty list values in ChromaDB metadata
        skills = metadata.get("skills")
        if isinstance(skills, list) and len(skills) == 0:
            metadata["skills"] = "unknown"

        # ChromaDB metadata values must be scalar
        metadata = {k: _sanitize_metadata_value(v) for k, v in metadata.items()}

        sanitized_embedding = [float(x) for x in chunk.get("embedding", [])]

        ids.append(chunk_id)
        documents.append(chunk.get("text", ""))
        embeddings.append(sanitized_embedding)
        metadatas.append(metadata)

    if not ids:
        print("Inserted 0 chunks")
        print(f"Total collection size: {collection.count()}")
        return

    # Filter out IDs that already exist in the collection
    existing_ids = set(_filter_existing_ids(collection, ids))
    if existing_ids:
        filtered = [
            (i, d, e, m)
            for i, d, e, m in zip(ids, documents, embeddings, metadatas)
            if i not in existing_ids
        ]
        if filtered:
            filtered_ids, filtered_docs, filtered_embs, filtered_metas = zip(*filtered)
            ids = list(filtered_ids)
            documents = list(filtered_docs)
            embeddings = list(filtered_embs)
            metadatas = list(filtered_metas)
        else:
            ids, documents, embeddings, metadatas = [], [], [], []

    inserted_count = 0
    if ids:
        batch_size = 5000
        for start in range(0, len(ids), batch_size):
            batch_ids = ids[start : start + batch_size]
            batch_docs = documents[start : start + batch_size]
            batch_embs = embeddings[start : start + batch_size]
            batch_metas = metadatas[start : start + batch_size]
            try:
                embeddings_cast = cast(Any, batch_embs)
                metadatas_cast = cast(Any, batch_metas)
                collection.add(
                    ids=batch_ids,
                    documents=batch_docs,
                    embeddings=embeddings_cast,
                    metadatas=metadatas_cast,
                )
                inserted_count += len(batch_ids)
            except Exception as exc:  # pragma: no cover
                print(f"WARNING: Failed to insert batch starting at {start}: {exc}")

    print(f"Inserted {inserted_count} chunks")
    print(f"Total collection size: {collection.count()}")


def validate_chroma_db() -> None:
    """
    Validate ChromaDB by printing count and sample records.
    """
    collection = get_collection()
    if collection is None:
        print("WARNING: Collection unavailable. Skipping validation.")
        return

    total = collection.count()
    print(f"Total collection size: {total}")

    if total == 0:
        print("No records found.")
        return

    try:
        sample = collection.get(limit=2, include=cast(Any, ["documents", "metadatas"]))
    except Exception as exc:  # pragma: no cover
        print(f"WARNING: Failed to retrieve sample records: {exc}")
        return

    if not isinstance(sample, dict):
        print("WARNING: Invalid sample response from collection.get()")
        return

    ids = sample.get("ids", []) or []
    docs = sample.get("documents", []) or []
    metas = sample.get("metadatas", []) or []

    for idx, chunk_id in enumerate(ids):
        doc = docs[idx] if idx < len(docs) else ""
        meta = metas[idx] if idx < len(metas) else {}
        preview = (doc[:100] + "...") if len(doc) > 100 else doc

        print("\nSample Record:")
        print(f"ID: {chunk_id}")
        print(f'Text: "{preview}"')
        print(f"Metadata: {meta}")


if __name__ == "__main__":
    # mock test or pipeline hook
    print("Running DB validation...")
    validate_chroma_db()
