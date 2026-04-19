"""
Parser Adapter Module

Converts parsed resume output into structured chunk objects for the ingestion pipeline.
"""

import re
import uuid
from typing import Any, Dict, List, Optional


def generate_chunk_id() -> str:
    """
    Generate a unique chunk ID using UUID4.

    Returns:
        UUID4 string
    """
    return str(uuid.uuid4())


def clean_text(text: str) -> str:
    """
    Clean and normalize text content.

    Args:
        text: Raw text string

    Returns:
        Cleaned text with stripped whitespace and removed excessive newlines
    """
    if not text:
        return ""

    # Strip leading/trailing whitespace
    text = text.strip()

    # Remove excessive newlines (more than 2 consecutive)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove excessive spaces
    text = re.sub(r" {2,}", " ", text)

    return text


def is_valid_text(text: str) -> bool:
    """
    Check if text is valid (non-empty after cleaning).

    Args:
        text: Text to validate

    Returns:
        True if text is valid, False otherwise
    """
    if not text:
        return False

    cleaned = clean_text(text)
    return len(cleaned) > 0


def create_chunk(
    text: str, candidate_id: str, section: str, metadata: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Create a single chunk object.

    Args:
        text: Chunk text content
        candidate_id: Candidate identifier
        section: Section label
        metadata: Additional metadata

    Returns:
        Chunk dictionary or None if invalid
    """
    # Clean the text
    cleaned_text = clean_text(text)

    # Skip if empty
    if not is_valid_text(cleaned_text):
        return None

    # Create chunk
    chunk = {
        "chunk_id": generate_chunk_id(),
        "text": cleaned_text,
        "candidate_id": candidate_id,
        "metadata": {
            "section": section,
            "skills": metadata.get("skills", []),
            "name": metadata.get("name", ""),
            "url": metadata.get("url", ""),
        },
    }

    return chunk


def adapt_parsed_resume(
    parsed: Dict[str, Any], candidate_id: str, url: str = ""
) -> List[Dict[str, Any]]:
    """
    Convert parsed resume output into structured chunk objects.

    Args:
        parsed: Dictionary with parsed resume data
            Expected keys: name, skills, experience, education, projects
        candidate_id: Candidate identifier (format: "cand_XXXX")

    Returns:
        List of chunk objects

    Example:
        >>> parsed = {
        ...     "name": "John Doe",
        ...     "skills": ["python", "aws"],
        ...     "experience": "Software Engineer...",
        ...     "education": "B.Tech...",
        ...     "projects": "E-commerce..."
        ... }
        >>> chunks = adapt_parsed_resume(parsed, "cand_0001")
        >>> len(chunks) >= 1
        True
    """
    # Validate candidate_id
    if not candidate_id or not isinstance(candidate_id, str):
        raise ValueError("candidate_id must be a non-empty string")

    # Enforce candidate_id format: cand_XXXX
    if not re.match(r"^cand_\d{4}$", candidate_id):
        raise ValueError("candidate_id must match format 'cand_XXXX'")

    # Initialize chunks list
    chunks: List[Dict[str, Any]] = []

    # Track used chunk_ids to prevent duplicates
    chunk_ids: set = set()

    # Extract common metadata
    name = parsed.get("name", "")
    skills = parsed.get("skills", [])

    # Base metadata
    base_metadata = {"name": name, "skills": skills, "url": url}

    # Process SKILLS section
    if skills and isinstance(skills, list) and len(skills) > 0:
        # Convert list to comma-separated string
        skills_text = ", ".join(skills)

        chunk = create_chunk(
            text=skills_text,
            candidate_id=candidate_id,
            section="skills",
            metadata=base_metadata,
        )

        if chunk and chunk["chunk_id"] not in chunk_ids:
            chunks.append(chunk)
            chunk_ids.add(chunk["chunk_id"])

    # Process EXPERIENCE section
    experience = parsed.get("experience", "")
    if experience and is_valid_text(experience):
        chunk = create_chunk(
            text=experience,
            candidate_id=candidate_id,
            section="experience",
            metadata=base_metadata,
        )

        if chunk and chunk["chunk_id"] not in chunk_ids:
            chunks.append(chunk)
            chunk_ids.add(chunk["chunk_id"])

    # Process EDUCATION section
    education = parsed.get("education", "")
    if education and is_valid_text(education):
        chunk = create_chunk(
            text=education,
            candidate_id=candidate_id,
            section="education",
            metadata=base_metadata,
        )

        if chunk and chunk["chunk_id"] not in chunk_ids:
            chunks.append(chunk)
            chunk_ids.add(chunk["chunk_id"])

    # Process PROJECTS section
    projects = parsed.get("projects", "")
    if projects and is_valid_text(projects):
        chunk = create_chunk(
            text=projects,
            candidate_id=candidate_id,
            section="projects",
            metadata=base_metadata,
        )

        if chunk and chunk["chunk_id"] not in chunk_ids:
            chunks.append(chunk)
            chunk_ids.add(chunk["chunk_id"])

    return chunks


def adapt_resume(
    parsed: Dict[str, Any], candidate_id: str, url: str = ""
) -> List[Dict[str, Any]]:
    """
    Compatibility wrapper for pipeline naming.
    """
    return adapt_parsed_resume(parsed, candidate_id, url)


def validate_chunks(chunks: List[Dict[str, Any]]) -> bool:
    """
    Validate that all chunks have required fields.

    Args:
        chunks: List of chunk objects

    Returns:
        True if all chunks are valid, False otherwise
    """
    if not chunks:
        return False

    required_fields = {"chunk_id", "text", "candidate_id", "metadata"}
    metadata_fields = {"section", "skills", "name"}

    chunk_ids = set()

    for chunk in chunks:
        # Check required fields
        if not all(field in chunk for field in required_fields):
            return False

        # Check metadata fields
        metadata = chunk.get("metadata", {})
        if not all(field in metadata for field in metadata_fields):
            return False

        # Check for duplicate chunk_ids
        chunk_id = chunk.get("chunk_id")
        if chunk_id in chunk_ids:
            return False
        chunk_ids.add(chunk_id)

        # Check non-empty text
        if not chunk.get("text", "").strip():
            return False

        # Check candidate_id exists
        if not chunk.get("candidate_id"):
            return False

    return True


def get_chunks_summary(chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate a summary of chunks.

    Args:
        chunks: List of chunk objects

    Returns:
        Summary dictionary
    """
    if not chunks:
        return {"total_chunks": 0, "sections": [], "candidate_id": None}

    sections = [chunk["metadata"]["section"] for chunk in chunks]

    return {
        "total_chunks": len(chunks),
        "sections": list(set(sections)),
        "candidate_id": chunks[0].get("candidate_id") if chunks else None,
        "has_skills": "skills" in sections,
        "has_experience": "experience" in sections,
        "has_education": "education" in sections,
        "has_projects": "projects" in sections,
    }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def chunk_to_dict(chunk: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert chunk to dictionary format (already a dict, but ensures structure).

    Args:
        chunk: Chunk object

    Returns:
        Dictionary representation
    """
    return {
        "chunk_id": chunk.get("chunk_id", ""),
        "text": chunk.get("text", ""),
        "candidate_id": chunk.get("candidate_id", ""),
        "metadata": chunk.get("metadata", {}),
    }


def merge_chunks(chunks: List[Dict[str, Any]]) -> str:
    """
    Merge all chunk texts into a single string.

    Args:
        chunks: List of chunk objects

    Returns:
        Merged text string
    """
    texts = [chunk.get("text", "") for chunk in chunks if chunk.get("text")]
    return "\n\n".join(texts)


def filter_chunks_by_section(
    chunks: List[Dict[str, Any]], section: str
) -> List[Dict[str, Any]]:
    """
    Filter chunks by section name.

    Args:
        chunks: List of chunk objects
        section: Section name to filter by

    Returns:
        Filtered list of chunks
    """
    return [
        chunk for chunk in chunks if chunk.get("metadata", {}).get("section") == section
    ]


# ============================================================================
# MODULE EXECUTION (for testing)
# ============================================================================

if __name__ == "__main__":
    # Test data
    test_parsed = {
        "name": "John Doe",
        "skills": ["python", "aws", "docker", "kubernetes"],
        "experience": "Software Engineer at Tech Corp (2020-Present)\n- Developed microservices\n- Led team of 5",
        "education": "Bachelor of Science in Computer Science\nStanford University (2016-2020)",
        "projects": "E-commerce Platform\n- Built full-stack application\n- Technologies: Django, React",
    }

    print("=" * 70)
    print("PARSER ADAPTER - TEST EXECUTION")
    print("=" * 70)

    # Test adaptation
    chunks = adapt_parsed_resume(test_parsed, "cand_0001")

    print(f"\nGenerated {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks, 1):
        print(f"\n--- Chunk {i} ---")
        print(f"Chunk ID: {chunk['chunk_id']}")
        print(f"Section: {chunk['metadata']['section']}")
        print(f"Text preview: {chunk['text'][:80]}...")

    # Test validation
    is_valid = validate_chunks(chunks)
    print(f"\n✓ Chunks valid: {is_valid}")

    # Test summary
    summary = get_chunks_summary(chunks)
    print(f"\n✓ Summary: {summary}")
