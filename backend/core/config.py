import os
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Built-in lightweight .env loader (guarantees .env is parsed without external packages)
_LAST_ENV_MTIME: Optional[float] = None

def _load_env_file(path: Path, override: bool = False):
    global _LAST_ENV_MTIME
    if not path.is_file():
        return
    try:
        _LAST_ENV_MTIME = path.stat().st_mtime
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if override or k not in os.environ:
                    os.environ[k] = v
    except Exception as e:
        print(f"Warning: Failed to read .env file at {path}: {e}")

def _resolve_path(env_val: Optional[str], default_path: Path) -> Path:
    if not env_val:
        return default_path
    p = Path(env_val)
    if not p.is_absolute():
        return (BASE_DIR / p).resolve()
    return p.resolve()

_load_env_file(BASE_DIR / ".env")

class Settings:
    PROJECT_NAME: str = "AI-Powered Resume Tailoring System"
    VERSION: str = "1.0.0"
    
    # Paths (Always anchored to BASE_DIR if relative)
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = _resolve_path(os.getenv("DATA_DIR"), BASE_DIR / "data")
    MASTER_RESUME_PATH: Path = _resolve_path(os.getenv("MASTER_RESUME_PATH"), BASE_DIR / "data" / "master" / "master_resume.md")
    PROJECTS_DIR: Path = _resolve_path(os.getenv("PROJECTS_DIR"), BASE_DIR / "data" / "projects")
    OUTPUT_DIR: Path = _resolve_path(os.getenv("OUTPUT_DIR"), BASE_DIR / "data" / "output")
    STATIC_DIR: Path = _resolve_path(os.getenv("STATIC_DIR"), BASE_DIR / "frontend" / "static")
    
    # AI / LLM Configuration
    # Supported: "gemini", "anthropic", "openai", "mock"
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY", None)
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Stage 0 High-Reasoning JD Structurer (Optional separate API key & reasoning model)
    GEMINI_REASONING_API_KEY: Optional[str] = os.getenv("GEMINI_REASONING_API_KEY", None)
    GEMINI_REASONING_MODEL: str = os.getenv("GEMINI_REASONING_MODEL", "gemini-2.5-pro")
    
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY", None)
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

    # Determine default provider
    _default_provider = "mock"
    if os.getenv("LLM_PROVIDER"):
        _default_provider = os.getenv("LLM_PROVIDER").lower()
    elif GEMINI_API_KEY:
        _default_provider = "gemini"
    elif ANTHROPIC_API_KEY:
        _default_provider = "anthropic"
    elif OPENAI_API_KEY:
        _default_provider = "openai"

    LLM_PROVIDER: str = _default_provider

    # GitHub Project Sync Configuration
    GITHUB_USERNAME: str = os.getenv("GITHUB_USERNAME", "SidhuManbirSingh")
    GITHUB_TOKEN: Optional[str] = os.getenv("GITHUB_TOKEN", None)
    AUTO_SYNC_GITHUB_PROJECTS: bool = os.getenv("AUTO_SYNC_GITHUB_PROJECTS", "true").lower() in ("true", "1", "yes")
    GITHUB_SYNC_LIMIT: int = int(os.getenv("GITHUB_SYNC_LIMIT", "5"))

    # Guardrail Limits
    MAX_JOB_DESCRIPTION_CHARS: int = int(os.getenv("MAX_JD_CHARS", "25000"))
    MIN_JOB_DESCRIPTION_WORDS: int = int(os.getenv("MIN_JD_WORDS", "15"))

    def reload_if_env_changed(self):
        """Hot-reloads .env values if the .env file was modified since startup."""
        env_path = BASE_DIR / ".env"
        if not env_path.is_file():
            return
        try:
            current_mtime = env_path.stat().st_mtime
            if _LAST_ENV_MTIME is None or current_mtime > _LAST_ENV_MTIME:
                _load_env_file(env_path, override=True)
                self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", None)
                self.GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                self.GEMINI_REASONING_API_KEY = os.getenv("GEMINI_REASONING_API_KEY", None)
                self.GEMINI_REASONING_MODEL = os.getenv("GEMINI_REASONING_MODEL", "gemini-2.5-pro")
                self.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", None)
                self.ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
                self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", None)
                self.OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
                self.GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "SidhuManbirSingh")
                self.GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", None)
                self.AUTO_SYNC_GITHUB_PROJECTS = os.getenv("AUTO_SYNC_GITHUB_PROJECTS", "true").lower() in ("true", "1", "yes")
                self.GITHUB_SYNC_LIMIT = int(os.getenv("GITHUB_SYNC_LIMIT", "5"))
                if os.getenv("LLM_PROVIDER"):
                    self.LLM_PROVIDER = os.getenv("LLM_PROVIDER").lower()
        except Exception:
            pass

settings = Settings()
