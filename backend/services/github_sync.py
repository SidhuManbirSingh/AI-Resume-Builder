"""
GitHub Project Synchronization Service.

Automatically checks the user's GitHub profile for newly added or updated projects,
scrapes repository metadata and README documentation, formats resume-grade project
files with YAML frontmatter, and saves them to `data/projects/`.

Runs on application startup and can also be triggered on demand via CLI or API.
"""
import base64
import logging
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import requests
import yaml

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Known aliases mapping GitHub repository names to existing project IDs in data/projects/
KNOWN_REPO_ALIASES = {
    "cotton-weed-prediction-model": "cotton_weed_ai_pipeline",
    "self-hosted-gitlab-ce-kubernetes": "gitlab_k8s_platform",
    "canadian-ai-exposure": "canadian_ai_exposure_dashboard",
    "glossy-rides": "glossy_rides_web_app",
    "transaction-analyser-haskell": "haskell_transaction_analyzer",
}

# Frameworks, libraries, and tools to detect from README text
TECH_KEYWORD_PATTERNS = [
    ("Next.js (App Router)", r'\bnext\.js\s*(?:\(app\s*router\))?\b'),
    ("Next.js", r'\bnext\.js\b'),
    ("React", r'\breact(?:\s*1[89])?\b'),
    ("TypeScript", r'\btypescript\b'),
    ("Tailwind CSS", r'\btailwind(?:\s*css)?\b'),
    ("Prisma", r'\bprisma(?:\s*orm)?\b'),
    ("Radix UI", r'\bradix(?:\s*ui)?\b'),
    ("PostgreSQL", r'\bpostgres(?:ql)?(?:\s*1[456])?\b'),
    ("Docker", r'\bdocker\b'),
    ("Docker Compose", r'\bdocker\s*compose\b'),
    ("Kubernetes", r'\bkubernetes|k8s|minikube\b'),
    ("FastAPI", r'\bfastapi\b'),
    ("Flask", r'\bflask\b'),
    ("Python", r'\bpython(?:\s*3(?:\.\d+)?)?\b'),
    ("PyTorch", r'\bpytorch\b'),
    ("YOLOv8", r'\byolov8[a-z]?\b'),
    ("OpenCV", r'\bopencv\b'),
    ("Intel OpenVINO", r'\bopenvino\b'),
    ("Pandas", r'\bpandas\b'),
    ("NumPy", r'\bnumpy\b'),
    ("yfinance", r'\byfinance\b'),
    ("Quandl API", r'\bquandl\b'),
    ("Prometheus", r'\bprometheus\b'),
    ("Grafana", r'\bgrafana\b'),
    ("NGINX", r'\bnginx\b'),
    ("Cert-Manager", r'\bcert-manager\b'),
    ("Redis", r'\bredis\b'),
    ("Active Directory", r'\bactive\s*directory|entra\s*id\b'),
    ("Azure", r'\bazure\b'),
    ("REST APIs", r'\brest(?:ful)?\s*apis?\b'),
    ("SQL", r'\bsql\b'),
    ("Prolog", r'\bprolog\b'),
    ("Haskell", r'\bhaskell\b'),
]


def _normalize_name(name: str) -> str:
    """Normalizes string for fuzzy/alias comparisons."""
    return re.sub(r'[^a-z0-9]', '', (name or "").lower())


def is_repo_already_present(repo_name: str, projects_dir: Path) -> Tuple[bool, Optional[str]]:
    """
    Checks if a GitHub repository is already represented in data/projects/.
    Inspects existing project file names, frontmatter id, title, and github_repo fields.
    """
    repo_clean = repo_name.strip().lower()
    repo_norm = _normalize_name(repo_clean)
    
    # Check known alias map
    alias_id = KNOWN_REPO_ALIASES.get(repo_clean)
    
    if not projects_dir.exists():
        return False, None

    for f in projects_dir.glob("*.md"):
        f_norm = _normalize_name(f.stem)
        if f_norm == repo_norm:
            return True, f.name

        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    meta = yaml.safe_load(parts[1]) or {}
                    p_id = meta.get("id", "")
                    p_title = meta.get("title", "")
                    p_repo = meta.get("github_repo", "")

                    if alias_id and p_id == alias_id:
                        return True, f.name

                    if p_repo and _normalize_name(p_repo) == repo_norm:
                        return True, f.name

                    if p_id and _normalize_name(p_id) == repo_norm:
                        return True, f.name

                    # Token overlap: check if multiple significant words match
                    tokens = [w for w in re.split(r'[-_]', repo_clean) if len(w) > 3]
                    if tokens:
                        p_text_lower = f"{f.stem} {p_id} {p_title}".lower()
                        matches = sum(1 for tok in tokens if tok in p_text_lower)
                        if matches >= 2 and matches >= len(tokens) * 0.6:
                            return True, f.name
        except Exception:
            continue

    return False, None


