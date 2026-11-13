from typing import Dict, Any, List
from backend.core.security import sanitize_job_description, sanitize_additional_notes
from backend.services.file_loader import FileLoaderService
from backend.services.llm_client import get_llm_client
from backend.services.validator import ResumeValidator
from backend.services.markdown_assembler import MarkdownAssembler
from backend.models.schemas import (
    TailoredResumeResponse,
    CoverLetterResponse,
    OutreachResponse,
    ProjectSlot,
    DiffItem
)

class AIResumeOrchestrator:
    @staticmethod
    def tailor_resume(raw_job_description: str, additional_notes: str = None) -> TailoredResumeResponse:
        """
        Executes the full 3-stage tailoring pipeline:
        1. Sanitize & normalize JD.
        2. Load read-only master resume & project catalog.
        3. Stage 1: JD Analysis & Project Matcher.
        4. Stage 2: Targeted Resume Customization.
        5. Stage 3: Invariance Guardrail Verification & GitHub Stripping.
        6. Assemble Markdown & generate diffs for UI review.
        """
        # Step 1: Sanitize Input
        clean_jd = sanitize_job_description(raw_job_description)
        clean_notes = sanitize_additional_notes(additional_notes) if additional_notes else ""
        if clean_notes:
            clean_jd = f"{clean_jd}\n\nAdditional Candidate Focus: {clean_notes}"

        # Step 2: Ingest Master Resume & Catalog
        master_raw, master_parsed = FileLoaderService.get_master_resume()
        projects = FileLoaderService.get_project_catalog()

        # Step 3: Initialize LLM Client
        llm = get_llm_client()

        # Stage 1: Analyze JD & Select Projects
        stage1_result = llm.analyze_and_select(clean_jd, master_parsed, projects)

        # Stage 2: Targeted Resume Customization
        stage2_result = llm.customize_sections(clean_jd, master_parsed, stage1_result, projects)

        # Stage 3: Deterministic Invariance Guardrail Validation
        validated_result, validation_warnings = ResumeValidator.validate_and_sanitize(
            master_parsed,
            stage2_result,
            job_description=clean_jd
        )

        # Resolve GitHub URLs from project catalog
        projects_by_id = {p.id: p for p in projects}
        p1 = projects_by_id.get(stage1_result.slot1_project_id)
        slot1_github_url = p1.github_url if p1 else None

        p2 = projects_by_id.get(stage1_result.slot2_project_id) if not stage1_result.slot2_is_proposed else None
        slot2_github_url = p2.github_url if p2 else None

        validated_result.slot1_github_url = slot1_github_url
        validated_result.slot2_github_url = slot2_github_url

        # Stage 4: Assemble Markdown
        tailored_markdown = MarkdownAssembler.assemble(master_parsed, validated_result)
        diff_items = MarkdownAssembler.generate_diffs(master_parsed, validated_result, projects)

        # Build Project Slot metadata for UI display
        slot1_meta = ProjectSlot(
            slot_number=1,
            project_id=stage1_result.slot1_project_id,
            title=validated_result.slot1_title,
            technologies=validated_result.slot1_technologies,
            bullets=validated_result.slot1_bullets,
            is_proposed=False,
            proposal_rationale=stage1_result.slot1_rationale,
            github_url=slot1_github_url
        )

        slot2_meta = ProjectSlot(
            slot_number=2,
            project_id=stage1_result.slot2_project_id,
            title=validated_result.slot2_title,
            technologies=validated_result.slot2_technologies,
            bullets=validated_result.slot2_bullets,
            is_proposed=validated_result.slot2_is_proposed,
            proposal_rationale=stage1_result.slot2_rationale,
            implementation_plan=stage1_result.slot2_proposed_plan,
            github_url=slot2_github_url
        )

        analysis_summary = {
            "target_role_title": stage1_result.target_role_title,
            "target_company": stage1_result.target_company,
            "role_family": stage1_result.role_family,
            "candidate_name": master_parsed.get("name", "Manbir Singh Sidhu"),
            "contact_info": master_parsed.get("contact_info", {}),
            "key_technical_requirements": stage1_result.key_technical_requirements,
            "key_responsibilities": stage1_result.key_responsibilities,
            "validation_warnings": validation_warnings,
            "slot1_project_id": stage1_result.slot1_project_id,
            "slot1_rationale": stage1_result.slot1_rationale,
            "slot2_project_id": stage1_result.slot2_project_id,
            "slot2_rationale": stage1_result.slot2_rationale,
            "slot2_is_proposed": stage1_result.slot2_is_proposed,
            "slot2_proposed_plan": stage1_result.slot2_proposed_plan
        }

        return TailoredResumeResponse(
            tailored_markdown=tailored_markdown,
            original_markdown=master_raw,
            analysis=analysis_summary,
            diffs=diff_items,
            slots=[slot1_meta, slot2_meta]
        )

    @staticmethod
    def tailor_cover_letter(
        raw_job_description: str,
        tailored_markdown: str = None,
        additional_notes: str = None
    ) -> CoverLetterResponse:
        """
        Generates a tailored, catchy, high-energy cover letter grounded in candidate facts and the target JD.
        """
        clean_jd = sanitize_job_description(raw_job_description)
        clean_notes = sanitize_additional_notes(additional_notes) if additional_notes else None

        if not tailored_markdown or not tailored_markdown.strip():
            master_raw, _ = FileLoaderService.get_master_resume()
            resume_ref = master_raw
        else:
            resume_ref = tailored_markdown.strip()

        llm = get_llm_client()
        result = llm.generate_cover_letter(
            job_description=clean_jd,
            resume_markdown=resume_ref,
            additional_notes=clean_notes
        )

        return CoverLetterResponse(
            cover_letter_markdown=result["cover_letter_markdown"],
            target_role_title=result.get("target_role_title", "Candidate"),
            target_company=result.get("target_company")
        )

    @staticmethod
    def tailor_outreach(
        raw_job_description: str,
        tailored_markdown: str = None,
        additional_notes: str = None
    ) -> OutreachResponse:
        """
        Generates two custom outreach versions (LinkedIn message and direct cold email) grounded in candidate facts and the target JD.
        """
        clean_jd = sanitize_job_description(raw_job_description)
        clean_notes = sanitize_additional_notes(additional_notes) if additional_notes else None

        if not tailored_markdown or not tailored_markdown.strip():
            master_raw, _ = FileLoaderService.get_master_resume()
            resume_ref = master_raw
        else:
            resume_ref = tailored_markdown.strip()

        llm = get_llm_client()
        result = llm.generate_outreach(
            job_description=clean_jd,
            resume_markdown=resume_ref,
            additional_notes=clean_notes
        )

        return OutreachResponse(
            linkedin_message=result.get("linkedin_message", "").strip(),
            email_subject=result.get("email_subject", "").strip(),
            email_body=result.get("email_body", "").strip(),
            target_role_title=result.get("target_role_title", "Candidate"),
            target_company=result.get("target_company")
        )
