import gc
import json
import logging
import os
import uuid
import warnings

from dotenv import load_dotenv

# Suppress the multiprocessing semaphore warning
warnings.filterwarnings("ignore", category=UserWarning, module="resource_tracker")
os.environ["PYTHONWARNINGS"] = "ignore::UserWarning"

import re
import time
import traceback
from functools import lru_cache
from typing import Any, Dict, List, Optional

import fitz
import httpx
import psutil
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from supabase import Client, create_client

# LOAD_ENV_FROM_ROOT_OR_LOCAL
load_dotenv()

# CONSTANTS_FROM_ENV
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

from backend.config import config
from backend.rag_engine import DocumentProcessor, RAGEngine
from backend.services.search_service import search_service

PORT = int(os.environ.get("PORT", 8000))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY"] = "False"

adapt_resume = None
refine_chunks = None
build_chroma_db = None
get_collection = None
embed_chunks = None
parse_resume = None
_INGESTION_AVAILABLE = False

try:
    from ingestion.adapters.parser_adapter import adapt_resume
    from ingestion.chunking.section_chunker import refine_chunks
    from ingestion.db.chroma_builder import build_chroma_db, get_collection
    from ingestion.embedding.embedder import embed_chunks
    from parser.resume_parser import parse_resume

    _INGESTION_AVAILABLE = True
except Exception:
    _INGESTION_AVAILABLE = False


app = FastAPI(
    title="Resume Screening API",
    description="AI-powered resume screening and analysis tool",
    version="1.0.0",
)

_static_dir = os.path.join(os.path.dirname(__file__), "static")
_assets_dir = os.path.join(_static_dir, "assets")
_fonts_dir = os.path.join(_static_dir, "fonts")

if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

if os.path.isdir(_assets_dir):
    app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

if os.path.isdir(_fonts_dir):
    app.mount("/fonts", StaticFiles(directory=_fonts_dir), name="fonts")

# --- THE GOLD-TIER CORS SETTINGS ---
origins = [
    "https://resuresq.app",
    "https://www.resuresq.app",
    # Keep localhost for your local Ryzen testing
    "http://localhost:5173",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows GET, POST, OPTIONS, etc.
    allow_headers=["*"],  # Allows all headers
)


@app.on_event("startup")
def _startup_load_indices() -> None:
    search_service.load_indices()


nvidia_api_key = os.environ.get("NVIDIA_API_KEY")
if not nvidia_api_key:
    logger.warning("NVIDIA_API_KEY not set — LLM features disabled.")

rag_engine = RAGEngine(nvidia_api_key=nvidia_api_key) if nvidia_api_key else None
doc_processor = DocumentProcessor()

processed_documents: Dict[str, Any] = {
    "resume": None,
    "job_description": None,
    "resume_text": None,
    "job_description_text": None,
}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB SAFETY_CAP
_supabase_client: Optional[Client] = None


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    sources: list


class MatchAnalysisResponse(BaseModel):
    match_percentage: int
    strengths: list
    gaps: list
    summary: str


class SearchRequest(BaseModel):
    query: str
    top_n: Optional[int] = 10


class EvidenceResponse(BaseModel):
    text: str
    section: str


class SearchResultResponse(BaseModel):
    candidate_id: str
    display_name: str
    resume_url: Optional[str] = None
    score: float
    skills: List[str]
    highlights: List[str]
    evidence: List[EvidenceResponse]


class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[SearchResultResponse]
    status: str
    message: Optional[str] = None


_turnstile_secret = os.environ.get("TURNSTILE_SECRET_KEY")


async def _verify_turnstile(token: str) -> bool:
    if not _turnstile_secret:
        print("WARNING: TURNSTILE_SECRET_KEY not set — skipping verification.")
        return True
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://challenges.cloudflare.com/turnstile/v0/siteverify",
            data={"secret": _turnstile_secret, "response": token},
        )
        return resp.json().get("success", False)


def _derive_candidate_id(filename: Optional[str]) -> str:
    if not filename:
        return "cand_0000"
    match = re.search(r"(\d{4,})", filename) or re.search(r"(\d+)", filename)
    if match:
        idx = int(match.group(1))
        return f"cand_{idx:04d}"
    return "cand_0000"


