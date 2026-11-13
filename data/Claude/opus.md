# Resume Tailor: Independent Code Review

**Reviewer:** Claude Opus (read-only review)
**Date:** 2026-11-10
**Scope:** The whole repository: backend, frontend, data, tests, Docker, docs
**Ground rules:** I changed no source files and made no commits. This file is the only thing I added to the repo. I ran one read-only probe script, kept outside the repo at `C:\Users\manbi\.gemini\antigravity\brain\01457966-ae82-4094-9436-a91651feb3da\scratch\review_probe.py`, so I could check my claims instead of guessing.

---

## 1. Summary

The idea is good and the architecture is mostly sound, but the code under it is fragile. It is overfit to one resume, and several "guarantees" in the UI and README are not actually enforced.

| Area | Score | One-line reason |
|---|---|---|
| Product idea / UX concept | **8/10** | Has a fixed master resume, separates the LLM from rendering, shows a diff, and adds a cover letter and outreach messages. Better thought out than most hobby resume tools. |
| Architecture (shape) | **7/10** | The two-stage LLM pipeline, Pydantic schemas, validator, and deterministic renderer are the right design. |
| Implementation correctness | **4/10** | I confirmed 5 real bugs by running the code, and 3 of them show up in the app's own sample job descriptions. |
| Maintainability | **4/10** | Candidate facts are hardcoded in about 6 places. `llm_client.py` is a 1,078-line god file. Many fixes are keyword patches. |
| Security (local app) | **5/10** | Fine for a single user on localhost, but there is one real API-key leak path, plus LAN exposure and XSS. |
| Tests | **3/10** | 19 tests pass in 0.05 s, but they mostly check the mock's hardcoded strings against themselves. None of the bugs below are caught. |
| Docs | **3/10** | The README describes an older version of the project and contradicts the code in several places. |

**Overall: about 5.5/10 as engineering, about 7/10 as a personal tool that works today.** It's a solid prototype. It needs roughly 1–2 focused days to make its claims true.

---

## 2. What's genuinely good

These are worth keeping:

1. **Separating "AI produces data" from "code renders the document."** The LLM returns structured JSON (`Stage1AnalysisResult`, `Stage2CustomizationResult`). A deterministic assembler and PDF writer do the layout. This is the most important design decision in the project, and it is correct.
2. **Two-stage pipeline.** Stage 1 analyzes the job and picks projects. Stage 2 customizes the resume. Splitting it this way keeps each prompt focused and makes failures easier to debug.
3. **An invariance validator exists at all.** Restoring company, title, and dates from the master is the right instinct. (It has a bug, see §3.3, but the idea is right.)
4. **Pure-Python PDF writer with real vector text.** It has no dependencies on wkhtmltopdf or Chrome, ATS parsers can extract the text, and it adds clickable `/Link` annotations. Recent changes added real Helvetica AFM widths, which fixed the line-wrapping problem properly.
5. **Provider abstraction.** Mock, Gemini, Anthropic, and OpenAI all share `BaseLLMClient`. The prompts were recently moved into shared builders (`_build_stage1_prompts`, `_build_stage2_prompts`), so all providers get the same instructions.
6. **Filename sanitization.** CRLF and path-traversal protection on download filenames is something many projects forget.
7. **No build step on the frontend.** Plain HTML, CSS, and JS served same-origin by FastAPI, so it's easy to run.
8. **The Docker compose file mounts master and projects read-only (`:ro`).** This is a thoughtful touch.

---

## 3. Bugs I confirmed by running the code

All of these come from the probe script, using the app's own built-in sample job descriptions.

### 3.1 Mock mode puts a sentence from the job posting in the summary headline

`llm_client.py` line 64:

```python
title_match = re.search(r'(?:title|position|role):\s*([^\n\r,]+)', job_description, re.IGNORECASE)
```

`\s*` also matches newlines, and `role:` matches **"About the Role:"**. With the built-in **Facilities / Ops** sample, the "target role" becomes:

> `We are seeking a Commercial Facilities Operations Coordinator to supervise building control systems (BAS/BMS)`

