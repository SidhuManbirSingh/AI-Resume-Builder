import sys
from pathlib import Path

# Automatically add project root to Python path so running from inside backend/ works
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

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
from backend.services.pdf_generator import ATSResumePDFGenerator
from backend.core.security import sanitize_filename

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Intelligently tailor master resumes to job descriptions while preserving factual accuracy and structure."
)

# Enable CORS for external frontend or local dev tools
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health_check():
    """
    Status endpoint verifying system configuration and file availability.
    """
    master_exists = settings.MASTER_RESUME_PATH.exists()
    projects = FileLoaderService.get_project_catalog()
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "llm_provider": settings.LLM_PROVIDER,
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tailoring failed: {str(e)}")

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cover letter generation failed: {str(e)}")

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Outreach message generation failed: {str(e)}")

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

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
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
