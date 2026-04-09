"""
Section Chunker Module

Refines resume chunks for semantic retrieval and ranking accuracy.
"""

import re
import uuid
from typing import Any, Dict, List


def _generate_chunk_id() -> str:
    return str(uuid.uuid4())


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text


def split_by_paragraphs(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r"\n{2,}", text)
    return [p.strip() for p in parts if p and p.strip()]


def split_by_bullets(text: str) -> List[str]:
    if not text:
        return []
    cleaned = _clean_text(text)
    if not cleaned:
        return []
    total_words = _word_count(cleaned)
    if total_words <= 275:
        return [cleaned]

    lines = cleaned.splitlines()
    midpoint = total_words / 2
    first_lines: List[str] = []
    second_lines: List[str] = []
    count = 0

    for line in lines:
        line_words = _word_count(line)
        if count + line_words <= midpoint or not first_lines:
            first_lines.append(line)
            count += line_words
        else:
            second_lines.append(line)

    if not second_lines:
        return [cleaned]

    first_chunk = "\n".join(first_lines).strip()
    second_chunk = "\n".join(second_lines).strip()
    return [c for c in [first_chunk, second_chunk] if c]


def _split_by_headings(text: str) -> List[str]:
    if not text:
        return []
    lines = text.splitlines()
    sections: List[str] = []
    buffer: List[str] = []

    def is_heading(line: str) -> bool:
        if not line:
            return False
        if re.match(r"^\s*[-*•]\s+", line):
            return False
        if re.match(r"^\s*\d+[\.\)]\s+", line):
            return False
        if line.endswith("."):
            return False
        words = line.strip().split()
        return 1 <= len(words) <= 8

    for line in lines:
        if is_heading(line) and buffer:
            sections.append("\n".join(buffer).strip())
            buffer = [line.strip()]
        else:
            buffer.append(line.strip())

    if buffer:
        sections.append("\n".join(buffer).strip())

    return [s for s in sections if s]


def enforce_word_limit(text: str, max_words: int = 400) -> List[str]:
    if not text:
        return []
    text = _clean_text(text)
    wc = _word_count(text)

    if wc < 20:
        return [text]
    if wc <= max_words:
        return [text]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: List[str] = []
    buffer: List[str] = []
    buffer_count = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        sentence_words = _word_count(sentence)

        if sentence_words > max_words:
            words = sentence.split()
            temp: List[str] = []
            for w in words:
                temp.append(w)
                if len(temp) >= max_words:
                    chunks.append(" ".join(temp).strip())
                    temp = []
            if temp:
                chunks.append(" ".join(temp).strip())
            continue

        if buffer_count + sentence_words <= max_words:
            buffer.append(sentence)
            buffer_count += sentence_words
        else:
            chunks.append(" ".join(buffer).strip())
            buffer = [sentence]
            buffer_count = sentence_words

    if buffer:
        chunks.append(" ".join(buffer).strip())

    return [c for c in chunks if c]


def _create_chunk(base_chunk: Dict[str, Any], text: str) -> Dict[str, Any]:
    return {
        "chunk_id": _generate_chunk_id(),
        "text": text,
        "candidate_id": base_chunk["candidate_id"],
        "metadata": base_chunk["metadata"],
    }


def _split_experience(text: str) -> List[str]:
    parts: List[str] = []
    for paragraph in split_by_paragraphs(text):
        subparts = split_by_bullets(paragraph)
        if subparts:
            parts.extend(subparts)
        else:
            parts.append(paragraph)
    return parts


def _split_projects(text: str) -> List[str]:
    heading_parts = _split_by_headings(text)
    if len(heading_parts) > 1:
        parts = heading_parts
    else:
        parts = split_by_paragraphs(text)

    refined: List[str] = []
    for part in parts:
        subparts = split_by_bullets(part)
        if subparts:
            refined.extend(subparts)
        else:
            refined.append(part)
    return refined


def refine_chunks(
    chunks: List[Dict[str, Any]], aggressive: bool = False
) -> List[Dict[str, Any]]:
    refined: List[Dict[str, Any]] = []

    for chunk in chunks:
        text = _clean_text(chunk.get("text", ""))
        if not text:
            continue

        section = chunk.get("metadata", {}).get("section", "").lower()

        if section == "skills":
            words = _word_count(text)
            if words > 400:
                for part in enforce_word_limit(text, max_words=400):
                    if part:
                        refined.append(_create_chunk(chunk, part))
            else:
                refined.append(_create_chunk(chunk, text))

        elif section == "education":
            words = _word_count(text)
            if words > 400:
                for part in enforce_word_limit(text, max_words=400):
                    if part:
                        refined.append(_create_chunk(chunk, part))
            else:
                refined.append(_create_chunk(chunk, text))

        elif section == "experience":
            parts = _split_experience(text)
            if aggressive and _word_count(text) > 350:
                extra_parts: List[str] = []
                for part in parts:
                    word_count = _word_count(part)
                    if word_count > 350:
                        extra_parts.extend(
                            [
                                p.strip()
                                for p in re.split(r"[;:]\s+|\.\s+", part)
                                if p.strip()
                            ]
                        )
                    else:
                        extra_parts.append(part)
                parts = extra_parts
            for part in parts:
                for sub in enforce_word_limit(part, max_words=400):
                    if sub:
                        refined.append(_create_chunk(chunk, sub))

        elif section == "projects":
            parts = _split_projects(text)
            if aggressive and _word_count(text) > 350:
                project_extra_parts: List[str] = []
                for part in parts:
                    word_count = _word_count(part)
                    if word_count > 350:
                        project_extra_parts.extend(
                            [
                                p.strip()
                                for p in re.split(r"[;:]\s+|\.\s+", part)
                                if p.strip()
                            ]
                        )
                    else:
                        project_extra_parts.append(part)
                parts = project_extra_parts
            for part in parts:
                for sub in enforce_word_limit(part, max_words=400):
                    if sub:
                        refined.append(_create_chunk(chunk, sub))

        else:
            for part in enforce_word_limit(text, max_words=400):
                if part:
                    refined.append(_create_chunk(chunk, part))

    return refined
