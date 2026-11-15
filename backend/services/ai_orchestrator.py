import hashlib
import logging
import time
from typing import Dict, Any, List
from backend.core.security import sanitize_job_description, sanitize_additional_notes
from backend.services.file_loader import FileLoaderService
from backend.services.llm_client import get_llm_client
from backend.services.validator import ResumeValidator
from backend.services.markdown_assembler import MarkdownAssembler
from backend.services.fact_registry import CandidateFactRegistry
from backend.services.scoring import DeterministicScorer, TAXONOMY_VERSION
from backend.services.pdf_generator import ATSResumePDFGenerator
from backend.services.qa_validator import FinalDocumentQAValidator
from backend.llm.base import _parse_and_structure_raw_jd
from backend.llm.prompts import PROMPT_VERSION, SCHEMA_VERSION
from backend.models.schemas import (
    TailoredResumeResponse,
    CoverLetterResponse,
    OutreachResponse,
    ProjectSlot,
    DiffItem,
    PipelineTelemetry,
)

logger = logging.getLogger(__name__)


class AIResumeOrchestrator:
    @staticmethod
    def tailor_resume(raw_job_description: str, additional_notes: str = None) -> TailoredResumeResponse:
        """
        Executes the full multi-stage tailoring pipeline:
        1. Sanitize & normalize JD and optional user notes.
        2. Build centralized CandidateFactRegistry from master resume & project catalog.
        3. Stage 1: Deterministic scoring + JD Analysis, Requirement Matrix & Project Selection.
        4. Stage 2: Targeted Resume Customization.
        5. Stage 3: Structural & Semantic Claim Verification Guardrails.
        6. Assemble Markdown, compute non-LLM ATS Score (0.40T+0.25R+0.20D+0.15K),
           and run Stage 4 Final Document QA on Markdown + compiled PDF bytes.
        """
        t_start = time.perf_counter()
        stage_timings: Dict[str, float] = {}

        # Step 1: Sanitize Input
        clean_jd = sanitize_job_description(raw_job_description)
        clean_notes = sanitize_additional_notes(additional_notes) if additional_notes else ""
        if clean_notes:
            clean_jd = f"{clean_jd}\n\nAdditional Candidate Focus: {clean_notes}"
        input_hash = hashlib.sha256(f"{clean_jd}\n{clean_notes}".encode("utf-8")).hexdigest()[:16]

        # Step 2: Ingest Master Resume & Catalog and build CandidateFactRegistry
        t0 = time.perf_counter()
        master_raw, master_parsed = FileLoaderService.get_master_resume()
        projects = FileLoaderService.get_project_catalog()
        fact_registry = CandidateFactRegistry.build(master_parsed, projects=projects)
        structured_jd = _parse_and_structure_raw_jd(clean_jd)
        stage_timings["ingest_and_registry_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)

        # Step 3: Initialize LLM Client
        llm = get_llm_client()
        provider = getattr(llm, "provider_name", "unknown")

        # Stage 1: Analyze JD & Select Projects
        t1 = time.perf_counter()
        stage1_result = llm.analyze_and_select(clean_jd, master_parsed, projects)
        stage_timings["stage1_ms"] = round((time.perf_counter() - t1) * 1000.0, 2)

        project_scores = stage1_result.project_scores or DeterministicScorer.rank_projects(
            projects, structured_jd, clean_jd
        )
        requirement_matrix = stage1_result.requirement_matrix or DeterministicScorer.build_requirement_matrix(
            structured_jd, fact_registry, projects
        )
        scores_by_id = {s.project_id: s.score for s in project_scores}

        # Stage 2: Targeted Resume Customization
        t2 = time.perf_counter()
        stage2_result = llm.customize_sections(clean_jd, master_parsed, stage1_result, projects)
        stage_timings["stage2_ms"] = round((time.perf_counter() - t2) * 1000.0, 2)

        # Stage 3: Structural Invariance & Semantic Claim Verification
        t3 = time.perf_counter()
        validated_result, validation_warnings = ResumeValidator.validate_and_sanitize(
            master_parsed,
            stage2_result,
            job_description=clean_jd,
            projects=projects,
            fact_registry=fact_registry,
            slot1_project_id=stage1_result.slot1_project_id,
        )
        skill_audit, _ = ResumeValidator.audit_skill_provenance(
            validated_result.skill_categories,
            fact_registry,
            jd_requirements=stage1_result.key_technical_requirements,
        )
        stage_timings["stage3_validation_ms"] = round((time.perf_counter() - t3) * 1000.0, 2)

        # Resolve GitHub URLs from project catalog
        projects_by_id = {p.id: p for p in projects}
        p1 = projects_by_id.get(stage1_result.slot1_project_id)
        slot1_github_url = p1.github_url if p1 else None

        p2 = projects_by_id.get(stage1_result.slot2_project_id) if not stage1_result.slot2_is_proposed else None
        slot2_github_url = p2.github_url if p2 else None

        validated_result.slot1_github_url = slot1_github_url
        validated_result.slot2_github_url = slot2_github_url

        # Stage 4: Assemble Markdown, Compute Non-LLM ATS Score, Compile PDF & Run Final QA
        tailored_markdown = MarkdownAssembler.assemble(master_parsed, validated_result)
        diff_items = MarkdownAssembler.generate_diffs(master_parsed, validated_result, projects)

        t4 = time.perf_counter()
        ats_score = DeterministicScorer.compute_resume_ats_score(
            tailored_markdown, validated_result, structured_jd, clean_jd
        )
        compiled_pdf_bytes = ATSResumePDFGenerator.markdown_to_pdf_bytes(tailored_markdown)
        qa_report = FinalDocumentQAValidator.validate(
            tailored_markdown, compiled_pdf_bytes, master_parsed, validated_result
        )
        stage_timings["stage4_scoring_qa_ms"] = round((time.perf_counter() - t4) * 1000.0, 2)
        stage_timings["total_ms"] = round((time.perf_counter() - t_start) * 1000.0, 2)

        telemetry = PipelineTelemetry(
            input_hash=input_hash,
            prompt_version=PROMPT_VERSION,
            schema_version=SCHEMA_VERSION,
            taxonomy_version=TAXONOMY_VERSION,
            provider=provider,
            stage_timings_ms=stage_timings,
            warnings_count=len(validation_warnings) + len(qa_report.warnings),
        )
        logger.info(
            "Pipeline completed: hash=%s provider=%s ats_score=%.1f qa_passed=%s total_ms=%.1f",
            input_hash, provider, ats_score.overall_score, qa_report.passed, stage_timings["total_ms"]
        )

        # Build Project Slot metadata for UI display
        slot1_meta = ProjectSlot(
            slot_number=1,
            project_id=stage1_result.slot1_project_id,
            title=validated_result.slot1_title,
            technologies=validated_result.slot1_technologies,
            bullets=validated_result.slot1_bullets,
            is_proposed=False,
            proposal_rationale=stage1_result.slot1_rationale,
            github_url=slot1_github_url,
            relevance_score=scores_by_id.get(stage1_result.slot1_project_id),
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
            github_url=slot2_github_url,
            relevance_score=scores_by_id.get(stage1_result.slot2_project_id) if stage1_result.slot2_project_id else None,
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
            "slot2_proposed_plan": stage1_result.slot2_proposed_plan,
            "ats_score": ats_score.model_dump(),
            "requirement_matrix": [m.model_dump() for m in requirement_matrix],
            "project_scores": [s.model_dump() for s in project_scores],
            "qa_report": qa_report.model_dump(),
            "skill_provenance_audit": skill_audit,
        }

        return TailoredResumeResponse(
            tailored_markdown=tailored_markdown,
            original_markdown=master_raw,
            analysis=analysis_summary,
            diffs=diff_items,
            slots=[slot1_meta, slot2_meta],
            ats_score=ats_score,
            requirement_matrix=requirement_matrix,
            qa_report=qa_report,
            telemetry=telemetry,
            fact_registry_summary=fact_registry.to_summary_dict(),
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
