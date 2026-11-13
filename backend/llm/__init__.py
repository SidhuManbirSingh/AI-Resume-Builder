from backend.core.config import settings
from backend.llm.base import (
    BaseLLMClient,
    _clean_extracted_title,
    _parse_and_structure_raw_jd,
    _extract_json
)
from backend.llm.prompts import (
    STAGE1_RESPONSE_SCHEMA,
    STAGE2_RESPONSE_SCHEMA,
    _build_stage1_prompts,
    _build_stage2_prompts,
    _build_cover_letter_prompts,
    _build_outreach_prompts
)
from backend.llm.mock import MockLLMClient
from backend.llm.gemini import GeminiLLMClient
from backend.llm.anthropic import AnthropicLLMClient
from backend.llm.openai import OpenAILLMClient


def get_llm_client() -> BaseLLMClient:
    """
    Factory returning the configured LLM client (hot-reloading .env if modified).
    """
    settings.reload_if_env_changed()
    provider = settings.LLM_PROVIDER
    if provider == "mock":
        return MockLLMClient()
    elif provider == "gemini" and (settings.GEMINI_API_KEY or settings.GEMINI_REASONING_API_KEY):
        primary_key = settings.GEMINI_API_KEY or settings.GEMINI_REASONING_API_KEY
        return GeminiLLMClient(
            api_key=primary_key,
            model=settings.GEMINI_MODEL,
            reasoning_api_key=settings.GEMINI_REASONING_API_KEY,
            reasoning_model=settings.GEMINI_REASONING_MODEL
        )
    elif provider == "anthropic" and settings.ANTHROPIC_API_KEY:
        return AnthropicLLMClient(api_key=settings.ANTHROPIC_API_KEY, model=settings.ANTHROPIC_MODEL)
    elif provider == "openai" and settings.OPENAI_API_KEY:
        return OpenAILLMClient(api_key=settings.OPENAI_API_KEY, model=settings.OPENAI_MODEL)
    elif settings.GEMINI_API_KEY or settings.GEMINI_REASONING_API_KEY:
        primary_key = settings.GEMINI_API_KEY or settings.GEMINI_REASONING_API_KEY
        return GeminiLLMClient(
            api_key=primary_key,
            model=settings.GEMINI_MODEL,
            reasoning_api_key=settings.GEMINI_REASONING_API_KEY,
            reasoning_model=settings.GEMINI_REASONING_MODEL
        )
    else:
        return MockLLMClient()


__all__ = [
    "BaseLLMClient",
    "MockLLMClient",
    "GeminiLLMClient",
    "AnthropicLLMClient",
    "OpenAILLMClient",
    "get_llm_client",
    "STAGE1_RESPONSE_SCHEMA",
    "STAGE2_RESPONSE_SCHEMA",
    "_clean_extracted_title",
    "_parse_and_structure_raw_jd",
    "_extract_json",
    "_build_stage1_prompts",
    "_build_stage2_prompts",
    "_build_cover_letter_prompts",
    "_build_outreach_prompts",
]