def _run_ingestion_pipeline(resume_path: str, candidate_id: str) -> None:
    if (
        not _INGESTION_AVAILABLE
        or parse_resume is None
        or adapt_resume is None
        or refine_chunks is None
        or embed_chunks is None
        or build_chroma_db is None
    ):
        print("WARNING: Ingestion pipeline modules unavailable — skipping ingestion.")
        return
    try:
        parsed = parse_resume(resume_path, use_llm_fallback=False)
        adapted = adapt_resume(parsed, candidate_id)

        for chunk in adapted:
            if "metadata" not in chunk:
                chunk["metadata"] = {}
            chunk["metadata"]["resume_path"] = f"/resume/{candidate_id}"

        refined = refine_chunks(adapted)
        embedded = embed_chunks(refined)
        build_chroma_db(embedded)
    except Exception as exc:
        print(f"WARNING: Ingestion pipeline failed: {exc}")


def _get_supabase_client() -> Client:
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(
            status_code=500,
            detail="Supabase credentials not configured.",
        )
    _supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase_client


def log_mem(stage: str) -> None:
    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / 1024 / 1024
    print(f"[MEM_CHECK] {stage}: {mem_mb:.2f} MB")


@app.post("/upload-resume")
async def handle_dynamic_ingestion(file: UploadFile = File(...)):
    log_mem("START_UPLOAD")
    content = await file.read()
    file_size = len(content)
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large for 1GB RAM constraint.",
        )

    embeddings = None
    chunks = None
    public_url = None
    doc = None
    model = None
    full_text = ""

    try:
        supabase = _get_supabase_client()
        resume_id = str(uuid.uuid4())
        filename = f"{resume_id}.pdf"

        supabase.storage.from_("resumes").upload(
            path=filename,
            file=content,
            file_options={"content-type": "application/pdf"},
        )
        public_url = supabase.storage.from_("resumes").get_public_url(filename)

        doc = fitz.open(stream=content, filetype="pdf")
        for page in doc:
            full_text += page.get_text()
        doc.close()

        chunks = [full_text[i : i + 1000] for i in range(0, len(full_text), 800)]
        model = SentenceTransformer("all-MiniLM-L6-v2")
        embeddings = model.encode(chunks).tolist()

        if get_collection is None:
            raise HTTPException(status_code=503, detail="ChromaDB unavailable.")

        collection = get_collection()
        if collection is None:
            raise HTTPException(status_code=503, detail="ChromaDB unavailable.")

        ids = [f"{resume_id}_{i}" for i in range(len(chunks))]
        metadatas: List[Dict[str, str | int | float | bool]] = [
            {
                "url": str(public_url),
                "source": str(file.filename or filename),
                "id": str(resume_id),
            }
            for _ in chunks
        ]

        collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=chunks,
        )

    finally:
        log_mem("PRE_GC")
        del content
        if embeddings is not None:
            del embeddings
        if chunks is not None:
            del chunks
        if full_text:
            del full_text
        if model is not None:
            del model
        if doc is not None:
            del doc
        gc.collect()
        log_mem("POST_GC")

    return {"status": "indexed", "resume_url": public_url}


def _extract_structured_resume(resume_text: str) -> Dict[str, Any]:
    prompt = f"""Extract structured information from the following resume text.
Return ONLY a JSON object with these fields:
{{
    "candidate_name": "<full name or null>",
    "email": "<email address or null>",
    "phone": "<phone number or null>",
    "skills": ["<skill1>", "<skill2>"],
    "experience_years": <integer or null>,
    "education": "<highest degree or null>",
    "current_title": "<most recent job title or null>"
}}

Resume:
{resume_text}
"""
    if rag_engine is None:
        return {
            "candidate_name": None,
            "email": None,
            "phone": None,
            "skills": [],
            "experience_years": None,
            "education": None,
            "current_title": None,
        }

    response = rag_engine.llm.invoke(prompt)
    response_text = response.content
    json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except Exception:
            pass
    return {
        "candidate_name": None,
        "email": None,
        "phone": None,
        "skills": [],
        "experience_years": None,
        "education": None,
        "current_title": None,
    }


def _insert_parsed_resume(
    structured: Dict[str, Any],
    match_analysis: Optional[Dict[str, Any]],
    resume_filename: Optional[str],
    resume_text: str,
) -> None:
    # Supabase persistence removed; ingestion + retrieval pipeline is now the source of truth.
    return


@app.get("/api/health", include_in_schema=True)
async def api_health_check():
    return {"message": "Resume Screening API is running", "status": "healthy"}