The professional summary then reads: *"We are seeking a Commercial Facilities Operations Coordinator to supervise building control systems (BAS/BMS) with over 3 years of hands-on…"*. The download filename is built from the same string.

The same pattern is in the mock cover letter (line 346) and mock outreach (line 438).

**Fix:** anchor the pattern to the start of a line, `^(?:job\s+)?(?:title|position)\s*:[ \t]*(.+)$` with `re.M`, and drop `role`.

> Note: this regex was introduced earlier in this same conversation, during the "ATS prompt" change. That's on the assistant, not on you.

### 3.2 Every software job with the word "database" gets treated as a facilities job

The facilities detector does substring matching on `"bas"` and `"bms"` (lines 85, 194, 352, 444). `"bas"` is inside **data*bas*e**, **bas**ic, **bas**h, **bas**ed.

Probe result for the built-in **Cloud / Systems** sample:

> SUMMARY: *"…Senior Systems Engineer… with over 3 years of hands-on commercial property operations experience, paired with leadership as an Acting Assistant Manager and Security Supervisor…"*

So in mock mode, a cloud job gets a facilities summary.

**Fix:** match whole words (`\b(bas|bms)\b`), or better, have Stage 1 return a `role_family` field and branch on that.

### 3.3 The validator can attach bullets to the wrong job (silently)

`validator.py` line 52 pairs master and tailored experiences **by position**:

```python
for i, (m_exp, t_exp) in enumerate(zip(master_exps, tuned_exps)):
```

If the LLM returns the same two jobs in a different order (which the prompt practically invites, since it talks about reordering), the validator "restores" each company, title, and date onto the other job's bullets. Probe result:

```
ULO Real Estate LLC      | Information Technology Coordinator | ['BULLET-FROM::GuardTeck Security Corp.']
GuardTeck Security Corp. | Security Supervisor, ...           | ['BULLET-FROM::ULO Real Estate LLC']
```

The result is security and mechanical-room bullets under the IT job, and IT bullets under GuardTeck. The headers look "valid", so nobody notices.

**Fix:** match each tailored experience to its master entry by normalized company (and title), not by index. Fall back to master bullets when nothing matches.

### 3.4 The skill parser splits on commas inside parentheses

`file_loader.py` line 76: `items.split(",")`. Master skills such as:

- `Work Order Management (MRI Angus, WPM Plus)`
- `Mechanical & electrical troubleshooting (pumps, motors, boilers, cooling towers, chillers, AHUs)`

become fragments: `Work Order Management (MRI Angus` and `WPM Plus)`. The mock then sorts fragments that match the job to the front, and the tailored resume ships with:

> **Platforms & Operations:** WPM Plus), Elevating Devices, Job Hazard Assessments (JHA), Work Order Management (MRI Angus, …

Gemini, Claude, and OpenAI also receive these broken fragments as input in `master_parsed['skills']`, so this affects every provider, not just mock.

**Fix:** split only on commas that are outside parentheses, e.g. `re.split(r',\s*(?![^()]*\))', items)`.

### 3.5 Your most relevant facilities projects are dropped from every tailored resume

The master has a `## RELEVANT OPERATIONS PROJECTS` section (*Preventative Maintenance & BMS Compliance Tracking*, *Commercial Facilities Workflow & Service Contract Optimization*). The parser (`file_loader.py`) has no branch for that heading, so the section is ignored completely.

The Projects section of the tailored resume is filled only from `data/projects/`, which holds your GitHub software projects. Probe result for the **facilities** sample:

> SLOTS: `Canadian Labor Market AI Exposure Map Dashboard`, `Azure Cloud Security & Compliance Auditor`

So a building-operations resume shows an AI dashboard and an Azure auditor as its projects, while the two projects actually about BMS and work orders never appear.

**Fix (easy):** move the two operations projects into `data/projects/` as their own `.md` files with `domain: Facilities Operations`. The ranker will pick them for facilities jobs.

### 3.6 "Reset to generated" in the editor does nothing

In `app.js` (line 224), every keystroke in the editor overwrites `state.tailoredMarkdown`. The reset button (line 230) then "resets" to that same value. The original LLM output is gone after the first edit.

**Fix:** keep a separate `state.generatedMarkdown` that only the generate call writes to.

---

## 4. Security findings

These are ordered by how much I'd care about them for a tool that runs on your laptop.

### 4.1 Your Gemini API key can show up in a browser alert (real leak path)

- `GeminiLLMClient._call_gemini` sends the key as a **URL query parameter** (`params={"key": ...}`, line 715).
- When `requests` fails at the network level (DNS failure, timeout, connection reset), its exception message includes the full URL, query string and all: `...:generateContent?key=AIza...`.
- `main.py` line 97 returns `detail=f"Tailoring failed: {str(e)}"` to the client, and the frontend shows `detail` in an `alert()`.

This leak happens on ordinary network failures like DNS or Wi-Fi drops, not just in unusual situations. The `NameResolutionError` seen earlier in this conversation's sandbox runs is exactly this kind of error.

**Fix:**
1. Send the key in the `x-goog-api-key` header instead.
2. Never return `str(e)` to the client. Log it on the server and return a generic message.

### 4.2 The server is reachable from your whole network, and any website can call it

- `main.py` line 185 binds to **`0.0.0.0`**. On café or school Wi-Fi, anyone on the same network can `GET /api/resume/master` (your phone number and email) and `POST /api/tailor` to spend your Gemini quota.
- CORS is `allow_origins=["*"]` with `allow_credentials=True` (line 40). Any website you visit can make requests to `localhost:8000` and read the responses. The frontend is served from the same origin, so **you don't need CORS at all.**

**Fix:** bind to `127.0.0.1` and remove the CORS middleware (or restrict it to `http://127.0.0.1:8000`).

### 4.3 Stored XSS in the resume preview

In `app.js` line 408, bullet text goes into `innerHTML` without escaping (only the `**bold**` replacement is applied). Bullet text comes from LLM output, which a pasted job description can influence. Job postings can contain hidden text, so a malicious posting could plant something like `<img src=x onerror=...>`.

**Fix:** call `escapeHtml(bulletText)` first, then apply the bold replacement.

### 4.4 Prompt injection: the defenses are weaker than the README says

- `sanitize_job_description` only neutralizes the exact lowercase `</job_description>`. `</JOB_DESCRIPTION>` or `</job_description >` get through.
- More importantly, `_build_stage2_prompts` puts `stage1_result.target_role_title`, a value **the LLM derived from the job description**, directly into the **system prompt** (lines 884, 926). That moves job-posting text into system-level instructions.
- `additional_notes` is appended **after** sanitization, so it isn't length-checked or neutralized.

For a personal tool this risk is low. But the README's claim of "strict delimiters… treated strictly as text" is stronger than what's implemented.

### 4.5 Misconfiguration silently falls back to mock

`get_llm_client()` falls back to `MockLLMClient()` whenever a key is missing (lines 1067, 1078). `/api/health` reports `settings.LLM_PROVIDER` (for example "gemini"), **not the client actually in use**. In Docker this happens by default: compose never passes `GEMINI_API_KEY`. You can believe you're getting Gemini output while actually getting the canned template. I'd make a misconfiguration fail loudly, or at least make the header badge show the real client.

### 4.6 Personal information is committed to git

`data/master/Manbir-OPS-Resume.md` and `.pdf` are tracked. If the repo is ever pushed publicly, your phone number and email go with it. `.env` is correctly ignored, which is good.

---

## 5. Career and content concerns

This section is about the resume the tool produces, not the code. These are judgment calls, and you make the final decision on each.

1. **"Factual invariance" only covers headers.** The validator checks company, title, dates, and location. It does **not** check bullet content, the summary, or skills. The marketing text ("ZERO FABRICATION • 100% FACTUAL INVARIANCE" in the footer, and "Factual Accuracy Guaranteed") promises more than the code enforces. The 5th Class Power Engineering episode shows this: the prompt told the model to add a credential you don't have, and nothing stopped it. A cheap guard: reject any certification or license term in the output that doesn't appear in the master.

2. **Stage-2 prompt directive #4 still pushes content for every job.** It tells the model to "*ensure bullets and skills explicitly feature minor plumbing repairs, lamp/ballast replacement, filter and belt changes, drywall/painting…*" for **every** job description, including the Cloud / Systems one. Directive #5 always puts chillers and boilers into the GuardTeck bullets. The prompt is now tuned to one facilities posting. It should branch on role type.

3. **Using the target job title as your headline.** "Building Operations Coordinator & Assistant Facility Manager with over 3 years…" reads as though that's a title you have held. Your real titles are Security Supervisor / Acting Assistant Manager and IT Coordinator. This helps keyword matching, but a hiring manager comparing the headline to your experience may see it as title inflation. A safer version that keeps most of the ATS benefit: *"Facilities operations professional targeting Building Operations Coordinator roles, with 3+ years…"*. This is your call; I'm just pointing out the trade-off.

4. **Degree status is inconsistent.** Education says *"University of the Fraser Valley (Attended)"*, and you asked earlier to remove the dates. The cover letter and outreach templates (mock lines 357, 450, 464, 500) and the cover-letter system prompt say *"I recently completed my… degree"* / *"recent graduate."* If the degree isn't finished, those letters overstate it, and that kind of claim gets checked. Please confirm which is true and make all of them say the same thing.

5. **Certifications appear twice.** OFA Level 1 and the BC Driver's License appear in both *Mechanical, Electrical & Building Systems* (a skills line) and *Certifications & Licenses*. Pick one.

6. **Inconsistent casing in the skills section.** "CORE COMPETENCIES:" is rendered in all caps while the other categories are Title Case. The category name comes straight from the master's `## **CORE COMPETENCIES**` heading. You can see this in your own screenshot.

---

## 6. Architecture and maintainability

### 6.1 Candidate facts are hardcoded in about 6 places

Your name, phone number, email, GPA, Dean's List, employers, equipment list, and LinkedIn/GitHub URLs are written into:
- the mock summary / cover letter / outreach templates (`llm_client.py`)
- the cover-letter and outreach **system prompts**
- the Stage-2 system prompt ("Apr 2026", "GuardTeck", …)
- `validator.py` (`"2026"` / `"2023"` sorting, phrase-specific replacements)
- `pdf_generator.py` (`DEFAULT_LINKEDIN_URL`, `DEFAULT_GITHUB_URL`)
- `app.js` (hardcoded name, phone, LinkedIn in the outreach PDF header, LinkedIn/GitHub fallbacks)

The master resume is supposed to be the single source of truth, but it isn't. You've already seen what happens: removing "5th Class" meant hunting through three files. Every future change to a fact has the same cost. All of this should come from `master_parsed`.

### 6.2 Patch-style fixes that will break later

Several "fixes" are string patches aimed at one specific output:

- `validator.py` removes the exact phrases *"directly analogous to AI adoption facilitation with business stakeholders"* and *"(directly transferable to Angus and WPM Plus)"*. Neither phrase exists in the master any more, so these lines do nothing.
- `validator.py` line 97 sorts experiences by checking whether the date contains `"2026"` or `"2023"`. **This breaks the first time you add a 2027 job**, which would sort to the bottom. Parse the start date instead.
- Removing "Results-driven technology and professional" with a regex leaves the summary starting mid-sentence.
- The mock customizer special-cases `"GuardTeck" in company` and rewrites one bullet word for word.

Each one fixes the symptom you saw, not the cause. This is the most consistent pattern in the codebase.

### 6.3 The mock is not a mock

`MockLLMClient` is about 470 lines of handwritten, candidate-specific prose. It works as three things at once: an offline fallback, a test double, and a content template. Because the tests assert on its hardcoded strings, they test the mock against itself (see §7).

Recommended split:
- a **tiny, generic test double** (no personal facts)
- **recorded fixtures** of real Gemini responses for regression tests
- if you want an offline mode, label it clearly in the UI as "template mode"

### 6.4 `llm_client.py` is 1,078 lines

It holds four clients, the mock, five prompt builders, JSON extraction, and the factory. Splitting it into `clients/`, `prompts/`, and `mock.py` would make it much easier to work with. Also, Gemini supports `response_schema` for structured output, which would replace the "please output JSON" instructions plus `_extract_json`, and remove a whole class of parse failures. There's no retry on 429/503 either, which `gemini-2.5-flash` returns regularly under load.

### 6.5 The parser is heading-keyword driven

`MasterResumeParser` decides what a section is by keywords. Any heading containing "lead" (e.g., `## LEADERSHIP`) is treated as a job (line 94). Any heading it doesn't recognize is silently dropped, which is the cause of §3.5. I'd log a warning for unrecognized sections, or add a passthrough so they're kept as-is.

### 6.6 Dead code and dependencies

- `backend/templates/document/resume_print.html` is never used.
- `jinja2`, `aiofiles`, `pydantic-settings`, and `python-multipart` are in requirements but never imported.
- `OUTPUT_DIR` is configured but nothing is ever written there.
- `frontend/static/app.js` and `frontend/static/styles.css` are leftover redirect stubs.
- `strip_github_links` is now applied only to bullets, even though GitHub is supposed to be in the header. The README still says GitHub is stripped (Rule 4.8), which is the opposite of what you asked for.

---

## 7. Tests

- **19 tests, all passing, 0.05 s total, all on the mock provider.**
- The new facilities test checks that the summary starts with "Building Operations Coordinator…". The mock **hardcodes that sentence**, so the test proves only that the template contains its own text.
- **None of the 6 bugs in §3 are caught.** Each would have been found by one test that runs the app's own `SAMPLE_JDS` and checks basic sanity (summary doesn't start with "We are seeking", no unbalanced parentheses in skills, bullets stay with their company).
- There are no tests for the real provider path: prompt construction, parsing a recorded Gemini response, or failure handling (bad JSON, 429, timeout).

