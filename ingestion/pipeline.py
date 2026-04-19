"""
Ingestion pipeline orchestrator.

Runs: PDF → Parser → Adapter → Chunker → Embedder → ChromaDB → BM25
"""

import os
import shutil
import time
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv
from supabase import Client, create_client

# Load environment variables from .env file FIRST
load_dotenv()

from ingestion.adapters.parser_adapter import adapt_resume
from ingestion.bm25.bm25_builder import build_bm25_index, load_bm25_index
from ingestion.chunking.section_chunker import refine_chunks
from ingestion.db.chroma_builder import build_chroma_db, get_collection
from ingestion.embedding.embedder import embed_chunks
from parser.resume_parser import parse_resume

DATA_DIR = os.path.join("data", "raw_resumes_clean")
DRY_RUN = os.environ.get("DRY_RUN", "0").lower() in ("1", "true", "yes")
MAX_TOTAL_SECONDS = 3600.0
MAX_EMBED_SECONDS = 600.0
MAX_RESUMES = int(os.environ.get("MAX_RESUMES", "650"))

# Initialize Supabase (Ensure these exist in your local .env)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client | None = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    print("WARNING: Supabase credentials missing. URLs will be empty.")


def _safe_listdir(path: str) -> List[str]:
    try:
        return sorted(os.listdir(path))
    except Exception as exc:
        print(f"WARNING: Failed to list directory {path}: {exc}")
        return []


def _count_embedded(chunks: List[Dict[str, Any]]) -> int:
    return sum(
        1
        for c in chunks
        if isinstance(c.get("embedding"), list) and len(c.get("embedding") or []) > 0
    )


def _find_duplicate_chunk_ids(chunks: List[Dict[str, Any]]) -> List[str]:
    seen = set()
    duplicates = []
    for c in chunks:
        cid = c.get("chunk_id")
        if not cid:
            continue
        if cid in seen:
            duplicates.append(cid)
        else:
            seen.add(cid)
    return duplicates


