import logging
import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Any, Tuple
from fastapi import HTTPException
from backend.core.config import settings
from backend.models.schemas import ProjectMetadata

logger = logging.getLogger(__name__)


class MasterResumeParser:
    @staticmethod
    def _normalize_category_name(name: str) -> str:
        cleaned = name.strip().rstrip(":").strip()
        if cleaned.isupper():
            return cleaned.title()
        return cleaned

    @staticmethod
    def _parse_contact_metadata(name: str, contact_line: str) -> Dict[str, str]:
        email_match = re.search(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', contact_line)
        phone_match = re.search(r'(?:\+?\d[\d\s\-().]{7,}\d)', contact_line)
        linkedin_match = re.search(r'https?://(?:www\.)?linkedin\.com/[^\s\)|]+', contact_line, re.I)
        github_match = re.search(r'https?://(?:www\.)?github\.com/[^\s\)|]+', contact_line, re.I)

        parts = [p.strip() for p in contact_line.split("|") if p.strip()]
        location = parts[0] if parts and "@" not in parts[0] and not any(c.isdigit() for c in parts[0]) else ""

        return {
            "name": name,
            "location": location,
            "phone": phone_match.group(0).strip() if phone_match else "",
            "email": email_match.group(0).strip() if email_match else "",
            "linkedin": linkedin_match.group(0).strip() if linkedin_match else "",
            "github": github_match.group(0).strip() if github_match else "",
            "raw": contact_line
        }

    @staticmethod
    def parse(markdown_text: str) -> Dict[str, Any]:
        """
        Parses master resume markdown into structured sections.
        Works robustly with various heading styles (##, ###, **HEADING**, etc.)
        """
        lines = markdown_text.splitlines()
        data: Dict[str, Any] = {
            "name": "",
            "contact": "",
            "contact_info": {},
            "summary": "",
            "skills": [],
            "skills_raw": "",
            "experiences": [],
            "experiences_raw": "",
            "projects_raw": "",
            "education": "",
            "certifications": "",
            "raw": markdown_text
        }
        
        # 1. Parse Name & Contact Header
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("# ") and not data["name"]:
                data["name"] = stripped.removeprefix("# ").replace("**", "").strip()
                for next_line in lines[i+1:]:
                    nl = next_line.strip()
                    if nl and not nl.startswith("#"):
                        data["contact"] = nl.replace("**", "").strip()
                        break
                break

        # Fallback for name if not found with #
        if not data["name"] and lines:
            first_line = lines[0].strip().replace("**", "").replace("#", "").strip()
            if first_line:
                data["name"] = first_line

        data["contact_info"] = MasterResumeParser._parse_contact_metadata(data["name"], data["contact"])

        # 2. Normalize bold section headers like **PROFESSIONAL EXPERIENCE** to ## PROFESSIONAL EXPERIENCE
        text_norm = re.sub(r'(?m)^\s*\*\*([A-Z\s,&/]+)\*\*\s*$', r'## \1', markdown_text)
        raw_sections = re.split(r'(?m)^##\s+', text_norm)

        in_experience_section = False
        skills_raw_parts = []

        for s in raw_sections:
            sec_lines = [l for l in s.splitlines()]
            if not sec_lines:
                continue
            h = sec_lines[0].replace("**", "").strip()
            if h.startswith("#"):
                continue
            body = "\n".join(sec_lines[1:]).strip()
            h_lower = h.lower().strip()

            if h_lower in ("professional summary", "summary", "profile", "executive summary"):
                data["summary"] = body
                in_experience_section = False
            elif re.match(r'^(certifications?|licenses?|certifications?\s*&\s*licenses?)$', h_lower):
                data["certifications"] = body
                in_experience_section = False
            elif re.match(r'^(core competencies|technical skills|skills|technical skills\s*&\s*building systems)$', h_lower):
                skills_raw_parts.append(body)
                in_experience_section = False
                cat_matches = re.findall(r'(?:^|\n)(?:-\s*)?\*\*([^\*:]+):?\*\*\s*:?\s*(.+)', body)
                if cat_matches:
                    for cat, items in cat_matches:
                        clean_skills = [x.strip() for x in re.split(r',\s*(?![^()]*\))', items) if x.strip()]
                        data["skills"].append({
                            "category": MasterResumeParser._normalize_category_name(cat),
                            "skills": clean_skills
                        })
                elif "•" in body:
                    items = [x.strip() for x in body.split("•") if x.strip()]
                    data["skills"].append({
                        "category": MasterResumeParser._normalize_category_name(h),
                        "skills": items
                    })
                else:
                    bullet_items = [re.sub(r'^[-*]\s*', '', l).strip() for l in body.splitlines() if l.strip().startswith(('-', '*'))]
                    if bullet_items:
                        data["skills"].append({
                            "category": MasterResumeParser._normalize_category_name(h),
                            "skills": bullet_items
                        })
            elif re.match(r'^(education|academic background)$', h_lower):
                data["education"] = body
                in_experience_section = False
            elif re.match(r'^(projects|relevant projects|relevant operations projects|technical projects|key projects)$', h_lower):
                data["projects_raw"] = body
                in_experience_section = False
            elif re.match(r'^(professional experience|experience|employment history|work history)$', h_lower):
                in_experience_section = True
                data["experiences_raw"] = body
                if "###" in body:
                    # Parse jobs inside the experience body (Alex Morgan style)
                    data["experiences"].extend(MasterResumeParser._parse_nested_experiences(body))
            elif in_experience_section:
                # Individual job header under experience (Manbir style)
                b_lines = [l.strip() for l in sec_lines[1:] if l.strip()]
                company = ""
                date_range = ""
                location = ""
                bullets = []
                for bl in b_lines:
                    if (bl.startswith('_') and bl.endswith('_')) or (bl.startswith('*') and bl.endswith('*')):
                        cleaned = bl.strip('_*').strip()
                        if '|' in cleaned:
                            parts = [p.strip() for p in cleaned.split('|')]
                            company = parts[0]
                            location = parts[1] if len(parts) > 1 else ""
                        elif any(m in cleaned.lower() for m in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec', 'present', '202']):
                            date_range = cleaned
                        elif not company:
                            company = cleaned
                    elif bl.startswith(('-', '*')):
                        bullets.append(re.sub(r'^[-*]\s*', '', bl).strip())

                data["experiences"].append({
                    "title": h,
                    "company": company or "Organization",
                    "date_range": date_range or "",
                    "location": location or "",
                    "bullets": bullets
                })
            else:
                logger.warning("Unrecognized master resume section heading skipped: '%s'", h)

        data["skills_raw"] = "\n\n".join(skills_raw_parts)
        return data

    @staticmethod
    def _parse_nested_experiences(exp_text: str) -> List[Dict[str, Any]]:
        """
        Parses nested jobs separated by ###
        """
        jobs = []
        job_blocks = re.split(r'\n(?=###\s+)', exp_text)
        for block in job_blocks:
            if not block.strip():
                continue
            lines = [l.strip() for l in block.splitlines() if l.strip()]
            header_line = lines[0].replace("###", "").replace("**", "").strip()
            parts = [p.strip() for p in header_line.split("|")]
            title = parts[0]
            company = parts[1] if len(parts) > 1 else ""

            date_range = ""
            location = ""
            bullets = []

            for line in lines[1:]:
                if line.startswith('*') and line.endswith('*'):
                    m_parts = [p.strip() for p in line.strip('*').split('|')]
                    date_range = m_parts[0]
                    location = m_parts[1] if len(m_parts) > 1 else ""
                elif (line.startswith('_') and line.endswith('_')):
                    m_parts = [p.strip() for p in line.strip('_').split('|')]
                    date_range = m_parts[0]
                    location = m_parts[1] if len(m_parts) > 1 else ""
                elif line.startswith(('-', '*')):
                    bullet = re.sub(r'^[-*]\s*', '', line).strip()
                    if bullet:
                        bullets.append(bullet)

            jobs.append({
                "title": title or "Professional Role",
                "company": company or "Organization",
                "date_range": date_range or "",
                "location": location or "",
                "bullets": bullets
            })
        return jobs


class FileLoaderService:
    @staticmethod
    def get_master_resume() -> Tuple[str, Dict[str, Any]]:
        """
        Reads master resume strictly read-only.
        Auto-detects active master resume file in data/master.
        """
        path = settings.MASTER_RESUME_PATH
        if not path.exists():
            # Fallback auto-detection inside data/master
            master_dir = settings.DATA_DIR / "master"
            if master_dir.exists():
                md_files = list(master_dir.glob("*.md"))
                if md_files:
                    path = md_files[0]
                    
        if not path.exists():
            logger.error("Master resume not found at path: %s", path)
            raise HTTPException(
                status_code=500,
                detail="Master resume not found. Ensure a markdown (.md) resume exists in data/master/."
            )
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            parsed = MasterResumeParser.parse(content)
            return content, parsed
        except Exception:
            logger.exception("Error reading master resume from %s", path)
            raise HTTPException(
                status_code=500,
                detail="Error reading master resume file."
            )

    @staticmethod
    def get_project_catalog() -> List[ProjectMetadata]:
        """
        Scans data/projects for markdown files with YAML frontmatter.
        """
        projects_dir = settings.PROJECTS_DIR
        if not projects_dir.exists():
            return []
            
        projects: List[ProjectMetadata] = []
        for file_path in projects_dir.glob("*.md"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    file_text = f.read()
                    
                meta, body = FileLoaderService._extract_frontmatter(file_text)
                
                # Required metadata fields
                p_id = meta.get("id", file_path.stem)
                p_title = meta.get("title", file_path.stem.replace("_", " ").title())
                p_tech = meta.get("technologies", [])
                p_domain = meta.get("domain", "General")
                p_status = meta.get("status", "completed")
                p_summary = meta.get("summary", "")
                p_metrics = meta.get("metrics", "")
                p_github_url = meta.get("github_url")
                p_github_repo = meta.get("github_repo")
                
                projects.append(ProjectMetadata(
                    id=p_id,
                    title=p_title,
                    technologies=p_tech,
                    domain=p_domain,
                    status=p_status,
                    summary=p_summary,
                    metrics=p_metrics,
                    full_markdown=body,
                    github_url=p_github_url,
                    github_repo=p_github_repo
                ))
            except Exception as e:
                print(f"Warning: Failed to load project {file_path.name}: {e}")
                
        return projects

    @staticmethod
    def _extract_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
        """
        Extracts YAML frontmatter from markdown file.
        """
        if not text.startswith("---"):
            return {}, text
            
        parts = text.split("---", 2)
        if len(parts) < 3:
            return {}, text
            
        try:
            metadata = yaml.safe_load(parts[1])
            body = parts[2].strip()
            return metadata or {}, body
        except Exception:
            return {}, text
