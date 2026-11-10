# AI-Powered Resume Tailoring System

A web application that tailors an existing master resume to specific job descriptions with precision and factual fidelity.

Unlike generative resume tools that hallucinate employment history or rewrite documents from scratch, this system follows an **Invariable Baseline, Targeted Modification** paradigm:
- **Structural Invariance:** The master resume's layout, structure, company names, job titles, employment dates, and educational credentials are immutable.
- **Selective Customization:** Only targeted sections (Professional Summary, bullet point emphasis in Experience, Project Selection/Proposal, and Technical Skills grouping) are tuned.
- **Zero AI in Document Layout:** The AI outputs structured semantic data; a deterministic rendering engine compiles this into clean Markdown and an ATS-friendly, single-column PDF.
- **Mandatory Privacy & ATS Rules:** Automatic sanitization strips GitHub profile links (Rule 4.8) while preserving LinkedIn, email, and phone contacts.

---

## Architecture Overview

```
                      +-----------------------------+
                      |   Target Job Description    |
                      +--------------+--------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
|                       Stage 1: Semantic Analysis                         |
|  - Ingests Master Resume (read-only) & Project Catalog                   |
|  - Extracts top JD competencies & domain keywords                        |
|  - Evaluates catalog: Selects Slot 1 (Best Existing Project)             |
|  - Identifies gaps: Decides Slot 2 (Existing vs 1-2 Day Proposed Project)|
+------------------------------------+-------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
|                     Stage 2: Targeted Customization                      |
|  - Adapts Professional Summary for target alignment                      |
|  - Re-anchors Experience bullets (highlights transferable skills)        |
|  - Formats Project Slot 1 (existing factual work)                        |
|  - Formats Project Slot 2 (transparently labeled proposed project)       |
|  - Reorders Technical Skills categories based on JD relevance            |
+------------------------------------+-------------------------------------+
                                     |
                                     v
+--------------------------------------------------------------------------+
|                 Stage 3: Invariance Guardrails & Assembly                |
|  - Asserts exact match of employers, titles, and dates against master    |
|  - Strips GitHub profile URLs                                            |
|  - Enforces "(Targeted Implementation / Prototype)" badge on Slot 2     |
|  - Assembles ATS-friendly Markdown & computes visual section diffs       |
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

### Option 1: Run with Docker Compose (Recommended)

Requires Docker and Docker Compose installed.

1. **Clone and enter repository:**
   ```bash
   cd e:\resume-builder
   ```

2. **Copy environment variables:**
   ```bash
   cp .env.example .env
   ```
   *(By default, `LLM_PROVIDER=mock` is active, allowing full testing without external API keys. Set `LLM_PROVIDER=anthropic` or `openai` to use live models).*

3. **Launch the application:**
   ```bash
   docker compose up --build
   ```

4. **Access the web interface:**
   Open your browser to:
   [http://localhost:8000](http://localhost:8000)

5. **Stop the application:**
   ```bash
   docker compose down
   ```

---

### Option 2: Run Locally with Python

Requires Python 3.10+ (Python 3.12 verified).

1. **Install dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```

2. **Run the server:**
   ```bash
   python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
   ```

