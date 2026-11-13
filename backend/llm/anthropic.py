import json
import requests
from typing import List, Dict, Any, Optional
from backend.models.schemas import (
    ProjectMetadata,
    Stage1AnalysisResult,
    Stage2CustomizationResult
)
from backend.llm.base import BaseLLMClient, _extract_json
from backend.llm.prompts import (
    _build_stage1_prompts,
    _build_stage2_prompts,
    _build_cover_letter_prompts,
    _build_outreach_prompts
)


class AnthropicLLMClient(BaseLLMClient):
    """
    Production client connecting to Anthropic Claude.
    Uses structured system instructions and JSON extraction.
    """
    provider_name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.anthropic.com/v1/messages"

    def _call_claude(self, system_prompt: str, user_prompt: str) -> str:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": self.model,
            "max_tokens": 4000,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2
        }
        response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
        if response.status_code != 200:
            raise RuntimeError(f"Anthropic API Error ({response.status_code}): {response.text}")
        data = response.json()
        return data["content"][0]["text"]

    def analyze_and_select(
        self,
        job_description: str,
        master_parsed: Dict[str, Any],
        projects: List[ProjectMetadata]
    ) -> Stage1AnalysisResult:
        system_prompt, user_prompt = _build_stage1_prompts(job_description, master_parsed, projects)
        raw_response = self._call_claude(system_prompt, user_prompt)
        json_clean = _extract_json(raw_response)
        return Stage1AnalysisResult.model_validate(json.loads(json_clean))

    def customize_sections(
        self,
        job_description: str,
        master_parsed: Dict[str, Any],
        stage1_result: Stage1AnalysisResult,
        projects: List[ProjectMetadata]
    ) -> Stage2CustomizationResult:
        system_prompt, user_prompt = _build_stage2_prompts(job_description, master_parsed, stage1_result, projects)
        raw_response = self._call_claude(system_prompt, user_prompt)
        json_clean = _extract_json(raw_response)
        return Stage2CustomizationResult.model_validate(json.loads(json_clean))

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
        raw_response = self._call_claude(system_prompt, user_prompt)
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
        raw_response = self._call_claude(system_prompt, user_prompt)
        json_clean = _extract_json(raw_response)
        data = json.loads(json_clean)
        return {
            "linkedin_message": data.get("linkedin_message", "").strip(),
            "email_subject": data.get("email_subject", "").strip(),
            "email_body": data.get("email_body", "").strip(),
            "target_role_title": data.get("target_role_title", "Candidate"),
            "target_company": data.get("target_company")
        }

