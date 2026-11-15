import re
from typing import Dict, List, Any, Set, Tuple
from backend.models.schemas import (
    ProjectMetadata,
    ProjectScoreBreakdown,
    RequirementMatrixItem,
    ATSScoreBreakdown,
    Stage2CustomizationResult,
)
from backend.services.fact_registry import CandidateFactRegistry


TAXONOMY_VERSION = "1.0.0"
MIN_PROJECT_RELEVANCE_THRESHOLD = 25.0

_STOPWORDS: Set[str] = {
    "with", "from", "that", "this", "have", "will", "your", "their", "about",
    "across", "using", "into", "through", "including", "within", "such", "ensure",
    "strong", "experience", "ability", "working", "knowledge", "preferred", "required",
    "role", "team", "work", "skills", "systems", "platform", "platforms", "tools",
    "processes", "and", "the", "for", "are", "you", "all", "over", "years", "year",
}

TECH_TAXONOMY: Dict[str, Set[str]] = {
    "kubernetes": {"kubernetes", "k8s", "minikube"},
    "docker": {"docker", "docker compose", "containerized", "containers"},
    "postgresql": {"postgresql", "postgres"},
    "sql": {"sql", "postgresql", "oracle", "dbeaver", "mysql", "database"},
    "python": {"python", "pandas", "numpy", "flask", "fastapi"},
    "react": {"react", "react.js", "reactjs"},
    "node.js": {"node.js", "nodejs", "typescript", "javascript"},
    "power bi": {"power bi", "bi reporting", "dashboards", "dashboard"},
    "etl": {"etl", "pentaho", "data pipeline", "data pipelines", "data ingestion", "data warehousing"},
    "ai / llm": {"ai", "llm", "claude", "chatgpt", "copilot", "openai", "anthropic", "yolov8", "pytorch", "opencv", "openvino"},
    "ci/cd": {"ci/cd", "gitlab", "github actions", "pipeline", "automation"},
    "monitoring": {"prometheus", "grafana", "efk", "elasticsearch", "kibana", "observability"},
    "azure": {"azure", "azure rbac", "microsoft 365", "active directory", "sharepoint"},
    "aws": {"aws", "cloud"},
    "linux": {"linux", "bash", "shell", "windows server"},
    "bms/bas": {"bms", "bas", "bms/bas", "building automation", "building management"},
    "cmms": {"cmms", "mri angus", "angus", "wpm plus", "vonigo", "work order", "work orders"},
    "hvac": {"hvac", "chillers", "chiller", "boilers", "boiler", "cooling towers", "ahus", "ahu", "pumps"},
    "dispatch": {"dispatch", "dispatching", "scheduling", "emergency", "same-day", "inbound", "vendor", "contractor"},
    "safety": {"oh&s", "life-safety", "life safety", "ofa", "first aid", "governance", "compliance", "security"},
}


