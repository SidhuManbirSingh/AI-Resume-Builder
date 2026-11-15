import re
from typing import Dict, List, Any, Optional, Set
from pydantic import BaseModel, Field
from backend.models.schemas import ProjectMetadata


class FactItem(BaseModel):
    fact: str
    source: str
    verified: bool = True
    modifiable: bool = False
    category: str = ""


class CandidateFactRegistry:
    """
    Centralized Source-of-Truth Registry extracted deterministically from the
    master resume and verified project catalog. Tracks factual provenance across:
    personal_information, employment_history, education, certifications,
    verified_skills, verified_achievements, and project_catalog.
    """

    METRIC_PATTERN = re.compile(
        r'(?<!\w)(?:~?\d[\d,]*(?:\.\d+)?%|\b\d+(?:\.\d+)?x\b|\$\d[\d,]*(?:\.\d+)?[kKmMbB]?)'
    )

    def __init__(self):
        self.personal_information: List[FactItem] = []
        self.employment_history: List[FactItem] = []
        self.education: List[FactItem] = []
        self.certifications: List[FactItem] = []
        self.verified_skills: List[FactItem] = []
        self.verified_achievements: List[FactItem] = []
        self.project_catalog: List[FactItem] = []

        self._verified_skill_phrases: Set[str] = set()
        self._project_skill_phrases: Set[str] = set()
        self._master_text_lower: str = ""
        self._projects_text_lower: str = ""
        self._master_metric_tokens: Set[str] = set()
        self._project_metric_tokens: Set[str] = set()
        self._project_metrics_by_id: Dict[str, Set[str]] = {}
        self._cert_text_lower: str = ""

    @staticmethod
    def _normalize_token(token: str) -> str:
        return re.sub(r'[~,\s]+', '', token.strip().lower())

    @classmethod
    def extract_metric_tokens(cls, text: str) -> List[str]:
        if not text:
            return []
        return [m.group(0).strip() for m in cls.METRIC_PATTERN.finditer(text)]

    @classmethod
    def build(
        cls,
        master_parsed: Dict[str, Any],
        projects: Optional[List[ProjectMetadata]] = None,
        source_name: str = "master_resume.md",
    ) -> "CandidateFactRegistry":
        reg = cls()
        projects = projects or []
        raw_master = master_parsed.get("raw", "") or ""
        reg._master_text_lower = " ".join([
            raw_master,
            master_parsed.get("summary", ""),
            master_parsed.get("skills_raw", ""),
            master_parsed.get("experiences_raw", ""),
            master_parsed.get("projects_raw", ""),
            master_parsed.get("education", ""),
            master_parsed.get("certifications", ""),
        ]).lower()

        # 1. Personal Information
        contact_info = master_parsed.get("contact_info", {}) or {}
        for field in ("name", "location", "phone", "email", "linkedin", "github"):
            val = (contact_info.get(field) or "").strip()
            if val:
                reg.personal_information.append(
                    FactItem(
                        fact=f"{field}: {val}",
                        source=source_name,
                        verified=True,
                        modifiable=False,
                        category=field,
                    )
                )

        # 2. Employment History
        for exp in master_parsed.get("experiences", []):
            comp = exp.get("company", "").strip()
            title = exp.get("title", "").strip()
            dr = exp.get("date_range", "").strip()
            loc = exp.get("location", "").strip()
            if comp or title:
                reg.employment_history.append(
                    FactItem(
                        fact=f"{title} | {comp} | {dr} | {loc}",
                        source=source_name,
                        verified=True,
                        modifiable=False,
                        category="employer_record",
                    )
                )
            for b in exp.get("bullets", []):
                b_clean = b.strip()
                if b_clean:
                    reg.employment_history.append(
                        FactItem(
                            fact=b_clean,
                            source=source_name,
                            verified=True,
                            modifiable=True,
                            category=f"bullet:{comp}",
                        )
                    )
                    for tok in cls.extract_metric_tokens(b_clean):
                        norm = cls._normalize_token(tok)
                        reg._master_metric_tokens.add(norm)
                        reg.verified_achievements.append(
                            FactItem(
                                fact=tok,
                                source=source_name,
                                verified=True,
                                modifiable=False,
                                category="experience_metric",
                            )
                        )

        # 3. Education
        edu_raw = (master_parsed.get("education") or "").strip()
        for line in edu_raw.splitlines():
            clean_line = re.sub(r'^[-*#_\s]+', '', line).strip()
            if clean_line:
                reg.education.append(
                    FactItem(
                        fact=clean_line,
                        source=source_name,
                        verified=True,
                        modifiable=False,
                        category="education",
                    )
                )

        # 4. Certifications
        certs_raw = (master_parsed.get("certifications") or "").strip()
        reg._cert_text_lower = "\n".join([
            certs_raw,
            edu_raw,
            master_parsed.get("summary", ""),
            master_parsed.get("experiences_raw", ""),
        ]).lower()
        for line in certs_raw.splitlines():
            clean_line = re.sub(r'^[-*#_\s]+', '', line).strip()
            if clean_line:
                reg.certifications.append(
                    FactItem(
                        fact=clean_line,
                        source=source_name,
                        verified=True,
                        modifiable=False,
                        category="certification",
                    )
                )

        # 5. Verified Skills (from master skill categories)
        for cat in master_parsed.get("skills", []):
            cat_name = cat.get("category", "Skills")
            for sk in cat.get("skills", []):
                sk_clean = sk.strip()
                if not sk_clean:
                    continue
                reg.verified_skills.append(
                    FactItem(
                        fact=sk_clean,
                        source=source_name,
                        verified=True,
                        modifiable=True,
                        category=cat_name,
                    )
                )
                reg._verified_skill_phrases.add(sk_clean.lower())
                # Split parenthesized sub-skills e.g. Python (Pandas, NumPy)
                base_part = re.sub(r'\([^)]*\)', '', sk_clean).strip()
                if base_part:
                    reg._verified_skill_phrases.add(base_part.lower())
                for inner in re.findall(r'\(([^)]+)\)', sk_clean):
                    for sub in re.split(r'[,/]+', inner):
                        if sub.strip():
                            reg._verified_skill_phrases.add(sub.strip().lower())
                for slash_part in sk_clean.split('/'):
                    sp = slash_part.strip().lower()
                    if len(sp) >= 2:
                        reg._verified_skill_phrases.add(sp)

        # Master achievements in summary / projects_raw / education / raw
        seen_metrics: Set[str] = set(reg._master_metric_tokens)
        for source_section, txt in (
            ("summary", master_parsed.get("summary", "")),
            ("projects_raw", master_parsed.get("projects_raw", "")),
            ("education", edu_raw),
        ):
            for tok in cls.extract_metric_tokens(txt):
                norm = cls._normalize_token(tok)
                reg._master_metric_tokens.add(norm)
                if norm not in seen_metrics:
                    seen_metrics.add(norm)
                    reg.verified_achievements.append(
                        FactItem(
                            fact=tok,
                            source=source_name,
                            verified=True,
                            modifiable=False,
                            category=source_section,
                        )
                    )

        # 6. Project Catalog & Project Skills / Metrics
        project_texts = []
        for p in projects:
            p_src = f"projects/{p.id}.md"
            reg.project_catalog.append(
                FactItem(
                    fact=f"{p.title} ({p.domain})",
                    source=p_src,
                    verified=True,
                    modifiable=False,
                    category="project",
                )
            )
            p_combined = " ".join([
                p.title or "",
                p.domain or "",
                p.summary or "",
                p.metrics or "",
                p.full_markdown or "",
            ])
            project_texts.append(p_combined)

            for tech in p.technologies:
                t_clean = tech.strip().lower()
                if t_clean:
                    reg._project_skill_phrases.add(t_clean)

            p_metrics = set()
            for tok in cls.extract_metric_tokens(p_combined):
                norm = cls._normalize_token(tok)
                p_metrics.add(norm)
                reg._project_metric_tokens.add(norm)
                if norm not in seen_metrics:
                    seen_metrics.add(norm)
                    reg.verified_achievements.append(
                        FactItem(
                            fact=tok,
                            source=p_src,
                            verified=True,
                            modifiable=False,
                            category="project_metric",
                        )
                    )
            reg._project_metrics_by_id[p.id] = p_metrics

        reg._projects_text_lower = "\n".join(project_texts).lower()
        return reg

    @staticmethod
    def _term_in_text(term_lower: str, corpus_lower: str) -> bool:
        if not term_lower or not corpus_lower:
            return False
        if len(term_lower) <= 3 and term_lower.isalnum():
            return bool(re.search(rf'(?<![a-z0-9]){re.escape(term_lower)}(?![a-z0-9])', corpus_lower))
        return term_lower in corpus_lower

    def classify_skill_provenance(
        self,
        skill: str,
        jd_requirements: Optional[List[str]] = None,
    ) -> str:
        """
        Distinguishes between:
        - possessed_by_candidate (verified in master resume skills/experience/education)
        - demonstrated_in_project (verified in project catalog)
        - required_by_employer (present in JD requirements only)
        - not_verified
        """
        sk = (skill or "").strip().lower()
        if not sk:
            return "not_verified"

        if sk in self._verified_skill_phrases or self._term_in_text(sk, self._master_text_lower):
            return "possessed_by_candidate"

        if sk in self._project_skill_phrases or self._term_in_text(sk, self._projects_text_lower):
            return "demonstrated_in_project"

        if jd_requirements:
            jd_lower_set = {r.strip().lower() for r in jd_requirements if r.strip()}
            if sk in jd_lower_set or any(sk in r or r in sk for r in jd_lower_set):
                return "required_by_employer"

        return "not_verified"

    def is_metric_supported(
        self,
        metric_token: str,
        project_id: Optional[str] = None,
        master_only: bool = False,
    ) -> bool:
        norm = self._normalize_token(metric_token)
        if not norm:
            return True
        if norm in self._master_metric_tokens:
            return True
        if master_only:
            return False
        if project_id and project_id in self._project_metrics_by_id:
            return norm in self._project_metrics_by_id[project_id]
        return norm in self._project_metric_tokens

    def find_unsupported_metrics(
        self,
        text: str,
        project_id: Optional[str] = None,
        master_only: bool = False,
    ) -> List[str]:
        unsupported = []
        for tok in self.extract_metric_tokens(text):
            if not self.is_metric_supported(tok, project_id=project_id, master_only=master_only):
                unsupported.append(tok)
        return unsupported

    def is_certification_verified(self, cert_name: str) -> bool:
        c = (cert_name or "").strip().lower()
        if not c:
            return False
        return c in self._cert_text_lower

    def to_summary_dict(self) -> Dict[str, Any]:
        return {
            "counts": {
                "personal_information": len(self.personal_information),
                "employment_history": len(self.employment_history),
                "education": len(self.education),
                "certifications": len(self.certifications),
                "verified_skills": len(self.verified_skills),
                "verified_achievements": len(self.verified_achievements),
                "project_catalog": len(self.project_catalog),
            },
            "verified_skills_list": [f.fact for f in self.verified_skills],
            "verified_metrics_list": [f.fact for f in self.verified_achievements],
        }