@app.post("/upload")
async def upload_documents(
    resume: Optional[UploadFile] = File(None),
    job_description: Optional[UploadFile] = File(None),
    job_description_text: Optional[str] = Form(None),
    turnstile_token: Optional[str] = Form(None),
):
    try:
        if not await _verify_turnstile(turnstile_token or ""):
            raise HTTPException(status_code=403, detail="Turnstile verification failed")

        if rag_engine is not None:
            rag_engine.clear_vector_store()
        global processed_documents
        processed_documents = {
            "resume": None,
            "job_description": None,
            "resume_text": None,
            "job_description_text": None,
        }

        resume_filename: Optional[str] = None

        if resume:
            resume_filename = resume.filename or "resume_upload.pdf"
            if not (
                resume_filename.endswith(".pdf") or resume_filename.endswith(".txt")
            ):
                raise HTTPException(
                    status_code=400, detail="Resume must be PDF or TXT file"
                )

            resume_content = await resume.read()
            candidate_id = _derive_candidate_id(resume_filename)

            os.makedirs("resumes", exist_ok=True)
            saved_resume_path = f"resumes/{candidate_id}.pdf"
            with open(saved_resume_path, "wb") as f:
                f.write(resume_content)

            resume_path = doc_processor.save_temp_file(resume_content, resume_filename)
            resume_text = doc_processor.extract_text(resume_path)
            if rag_engine is not None:
                rag_engine.index_document(resume_path, doc_type="resume")
            processed_documents["resume"] = resume_path
            processed_documents["resume_text"] = resume_text

            _run_ingestion_pipeline(resume_path, candidate_id)

        if job_description:
            job_description_filename = (
                job_description.filename or "job_description_upload.pdf"
            )
            if not (
                job_description_filename.endswith(".pdf")
                or job_description_filename.endswith(".txt")
            ):
                raise HTTPException(
                    status_code=400, detail="Job description must be PDF or TXT file"
                )

            jd_content = await job_description.read()
            jd_path = doc_processor.save_temp_file(jd_content, job_description_filename)
            jd_text = doc_processor.extract_text(jd_path)
            processed_documents["job_description"] = jd_path
            processed_documents["job_description_text"] = jd_text

        elif job_description_text and job_description_text.strip():
            jd_text = job_description_text.strip()
            jd_path = doc_processor.save_temp_file(
                jd_text.encode("utf-8"), "job_description_pasted.txt"
            )
            processed_documents["job_description"] = jd_path
            processed_documents["job_description_text"] = jd_text

        match_result = None
        if (
            rag_engine is not None
            and processed_documents["resume_text"]
            and processed_documents["job_description_text"]
        ):
            match_result = rag_engine.calculate_match_score(
                processed_documents["resume_text"],
                processed_documents["job_description_text"],
            )

        if processed_documents["resume_text"]:
            try:
                structured = _extract_structured_resume(
                    processed_documents["resume_text"]
                )
                _insert_parsed_resume(
                    structured,
                    match_result,
                    resume_filename if resume else None,
                    processed_documents["resume_text"],
                )
            except Exception as db_err:
                print(f"WARNING: Failed to persist parsed resume: {db_err}")

        return {
            "status": "success",
            "message": (
                "Documents uploaded and analysed successfully"
                if match_result
                else "Documents uploaded successfully."
            ),
            "match_analysis": match_result,
            "files_uploaded": {
                "resume": resume.filename if resume else None,
                "job_description": job_description.filename
                if job_description
                else None,
            },
        }

    except HTTPException:
        raise
    except Exception as err:
        print(f"ERROR in /upload: {str(err)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500, detail=f"Error processing documents: {str(err)}"
        )


@app.post("/chat", response_model=ChatResponse)
async def chat_with_resume(request: ChatRequest):
    try:
        if not processed_documents["resume"]:
            return ChatResponse(
                answer="Please upload a resume first before asking questions.",
                sources=[],
            )

        if rag_engine is None:
            return ChatResponse(
                answer="LLM features are disabled. Please set NVIDIA_API_KEY.",
                sources=[],
            )

        result = rag_engine.chat(request.question)
        return ChatResponse(answer=result["answer"], sources=result["sources"])

    except Exception as err:
        print(f"ERROR in /chat: {str(err)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500, detail=f"Error processing chat: {str(err)}"
        )


@lru_cache(maxsize=100)
def cached_search(query: str, top_n: int):
    return search_service.search(query, top_n=top_n)


