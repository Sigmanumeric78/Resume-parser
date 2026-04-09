"""
RAG Engine for Resume Screening Tool
LangChain-free implementation using sentence-transformers embeddings and NVIDIA NIM via HTTP.
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    from PyPDF2 import PdfReader  # type: ignore
except ImportError:
    PdfReader = None


_embed_chunks = None


def _load_embedder_class():
    from ingestion.embedding.embedder import (
        Embedder as _Embedder,
    )
    from ingestion.embedding.embedder import (
        embed_chunks as _embed_chunks_fn,
    )

    globals()["_embed_chunks"] = _embed_chunks_fn
    return _Embedder


Embedder = _load_embedder_class()


@dataclass
class Document:
    page_content: str
    metadata: Dict[str, Any]


@dataclass
class SimpleResponse:
    content: str


class NIMClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://integrate.api.nvidia.com/v1",
        temperature: float = 0.7,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.timeout = timeout

    def invoke(self, prompt: str) -> SimpleResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.temperature,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = (
                    data.get("choices", [{}])[0].get("message", {}).get("content", "")
                )
                return SimpleResponse(content=content or "")
        except Exception as exc:
            return SimpleResponse(content=f"LLM error: {exc}")


def split_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    if not text:
        return []
    if chunk_size <= 0:
        return [text]

    chunks: List[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + chunk_size, length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == length:
            break
        start = max(0, end - overlap)

    return chunks


class RAGEngine:
    """
    RAG Engine that handles:
    1. Document extraction from PDF/TXT files
    2. Text chunking
    3. Vector embedding generation
    4. Simple in-memory retrieval
    5. Augmented generation via NVIDIA NIM
    """

    def __init__(
        self,
        nvidia_api_key: Optional[str] = None,
        model: str = "nvidia/nemotron-3-super-120b-a12b",
    ) -> None:
        self.nvidia_api_key = nvidia_api_key or os.getenv("NVIDIA_API_KEY")
        if not self.nvidia_api_key:
            raise ValueError(
                "NVIDIA_API_KEY not provided and not found in environment variables"
            )

        self.model = model
        self.llm = NIMClient(api_key=self.nvidia_api_key, model=self.model)

        self.embedder: Any = Embedder()
        self.documents: List[Document] = []
        self.document_embeddings: List[List[float]] = []

        self.vector_store = None

    def extract_text_from_file(self, file_path: str) -> str:
        if file_path.endswith(".pdf"):
            text_parts: List[str] = []
            if pdfplumber is not None:
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text() or ""
                        if page_text:
                            text_parts.append(page_text)
            elif PdfReader is not None:
                reader = PdfReader(file_path)
                for page in reader.pages:
                    page_text = page.extract_text() or ""
                    if page_text:
                        text_parts.append(page_text)
            else:
                raise ValueError("PDF extraction requires pdfplumber or PyPDF2.")
            return "\n".join(text_parts).strip()
        elif file_path.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        else:
            raise ValueError(f"Unsupported file format: {file_path}")

    def process_document(
        self, file_path: str, doc_type: str = "resume"
    ) -> List[Document]:
        text = self.extract_text_from_file(file_path)
        chunks = split_text(text, chunk_size=1000, overlap=200)

        documents: List[Document] = []
        for i, chunk in enumerate(chunks):
            documents.append(
                Document(
                    page_content=chunk,
                    metadata={
                        "source": file_path,
                        "doc_type": doc_type,
                        "chunk_id": i,
                        "total_chunks": len(chunks),
                    },
                )
            )

        return documents

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        if hasattr(self.embedder, "_embed_texts"):
            embeddings = self.embedder._embed_texts(texts)
            if embeddings:
                return embeddings

        chunks = [{"text": t} for t in texts]
        if _embed_chunks is not None:
            chunks = _embed_chunks(chunks)
        results: List[List[float]] = []
        for chunk in chunks:
            emb = chunk.get("embedding")
            if isinstance(emb, list):
                results.append([float(x) for x in emb])
        return results

    def index_document(self, file_path: str, doc_type: str = "resume") -> None:
        chunks = self.process_document(file_path, doc_type)
        if not chunks:
            return

        texts = [c.page_content for c in chunks]
        embeddings = self._embed_texts(texts)

        if embeddings and len(embeddings) == len(chunks):
            self.documents.extend(chunks)
            self.document_embeddings.extend(embeddings)
        else:
            for c in chunks:
                self.documents.append(c)
                self.document_embeddings.append([])

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def retrieve_relevant_chunks(self, query: str, k: int = 3) -> List[Document]:
        if not self.documents:
            return []

        query_embs = self._embed_texts([query])
        if not query_embs:
            return []

        query_emb = query_embs[0]
        scores = [
            (self._cosine_similarity(query_emb, emb), idx)
            for idx, emb in enumerate(self.document_embeddings)
        ]
        scores.sort(key=lambda x: x[0], reverse=True)
        top_indices = [idx for _, idx in scores[:k]]
        return [self.documents[i] for i in top_indices]

    def generate_answer(
        self, question: str, context: Optional[List[Document]] = None
    ) -> str:
        if context is None:
            context = self.retrieve_relevant_chunks(question)

        if not context:
            return (
                "I don't have any resume information to answer that question. "
                "Please upload a resume first."
            )

        context_text = "\n\n".join([doc.page_content for doc in context])
        prompt = f"""You are an AI assistant helping a recruiter analyze a candidate's resume.
