from datetime import datetime
import re
from typing import Dict, Any, List, Tuple, Optional
from backend.core.security import strip_github_links
from backend.models.schemas import Stage2CustomizationResult, TunedExperience
from backend.llm.base import _parse_and_structure_raw_jd


class FactualInvarianceValidationError(Exception):
    """Raised when an AI-generated resume violates core factual invariance rules."""
    pass


class ResumeValidator:
    _UNVERIFIED_CERT_PATTERNS = [
        r',?\s*eligible for 5th Class Power Engineering,?',
        r'5th Class Power Engineering[^\.;]*[\.;]?',
        r'\bBOMA\s+(?:courses?|certifications?|tickets?)\b[^\.;]*[\.;]?',
    ]

    @staticmethod
    def _parse_date_sort_key(date_range: str) -> Tuple[int, int]:
        """
        Parses start date from a date_range string (e.g., 'Apr 2026 - Present', 'Feb 2023 - Present')
        into a (year, month) tuple for reverse-chronological sorting using datetime.strptime.
        """
        if not date_range:
            return (0, 0)
        start_part = re.split(r'\s*[-–—]\s*', date_range.strip())[0].strip()
        for fmt in ("%b %Y", "%B %Y", "%Y-%m", "%m/%Y", "%Y"):
            try:
                dt = datetime.strptime(start_part, fmt)
                return (dt.year, dt.month)
            except ValueError:
                continue
        # Fallback regex extraction for month/year tokens
        m = re.search(
            r'\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{4})\b',
            date_range,
            re.IGNORECASE
        )
        if m:
            try:
                dt = datetime.strptime(f"{m.group(1)[:3].title()} {m.group(2)}", "%b %Y")
                return (dt.year, dt.month)
            except ValueError:
                pass
        yr = re.search(r'\b(19\d{2}|20\d{2})\b', date_range)
        if yr:
            return (int(yr.group(1)), 1)
        return (0, 0)

    @staticmethod
    def _clean_text_artifacts(text: str, master_certs: str) -> str:
        if not text:
            return ""
        cleaned = re.sub(r'Results-driven technology and professional', '', text, flags=re.I).strip()
        cleaned = cleaned.replace("directly analogous to AI adoption facilitation with business stakeholders", "").strip()
        cleaned = re.sub(r',?\s*directly analogous to [^.,;]+', '', cleaned, flags=re.I).strip()
        cleaned = re.sub(
            r'\(directly transferable to Angus and WPM Plus\)',
            'utilizing enterprise CMMS workflows equivalent to MRI Angus and WPM Plus',
            cleaned,
            flags=re.I
        )
        certs_lower = (master_certs or "").lower()
        if "5th class" not in certs_lower:
            for pat in ResumeValidator._UNVERIFIED_CERT_PATTERNS:
                cleaned = re.sub(pat, '', cleaned, flags=re.I).strip()
        return cleaned

    @staticmethod
    def validate_and_sanitize(
        master_parsed: Dict[str, Any],
        customized: Stage2CustomizationResult,
        job_description: Optional[str] = None
    ) -> Tuple[Stage2CustomizationResult, List[str]]:
        """
        Validates the customized resume data against the master resume:
        1. Matches tailored experience entries to master entries by normalized (company, title) or company key
           so reordered LLM outputs never overwrite the wrong employer's bullets.
        2. Restores tampered job titles, companies, dates, and locations verbatim.
        3. Sorts experiences in reverse-chronological order using real date parsing.
        4. Enforces that proposed projects are explicitly marked and labeled.
        5. Strips unverified certifications and GitHub links from body text.
        """
        warnings: List[str] = []
        master_exps = master_parsed.get("experiences", [])
        master_certs = master_parsed.get("certifications", "")
        tuned_exps = list(customized.experiences or [])

        if len(tuned_exps) != len(master_exps):
            warnings.append(
                f"AI returned {len(tuned_exps)} experience records vs {len(master_exps)} in master. "
                "Aligning strictly to master employment history."
            )

        # Match each master experience by (company, title) or company key first
        used_indices = set()
        matched_pairs: List[Tuple[Dict[str, Any], TunedExperience]] = []
        unmatched_master_indices: List[int] = []

        for m_idx, m_exp in enumerate(master_exps):
            m_comp = m_exp["company"].strip().lower()
            m_title = m_exp["title"].strip().lower()
            found_t_idx = None

            # Exact (company, title) match
            for t_idx, t_exp in enumerate(tuned_exps):
                if t_idx in used_indices:
                    continue
                if t_exp.company.strip().lower() == m_comp and t_exp.title.strip().lower() == m_title:
                    found_t_idx = t_idx
                    break

            # Fallback to company match or title match
            if found_t_idx is None:
                for t_idx, t_exp in enumerate(tuned_exps):
                    if t_idx in used_indices:
                        continue
                    if t_exp.company.strip().lower() == m_comp or t_exp.title.strip().lower() == m_title:
                        found_t_idx = t_idx
                        break

            if found_t_idx is not None:
                used_indices.add(found_t_idx)
                matched_pairs.append((m_exp, tuned_exps[found_t_idx]))
            else:
                unmatched_master_indices.append(m_idx)

        # Pair any remaining unmatched master entries with remaining unused tuned entries (tampered records)
        remaining_tuned = [t_exp for t_idx, t_exp in enumerate(tuned_exps) if t_idx not in used_indices]
        for m_idx in unmatched_master_indices:
            m_exp = master_exps[m_idx]
            if remaining_tuned:
                t_exp = remaining_tuned.pop(0)
                matched_pairs.append((m_exp, t_exp))
            else:
                matched_pairs.append((
                    m_exp,
                    TunedExperience(
                        company=m_exp["company"],
                        title=m_exp["title"],
                        date_range=m_exp["date_range"],
                        location=m_exp["location"],
                        bullets=list(m_exp["bullets"])
                    )
                ))

        aligned_exps: List[TunedExperience] = []
        for m_exp, t_exp in matched_pairs:
            if m_exp["company"].strip().lower() != t_exp.company.strip().lower():
                warnings.append(f"Restoring original company name: '{m_exp['company']}' (was altered to '{t_exp.company}')")
                t_exp.company = m_exp["company"]

            if m_exp["title"].strip().lower() != t_exp.title.strip().lower():
                warnings.append(f"Restoring original job title: '{m_exp['title']}' (was altered to '{t_exp.title}')")
                t_exp.title = m_exp["title"]

            if m_exp["date_range"].strip() != t_exp.date_range.strip():
                warnings.append(f"Restoring original employment dates: '{m_exp['date_range']}'")
                t_exp.date_range = m_exp["date_range"]

            if m_exp["location"].strip() != t_exp.location.strip():
                t_exp.location = m_exp["location"]

            cleaned_bullets = []
            for b in t_exp.bullets:
                b_str = ResumeValidator._clean_text_artifacts(b.strip(), master_certs)
                if not b_str or b_str == ".":
                    continue
                cleaned_bullets.append(strip_github_links(b_str))

            t_exp.bullets = cleaned_bullets if cleaned_bullets else [strip_github_links(b) for b in m_exp["bullets"]]
            aligned_exps.append(t_exp)

        # Sort experiences in reverse-chronological order using real date parsing
        aligned_exps.sort(key=lambda e: ResumeValidator._parse_date_sort_key(e.date_range), reverse=True)
        customized.experiences = aligned_exps

        # Normalize skill category headings (e.g. CORE COMPETENCIES -> Core Competencies) & guard unverified certs
        certs_lower = (master_certs or "").lower()
        for cat in customized.skill_categories:
            if cat.category_name.isupper():
                cat.category_name = cat.category_name.title()
            if "5th class" not in certs_lower:
                cat.skills = [
                    s for s in cat.skills
                    if "5th class" not in s.lower() and "boma" not in s.lower()
                ]

        # Project Slot 2: Custom JD-Fit Proposed Project & '(Under Development)' Label Enforcement
        fallback_proj = _parse_and_structure_raw_jd(job_description or "")["proposed_project"]
        raw_s2_title = re.sub(
            r'\s*\((?:Targeted Implementation / Prototype|Proposed Project|Proposed|Under Development)\)',
            '',
            customized.slot2_title or "",
            flags=re.I
        ).strip()

        if not raw_s2_title or raw_s2_title.lower() in {
            "project title", "project", "project 2", "second project", "complementary systems project"
        }:
            customized.slot2_title = fallback_proj["title"]
            customized.slot2_is_proposed = True
            warnings.append("Replaced placeholder Slot 2 title with JD-tailored '(Under Development)' project title.")
        elif customized.slot2_is_proposed or "(under development)" in (customized.slot2_title or "").lower() or job_description:
            customized.slot2_is_proposed = True
            required_badge = "(Under Development)"
            if required_badge.lower() not in customized.slot2_title.lower():
                customized.slot2_title = f"{raw_s2_title} {required_badge}"
                warnings.append("Appended '(Under Development)' badge to Project Slot 2 title.")

        # Clean summary and project bullets
        customized.tailored_summary = strip_github_links(
            ResumeValidator._clean_text_artifacts(customized.tailored_summary, master_certs)
        )

        customized.slot1_bullets = [
            strip_github_links(ResumeValidator._clean_text_artifacts(b.strip(), master_certs))
            for b in customized.slot1_bullets
            if b.strip() and b.strip() != "."
        ]
        cleaned_s2_bullets = [
            strip_github_links(ResumeValidator._clean_text_artifacts(b.strip(), master_certs))
            for b in customized.slot2_bullets
            if b.strip() and b.strip() not in {".", "bullet", "string", "project bullet"}
        ]
        if not cleaned_s2_bullets or (job_description and (len(cleaned_s2_bullets) < 2 or any(len(b) < 20 for b in cleaned_s2_bullets))):
            cleaned_s2_bullets = list(fallback_proj["bullets"])
            warnings.append("Populated Project Slot 2 with JD-tailored '(Under Development)' project bullets.")
        customized.slot2_bullets = cleaned_s2_bullets

        return customized, warnings