Five tests worth adding first:
1. Validator with swapped experience order → bullets stay with their company.
2. Parser with parenthesized comma lists → no unbalanced fragments.
3. Both built-in sample job descriptions → sane title, correct role family, the facilities job picks facilities projects.
4. Gemini client given a recorded fixture response → valid `Stage2CustomizationResult`.
5. An API error path → response `detail` never contains `key=`.

---

## 8. Frontend

**Good:** clear two-column workspace, tabs, a loading state, copy buttons, a word counter, and sensible download filenames (`Manbir - Role - Company.pdf`).

**Issues:**
- The XSS in §4.3 and the broken reset button in §3.6.
- The **diff tab doesn't show experience bullet changes**, which are the edits you most need to review. It shows the summary, skills, and projects. The "original" side for projects is a placeholder string. For a tool whose selling point is "targeted modification", this is the most important view and it's missing.
- The cover letter can't be edited. Only the resume has an editor.
- All errors appear in `alert()` boxes. The tabs have `role="tab"` but no `aria-selected` or keyboard handling.
- Leftover names: `loadSampleBackendBtn` loads the facilities sample, and `SAMPLE_JDS.backend` is the facilities job.
- Many inline styles in `index.html` and `app.js` despite the "decoupled from style sheets" comment.

---

## 9. PDF engine

