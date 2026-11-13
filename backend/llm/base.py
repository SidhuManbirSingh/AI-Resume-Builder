import re
from typing import Dict, Any, List, Optional
from backend.models.schemas import (
    Stage1AnalysisResult,
    Stage2CustomizationResult,
    ProjectMetadata,
)


class BaseLLMClient:
    provider_name: str = "base"

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


def _extract_json(text: str) -> str:
    """
    Safely extracts JSON substring if wrapped in markdown code blocks.
    """
    text = text.strip()
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


_FLUFF_ADJECTIVES = {
    "highly", "organized", "and", "customer-focused", "customer", "focused",
    "motivated", "experienced", "dynamic", "dedicated", "detail-oriented",
    "detail", "oriented", "results-driven", "results", "driven", "full-time",
    "part-time", "proactive", "reliable", "skilled", "talented", "passionate",
    "energetic", "hardworking", "seasoned", "qualified", "professional",
    "bilingual", "friendly", "enthusiastic", "self-motivated", "hands-on",
    "ambitious", "collaborative", "adaptable", "resourceful", "dependable",
    "growing", "fast-paced", "team-oriented", "service-oriented", "client-focused",
    "exceptional", "strong", "capable", "committed", "diligent", "personable"
}


def _clean_extracted_title(raw_title: str) -> str:
    """
    Cleans raw extracted role titles by stripping leading job-board fluff adjectives
    ('highly organized and customer-focused Service Coordinator / Dispatcher' -> 'Service Coordinator / Dispatcher')
    and removing any multiline or trailing clause artifacts.
    """
    if not raw_title:
        return "Operations & Service Coordinator"
    lines = [ln.strip() for ln in raw_title.splitlines() if ln.strip()]
    candidate = lines[0] if lines else raw_title.strip()

    candidate = re.split(
        r'\s+(?:to\s+join|to\s+lead|to\s+support|to\s+manage|to\s+oversee|to\s+serve|to\s+supervise|to\s+architect|for\s+our|at\s+our|in\s+[A-Z][a-z]+|who\s+will|with\s+previous|with\s+experience|based\s+in)\b',
        candidate,
        maxsplit=1,
        flags=re.IGNORECASE
    )[0].strip()

    tokens = candidate.split()
    idx = 0
    while idx < len(tokens) - 1:
        raw_tok = tokens[idx].strip(",.;:-")
        low_tok = raw_tok.lower()
        if low_tok in ("a", "an", "the", "our") or low_tok in _FLUFF_ADJECTIVES:
            idx += 1
            continue
        break

    cleaned = " ".join(tokens[idx:]).strip(" ,.;:-")
    if not cleaned or len(cleaned) > 85:
        return "Operations & Service Coordinator"

    words = cleaned.split()
    formatted_words = []
    for w in words:
        if w.upper() in {"IT", "BMS", "BAS", "HVAC", "QA", "AI", "ERP", "CRM", "SQL", "AWS", "NOC", "SOC", "GIS", "API"}:
            formatted_words.append(w.upper())
        elif w in {"/", "&", "-", "and", "of", "for", "in"}:
            formatted_words.append(w.lower() if w in {"and", "of", "for", "in"} else w)
        else:
            formatted_words.append(w[0].upper() + w[1:] if len(w) > 1 else w.upper())
    return " ".join(formatted_words)


def _has_whole_word(text: str, word_or_phrase: str) -> bool:
    return bool(re.search(rf'\b{re.escape(word_or_phrase)}\b', text, re.IGNORECASE))


