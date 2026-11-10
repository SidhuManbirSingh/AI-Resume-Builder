import re
from typing import Dict, Any, List, Tuple
from backend.core.security import strip_github_links
from backend.models.schemas import Stage2CustomizationResult, TunedExperience

class FactualInvarianceValidationError(Exception):
    """Raised when an AI-generated resume violates core factual invariance rules."""
    pass

class ResumeValidator:
    @staticmethod
    def validate_and_sanitize(
        master_parsed: Dict[str, Any],
        customized: Stage2CustomizationResult
    ) -> Tuple[Stage2CustomizationResult, List[str]]:
        """
        Validates the customized resume data against the master resume:
        1. Ensures job titles, companies, dates, and locations match verbatim.
        2. Ensures number of employment history records matches master.
        3. Enforces that proposed projects are explicitly marked and labeled.
        4. Verifies no GitHub links exist.
        Returns the sanitized result and a list of verification notices.
        """
        warnings = []
        master_exps = master_parsed.get("experiences", [])
        tuned_exps = customized.experiences

        # 1. Experience count and identity invariance
        # Ensure tuned_exps has exactly the same records as master_exps
        if len(tuned_exps) != len(master_exps):
            warnings.append(f"AI returned {len(tuned_exps)} experience records vs {len(master_exps)} in master. Aligning strictly to master employment history.")
            # Map tuned experiences by company key
            tuned_by_company = {t.company.strip().lower(): t for t in tuned_exps}
            aligned_exps = []
            for m_exp in master_exps:
                m_comp = m_exp["company"].strip().lower()
                if m_comp in tuned_by_company:
                    aligned_exps.append(tuned_by_company[m_comp])
                else:
                    # Fallback to pristine master experience
                    aligned_exps.append(TunedExperience(
                        company=m_exp["company"],
                        title=m_exp["title"],
                        date_range=m_exp["date_range"],
                        location=m_exp["location"],
                        bullets=m_exp["bullets"]
                    ))
            customized.experiences = aligned_exps
            tuned_exps = customized.experiences

        # 2. Strict Company, Title, Date invariance
        for i, (m_exp, t_exp) in enumerate(zip(master_exps, tuned_exps)):
            # Enforce exact match on company
            if m_exp["company"].strip().lower() != t_exp.company.strip().lower():
                warnings.append(f"Restoring original company name: '{m_exp['company']}' (was altered to '{t_exp.company}')")
                t_exp.company = m_exp["company"]
            
            # Enforce exact match on title
            if m_exp["title"].strip().lower() != t_exp.title.strip().lower():
                warnings.append(f"Restoring original job title: '{m_exp['title']}' (was altered to '{t_exp.title}')")
                t_exp.title = m_exp["title"]
            
            # Enforce exact match on date range
            if m_exp["date_range"].strip() != t_exp.date_range.strip():
                warnings.append(f"Restoring original employment dates: '{m_exp['date_range']}'")
                t_exp.date_range = m_exp["date_range"]

            # Enforce exact match on location
            if m_exp["location"].strip() != t_exp.location.strip():
                t_exp.location = m_exp["location"]

            # Validate bullets: don't allow blank bullets, strip floating periods and clean leftover artifacts
            cleaned_bullets = []
            for b in t_exp.bullets:
                b_str = b.strip()
                if not b_str or b_str == ".":
                    continue
                # Remove leftover AI text
                b_str = b_str.replace("directly analogous to AI adoption facilitation with business stakeholders", "").strip()
                # Replace defensive notes with active enterprise CMMS phrasing
                b_str = re.sub(
                    r'\(directly transferable to Angus and WPM Plus\)',
                    'utilizing enterprise CMMS workflows equivalent to MRI Angus and WPM Plus',
                    b_str,
                    flags=re.I
                )
                cleaned_bullets.append(b_str)

            t_exp.bullets = cleaned_bullets
            if not t_exp.bullets:
                # Fallback to master bullets if AI emptied them
                t_exp.bullets = m_exp["bullets"]

        # Enforce reverse-chronological order: Apr 2026 above Feb 2023
        def exp_order(e: TunedExperience):
            dr = e.date_range.lower()
            if "2026" in dr:
                return 0
            elif "2023" in dr:
                return 1
            return 2

        customized.experiences.sort(key=exp_order)

        # 3. Project Slot 2 Proposed Label Enforcement
        if customized.slot2_is_proposed:
            # Clean any legacy prototype/proposed tags
            customized.slot2_title = re.sub(
                r'\s*\((?:Targeted Implementation / Prototype|Proposed Project|Proposed)\)',
                '',
                customized.slot2_title,
                flags=re.I
            ).strip()

            required_badge = "(Under Development)"
            if required_badge.lower() not in customized.slot2_title.lower():
                customized.slot2_title = f"{customized.slot2_title} {required_badge}"
                warnings.append("Appended '(Under Development)' badge to Project Slot 2 title.")

        # 4. Clean up summary typos and leftover AI text
        customized.tailored_summary = re.sub(
            r'Results-driven technology and professional',
            '',
            customized.tailored_summary,
            flags=re.I
        ).strip()
        customized.tailored_summary = customized.tailored_summary.replace(
            "directly analogous to AI adoption facilitation with business stakeholders", ""
        ).strip()

        # Clean slot bullets
        clean_s1 = []
        for b in customized.slot1_bullets:
            b_s = b.strip()
            if b_s and b_s != ".":
                b_s = b_s.replace("directly analogous to AI adoption facilitation with business stakeholders", "").strip()
                b_s = re.sub(r'\(directly transferable to Angus and WPM Plus\)', 'utilizing enterprise CMMS workflows equivalent to MRI Angus and WPM Plus', b_s, flags=re.I)
                clean_s1.append(b_s)
        customized.slot1_bullets = clean_s1

        clean_s2 = []
        for b in customized.slot2_bullets:
            b_s = b.strip()
            if b_s and b_s != ".":
                b_s = b_s.replace("directly analogous to AI adoption facilitation with business stakeholders", "").strip()
                b_s = re.sub(r'\(directly transferable to Angus and WPM Plus\)', 'utilizing enterprise CMMS workflows equivalent to MRI Angus and WPM Plus', b_s, flags=re.I)
                clean_s2.append(b_s)
        customized.slot2_bullets = clean_s2

        # 5. Strip any GitHub references from Summary and Bullets
        customized.tailored_summary = strip_github_links(customized.tailored_summary)
        for exp in customized.experiences:
            exp.bullets = [strip_github_links(b) for b in exp.bullets]
        customized.slot1_bullets = [strip_github_links(b) for b in customized.slot1_bullets]
        customized.slot2_bullets = [strip_github_links(b) for b in customized.slot2_bullets]

        return customized, warnings