**Good:** valid PDF 1.4 with a correct xref table, real text that can be extracted, centered header, blue clickable links, metric-based line wrapping, and page-break checks.

**Issues:**
- **ASCII only.** `_sanitize` replaces every non-ASCII character with a space. Any accented name, company, or city (é, ñ, ü) silently loses letters. The fix is to declare `/Encoding /WinAnsiEncoding` on the fonts and map Latin-1 characters instead of blanking them.
- URIs in link annotations aren't escaped. A `(` or `)` in a URL would corrupt the PDF.
- There's no `/Info` dictionary (Title / Author). Some ATS and email previews show this. It's about 5 lines to add.
- `line.lstrip("## ")` strips a **set of characters**, not a prefix. A heading like `## #1 Priority` would lose the `#1`. Use `removeprefix`.
- There is no widow/orphan control, so a job header can end up as the last line of a page with its bullets on the next page.

---

## 10. Docs and DevOps

- **The README is out of date.** It lists project files that don't exist (`cloud_cost_optimizer.md`, …), says GitHub links are stripped, refers to the old `(Targeted Implementation / Prototype)` badge, says mock is the default (but `.env.example` sets gemini), and doesn't document Gemini, which is the provider you actually use.
- **docker-compose** sets `MASTER_RESUME_PATH=/app/data/master/master_resume.md`, a file that doesn't exist. It only works because of the glob fallback in `file_loader`. It also never passes `GEMINI_API_KEY`, so Docker runs on mock without any warning (§4.5).
- There's no `.dockerignore`, and the build context includes `data/output`.
- `version: '3.8'` in compose is obsolete; current Docker Compose prints a warning about it.
- Git history: one "initial commit" plus uncommitted changes. Two project files (`stock-market-forecasting.md`, `community-event-cli.md`) are deleted but not committed. I assume that's intentional, but it's worth checking.