def run_pipeline() -> None:
    files = _safe_listdir(DATA_DIR)
    total_files = len(files)
    if MAX_RESUMES > 0:
        files = files[:MAX_RESUMES]
    if not files:
        print("WARNING: No resumes found to process.")
        return

    if total_files != len(files):
        print(f"Total PDFs detected: {total_files} (processing {len(files)})")
    else:
        print(f"Total PDFs detected: {len(files)}")

    if DRY_RUN:
        print("DRY_RUN enabled — DB and BM25 writes will be skipped.")
    else:
        if os.path.exists("data/chroma_db"):
            print("Existing ChromaDB detected — deleting for clean-slate run.")
            shutil.rmtree("data/chroma_db")
        if os.path.exists("data/bm25_index"):
            print("Existing BM25 index detected — deleting for clean-slate run.")
            shutil.rmtree("data/bm25_index")

    total_time_start = time.perf_counter()

    total_resumes = 0
    adapted_per_candidate: List[Tuple[str, List[Dict[str, Any]]]] = []
    total_chunks_before_refine = 0

    for i, filename in enumerate(files):
        path = os.path.join(DATA_DIR, filename)
        candidate_id = f"cand_{i:04d}"

        try:
            public_url = ""
            # --- SUPABASE UPLOAD ---
            if supabase and not DRY_RUN:
                try:
                    file_name = f"{candidate_id}.pdf"
                    with open(path, "rb") as f:
                        file_bytes = f.read()

                    # Upload (or overwrite if exists)
                    supabase.storage.from_("resumes").upload(
                        path=file_name,
                        file=file_bytes,
                        file_options={
                            "content-type": "application/pdf",
                            "upsert": "true",
                        },
                    )
                    public_url = supabase.storage.from_("resumes").get_public_url(
                        file_name
                    )
                    print(f"Uploaded {filename} -> {public_url}")
                except Exception as up_exc:
                    print(f"WARNING: Supabase upload failed for {filename}: {up_exc}")
            # -----------------------

            parsed = parse_resume(path, use_llm_fallback=False)
            adapted = adapt_resume(parsed, candidate_id, url=public_url)
            adapted_per_candidate.append((candidate_id, adapted))
            total_chunks_before_refine += len(adapted)
            total_resumes += 1
        except Exception as exc:
            print(f"WARNING: Failed to process {filename}: {exc}")
            continue

    all_chunks: List[Dict[str, Any]] = []
    chunks_per_candidate: Dict[str, int] = defaultdict(int)
    avg_chunks = 0.0

    for attempt in range(2):
        all_chunks = []
        chunks_per_candidate = defaultdict(int)
        aggressive = attempt == 1

        for candidate_id, adapted in adapted_per_candidate:
            refined = refine_chunks(adapted, aggressive=aggressive)
            all_chunks.extend(refined)
            chunks_per_candidate[candidate_id] += len(refined)

        print(f"Total resumes processed: {total_resumes}")
        print(f"Total chunks before refinement: {total_chunks_before_refine}")
        print(f"Total chunks after refinement: {len(all_chunks)}")

        if chunks_per_candidate:
            counts = list(chunks_per_candidate.values())
            avg_chunks = sum(counts) / max(len(counts), 1)
            min_chunks = min(counts)
            max_chunks = max(counts)
            print(f"Avg chunks per resume: {avg_chunks:.2f}")
            print(f"Min chunks per resume: {min_chunks}")
            print(f"Max chunks per resume: {max_chunks}")
            if avg_chunks < 5 and attempt == 0:
                print(
                    "WARNING: Avg chunks per resume below 5 — rerunning with aggressive chunking."
                )
                continue
            if avg_chunks < 5 and attempt == 1:
                print(
                    "WARNING: Avg chunks per resume still below 5 after aggressive chunking."
                )
        break

    embedded_chunks: List[Dict[str, Any]] = []
    embedded_count = 0
    embedding_time = 0.0
    try:
        print("Starting embedding stage...")
        print("Embedding source: sentence-transformers API")
        embed_start = time.perf_counter()
        embedded_chunks = embed_chunks(all_chunks)
        embedding_time = time.perf_counter() - embed_start
        embedded_count = _count_embedded(embedded_chunks)
        print(f"Total embedded: {embedded_count}")
        print(f"Embedding time (s): {embedding_time:.2f}")

        embedding_dim = None
        invalid_embeddings = 0
        zero_values = 0
        total_values = 0

        for chunk in embedded_chunks:
            emb = chunk.get("embedding")
            if not isinstance(emb, list) or (emb and isinstance(emb[0], list)):
                invalid_embeddings += 1
                continue
            if embedding_dim is None:
                embedding_dim = len(emb)
            if len(emb) != embedding_dim:
                invalid_embeddings += 1
                continue

            sanitized = []
            for v in emb:
                if not isinstance(v, float):
                    try:
                        v = float(v)
                    except Exception:
                        invalid_embeddings += 1
                        sanitized = []
                        break
                sanitized.append(v)

            if not sanitized:
                continue

            chunk["embedding"] = sanitized
            total_values += len(sanitized)
            zero_values += sum(1 for v in sanitized if v == 0.0)

        zero_pct = (zero_values / total_values * 100.0) if total_values else 0.0
        print(f"Embedding dimension: {embedding_dim}")
        print(f"Embeddings validated: {embedded_count}")
        print(f"Invalid embeddings: {invalid_embeddings}")
        print(f"% zero values per embedding: {zero_pct:.2f}")

        if invalid_embeddings > 0 or embedding_dim is None:
            print("ERROR: Invalid embeddings detected — stopping execution.")
            raise SystemExit(1)
    except Exception as exc:
        print(f"ERROR: Embedding stage failed: {exc}")
        raise SystemExit(1)

    db_count = 0
    db_time = 0.0
    if DRY_RUN:
        print("DRY_RUN: Skipping ChromaDB build stage.")
    else:
        try:
            print("Starting ChromaDB build stage...")
            db_start = time.perf_counter()
            build_chroma_db(embedded_chunks)
            db_time = time.perf_counter() - db_start
            collection = get_collection()
            db_count = collection.count() if collection is not None else 0
            print(f"DB count: {db_count}")
            print(f"DB insertion time (s): {db_time:.2f}")
        except Exception as exc:
            print(f"WARNING: ChromaDB stage failed: {exc}")

    bm25_count = 0
    bm25_time = 0.0
    if DRY_RUN:
        print("DRY_RUN: Skipping BM25 build stage.")
    else:
        try:
            print("Starting BM25 build stage...")
            bm25_start = time.perf_counter()
            build_bm25_index(embedded_chunks)
            bm25_time = time.perf_counter() - bm25_start
            bm25_data = load_bm25_index()
            bm25_count = len(bm25_data.get("corpus_tokens", [])) if bm25_data else 0
            print(f"BM25 count: {bm25_count}")
            print(f"BM25 build time (s): {bm25_time:.2f}")
        except Exception as exc:
            print(f"WARNING: BM25 stage failed: {exc}")

    if not DRY_RUN:
        if embedded_count != db_count:
            print(
                f"ERROR: Embedded count ({embedded_count}) "
                f"does not match DB count ({db_count})"
            )
            dup_ids = _find_duplicate_chunk_ids(embedded_chunks)
            if dup_ids:
                print(f"Duplicate chunk_ids detected: {dup_ids[:20]}")
            conflict_ids = [
                c.get("chunk_id") for c in embedded_chunks if c.get("chunk_id")
            ]
            print(f"Conflicting chunk_ids sample: {conflict_ids[:20]}")
            raise SystemExit(1)

        if embedded_count != bm25_count:
            print(
                f"ERROR: Embedded count ({embedded_count}) "
                f"does not match BM25 count ({bm25_count})"
            )
            raise SystemExit(1)
    else:
        print("DRY_RUN: Skipping DB/BM25 count assertions.")

    total_time = time.perf_counter() - total_time_start
    print(f"Total processing time (s): {total_time:.2f}")

    if total_time > MAX_TOTAL_SECONDS:
        raise SystemExit(
            f"ERROR: Pipeline exceeded max time {MAX_TOTAL_SECONDS}s (actual {total_time:.2f}s)"
        )
    if embedding_time > MAX_EMBED_SECONDS:
        raise SystemExit(
            f"ERROR: Embedding exceeded max time {MAX_EMBED_SECONDS}s (actual {embedding_time:.2f}s)"
        )


if __name__ == "__main__":
    run_pipeline()
