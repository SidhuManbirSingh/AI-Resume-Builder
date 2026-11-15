from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class JobDescriptionRequest(BaseModel):
    job_description: str = Field(..., description="Full text of the target job description.")
    additional_notes: Optional[str] = Field(None, description="Optional user preferences or specific focus areas.")

class ProjectMetadata(BaseModel):
    id: str
    title: str
    technologies: List[str]
    domain: str
    status: str
    summary: str
    metrics: Optional[str] = None
    full_markdown: Optional[str] = None
    github_url: Optional[str] = None
    github_repo: Optional[str] = None

class RequirementMatrixItem(BaseModel):
    requirement: str
    candidate_evidence: str
    match_level: str  # "Strong", "Partial", "Gap"
    provenance: str   # "possessed_by_candidate", "demonstrated_in_project", "required_by_employer", "not_verified"


class ProjectScoreBreakdown(BaseModel):
    project_id: str
    title: str
    technical_overlap: float
    responsibility_alignment: float
    domain_relevance: float
    keyword_coverage: float
    score: float
    meets_threshold: bool = True


class ATSScoreBreakdown(BaseModel):
    overall_score: float
    technical_overlap: float
    responsibility_alignment: float
    domain_relevance: float
    keyword_coverage: float
    formula: str = "0.40*T + 0.25*R + 0.20*D + 0.15*K"
    matched_keywords: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)


class QACheckItem(BaseModel):
    name: str
    passed: bool
    severity: str = "info"  # "info", "warning", "error"
    details: str


class DocumentQAReport(BaseModel):
    passed: bool
    checks: List[QACheckItem] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    pdf_page_count: int = 1
    summary: str = ""


class PipelineTelemetry(BaseModel):
    input_hash: str
    prompt_version: str
    schema_version: str
    taxonomy_version: str
    provider: str
    stage_timings_ms: Dict[str, float] = Field(default_factory=dict)
    warnings_count: int = 0


class ProjectSlot(BaseModel):
    slot_number: int
    project_id: Optional[str] = None
    title: str
    technologies: List[str] = Field(default_factory=list)
    bullets: List[str] = Field(default_factory=list)
    is_proposed: bool = False
    proposal_rationale: Optional[str] = None
    implementation_plan: Optional[str] = None
    github_url: Optional[str] = None
    relevance_score: Optional[float] = None


class Stage1AnalysisResult(BaseModel):
    target_role_title: str
    target_company: Optional[str] = None
    role_family: str = "general"  # "facilities", "service_dispatch", "software_it", "operations_general", "security", "general"
    key_technical_requirements: List[str]
    key_responsibilities: List[str]
    slot1_project_id: str
    slot1_rationale: str
    slot2_is_proposed: bool
    slot2_project_id: Optional[str] = None
    slot2_rationale: str
    slot2_proposed_title: Optional[str] = None
    slot2_proposed_technologies: Optional[List[str]] = None
    slot2_proposed_plan: Optional[str] = None
    requirement_matrix: List[RequirementMatrixItem] = Field(default_factory=list)
    project_scores: List[ProjectScoreBreakdown] = Field(default_factory=list)

class TunedExperience(BaseModel):
    company: str
    title: str
    date_range: str
    location: str
    bullets: List[str]

class SkillCategory(BaseModel):
    category_name: str
    skills: List[str]

class Stage2CustomizationResult(BaseModel):
    tailored_summary: str
    skill_categories: List[SkillCategory]
    experiences: List[TunedExperience]
    slot1_title: str
    slot1_technologies: List[str] = Field(default_factory=list)
    slot1_bullets: List[str]
    slot1_github_url: Optional[str] = None
    slot2_title: str
    slot2_technologies: List[str] = Field(default_factory=list)
    slot2_bullets: List[str]
    slot2_is_proposed: bool = False
    slot2_github_url: Optional[str] = None

class DiffItem(BaseModel):
    section: str
    original: str
    modified: str
    change_type: str # "modified", "reordered", "selected", "proposed"

class TailoredResumeResponse(BaseModel):
    tailored_markdown: str
    original_markdown: str
    analysis: Dict[str, Any]
    diffs: List[DiffItem] = Field(default_factory=list)
    slots: List[ProjectSlot] = Field(default_factory=list)
    ats_score: Optional[ATSScoreBreakdown] = None
    requirement_matrix: List[RequirementMatrixItem] = Field(default_factory=list)
    qa_report: Optional[DocumentQAReport] = None
    telemetry: Optional[PipelineTelemetry] = None
    fact_registry_summary: Optional[Dict[str, Any]] = None

class ExportRequest(BaseModel):
    markdown_content: str
    filename: Optional[str] = "tailored_resume.pdf"

class CoverLetterRequest(BaseModel):
    job_description: str = Field(..., description="Full text of the target job description.")
    tailored_markdown: Optional[str] = Field(None, description="Optional tailored resume markdown to ground the cover letter on.")
    additional_notes: Optional[str] = Field(None, description="Optional user preferences or specific focus areas.")

class CoverLetterResponse(BaseModel):
    cover_letter_markdown: str
    target_role_title: str
    target_company: Optional[str] = None

class OutreachRequest(BaseModel):
    job_description: str = Field(..., description="Full text of the target job description.")
    tailored_markdown: Optional[str] = Field(None, description="Optional tailored resume markdown.")
    additional_notes: Optional[str] = Field(None, description="Optional user preferences or specific focus areas.")

class OutreachResponse(BaseModel):
    linkedin_message: str
    email_subject: str
    email_body: str
    target_role_title: str
    target_company: Optional[str] = None
