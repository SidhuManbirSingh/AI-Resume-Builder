import json
import time
import logging
import requests
from typing import List, Dict, Any, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError
from backend.models.schemas import (
    ProjectMetadata,
    Stage1AnalysisResult,
    Stage2CustomizationResult
)
from backend.llm.base import (
    BaseLLMClient,
    _parse_and_structure_raw_jd,
    _clean_extracted_title,
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
from backend.services.fact_registry import CandidateFactRegistry
from backend.services.scoring import DeterministicScorer

logger = logging.getLogger(__name__)
TModel = TypeVar("TModel", bound=BaseModel)


class GeminiLLMClient(BaseLLMClient):
    """
    Production client connecting to Google Gemini API.
    - Passes API key exclusively via 'x-goog-api-key' HTTP header (never in URL query params).
    - Enforces structural output via 'responseSchema' in 'generationConfig'.
    - Retries transient HTTP 429 and 503 responses with exponential backoff.
    - Bounded schema validation retry loop (MAX_SCHEMA_RETRIES = 2) on malformed JSON/schema responses.
    - Supports optional Stage 0 high-reasoning JD structurer key/model.
    """
    provider_name = "gemini"
    MAX_SCHEMA_RETRIES = 2

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-4-hydrogen",
        reasoning_api_key: Optional[str] = None,
        reasoning_model: str = "gemini-3.1-pro",
        max_retries: int = 3,
        base_backoff: float = 0.5
    ):
        self.api_key = api_key
        self.model = model.replace("models/", "")
        self.reasoning_api_key = (
            reasoning_api_key.strip()
            if reasoning_api_key and reasoning_api_key.strip()
            else api_key
        )
        self.reasoning_model = (reasoning_model or "gemini-2.5-pro").replace("models/", "")
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self._stage0_cache: Dict[str, Dict[str, Any]] = {}

    def _call_gemini_endpoint(
        self,
        system_instruction: str,
        user_prompt: str,
        api_key: str,
        model_name: str,
        response_schema: Optional[Dict[str, Any]] = None,
        thinking_budget: Optional[int] = None
    ) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }
        gen_config: Dict[str, Any] = {
            "responseMimeType": "application/json",
            "temperature": 0.2
        }
        if response_schema is not None:
            gen_config["responseSchema"] = response_schema
        if thinking_budget is not None:
            gen_config["thinkingConfig"] = {"thinkingBudget": thinking_budget}
        elif "2.5-flash" in model_name:
            gen_config["thinkingConfig"] = {"thinkingBudget": 0}

        payload = {
            "system_instruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}]
                }
            ],
            "generationConfig": gen_config
        }

        last_response = None
        last_timeout_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=(10, 25))
            except requests.exceptions.Timeout as exc:
                last_timeout_exc = exc
                if attempt < self.max_retries - 1:
                    sleep_seconds = self.base_backoff * (2 ** attempt)
                    logger.warning(
                        "Gemini API timed out on %s (attempt %d/%d); retrying in %.2fs",
                        model_name, attempt + 1, self.max_retries, sleep_seconds,
                    )
                    time.sleep(sleep_seconds)
                    continue
                raise RuntimeError(f"Gemini API timeout on {model_name}: {exc}") from exc

            last_response = response
            if response.status_code in (429, 503) and attempt < self.max_retries - 1:
                sleep_seconds = self.base_backoff * (2 ** attempt)
                logger.warning(
                    "Gemini API returned HTTP %s on %s (attempt %d/%d); retrying in %.2fs",
                    response.status_code, model_name, attempt + 1, self.max_retries, sleep_seconds
                )
                time.sleep(sleep_seconds)
                continue
            break

        if last_response is None:
            raise RuntimeError(f"Gemini API timeout on {model_name}: {last_timeout_exc}")

        if last_response.status_code != 200:
            raise RuntimeError(f"Gemini API Error ({last_response.status_code}) on {model_name}: {last_response.text}")

        data = last_response.json()
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError(f"Gemini returned no candidates: {data}")
            parts = candidates[0]["content"]["parts"]
            for p in reversed(parts):
                if "text" in p and not p.get("thought", False):
                    return p["text"]
            return parts[-1]["text"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected Gemini response structure: {data} (Error: {e})")

    def _call_gemini(
        self,
        system_instruction: str,
        user_prompt: str,
        response_schema: Optional[Dict[str, Any]] = None
    ) -> str:
        """Calls primary model (gemini-2.5-flash), trying reasoning_api_key and fallback 'gemini-2.0-flash' on RuntimeError."""
        try:
            return self._call_gemini_endpoint(
                system_instruction,
                user_prompt,
                self.api_key,
                self.model,
                response_schema=response_schema
            )
        except RuntimeError as primary_err:
            if self.reasoning_api_key and self.reasoning_api_key != self.api_key:
                try:
                    return self._call_gemini_endpoint(
                        system_instruction,
                        user_prompt,
                        self.reasoning_api_key,
                        self.model,
                        response_schema=response_schema
                    )
                except RuntimeError:
                    pass
            if self.model != "gemini-2.0-flash":
                logger.warning(
                    "Primary model '%s' failed (%s); falling back to 'gemini-2.0-flash'.",
                    self.model, primary_err,
                )
                return self._call_gemini_endpoint(
                    system_instruction,
                    user_prompt,
                    self.api_key,
                    "gemini-2.0-flash",
                    response_schema=response_schema,
                )
            raise primary_err

    def structure_raw_job_description(self, job_description: str, master_parsed: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deterministically structures the raw job posting and caches it for Stage 1 & Stage 2.
        """
        cache_key = job_description[:500]
        if cache_key in self._stage0_cache:
            return self._stage0_cache[cache_key]

        base_structured = _parse_and_structure_raw_jd(job_description)
        self._stage0_cache[cache_key] = base_structured
        return base_structured

    def _call_with_schema_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Dict[str, Any],
        model_cls: Type[TModel],
    ) -> TModel:
        """
        Calls Gemini with bounded schema retries if JSON extraction or Pydantic validation fails.
        """
        current_prompt = user_prompt
        last_err: Optional[Exception] = None
        for attempt in range(self.MAX_SCHEMA_RETRIES + 1):
            raw_response = self._call_gemini(system_prompt, current_prompt, response_schema=response_schema)
            try:
                json_clean = _extract_json(raw_response)
                parsed = json.loads(json_clean)
                return model_cls.model_validate(parsed)
            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                last_err = exc
                logger.warning(
                    "Schema validation attempt %d/%d failed for %s: %s",
                    attempt + 1,
                    self.MAX_SCHEMA_RETRIES + 1,
                    model_cls.__name__,
                    exc,
                )
                current_prompt = (
                    f"{user_prompt}\n\n"
                    f"CORRECTION REQUIRED: Previous output failed JSON/schema validation ({exc}). "
                    "Return ONLY strictly valid raw JSON matching the exact schema."
                )
        raise ValueError(f"Failed schema validation for {model_cls.__name__} after retries: {last_err}")

    def analyze_and_select(
        self,
        job_description: str,
        master_parsed: Dict[str, Any],
        projects: List[ProjectMetadata]
    ) -> Stage1AnalysisResult:
        structured = self.structure_raw_job_description(job_description, master_parsed)
        fact_registry = CandidateFactRegistry.build(master_parsed, projects=projects)
        project_scores = DeterministicScorer.rank_projects(projects, structured, job_description)
        requirement_matrix = DeterministicScorer.build_requirement_matrix(structured, fact_registry, projects)

        system_prompt, user_prompt = _build_stage1_prompts(
            job_description,
            master_parsed,
            projects,
            structured=structured,
            project_scores=project_scores,
        )
        result = self._call_with_schema_retry(
            system_prompt, user_prompt, STAGE1_RESPONSE_SCHEMA, Stage1AnalysisResult
        )
        valid_ids = {p.id for p in projects}
        if result.slot1_project_id not in valid_ids and project_scores:
            logger.warning(
                "Stage 1 returned unknown project id '%s'; falling back to top scored '%s'.",
                result.slot1_project_id,
                project_scores[0].project_id,
            )
            result.slot1_project_id = project_scores[0].project_id
        result.project_scores = project_scores
        result.requirement_matrix = requirement_matrix
        if len(result.target_role_title) > 65 or "\n" in result.target_role_title:
            result.target_role_title = _clean_extracted_title(structured["clean_role_title"])
        if not result.target_company and structured.get("target_company"):
            result.target_company = structured["target_company"]
        return result

    def customize_sections(
        self,
        job_description: str,
        master_parsed: Dict[str, Any],
        stage1_result: Stage1AnalysisResult,
        projects: List[ProjectMetadata]
    ) -> Stage2CustomizationResult:
        structured = self.structure_raw_job_description(job_description, master_parsed)
        system_prompt, user_prompt = _build_stage2_prompts(
            job_description, master_parsed, stage1_result, projects, structured
        )
        return self._call_with_schema_retry(
            system_prompt, user_prompt, STAGE2_RESPONSE_SCHEMA, Stage2CustomizationResult
        )

    def generate_cover_letter(
        self,
        job_description: str,
        resume_markdown: str,
        additional_notes: Optional[str] = None,
        contact_info: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        system_prompt, user_prompt = _build_cover_letter_prompts(
            job_description, resume_markdown, additional_notes, contact_info=contact_info
        )
        raw_response = self._call_gemini(system_prompt, user_prompt)
        json_clean = _extract_json(raw_response)
        data = json.loads(json_clean)
        return {
            "cover_letter_markdown": data.get("cover_letter_markdown", "").strip(),
            "target_role_title": data.get("target_role_title", "Candidate"),
            "target_company": data.get("target_company")
        }

    def generate_outreach(
        self,
        job_description: str,
        resume_markdown: str,
        additional_notes: Optional[str] = None,
        contact_info: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        system_prompt, user_prompt = _build_outreach_prompts(
            job_description, resume_markdown, additional_notes, contact_info=contact_info
        )
        raw_response = self._call_gemini(system_prompt, user_prompt)
        json_clean = _extract_json(raw_response)
        data = json.loads(json_clean)
        return {
            "linkedin_message": data.get("linkedin_message", "").strip(),
            "email_subject": data.get("email_subject", "").strip(),
            "email_body": data.get("email_body", "").strip(),
            "target_role_title": data.get("target_role_title", "Candidate"),
            "target_company": data.get("target_company")
        }

