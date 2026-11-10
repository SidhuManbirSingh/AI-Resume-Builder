import os
import json
import re
from typing import Dict, Any, List, Optional, Tuple
import requests
from backend.core.config import settings
from backend.models.schemas import (
    Stage1AnalysisResult,
    Stage2CustomizationResult,
    ProjectMetadata,
    SkillCategory,
    TunedExperience
)

class BaseLLMClient:
    def analyze_and_select(
        self,
        job_description: str,
        master_parsed: Dict[str, Any],
        projects: List[ProjectMetadata]
    ) -> Stage1AnalysisResult:
        raise NotImplementedError

    def customize_sections(
        self,
        job_description: str,
        master_parsed: Dict[str, Any],
        stage1_result: Stage1AnalysisResult,
        projects: List[ProjectMetadata]
    ) -> Stage2CustomizationResult:
        raise NotImplementedError

    def generate_cover_letter(
        self,
        job_description: str,
        resume_markdown: str,
        additional_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        raise NotImplementedError

    def generate_outreach(
        self,
        job_description: str,
        resume_markdown: str,
        additional_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        raise NotImplementedError


class MockLLMClient(BaseLLMClient):
    """
    High-fidelity deterministic local engine for local development & offline testing.
    Performs intelligent keyword extraction, project ranking, and targeted tuning without requiring external API credits.
    """
    def analyze_and_select(
        self,
        job_description: str,
        master_parsed: Dict[str, Any],
        projects: List[ProjectMetadata]
    ) -> Stage1AnalysisResult:
        jd_lower = job_description.lower()
        
        # 1. Infer Target Role Title
        title_match = re.search(r'(?:title|position|role):\s*([^\n\r,]+)', job_description, re.IGNORECASE)
        if title_match:
            target_role = title_match.group(1).strip()
        else:
            role_regex = re.search(
                r'(senior|lead|chief|assistant)?\s*(building\s+operations\s+coordinator|facility\s+manager|facilities\s+coordinator|building\s+operator|operations\s+coordinator|property\s+operations\s+coordinator|building\s+systems\s+operator)',
                jd_lower
            )
            if not role_regex:
                role_regex = re.search(
                    r'(senior|lead|staff|principal)?\s*(software|backend|systems|cloud|platform|data|infrastructure)\s*(engineer|developer|architect)',
                    jd_lower
                )
            if not role_regex:
                role_regex = re.search(
                    r'([A-Za-z\s/&-]+(?:Coordinator|Specialist|Manager|Supervisor|Engineer|Operator|Technician))',
                    job_description
                )
            target_role = role_regex.group(0).strip().title() if role_regex else "Building Operations Coordinator & Assistant Facility Manager"

        is_facilities = any(k in jd_lower for k in [
            "facility", "facilities", "building", "hvac", "bms", "bas", "maintenance", "operations", "property", "chiller", "boiler", "pumps"
        ]) or any(k in target_role.lower() for k in [
            "facility", "facilities", "building", "operations", "operator", "property"
        ])

        # 2. Extract technical requirements from JD
        if is_facilities:
            tech_keywords = [
                "bms", "bas", "hvac", "chillers", "boilers", "cooling towers", "pumps", "ahus",
                "mri angus", "wpm plus", "ofa level 1", "5th class", "power engineering",
                "preventative maintenance", "plumbing", "electrical", "work orders"
            ]
            found_tech = [t.title() for t in tech_keywords if t in jd_lower]
            if not found_tech:
                found_tech = ["BMS/BAS Controls", "HVAC & Mechanical Systems", "MRI Angus", "Preventative Maintenance", "OFA Level 1"]
        else:
            tech_keywords = [
                "python", "go", "golang", "fastapi", "django", "kafka", "aws", "kubernetes",
                "docker", "redis", "postgresql", "terraform", "microservices", "distributed systems",
                "rag", "llm", "vector", "grpc", "ci/cd", "prometheus", "graphql"
            ]
            found_tech = [t.capitalize() for t in tech_keywords if t in jd_lower]
            if not found_tech:
                found_tech = ["Python", "Go", "AWS", "PostgreSQL", "Docker"]

        # 3. Score and Rank Existing Projects
        scored_projects = []
        for p in projects:
            score = 0
            for tech in p.technologies:
                if tech.lower() in jd_lower:
                    score += 3
            if p.domain.lower() in jd_lower:
                score += 2
            for word in p.summary.lower().split():
                if len(word) > 4 and word in jd_lower:
                    score += 1
            scored_projects.append((score, p))
            
        scored_projects.sort(key=lambda x: x[0], reverse=True)
        slot1_project = scored_projects[0][1] if scored_projects else None
        slot1_id = slot1_project.id if slot1_project else "gitlab_k8s_platform"
        
        # 4. Determine Slot 2: Existing vs Complementary Proposed Project
        gap_tech = None
        for candidate_gap in ["gRPC", "GraphQL", "Apache Spark", "Rust", "WebSockets"]:
            if candidate_gap.lower() in jd_lower:
                gap_tech = candidate_gap
                break
                
        if gap_tech:
            slot2_is_proposed = True
            slot2_project_id = None
            slot2_proposed_title = f"High-Throughput {gap_tech} Service & Integration Test Harness"
            slot2_proposed_tech = [gap_tech, "Go", "Docker", "Redis"]
            slot2_proposed_plan = f"Achievable 1-2 day prototype: Implements core {gap_tech} endpoints with schema validation, connection pooling, and automated integration test coverage in Docker."
            slot2_rationale = f"Job description specifically calls for {gap_tech}. Proposing a lightweight, targeted 1-2 day implementation to demonstrate immediate hands-on capability."
        else:
            slot2_is_proposed = False
            slot2_project = scored_projects[1][1] if len(scored_projects) > 1 else scored_projects[0][1]
            slot2_project_id = slot2_project.id if slot2_project else None
            slot2_proposed_title = None
            slot2_proposed_tech = None
            slot2_proposed_plan = None
            slot2_rationale = f"Existing project '{slot2_project.title if slot2_project else ''}' provides strong, verified evidence of relevant competencies."

        # 5. Extract Company name if present
        company_match = re.search(r'(?:company|client|employer|organization):\s*([^\n\r,]+)', job_description, re.IGNORECASE)
        target_company = company_match.group(1).strip() if company_match else None

        if is_facilities:
            key_resp = [
                "Conduct daily building rounds, inspect mechanical rooms (chillers, boilers, AHUs, pumps), and log system parameters.",
                "Manage computerized work order dispatch (MRI Angus / WPM Plus) and coordinate HVAC, plumbing, and electrical trade contractors.",
                "Ensure strict life-safety, fire system, and Occupational Health & Safety (OH&S) compliance across commercial properties."
            ]
        else:
            key_resp = [
                "Architect and scale reliable backend microservices and distributed APIs.",
                "Optimize data storage, caching layers, and high-throughput transaction pipelines.",
                "Drive engineering best practices, automated testing, and cloud infrastructure reliability."
            ]

        return Stage1AnalysisResult(
            target_role_title=target_role,
            target_company=target_company,
            key_technical_requirements=found_tech[:6],
            key_responsibilities=key_resp,
            slot1_project_id=slot1_id,
            slot1_rationale=f"Project '{slot1_project.title if slot1_project else slot1_id}' exhibits direct alignment with target stack: {', '.join(slot1_project.technologies if slot1_project else [])}.",
            slot2_is_proposed=slot2_is_proposed,
            slot2_project_id=slot2_project_id,
            slot2_rationale=slot2_rationale,
            slot2_proposed_title=slot2_proposed_title,
            slot2_proposed_technologies=slot2_proposed_tech,
            slot2_proposed_plan=slot2_proposed_plan
        )

    def customize_sections(
        self,
        job_description: str,
        master_parsed: Dict[str, Any],
        stage1_result: Stage1AnalysisResult,
        projects: List[ProjectMetadata]
    ) -> Stage2CustomizationResult:
        projects_by_id = {p.id: p for p in projects}
        jd_lower = job_description.lower()
        
        is_facilities = any(k in jd_lower for k in [
            "facility", "facilities", "building", "hvac", "bms", "bas", "maintenance", "operations", "property", "chiller", "boiler", "pumps"
        ]) or any(k in stage1_result.target_role_title.lower() for k in [
            "facility", "facilities", "building", "operations", "operator", "property"
        ])

        # 1. Adapt Professional Summary
        # Fix the summary typo and add exact target job title as headline
        # Keep Security Supervisor secondary so parser categorizes under Facilities Management rather than Protective Services
        if is_facilities:
            tailored_summary = (
                f"{stage1_result.target_role_title} with over 3 years of hands-on commercial property operations experience, "
                "paired with leadership as an Acting Assistant Manager and Security Supervisor. Proven expertise conducting "
                "daily building and mechanical room rounds (chillers, boilers, pumps, AHUs), managing building automation systems "
                "(BAS/BMS), coordinating trade contractors across HVAC, plumbing, and electrical, and maintaining strict OH&S compliance. "
                "Certified in Occupational First Aid (OFA Level 1), eligible for 5th Class Power Engineering, and holds a valid BC Driver's License "
                "with a reliable personal vehicle. Computer Information Systems background (4.1 GPA) focused on preventative maintenance "
                "workflows and computerized building operations."
            )
        else:
            primary_tech = ", ".join(stage1_result.key_technical_requirements[:4])
            tailored_summary = (
                f"{stage1_result.target_role_title} and Computer Information Systems graduate (4.1 GPA) with hands-on systems, networking, "
                f"and cloud infrastructure experience. Demonstrated expertise in {primary_tech}, with a focus on high throughput, zero-downtime reliability, "
                "and automated operational workflows. Adept at aligning technical architecture with business demands while maintaining rigorous operational standards."
            )

        # 2. Reorganize Technical Skills based on JD relevance
        original_skills = master_parsed.get("skills", [])
        tuned_categories: List[SkillCategory] = []
        for cat in original_skills:
            cat_name = cat["category"]
            skills_list = cat["skills"]
            sorted_skills = sorted(skills_list, key=lambda s: 0 if s.lower() in jd_lower else 1)
            tuned_categories.append(SkillCategory(
                category_name=cat_name,
                skills=sorted_skills
            ))

        # 3. Tune Experience Bullets (Preserve all employers, titles, dates, metrics)
        # Reverse-chronological order: Apr 2026 above Feb 2023
        # Remove floating periods, remove leftover AI text, replace defensive CMMS phrasing
        # Embed mechanical assets into GuardTeck rounds
        tuned_experiences: List[TunedExperience] = []
        for exp in master_parsed.get("experiences", []):
            tuned_bullets = []
            for b in exp["bullets"]:
                polished = b.strip()
                if not polished or polished == ".":
                    continue
                # Remove leftover AI text
                polished = polished.replace("directly analogous to AI adoption facilitation with business stakeholders", "").strip()
                # Replace defensive notes with active enterprise CMMS phrasing
                polished = re.sub(
                    r'\(directly transferable to Angus and WPM Plus\)',
                    'utilizing enterprise CMMS workflows equivalent to MRI Angus and WPM Plus',
                    polished,
                    flags=re.I
                )
                if "GuardTeck" in exp.get("company", ""):
                    # Move specific equipment terms (chillers, cooling towers, AHUs, boilers, pumps) directly into daily rounds
                    if "daily building rounds" in polished.lower() and "chillers" not in polished.lower():
                        polished = (
                            "Conducted daily building rounds and mechanical room inspections across commercial properties, "
                            "inspecting and logging operating parameters for chillers, cooling towers, AHUs, boilers, and pumps "
                            "while monitoring building exteriors, envelopes, and grounds."
                        )
                tuned_bullets.append(polished)
                
            tuned_experiences.append(TunedExperience(
                company=exp["company"],
                title=exp["title"],
                date_range=exp["date_range"],
                location=exp["location"],
                bullets=tuned_bullets
            ))

        # Enforce reverse-chronological order (Apr 2026 - Present above Feb 2023 - Present)
        def exp_order(e: TunedExperience):
            dr = e.date_range.lower()
            if "2026" in dr:
                return 0
            elif "2023" in dr:
                return 1
            return 2

        tuned_experiences.sort(key=exp_order)

        # 4. Build Projects: Slot 1
        p1 = projects_by_id.get(stage1_result.slot1_project_id, projects[0] if projects else None)
        slot1_title = p1.title if p1 else "Key Operations Project"
        slot1_bullets = []
        if p1 and p1.full_markdown:
            for line in p1.full_markdown.splitlines():
                line_s = line.strip()
                if line_s.startswith("- ") or line_s.startswith("* "):
                    cleaned = line_s[2:].strip()
                    cleaned = cleaned.replace("directly analogous to AI adoption facilitation with business stakeholders", "").strip()
                    if cleaned and cleaned != ".":
                        slot1_bullets.append(cleaned)
        if not slot1_bullets:
            slot1_bullets = [
                "Streamlined incident logging, preventative maintenance schedules, and computerized building control metrics.",
                "Standardized maintenance workflows and compliance reporting in full alignment with enterprise standards."
            ]

        # Slot 2 (Existing or Proposed)
        if stage1_result.slot2_is_proposed:
            slot2_title = f"{stage1_result.slot2_proposed_title} (Under Development)"
            tech_str = ", ".join(stage1_result.slot2_proposed_technologies or ["Python", "Docker"])
            slot2_bullets = [
                f"Scoped 1-2 day targeted implementation addressing specific operational requirements using {tech_str}.",
                f"Architecture: {stage1_result.slot2_proposed_plan}",
                "Deliverables: Functional module with comprehensive test suite, operational documentation, and clean workflow integration."
            ]
            slot2_is_proposed = True
        else:
            p2 = projects_by_id.get(stage1_result.slot2_project_id, projects[1] if len(projects) > 1 else projects[0])
            slot2_title = p2.title if p2 else "Complementary Systems Project"
            slot2_bullets = []
            if p2 and p2.full_markdown:
                for line in p2.full_markdown.splitlines():
                    line_s = line.strip()
                    if line_s.startswith("- ") or line_s.startswith("* "):
                        cleaned = line_s[2:].strip()
                        cleaned = cleaned.replace("directly analogous to AI adoption facilitation with business stakeholders", "").strip()
                        if cleaned and cleaned != ".":
                            slot2_bullets.append(cleaned)
            slot2_is_proposed = False

        return Stage2CustomizationResult(
            tailored_summary=tailored_summary,
            skill_categories=tuned_categories,
            experiences=tuned_experiences,
            slot1_title=slot1_title,
            slot1_bullets=slot1_bullets,
            slot2_title=slot2_title,
            slot2_bullets=slot2_bullets,
            slot2_is_proposed=slot2_is_proposed
        )

    def generate_cover_letter(
        self,
        job_description: str,
        resume_markdown: str,
        additional_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        from datetime import datetime
        current_date = datetime.now().strftime("%B %d, %Y")

        comp_match = re.search(r'(?:Company|Client|Employer|Organization):\s*([^\n\r,]+)', job_description, re.IGNORECASE)
        target_company = comp_match.group(1).strip() if comp_match else "Hiring Team"

        role_match = re.search(r'(?:Title|Position|Role):\s*([^\n\r]+)', job_description, re.IGNORECASE)
        if not role_match:
            role_match = re.search(r'([A-Za-z\s/&-]+(?:Coordinator|Specialist|Manager|Supervisor|Engineer|Operator))', job_description)
        target_role = role_match.group(1).strip() if role_match else "Commercial Facilities Operations Coordinator"

        jd_lower = job_description.lower()
        is_facilities = any(k in jd_lower for k in ["facility", "facilities", "building", "hvac", "bms", "bas", "maintenance", "operations", "property"])

        if is_facilities:
            body_p1 = (
                f"When I saw the opening for the {target_role} role at {target_company}, I knew immediately this was the "
                "challenge I have been preparing for. I recently completed my Computer Information Systems degree at the University of the Fraser Valley "
                "with a 4.1 GPA and consecutive Dean's List honors - not by staying in a classroom bubble, but by pairing rigorous systems coursework "
                "with over three years of boots-on-the-ground operational supervision across high-traffic commercial properties."
            )
            body_p2 = (
                f"Your posting emphasizes proactive building control systems (BAS/BMS), preventative maintenance scheduling, and trade contractor dispatch. "
                "That is not abstract theory to me. As an Acting Assistant Manager and Security Supervisor, I've conducted hands-on daily rounds through mechanical rooms, "
                "monitored pumps, boilers, and air handlers, dispatched trade contractors via computerized work order platforms (Angus, WPM Plus), and managed life-safety "
                "escalations under real-world pressure. Holding an OFA Level 1 certification, clean BC Driver's License, and reliable personal vehicle, I'm ready to roll up "
                "my sleeves on site on day one."
            )
            body_p3 = (
                "Here is why hiring me gives you an unfair advantage: I bring the relentless energy, hunger, and zero bad habits of a fresh graduate who feels lucky "
                "every single day to do this work, combined with a technical mindset that actively automates diagnostics, daily maintenance logs, and dispatch workflows. "
                "I don't wait around to be told what to do - I inspect the issue, coordinate the right trades, and ensure tenant satisfaction and OH&S standards are met."
            )
            body_p4 = (
                f"I don't expect anything handed to me; I want the opportunity to prove my work ethic on your hardest shifts. I would welcome 15 minutes to discuss how my "
                f"dedication, technical background, and operational reliability will deliver immediate value to {target_company}."
            )
        else:
            body_p1 = (
                f"When I saw the opening for the {target_role} position at {target_company}, I knew I had to put my name forward. "
                "I am a recent Computer Information Systems graduate (4.1 GPA, 4-time consecutive Dean's List honoree) with a deep hunger to build, "
                "learn, and outwork expectations. I am not looking for a comfortable 9-to-5 - I am looking for a high-standard engineering environment where "
                "I can absorb your architecture like a sponge and contribute reliable, high-quality work immediately."
            )
            body_p2 = (
                f"Your team needs someone who understands modern backend systems and distributed architecture. Through intensive coursework, remote IT infrastructure "
                "coordination, and hands-on systems development, I have engineered scalable services using Python, Docker, relational databases, and automated monitoring. "
                "I take immense pride in writing clean, well-tested code and understanding the underlying operating system and networking protocols."
            )
            body_p3 = (
                "My greatest asset is velocity combined with coachability. Coming straight out of university, I bring zero complacency, relentless curiosity, "
                "and an obsessive commitment to problem-solving. Whether it is tracing tricky latency bottlenecks, debugging production services, or automating "
                "repetitive operational tasks, I stay until the problem is solved and thoroughly documented."
            )
            body_p4 = (
                f"I am ready to work hard and earn my place on your team. I would love the chance to speak with you for 15 minutes to discuss how my drive, "
                f"technical aptitude, and work ethic will make an immediate impact at {target_company}."
            )

        cover_letter_md = f"""# Manbir Singh Sidhu
Surrey, BC | +1 778-956-1186 | manbirs285@gmail.com | [LinkedIn](https://www.linkedin.com/in/manbir-singh-sidhu/) | [GitHub](https://github.com/SidhuManbirSingh/SidhuManbirSingh/)

{current_date}

Hiring Team
{target_company}

RE: Application for {target_role}

Dear Hiring Team,

{body_p1}

{body_p2}

{body_p3}

{body_p4}

Sincerely,

Manbir Singh Sidhu"""

        return {
            "cover_letter_markdown": cover_letter_md.strip(),
            "target_role_title": target_role,
            "target_company": target_company
        }

    def generate_outreach(
        self,
        job_description: str,
        resume_markdown: str,
        additional_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        comp_match = re.search(r'(?:Company|Client|Employer|Organization):\s*([^\n\r,]+)', job_description, re.IGNORECASE)
        target_company = comp_match.group(1).strip() if comp_match else "your team"

        role_match = re.search(r'(?:Title|Position|Role):\s*([^\n\r]+)', job_description, re.IGNORECASE)
        if not role_match:
            role_match = re.search(r'([A-Za-z\s/&-]+(?:Coordinator|Specialist|Manager|Supervisor|Engineer|Operator))', job_description)
        target_role = role_match.group(1).strip() if role_match else "Commercial Facilities Operations Coordinator"

        jd_lower = job_description.lower()
        is_facilities = any(k in jd_lower for k in ["facility", "facilities", "building", "hvac", "bms", "bas", "maintenance", "operations", "property"])

        if is_facilities:
            linkedin_message = (
                f"Hi Hiring Team,\n\n"
                f"I came across the {target_role} opening at {target_company} and wanted to reach out directly. "
                f"I recently graduated with a Computer Information Systems degree (4.1 GPA, 4-time Dean's List), "
                f"pairing technical systems knowledge with 3+ years of boots-on-the-ground commercial facility operations—including "
                f"mechanical room inspections (pumps, boilers, HVAC), BMS/BAS monitoring, trade contractor dispatch (Angus/WPM), "
                f"and life-safety protocols.\n\n"
                f"I hold an OFA Level 1 certification, clean BC driver's license, and reliable vehicle. Coming straight out of college, "
                f"I bring relentless energy, zero bad habits, and genuine excitement to roll up my sleeves on site.\n\n"
                f"Would you be open to connecting or having a brief 5-minute chat?\n\n"
                f"Best regards,\nManbir Singh Sidhu\n+1 778-956-1186 | https://www.linkedin.com/in/manbir-singh-sidhu/ | https://github.com/SidhuManbirSingh/SidhuManbirSingh/"
            )

            email_subject = f"Application: {target_role} - Manbir Singh Sidhu (4.1 GPA | 3+ Yrs Commercial Operations)"
            email_body = (
                f"Dear {target_company} Hiring Team,\n\n"
                f"I am writing to express my strong interest in the {target_role} position at {target_company}. "
                f"I recently completed my Computer Information Systems degree at the University of the Fraser Valley with a 4.1 GPA "
                f"(consecutive Dean's List honors). Rather than remaining in a classroom bubble, I spent the last three years in the field "
                f"as an Acting Assistant Manager and Security Supervisor across high-traffic commercial real estate properties.\n\n"
                f"Your posting highlights proactive building control systems (BAS/BMS), preventative maintenance scheduling, and trade dispatch. "
                f"In my daily operational rounds, I actively monitored mechanical rooms (boilers, pumps, air handlers), coordinated emergency and scheduled "
                f"trade repairs via computerized work order systems (Angus, WPM Plus), and enforced life-safety and OH&S standards under real-world conditions. "
                f"With an OFA-1 first aid certification, a clean BC Driver's License, and a reliable personal vehicle, I am ready to step onto your site and "
                f"deliver immediate reliability from day one.\n\n"
                f"What sets me apart is a blend of relentless work ethic and technical grit: I bring the coachability, hunger, and drive of a fresh graduate "
                f"who feels lucky every single day to tackle challenging operational problems, backed by the technical capability to automate maintenance logs "
                f"and streamline contractor workflows. I would welcome the opportunity to speak with you for 10-15 minutes to discuss how my hands-on "
                f"dedication can support {target_company}.\n\n"
                f"Sincerely,\n\n"
                f"Manbir Singh Sidhu\n"
                f"Surrey, BC | +1 778-956-1186\n"
                f"manbirs285@gmail.com\n"
                f"LinkedIn: https://www.linkedin.com/in/manbir-singh-sidhu/\n"
                f"GitHub: https://github.com/SidhuManbirSingh/SidhuManbirSingh/"
            )
        else:
            linkedin_message = (
                f"Hi Hiring Team,\n\n"
                f"I noticed the {target_role} opening at {target_company} and wanted to reach out. "
                f"I am a recent Computer Information Systems graduate (4.1 GPA, 4-time consecutive Dean's List) "
                f"with hands-on experience building resilient cloud services and distributed backends using Python, Docker, "
                f"relational databases, and automated infrastructure monitoring.\n\n"
                f"Straight out of college, I am hungry to learn, coachable, and eager to outwork expectations. "
                f"I take immense pride in writing clean, well-tested code and resolving tough operational challenges.\n\n"
                f"Would you be open to connecting or a quick 5-minute introductory call?\n\n"
                f"Best regards,\nManbir Singh Sidhu\n+1 778-956-1186 | https://www.linkedin.com/in/manbir-singh-sidhu/ | https://github.com/SidhuManbirSingh/SidhuManbirSingh/"
            )

            email_subject = f"Application: {target_role} - Manbir Singh Sidhu (4.1 GPA | CIS Graduate)"
            email_body = (
                f"Dear {target_company} Hiring Team,\n\n"
                f"I am writing to express my strong enthusiasm for the {target_role} opportunity at {target_company}. "
                f"I recently graduated with a Bachelor's in Computer Information Systems (Systems & Networking) from the University of the "
                f"Fraser Valley, maintaining a 4.1 GPA and 4 consecutive Dean's List awards.\n\n"
                f"My focus has been building reliable backend systems, containerized services (Docker, Python), and cloud infrastructure. "
                f"I have practical experience coordinating remote systems, diagnosing network latency bottlenecks, and automating operational "
                f"deployments with high precision and test coverage.\n\n"
                f"Coming straight out of university, I bring zero complacency, relentless curiosity, and an obsessive commitment to learning and delivering value. "
                f"I would appreciate 10-15 minutes of your time to discuss how my energy, technical foundation, and work ethic will make an immediate contribution at {target_company}.\n\n"
                f"Sincerely,\n\n"
                f"Manbir Singh Sidhu\n"
                f"Surrey, BC | +1 778-956-1186\n"
                f"manbirs285@gmail.com\n"
                f"LinkedIn: https://www.linkedin.com/in/manbir-singh-sidhu/\n"
                f"GitHub: https://github.com/SidhuManbirSingh/SidhuManbirSingh/"
            )

        return {
            "linkedin_message": linkedin_message.strip(),
            "email_subject": email_subject.strip(),
            "email_body": email_body.strip(),
            "target_role_title": target_role,
            "target_company": target_company
        }


class AnthropicLLMClient(BaseLLMClient):
    """
    Production client connecting to Anthropic Claude 3.5 Sonnet.
    Uses structured system instructions and JSON mode.
    """
    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.anthropic.com/v1/messages"

    def _call_claude(self, system_prompt: str, user_prompt: str) -> str:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": self.model,
            "max_tokens": 4000,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2
        }
        response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
        if response.status_code != 200:
            raise RuntimeError(f"Anthropic API Error ({response.status_code}): {response.text}")
        data = response.json()
        return data["content"][0]["text"]

    def analyze_and_select(
        self,
        job_description: str,
        master_parsed: Dict[str, Any],
        projects: List[ProjectMetadata]
    ) -> Stage1AnalysisResult:
        system_prompt, user_prompt = _build_stage1_prompts(job_description, master_parsed, projects)
        raw_response = self._call_claude(system_prompt, user_prompt)
        json_clean = _extract_json(raw_response)
        return Stage1AnalysisResult.model_validate(json.loads(json_clean))

    def customize_sections(
        self,
        job_description: str,
        master_parsed: Dict[str, Any],
        stage1_result: Stage1AnalysisResult,
        projects: List[ProjectMetadata]
    ) -> Stage2CustomizationResult:
        system_prompt, user_prompt = _build_stage2_prompts(job_description, master_parsed, stage1_result, projects)
        raw_response = self._call_claude(system_prompt, user_prompt)
        json_clean = _extract_json(raw_response)
        return Stage2CustomizationResult.model_validate(json.loads(json_clean))

    def generate_cover_letter(
        self,
        job_description: str,
        resume_markdown: str,
        additional_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        system_prompt, user_prompt = _build_cover_letter_prompts(job_description, resume_markdown, additional_notes)
        raw_response = self._call_claude(system_prompt, user_prompt)
        json_clean = _extract_json(raw_response)
        data = json.loads(json_clean)
        return {
            "cover_letter_markdown": data.get("cover_letter_markdown", "").strip(),
            "target_role_title": data.get("target_role_title", "Candidate"),
            "target_company": data.get("target_company")
        }

    def generate_outreach(
        self,
        job_description: str,
        resume_markdown: str,
        additional_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        system_prompt, user_prompt = _build_outreach_prompts(job_description, resume_markdown, additional_notes)
        raw_response = self._call_claude(system_prompt, user_prompt)
        json_clean = _extract_json(raw_response)
        data = json.loads(json_clean)
        return {
            "linkedin_message": data.get("linkedin_message", "").strip(),
            "email_subject": data.get("email_subject", "").strip(),
            "email_body": data.get("email_body", "").strip(),
            "target_role_title": data.get("target_role_title", "Candidate"),
            "target_company": data.get("target_company")
        }


class OpenAILLMClient(BaseLLMClient):
    """
    Production client connecting to OpenAI GPT-4o.
    Uses json_object response format.
    """
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.openai.com/v1/chat/completions"

    def _call_openai(self, system_prompt: str, user_prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.2
        }
        response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
        if response.status_code != 200:
            raise RuntimeError(f"OpenAI API Error ({response.status_code}): {response.text}")
        data = response.json()
        return data["choices"][0]["message"]["content"]

    def analyze_and_select(
        self,
        job_description: str,
        master_parsed: Dict[str, Any],
        projects: List[ProjectMetadata]
    ) -> Stage1AnalysisResult:
        system_prompt, user_prompt = _build_stage1_prompts(job_description, master_parsed, projects)
        raw_response = self._call_openai(system_prompt, user_prompt)
        json_clean = _extract_json(raw_response)
        return Stage1AnalysisResult.model_validate(json.loads(json_clean))

    def customize_sections(
        self,
        job_description: str,
        master_parsed: Dict[str, Any],
        stage1_result: Stage1AnalysisResult,
        projects: List[ProjectMetadata]
    ) -> Stage2CustomizationResult:
        system_prompt, user_prompt = _build_stage2_prompts(job_description, master_parsed, stage1_result, projects)
        raw_response = self._call_openai(system_prompt, user_prompt)
        json_clean = _extract_json(raw_response)
        return Stage2CustomizationResult.model_validate(json.loads(json_clean))

    def generate_cover_letter(
        self,
        job_description: str,
        resume_markdown: str,
        additional_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        system_prompt, user_prompt = _build_cover_letter_prompts(job_description, resume_markdown, additional_notes)
        raw_response = self._call_openai(system_prompt, user_prompt)
        data = json.loads(raw_response)
        return {
            "cover_letter_markdown": data.get("cover_letter_markdown", "").strip(),
            "target_role_title": data.get("target_role_title", "Candidate"),
            "target_company": data.get("target_company")
        }

    def generate_outreach(
        self,
        job_description: str,
        resume_markdown: str,
        additional_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        system_prompt, user_prompt = _build_outreach_prompts(job_description, resume_markdown, additional_notes)
        raw_response = self._call_openai(system_prompt, user_prompt)
        data = json.loads(raw_response)
        return {
            "linkedin_message": data.get("linkedin_message", "").strip(),
            "email_subject": data.get("email_subject", "").strip(),
            "email_body": data.get("email_body", "").strip(),
            "target_role_title": data.get("target_role_title", "Candidate"),
            "target_company": data.get("target_company")
        }


class GeminiLLMClient(BaseLLMClient):
    """
    Production client connecting to Google Gemini API (gemini-2.5-flash).
    Uses REST generateContent with native response_mime_type: application/json.
    """
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        clean_model = model.replace("models/", "")
        self.model = clean_model
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    def _call_gemini(self, system_instruction: str, user_prompt: str) -> str:
        headers = {
            "Content-Type": "application/json"
        }
        params = {
            "key": self.api_key
        }
        payload = {
            "system_instruction": {
                "parts": [{"text": system_instruction}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2
            }
        }
        
        response = requests.post(self.api_url, headers=headers, params=params, json=payload, timeout=60)
        if response.status_code != 200:
            raise RuntimeError(f"Gemini API Error ({response.status_code}): {response.text}")
        data = response.json()
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError(f"Gemini returned no candidates: {data}")
            return candidates[0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected Gemini response structure: {data} (Error: {e})")

    def analyze_and_select(
        self,
        job_description: str,
        master_parsed: Dict[str, Any],
        projects: List[ProjectMetadata]
    ) -> Stage1AnalysisResult:
        system_prompt, user_prompt = _build_stage1_prompts(job_description, master_parsed, projects)
        raw_response = self._call_gemini(system_prompt, user_prompt)
        json_clean = _extract_json(raw_response)
        return Stage1AnalysisResult.model_validate(json.loads(json_clean))

    def customize_sections(
        self,
        job_description: str,
        master_parsed: Dict[str, Any],
        stage1_result: Stage1AnalysisResult,
        projects: List[ProjectMetadata]
    ) -> Stage2CustomizationResult:
        system_prompt, user_prompt = _build_stage2_prompts(job_description, master_parsed, stage1_result, projects)
        raw_response = self._call_gemini(system_prompt, user_prompt)
        json_clean = _extract_json(raw_response)
        data = json.loads(json_clean)
        return Stage2CustomizationResult.model_validate(data)

    def generate_cover_letter(
        self,
        job_description: str,
        resume_markdown: str,
        additional_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        system_prompt, user_prompt = _build_cover_letter_prompts(job_description, resume_markdown, additional_notes)
        raw_response = self._call_gemini(system_prompt, user_prompt)
        json_clean = _extract_json(raw_response)
        data = json.loads(json_clean)
        return {
            "cover_letter_markdown": data.get("cover_letter_markdown", "").strip(),
            "target_role_title": data.get("target_role_title", "Candidate"),
            "target_company": data.get("target_company")
        }

    def generate_outreach(
        self,
        job_description: str,
        resume_markdown: str,
        additional_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        system_prompt, user_prompt = _build_outreach_prompts(job_description, resume_markdown, additional_notes)
        raw_response = self._call_gemini(system_prompt, user_prompt)
        json_clean = _extract_json(raw_response)
        data = json.loads(json_clean)
        return {
            "linkedin_message": data.get("linkedin_message", "").strip(),
            "email_subject": data.get("email_subject", "").strip(),
            "email_body": data.get("email_body", "").strip(),
            "target_role_title": data.get("target_role_title", "Candidate"),
            "target_company": data.get("target_company")
        }


def _build_stage1_prompts(
    job_description: str,
    master_parsed: Dict[str, Any],
    projects: List[ProjectMetadata]
) -> Tuple[str, str]:
    projects_summary = [
        {
            "id": p.id,
            "title": p.title,
            "technologies": p.technologies,
            "domain": p.domain,
            "summary": p.summary,
            "metrics": p.metrics
        }
        for p in projects
    ]

    system_prompt = (
        "You are an expert technical resume architect and ATS optimization specialist. Your task is to analyze a target job description, "
        "evaluate the candidate's master profile and verified project catalog, extract the exact target job title matching the requisition, "
        "select the best existing project for Slot 1, and determine whether Slot 2 should be an existing project or a targeted 1-2 day complementary project.\n\n"
        "MANDATORY ATS ANALYSIS DIRECTIVES:\n"
        "1. EXACT TARGET ROLE TITLE: Extract the exact requisition title (e.g. 'Building Operations Coordinator & Assistant Facility Manager', 'Building Operator', 'Facilities Operations Coordinator', or 'Senior Backend Engineer'). Avoid vague or generic titles.\n"
        "2. TARGET COMPANY: Extract employer or client company name if specified in the JD, otherwise null.\n"
        "3. TECHNICAL & OPERATIONAL REQUIREMENTS: Extract core technical keywords, certifications, building mechanical systems (chillers, boilers, pumps, AHUs, cooling towers), work order platforms (MRI Angus, WPM Plus), or software stacks demanded by the posting.\n"
        "4. PROJECT SELECTION: Select the highest-impact existing project for Slot 1 from the catalog. For Slot 2, decide whether existing projects cover the JD or if a realistic 1-2 day complementary project should be proposed.\n"
        "CRITICAL: Output ONLY valid, raw JSON matching the requested schema. No markdown formatting, no commentary."
    )

    user_prompt = f"""Analyze the following Job Description against the Candidate's Master Profile and Project Catalog.

<job_description>
{job_description}
</job_description>

<candidate_profile>
Name: {master_parsed.get('name')}
Current Summary: {master_parsed.get('summary')}
Current Skills: {master_parsed.get('skills_raw')}
</candidate_profile>

<project_catalog>
{json.dumps(projects_summary, indent=2)}
</project_catalog>

Respond with a JSON object with this exact structure:
{{
  "target_role_title": "string (exact target job title from posting, e.g. Building Operations Coordinator & Assistant Facility Manager)",
  "target_company": "string or null (target employer/company name if stated in JD, otherwise null)",
  "key_technical_requirements": ["string", "string"],
  "key_responsibilities": ["string", "string"],
  "slot1_project_id": "string (matching one of the catalog ids)",
  "slot1_rationale": "string explanation",
  "slot2_is_proposed": true/false (true if a key required technology/skill is missing from existing projects and can be prototyped in 1-2 days, false if existing projects cover requirements),
  "slot2_project_id": "string or null",
  "slot2_rationale": "string explanation",
  "slot2_proposed_title": "string or null",
  "slot2_proposed_technologies": ["string"] or null,
  "slot2_proposed_plan": "string or null (clear 1-2 day scope, tech stack, deliverables)"
}}
"""
    return system_prompt, user_prompt


def _build_stage2_prompts(
    job_description: str,
    master_parsed: Dict[str, Any],
    stage1_result: Stage1AnalysisResult,
    projects: List[ProjectMetadata]
) -> Tuple[str, str]:
    projects_by_id = {p.id: p for p in projects}
    p1 = projects_by_id.get(stage1_result.slot1_project_id, projects[0] if projects else None)
    p1_markdown = p1.full_markdown if p1 else ""
    master_experiences = master_parsed.get('experiences', [])

    system_prompt = (
        "You are an elite ATS resume customizer and career architect. You tailor a candidate's resume to match a target job description "
        "with maximum ATS keyword alignment, clean parsing, and compelling hiring manager impact, while strictly preserving core factual invariance.\n\n"
        "MANDATORY ATS OPTIMIZATION & TAILORING DIRECTIVES:\n\n"
        "1. FIX THE SUMMARY TYPO AND ADD THE EXACT TARGET JOB TITLE:\n"
        f"   - Replace generic phrases like 'Results-driven technology and professional' or 'Results-driven professional' with the exact job title from the posting: '{stage1_result.target_role_title}'. The resume summary headline must open directly with this exact role title so ATS matches the candidate's headline directly to the requisition.\n"
        "   - Frame the candidate primarily under the target discipline (Facilities Management / Commercial Property Operations for facilities roles, Systems / Software Engineering for technical roles).\n"
        "   - Keep 'Security Supervisor' secondary in the summary (e.g., 'paired with leadership as an Acting Assistant Manager and Security Supervisor') so the parser categorizes the candidate's primary profile under Facilities Management / Operations rather than Protective Services or Security Guard.\n\n"
        "2. RENAME NON-STANDARD SECTION HEADERS AND CLEAN BROKEN ARTIFACTS:\n"
        "   - Standardize all section headers to standard ATS-recognized headers (e.g., 'RELEVANT OPERATIONS PROJECTS' instead of non-standard headings like 'OPERATIONS WORKFLOW, COMPLIANCE & COST TRACKING').\n"
        "   - Remove any floating periods ('.') that appear on blank lines above bullets or dates, which are broken bullet artifacts from PDF conversion.\n\n"
        "3. REMOVE LEFTOVER AI TEXT AND DEFENSIVE KEYWORD NOTES:\n"
        "   - Delete any copy-paste leftover phrases such as 'directly analogous to AI adoption facilitation with business stakeholders'.\n"
        "   - NEVER use defensive or apologetic notes like '(directly transferable to Angus and WPM Plus)'. Instead, change to confident, direct enterprise phrasing: 'utilizing enterprise CMMS workflows equivalent to MRI Angus and WPM Plus' for cleaner keyword indexing.\n\n"
        "4. ADD MISSING HANDS-ON MAINTENANCE & BC CERTIFICATION KEYWORDS:\n"
        "   - Standard Building Operator JDs scan for hands-on repair keywords: ensure bullets and skills explicitly feature minor plumbing repairs, lamp/ballast replacement, filter and belt changes, drywall/painting touch-ups, and groundskeeping.\n"
        "   - Explicitly weave in industry tickets and credentials: 5th Class Power Engineering (in progress / eligible), BOMA courses / coursework, Occupational First Aid (OFA Level 1), valid BC Driver's License and reliable vehicle.\n\n"
        "5. CORRECT REVERSE-CHRONOLOGICAL ORDER AND EMBED SYSTEM KEYWORDS IN WORK HISTORY:\n"
        "   - The 'experiences' array MUST contain all original employment records from the master resume verbatim (company, title, date_range, location). Do not add or remove employers.\n"
        "   - In Professional Experience, maintain strict reverse-chronological order: list Apr 2026 – Present ('Information Technology Coordinator (Part-Time / Contract)') above Feb 2023 – Present ('Security Supervisor, Acting Assistant Manager'). Clarify the remote IT role is (Part-Time / Contract) so the ATS timeline parser does not flag a chronological error or full-time availability conflict.\n"
        "   - In the GuardTeck daily building round bullets, move specific equipment terms (chillers, cooling towers, AHUs, boilers, pumps) directly into the bullets so the ATS scores 3+ years of hands-on experience with those assets.\n\n"
        "6. STRICT FACTUAL INVARIANCE & HYPERLINKS:\n"
        "   - NEVER fabricate company names, dates, or degrees.\n"
        "   - DO NOT include raw GitHub or LinkedIn links in summary, skills, experience, or project bullets (contact line handles links).\n"
        "   - If Slot 2 is proposed, label its title with '(Under Development)' and do not present it as completed.\n\n"
        "CRITICAL: Output ONLY strictly valid, raw JSON matching the schema."
    )

    user_prompt = f"""Job Description:
<job_description>
{job_description}
</job_description>

Stage 1 Analysis:
{stage1_result.model_dump_json(indent=2)}

Original Master Resume Data:
- Name: {master_parsed.get('name')}
- Current Summary: {master_parsed.get('summary')}
- Current Skills: {json.dumps(master_parsed.get('skills'))}
- Experiences: {json.dumps(master_experiences)}

Slot 1 Selected Existing Project Details:
{p1_markdown}

Respond with a JSON object matching this schema:
{{
  "tailored_summary": "3-4 sentence professional summary opening with '{stage1_result.target_role_title}', keeping Security Supervisor secondary, and highlighting relevant competencies",
  "skill_categories": [
    {{
      "category_name": "string",
      "skills": ["string"]
    }}
  ],
  "experiences": [
    {{
      "company": "must match master exactly",
      "title": "must match master exactly",
      "date_range": "must match master exactly",
      "location": "must match master exactly",
      "bullets": ["tuned bullet embedding equipment/maintenance keywords and active CMMS phrasing"]
    }}
  ],
  "slot1_title": "{p1.title if p1 else 'Project'}",
  "slot1_technologies": {json.dumps(p1.technologies if p1 else [])},
  "slot1_bullets": ["bullet emphasizing JD-relevant aspects of this existing project without leftover AI text"],
  "slot2_title": "Project Title",
  "slot2_technologies": ["string"],
  "slot2_bullets": ["bullet without leftover AI text"],
  "slot2_is_proposed": {str(stage1_result.slot2_is_proposed).lower()}
}}
"""
    return system_prompt, user_prompt


def _build_cover_letter_prompts(job_description: str, resume_markdown: str, additional_notes: Optional[str] = None):
    from datetime import datetime
    current_date = datetime.now().strftime("%B %d, %Y")

    system_prompt = (
        "You are an elite career strategist and executive copywriter creating a compelling, irresistible, high-conversion cover letter. "
        "The candidate is Manbir Singh Sidhu, a recent Computer Information Systems graduate (Systems & Networking, 4.1 / 4.3 GPA, 4-time consecutive Dean's List) "
        "who also possesses over three years of real-world operational and technical experience:\n"
        "- Security Supervisor & Acting Assistant Manager across commercial properties: mechanical room rounds, boilers, pumps, chillers, AHUs, BMS/BAS operations, "
        "computerized work orders (Angus, WPM Plus), trade contractor coordination, tenant operations, emergency on-call response, life safety panels, and OH&S compliance.\n"
        "- IT Coordinator: cloud servers, remote systems deployment, Active Directory, Azure, VPN, endpoint security, automation scripts.\n"
        "- Certifications: OFA Level 1, clean BC Driver's License, reliable personal vehicle.\n\n"
        "MANDATORY TONE & PERSONA DIRECTIVES:\n"
        "1. Mindset: 'Think that I just came straight out of college. I'm eager to learn. I'm lucky, ready to work hard. "
        "Make a cover letter that is very catchy. If someone reads this, they say: I need to hire this guy.'\n"
        "2. Voice: Energetic, hungry, humble yet deeply confident, grounded in practical grit, proactive reliability, and rapid learning ability.\n"
        "3. Zero fluff: DO NOT use cliché robotic openings like 'I am writing to express my interest in...' or 'I believe I am the ideal candidate'.\n"
        "4. Hook the reader immediately: Open with memorable passion, academic excellence (4.1 GPA), and real-world operational experience.\n"
        "5. Target alignment: Directly address the core responsibilities and technologies mentioned in the job description.\n"
        "6. Frame being a fresh graduate as a massive competitive advantage: zero bad habits, coachable sponge, unshakeable work ethic, eager to tackle tough shifts and solve stubborn problems.\n"
        "7. Call to Action: Direct, respectful, confident closing requesting a brief 15-minute conversation.\n"
        "8. Output strictly valid JSON matching the requested schema."
    )

    user_prompt = f"""Target Job Description:
<job_description>
{job_description}
</job_description>

Candidate's Background & Tailored Resume:
<resume>
{resume_markdown}
</resume>

Additional Candidate Notes:
{additional_notes or "Emphasize eager learning, relentless work ethic, rapid adaptability, and hands-on operational grit."}

Current Date: {current_date}

Respond with a JSON object matching this schema:
{{
  "target_company": "string (company name from JD, or 'Hiring Team')",
  "target_role_title": "string (role title from JD)",
  "cover_letter_markdown": "string (full Markdown of the cover letter. Must begin with '# Manbir Singh Sidhu', followed by contact line with [LinkedIn](https://www.linkedin.com/in/manbir-singh-sidhu/) | [GitHub](https://github.com/SidhuManbirSingh/SidhuManbirSingh/), current date, recipient address block, 'RE: Application for [Role]', salutation, 3-4 structured punchy paragraphs, and 'Sincerely,\\n\\nManbir Singh Sidhu')"
}}
"""
    return system_prompt, user_prompt


def _build_outreach_prompts(job_description: str, resume_markdown: str, additional_notes: Optional[str] = None):
    system_prompt = (
        "You are an elite career strategist, recruiting insider, and high-conversion copywriter. "
        "Your task is to write TWO customized outreach messages for the candidate to shoot directly to hiring teams, "
        "recruiters, or managers:\n"
        "1. A punchy LinkedIn InMail / Direct Message (around 100-150 words) with low-friction call-to-action.\n"
        "2. A direct Cold Email application with a compelling high-open-rate subject line and concise 3-paragraph body.\n\n"
        "CANDIDATE PERSONA & FACTS (STRICT FACTUAL INVARIANCE):\n"
        "- Candidate: Manbir Singh Sidhu\n"
        "- Education: Computer Information Systems (Systems & Networking) at University of the Fraser Valley, 4.1 / 4.3 GPA, 4-time consecutive Dean's List.\n"
        "- Real-world Experience: Over 3 years in commercial property & building operations (Acting Assistant Manager & Security Supervisor) handling mechanical room rounds, boilers, chillers, pumps, BMS/BAS monitoring, computerized work orders (Angus, WPM Plus), trade contractor dispatch, emergency escalation, and life safety/OH&S compliance.\n"
        "- Technical IT experience: Azure, Active Directory, cloud systems deployment, script automation.\n"
        "- Credentials: OFA Level 1, clean BC Driver's License, reliable personal vehicle.\n"
        "- Contact: Surrey, BC | +1 778-956-1186 | manbirs285@gmail.com | https://www.linkedin.com/in/manbir-singh-sidhu/ | https://github.com/SidhuManbirSingh/SidhuManbirSingh/\n\n"
        "MANDATORY TONE DIRECTIVES:\n"
        "- Mindset: 'Think that I just came straight out of college. I'm eager to learn. I'm lucky, ready to work hard. "
        "Make it very catchy. If someone reads this, they say: I need to hire this guy.'\n"
        "- Energetic, humble, hungry, zero bad habits, coachable sponge, unshakeable work ethic.\n"
        "- No robotic corporate jargon like 'I am writing to express my deepest interest...'. Open with punch and immediate proof of dedication.\n"
        "- Output strictly valid JSON matching the requested schema."
    )

    user_prompt = f"""Target Job Description:
<job_description>
{job_description}
</job_description>

Candidate's Resume & Background:
<resume>
{resume_markdown}
</resume>

Additional Candidate Notes:
{additional_notes or "Highlight rapid learning, high energy, humble yet confident attitude, and readiness to work hard on site."}

Respond with a JSON object matching this schema:
{{
  "target_company": "string (company name from JD, or 'Hiring Team')",
  "target_role_title": "string (role title from JD)",
  "linkedin_message": "string (100-150 words punchy LinkedIn message including low-friction CTA and contact signature)",
  "email_subject": "string (high-open-rate email subject line, e.g. 'Application: [Role] - Manbir Singh Sidhu (4.1 GPA | [Highlight])')",
  "email_body": "string (concise 3-paragraph email with salutation, hook, hands-on evidence, humble/hungry closing, and signature block)"
}}
"""
    return system_prompt, user_prompt


def _extract_json(text: str) -> str:
    """
    Safely extracts JSON substring if wrapped in markdown code blocks.
    """
    text = text.strip()
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def get_llm_client() -> BaseLLMClient:
    """
    Factory returning the configured LLM client.
    """
    provider = settings.LLM_PROVIDER
    if provider == "mock":
        return MockLLMClient()
    elif provider == "gemini" and settings.GEMINI_API_KEY:
        return GeminiLLMClient(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL)
    elif provider == "anthropic" and settings.ANTHROPIC_API_KEY:
        return AnthropicLLMClient(api_key=settings.ANTHROPIC_API_KEY, model=settings.ANTHROPIC_MODEL)
    elif provider == "openai" and settings.OPENAI_API_KEY:
        return OpenAILLMClient(api_key=settings.OPENAI_API_KEY, model=settings.OPENAI_MODEL)
    elif settings.GEMINI_API_KEY:
        return GeminiLLMClient(api_key=settings.GEMINI_API_KEY, model=settings.GEMINI_MODEL)
    else:
        # Default fallback to high-fidelity mock engine
        return MockLLMClient()
