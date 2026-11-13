import re
from typing import Dict, Any, List
from backend.core.security import strip_github_links
from backend.models.schemas import Stage2CustomizationResult, DiffItem

class MarkdownAssembler:
    @staticmethod
    def assemble(
        master_parsed: Dict[str, Any],
        customized: Stage2CustomizationResult
    ) -> str:
        """
        Assembles structured resume sections into a clean, deterministic, ATS-friendly Markdown document.
        """
        lines = []
        
        # 1. Header & Contact
        name = master_parsed.get("name", "Candidate")
        contact_raw = master_parsed.get("contact", "").strip()
        
        lines.append(f"# {name}")
        lines.append(contact_raw)
        lines.append("")
        
        # 2. Professional Summary
        lines.append("## Professional Summary")
        lines.append(customized.tailored_summary.strip())
        lines.append("")
        
        # 3. Technical Skills
        lines.append("## Technical Skills")
        for cat in customized.skill_categories:
            skills_joined = ", ".join([s.strip() for s in cat.skills if s.strip()])
            lines.append(f"- **{cat.category_name}:** {skills_joined}")
        lines.append("")
        
        # 4. Professional Experience
        lines.append("## Professional Experience")
        for exp in customized.experiences:
            lines.append(f"### {exp.title} | {exp.company}")
            lines.append(f"*{exp.date_range} | {exp.location}*")
            for bullet in exp.bullets:
                b_str = bullet.strip()
                if b_str and b_str != ".":
                    lines.append(f"- {b_str}")
            lines.append("")
            
        # 5. Projects (Slot 1 and Slot 2)
        lines.append("## Projects")
        
        # Slot 1
        slot1_title = customized.slot1_title
        if customized.slot1_github_url and "[github]" not in slot1_title.lower():
            slot1_title = f"{slot1_title} | [GitHub]({customized.slot1_github_url})"
        lines.append(f"### {slot1_title}")
        for bullet in customized.slot1_bullets:
            b_str = bullet.strip()
            if b_str and b_str != ".":
                lines.append(f"- {b_str}")
        lines.append("")
        
        # Slot 2
        slot2_title = customized.slot2_title
        if customized.slot2_is_proposed:
            slot2_title = re.sub(
                r'\s*\((?:Targeted Implementation / Prototype|Proposed Project|Proposed)\)',
                '',
                slot2_title,
                flags=re.I
            ).strip()
            if "(under development)" not in slot2_title.lower():
                slot2_title = f"{slot2_title} (Under Development)"
        elif customized.slot2_github_url and "[github]" not in slot2_title.lower():
            slot2_title = f"{slot2_title} | [GitHub]({customized.slot2_github_url})"

        lines.append(f"### {slot2_title}")
        for bullet in customized.slot2_bullets:
            b_str = bullet.strip()
            if b_str and b_str != ".":
                lines.append(f"- {b_str}")
        lines.append("")
        
        # 6. Education
        education_content = master_parsed.get("education", "").strip()
        if education_content:
            # Clean headers: remove stars and normalize italics to asterisks
            clean_edu = re.sub(r'###\s*\*\*([^\*]+)\*\*', r'### \1', education_content)
            clean_edu = re.sub(r'_\s*([^_\n]+)\s*_', r'*\1*', clean_edu)
            lines.append("## Education")
            lines.append(clean_edu)
            lines.append("")

        # 7. Certifications & Licenses (if present in master)
        certifications_content = master_parsed.get("certifications", "").strip()
        if certifications_content:
            lines.append("## Certifications & Licenses")
            lines.append(certifications_content)
            lines.append("")
            
        return "\n".join(lines).strip()

    @staticmethod
    def generate_diffs(
        master_parsed: Dict[str, Any],
        customized: Stage2CustomizationResult,
        projects: List[Any] = None
    ) -> List[DiffItem]:
        """
        Generates section-by-section diff items for the frontend comparison view,
        including Professional Summary, Technical Skills, Experience Bullets, and Project Slots.
        """
        diffs = []
        
        # 1. Summary diff
        orig_summary = master_parsed.get("summary", "")
        if orig_summary != customized.tailored_summary:
            diffs.append(DiffItem(
                section="Professional Summary",
                original=orig_summary,
                modified=customized.tailored_summary,
                change_type="modified"
            ))
            
        # 2. Skills diff
        orig_skills = master_parsed.get("skills_raw", "")
        new_skills = "\n".join([f"- **{c.category_name}:** {', '.join(c.skills)}" for c in customized.skill_categories])
        diffs.append(DiffItem(
            section="Technical Skills",
            original=orig_skills,
            modified=new_skills,
            change_type="reordered"
        ))

        # 3. Experience bullet diffs (per employer)
        master_exps = master_parsed.get("experiences", [])
        master_by_comp = {e["company"].strip().lower(): e for e in master_exps}
        for t_exp in customized.experiences:
            m_exp = master_by_comp.get(t_exp.company.strip().lower())
            orig_bullets = "\n".join([f"- {b}" for b in (m_exp["bullets"] if m_exp else [])])
            mod_bullets = "\n".join([f"- {b}" for b in t_exp.bullets])
            if orig_bullets != mod_bullets:
                diffs.append(DiffItem(
                    section=f"Experience: {t_exp.title} | {t_exp.company}",
                    original=orig_bullets or "[Master Experience Baseline]",
                    modified=mod_bullets,
                    change_type="modified"
                ))
        
        # 4. Projects diff (lookup actual catalog project baseline if available)
        projects_by_title = {}
        if projects:
            for p in projects:
                projects_by_title[p.title.strip().lower()] = p

        p1_match = projects_by_title.get(customized.slot1_title.strip().lower())
        p1_orig = p1_match.full_markdown.strip() if (p1_match and p1_match.full_markdown) else (master_parsed.get("projects_raw") or "[Catalog Project Baseline]")
        diffs.append(DiffItem(
            section="Project Slot 1",
            original=p1_orig,
            modified=f"{customized.slot1_title}\n" + "\n".join([f"- {b}" for b in customized.slot1_bullets]),
            change_type="selected"
        ))
        
        slot2_type = "proposed" if customized.slot2_is_proposed else "selected"
        clean_s2_title = re.sub(r'\s*\(Under Development\)\s*$', '', customized.slot2_title, flags=re.I).strip().lower()
        p2_match = projects_by_title.get(clean_s2_title)
        if customized.slot2_is_proposed:
            p2_orig = "[New 1-2 Day Targeted Prototype Proposal]"
        elif p2_match and p2_match.full_markdown:
            p2_orig = p2_match.full_markdown.strip()
        else:
            p2_orig = master_parsed.get("projects_raw") or "[Catalog Project Baseline]"

        diffs.append(DiffItem(
            section="Project Slot 2",
            original=p2_orig,
            modified=f"{customized.slot2_title}\n" + "\n".join([f"- {b}" for b in customized.slot2_bullets]),
            change_type=slot2_type
        ))
        
        return diffs
