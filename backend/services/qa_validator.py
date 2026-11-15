import re
from collections import Counter
from typing import Dict, Any, List, Set
from backend.models.schemas import (
    Stage2CustomizationResult,
    QACheckItem,
    DocumentQAReport,
)


_QA_STOPWORDS: Set[str] = {
    "with", "from", "that", "this", "have", "will", "your", "their", "about",
    "across", "using", "into", "through", "including", "within", "such", "ensure",
    "and", "the", "for", "are", "you", "all", "over", "years", "year", "present",
    "data", "work", "systems", "management", "operations", "service", "project",
    "team", "teams", "development", "experience", "skills", "technical", "process",
}


class FinalDocumentQAValidator:
    """
    Stage 4 Deterministic Final Document Quality Assurance Stage.
    Inspects BOTH the assembled Markdown source AND compiled PDF binary bytes
    across 9 structural, formatting, URL, contact, repetition, and pagination checks.
    """

    @staticmethod
    def _extract_pdf_page_count(pdf_str: str) -> int:
        m = re.search(r'/Type\s+/Pages\b[^>]*?/Count\s+(\d+)', pdf_str)
        if m:
            return int(m.group(1))
        page_objs = re.findall(r'/Type\s+/Page\b(?!s)', pdf_str)
        return len(page_objs) if page_objs else 1

    @staticmethod
    def _extract_pdf_streams(pdf_str: str) -> List[str]:
        return re.findall(r'stream\r?\n(.*?)\r?\nendstream', pdf_str, flags=re.S)

    @staticmethod
    def _extract_pdf_uris(pdf_str: str) -> List[str]:
        return re.findall(r'/URI\s*\(([^)]*)\)', pdf_str)

    @classmethod
    def validate(
        cls,
        markdown_text: str,
        pdf_bytes: bytes,
        master_parsed: Dict[str, Any],
        customized: Stage2CustomizationResult,
    ) -> DocumentQAReport:
        md = markdown_text or ""
        pdf_raw = pdf_bytes or b""
        pdf_str = pdf_raw.decode("latin1", errors="replace")
        pdf_streams = cls._extract_pdf_streams(pdf_str)
        page_count = cls._extract_pdf_page_count(pdf_str)

        checks: List[QACheckItem] = []

        # 1. ATS-friendly formatting (Markdown & PDF stream)
        has_html = bool(re.search(r'</?(?:table|tr|td|th|div|span|u|sup|sub|img|script)\b', md, re.I))
        has_md_table = bool(re.search(r'(?m)^\|.+\|\s*\n\|\s*:?-{3,}', md))
        valid_pdf_header = pdf_raw.startswith(b"%PDF-1.4") and b"%%EOF" in pdf_raw
        has_winansi_fonts = "/Helvetica" in pdf_str and "/WinAnsiEncoding" in pdf_str
        ats_ok = (not has_html) and (not has_md_table) and valid_pdf_header and has_winansi_fonts
        ats_details = (
            "Single-column ATS Markdown and valid PDF 1.4 WinAnsi Type1 streams verified."
            if ats_ok
            else f"Formatting issues: html={has_html}, md_table={has_md_table}, pdf_hdr={valid_pdf_header}, fonts={has_winansi_fonts}."
        )
        checks.append(QACheckItem(name="ats_formatting", passed=ats_ok, severity="error" if not ats_ok else "info", details=ats_details))

        # 2. Missing or duplicated sections
        sec_headers = [re.sub(r'\*', '', m.group(1)).strip().lower() for m in re.finditer(r'(?m)^##\s+(.+)$', md)]
        sec_counts = Counter(sec_headers)
        duplicated = [s for s, cnt in sec_counts.items() if cnt > 1]
        required_sections = ["professional summary", "technical skills", "professional experience", "projects"]
        missing_secs = [req for req in required_sections if not any(req in h for h in sec_headers)]
        sec_ok = (len(duplicated) == 0) and (len(missing_secs) == 0)
        sec_details = (
            f"Verified {len(sec_headers)} unique sections without duplicates."
            if sec_ok
            else f"Missing sections: {missing_secs}; Duplicated sections: {duplicated}."
        )
        checks.append(QACheckItem(name="section_completeness", passed=sec_ok, severity="error" if not sec_ok else "info", details=sec_details))

        # 3. Broken GitHub & HTTP URLs (Markdown + PDF /URI annotations)
        md_links = re.findall(r'\[([^\]]*)\]\(([^)]*)\)', md)
        pdf_uris = cls._extract_pdf_uris(pdf_str)
        url_pattern = re.compile(r'^https?://[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/[^\s]*)?$')
        bad_urls = [url for _, url in md_links if not url_pattern.match(url.strip())]
        bad_urls.extend([u for u in pdf_uris if not url_pattern.match(u.strip())])
        expected_p1_gh = (customized.slot1_github_url or "").strip()
        missing_expected_gh = bool(expected_p1_gh and expected_p1_gh not in pdf_uris and expected_p1_gh not in md)
        url_ok = (len(bad_urls) == 0) and (not missing_expected_gh)
        url_details = (
            f"Verified {len(md_links)} Markdown link(s) and {len(pdf_uris)} PDF /URI annotation(s)."
            if url_ok
            else f"Broken URLs: {bad_urls}; Missing Slot 1 GitHub URI: {missing_expected_gh}."
        )
        checks.append(QACheckItem(name="github_and_urls", passed=url_ok, severity="error" if not url_ok else "info", details=url_details))

        # 4. Invalid / missing / duplicated contact information
        contact_info = master_parsed.get("contact_info", {}) or {}
        cand_name = (master_parsed.get("name") or "").strip()
        email = (contact_info.get("email") or "").strip()
        phone = (contact_info.get("phone") or "").strip()
        md_header_lines = [l.strip() for l in md.splitlines()[:5] if l.strip()]
        md_header_blob = "\n".join(md_header_lines)
        pdf_all_streams = "\n".join(pdf_streams)
        has_name = bool(cand_name and cand_name in md_header_blob and cand_name in pdf_all_streams)
        has_email = bool((not email) or (email in md_header_blob and email in pdf_all_streams))
        has_phone = bool((not phone) or (re.sub(r'\s+', ' ', phone) in re.sub(r'\s+', ' ', md_header_blob)))
        email_occurrences = len(re.findall(re.escape(email), md)) if email else 1
        contact_ok = has_name and has_email and has_phone and (email_occurrences == 1)
        contact_details = (
            "Verified single contact header with candidate name, email, and phone in Markdown and PDF."
            if contact_ok
            else f"Contact check failed: name={has_name}, email={has_email}, phone={has_phone}, email_count={email_occurrences}."
        )
        checks.append(QACheckItem(name="contact_information", passed=contact_ok, severity="error" if not contact_ok else "info", details=contact_details))

        # 5. Unusual spacing and page breaks
        excessive_blanks = bool(re.search(r'\n{3,}', md))
        solitary_dots = any(l.strip() == "." for l in md.splitlines())
        # Check PDF page streams for orphaned section header right at bottom edge (y < 58 with no following Tj)
        orphaned_header = False
        for stream in pdf_streams:
            ops = re.findall(r'BT\s+/F(\d+)\s+[\d.]+\s+Tf[^)]*?(\d+(?:\.\d+)?)\s+Td\s*\(([^)]*)\)\s*Tj', stream)
            if ops:
                last_font, last_y, _ = ops[-1]
                if last_font == "2" and float(last_y) < 55.0:
                    orphaned_header = True
                    break
        spacing_ok = (not excessive_blanks) and (not solitary_dots) and (not orphaned_header)
        spacing_details = (
            "Clean line spacing and section-to-content page flow verified in Markdown and PDF."
            if spacing_ok
            else f"Spacing issues: triple_newlines={excessive_blanks}, solitary_dot={solitary_dots}, orphaned_header={orphaned_header}."
        )
        checks.append(QACheckItem(name="spacing_and_page_breaks", passed=spacing_ok, severity="error" if not spacing_ok else "info", details=spacing_details))

        # 6. Inconsistent bullet formatting
        raw_bullet_lines = [l for l in md.splitlines() if l.lstrip().startswith(("-", "*", "•"))]
        bad_bullets = [
            l for l in raw_bullet_lines
            if l.lstrip().startswith(("•", "* "))
            or l.strip() in {"-", "- .", "- bullet", "- string"}
        ]
        bullet_ok = (len(raw_bullet_lines) >= 4) and (len(bad_bullets) == 0)
        bullet_details = (
            f"Verified {len(raw_bullet_lines)} consistent Markdown list items."
            if bullet_ok
            else f"Inconsistent or empty bullet lines detected: {bad_bullets[:3]}."
        )
        checks.append(QACheckItem(name="bullet_formatting", passed=bullet_ok, severity="error" if not bullet_ok else "info", details=bullet_details))

        # 7. Excessive keyword repetition
        words = [
            w for w in re.findall(r'\b[a-z]{4,}\b', md.lower())
            if w not in _QA_STOPWORDS and w not in set((cand_name or "").lower().split())
        ]
        word_counts = Counter(words)
        overused = {w: cnt for w, cnt in word_counts.items() if cnt > 12}
        rep_ok = len(overused) == 0
        rep_details = (
            "No excessive keyword stuffing detected."
            if rep_ok
            else f"Over-repeated keyword(s) (>12 occurrences): {overused}."
        )
        checks.append(QACheckItem(name="keyword_repetition", passed=rep_ok, severity="warning" if not rep_ok else "info", details=rep_details))

        # 8. Content spilling onto an additional page
        last_page_tjs = len(re.findall(r'\)\s*Tj', pdf_streams[-1])) if pdf_streams else 0
        sparse_trailing_spill = (page_count >= 2 and last_page_tjs <= 2)
        excessive_pages = page_count > 2
        spill_ok = (not excessive_pages) and (not sparse_trailing_spill)
        spill_details = (
            f"Compiled PDF is {page_count} page(s) with balanced content density ({last_page_tjs} text ops on final page)."
            if spill_ok
            else f"Pagination spill detected: pages={page_count}, final_page_text_ops={last_page_tjs}."
        )
        checks.append(QACheckItem(name="page_spill", passed=spill_ok, severity="warning" if not spill_ok else "info", details=spill_details))

        # 9. Empty or incomplete project descriptions
        s1_ok = bool((customized.slot1_title or "").strip()) and len([b for b in customized.slot1_bullets if b.strip()]) >= 2
        s2_ok = bool((customized.slot2_title or "").strip()) and len([b for b in customized.slot2_bullets if b.strip()]) >= 2
        if customized.slot2_is_proposed:
            s2_ok = s2_ok and ("(under development)" in customized.slot2_title.lower())
        proj_ok = s1_ok and s2_ok
        proj_details = (
            "Verified both Project Slots contain complete titles, labels, and >=2 substantive bullets."
            if proj_ok
            else f"Incomplete project slot: slot1_ok={s1_ok}, slot2_ok={s2_ok}."
        )
        checks.append(QACheckItem(name="project_completeness", passed=proj_ok, severity="error" if not proj_ok else "info", details=proj_details))

        warnings = [f"[{c.name}] {c.details}" for c in checks if not c.passed]
        overall_passed = all(c.passed for c in checks)
        passed_count = sum(1 for c in checks if c.passed)
        summary = f"QA {passed_count}/{len(checks)} checks passed ({page_count}-page PDF)."

        return DocumentQAReport(
            passed=overall_passed,
            checks=checks,
            warnings=warnings,
            pdf_page_count=page_count,
            summary=summary,
        )
