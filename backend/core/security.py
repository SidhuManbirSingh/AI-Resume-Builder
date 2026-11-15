import re
from fastapi import HTTPException
from backend.core.config import settings

def sanitize_job_description(raw_text: str) -> str:
    """
    Sanitizes the input job description:
    - Verifies length bounds (min words, max characters).
    - Strips dangerous control characters and null bytes.
    - Neutralizes potential delimiter escape attempts (e.g., closing XML tags).
    """
    if not raw_text or not raw_text.strip():
        raise HTTPException(status_code=400, detail="Job description cannot be empty.")
    
    cleaned = raw_text.replace("\x00", "").strip()
    
    # Check max character ceiling
    if len(cleaned) > settings.MAX_JOB_DESCRIPTION_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Job description is too large ({len(cleaned)} characters). Maximum permitted is {settings.MAX_JOB_DESCRIPTION_CHARS}."
        )
    
    # Check minimum word floor
    words = cleaned.split()
    if len(words) < settings.MIN_JOB_DESCRIPTION_WORDS:
        raise HTTPException(
            status_code=400,
            detail=f"Job description too brief ({len(words)} words). Please paste a complete job description (minimum {settings.MIN_JOB_DESCRIPTION_WORDS} words)."
        )
    
    # Neutralize injection delimiters (case-insensitive regex across all XML prompt tags)
    cleaned = re.sub(
        r'</?\s*(?:job_description|untrusted_job_description|untrusted_user_notes|raw_job_posting|stage0_structured_brief|stage0_blueprint|resume|candidate_profile|project_catalog|requirement_matrix)\s*>',
        '',
        cleaned,
        flags=re.IGNORECASE
    )
    
    return cleaned


def sanitize_additional_notes(notes: str) -> str:
    """
    Sanitizes optional additional_notes against prompt delimiter breakout and excessive length.
    """
    if not notes or not notes.strip():
        return ""
    cleaned = notes.replace("\x00", "").strip()[:2000]
    cleaned = re.sub(
        r'</?\s*(?:job_description|untrusted_job_description|untrusted_user_notes|raw_job_posting|stage0_structured_brief|stage0_blueprint|resume|candidate_profile|project_catalog|requirement_matrix)\s*>',
        '',
        cleaned,
        flags=re.IGNORECASE
    )
    return cleaned

def strip_github_links(text: str) -> str:
    """
    Mandatory Rule 4.8: Do not include a GitHub profile link in the generated resume.
    Strips raw URLs, markdown links, or plain text references to GitHub profiles.
    Preserves other contact items (LinkedIn, email, phone, personal website).
    """
    # 1. Remove markdown links: [GitHub](https://github.com/username) or [username](https://github.com/...)
    text = re.sub(r'\[([^\]]*?)\]\(https?://(?:www\.)?github\.com/[^\)\s]+\)', '', text, flags=re.IGNORECASE)
    
    # 2. Remove standard URLs: https://github.com/username or github.com/username
    text = re.sub(r'https?://(?:www\.)?github\.com/[A-Za-z0-9_\-\.]+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'(?<!\w)github\.com/[A-Za-z0-9_\-\.]+', '', text, flags=re.IGNORECASE)
    
    # 3. Clean up dangling delimiters like "|  |" or "| \n" in contact headers
    text = re.sub(r'\|\s*\|', '|', text)
    text = re.sub(r'\|\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\|', '', text, flags=re.MULTILINE)
    text = re.sub(r'[ \t]+', ' ', text)
    
    return text.strip()

def sanitize_filename(filename: str, default_name: str = "document", extension: str = ".pdf") -> str:
    """
    Sanitizes download filenames to prevent HTTP response splitting, header injection,
    and path traversal attacks (CWE-113 / CWE-22).
    """
    if not filename:
        return f"{default_name}{extension}"
    
    # Strip dangerous characters: quotes, newlines, carriage returns, slashes, control characters
    clean = re.sub(r'[\r\n"\'\\/\x00<>:|?*]', '', filename).strip()
    clean = clean.replace("..", "")
    if not clean or clean == extension:
        clean = default_name
    
    if not clean.endswith(extension):
        clean += extension
    return clean