3. **Open the browser:**
   Navigate to [http://127.0.0.1:8000](http://127.0.0.1:8000).

---

## Project Structure

```
resume-builder/
├── docker-compose.yml              # Docker orchestration with read-only data mounts
├── Dockerfile                      # Production container build
├── .env.example                    # Environment variable configuration template
├── README.md                       # Documentation & setup guide
│
├── data/                           # Application Data Assets
│   ├── master/
│   │   └── master_resume.md        # The immutable master resume baseline
│   ├── projects/                   # Markdown project catalog with YAML frontmatter
│   │   ├── cloud_cost_optimizer.md
│   │   ├── event_stream_pipeline.md
│   │   ├── kubernetes_auto_scaler.md
│   │   └── rag_knowledge_search.md
│   └── output/                     # Generated tailored resumes (.md and .pdf)
│
├── backend/
│   ├── main.py                     # FastAPI REST API & static file mount
│   ├── requirements.txt            # Python dependencies
│   ├── core/
│   │   ├── config.py               # Settings & environment parser
│   │   └── security.py             # JD sanitization & GitHub link stripper (Rule 4.8)
│   ├── models/
│   │   └── schemas.py              # Pydantic schemas for LLM and API contracts
│   ├── services/
│   │   ├── file_loader.py          # Read-only master resume & project parser
│   │   ├── llm_client.py           # Multi-provider client (Mock, Anthropic, OpenAI)
│   │   ├── ai_orchestrator.py      # Multi-stage AI execution pipeline
│   │   ├── validator.py            # Factual invariance guardrails
│   │   ├── markdown_assembler.py   # Assembles ATS Markdown & generates visual diffs
│   │   └── pdf_generator.py        # Deterministic, pure-Python ATS PDF generator
│   ├── templates/
│   │   └── document/
│   │       ├── resume_print.html   # HTML/CSS Paged Media template
│   │       └── resume_print.css
│   └── tests/
│       ├── test_tailoring.py       # Unit tests for invariance rules & pipelines
│       └── test_api_endpoints.py   # Direct API route handler test suite
│
└── frontend/
    └── static/
        ├── index.html              # Kinetic poster layout & dual previews
        ├── css/
        │   └── kinetic.css         # Kinetic design system (authoritative tokens & styles)
        └── js/
            └── app.js              # Decoupled application logic controller
```

---

## Resume Customization & Preservation Rules

The system strictly enforces the mandatory constraints:

1. **Employment History Invariance:** Job titles, company names, employment dates, locations, and degree credentials are validated against the master resume and restored if any tampering occurs.
2. **Project Slots:**
   - **Slot 1 (Existing Project):** Ranked and selected from the `data/projects/` catalog based on JD semantic relevance.
   - **Slot 2 (Complementary Project):** If a required technology in the JD is missing from the existing catalog, proposes a realistic, 1–2 day deliverable explicitly badged as `(Targeted Implementation / Prototype)`. If existing projects already cover the tech stack strongly, selects a second existing project instead.
3. **Contact Sanitization (Rule 4.8):** All references matching `github.com/...` are automatically stripped from the contact header and body, while preserving LinkedIn, email, and phone numbers.
4. **ATS Friendly Layout:** Renders single-column standard headers (`Professional Summary`, `Technical Skills`, `Professional Experience`, `Projects`, `Education`) with selectable vector text.

---

## Configuration & LLM Providers

Edit `.env` to configure your preferred LLM provider:

### 1. Mock Engine (Default out-of-the-box)
```env
LLM_PROVIDER=mock
```
Runs locally with zero external API calls. Performs intelligent keyword matching, project ranking, and targeted tuning. Ideal for offline work and automated testing.

### 2. Anthropic Claude (Claude 3.5 Sonnet)
```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-api03-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
```

### 3. OpenAI (GPT-4o)
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
```

---

## Running the Automated Test Suite

Run the complete test suite:
```bash
python -m unittest discover -s backend/tests
```

This verifies:
- Read-only master resume ingestion
- YAML frontmatter project catalog parsing
- GitHub profile link stripping (Rule 4.8)
- Invariance validator restoring tampered employers/titles/dates
- Proposed project transparent labeling (Rule 3.C)
- Deterministic ATS PDF compilation
- Direct API endpoint handling

---

## Security & Local Development Considerations

1. **Volume Mount Safety:** In `docker-compose.yml`, `./data/master` and `./data/projects` are mounted with the `:ro` (read-only) flag, guaranteeing that the original files cannot be overwritten even if application code attempts a write operation.
2. **Indirect Prompt Injection:** User-submitted job descriptions are parsed with character limits and wrapped in strict `<job_description>` delimiters in the LLM prompts with explicit system instructions to treat content strictly as text data rather than instructions.
3. **API Key Isolation:** API keys remain strictly within `.env` on the host and are never exposed to client-side code.