def fetch_recent_github_repos(
    username: str,
    limit: int = 5,
    token: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Fetches the user's latest repositories from the GitHub API,
    ordered by most recent push date.
    """
    url = f"https://api.github.com/users/{username}/repos?sort=pushed&per_page=15"
    headers = {"User-Agent": "Resume-Builder-GitHub-Sync/1.0"}
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code != 200:
            logger.warning(
                "GitHub API returned HTTP %s for user '%s': %s",
                response.status_code, username, response.text[:200]
            )
            return []

        repos = response.json()
        if not isinstance(repos, list):
            return []

        # Filter out user profile README repository (e.g. SidhuManbirSingh/SidhuManbirSingh) and forks
        filtered = []
        for r in repos:
            r_name = r.get("name", "")
            if r_name.lower() == username.lower():
                continue
            if r.get("fork", False):
                continue
            filtered.append(r)

        return filtered[:limit]
    except Exception as e:
        logger.warning("Failed to connect to GitHub API for '%s': %s", username, e)
        return []


def scrape_repo_details(
    username: str,
    repo_name: str,
    token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Scrapes detailed metadata, languages, and README content for a specific repository.
    """
    headers = {"User-Agent": "Resume-Builder-GitHub-Sync/1.0"}
    if token:
        headers["Authorization"] = f"token {token}"

    base_url = f"https://api.github.com/repos/{username}/{repo_name}"

    details = {
        "repo_name": repo_name,
        "description": "",
        "html_url": f"https://github.com/{username}/{repo_name}",
        "languages": [],
        "topics": [],
        "readme_text": "",
        "pushed_at": "",
        "created_at": ""
    }

    # 1. Main repo metadata
    try:
        r_repo = requests.get(base_url, headers=headers, timeout=10)
        if r_repo.status_code == 200:
            data = r_repo.json()
            details["description"] = data.get("description") or ""
            details["html_url"] = data.get("html_url") or details["html_url"]
            details["topics"] = data.get("topics") or []
            details["pushed_at"] = data.get("pushed_at") or ""
            details["created_at"] = data.get("created_at") or ""
    except Exception as e:
        logger.debug("Failed to fetch repo metadata for %s: %e", repo_name, e)

    # 2. Languages breakdown
    try:
        r_lang = requests.get(f"{base_url}/languages", headers=headers, timeout=10)
        if r_lang.status_code == 200:
            lang_dict = r_lang.json()
            # Order languages by byte count
            details["languages"] = sorted(lang_dict.keys(), key=lambda k: lang_dict[k], reverse=True)
    except Exception as e:
        logger.debug("Failed to fetch languages for %s: %e", repo_name, e)

    # 3. README text
    try:
        r_readme = requests.get(f"{base_url}/readme", headers=headers, timeout=10)
        if r_readme.status_code == 200:
            data = r_readme.json()
            content_b64 = data.get("content", "")
            if content_b64:
                details["readme_text"] = base64.b64decode(content_b64).decode("utf-8", errors="ignore")
    except Exception as e:
        logger.debug("Failed to fetch README for %s: %e", repo_name, e)

    return details


def infer_domain(text: str, technologies: List[str]) -> str:
    """Infers an ATS-friendly engineering domain from content and technologies."""
    t_lower = (text + " " + " ".join(technologies)).lower()

    if any(k in t_lower for k in ["computer vision", "yolo", "yolov8", "opencv", "pytorch", "deep learning", "ai model", "drone"]):
        return "Computer Vision & Applied Machine Learning"
    if any(k in t_lower for k in ["stock", "financial", "dividend", "yfinance", "quandl", "ticker", "balance sheet", "debt-to-equity"]):
        return "Financial Data Engineering & Analytics"
    if any(k in t_lower for k in ["next.js", "react", "tailwind", "prisma", "radix", "frontend", "full-stack", "spa", "web application"]):
        return "Full-Stack Web Development"
    if any(k in t_lower for k in ["kubernetes", "k8s", "docker compose", "minikube", "ingress", "prometheus", "grafana", "ci/cd", "efk"]):
        return "Cloud Infrastructure & DevOps"
    if any(k in t_lower for k in ["azure", "iam", "cloud security", "nsg", "compliance", "auditing", "entra id"]):
        return "Cloud Security & Governance"
    if any(k in t_lower for k in ["prolog", "haskell", "functional programming", "decision"]):
        return "Functional & Logic Programming"
    if any(k in t_lower for k in ["bms", "bas", "hvac", "chillers", "boilers", "facilities"]):
        return "Facilities Operations"
    return "Software Engineering & Data Systems"


def parse_and_format_project(repo_details: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    """
    Parses scraped repository details and README into a production-ready project file:
    Returns (file_slug, markdown_content, metadata_dict).
    """
    repo_name = repo_details["repo_name"]
    readme = repo_details.get("readme_text", "")
    desc = repo_details.get("description", "")
    languages = repo_details.get("languages", [])
    topics = repo_details.get("topics", [])
    html_url = repo_details.get("html_url", "")

    # 1. Title Extraction
    title = ""
    for line in readme.splitlines():
        line_clean = line.strip()
        if line_clean.startswith("# "):
            raw_h1 = line_clean.removeprefix("# ").strip()
            # Strip badges, markdown links, or emojis
            raw_h1 = re.sub(r'\[!\[.*?\]\(.*?\)\]\(.*?\)', '', raw_h1)
            raw_h1 = re.sub(r'\[.*?\]\(.*?\)', '', raw_h1)
            raw_h1 = raw_h1.split("—")[0].strip() if "—" in raw_h1 and len(raw_h1) > 55 else raw_h1.strip()
            if len(raw_h1) >= 4:
                title = raw_h1
                break

    if not title:
        # Format repo name into clean Title
        clean_words = [w.capitalize() for w in re.split(r'[-_]', repo_name) if w]
        title = " ".join(clean_words)

    # 2. Technologies Extraction
    tech_detected = []
    # Add top languages
    for lang in languages[:5]:
        if lang not in tech_detected and lang not in ("Dockerfile", "CSS", "HTML"):
            tech_detected.append(lang)

    # Scan README and description for recognized frameworks
    combined_text = f"{title}\n{desc}\n{readme}"
    for label, pat in TECH_KEYWORD_PATTERNS:
        if label not in tech_detected and re.search(pat, combined_text, re.IGNORECASE):
            tech_detected.append(label)

    # Deduplicate Next.js if Next.js (App Router) is present
    if "Next.js (App Router)" in tech_detected and "Next.js" in tech_detected:
        tech_detected.remove("Next.js")

    # Add topics
    for top in topics:
        top_formatted = top.replace("-", " ").title()
        if top_formatted not in tech_detected:
            tech_detected.append(top_formatted)

    if not tech_detected:
        tech_detected = [languages[0]] if languages else ["Python"]

    # 3. Domain
    domain = infer_domain(combined_text, tech_detected)

    # 4. Summary
    summary = ""
    if desc and len(desc) >= 30:
        summary = desc.strip()
    else:
        # Extract first non-header, non-empty paragraph from README
        in_intro = False
        intro_lines = []
        for line in readme.splitlines():
            s = line.strip()
            if s.startswith("# "):
                in_intro = True
                continue
            if in_intro:
                if s.startswith("## ") or s.startswith("---") or s.startswith("```"):
                    if intro_lines:
                        break
                    continue
                if s:
                    intro_lines.append(s)
                elif intro_lines:
                    break
        if intro_lines:
            summary = " ".join(intro_lines).strip()
            summary = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', summary)
            summary = re.sub(r'[*_`]', '', summary)

    if not summary:
        summary = f"Engineered {title} utilizing {', '.join(tech_detected[:4])}."

    # Trim summary to clean 1-2 sentences
    summary_sentences = re.split(r'(?<=[.!?])\s+', summary)
    summary = " ".join(summary_sentences[:2]).strip()

    # 5. Metrics
    metrics = ""
    metric_matches = re.findall(
        r'(\b\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?ms|\b\d+\+?\s*(?:commits|years|users|tickers|records|datapoints)|\b100%|\bmAP@50\b)',
        combined_text,
        re.IGNORECASE
    )
    if metric_matches:
        metrics = f"Demonstrated high engineering fidelity with {', '.join(dict.fromkeys(metric_matches[:3]))}; 100% functional deployment."
    else:
        metrics = f"Complete implementation built with {', '.join(tech_detected[:3])} and containerized cross-platform deployment."

    # 6. Bullets Extraction
    bullets = []
    # If this is EverGrace specifically, ensure top-tier full-stack bullets
    if "evergrace" in repo_name.lower():
        bullets = [
            "Architected an accessible, multi-user online training platform utilizing Next.js (App Router), TypeScript, Tailwind CSS, and Radix UI.",
            "Engineered first-class accessibility controls including dynamic text scaling, high-contrast modes, text-to-speech read-aloud support, and light/dark theme switching.",
            "Designed dual portal experiences featuring a senior member experience paired with an administrative console for curriculum and roster management.",
            "Implemented data persistence and schema migrations using Prisma ORM with an isolated internal PostgreSQL 16 container.",
            "Orchestrated local development and production container builds via Docker Compose for reproducible cross-platform deployment."
        ]
    else:
        # Try finding bullets in README
        for line in readme.splitlines():
            s = line.strip()
            if s.startswith(("- ", "* ")) and len(s) > 25:
                clean_b = s[2:].strip()
                clean_b = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', clean_b)
                clean_b = re.sub(r'[*_`]', '', clean_b)
                if not clean_b.lower().startswith(("todo", "prerequisites", "license", "table of contents")):
                    bullets.append(clean_b)
                    if len(bullets) >= 4:
                        break

    # If not enough bullets found from README, synthesize strong resume-grade bullets
    if len(bullets) < 3:
        primary_stack = ", ".join(tech_detected[:4])
        bullets = [
            f"Architected and developed {title} leveraging {primary_stack} with clean modular architecture and robust error handling.",
            f"Implemented core business logic, automated data pipelines, and responsive interfaces adhering to performance and usability best practices.",
            f"Engineered test suites and operational workflows to ensure reliable execution, high availability, and consistent deployment.",
            f"Documented system architecture, configuration protocols, and setup automation for zero-friction team onboarding."
        ]

    # Prefix bullets with strong action verbs if missing
    polished_bullets = []
    action_verbs = ("architected", "engineered", "developed", "implemented", "built", "designed", "containerized", "automated", "created", "configured", "integrated")
    for b in bullets:
        b_clean = b.strip().rstrip(".")
        first_word = b_clean.split()[0].lower() if b_clean.split() else ""
        if first_word not in action_verbs:
            b_clean = f"Developed {b_clean[0].lower() + b_clean[1:] if len(b_clean) > 1 else b_clean}"
        polished_bullets.append(b_clean + ".")

    # 7. Generate YAML Frontmatter and Markdown
    slug = re.sub(r'[^a-z0-9]+', '-', repo_name.lower()).strip('-')
    p_id = slug.replace('-', '_')

    meta_dict = {
        "id": p_id,
        "title": title,
        "github_repo": repo_name,
        "github_url": html_url,
        "technologies": tech_detected[:8],
        "domain": domain,
        "status": "completed",
        "summary": summary,
        "metrics": metrics
    }

    yaml_header = yaml.dump(meta_dict, sort_keys=False, default_flow_style=False).strip()
    tech_pills = " | ".join(tech_detected[:6])
    bullet_md = "\n".join(f"- {b}" for b in polished_bullets)

    markdown_content = f"""---
{yaml_header}
---

### {title} | [GitHub]({html_url})
*{tech_pills}*

{bullet_md}
"""
    return slug, markdown_content, meta_dict


def sync_github_projects(
    username: Optional[str] = None,
    limit: Optional[int] = None,
    projects_dir: Optional[Path] = None,
    token: Optional[str] = None,
    force: bool = False
) -> List[Dict[str, Any]]:
    """
    Core synchronization workflow:
    1. Fetches the latest repositories for the configured username.
    2. Inspects data/projects/ to verify if they are already present.
    3. Scrapes metadata & README for new repositories and creates resume project files.
    4. Returns a list of newly created projects.
    """
    user = username or settings.GITHUB_USERNAME
    sync_limit = limit or settings.GITHUB_SYNC_LIMIT
    p_dir = projects_dir or settings.PROJECTS_DIR
    gh_token = token or settings.GITHUB_TOKEN

    if not p_dir.exists():
        p_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Connecting to GitHub to check recent projects for user '%s' (limit: %d)...", user, sync_limit)

    repos = fetch_recent_github_repos(user, limit=sync_limit, token=gh_token)
    if not repos:
        logger.info("No repositories returned from GitHub for user '%s'.", user)
        return []

    created_projects = []

    for repo in repos:
        repo_name = repo.get("name", "")
        pushed_date = repo.get("pushed_at", "")[:10]

        already_present, existing_filename = is_repo_already_present(repo_name, p_dir)
        if already_present and not force:
            logger.info("GitHub project '%s' is already represented by '%s' (skipped).", repo_name, existing_filename)
            continue

        logger.info("New GitHub project detected: '%s' (pushed: %s). Scraping repository...", repo_name, pushed_date)
        details = scrape_repo_details(user, repo_name, token=gh_token)
        slug, md_content, meta = parse_and_format_project(details)

        target_file = p_dir / f"{slug}.md"
        target_file.write_text(md_content, encoding="utf-8")
        logger.info("Created new project file: %s", target_file)

        created_projects.append({
            "id": meta["id"],
            "title": meta["title"],
            "filename": target_file.name,
            "path": str(target_file),
            "pushed_at": pushed_date,
            "technologies": meta["technologies"],
            "domain": meta["domain"]
        })

    return created_projects


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print(f"Running GitHub project sync for user '{settings.GITHUB_USERNAME}'...")
    results = sync_github_projects()
    print(f"\nSync complete. Created {len(results)} new project file(s):")
    for r in results:
        print(f" - [{r['id']}] {r['title']} -> {r['filename']}")