@app.post("/search", response_model=SearchResponse)
def search_candidates(request: SearchRequest):
    start_time = time.time()
    raw_query = request.query or ""
    query = raw_query.strip().lower()
    top_n = max(1, min(int(request.top_n or 20), 100))
    logger.info(f"Search query: {query}")
    try:
        cache_before = cached_search.cache_info().hits
        results_raw = cached_search(query, top_n) or []
        cache_after = cached_search.cache_info().hits
        if cache_after > cache_before:
            logger.info(f"Cache hit for query: {query}")
        else:
            logger.info(f"Cache miss for query: {query}")
        latency_ms = (time.time() - start_time) * 1000
        logger.info(f"Search latency (ms): {latency_ms:.2f}")
        logger.info(f"Results count: {len(results_raw)}")

        def _get(item, key, default):
            if isinstance(item, dict):
                val = item.get(key, default)
            else:
                val = getattr(item, key, default)
            return default if val is None else val

        normalized_results = []
        for item in results_raw[:top_n]:
            candidate_id = _get(item, "candidate_id", "")
            display_name = _get(item, "display_name", "")

            resume_url = _get(item, "resume_url", "")
            if not resume_url:
                resume_url = _get(item, "url", "")

            if not resume_url:
                metadata = _get(item, "metadata", {})
                if isinstance(metadata, dict):
                    # 1. Try to get the raw URL
                    resume_url = metadata.get("url", "") or metadata.get(
                        "resume_url", ""
                    )

                    # 2. If no raw URL, check if the ingestion script saved the UUID in 'source' or 'id'
                    if not resume_url and SUPABASE_URL:
                        file_id = metadata.get("id", "") or metadata.get("source", "")
                        # Clean up the file_id just in case it's a full path
                        if file_id:
                            file_name = file_id.split("/")[-1]
                            if not file_name.endswith(".pdf"):
                                file_name = f"{file_name}.pdf"
                            resume_url = f"{SUPABASE_URL.rstrip('/')}/storage/v1/object/public/resumes/{file_name}"

            match_score = _get(item, "match_score", None)
            if match_score is None:
                match_score = _get(item, "score", 0)
            score = float(match_score)
            highlights = _get(item, "highlights", []) or []
            skills = _get(item, "skills", []) or []
            evidence_raw = _get(item, "evidence", []) or []
            evidence = []
            for e in evidence_raw:
                if isinstance(e, dict):
                    text = e.get("text") or ""
                    section = e.get("section") or ""
                else:
                    text = getattr(e, "text", "") or ""
                    section = getattr(e, "section", "") or ""
                evidence.append({"text": text, "section": section})

            normalized_results.append(
                {
                    "candidate_id": candidate_id or "",
                    "display_name": display_name or "",
                    "resume_url": resume_url or "",
                    "score": score,
                    "skills": skills,
                    "highlights": highlights,
                    "evidence": evidence,
                }
            )

        return {
            "query": raw_query,
            "total_results": len(results_raw),
            "results": normalized_results,
            "status": "success",
        }
    except Exception as e:
        logger.error("Search failed", exc_info=True)
        return {
            "query": raw_query,
            "total_results": 0,
            "results": [],
            "status": "error",
            "message": "Search failed",
        }


@app.post("/api/search", response_model=SearchResponse)
def api_search_candidates(request: SearchRequest):
    return search_candidates(request)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/resume/{candidate_id}")
async def get_resume_pdf(candidate_id: str):
    file_path = f"resumes/{candidate_id}.pdf"
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="application/pdf")
    raise HTTPException(status_code=404, detail="Resume not found")


@app.get("/status")
async def get_status():
    return {
        "resume_uploaded": processed_documents["resume"] is not None,
        "job_description_uploaded": processed_documents["job_description"] is not None,
        "vector_store_ready": rag_engine is not None
        and rag_engine.vector_store is not None,
        "total_chunks": len(rag_engine.documents)
        if rag_engine is not None and rag_engine.documents
        else 0,
    }


@app.delete("/clear")
async def clear_documents():
    global processed_documents
    processed_documents = {
        "resume": None,
        "job_description": None,
        "resume_text": None,
        "job_description_text": None,
    }
    if rag_engine is not None:
        rag_engine.clear_vector_store()
    return {"message": "All documents cleared successfully"}


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    index = os.path.join(_static_dir, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {"message": "Resume Screening API is running", "status": "healthy"}


@app.get("/api/debug/chroma")
def debug_chroma():
    """Fetches exactly one chunk from ChromaDB to inspect its metadata keys"""
    try:
        results = cached_search("java", 1)
        if not results:
            return {"message": "No results found in ChromaDB"}

        # Return the raw, unformatted item so we can see the exact metadata
        return {"raw_item_data": results[0]}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=config.HOST,
        port=PORT,
        log_level="info" if config.DEBUG else "warning",
    )
