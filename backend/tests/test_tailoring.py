import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import unittest
import json
from unittest.mock import patch, MagicMock
from backend.services.file_loader import FileLoaderService, MasterResumeParser
from backend.core.security import strip_github_links, sanitize_job_description, sanitize_filename
from backend.services.validator import ResumeValidator, FactualInvarianceValidationError
from backend.services.ai_orchestrator import AIResumeOrchestrator
from backend.services.pdf_generator import ATSResumePDFGenerator
from backend.services.markdown_assembler import MarkdownAssembler
from backend.services.llm_client import GeminiLLMClient
from backend.models.schemas import (
    Stage1AnalysisResult,
    Stage2CustomizationResult,
    TunedExperience,
    SkillCategory
)
from backend.core.config import settings

class TestResumeTailoringSystem(unittest.TestCase):

    def setUp(self):
        # Enforce deterministic mock LLM provider for fast, offline unit testing
        self._orig_provider = settings.LLM_PROVIDER
        settings.LLM_PROVIDER = "mock"

    def tearDown(self):
        settings.LLM_PROVIDER = self._orig_provider

    def test_file_loader_master_resume(self):
        """Verify master resume loads and parses sections without mutating the source."""
        raw, parsed = FileLoaderService.get_master_resume()
        self.assertTrue(bool(parsed["name"]))
        self.assertTrue(len(parsed["experiences"]) >= 1)
        self.assertTrue(len(parsed["skills"]) >= 1)
        self.assertTrue("summary" in parsed or "Professional Summary" in raw)

    def test_project_catalog_loader(self):
        """Verify projects are indexed with YAML frontmatter metadata."""
        projects = FileLoaderService.get_project_catalog()
        self.assertGreaterEqual(len(projects), 5)
        ids = [p.id for p in projects]
        self.assertIn("gitlab_k8s_platform", ids)
        self.assertIn("cotton_weed_ai_pipeline", ids)
        self.assertIn("azure_cloud_security_auditor", ids)
        self.assertIn("canadian_ai_exposure_dashboard", ids)
        
        # Verify frontmatter parsing
        p_gitlab = next(p for p in projects if p.id == "gitlab_k8s_platform")
        self.assertIn("Kubernetes", p_gitlab.technologies)
        self.assertIn("Docker Compose", p_gitlab.technologies)

    def test_strip_github_links_rule_4_8(self):
        """Mandatory Rule 4.8: Do not include a GitHub profile link in the generated resume."""
        header_with_github = "San Francisco, CA | alex@email.com | (555) 000-0000 | linkedin.com/in/alex | github.com/alexmorgan"
        cleaned = strip_github_links(header_with_github)
        self.assertNotIn("github.com", cleaned.lower())
        self.assertIn("linkedin.com/in/alex", cleaned)
        self.assertIn("alex@email.com", cleaned)

        # Markdown link format
        md_link = "Check my code at [GitHub](https://github.com/myusername) and [LinkedIn](https://linkedin.com/in/myuser)"
        cleaned_md = strip_github_links(md_link)
        self.assertNotIn("github.com", cleaned_md)
        self.assertIn("LinkedIn", cleaned_md)

    def test_sanitize_filename_prevents_header_injection_and_traversal(self):
        """Pen-check test: Verify filename sanitization against CRLF injection and path traversal."""
        malicious_input = 'resume\r\nSet-Cookie: session=evil\r\nContent-Disposition: inline.pdf'
        safe = sanitize_filename(malicious_input, "resume", ".pdf")
        self.assertNotIn("\r", safe)
        self.assertNotIn("\n", safe)
        self.assertTrue(safe.endswith(".pdf"))

        traversal_input = '../../../../etc/passwd.pdf'
        safe_trav = sanitize_filename(traversal_input, "resume", ".pdf")
        self.assertNotIn("..", safe_trav)
        self.assertNotIn("/", safe_trav)
        self.assertNotIn("\\", safe_trav)

    def test_invariance_validator_restores_tampered_metadata(self):
        """Verify that any unauthorized alterations to employers, titles, or dates are restored."""
        _, master_parsed = FileLoaderService.get_master_resume()
        
        tampered_exps = [
            TunedExperience(
                company="Google LLC", # Tampered!
                title="VP of Engineering", # Tampered!
                date_range="2010 – Present", # Tampered!
                location="Mountain View, CA",
                bullets=["Led worldwide engineering."]
            )
        ]
        for exp in master_parsed["experiences"][1:]:
            tampered_exps.append(TunedExperience(
                company=exp["company"],
                title=exp["title"],
                date_range=exp["date_range"],
                location=exp["location"],
                bullets=["Valid bullet."]
            ))

        tampered = Stage2CustomizationResult(
            tailored_summary="Expert software engineer with 10 years experience.",
            skill_categories=[SkillCategory(category_name="Languages", skills=["Go", "Python"])],
            experiences=tampered_exps,
            slot1_title="Key Project",
            slot1_bullets=["Bullet 1"],
            slot2_title="Proposed System",
            slot2_bullets=["Bullet 2"],
            slot2_is_proposed=True
        )

        validated, warnings = ResumeValidator.validate_and_sanitize(master_parsed, tampered)
        
        # Verify restoration of original truth
        self.assertEqual(validated.experiences[0].company, master_parsed["experiences"][0]["company"])
        self.assertEqual(validated.experiences[0].title, master_parsed["experiences"][0]["title"])
        self.assertEqual(validated.experiences[0].date_range, master_parsed["experiences"][0]["date_range"])
        self.assertTrue(any("Restoring original company name" in w for w in warnings))

    def test_proposed_project_badge_enforcement(self):
        """Verify Rule 3.C: proposed projects must be clearly labeled."""
        _, master_parsed = FileLoaderService.get_master_resume()
        customized = Stage2CustomizationResult(
            tailored_summary="Summary",
            skill_categories=[SkillCategory(category_name="Languages", skills=["Go"])],
            experiences=[
                TunedExperience(
                    company=exp["company"],
                    title=exp["title"],
                    date_range=exp["date_range"],
                    location=exp["location"],
                    bullets=exp["bullets"]
                )
                for exp in master_parsed["experiences"]
            ],
            slot1_title="Existing Project",
            slot1_bullets=["Bullet"],
            slot2_title="Autonomous Data Lake", # Missing required proposal badge!
            slot2_bullets=["Bullet"],
            slot2_is_proposed=True
        )

        validated, warnings = ResumeValidator.validate_and_sanitize(master_parsed, customized)
        self.assertIn("(Under Development)", validated.slot2_title)

    def test_end_to_end_tailoring_pipeline(self):
        """Executes full multi-stage tailoring against a real job description."""
        _, master_parsed = FileLoaderService.get_master_resume()
        sample_jd = """
        Staff Distributed Systems Engineer - High Throughput Streaming
        Requirements:
        - 5+ years building distributed backend systems in Go and Python.
        - Experience with Apache Kafka, message queues, and high-volume event ingestion.
        - Expertise in Redis caching and PostgreSQL optimization.
        - Deep understanding of containerized deployment with Docker and Kubernetes on AWS.
        """
        response = AIResumeOrchestrator.tailor_resume(sample_jd)

        # 1. Output exists and is populated
        self.assertIsNotNone(response.tailored_markdown)
        self.assertIn("## Professional Summary", response.tailored_markdown)
        self.assertIn("## Projects", response.tailored_markdown)

        # 2. GitHub profile link verified on contact header
        self.assertIn("github.com", response.tailored_markdown.lower())

        # 3. Project Slot 1 selected from existing catalog
        slot1 = next(s for s in response.slots if s.slot_number == 1)
        self.assertIn("GitLab", slot1.title)

        # 4. Invariance of company and job titles
        for exp in master_parsed["experiences"]:
            self.assertIn(exp["company"], response.tailored_markdown)

    def test_pdf_generation_deterministic(self):
        """Verify deterministic conversion of markdown to valid ATS PDF."""
        sample_jd = """
        Senior Backend Software Engineer - Cloud Platform
        We are seeking an experienced Senior Software Engineer with strong background in Python, FastAPI, and AWS.
        You will be responsible for architecting and deploying scalable microservices, optimizing database performance,
        and designing robust RESTful APIs in an agile environment. Experience with Docker, PostgreSQL, and Redis is required.
        """
        response = AIResumeOrchestrator.tailor_resume(sample_jd)
        pdf_bytes = ATSResumePDFGenerator.markdown_to_pdf_bytes(response.tailored_markdown)

        self.assertGreater(len(pdf_bytes), 2000)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-1.4"))
        self.assertTrue(b"%%EOF" in pdf_bytes)

    def test_facilities_ats_prompt_optimization(self):
        """Verify prompt & formatting optimization for Facilities/Building Coordinator JDs."""
        facilities_jd = """
        Job Title: Building Operations Coordinator & Assistant Facility Manager
        Company: QuadReal Property Group
        Location: Vancouver, BC
        Responsibilities:
        - Conduct daily building rounds, inspect mechanical rooms (chillers, cooling towers, AHUs, boilers, pumps), and log system parameters.
        - Manage computerized work order dispatch (MRI Angus / WPM Plus) and coordinate HVAC, plumbing, and electrical trade contractors.
        - Perform minor plumbing repairs, lamp/ballast replacement, filter and belt changes, and groundskeeping.
        - Maintain strict life-safety, fire system, and Occupational Health & Safety (OH&S) compliance.
        Requirements:
        - 3+ years in commercial building operations.
        - OFA Level 1 first aid certification, valid BC Driver's License and reliable vehicle.
        - 5th Class Power Engineering ticket or BOMA coursework considered a strong asset.
        """
        response = AIResumeOrchestrator.tailor_resume(facilities_jd)
        md = response.tailored_markdown

        # 1. Exact Target Job Title headline & no typo
        self.assertIn("Building Operations Coordinator & Assistant Facility Manager", md)
        self.assertNotIn("Results-driven technology and professional", md)

        # 2. Security Supervisor kept secondary
        summary_line = [l for l in md.splitlines() if "Building Operations Coordinator" in l][0]
        self.assertTrue(summary_line.startswith("Building Operations Coordinator"))
        self.assertIn("Acting Assistant Manager and Security Supervisor", summary_line)

        # 3. Mechanical assets embedded in GuardTeck bullets
        self.assertIn("chillers, cooling towers, AHUs, boilers, and pumps", md)

        # 4. Clean enterprise CMMS phrasing (no defensive note)
        self.assertIn("utilizing enterprise CMMS workflows equivalent to MRI Angus and WPM Plus", md)
        self.assertNotIn("directly transferable to Angus", md)

        # 5. Reverse-chronological order: Apr 2026 above Feb 2023
        idx_2026 = md.find("Apr 2026 - Present")
        idx_2023 = md.find("Feb 2023 - Present")
        self.assertTrue(idx_2026 != -1 and idx_2023 != -1)
        self.assertLess(idx_2026, idx_2023)

        # 6. No leftover AI text
        self.assertNotIn("directly analogous to AI adoption facilitation", md)

        # 7. No floating periods on blank lines or solitary periods
        for line in md.splitlines():
            self.assertNotEqual(line.strip(), ".")

        # 8. Unverified tickets removed (user explicitly does not have 5th class)
        self.assertNotIn("5th Class Power Engineering", md)
        self.assertNotIn("eligible for 5th Class", md)

    def test_pdf_header_centered_and_blue_links(self):
        """Verify candidate name & contact are centered, and links are colored blue."""
        _, master_parsed = FileLoaderService.get_master_resume()
        sample_jd = (
            "We are seeking an experienced Building Operations Coordinator to manage commercial property maintenance, "
            "monitor mechanical room equipment including chillers and boilers, dispatch trade contractors, and enforce life safety standards."
        )
        response = AIResumeOrchestrator.tailor_resume(sample_jd)
        pdf_bytes = ATSResumePDFGenerator.markdown_to_pdf_bytes(response.tailored_markdown)
        pdf_text = pdf_bytes.decode('latin1', errors='replace')

        # Verify blue color operator in PDF stream for links
        self.assertIn("0.05 0.40 0.85 rg", pdf_text)

        # Verify PDF Link Annotations exist for LinkedIn and GitHub
        self.assertIn("/Subtype /Link", pdf_text)
        self.assertIn("linkedin.com", pdf_text.lower())
        self.assertIn("github.com", pdf_text.lower())

    def test_raw_copy_pasted_service_coordinator_dispatcher_jd(self):
        """
        Verifies that raw copy-pasted job postings (containing UI header noise like
        'ull job description', narrative intros like 'Company X is seeking a highly organized...',
        and footer noise like 'Pay:' and 'Benefits:') are cleanly parsed by Stage 0 into the exact
        role title and tailored Service Coordinator / Dispatcher profile summary.
        """
        raw_pioneer_jd = (
            "ull job description\n"
            "Job Summary\n\n"
            "Pioneer Plumbing & Heating is seeking a highly organized and customer-focused "
            "Service Coordinator / Dispatcher to join our growing team in Vancouver.\n\n"
            "In this critical role, you will serve as the central communication hub between our customers, "
            "technicians, and office team. You will be responsible for coordinating service appointments, "
            "dispatching technicians efficiently, managing workflow throughout the day, and ensuring an "
            "exceptional customer experience from the initial call through job completion.\n\n"
            "Responsibilities\n"
            "Answer incoming customer calls and inquiries professionally and courteously.\n"
            "Schedule and dispatch plumbing service technicians, balancing workload, technician availability, and service priorities.\n"
            "Coordinate emergency and same-day service requests.\n"
            "Maintain accurate job records, customer information, dispatch notes, and service logs within Vonigo.\n"
            "Pay: $52,000.00-$62,000.00 per year\n"
            "Benefits:\nCompany events\nExtended health care\nWork Location: In person"
        )
        res = AIResumeOrchestrator.tailor_resume(raw_pioneer_jd)
        self.assertEqual(res.analysis["target_role_title"], "Service Coordinator / Dispatcher")
        self.assertNotIn("ull job description", res.tailored_markdown.lower())
        self.assertIn("Service Coordinator / Dispatcher", res.tailored_markdown)
        self.assertIn("Vonigo", res.tailored_markdown)
        self.assertIn("central communication hub", res.tailored_markdown)
        # Verify Slot 2 is a custom JD-fit project labeled (Under Development) and never placeholder text
        slot2 = next(s for s in res.slots if s.slot_number == 2)
        self.assertIn("(Under Development)", slot2.title)
        self.assertNotIn("Project Title", slot2.title)
        self.assertGreaterEqual(len(slot2.bullets), 3)
        self.assertNotIn("- bullet", res.tailored_markdown.lower())

    def test_validator_retains_employer_bullets_when_order_swapped(self):
        """
        Regression Test 1: Validator matches experiences by normalized (company, title) key
        so each employer retains its own tailored bullets even when tuned_exps order is swapped
        relative to master_exps, and sorts chronologically via date parsing.
        """
        _, master_parsed = FileLoaderService.get_master_resume()
        master_exps = master_parsed["experiences"]
        self.assertGreaterEqual(len(master_exps), 2)

        exp_0 = master_exps[0]
        exp_1 = master_exps[1]

        # Swap order relative to master_exps and attach distinct employer-specific bullets
        swapped_tuned = [
            TunedExperience(
                company=exp_1["company"],
                title=exp_1["title"],
                date_range=exp_1["date_range"],
                location=exp_1["location"],
                bullets=[f"Unique tailored bullet specifically for {exp_1['company']}"]
            ),
            TunedExperience(
                company=exp_0["company"],
                title=exp_0["title"],
                date_range=exp_0["date_range"],
                location=exp_0["location"],
                bullets=[f"Unique tailored bullet specifically for {exp_0['company']}"]
            ),
        ]

        stage2 = Stage2CustomizationResult(
            tailored_summary="Operations Coordinator with 3+ years experience.",
            skill_categories=[SkillCategory(category_name="Core Competencies", skills=["BMS/BAS Controls"])],
            experiences=swapped_tuned,
            slot1_title="Preventative Maintenance & BMS Compliance Tracking",
            slot1_bullets=["Project bullet 1"],
            slot2_title="Commercial Facilities Workflow & Dispatch Optimization",
            slot2_bullets=["Project bullet 2"],
            slot2_is_proposed=False
        )

        validated, _ = ResumeValidator.validate_and_sanitize(master_parsed, stage2)
        by_company = {e.company: e for e in validated.experiences}
        self.assertIn(f"Unique tailored bullet specifically for {exp_0['company']}", by_company[exp_0["company"]].bullets[0])
        self.assertIn(f"Unique tailored bullet specifically for {exp_1['company']}", by_company[exp_1["company"]].bullets[0])

        # Also verify reverse-chronological sorting places Apr 2026 - Present first
        self.assertIn("2026", validated.experiences[0].date_range)
        self.assertIn("2023", validated.experiences[1].date_range)

    def test_parser_preserves_commas_inside_parentheses(self):
        """
        Regression Test 2: MasterResumeParser.parse keeps 'Work Order Management (MRI Angus, WPM Plus)'
        intact as a single skill item without splitting on commas inside parentheses.
        """
        _, parsed = FileLoaderService.get_master_resume()
        all_skills = [s for cat in parsed["skills"] for s in cat["skills"]]
        self.assertIn("Work Order Management (MRI Angus, WPM Plus)", all_skills)
        self.assertNotIn("WPM Plus)", all_skills)

    def test_builtin_sample_jds_end_to_end(self):
        """
        Regression Test 3: End-to-end run on both built-in SAMPLE_JDS ('facilities' and 'cloud')
        verifying clean role titles, role_family, and Facilities Operations project selection.
        """
        sample_facilities_jd = """Job Title: Commercial Facilities Operations Coordinator & Building Automation Specialist
Location: Vancouver / Surrey, BC (On-Site)

About the Role:
We are seeking a proactive, technically skilled Operations Coordinator and Building Systems Specialist to oversee daily facility operations, preventative maintenance, and computerized building management systems (BMS/BAS) across a flagship commercial real estate portfolio. You will act as the operational bridge between on-site mechanical/electrical systems, trade contractors, and digital work-order tracking platforms.

Key Responsibilities:
- Conduct daily building rounds, inspect mechanical rooms (boilers, chillers, cooling towers, AHUs, pumps), and log system parameters.
- Monitor and adjust Building Automation Systems (BAS/BMS) to optimize HVAC performance, energy efficiency, and tenant comfort.
- Manage computerized maintenance management systems (CMMS) such as MRI Angus and WPM Plus to dispatch work orders, track preventative maintenance schedules, and coordinate external HVAC, plumbing, and electrical contractors.
- Lead on-site emergency response protocols, life-safety system inspections, fire alarm drills, and Occupational Health & Safety (OH&S / JOHSC) compliance.
- Utilize data analytics and reporting tools (SQL, Power BI, Excel, Python scripts) to track incident trends, vendor SLAs, and maintenance KPIs.

Required Qualifications:
- 2 to 4+ years of hands-on experience in commercial building operations, facility supervision, security operations, or technical coordination.
- Strong working knowledge of HVAC, mechanical/electrical troubleshooting, plumbing repairs, life safety systems, and BMS/BAS controls.
- Proven experience with work order management platforms (Angus, WPM Plus, or enterprise ticketing systems).
- Valid Occupational First Aid (OFA Level 1) certification and clean BC Driver's License with reliable vehicle.
- Technical degree or diploma in Computer Information Systems, Building Engineering, or related technical field is a strong asset."""

        sample_cloud_jd = """Job Title: Senior Cloud & Distributed Systems Software Engineer
Location: Vancouver, BC / Hybrid

About the Role:
We are looking for a Systems & Cloud Infrastructure Engineer to architect, deploy, and secure scalable backend platforms and automated data pipelines. You will work closely with engineering and security teams to maintain 99.99% uptime across Kubernetes clusters, Azure/AWS cloud environments, and real-time analytics dashboards.

Key Responsibilities:
- Design, deploy, and maintain containerized microservices and CI/CD pipelines using Docker, Kubernetes, and GitLab.
- Automate cloud security posture auditing, identity governance (Active Directory, Azure RBAC), and network compliance checks using Python and REST APIs.
- Build and optimize end-to-end data ingestion pipelines and interactive executive dashboards using SQL, Python, and Power BI.
- Troubleshoot distributed network protocols, VPN connectivity, Linux/Windows server infrastructure, and high-concurrency backend workloads.
- Write clean, well-tested, maintainable code with comprehensive unit and integration test coverage.

Required Qualifications:
- Bachelor's degree in Computer Information Systems, Computer Science, or equivalent practical experience (strong academic standing preferred).
- Strong proficiency in Python, SQL, Bash/PowerShell, and modern Git workflows.
- Hands-on experience with Docker, Kubernetes, Azure or AWS cloud services, and automated CI/CD pipelines.
- Solid foundation in networking protocols, system administration, and cloud security best practices."""

        res_fac = AIResumeOrchestrator.tailor_resume(sample_facilities_jd)
        self.assertEqual(
            res_fac.analysis["target_role_title"],
            "Commercial Facilities Operations Coordinator & Building Automation Specialist"
        )
        self.assertEqual(res_fac.analysis["role_family"], "facilities")
        projects_by_id = {p.id: p for p in FileLoaderService.get_project_catalog()}
        slot1_fac = projects_by_id[res_fac.analysis["slot1_project_id"]]
        self.assertEqual(slot1_fac.domain, "Facilities Operations")

        res_cloud = AIResumeOrchestrator.tailor_resume(sample_cloud_jd)
        self.assertEqual(
            res_cloud.analysis["target_role_title"],
            "Senior Cloud & Distributed Systems Software Engineer"
        )
        self.assertEqual(res_cloud.analysis["role_family"], "software_it")
        slot1_cloud = projects_by_id[res_cloud.analysis["slot1_project_id"]]
        self.assertNotEqual(slot1_cloud.domain, "Facilities Operations")

    def test_gemini_client_parses_raw_api_fixture_into_stage2_result(self):
        """
        Regression Test 4: GeminiLLMClient parses a recorded raw Gemini API JSON fixture into a
        valid Stage2CustomizationResult, passes the API key via x-goog-api-key header (never params),
        and includes responseSchema in generationConfig.
        """
        _, master_parsed = FileLoaderService.get_master_resume()
        projects = FileLoaderService.get_project_catalog()
        stage1 = Stage1AnalysisResult(
            target_role_title="Building Operations Coordinator",
            target_company="QuadReal",
            role_family="facilities",
            key_technical_requirements=["BMS/BAS Controls", "MRI Angus", "HVAC"],
            key_responsibilities=["Conduct daily building rounds"],
            slot1_project_id="preventative_maintenance_bms_tracking",
            slot1_rationale="Direct facilities alignment.",
            slot2_is_proposed=False,
            slot2_project_id="commercial_facilities_workflow_optimization",
            slot2_rationale="Complementary CMMS project."
        )

        stage2_payload = {
            "tailored_summary": "Building Operations Coordinator with 3+ years of commercial operations experience.",
            "skill_categories": [
                {"category_name": "Core Competencies", "skills": ["BMS/BAS Controls", "Work Order Management (MRI Angus, WPM Plus)"]}
            ],
            "experiences": [
                {
                    "company": exp["company"],
                    "title": exp["title"],
                    "date_range": exp["date_range"],
                    "location": exp["location"],
                    "bullets": ["Conducted daily building rounds inspecting chillers, boilers, and AHUs."]
                }
                for exp in master_parsed["experiences"]
            ],
            "slot1_title": "Preventative Maintenance & BMS Compliance Tracking",
            "slot1_technologies": ["BMS/BAS", "MRI Angus", "Python"],
            "slot1_bullets": ["Automated preventative maintenance tracking across commercial properties."],
            "slot2_title": "Commercial Facilities Workflow & Dispatch Optimization",
            "slot2_technologies": ["WPM Plus", "Power BI", "SQL"],
            "slot2_bullets": ["Optimized trade contractor dispatch and SLA compliance."],
            "slot2_is_proposed": False
        }

        raw_gemini_api_fixture = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": json.dumps(stage2_payload)}
                        ],
                        "role": "model"
                    },
                    "finishReason": "STOP"
                }
            ]
        }

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = raw_gemini_api_fixture

        client = GeminiLLMClient(api_key="AIzaTestHeaderOnlyKey", model="gemini-2.5-flash")
        with patch("backend.llm.gemini.requests.post", return_value=mock_resp) as mock_post:
            result = client.customize_sections(
                "Job Title: Building Operations Coordinator\nInspect chillers, boilers, BMS/BAS, MRI Angus.",
                master_parsed,
                stage1,
                projects
            )
            self.assertIsInstance(result, Stage2CustomizationResult)
            self.assertEqual(result.slot1_title, "Preventative Maintenance & BMS Compliance Tracking")
            self.assertEqual(len(result.experiences), len(master_parsed["experiences"]))

            # Verify API key was sent via header and NOT URL params
            _, call_kwargs = mock_post.call_args
            self.assertEqual(call_kwargs["headers"].get("x-goog-api-key"), "AIzaTestHeaderOnlyKey")
            self.assertNotIn("params", call_kwargs)
            self.assertIn("responseSchema", call_kwargs["json"]["generationConfig"])

    def test_project_catalog_loads_github_url(self):
        """Verify that FileLoaderService indexes github_url and github_repo metadata."""
        projects = FileLoaderService.get_project_catalog()
        projects_by_id = {p.id: p for p in projects}
        
        self.assertIn("gitlab_k8s_platform", projects_by_id)
        k8s = projects_by_id["gitlab_k8s_platform"]
        self.assertEqual(k8s.github_url, "https://github.com/SidhuManbirSingh/SELF-HOSTED-GITLAB-CE-KUBERNETES")
        self.assertEqual(k8s.github_repo, "SELF-HOSTED-GITLAB-CE-KUBERNETES")

        self.assertIn("cotton_weed_ai_pipeline", projects_by_id)
        cotton = projects_by_id["cotton_weed_ai_pipeline"]
        self.assertEqual(cotton.github_url, "https://github.com/SidhuManbirSingh/Cotton-Weed-Prediction-Model")

    def test_markdown_assembler_appends_project_github_links(self):
        """Verify MarkdownAssembler appends | [GitHub](url) to project headers when available."""
        _, master_parsed = FileLoaderService.get_master_resume()
        customized = Stage2CustomizationResult(
            tailored_summary="Experienced coordinator.",
            skill_categories=[],
            experiences=[],
            slot1_title="Self-Hosted GitLab CI/CD Platform on Kubernetes",
            slot1_bullets=["Configured PostgreSQL on Kubernetes."],
            slot1_github_url="https://github.com/SidhuManbirSingh/SELF-HOSTED-GITLAB-CE-KUBERNETES",
            slot2_title="Targeted Prototype Dispatch System",
            slot2_bullets=["Built dispatch queues."],
            slot2_is_proposed=True
        )
        md = MarkdownAssembler.assemble(master_parsed, customized)
        self.assertIn("### Self-Hosted GitLab CI/CD Platform on Kubernetes | [GitHub](https://github.com/SidhuManbirSingh/SELF-HOSTED-GITLAB-CE-KUBERNETES)", md)
        self.assertIn("### Targeted Prototype Dispatch System (Under Development)", md)

    def test_pdf_project_header_renders_clickable_blue_link(self):
        """Verify PDF generator renders project headers with clickable blue [GitHub] link annotations."""
        test_md = """# Candidate Name
City, BC | email@test.com | [LinkedIn](https://linkedin.com/in/test)

## Projects
### Self-Hosted GitLab CI/CD Platform on Kubernetes | [GitHub](https://github.com/SidhuManbirSingh/SELF-HOSTED-GITLAB-CE-KUBERNETES)
- Architected Kubernetes CI/CD platform across 75 commits.

### Preventative Maintenance & BMS Compliance Tracking (Under Development)
- Built automated compliance tracking logs.
"""
        pdf_bytes = ATSResumePDFGenerator.markdown_to_pdf_bytes(test_md)
        pdf_str = pdf_bytes.decode("latin1", errors="ignore")
        
        # Verify link annotation pointing to GitHub repo exists
        self.assertIn("/Subtype /Link", pdf_str)
        self.assertIn("https://github.com/SidhuManbirSingh/SELF-HOSTED-GITLAB-CE-KUBERNETES", pdf_str)
        # Verify blue color is used for link text
        self.assertIn("0.05 0.40 0.85 rg", pdf_str)
        # Verify project header title is rendered
        self.assertIn("(Self-Hosted GitLab CI/CD Platform on Kubernetes)", pdf_str)

    def test_slot2_placeholder_replaces_project_title_and_bullet(self):
        """Regression test verifying that placeholder 'Project Title' and 'bullet' are never leaked."""
        _, master_parsed = FileLoaderService.get_master_resume()
        raw_stage2 = Stage2CustomizationResult(
            tailored_summary="Experienced operations coordinator.",
            skill_categories=[],
            experiences=[
                TunedExperience(
                    company="GuardTeck Security Corp.",
                    title="Security Supervisor, Acting Assistant Manager",
                    date_range="Feb 2023 - Present",
                    location="Surrey, BC",
                    bullets=["Conducted daily building rounds."]
                )
            ],
            slot1_title="Preventative Maintenance & BMS Compliance Tracking",
            slot1_bullets=["Designed automated compliance tracking logs."],
            slot2_title="Project Title",
            slot2_bullets=["bullet"],
            slot2_is_proposed=False
        )
        validated, warnings = ResumeValidator.validate_and_sanitize(
            master_parsed,
            raw_stage2,
            job_description="Plumbing and HVAC service coordinator / dispatcher role."
        )
        self.assertNotIn("Project Title", validated.slot2_title)
        self.assertIn("(Under Development)", validated.slot2_title)
        self.assertTrue(len(validated.slot2_bullets) >= 2)
        for b in validated.slot2_bullets:
            self.assertNotEqual(b.strip().lower(), "bullet")
            self.assertTrue(len(b) > 20)

if __name__ == "__main__":
    unittest.main()