def _parse_and_structure_raw_jd(job_description: str) -> Dict[str, Any]:
    """
    Stage 0 Deterministic Job Posting Parser & Structurer.
    Uses anchored line regexes and whole-word boundary checks (never matching 'bas'/'bms' inside 'database'/'bash'
    and never matching 'About the Role:' as a job title).
    """
    cleaned_lines = []
    in_benefits_or_footer = False
    for line in job_description.splitlines():
        s = line.strip()
        s_low = s.lower()
        if s_low in {
            "ull job description", "full job description", "job description",
            "job summary", "about the role", "about the role:", "position summary", "overview"
        }:
            continue
        if re.match(r'^(?:pay|salary|compensation|benefits|work\s+location|supplemental\s+pay|schedule|job\s+types?)\s*:', s_low):
            if s_low.startswith("benefits"):
                in_benefits_or_footer = True
            continue
        if in_benefits_or_footer:
            if s_low in {
                "company events", "employee assistance program", "extended health care",
                "paid time off", "wellness program", "dental care", "vision care",
                "life insurance", "rrsp match", "on-site parking", "casual dress"
            } or len(s.split()) <= 4:
                continue
            else:
                in_benefits_or_footer = False
        cleaned_lines.append(line)

    cleaned_jd_text = "\n".join(cleaned_lines).strip()
    if not cleaned_jd_text:
        cleaned_jd_text = job_description.strip()
    jd_lower = cleaned_jd_text.lower()

    # 1. Extract Target Company
    target_company = None
    comp_explicit = re.search(
        r'^\s*(?:Company|Client|Employer|Organization)[ \t]*:[ \t]*([^\n\r,]+)',
        job_description,
        re.IGNORECASE | re.MULTILINE
    )
    if comp_explicit:
        target_company = comp_explicit.group(1).strip()
    else:
        comp_narrative = re.search(
            r'^\s*([A-Z][A-Za-z0-9 \t&\.,\'-]{1,50}?)\s+(?:is\s+seeking|are\s+seeking|is\s+looking\s+for|are\s+looking\s+for|is\s+hiring|are\s+hiring)\b',
            cleaned_jd_text,
            re.MULTILINE
        )
        if comp_narrative:
            cand_comp = comp_narrative.group(1).strip()
            if cand_comp.lower() not in {"we", "our team", "the company", "our client", "job summary"}:
                target_company = cand_comp

    # 2. Extract Clean Target Role Title
    # Step A: Anchored explicit 'Job Title:' or 'Title:' or 'Position:' (never 'About the Role:')
    target_role = None
    title_explicit = re.search(
        r'^\s*(?:job[ \t]+)?(?:title|position|role)[ \t]*:[ \t]*([^\n\r,]+)',
        job_description,
        re.IGNORECASE | re.MULTILINE
    )
    if title_explicit:
        target_role = _clean_extracted_title(title_explicit.group(1).strip())

    # Step B: Check if the very first non-empty line is a standalone role headline (like in SAMPLE_JDS)
    if not target_role:
        non_empty_lines = [ln.strip() for ln in cleaned_jd_text.splitlines() if ln.strip()]
        if non_empty_lines:
            first_ln = non_empty_lines[0]
            if (
                len(first_ln) <= 85
                and ":" not in first_ln
                and not first_ln.endswith(".")
                and re.search(
                    r'\b(?:Coordinator|Dispatcher|Specialist|Manager|Supervisor|Engineer|Developer|Architect|Operator|Technician|Administrator|Analyst)\b',
                    first_ln,
                    re.IGNORECASE
                )
            ):
                target_role = _clean_extracted_title(first_ln)

    # Step C: Narrative recruitment sentences ("is seeking a ... [Role] to join...")
    if not target_role:
        narrative_role = re.search(
            r'(?:is\s+seeking|are\s+seeking|is\s+looking\s+for|are\s+looking\s+for|is\s+hiring|are\s+hiring|searching\s+for|seeking|looking\s+for|hiring)\s+(?:an?\s+)?([^\.\n\r]{3,90}?)\s+(?:to\s+join|to\s+lead|to\s+support|to\s+manage|to\s+oversee|to\s+serve|to\s+supervise|to\s+architect|for\s+our|at\s+our|in\s+[A-Z][a-z]+|who\s+will|with\s+previous|with\s+experience|with\s+strong)',
            cleaned_jd_text,
            re.IGNORECASE
        )
        if narrative_role:
            target_role = _clean_extracted_title(narrative_role.group(1))

    # Step D: Single-line role pattern
    if not target_role:
        line_role = re.search(
            r'\b((?:Senior|Lead|Chief|Assistant|Junior|Acting|Commercial|Field|Technical|Building|Property|Facilities|Facility|Service|Operations|IT|Systems|Cloud|Software|Backend|Platform|Data|Infrastructure|Maintenance|Project|Customer[ \t]+Service|Dispatch)[A-Za-z0-9 \t/&,-]{0,45}?(?:Coordinator|Dispatcher|Specialist|Manager|Supervisor|Engineer|Developer|Architect|Operator|Technician|Administrator|Analyst)(?:[ \t]*/[ \t]*[A-Za-z0-9 \t&-]+)?)\b',
            cleaned_jd_text,
            re.IGNORECASE
        )
        if line_role:
            target_role = _clean_extracted_title(line_role.group(1))

    if not target_role:
        target_role = "Operations & Service Coordinator"

    # 3. Detect Named Software / Platforms
    software_catalog = [
        ("vonigo", "Vonigo"),
        ("servicetitan", "ServiceTitan"),
        ("jobber", "Jobber"),
        ("mri angus", "MRI Angus"),
        ("wpm plus", "WPM Plus"),
        ("yardi", "Yardi"),
        ("servicenow", "ServiceNow"),
        ("zendesk", "Zendesk"),
        ("jira", "Jira"),
        ("salesforce", "Salesforce"),
        ("sap", "SAP"),
        ("active directory", "Active Directory"),
        ("azure", "Azure"),
        ("m365", "Microsoft 365"),
        ("power bi", "Power BI"),
    ]
    named_software = [label for key, label in software_catalog if _has_whole_word(jd_lower, key)]

    # 4. Classify Role Archetype & Role Family using whole-word boundary matching
    role_low = target_role.lower()
    is_dispatch = (
        any(w in role_low for w in ["dispatcher", "dispatch", "service coordinator", "scheduling coordinator", "call taker", "customer service"])
        or sum(1 for k in ["dispatching", "inbound calls", "call-taking", "vonigo", "field service technicians", "same-day service", "appointment updates"] if _has_whole_word(jd_lower, k)) >= 2
    )
    facilities_terms = [
        "mechanical room", "chillers", "chiller", "boilers", "boiler", "cooling towers",
        "ahus", "ahu", "bms", "bas", "mri angus", "wpm plus", "ofa level 1", "building rounds",
        "hvac", "groundskeeping", "lamp/ballast", "preventative maintenance"
    ]
    is_building_ops = (
        not is_dispatch and (
            any(w in role_low for w in ["building", "facility", "facilities", "operator", "property", "maintenance"])
            or sum(1 for k in facilities_terms if _has_whole_word(jd_lower, k)) >= 2
        )
    )
    is_it_systems = (
        not is_dispatch and not is_building_ops and (
            any(_has_whole_word(role_low, w) for w in ["it", "information technology", "helpdesk", "technical support", "systems administrator", "network", "desktop"])
            or sum(1 for k in ["active directory", "azure", "vpn", "workstation", "helpdesk", "ticketing", "endpoint", "windows server"] if _has_whole_word(jd_lower, k)) >= 2
        )
    )

    if is_dispatch:
        role_archetype = "service_dispatch"
        role_family = "service_dispatch"
    elif is_building_ops:
        role_archetype = "building_operations"
        role_family = "facilities"
    elif is_it_systems:
        role_archetype = "it_systems"
        role_family = "software_it"
    else:
        role_archetype = "software_engineering"
        role_family = "software_it"

    # 5. Build Archetype-Specific Keywords, Responsibilities, and Profile Summary Blueprint
    if role_archetype == "service_dispatch":
        sw_mention = f"{', '.join(named_software)}, " if named_software else ""
        found_tech = []
        for kw, label in [
            ("dispatch", "Technician Dispatching & Scheduling"),
            ("vonigo", "Vonigo / Field Service Software"),
            ("work order", "Work Order Management (Booking to Completion)"),
            ("emergency", "Emergency & Same-Day Service Coordination"),
            ("inbound", "High-Volume Inbound Call Handling"),
            ("vendor", "Parts, Materials & Vendor Coordination"),
            ("plumbing", "Plumbing & Mechanical Service Terminology"),
            ("customer", "Customer Communication & Arrival Updates"),
        ]:
            if kw in jd_lower:
                found_tech.append(label)
        if not found_tech:
            found_tech = [
                "Service Coordination & Technician Dispatching",
                "Emergency & Same-Day Scheduling",
                "Work Order Lifecycle Management",
                "High-Volume Inbound Call Handling",
                "Vendor & Parts Coordination"
            ]
        key_resp = [
            "Serve as the central communication hub between customers, field service technicians, and office management.",
            f"Schedule and dispatch service technicians, balance daily workloads and emergency/same-day requests, and track work orders from booking through completion in {sw_mention}enterprise service management software.",
            "Maintain accurate job records, customer arrival updates, dispatch notes, and vendor/parts coordination while identifying workflow efficiency improvements."
        ]
        profile_summary_blueprint = (
            f"Write a compelling 3-4 sentence Professional Summary opening with the exact title '{target_role}'. "
            "Position the candidate as a central communication and dispatch hub with over 3 years of high-volume operations, 24/7 dispatching, "
            "and emergency/same-day service coordination experience (paired with leadership as an Acting Assistant Manager and IT Coordinator). "
            f"Highlight proven ability to answer inbound inquiries, schedule and dispatch field technicians (plumbing, HVAC, mechanical), track work orders from booking through completion, "
            f"and maintain accurate job records and dispatch logs in service management software ({sw_mention}MRI Angus, WPM Plus, enterprise CMMS). "
            "Emphasize vendor/parts coordination, multitasking in fast-paced environments, data entry accuracy, and strong multi-system computer skills (Computer Information Systems, 4.1 GPA)."
        )
        sw_primary = named_software[0] if named_software else "Field Service"
        proposed_project = {
            "title": f"Automated {sw_primary} Dispatch & Work-Order Lifecycle Tracker (Under Development)",
            "technologies": (named_software if named_software else ["Field Service CRM"]) + ["Python", "SQL", "Power BI", "Automated Dispatch"],
            "plan": (
                f"Targeted operational prototype modeling {sw_primary} scheduling, emergency/same-day technician dispatch, "
                "real-time job status tracking from booking through completion, and automated parts/vendor coordination logs."
            ),
            "rationale": f"Custom-designed project directly targeting {target_role} workflows, {sw_primary} dispatching, and real-time technician coordination.",
            "bullets": [
                f"Developing an automated field service dispatch and technician scheduling workflow modeled on {sw_primary} to balance daily technician availability, workload priorities, and emergency or same-day service requests.",
                "Building end-to-end work order lifecycle tracking from initial customer call and appointment booking through technician dispatch, real-time progress monitoring, customer arrival updates, and final job completion.",
                "Integrating parts, materials, and vendor coordination logs with SQL and Power BI analytics dashboards to eliminate scheduling bottlenecks and maintain 100% dispatch log accuracy."
            ]
        }
    elif role_archetype == "building_operations":
        tech_keywords = [
            ("bms", "BMS/BAS Controls"),
            ("bas", "BAS Automation"),
            ("hvac", "HVAC Systems"),
            ("chillers", "Chillers"),
            ("boilers", "Boilers"),
            ("cooling towers", "Cooling Towers"),
            ("pumps", "Pumps"),
            ("ahus", "AHUs"),
            ("mri angus", "MRI Angus"),
            ("wpm plus", "WPM Plus"),
            ("ofa level 1", "OFA Level 1"),
            ("preventative maintenance", "Preventative Maintenance"),
            ("plumbing", "Minor Plumbing Repairs"),
            ("electrical", "Electrical Troubleshooting"),
            ("work order", "Work Order Management")
        ]
        found_tech = [label for kw, label in tech_keywords if _has_whole_word(jd_lower, kw)]
        if not found_tech:
            found_tech = ["BMS/BAS Controls", "HVAC & Mechanical Systems", "MRI Angus", "Preventative Maintenance", "OFA Level 1"]
        key_resp = [
            "Conduct daily building rounds, inspect mechanical rooms (chillers, boilers, AHUs, pumps), and log system parameters.",
            "Manage computerized work order dispatch (MRI Angus / WPM Plus) and coordinate HVAC, plumbing, and electrical trade contractors.",
            "Ensure strict life-safety, fire system, and Occupational Health & Safety (OH&S) compliance across commercial properties."
        ]
        profile_summary_blueprint = (
            f"Write a 3-4 sentence Professional Summary opening with the exact title '{target_role}'. "
            "Highlight over 3 years of hands-on commercial property operations experience, paired with leadership as an Acting Assistant Manager and Security Supervisor. "
            "Emphasize daily building and mechanical room rounds (chillers, boilers, pumps, AHUs), BAS/BMS monitoring, trade contractor coordination across HVAC, plumbing, and electrical, "
            "OH&S compliance, OFA Level 1 certification, valid BC Driver's License with reliable vehicle, and 4.1 GPA CIS background."
        )
        cmms_label = " & ".join(named_software[:2]) if named_software else "MRI Angus & WPM Plus"
        proposed_project = {
            "title": f"Smart Building Mechanical Telemetry & {cmms_label} Work-Order Automator (Under Development)",
            "technologies": ["BMS/BAS Controls", "MRI Angus", "WPM Plus", "HVAC Telemetry", "Python", "SQL", "Power BI"],
            "plan": (
                f"Targeted facilities operations tool integrating daily mechanical room inspection logs (chillers, boilers, cooling towers, AHUs, pumps) "
                f"with automated {cmms_label} preventative maintenance work-order scheduling and OH&S compliance tracking."
            ),
            "rationale": f"Custom-designed project tailored specifically to {target_role} requirements across BMS/BAS monitoring, mechanical rounds, and CMMS work-order dispatch.",
            "bullets": [
                "Developing a centralized digital log and anomaly-alerting utility for daily mechanical room rounds across chillers, cooling towers, boilers, AHUs, and pumps to proactively flag pressure and temperature drift.",
                f"Automating preventative maintenance scheduling and trade contractor dispatch tracking across HVAC, plumbing, electrical, and life-safety work orders modeled on {cmms_label} CMMS workflows.",
                "Building interactive SQL and Power BI operational dashboards tracking filter/belt changes, lamp/ballast replacements, vendor SLA turnaround times, and Occupational Health & Safety (OH&S / JHA) compliance."
            ]
        }
    elif role_archetype == "it_systems":
        found_tech = ["Active Directory & Azure", "Microsoft 365 Administration", "Cloud Infrastructure & VPNs", "Technical Support & Ticketing", "Python & SQL Automation", "Power BI Reporting"]
        key_resp = [
            "Manage cloud infrastructure, remote servers, Active Directory, and endpoint security to ensure high system availability.",
            "Provide responsive technical support, workstation deployment, and incident resolution across distributed teams.",
            "Automate operational workflows, reporting dashboards, and system documentation."
        ]
        profile_summary_blueprint = (
            f"Write a 3-4 sentence Professional Summary opening with the exact title '{target_role}'. "
            "Combine the candidate's Computer Information Systems background (4.1 GPA, 4x Dean's List) and IT Coordinator experience at ULO Real Estate "
            "with 3+ years of operational leadership, incident dispatch, and multi-system troubleshooting."
        )
        proposed_project = {
            "title": "Enterprise Endpoint Diagnostics & Automated IT Ticketing Orchestrator (Under Development)",
            "technologies": ["Active Directory", "Azure", "Microsoft 365", "Python", "PowerShell", "SQL"],
            "plan": "Targeted IT operations platform automating workstation onboarding, VPN/MFA health checks, and SLA-prioritized support ticket routing.",
            "rationale": f"Custom-designed project directly aligned with {target_role} responsibilities in identity administration, endpoint support, and workflow automation.",
            "bullets": [
                "Developing an automated endpoint health-check and user onboarding utility integrating Active Directory, Azure RBAC, and Microsoft 365 provisioning to reduce manual workstation setup time.",
                "Building an intelligent support ticket triage and escalation tracker in Python and SQL to monitor incident response SLAs across distributed remote teams.",
                "Creating real-time infrastructure uptime and security compliance dashboards in Power BI to track VPN connectivity, patch status, and license utilization."
            ]
        }
    else:
        tech_keywords = [
            "python", "go", "golang", "fastapi", "django", "kafka", "aws", "kubernetes",
            "docker", "redis", "postgresql", "terraform", "microservices", "distributed systems",
            "rag", "llm", "vector", "grpc", "ci/cd", "prometheus", "graphql", "sql", "power bi"
        ]
        found_tech = [t.capitalize() for t in tech_keywords if _has_whole_word(jd_lower, t)]
        if not found_tech:
            found_tech = ["Python", "Go", "AWS", "PostgreSQL", "Docker"]
        key_resp = [
            "Architect and scale reliable backend microservices and distributed APIs.",
            "Optimize data storage, caching layers, and high-throughput transaction pipelines.",
            "Drive engineering best practices, automated testing, and cloud infrastructure reliability."
        ]
        profile_summary_blueprint = (
            f"Write a 3-4 sentence Professional Summary opening with the exact title '{target_role}' and highlighting Computer Information Systems background (4.1 GPA) "
            f"plus hands-on expertise in {', '.join(found_tech[:4])}."
        )
        top_stack = ", ".join(found_tech[:3])
        proposed_project = {
            "title": f"High-Availability {found_tech[0]} Service & Telemetry Pipeline (Under Development)",
            "technologies": found_tech[:5],
            "plan": f"Targeted engineering prototype implementing resilient service endpoints, automated schema validation, and observability metrics using {top_stack}.",
            "rationale": f"Custom-designed project demonstrating direct hands-on execution with the core {top_stack} stack required for {target_role}.",
            "bullets": [
                f"Architecting a fault-tolerant backend service and data processing pipeline using {top_stack} with strict schema validation, connection pooling, and automated retry handling.",
                "Implementing containerized integration test suites and CI/CD quality gates to verify throughput, latency targets, and zero-downtime deployment readiness.",
                "Building real-time operational telemetry and health-check endpoints to monitor system performance, error budgets, and resource utilization."
            ]
        }

    return {
        "clean_role_title": target_role,
        "target_company": target_company,
        "role_archetype": role_archetype,
        "role_family": role_family,
        "named_software": named_software,
        "key_technical_requirements": found_tech[:6],
        "key_responsibilities": key_resp,
        "cleaned_jd_text": cleaned_jd_text,
        "profile_summary_blueprint": profile_summary_blueprint,
        "proposed_project": proposed_project
    }

