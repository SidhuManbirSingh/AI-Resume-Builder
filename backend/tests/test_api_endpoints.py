import sys
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import unittest
from unittest.mock import patch
import requests
from fastapi import HTTPException
from backend.main import (
    health_check,
    get_master_resume,
    get_projects,
    trigger_github_sync,
    tailor_resume,
    tailor_cover_letter,
    tailor_outreach,
    export_pdf,
    export_markdown,
    serve_frontend
)
from backend.models.schemas import JobDescriptionRequest, CoverLetterRequest, OutreachRequest, ExportRequest
from backend.core.config import settings

class TestAPIEndpointsDirect(unittest.TestCase):

    def setUp(self):
        self._orig_provider = settings.LLM_PROVIDER
        settings.LLM_PROVIDER = "mock"

    def tearDown(self):
        settings.LLM_PROVIDER = self._orig_provider

    def test_health_endpoint(self):
        data = health_check()
        self.assertEqual(data["status"], "healthy")
        self.assertTrue(data["master_resume_loaded"])
        self.assertGreaterEqual(data["projects_count"], 3)

    def test_master_resume_endpoint(self):
        data = get_master_resume()
        self.assertIn("raw_markdown", data)
        self.assertTrue(len(data["raw_markdown"]) > 50)
        self.assertTrue(bool(data["parsed"]["name"]))

    def test_projects_endpoint(self):
        data = get_projects()
        self.assertGreaterEqual(data["count"], 3)
        self.assertTrue(len(data["projects"]) >= 3)

    def test_github_sync_endpoint(self):
        with patch("backend.services.github_sync.sync_github_projects", return_value=[]) as mock_sync:
            res = trigger_github_sync()
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["new_projects_count"], 0)
            self.assertGreaterEqual(res["total_catalog_count"], 3)
            mock_sync.assert_called_once()

    def test_tailor_endpoint_success(self):
        master_data = get_master_resume()
        req = JobDescriptionRequest(
            job_description="""
            Senior Systems and Infrastructure Software Engineer
            We need an engineer experienced with Python, Go, Docker, and Kubernetes.
            Responsibilities include optimizing microservices, cloud monitoring, and disaster recovery on AWS.
            Must have strong experience with distributed databases and high-volume message queues.
            """,
            additional_notes="Highlight Go and Kubernetes experience"
        )
        response = tailor_resume(req)
        self.assertIsNotNone(response.tailored_markdown)
        self.assertIn(master_data["parsed"]["name"], response.tailored_markdown)
        self.assertIn("github.com", response.tailored_markdown.lower())
        self.assertTrue(len(response.slots) == 2)
        self.assertTrue(len(response.diffs) >= 2)

    def test_tailor_endpoint_validation_error(self):
        req = JobDescriptionRequest(job_description="Too brief JD.")
        with self.assertRaises(HTTPException) as ctx:
            tailor_resume(req)
        self.assertEqual(ctx.exception.status_code, 400)

    def test_export_pdf_endpoint(self):
        req = ExportRequest(
            markdown_content="# Test Candidate\nSan Francisco, CA | test@email.com\n\n## Professional Summary\nExperienced engineer.\n\n## Education\nBS CS",
            filename="my_resume.pdf"
        )
        response = export_pdf(req)
        self.assertEqual(response.media_type, "application/pdf")
        self.assertTrue(response.body.startswith(b"%PDF"))

    def test_export_markdown_endpoint(self):
        content = "# Markdown Resume\n\n## Summary\nTest content"
        req = ExportRequest(
            markdown_content=content,
            filename="my_resume.md"
        )
        response = export_markdown(req)
        self.assertEqual(response.media_type, "text/markdown; charset=utf-8")
        self.assertEqual(response.body.decode("utf-8"), content)

    def test_tailor_cover_letter_endpoint(self):
        req = CoverLetterRequest(
            job_description="""
            Commercial Facilities Operations Coordinator
            Company: Apex Commercial Property Management
            Location: Vancouver / Surrey, BC
            Requirements:
            - 3+ years experience in commercial building operations
            - Knowledge of BMS/BAS control systems
            - Experience with work order management systems
            """
        )
        response = tailor_cover_letter(req)
        self.assertIsNotNone(response.cover_letter_markdown)
        self.assertIn("Manbir Singh Sidhu", response.cover_letter_markdown)
        self.assertIn("Apex Commercial", response.cover_letter_markdown)
        self.assertIn("Commercial Facilities Operations Coordinator", response.target_role_title)

    def test_tailor_outreach_endpoint(self):
        req = OutreachRequest(
            job_description="""
            Commercial Facilities Operations Coordinator
            Company: Apex Commercial Property Management
            Location: Vancouver / Surrey, BC
            Requirements:
            - 3+ years experience in commercial building operations
            - Knowledge of BMS/BAS control systems
            - Experience with work order management systems
            """
        )
        response = tailor_outreach(req)
        self.assertIsNotNone(response.linkedin_message)
        self.assertIsNotNone(response.email_subject)
        self.assertIsNotNone(response.email_body)
        self.assertIn("Manbir Singh Sidhu", response.linkedin_message)
        self.assertIn("Manbir Singh Sidhu", response.email_body)
        self.assertIn("Apex Commercial", response.linkedin_message)
        self.assertIn("Apex Commercial", response.email_body)
        self.assertIn("4.1 GPA", response.email_subject)
        self.assertIn("Commercial Facilities Operations Coordinator", response.target_role_title)

    def test_tailor_endpoint_sanitizes_network_exception_leak(self):
        """
        Regression Test 5: Simulated network exception during /api/tailor verifying the HTTP 500
        response detail never contains 'AIza' or 'key='.
        """
        settings.LLM_PROVIDER = "gemini"
        settings.GEMINI_API_KEY = "AIzaSySecretKeyLeakTest999"
        req = JobDescriptionRequest(
            job_description=(
                "Commercial Facilities Operations Coordinator\n"
                "We are seeking an experienced Building Operations Coordinator to inspect mechanical rooms, "
                "chillers, boilers, AHUs, and manage MRI Angus and WPM Plus work order dispatch."
            )
        )
        simulated_exc = requests.exceptions.ConnectionError(
            "HTTPSConnectionPool(host='generativelanguage.googleapis.com', port=443): "
            "Max retries exceeded with url: /v1beta/models/gemini-2.5-flash:generateContent?key=AIzaSySecretKeyLeakTest999"
        )
        with patch("backend.llm.gemini.requests.post", side_effect=simulated_exc):
            with self.assertRaises(HTTPException) as ctx:
                tailor_resume(req)
            self.assertEqual(ctx.exception.status_code, 500)
            detail = str(ctx.exception.detail)
            self.assertNotIn("AIza", detail)
            self.assertNotIn("key=", detail)

if __name__ == "__main__":
    unittest.main()
