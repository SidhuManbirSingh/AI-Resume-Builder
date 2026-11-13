import re
from typing import List, Dict, Any, Optional
from backend.models.schemas import (
    ProjectMetadata,
    Stage1AnalysisResult,
    Stage2CustomizationResult,
    SkillCategory,
    TunedExperience
)
from backend.llm.base import BaseLLMClient, _parse_and_structure_raw_jd


class MockLLMClient(BaseLLMClient):
    """
    High-fidelity deterministic local engine for local development & offline testing.
    Uses the Stage 0 Raw Job Posting Structurer to cleanly parse any copy-pasted job posting
    and tailor the Profile Summary, Skills, and Experience bullets to the exact role family.
    """
    provider_name = "mock"

    def analyze_and_select(
        self,
        job_description: str,
        master_parsed: Dict[str, Any],
        projects: List[ProjectMetadata]
    ) -> Stage1AnalysisResult:
        structured = _parse_and_structure_raw_jd(job_description)
        jd_lower = structured["cleaned_jd_text"].lower()
        target_role = structured["clean_role_title"]
        target_company = structured["target_company"]
        role_family = structured["role_family"]
        found_tech = structured["key_technical_requirements"]
        key_resp = structured["key_responsibilities"]

        # Score and Rank Existing Projects with domain alignment
        scored_projects = []
        for p in projects:
            score = 0
            if role_family in ("facilities", "service_dispatch") and p.domain == "Facilities Operations":
                score += 10
            elif role_family == "software_it" and p.domain != "Facilities Operations":
                score += 5

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

        # Determine Slot 2: Custom JD-Tailored Proposed Project (Under Development)
        proposed_proj = structured.get("proposed_project", {})
        gap_tech = None
        for candidate_gap in ["gRPC", "GraphQL", "Apache Spark", "Rust", "WebSockets"]:
            if candidate_gap.lower() in jd_lower:
                gap_tech = candidate_gap
                break

        slot2_is_proposed = True
        slot2_project_id = None
        if gap_tech:
            slot2_proposed_title = f"High-Throughput {gap_tech} Service & Integration Test Harness (Under Development)"
            slot2_proposed_tech = [gap_tech, "Go", "Docker", "Redis"]
            slot2_proposed_plan = f"Achievable 1-2 day prototype: Implements core {gap_tech} endpoints with schema validation, connection pooling, and automated integration test coverage in Docker."
            slot2_rationale = f"Job description specifically calls for {gap_tech}. Proposing a targeted implementation to demonstrate immediate hands-on capability."
        else:
            slot2_proposed_title = proposed_proj.get("title", "Automated Operations & Dispatch Workflow Tracker (Under Development)")
            slot2_proposed_tech = proposed_proj.get("technologies", ["Python", "SQL", "Power BI"])
            slot2_proposed_plan = proposed_proj.get("plan", "Targeted prototype addressing core job description workflows.")
            slot2_rationale = proposed_proj.get("rationale", "Custom-designed project tailored directly to the target job description.")

        return Stage1AnalysisResult(
            target_role_title=target_role,
            target_company=target_company,
            role_family=role_family,
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
        structured = _parse_and_structure_raw_jd(job_description)
        jd_lower = structured["cleaned_jd_text"].lower()
        role_family = getattr(stage1_result, "role_family", None) or structured["role_family"]
        named_software = structured["named_software"]
        sw_bridge = f"{', '.join(named_software)}, " if named_software else ""

        # 1. Adapt Professional Summary according to role_family
        if role_family == "service_dispatch":
            tailored_summary = (
                f"{stage1_result.target_role_title} with over 3 years of high-volume operations, 24/7 dispatch, and emergency service "
                "coordination experience, paired with leadership as an Acting Assistant Manager and IT Coordinator. Proven ability to serve "
                "as the central communication hub between customers, field technicians, and office teams—answering inbound calls, scheduling "
                "and dispatching plumbing, HVAC, and mechanical technicians, balancing workload and same-day emergency priorities, and following "
                "work orders from booking through completion. Experienced maintaining accurate job records, customer arrival updates, dispatch notes, "
                f"and service logs within computerized service management software (equivalent to {sw_bridge}MRI Angus, and WPM Plus), coordinating "
                "parts and vendor communications, and driving workflow improvements backed by strong computer skills (Computer Information Systems, 4.1 GPA)."
            )
        elif role_family == "facilities":
            tailored_summary = (
                f"{stage1_result.target_role_title} with over 3 years of hands-on commercial property operations experience, "
                "paired with leadership as an Acting Assistant Manager and Security Supervisor. Proven expertise conducting "
                "daily building and mechanical room rounds (chillers, boilers, pumps, AHUs), managing building automation systems "
                "(BAS/BMS), coordinating trade contractors across HVAC, plumbing, and electrical, and maintaining strict OH&S compliance. "
                "Certified in Occupational First Aid (OFA Level 1) and holds a valid BC Driver's License "
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

        # 2. Reorganize & Tailor Technical Skills based on role_family & JD relevance
        original_skills = master_parsed.get("skills", [])
        tuned_categories: List[SkillCategory] = []
        if role_family == "service_dispatch":
            sw_list = named_software + ["MRI Angus", "WPM Plus", "Enterprise CMMS"]
            sw_str = f"Service & Dispatch Software ({', '.join(dict.fromkeys(sw_list))})"
            tuned_categories = [
                SkillCategory(
                    category_name="Core Competencies",
                    skills=[
                        "Service Coordination & Technician Dispatching",
                        "Emergency & Same-Day Service Scheduling",
                        "High-Volume Inbound Calls & Customer Communication",
                        "Work Order Tracking (Booking to Completion)",
                        "Workload Balancing & Route/Schedule Adjustments",
                        "Parts, Materials & Vendor Coordination",
                        "Data Entry Accuracy & Dispatch Logging",
                        "Process & Workflow Improvement"
                    ]
                ),
                SkillCategory(
                    category_name="Dispatch, Scheduling & Service Operations",
                    skills=[
                        sw_str,
                        "Plumbing, HVAC & Mechanical Service Terminology",
                        "Customer Appointment & Arrival Updates",
                        "Real-Time Field Technician Monitoring",
                        "Escalation Resolution & SLA Management",
                        "Valid BC Driver's License & Reliable Vehicle"
                    ]
                ),
                SkillCategory(
                    category_name="Technical & Computer Proficiency",
                    skills=[
                        "Strong Multi-System Software Adaptability",
                        "Microsoft 365 (Excel, Outlook, Teams)",
                        "CRM & Ticketing Databases",
                        "SQL",
                        "Power BI",
                        "Python",
                        "Automated Workflow & Log Reporting"
                    ]
                )
            ]
        else:
            for cat in original_skills:
                cat_name = cat["category"]
                if cat_name.isupper():
                    cat_name = cat_name.title()
                skills_list = cat["skills"]
                sorted_skills = sorted(skills_list, key=lambda s: 0 if s.lower() in jd_lower else 1)
                tuned_categories.append(SkillCategory(
                    category_name=cat_name,
                    skills=sorted_skills
                ))

        # 3. Tune Experience Bullets (Preserve all employers, titles, dates, locations)
        tuned_experiences: List[TunedExperience] = []
        for exp in master_parsed.get("experiences", []):
            comp_name = exp.get("company", "")
            if role_family == "service_dispatch" and "GuardTeck" in comp_name:
                sw_equiv = f"{', '.join(named_software)}, MRI Angus, and WPM Plus" if named_software else "Vonigo, MRI Angus, and WPM Plus"
                tuned_bullets = [
                    "Served as the central communication and dispatch hub across high-traffic commercial operations, answering incoming calls and inquiries professionally while coordinating field personnel and plumbing, HVAC, and electrical service technicians.",
                    "Scheduled and dispatched service and field personnel, balancing technician availability, workload, and urgent emergency or same-day service priorities while monitoring real-time progress and making schedule adjustments throughout the day.",
                    f"Maintained accurate job records, customer arrival updates, dispatch notes, and service logs within computerized service management workflows equivalent to {sw_equiv}, following work orders from initial booking through completion.",
                    "Coordinated vendor communications, parts/materials readiness, and workflow improvements with technicians, management, and administrative staff to maintain exceptional service standards and customer satisfaction."
                ]
            elif role_family == "service_dispatch" and "ULO Real Estate" in comp_name:
                tuned_bullets = [
                    "Manage multi-system software platforms, cloud databases, and remote operational workflows to ensure 100% data accuracy, system reliability, and seamless communication between office and field teams.",
                    "Coordinate inbound technical and service support tickets from booking through resolution, maintaining detailed service logs and recommending workflow improvements to boost daily operational efficiency.",
                    "Collaborate with vendors, external contractors, and administrative staff to streamline scheduling, system onboarding, and standard operating procedures."
                ]
            else:
                tuned_bullets = []
                for b in exp["bullets"]:
                    polished = b.strip()
                    if not polished or polished == ".":
                        continue
                    polished = polished.replace("directly analogous to AI adoption facilitation with business stakeholders", "").strip()
                    polished = re.sub(
                        r'\(directly transferable to Angus and WPM Plus\)',
                        'utilizing enterprise CMMS workflows equivalent to MRI Angus and WPM Plus',
                        polished,
                        flags=re.I
                    )
                    if role_family == "facilities" and "GuardTeck" in comp_name:
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

        # Enforce reverse-chronological order
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

        # Slot 2: Custom JD-Fit Proposed Project (Under Development)
        proposed_proj = structured.get("proposed_project", {})
        raw_slot2_title = (
            stage1_result.slot2_proposed_title
            or proposed_proj.get("title")
            or "Automated Operations & Dispatch Workflow Tracker (Under Development)"
        )
        if "(under development)" not in raw_slot2_title.lower():
            slot2_title = f"{raw_slot2_title.strip()} (Under Development)"
        else:
            slot2_title = raw_slot2_title.strip()

        slot2_technologies = (
            stage1_result.slot2_proposed_technologies
            or proposed_proj.get("technologies")
            or ["Python", "SQL", "Power BI"]
        )
        slot2_bullets = list(proposed_proj.get("bullets") or [
            f"Developing a targeted operational workflow and scheduling solution using {', '.join(slot2_technologies[:3])}.",
            f"Architecture: {stage1_result.slot2_proposed_plan or proposed_proj.get('plan', 'End-to-end work-order lifecycle tracking.')}",
            "Deliverables: Automated status tracking, SLA alerting, and interactive KPI reporting dashboards."
        ])
        slot2_is_proposed = True

        return Stage2CustomizationResult(
            tailored_summary=tailored_summary,
            skill_categories=tuned_categories,
            experiences=tuned_experiences,
            slot1_title=slot1_title,
            slot1_technologies=p1.technologies if p1 else [],
            slot1_bullets=slot1_bullets,
            slot2_title=slot2_title,
            slot2_technologies=slot2_technologies,
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

        structured = _parse_and_structure_raw_jd(job_description)
        target_company = structured["target_company"] or "Hiring Team"
        target_role = structured["clean_role_title"]
        role_family = structured["role_family"]
        named_software = structured["named_software"]
        sw_text = f"{', '.join(named_software)}, " if named_software else "Vonigo, "

        if role_family == "service_dispatch":
            body_p1 = (
                f"When I saw the opening for the {target_role} role at {target_company}, I knew immediately this was the "
                "exact environment I thrive in. I recently completed my Computer Information Systems degree at the University of the Fraser Valley "
                "with a 4.1 GPA and consecutive Dean's List honors—while spending over three years on the front lines as an Acting Assistant Manager, "
                "Supervisor, and IT Coordinator managing 24/7 dispatch, high-volume calls, and emergency service workflows."
            )
            body_p2 = (
                f"Your posting calls for a central communication hub between customers, field technicians, and the office team who understands the fast pace "
                f"of emergency and same-day service work. That has been my daily reality. For over three years, I have answered high-volume inquiries, scheduled "
                f"and dispatched field personnel and plumbing, HVAC, and mechanical technicians, balanced changing daily workloads, and tracked work orders from "
                f"initial booking through completion using computerized dispatch software (utilizing workflows equivalent to {sw_text}MRI Angus, and WPM Plus)."
            )
            body_p3 = (
                "Here is why hiring me gives your dispatch desk an immediate edge: coming straight out of university with a 4.1 GPA in Computer Information Systems, "
                "I learn new software systems like Vonigo in hours rather than weeks, maintain spotless data entry and dispatch logs, and bring relentless energy, "
                "zero bad habits, and unshakeable composure when phones are ringing off the hook and emergency requests come in."
            )
            body_p4 = (
                f"I am hungry to learn, grateful for the opportunity to work hard, and ready to support your technicians and customers from day one. "
                f"I would welcome 15 minutes to discuss how my dispatch experience, computer proficiency, and work ethic will deliver immediate value to {target_company}."
            )
        elif role_family == "facilities":
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
        structured = _parse_and_structure_raw_jd(job_description)
        target_company = structured["target_company"] or "your team"
        target_role = structured["clean_role_title"]
        role_family = structured["role_family"]
        named_software = structured["named_software"]
        sw_text = f"{', '.join(named_software)}, " if named_software else "Vonigo, "

        if role_family == "service_dispatch":
            linkedin_message = (
                f"Hi Hiring Team,\n\n"
                f"I came across the {target_role} opening at {target_company} and wanted to reach out directly. "
                f"I recently graduated with a Computer Information Systems degree (4.1 GPA, 4-time Dean's List), "
                f"pairing strong multi-system computer skills with 3+ years of high-volume dispatch, emergency service coordination, "
                f"and field technician scheduling—tracking work orders from booking through completion in computerized dispatch systems ({sw_text}Angus/WPM).\n\n"
                f"Coming straight out of college, I bring relentless energy, fast software mastery, and calm professionalism under high call volumes.\n\n"
                f"Would you be open to connecting or having a brief 5-minute chat?\n\n"
                f"Best regards,\nManbir Singh Sidhu\n+1 778-956-1186 | https://www.linkedin.com/in/manbir-singh-sidhu/ | https://github.com/SidhuManbirSingh/SidhuManbirSingh/"
            )

            email_subject = f"Application: {target_role} - Manbir Singh Sidhu (3+ Yrs Dispatch & Service Coordination | 4.1 GPA)"
            email_body = (
                f"Dear {target_company} Hiring Team,\n\n"
                f"I am reaching out regarding the {target_role} position at {target_company}. "
                f"I recently graduated with a Computer Information Systems degree from the University of the Fraser Valley (4.1 GPA, 4x Dean's List) "
                f"while spending the past three years working as an Acting Assistant Manager, Supervisor, and IT Coordinator managing real-time dispatch, "
                f"emergency escalations, and trade technician coordination.\n\n"
                f"Your posting highlights serving as the central communication hub between customers, field technicians, and office staff—scheduling appointments, "
                f"coordinating emergency and same-day plumbing/service requests, and tracking work orders from booking through completion. In my daily operations, "
                f"I have managed inbound inquiries, dispatched plumbing, HVAC, and field personnel, coordinated vendor/parts availability, and maintained detailed "
                f"service logs in enterprise dispatch platforms ({sw_text}MRI Angus, WPM Plus).\n\n"
                f"Because of my Computer Information Systems background, I pick up new dispatch and field service software rapidly with exceptional data entry accuracy. "
                f"I would welcome 10-15 minutes to discuss how my work ethic, calm phone manner, and dispatch experience can support {target_company}.\n\n"
                f"Sincerely,\n\n"
                f"Manbir Singh Sidhu\n"
                f"Surrey, BC | +1 778-956-1186\n"
                f"manbirs285@gmail.com\n"
                f"LinkedIn: https://www.linkedin.com/in/manbir-singh-sidhu/\n"
                f"GitHub: https://github.com/SidhuManbirSingh/SidhuManbirSingh/"
            )
        elif role_family == "facilities":
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