Use only the information provided in the context below to answer the question.
If the answer is not in the context, say that you don't have that information.

Context from resume:
{context_text}

Question: {question}

Answer:"""

        response = self.llm.invoke(prompt)
        return response.content

    def chat(self, question: str) -> Dict[str, Any]:
        relevant_chunks = self.retrieve_relevant_chunks(question)
        answer = self.generate_answer(question, relevant_chunks)
        sources = [
            {"content": chunk.page_content[:200] + "...", "metadata": chunk.metadata}
            for chunk in relevant_chunks
        ]
        return {"answer": answer, "sources": sources}

    def calculate_match_score(
        self, resume_text: str, job_description: str
    ) -> Dict[str, Any]:
        prompt = f"""Analyze the following resume and job description.

Provide a detailed analysis including:
1. A match percentage (0-100%)
2. Top strengths (skills/experience that match)
3. Key gaps (requirements not found in resume)

Resume:
{resume_text}

Job Description:
{job_description}

Please respond in the following JSON format:
{{
    "match_percentage": <number>,
    "strengths": [<list of 3-5 matched skills/experience>],
    "gaps": [<list of 3-5 missing requirements>],
    "summary": "<brief overall assessment>"
}}
"""

        response = self.llm.invoke(prompt)
        response_text = response.content

        try:
            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found in response")
        except Exception:
            result = {
                "match_percentage": 50,
                "strengths": ["Unable to parse strengths"],
                "gaps": ["Unable to parse gaps"],
                "summary": "Error in parsing LLM response",
            }

        return result

    def clear_vector_store(self) -> None:
        self.vector_store = None
        self.documents = []
        self.document_embeddings = []


class DocumentProcessor:
    """Helper class for processing uploaded files"""

    @staticmethod
    def save_temp_file(file_content: bytes, filename: str) -> str:
        temp_dir = tempfile.gettempdir()
        ext = os.path.splitext(filename)[1]
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext, dir=temp_dir)
        temp_file.write(file_content)
        temp_file.close()
        return temp_file.name

    @staticmethod
    def extract_text(file_path: str) -> str:
        if file_path.endswith(".pdf"):
            text_parts: List[str] = []
            if pdfplumber is not None:
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text() or ""
                        if page_text:
                            text_parts.append(page_text)
            elif PdfReader is not None:
                reader = PdfReader(file_path)
                for page in reader.pages:
                    page_text = page.extract_text() or ""
                    if page_text:
                        text_parts.append(page_text)
            else:
                raise ValueError("PDF extraction requires pdfplumber or PyPDF2.")
            return "\n".join(text_parts).strip()
        elif file_path.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().strip()
        else:
            raise ValueError(f"Unsupported file format: {file_path}")
