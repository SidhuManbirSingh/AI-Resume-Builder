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

class Stage1AnalysisResult(BaseModel):
    target_role_title: str
    target_company: Optional[str] = None
    role_family: str = "general"  # "facilities", "service_dispatch", "software_it", "security", "general"
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
