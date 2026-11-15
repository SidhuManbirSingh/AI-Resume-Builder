import sys
from pathlib import Path

# Automatically add project root to Python path so running from inside backend/ works
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import logging
import os
from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

from backend.core.config import settings
from backend.models.schemas import (
    JobDescriptionRequest,
    TailoredResumeResponse,
    CoverLetterRequest,
    CoverLetterResponse,
    OutreachRequest,
    OutreachResponse,
    ExportRequest,
    ProjectMetadata
)
from backend.services.file_loader import FileLoaderService
from backend.services.ai_orchestrator import AIResumeOrchestrator
from backend.services.llm_client import get_llm_client
from backend.services.pdf_generator import ATSResumePDFGenerator
from backend.core.security import sanitize_filename

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Intelligently tailor master resumes to job descriptions while preserving factual accuracy and structure."
)

# Restrict CORS strictly to local same-host origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

@app.on_event("startup")
def startup_github_sync():
    """
    On application startup, checks the user's GitHub for recent projects (last 5)
    and syncs any newly added projects into data/projects/ automatically.
    """
    if getattr(settings, "AUTO_SYNC_GITHUB_PROJECTS", True):
        try:
            from backend.services.github_sync import sync_github_projects
            logger.info("Checking GitHub for newly added/updated projects on startup (User: %s)...", settings.GITHUB_USERNAME)
            new_projects = sync_github_projects()
            if new_projects:
                logger.info(
                    "GitHub Startup Sync: Created %d new project(s): %s",
                    len(new_projects), [p["title"] for p in new_projects]
                )
            else:
                logger.info("GitHub Startup Sync: All recent projects are up to date.")
        except Exception as e:
            logger.warning("GitHub project sync on startup skipped (offline or network error): %s", e)

@app.get("/api/health")
def health_check():
    """
    Status endpoint verifying system configuration, active LLM provider, and file availability.
    """
    master_exists = FileLoaderService.resolve_master_resume_path() is not None
    projects = FileLoaderService.get_project_catalog()
    llm_client = get_llm_client()
    active_provider = getattr(llm_client, "provider_name", settings.LLM_PROVIDER)
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "configured_provider": settings.LLM_PROVIDER,
        "active_provider": active_provider,
        "llm_provider": active_provider,
        "master_resume_loaded": master_exists,
        "projects_count": len(projects)
    }

@app.get("/api/resume/master")
def get_master_resume():
    """
    Retrieves the read-only master resume.
    """
    raw_markdown, parsed_structure = FileLoaderService.get_master_resume()
    return {
        "raw_markdown": raw_markdown,
        "parsed": parsed_structure
    }

@app.get("/api/projects")
def get_projects():
    """
    Returns the indexed project portfolio catalog.
    """
    projects = FileLoaderService.get_project_catalog()
    return {
        "count": len(projects),
        "projects": [p.model_dump() for p in projects]
    }

@app.post("/api/projects/sync-github")
def trigger_github_sync():
    """
    Manually triggers GitHub repository check and sync for new projects into data/projects/.
    """
    try:
        from backend.services.github_sync import sync_github_projects
        new_projects = sync_github_projects()
        all_projects = FileLoaderService.get_project_catalog()
        return {
            "status": "success",
            "new_projects_count": len(new_projects),
            "new_projects": new_projects,
            "total_catalog_count": len(all_projects)
        }
    except Exception:
        logger.exception("Failed to sync GitHub projects")
        raise HTTPException(status_code=500, detail="GitHub sync failed due to an internal error.")

@app.post("/api/tailor", response_model=TailoredResumeResponse)
def tailor_resume(request: JobDescriptionRequest):
    """
    Executes the multi-stage AI tailoring pipeline against the provided job description.
    """
    try:
        response = AIResumeOrchestrator.tailor_resume(
            raw_job_description=request.job_description,
            additional_notes=request.additional_notes
        )
        return response
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unhandled error during /api/tailor execution")
        raise HTTPException(
            status_code=500,
            detail="Tailoring failed due to an internal processing error. Please check server logs."
        )

@app.post("/api/tailor/cover-letter", response_model=CoverLetterResponse)
def tailor_cover_letter(request: CoverLetterRequest):
    """
    Generates a targeted, catchy, high-impact cover letter grounded in candidate facts and the target job description.
    """
    try:
        response = AIResumeOrchestrator.tailor_cover_letter(
            raw_job_description=request.job_description,
            tailored_markdown=request.tailored_markdown,
            additional_notes=request.additional_notes
        )
        return response
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unhandled error during /api/tailor/cover-letter execution")
        raise HTTPException(
            status_code=500,
            detail="Cover letter generation failed due to an internal processing error."
        )

@app.post("/api/tailor/outreach", response_model=OutreachResponse)
def tailor_outreach(request: OutreachRequest):
    """
    Generates tailored outreach messages (LinkedIn DM + Cold Email) grounded in candidate facts and the target JD.
    """
    try:
        response = AIResumeOrchestrator.tailor_outreach(
            raw_job_description=request.job_description,
            tailored_markdown=request.tailored_markdown,
            additional_notes=request.additional_notes
        )
        return response
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unhandled error during /api/tailor/outreach execution")
        raise HTTPException(
            status_code=500,
            detail="Outreach message generation failed due to an internal processing error."
        )

@app.post("/api/export/pdf")
def export_pdf(request: ExportRequest):
    """
    Deterministically compiles given Markdown text into an ATS-compliant PDF.
    """
    if not request.markdown_content or not request.markdown_content.strip():
        raise HTTPException(status_code=400, detail="Markdown content cannot be empty.")
    try:
        pdf_bytes = ATSResumePDFGenerator.markdown_to_pdf_bytes(request.markdown_content)
        safe_filename = sanitize_filename(request.filename, default_name="tailored_resume", extension=".pdf")
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{safe_filename}"'
            }
        )
    except Exception:
        logger.exception("Unhandled error during /api/export/pdf execution")
        raise HTTPException(status_code=500, detail="PDF generation failed due to an internal rendering error.")

@app.post("/api/export/markdown")
def export_markdown(request: ExportRequest):
    """
    Exports given Markdown text as a downloadable file.
    """
    if not request.markdown_content or not request.markdown_content.strip():
        raise HTTPException(status_code=400, detail="Markdown content cannot be empty.")
    safe_filename = sanitize_filename(request.filename, default_name="tailored_resume", extension=".md")
        
    return Response(
        content=request.markdown_content.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"'
        }
    )

# Static file serving for Frontend SPA
static_path = settings.STATIC_DIR
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    @app.get("/")
    def serve_frontend():
        index_file = static_path / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return HTMLResponse("<h1>AI Resume Tailor Backend API Running</h1><p>Frontend static files not found.</p>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
