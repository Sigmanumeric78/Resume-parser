"""
Production-Grade Resume Parser
Hybrid approach: Rule-based parsing (primary) + LLM fallback (only when required)
"""

import json
import os
import re
from typing import Any, Dict, List, Optional, cast

pdfplumber = None
try:
    import pdfplumber

    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False


# ============================================================================
# STEP 1: TEXT EXTRACTION
# ============================================================================


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from PDF using pdfplumber.

    Args:
        file_path: Path to PDF file

    Returns:
        Extracted text as single string, or empty string on failure
    """
    if pdfplumber is None:
        print("WARNING: pdfplumber not available")
        return ""

    if not os.path.exists(file_path):
        print(f"ERROR: File not found: {file_path}")
        return ""

    try:
        text_parts: List[str] = []
        _pdfplumber = cast(Any, pdfplumber)

        with _pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        full_text = "\n".join(text_parts)
        return full_text.strip()

    except Exception as e:
        print(f"ERROR extracting text from PDF: {e}")
        return ""


# ============================================================================
# STEP 2: NAME EXTRACTION
# ============================================================================


def extract_name(text: str) -> str:
    """
    Extract candidate name using heuristic: first non-empty line.
    Removes emails and phone numbers.

    Args:
        text: Full resume text

    Returns:
        Extracted name or empty string
    """
    if not text:
        return ""

    lines = text.strip().split("\n")

    # Email pattern
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    # Phone pattern (various formats)
    phone_pattern = r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"

    for line in lines:
        # Clean the line
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Skip lines that are just emails or phones
        if re.match(rf"^{email_pattern}$", line):
            continue
        if re.match(rf"^{phone_pattern}$", line):
            continue

        # Remove emails and phones from the line
        line = re.sub(email_pattern, "", line)
        line = re.sub(phone_pattern, "", line)

        # Clean up extra whitespace
        line = " ".join(line.split())

        # Skip if line becomes empty after cleaning
        if not line:
            continue

        # Skip if line is too long (likely a paragraph)
        if len(line) > 100:
            continue

        # Skip if line contains typical section keywords
        lower_line = line.lower()
        skip_keywords = [
            "resume",
            "curriculum vitae",
            "cv",
            "email",
            "phone",
            "linkedin",
            "github",
            "address",
            "profile",
            "summary",
            "objective",
            "career",
            "professional",
        ]
        if any(keyword in lower_line for keyword in skip_keywords):
            continue

        uppercase_keywords = {
            "ENGINEER",
            "SPECIALIST",
            "TECHNICIAN",
            "MANAGER",
            "DEVELOPER",
        }
        if line.isupper() and any(keyword in line for keyword in uppercase_keywords):
            continue

        # Return first valid line as name
        return line.strip()

    return ""


# ============================================================================
# STEP 3: SECTION EXTRACTION (REGEX)
# ============================================================================

# Known section headers to stop at
KNOWN_SECTIONS = [
    "experience",
    "work experience",
    "professional experience",
    "employment",
    "work history",
    "professional background",
    "career focus",
    "education",
    "education and training",
    "academic background",
    "academic qualifications",
    "educational background",
    "academics",
    "skills",
    "technical skills",
    "core competencies",
    "key skills",
    "competencies",
    "technologies",
    "technical expertise",
    "skill set",
    "areas of expertise",
    "projects",
    "personal projects",
    "academic projects",
    "project experience",
    "key projects",
    "notable projects",
    "summary",
    "objective",
    "profile",
    "about",
    "contact",
    "certifications",
    "awards",
    "achievements",
    "accomplishments",
    "publications",
    "professional affiliations",
    "references",
    "languages",
    "interests",
    "hobbies",
]


def extract_section(text: str, section_names: List[str]) -> str:
    """
    Extract a section from resume text using regex patterns.

    Args:
        text: Full resume text
        section_names: List of possible section header names

    Returns:
        Extracted section content or empty string
    """
    if not text or not section_names:
        return ""

    # Escape section names for regex
    escaped_names = [re.escape(name) for name in section_names]
    escaped_known = [re.escape(s) for s in KNOWN_SECTIONS]

    # Build regex pattern
    # Look for section header on its own line (possibly with colon)
    # Capture everything until next known section header or end
    pattern = (
        r"(?i)^[ \t]*("
        + "|".join(escaped_names)
        + r")[ \t]*:?[ \t]*\n(.*?)(?=\n[ \t]*("
        + "|".join(escaped_known)
        + r")[ \t]*:?[ \t]*\n|\Z)"
    )

    match = re.search(pattern, text, re.MULTILINE | re.DOTALL | re.IGNORECASE)

    if match:
        content = match.group(2).strip()
        return content

    return ""


def extract_experience(text: str) -> str:
    """Extract experience section."""
    section_names = [
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "work history",
        "professional background",
    ]
    return extract_section(text, section_names)


def extract_education(text: str) -> str:
    """Extract education section."""
    section_names = [
        "education",
        "academic background",
        "academic qualifications",
        "educational background",
        "academics",
    ]
    return extract_section(text, section_names)


def extract_projects(text: str) -> str:
    """Extract projects section."""
    section_names = [
        "projects",
        "personal projects",
        "academic projects",
        "project experience",
        "key projects",
        "notable projects",
    ]
    return extract_section(text, section_names)


# ============================================================================
# STEP 4: SKILLS EXTRACTION
# ============================================================================


def extract_skills(text: str) -> List[str]:
    """
    Extract skills from skills section.
    Splits by commas, newlines, bullet points, and dashes.

    Args:
        text: Full resume text or skills section

    Returns:
        List of normalized skills
    """
    if not text:
        return []

    # First try to extract skills section
    skills_section_names = [
        "skills",
        "technical skills",
        "core competencies",
        "key skills",
        "competencies",
        "technologies",
        "technical expertise",
        "skill set",
    ]

    skills_section = extract_section(text, skills_section_names)

    # If no skills section found, use the entire text
    content = skills_section if skills_section else text

    # Split by common delimiters
    # Comma, newline, bullet point, dash, semicolon
    parts = re.split(r"[,\n•·–—;]", content)

    skills: List[str] = []

    for part in parts:
        # Normalize: lowercase and strip
        skill = part.lower().strip()

        # Remove leading/trailing special characters
        skill = re.sub(r"^[\s\-\*•]+|[\s\-\*•]+$", "", skill)

        # Skip empty or too short
        if not skill or len(skill) < 2:
            continue

        # Skip if too long (likely not a skill)
        if len(skill) > 50:
            continue

        # Skip common non-skill words
        skip_words = {
            "and",
            "or",
            "the",
            "a",
            "an",
            "in",
            "at",
            "of",
            "with",
            "for",
            "to",
            "from",
            "by",
            "skills",
            "technical",
        }
        if skill in skip_words:
            continue

        # Add if not duplicate
        if skill not in skills:
            skills.append(skill)

    return skills


# ============================================================================
# STEP 5: DETECT MISSING SECTIONS
# ============================================================================


def detect_missing_fields(parsed_data: Dict[str, Any]) -> List[str]:
    """
    Identify which fields are missing or empty.

    Args:
        parsed_data: Dictionary with parsed resume data

    Returns:
        List of field names that are missing
    """
    missing: List[str] = []

    # Fields to check (excluding name which has different handling)
    fields_to_check = ["experience", "education", "projects", "skills"]

    for field in fields_to_check:
        value = parsed_data.get(field)

        # Check if empty string
        if value == "":
            missing.append(field)
        # Check if None
        elif value is None:
            missing.append(field)
        # Check if empty list (for skills)
        elif isinstance(value, list) and len(value) == 0:
            missing.append(field)

    return missing


# ============================================================================
# STEP 6: GLM5 FALLBACK
# ============================================================================


def call_glm5_for_missing_fields(
    resume_text: str, missing_fields: List[str], api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Call GLM5 API to extract ONLY missing fields.

    Args:
        resume_text: Full resume text
        missing_fields: List of fields that need to be extracted
        api_key: Optional API key for GLM5

    Returns:
        Dictionary with extracted missing fields
    """
    if not missing_fields:
        return {}

    if not resume_text:
        return {}

    # Get API key from environment if not provided
    if not api_key:
        api_key = os.environ.get("GLM5_API_KEY") or os.environ.get("NVIDIA_API_KEY")

    if not api_key:
        print("WARNING: No GLM5 API key available for fallback")
        return {}

    # Build field-specific prompt
    fields_str = ", ".join(missing_fields)

    prompt = f"""Extract ONLY the following missing fields from this resume: {fields_str}

Return STRICT JSON format:
{{
    "experience": "...",
    "education": "...",
    "projects": "...",
    "skills": ["skill1", "skill2"]
}}

Rules:
- Only extract fields that are present in the resume
- If a field is not found, use empty string "" (or empty list [] for skills)
- Do NOT hallucinate or invent information
- Keep descriptions concise but informative

Resume:
{resume_text[:4000]}

Return ONLY the JSON object, no additional text:"""

    try:
        import httpx

        # GLM5 API endpoint (adjust based on actual API)
        api_url = os.environ.get(
            "GLM5_API_URL", "https://integrate.api.nvidia.com/v1/chat/completions"
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "nvidia/nemotron-5b",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 1000,
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.post(api_url, headers=headers, json=payload)

            if response.status_code != 200:
                print(f"GLM5 API error: {response.status_code}")
                return {}

            result = response.json()

            # Extract content from response
            content = (
                result.get("choices", [{}])[0].get("message", {}).get("content", "")
            )

            # Parse JSON from response
            # Try to find JSON in the response
            json_match = re.search(r"\{[\s\S]*\}", content)

            if json_match:
                extracted = json.loads(json_match.group())

                # Filter to only requested fields
                filtered = {}
                for field in missing_fields:
                    if field in extracted:
                        filtered[field] = extracted[field]

                return filtered

    except json.JSONDecodeError as e:
        print(f"GLM5 JSON parse error: {e}")
    except Exception as e:
        print(f"GLM5 API call failed: {e}")

    return {}


# ============================================================================
# STEP 7: MERGE OUTPUT
# ============================================================================


def merge_results(
    rule_based: Dict[str, Any], llm_fallback: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge rule-based results with LLM fallback.
    NEVER overwrite existing correct data.

    Args:
        rule_based: Results from rule-based parsing
        llm_fallback: Results from LLM fallback

    Returns:
        Merged dictionary
    """
    merged = rule_based.copy()

    for field, value in llm_fallback.items():
        # Only fill if rule-based result is empty/missing
        existing = merged.get(field)

        # Check if existing value is empty
        is_empty = (
            existing is None
            or existing == ""
            or (isinstance(existing, list) and len(existing) == 0)
        )

        # Only use LLM value if existing is empty
        if is_empty and value:
            merged[field] = value

    return merged


# ============================================================================
# STEP 8: FINAL FUNCTION
# ============================================================================


def parse_resume(file_path: str, use_llm_fallback: bool = False) -> Dict[str, Any]:
    """
    Main entry point for resume parsing.

    Flow:
    1. Extract text from PDF
    2. Run rule-based parsing
    3. Identify missing fields
    4. Call GLM5 if needed
    5. Merge results
    6. Return final dict

    Args:
        file_path: Path to resume PDF file
        use_llm_fallback: Whether to use LLM for missing fields

    Returns:
        Structured dictionary with resume data
    """
    use_llm_fallback = False
    # Initialize empty result structure
    empty_result = {
        "name": "",
        "skills": [],
        "experience": "",
        "education": "",
        "projects": "",
    }

    # STEP 1: Extract text
    text = extract_text_from_pdf(file_path)

    if not text:
        print("WARNING: No text extracted from PDF")
        return empty_result

    # STEP 2: Rule-based parsing
    rule_based_result = {
        "name": extract_name(text),
        "skills": extract_skills(text),
        "experience": extract_experience(text),
        "education": extract_education(text),
        "projects": extract_projects(text),
    }

    # STEP 3: Detect missing fields
    missing_fields = detect_missing_fields(rule_based_result)

    # STEP 4: LLM fallback (only if missing fields and enabled)
    llm_result = {}

    if missing_fields and use_llm_fallback:
        print(f"INFO: Missing fields detected: {missing_fields}")
        print("INFO: Attempting LLM fallback...")

        llm_result = call_glm5_for_missing_fields(text, missing_fields)

    # STEP 5: Merge results
    final_result = merge_results(rule_based_result, llm_result)

    # STEP 6: Return final dict
    return final_result


# ============================================================================
# STEP 9: ERROR HANDLING (Wrapper Functions)
# ============================================================================


def safe_parse_resume(file_path: str, use_llm_fallback: bool = False) -> Dict[str, Any]:
    """
    Safe wrapper around parse_resume that never crashes.

    Args:
        file_path: Path to resume PDF file
        use_llm_fallback: Whether to use LLM for missing fields

    Returns:
        Structured dictionary with resume data (empty on any error)
    """
    empty_result = {
        "name": "",
        "skills": [],
        "experience": "",
        "education": "",
        "projects": "",
    }

    try:
        return parse_resume(file_path, use_llm_fallback)
    except Exception as e:
        print(f"ERROR in safe_parse_resume: {e}")
        return empty_result


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def validate_parsed_resume(data: Dict[str, Any]) -> bool:
    """
    Validate that parsed resume has at least some data.

    Args:
        data: Parsed resume dictionary

    Returns:
        True if at least one field has data
    """
    if not data:
        return False

    # Check if at least one field has meaningful data
    has_name = bool(data.get("name", "").strip())
    has_skills = len(data.get("skills", [])) > 0
    has_experience = bool(data.get("experience", "").strip())
    has_education = bool(data.get("education", "").strip())
    has_projects = bool(data.get("projects", "").strip())

    return has_name or has_skills or has_experience or has_education or has_projects


def get_parsing_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get a summary of parsing results.

    Args:
        data: Parsed resume dictionary

    Returns:
        Summary dictionary with field status
    """
    return {
        "has_name": bool(data.get("name", "").strip()),
        "skills_count": len(data.get("skills", [])),
        "has_experience": bool(data.get("experience", "").strip()),
        "has_education": bool(data.get("education", "").strip()),
        "has_projects": bool(data.get("projects", "").strip()),
        "is_complete": all(
            [
                data.get("name", "").strip(),
                data.get("skills", []),
                data.get("experience", "").strip(),
                data.get("education", "").strip(),
                data.get("projects", "").strip(),
            ]
        ),
    }


# ============================================================================
# MODULE EXECUTION (for testing)
# ============================================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python resume_parser.py <resume_pdf_path>")
        print("\nThis module is designed to be imported, not run directly.")
        print("\nExample usage:")
        print("  from resume_parser import parse_resume")
        print("  result = parse_resume('resume.pdf')")
        print("  print(result)")
        sys.exit(1)

    pdf_path = sys.argv[1]

    print(f"Parsing resume: {pdf_path}")
    print("-" * 60)

    result = safe_parse_resume(pdf_path)

    print("\nParsed Result:")
    print(json.dumps(result, indent=2))

    print("\nParsing Summary:")
    summary = get_parsing_summary(result)
    print(json.dumps(summary, indent=2))
