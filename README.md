# AI-Powered Resume Tailoring System

A local-first web application that tailors an existing master resume, cover letter, and outreach messages to specific job descriptions with strict factual fidelity and deterministic ATS-ready PDF compilation.

Unlike generative resume tools that hallucinate employment history or rewrite documents from scratch, this system follows an **Invariable Baseline, Targeted Modification** paradigm:
- **Structural Invariance:** The master resume's layout, company names, job titles, employment dates, and educational credentials are immutable and enforced by `ResumeValidator`.
- **Role-Family Aware Customization:** Automatically classifies postings into role families (`facilities`, `service_dispatch`, `software_it`, `security`, `general`) so tailoring rules, skill categories, and experience emphasis match the target domain without cross-contaminating keywords.
- **Zero AI in Document Layout:** The LLM outputs structured semantic JSON (validated against Pydantic and Gemini `responseSchema`); a pure-Python deterministic PDF engine (`ATSResumePDFGenerator`) compiles this into clean Markdown and an ATS-friendly single-column PDF with WinAnsiEncoding and clickable blue contact links.

---

## Architecture Overview

```
                      +-----------------------------+
                      |   Target Job Description    |
                      +--------------+--------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
|             Stage 0 & 1: JD Structuring & Semantic Analysis              |
|  - Strips raw job-board noise (headers, pay/benefits footers)            |
|  - Classifies role_family (facilities, service_dispatch, software_it)    |
|  - Evaluates catalog: Selects Slot 1 & Slot 2 from data/projects/        |
+------------------------------------+-------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
|                     Stage 2: Targeted Customization                      |
|  - Adapts Professional Summary opening with the exact target role title  |
|  - Tunes Experience bullets while preserving employer/title/date truth   |
|  - Selects & formats domain-aligned projects                             |
|  - Reorders Technical Skills categories (preserving parenthetical lists) |
+------------------------------------+-------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
|                 Stage 3: Invariance Guardrails & Assembly                |
|  - Matches experiences by normalized (company, title) key                |
|  - Sorts work history in reverse-chronological order via date parsing    |
|  - Strips unverified certifications not present in the master resume     |
|  - Assembles ATS-friendly Markdown & side-by-side section diffs          |
+------------------------------------+-------------------------------------+
                                     |
                  +------------------+------------------+
                  |                                     |
                  v                                     v
        +--------------------+                +--------------------+
        |  Interactive Web   |                | Deterministic PDF  |
        |  Editor & Previews |                | Engine (Pure Py)   |
        +--------------------+                +--------------------+
```

---

## Quickstart

### Option 1: Run Locally with Python

Requires Python 3.10+ (Python 3.12 verified).

1. **Install dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```

2. **Configure environment variables (`.env`):**
   ```env
   LLM_PROVIDER=gemini
   GEMINI_API_KEY=your_gemini_api_key
   GEMINI_MODEL=gemini-2.5-flash
   GEMINI_REASONING_API_KEY=your_optional_reasoning_key
   GEMINI_REASONING_MODEL=gemini-2.5-pro
   MASTER_RESUME_PATH=data/master/Manbir-OPS-Resume.md
   ```

3. **Run the server (bound to localhost `127.0.0.1`):**
   ```bash
   python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
   ```

4. **Open the browser:**
   Navigate to [http://127.0.0.1:8000](http://127.0.0.1:8000).

---

### Option 2: Run with Docker Compose

1. **Launch the application:**
   ```bash
   docker compose up --build
   ```

2. **Access the web interface:**
   Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

---

## Project Structure

```
resume-builder/
├── docker-compose.yml              # Docker orchestration bound to 127.0.0.1:8000
├── Dockerfile                      # Production container build
├── .dockerignore                   # Excludes .env, .git, caches, and output artifacts
├── README.md                       # Documentation & setup guide
│
├── scripts/
│   └── sync_github_projects.py     # CLI tool to check GitHub profile & sync recent projects
│
├── data/                           # Application Data Assets
│   ├── master/
│   │   ├── Manbir-OPS-Resume.md    # Primary operations & CIS master resume
│   │   └── master_resume.md        # Fallback template resume
│   ├── projects/                   # Markdown project catalog with YAML frontmatter
│   │   ├── preventative_maintenance_bms_tracking.md
│   │   ├── commercial_facilities_workflow_optimization.md
│   │   ├── gitlab_k8s_platform.md
│   │   ├── azure_cloud_security_auditor.md
│   │   ├── canadian_ai_exposure_dashboard.md
│   │   └── cotton_weed_ai_pipeline.md
│   └── output/                     # Generated tailored resumes (.md and .pdf)
│
├── backend/
│   ├── main.py                     # FastAPI REST API (localhost-bound, sanitized errors)
│   ├── requirements.txt            # Minimal Python dependencies
│   ├── core/
│   │   ├── config.py               # Settings & hot-reloading .env parser
│   │   └── security.py             # Prompt delimiter & filename sanitization
│   ├── llm/                        # Modular Multi-Provider LLM Package
│   │   ├── __init__.py             # Factory (get_llm_client) & exports
│   │   ├── base.py                 # BaseLLMClient & Stage 0 JD structurer
│   │   ├── prompts.py              # Role-family prompt builders & JSON schemas
│   │   ├── gemini.py               # Gemini client (x-goog-api-key header, responseSchema, retry)
│   │   ├── anthropic.py            # Anthropic Claude client
│   │   ├── openai.py               # OpenAI GPT-4o client
│   │   └── mock.py                 # Deterministic offline engine
│   ├── models/
│   │   └── schemas.py              # Pydantic schemas for LLM & API contracts
│   ├── services/
│   │   ├── file_loader.py          # Read-only master resume & project catalog parser
│   │   ├── llm_client.py           # Backward-compatible facade for backend.llm
│   │   ├── ai_orchestrator.py      # Multi-stage tailoring, cover letter & outreach orchestrator
│   │   ├── validator.py            # Factual invariance & certification guardrails
│   │   ├── markdown_assembler.py   # ATS Markdown assembly & side-by-side section diffs
│   │   └── pdf_generator.py        # Pure-Python ATS PDF generator (WinAnsiEncoding, /Info)
│   └── tests/
│       ├── test_tailoring.py       # Unit & regression tests for parser, validator, LLM, and PDF
│       └── test_api_endpoints.py   # API route & error-sanitization tests
│
└── frontend/
    └── static/
        ├── index.html              # Kinetic layout with Resume, Cover Letter, Outreach & Diffs
        ├── css/
        │   └── kinetic.css         # Kinetic design system
        └── js/
            └── app.js              # Frontend controller (XSS-hardened preview & state management)
```

---

## Running the Automated Test Suite

```bash
python -m unittest discover -s backend/tests
```

---

## Automatic GitHub Project Sync

The system automatically checks your GitHub profile (`SidhuManbirSingh`) on server startup:
- Fetches the last 5 recently updated/pushed repositories.
- Compares against existing projects in `data/projects/`.
- If a new project is detected, it scrapes the repository metadata, languages, and README, generates a resume-grade markdown project file with YAML frontmatter, and adds it to your catalog.
- Offline-safe: if network is unavailable, startup proceeds without disruption.

You can also run the sync manually at any time:
```bash
# Check last 5 projects (default)
python scripts/sync_github_projects.py

# Check custom limit or username
python scripts/sync_github_projects.py --limit 5 --username SidhuManbirSingh
```
Or trigger it via API:
```bash
curl -X POST http://127.0.0.1:8000/api/projects/sync-github
```
