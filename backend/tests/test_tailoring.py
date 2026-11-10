import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import unittest
from backend.services.file_loader import FileLoaderService, MasterResumeParser
from backend.core.security import strip_github_links, sanitize_job_description, sanitize_filename
from backend.services.validator import ResumeValidator, FactualInvarianceValidationError
from backend.services.ai_orchestrator import AIResumeOrchestrator
from backend.services.pdf_generator import ATSResumePDFGenerator
from backend.models.schemas import Stage2CustomizationResult, TunedExperience, SkillCategory
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

if __name__ == "__main__":
    unittest.main()
