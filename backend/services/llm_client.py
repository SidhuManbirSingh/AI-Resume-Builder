"""
Backward-compatible facade re-exporting the modularized LLM client package (`backend.llm`).
See:
  - backend/llm/base.py
  - backend/llm/prompts.py
  - backend/llm/mock.py
  - backend/llm/gemini.py
  - backend/llm/anthropic.py
  - backend/llm/openai.py
"""
from backend.llm import (
    BaseLLMClient,
    MockLLMClient,
    GeminiLLMClient,
    AnthropicLLMClient,
    OpenAILLMClient,
    get_llm_client,
    STAGE1_RESPONSE_SCHEMA,
    STAGE2_RESPONSE_SCHEMA,
    _clean_extracted_title,
    _parse_and_structure_raw_jd,
    _extract_json,
    _build_stage1_prompts,
    _build_stage2_prompts,
    _build_cover_letter_prompts,
    _build_outreach_prompts,
)

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