---

## 11. Patterns in the Gemini-built code

You asked how good the original build is. My read:

**Strengths:** it sets up a lot of structure quickly, follows your instructions closely, uses good default architecture (schemas, a validator, separated rendering), and writes clear docstrings and readable code. Each feature you asked for was delivered.

**Weaknesses:**
1. **It fixes the latest symptom, not the cause.** It patches specific phrases and specific years, and it only tests what was asked about.
2. **It hardcodes facts in many places instead of reading them from one source.** The data model drifts a little with each request.
3. **The tests confirm the code rather than challenge it.** They're written to pass against what was just built, not to find what's broken.
4. **The claims run ahead of the implementation.** "Guaranteed", "100% factual invariance", and "zero fabrication" go beyond what the validator actually checks.
5. **It doesn't run end-to-end checks after a change.** Three of the bugs in §3 appear with the built-in sample buttons. One run of each sample after each change would have caught them.

None of this is unusual for fast, request-by-request AI-assisted building. It's what happens when nobody steps back to look at the system as a whole.

---

## 12. Recommended fix order

| # | Fix | Why | Effort |
|---|---|---|---|
| 1 | Send the Gemini key in a header and stop returning `str(e)` to the client | Prevents key leak | 15 min |
| 2 | Bind to `127.0.0.1` and remove CORS | Stops LAN/web access to your PII and quota | 5 min |
| 3 | Escape bullet HTML in `renderMarkdownResume` | Fixes XSS | 5 min |
| 4 | Match experiences by company in the validator; parse dates for sorting | Prevents bullets attached to the wrong job | 30 min |
| 5 | Split skills only on commas outside parentheses | Fixes visible broken skills | 10 min |
| 6 | Move the two operations projects into `data/projects/` | Facilities resumes get relevant projects | 15 min |
| 7 | Anchor the title regex; whole-word facilities detection | Fixes the broken headline in mock mode | 20 min |
| 8 | Make the Stage-2 prompt branch on role family | Stops facilities keywords leaking into tech resumes | 45 min |
| 9 | Check that degree status matches across resume, cover letter, and outreach | Avoids a claim that can be checked and found wrong | 10 min (you decide) |
| 10 | Remove hardcoded candidate facts; read everything from `master_parsed` | Ends the 3-file hunt for every change | 2–3 h |
| 11 | Show experience-bullet changes in the diff tab | Makes the main selling point reviewable | 1 h |
| 12 | Add the 5 tests from §7, using real sample job descriptions | Catches regressions | 1–2 h |
| 13 | Rewrite the README to match the code | Docs match reality | 30 min |
| 14 | Use Gemini `response_schema` and add retry with backoff on 429/503 | Reliability | 1 h |

Items 1–7 take about **2 hours** and fix everything a recruiter or attacker could actually notice.

---

## 13. About me and usage limits

You asked about my usage limits. Here's what I can and can't tell you:

- **I can't see my account quota, rate limits, or remaining token budget.** That information isn't available to me inside the session, so I won't guess a number.
- **What I can describe are the per-tool limits in this environment:** each file read returns up to about 800 lines or about 45 KB, commands wait up to 10 s before moving to the background, and the terminal sandbox has no network access. That's why everything I verified here was offline, in mock mode.
- **What this review involved:** I read every source file in the repo (backend, frontend, tests, Docker, README, data). I ran one read-only probe that exercised the real pipeline with your built-in sample job descriptions and the validator. I hit no limits.

This review is also the evidence for how good I am, so hold me to it. Every bug in §3 comes with the exact line number, the probe output, and a specific fix.