class DeterministicScorer:
    """
    Non-LLM deterministic scoring & requirement mapping engine.
    Applies the weighted formula:
        Score = 0.40 * T + 0.25 * R + 0.20 * D + 0.15 * K
    normalized strictly to [0.0, 100.0].
    """

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        if not text:
            return set()
        tokens = set(re.findall(r'[a-z][a-z0-9\+\#/\-]{2,}', text.lower()))
        return {t for t in tokens if t not in _STOPWORDS and len(t) >= 3}

    @staticmethod
    def _term_in_text(term: str, text_lower: str) -> bool:
        t = term.strip().lower()
        if not t or not text_lower:
            return False
        if len(t) <= 3 and t.isalnum():
            return bool(re.search(rf'(?<![a-z0-9]){re.escape(t)}(?![a-z0-9])', text_lower))
        return t in text_lower

    @classmethod
    def _extract_canonical_concepts(cls, text_lower: str) -> Set[str]:
        matched: Set[str] = set()
        for canonical, aliases in TECH_TAXONOMY.items():
            if any(cls._term_in_text(alias, text_lower) for alias in aliases):
                matched.add(canonical)
        return matched

    @classmethod
    def _project_corpus(cls, project: ProjectMetadata) -> str:
        return " ".join([
            project.title or "",
            project.domain or "",
            " ".join(project.technologies or []),
            project.summary or "",
            project.metrics or "",
            project.full_markdown or "",
        ]).lower()

    @classmethod
    def _domain_relevance_score(cls, role_family: str, project: ProjectMetadata, jd_lower: str) -> float:
        p_domain = (project.domain or "").lower()
        is_fac_proj = "facilities" in p_domain or "building" in p_domain
        is_tech_proj = any(
            k in p_domain
            for k in ("cloud", "devops", "infrastructure", "security", "vision", "machine learning", "analytics", "data", "software", "web")
        )

        score = 40.0
        if role_family in ("facilities", "service_dispatch"):
            if is_fac_proj:
                score = 100.0
            elif "analytics" in p_domain or "data" in p_domain:
                score = 45.0
            else:
                score = 15.0
        elif role_family == "software_it":
            if is_fac_proj:
                score = 10.0
            elif is_tech_proj:
                score = 95.0
            else:
                score = 60.0
        elif role_family == "operations_general":
            if is_fac_proj or "analytics" in p_domain or "data" in p_domain:
                score = 85.0
            else:
                score = 55.0
        elif role_family == "security":
            if "security" in p_domain or is_fac_proj:
                score = 95.0
            else:
                score = 45.0

        # Boost slightly if explicit domain words appear in JD text
        domain_words = cls._tokenize(project.domain)
        if domain_words and any(cls._term_in_text(dw, jd_lower) for dw in domain_words):
            score = min(100.0, score + 10.0)
        return round(score, 1)

    @classmethod
    def score_project(
        cls,
        project: ProjectMetadata,
        structured_jd: Dict[str, Any],
        jd_text: str,
    ) -> ProjectScoreBreakdown:
        jd_lower = (structured_jd.get("cleaned_jd_text") or jd_text or "").lower()
        p_lower = cls._project_corpus(project)
        role_family = structured_jd.get("role_family", "general")

        # T: Technical skill overlap (0-100)
        jd_reqs = [r.strip().lower() for r in structured_jd.get("key_technical_requirements", []) if r.strip()]
        jd_concepts = cls._extract_canonical_concepts(jd_lower)
        p_concepts = cls._extract_canonical_concepts(p_lower)
        p_techs = [t.strip().lower() for t in (project.technologies or []) if t.strip()]

        req_hits = 0
        for req in jd_reqs:
            req_tokens = cls._tokenize(req)
            if cls._term_in_text(req, p_lower) or (req_tokens and len(req_tokens & cls._tokenize(p_lower)) >= 1):
                req_hits += 1
        req_ratio = (req_hits / len(jd_reqs)) if jd_reqs else 0.5

        concept_ratio = (len(jd_concepts & p_concepts) / len(jd_concepts)) if jd_concepts else 0.5
        p_tech_hits = sum(1 for t in p_techs if cls._term_in_text(t, jd_lower) or bool(cls._extract_canonical_concepts(t) & jd_concepts))
        p_tech_ratio = (p_tech_hits / len(p_techs)) if p_techs else 0.0

        T = min(100.0, round((0.40 * req_ratio + 0.35 * concept_ratio + 0.25 * p_tech_ratio) * 100.0, 1))

        # R: Responsibility alignment (0-100)
        resp_tokens: Set[str] = set()
        for r in structured_jd.get("key_responsibilities", []):
            resp_tokens.update(cls._tokenize(r))
        p_tokens = cls._tokenize(p_lower)
        if resp_tokens:
            r_overlap = len(resp_tokens & p_tokens) / len(resp_tokens)
            R = min(100.0, round(r_overlap * 220.0, 1))
        else:
            R = 50.0

        # D: Domain relevance (0-100)
        D = cls._domain_relevance_score(role_family, project, jd_lower)

        # K: Keyword coverage (0-100)
        jd_tokens = cls._tokenize(jd_lower)
        if jd_tokens:
            k_overlap = len(jd_tokens & p_tokens) / min(len(jd_tokens), 45)
            K = min(100.0, round(k_overlap * 140.0, 1))
        else:
            K = 50.0

        total = round(min(100.0, max(0.0, 0.40 * T + 0.25 * R + 0.20 * D + 0.15 * K)), 1)
        return ProjectScoreBreakdown(
            project_id=project.id,
            title=project.title,
            technical_overlap=T,
            responsibility_alignment=R,
            domain_relevance=D,
            keyword_coverage=K,
            score=total,
            meets_threshold=total >= MIN_PROJECT_RELEVANCE_THRESHOLD,
        )

    @classmethod
    def rank_projects(
        cls,
        projects: List[ProjectMetadata],
        structured_jd: Dict[str, Any],
        jd_text: str,
    ) -> List[ProjectScoreBreakdown]:
        breakdowns = [cls.score_project(p, structured_jd, jd_text) for p in projects]
        breakdowns.sort(key=lambda b: b.score, reverse=True)
        return breakdowns

    @classmethod
    def build_requirement_matrix(
        cls,
        structured_jd: Dict[str, Any],
        fact_registry: CandidateFactRegistry,
        projects: List[ProjectMetadata],
    ) -> List[RequirementMatrixItem]:
        matrix: List[RequirementMatrixItem] = []
        raw_items = list(structured_jd.get("key_technical_requirements", [])) + list(
            structured_jd.get("key_responsibilities", [])
        )
        seen: Set[str] = set()
        jd_reqs_list = list(structured_jd.get("key_technical_requirements", []))

        for req in raw_items:
            req_clean = req.strip()
            if not req_clean or req_clean.lower() in seen:
                continue
            seen.add(req_clean.lower())

            provenance = fact_registry.classify_skill_provenance(req_clean, jd_requirements=jd_reqs_list)
            req_tokens = cls._tokenize(req_clean)
            evidence_hits: List[str] = []

            # Search master verified skills
            matched_skills = [
                f.fact for f in fact_registry.verified_skills
                if req_clean.lower() in f.fact.lower()
                or f.fact.lower() in req_clean.lower()
                or (req_tokens and len(req_tokens & cls._tokenize(f.fact)) >= 1)
            ]
            if matched_skills:
                evidence_hits.append(f"Skills: {', '.join(matched_skills[:3])}")

            # Search employment history
            matched_jobs = [
                f.fact for f in fact_registry.employment_history
                if req_tokens and len(req_tokens & cls._tokenize(f.fact)) >= 2
            ]
            if matched_jobs:
                snippet = matched_jobs[0][:90] + ("..." if len(matched_jobs[0]) > 90 else "")
                evidence_hits.append(f"Work History: {snippet}")

            # Search project catalog
            matched_projs = [
                p.title for p in projects
                if req_tokens and len(req_tokens & cls._tokenize(cls._project_corpus(p))) >= 1
            ]
            if matched_projs:
                evidence_hits.append(f"Projects: {', '.join(matched_projs[:2])}")

            if provenance == "possessed_by_candidate" or (matched_skills and len(req_tokens & cls._tokenize(" ".join(matched_skills))) >= 1):
                provenance = "possessed_by_candidate"
                match_level = "Strong"
            elif matched_jobs or (len(matched_projs) > 0 and provenance != "not_verified"):
                if not provenance or provenance == "not_verified":
                    provenance = "demonstrated_in_project" if matched_projs and not matched_jobs else "possessed_by_candidate"
                match_level = "Strong" if (matched_jobs and matched_skills) else "Partial"
            elif matched_projs:
                provenance = "demonstrated_in_project"
                match_level = "Partial"
            else:
                provenance = "required_by_employer"
                match_level = "Gap"

            evidence_str = " | ".join(evidence_hits) if evidence_hits else "No direct master/project evidence (transferable only)"
            matrix.append(
                RequirementMatrixItem(
                    requirement=req_clean,
                    candidate_evidence=evidence_str,
                    match_level=match_level,
                    provenance=provenance,
                )
            )
            if len(matrix) >= 10:
                break

        return matrix

    @classmethod
    def compute_resume_ats_score(
        cls,
        tailored_markdown: str,
        customized: Stage2CustomizationResult,
        structured_jd: Dict[str, Any],
        jd_text: str,
    ) -> ATSScoreBreakdown:
        """
        Deterministically computes the final non-LLM ATS Match Score (0-100) using:
            Score = 0.40 * T + 0.25 * R + 0.20 * D + 0.15 * K
        """
        md_lower = (tailored_markdown or "").lower()
        jd_lower = (structured_jd.get("cleaned_jd_text") or jd_text or "").lower()
        role_title = (structured_jd.get("clean_role_title") or "").strip().lower()
        role_family = structured_jd.get("role_family", "general")

        resume_tokens = cls._tokenize(md_lower)
        resume_concepts = cls._extract_canonical_concepts(md_lower)
        jd_concepts = cls._extract_canonical_concepts(jd_lower)

        # T: Technical requirement alignment (0-100)
        jd_reqs = [r.strip() for r in structured_jd.get("key_technical_requirements", []) if r.strip()]
        skills_text = " ".join(
            [s.lower() for c in customized.skill_categories for s in c.skills]
            + [t.lower() for t in customized.slot1_technologies]
            + [t.lower() for t in customized.slot2_technologies]
        )
        matched_reqs: List[str] = []
        missing_reqs: List[str] = []
        for req in jd_reqs:
            r_low = req.lower()
            r_tokens = cls._tokenize(r_low)
            r_concepts = cls._extract_canonical_concepts(r_low)
            if (
                cls._term_in_text(r_low, md_lower)
                or cls._term_in_text(r_low, skills_text)
                or (r_concepts and bool(r_concepts & resume_concepts))
                or (r_tokens and len(r_tokens & resume_tokens) >= max(1, len(r_tokens) // 2))
            ):
                matched_reqs.append(req)
            else:
                missing_reqs.append(req)

        req_hit_ratio = (len(matched_reqs) / len(jd_reqs)) if jd_reqs else 0.75
        concept_hit_ratio = (len(jd_concepts & resume_concepts) / len(jd_concepts)) if jd_concepts else 0.75
        T = min(100.0, round((0.60 * req_hit_ratio + 0.40 * concept_hit_ratio) * 100.0, 1))

        # R: Responsibility alignment across tailored summary, experiences & projects (0-100)
        resp_text = " ".join([
            customized.tailored_summary or "",
            " ".join(b for e in customized.experiences for b in e.bullets),
            " ".join(customized.slot1_bullets or []),
            " ".join(customized.slot2_bullets or []),
        ]).lower()
        resp_resume_tokens = cls._tokenize(resp_text)
        jd_resp_tokens: Set[str] = set()
        for r in structured_jd.get("key_responsibilities", []):
            jd_resp_tokens.update(cls._tokenize(r))
        if jd_resp_tokens:
            r_ratio = len(jd_resp_tokens & resp_resume_tokens) / len(jd_resp_tokens)
            R = min(100.0, round(r_ratio * 155.0, 1))
        else:
            R = 75.0

        # D: Domain & Role-Title alignment (0-100)
        D = 60.0
        if role_title and role_title in (customized.tailored_summary or "").lower():
            D += 25.0
        elif role_title and len(cls._tokenize(role_title) & cls._tokenize(customized.tailored_summary)) >= 1:
            D += 15.0
        if role_family in ("facilities", "service_dispatch") and any(
            k in md_lower for k in ("mri angus", "wpm plus", "vonigo", "dispatch", "cmms", "hvac", "mechanical", "bms")
        ):
            D += 15.0
        elif role_family in ("software_it", "operations_general", "general") and len(jd_concepts & resume_concepts) >= 1:
            D += 15.0
        D = min(100.0, round(D, 1))

        # K: Overall JD keyword coverage across final Markdown (0-100)
        jd_keywords = cls._tokenize(jd_lower)
        if jd_keywords:
            matched_kw_count = len(jd_keywords & resume_tokens)
            denom = min(len(jd_keywords), 40)
            K = min(100.0, round((matched_kw_count / denom) * 125.0, 1))
        else:
            K = 75.0

        overall = round(min(100.0, max(0.0, 0.40 * T + 0.25 * R + 0.20 * D + 0.15 * K)), 1)
        return ATSScoreBreakdown(
            overall_score=overall,
            technical_overlap=T,
            responsibility_alignment=R,
            domain_relevance=D,
            keyword_coverage=K,
            formula="0.40*T + 0.25*R + 0.20*D + 0.15*K",
            matched_keywords=matched_reqs,
            missing_keywords=missing_reqs,
        )
