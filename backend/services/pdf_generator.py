import re
from typing import List, Tuple

class SimpleATSPDFWriter:
    """
    Lightweight, deterministic, pure-Python PDF 1.4 generator for ATS-friendly resumes.
    Features:
    - Pure black-and-white high-contrast typography (100% professional and ATS-compliant).
    - Automatic text wrapping, bold section headers, and bullet indentation.
    - True vector text stream with full ASCII sanitization (zero '?' glyph artifacts).
    - Standard US-Letter dimensions (612 x 792 pt) with 0.5-inch margins (36 pt).
    - Deterministic multi-page pagination.
    """
    PAGE_WIDTH = 612
    PAGE_HEIGHT = 792
    MARGIN_LEFT = 45
    MARGIN_RIGHT = 45
    MARGIN_TOP = 42
    MARGIN_BOTTOM = 40
    USABLE_WIDTH = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT

    DEFAULT_LINKEDIN_URL = "https://www.linkedin.com/in/manbir-singh-sidhu/"
    DEFAULT_GITHUB_URL = "https://github.com/SidhuManbirSingh/SidhuManbirSingh/"

    FONT_CHAR_WIDTH_RATIO = {
        "/F1": 0.52,  # Helvetica Regular
        "/F2": 0.56,  # Helvetica Bold
        "/F3": 0.52,  # Helvetica Oblique (Italic)
    }

    HELVETICA_CHAR_WIDTHS = {
        ' ': 278, '!': 278, '"': 355, '#': 556, '$': 556, '%': 889, '&': 667, "'": 191,
        '(': 333, ')': 333, '*': 389, '+': 584, ',': 278, '-': 333, '.': 278, '/': 278,
        '0': 556, '1': 556, '2': 556, '3': 556, '4': 556, '5': 556, '6': 556, '7': 556,
        '8': 556, '9': 556, ':': 278, ';': 278, '<': 584, '=': 584, '>': 584, '?': 556,
        '@': 1015, 'A': 667, 'B': 667, 'C': 722, 'D': 722, 'E': 667, 'F': 611, 'G': 778,
        'H': 722, 'I': 278, 'J': 500, 'K': 667, 'L': 556, 'M': 833, 'N': 722, 'O': 778,
        'P': 667, 'Q': 778, 'R': 722, 'S': 667, 'T': 611, 'U': 722, 'V': 667, 'W': 944,
        'X': 667, 'Y': 667, 'Z': 611, '[': 278, '\\': 278, ']': 278, '^': 469, '_': 556,
        '`': 222, 'a': 556, 'b': 556, 'c': 500, 'd': 556, 'e': 556, 'f': 278, 'g': 556,
        'h': 556, 'i': 222, 'j': 222, 'k': 500, 'l': 222, 'm': 833, 'n': 556, 'o': 556,
        'p': 556, 'q': 556, 'r': 333, 's': 500, 't': 278, 'u': 556, 'v': 500, 'w': 722,
        'x': 500, 'y': 500, 'z': 500, '{': 334, '|': 260, '}': 334, '~': 584
    }

    def __init__(self):
        self.pages: List[List[str]] = [[]]
        self.annots: List[List[str]] = [[]]
        self.current_page = 0
        self.y = self.PAGE_HEIGHT - self.MARGIN_TOP

    def _start_new_page(self):
        self.pages.append([])
        self.annots.append([])
        self.current_page += 1
        self.y = self.PAGE_HEIGHT - self.MARGIN_TOP

    def _get_text_width(self, text: str, font: str, font_size: float) -> float:
        sanitized = self._sanitize(text)
        is_bold = (font == "/F2")
        total = 0
        for ch in sanitized:
            w = self.HELVETICA_CHAR_WIDTHS.get(ch)
            if w is None:
                if 'A' <= ch <= 'Z':
                    w = 722 if is_bold else 667
                elif 'a' <= ch <= 'z':
                    w = 556 if is_bold else 500
                else:
                    w = 556
            elif is_bold and ch.isalpha():
                w = int(w * 1.08)
            total += w
        return total * font_size / 1000.0

    def _check_page_space(self, needed_pt: float):
        if self.y - needed_pt < self.MARGIN_BOTTOM:
            self._start_new_page()

    def _sanitize(self, text: str) -> str:
        """
        Sanitizes Unicode symbols to ensure zero '?' question mark replacements in standard PDF fonts.
        """
        if not text:
            return ""
        # Unicode dashes & minuses to ASCII hyphen
        for u in ['\u2013', '\u2014', '\u2212', '–', '—', '−']:
            text = text.replace(u, '-')
        # Curly quotes to ASCII single and double quotes
        for q in ['\u2018', '\u2019', '’', '‘', '`']:
            text = text.replace(q, "'")
        for q in ['\u201c', '\u201d', '“', '”']:
            text = text.replace(q, '"')
        # Bullets and ellipses
        text = text.replace('\u2022', '-').replace('•', '-')
        text = text.replace('\u2026', '...').replace('…', '...')
        # Strip remaining non-ASCII safely
        cleaned = []
        for ch in text:
            code = ord(ch)
            if code < 128:
                cleaned.append(ch)
            elif code in (160,):
                cleaned.append(' ')
            else:
                cleaned.append('-' if ch in '-–—−' else ' ')
        return "".join(cleaned)

    def _escape(self, text: str) -> str:
        """Escape parentheses and backslashes for PDF string literals."""
        sanitized = self._sanitize(text)
        return sanitized.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')

    def _wrap_text(self, text: str, font: str, font_size: float, max_width: float) -> List[str]:
        sanitized = self._sanitize(text)
        char_ratio = self.FONT_CHAR_WIDTH_RATIO.get(font, 0.52)
        char_width = font_size * char_ratio
        max_chars = max(10, int(max_width / char_width))

        words = sanitized.split()
        if not words:
            return []

        lines = []
        current_line = []
        current_length = 0

        for word in words:
            if current_length + len(word) + 1 <= max_chars:
                current_line.append(word)
                current_length += len(word) + 1
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_length = len(word)

        if current_line:
            lines.append(" ".join(current_line))

        return lines

    def add_name_header(self, name: str, contact_line: str):
        self._check_page_space(55)
        escaped_name = self._escape(name)
        stream = self.pages[self.current_page]
        
        # Candidate Name: 18pt Bold, Pure Black
        stream.append(f"BT /F2 18 Tf 0 0 0 rg {self.MARGIN_LEFT} {self.y} Td ({escaped_name}) Tj ET")
        self.y -= 20

        # Contact Line with clickable hyperlinks (LinkedIn, GitHub, etc.)
        if contact_line:
            raw_contact = contact_line.strip()
            links_to_annotate = []
            
            # Find all markdown links [label](url)
            md_link_pattern = re.compile(r'\[([^\]]+)\]\((https?://[^\)]+)\)')
            display_contact = ""
            last_idx = 0
            for m in md_link_pattern.finditer(raw_contact):
                display_contact += raw_contact[last_idx:m.start()]
                char_pos = len(display_contact)
                label = m.group(1).strip()
                url = m.group(2).strip()
                display_contact += label
                links_to_annotate.append((label, url, char_pos))
                last_idx = m.end()
            display_contact += raw_contact[last_idx:]

            # Fallbacks for raw unformatted URLs or keywords
            if not any("linkedin" in lbl.lower() for lbl, _, _ in links_to_annotate):
                if "linkedin.com" in display_contact.lower():
                    raw_match = re.search(r'https?://(?:www\.)?linkedin\.com/in/[A-Za-z0-9_\-\/]+', display_contact)
                    if raw_match:
                        url = raw_match.group(0)
                        start_idx = raw_match.start()
                        display_contact = display_contact[:start_idx] + "LinkedIn" + display_contact[raw_match.end():]
                        links_to_annotate.append(("LinkedIn", url, start_idx))
                elif "linkedin" in display_contact.lower():
                    links_to_annotate.append(("LinkedIn", self.DEFAULT_LINKEDIN_URL, display_contact.lower().find("linkedin")))

            if not any("github" in lbl.lower() for lbl, _, _ in links_to_annotate):
                if "github.com" in display_contact.lower():
                    raw_match = re.search(r'https?://(?:www\.)?github\.com/[A-Za-z0-9_\-\/]+', display_contact)
                    if raw_match:
                        url = raw_match.group(0)
                        start_idx = raw_match.start()
                        display_contact = display_contact[:start_idx] + "GitHub" + display_contact[raw_match.end():]
                        links_to_annotate.append(("GitHub", url, start_idx))
                elif "github" in display_contact.lower():
                    links_to_annotate.append(("GitHub", self.DEFAULT_GITHUB_URL, display_contact.lower().find("github")))

            display_contact = re.sub(r'[ \t]+', ' ', display_contact).strip()

            # Add PDF Hyperlink Annotations over each link
            for label, url, _ in links_to_annotate:
                if label in display_contact:
                    idx = display_contact.index(label)
                    prefix_text = display_contact[:idx]
                    prefix_w = self._get_text_width(prefix_text, "/F1", 9.5)
                    label_w = self._get_text_width(label, "/F1", 9.5)

                    llx = self.MARGIN_LEFT + prefix_w
                    urx = llx + label_w
                    lly = self.y - 2
                    ury = self.y + 10

                    annot = (
                        f"<< /Type /Annot /Subtype /Link "
                        f"/Rect [{llx:.2f} {lly:.2f} {urx:.2f} {ury:.2f}] "
                        f"/Border [0 0 0] "
                        f"/A << /Type /Action /S /URI /URI ({url}) >> >>"
                    )
                    self.annots[self.current_page].append(annot)

            escaped_contact = self._escape(display_contact)
            stream.append(f"BT /F1 9.5 Tf 0 0 0 rg {self.MARGIN_LEFT} {self.y} Td ({escaped_contact}) Tj ET")
            self.y -= 14

        # Clean black dividing rule
        stream.append(f"0.75 w 0 0 0 RG {self.MARGIN_LEFT} {self.y} m {self.PAGE_WIDTH - self.MARGIN_RIGHT} {self.y} l S")
        self.y -= 14

    def add_section_header(self, title: str):
        # Add generous breathing space before section header (unless at top of page)
        if self.y < (self.PAGE_HEIGHT - self.MARGIN_TOP - 25):
            self.y -= 10
        self._check_page_space(34)
        escaped_title = self._escape(title.upper())
        stream = self.pages[self.current_page]
        # Section title in 11pt Bold, Pure Black
        stream.append(f"BT /F2 11 Tf 0 0 0 rg {self.MARGIN_LEFT} {self.y} Td ({escaped_title}) Tj ET")
        self.y -= 4
        # Clean subtle black/charcoal dividing rule
        stream.append(f"0.5 w 0.35 0.35 0.35 RG {self.MARGIN_LEFT} {self.y} m {self.PAGE_WIDTH - self.MARGIN_RIGHT} {self.y} l S")
        self.y -= 11

    def add_paragraph(self, text: str, font_size: float = 9.5):
        lines = self._wrap_text(text, "/F1", font_size, self.USABLE_WIDTH)
        line_height = font_size * 1.36
        for line in lines:
            self._check_page_space(line_height)
            escaped = self._escape(line)
            self.pages[self.current_page].append(
                f"BT /F1 {font_size} Tf 0 0 0 rg {self.MARGIN_LEFT} {self.y} Td ({escaped}) Tj ET"
            )
            self.y -= line_height
        self.y -= 5

    def add_job_header(self, title: str, company: str, dates: str, location: str, add_top_space: bool = False):
        if add_top_space:
            self.y -= 8
        self._check_page_space(32)
        # Title and Company: 10pt Bold, Pure Black
        job_title_str = f"{title} | {company}" if company else title
        lines = self._wrap_text(job_title_str, "/F2", 10.0, self.USABLE_WIDTH)
        for line in lines:
            self._check_page_space(14)
            escaped = self._escape(line)
            self.pages[self.current_page].append(
                f"BT /F2 10 Tf 0 0 0 rg {self.MARGIN_LEFT} {self.y} Td ({escaped}) Tj ET"
            )
            self.y -= 13.5

        # Dates & Location: 9pt Italic, Neutral Dark Charcoal
        meta_str = f"{dates} | {location}" if location and dates else (dates or location)
        if meta_str.strip():
            self._check_page_space(13)
            escaped_meta = self._escape(meta_str)
            self.pages[self.current_page].append(
                f"BT /F3 9 Tf 0.25 0.25 0.25 rg {self.MARGIN_LEFT} {self.y} Td ({escaped_meta}) Tj ET"
            )
            self.y -= 13
        self.y -= 3.5

    def add_project_header(self, title: str, add_top_space: bool = False):
        if add_top_space:
            self.y -= 8
        self._check_page_space(24)
        clean_title = re.sub(r'\((?:Targeted Implementation / Prototype|Proposed Project|Proposed)\)', '(Under Development)', title, flags=re.I)
        lines = self._wrap_text(clean_title, "/F2", 10.0, self.USABLE_WIDTH)
        for line in lines:
            self._check_page_space(14)
            escaped = self._escape(line)
            self.pages[self.current_page].append(
                f"BT /F2 10 Tf 0 0 0 rg {self.MARGIN_LEFT} {self.y} Td ({escaped}) Tj ET"
            )
            self.y -= 13.5
        self.y -= 3.5

    def add_bullet(self, text: str, font_size: float = 9.5):
        bullet_indent = 13
        content_width = self.USABLE_WIDTH - bullet_indent
        lines = self._wrap_text(text, "/F1", font_size, content_width)
        line_height = font_size * 1.36

        if not lines:
            return

        self._check_page_space(line_height)
        stream = self.pages[self.current_page]

        # Bullet symbol (-) in pure black
        stream.append(f"BT /F2 {font_size} Tf 0 0 0 rg {self.MARGIN_LEFT + 2} {self.y} Td (-) Tj ET")

        # First line
        escaped_first = self._escape(lines[0])
        stream.append(f"BT /F1 {font_size} Tf 0 0 0 rg {self.MARGIN_LEFT + bullet_indent} {self.y} Td ({escaped_first}) Tj ET")
        self.y -= line_height

        # Remaining wrapped lines
        for line in lines[1:]:
            self._check_page_space(line_height)
            escaped = self._escape(line)
            self.pages[self.current_page].append(
                f"BT /F1 {font_size} Tf 0 0 0 rg {self.MARGIN_LEFT + bullet_indent} {self.y} Td ({escaped}) Tj ET"
            )
            self.y -= line_height

        self.y -= 3.5

    def add_skill_line(self, category: str, skills_str: str, font_size: float = 9.5, has_bullet: bool = True):
        """
        Renders skills line with Bold category name in /F2 and Regular skills list in /F1.
        All multi-line skill items are strictly column-aligned using a clean hanging indent.
        """
        category_clean = self._sanitize(category).strip()
        skills_clean = self._sanitize(skills_str).strip()
        prefix = f"{category_clean}: "
        
        prefix_width = self._get_text_width(prefix, "/F2", font_size)
        bullet_indent = 12 if has_bullet else 0
        start_x = self.MARGIN_LEFT + bullet_indent
        
        # Hanging indent: aligns subsequent wrapped lines under the skills column
        # Cap hanging indent at 145pt so very long categories still have ample width for skills
        hanging_indent = min(prefix_width, 145.0)
        
        first_avail = self.USABLE_WIDTH - bullet_indent - prefix_width
        subseq_avail = self.USABLE_WIDTH - bullet_indent - hanging_indent
        
        # Word wrap skills list
        words = skills_clean.split()
        if not words:
            return

        skill_lines = []
        current_words = []
        current_w = 0.0
        max_w = first_avail

        for word in words:
            word_w = self._get_text_width(word, "/F1", font_size)
            space_w = self._get_text_width(" ", "/F1", font_size)
            add_w = word_w if not current_words else (space_w + word_w)
            
            if current_w + add_w <= max_w:
                current_words.append(word)
                current_w += add_w
            else:
                if current_words:
                    skill_lines.append(" ".join(current_words))
                current_words = [word]
                current_w = word_w
                max_w = subseq_avail

        if current_words:
            skill_lines.append(" ".join(current_words))

        line_height = font_size * 1.36
        
        # Total needed vertical space
        needed_pt = len(skill_lines) * line_height + 4.5
        self._check_page_space(needed_pt)
        stream = self.pages[self.current_page]

        # Draw bullet if present
        if has_bullet:
            stream.append(f"BT /F2 {font_size} Tf 0 0 0 rg {self.MARGIN_LEFT + 2} {self.y} Td (-) Tj ET")

        # Line 1: Category prefix in /F2 Bold
        escaped_prefix = self._escape(prefix)
        stream.append(
            f"BT /F2 {font_size} Tf 0 0 0 rg {start_x} {self.y} Td ({escaped_prefix}) Tj ET"
        )
        
        # Line 1: First line of skills in /F1 Regular, starting at start_x + prefix_width
        escaped_first_skills = self._escape(skill_lines[0])
        skills_x = start_x + prefix_width
        stream.append(
            f"BT /F1 {font_size} Tf 0 0 0 rg {skills_x} {self.y} Td ({escaped_first_skills}) Tj ET"
        )
        self.y -= line_height

        # Subsequent lines: all aligned at start_x + hanging_indent
        for line_text in skill_lines[1:]:
            self._check_page_space(line_height)
            escaped_text = self._escape(line_text)
            subseq_x = start_x + hanging_indent
            self.pages[self.current_page].append(
                f"BT /F1 {font_size} Tf 0 0 0 rg {subseq_x} {self.y} Td ({escaped_text}) Tj ET"
            )
            self.y -= line_height

        self.y -= 4.5

    def build_pdf_bytes(self) -> bytes:
        """
        Assembles all pages, content streams, fonts, annotations, and xref tables into valid PDF 1.4 binary bytes.
        """
        num_pages = len(self.pages)
        objects = []

        def add_object(content: str) -> int:
            objects.append(content)
            return len(objects)

        # Standard PDF Objects
        objects.append("") # 1: Catalog
        objects.append("") # 2: Pages
        objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>") # 3: F1 Regular
        objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>") # 4: F2 Bold
        objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique >>") # 5: F3 Italic

        page_obj_ids = []
        for p_idx, stream_ops in enumerate(self.pages):
            stream_body = "\n".join(stream_ops)
            stream_bytes = stream_body.encode('latin1', errors='replace')
            stream_len = len(stream_bytes)
            
            content_obj = f"<< /Length {stream_len} >>\nstream\n{stream_body}\nendstream"
            content_id = add_object(content_obj)
            
            annots_entry = ""
            if p_idx < len(self.annots) and self.annots[p_idx]:
                annots_joined = " ".join(self.annots[p_idx])
                annots_entry = f" /Annots [{annots_joined}]"
            
            page_obj = (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.PAGE_WIDTH} {self.PAGE_HEIGHT}] "
                f"/Contents {content_id} 0 R "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >>{annots_entry} >>"
            )
            page_id = add_object(page_obj)
            page_obj_ids.append(page_id)

        kids_str = " ".join([f"{pid} 0 R" for pid in page_obj_ids])
        objects[0] = "<< /Type /Catalog /Pages 2 0 R >>"
        objects[1] = f"<< /Type /Pages /Kids [{kids_str}] /Count {num_pages} >>"

        output = [b"%PDF-1.4\n"]
        xref_offsets = [0]

        offset = len(output[0])
        for i, obj_content in enumerate(objects):
            xref_offsets.append(offset)
            obj_bytes = f"{i+1} 0 obj\n{obj_content}\nendobj\n".encode('latin1', errors='replace')
            output.append(obj_bytes)
            offset += len(obj_bytes)

        xref_start = offset
        num_entries = len(objects) + 1
        xref_table = [f"xref\n0 {num_entries}\n0000000000 65535 f \n".encode('latin1')]
        for off in xref_offsets[1:]:
            xref_table.append(f"{off:010d} 00000 n \n".encode('latin1'))

        output.extend(xref_table)
        trailer = (
            f"trailer\n<< /Size {num_entries} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n"
        ).encode('latin1')
        output.append(trailer)

        return b"".join(output)


class ATSResumePDFGenerator:
    @staticmethod
    def markdown_to_pdf_bytes(markdown_text: str) -> bytes:
        """
        Parses ATS-formatted markdown and renders into standard PDF 1.4 bytes.
        Guarantees zero duplicate contact lines and strict black-and-white formatting.
        """
        writer = SimpleATSPDFWriter()
        lines = markdown_text.splitlines()

        name = ""
        contact = ""
        header_end_idx = 0

        # Step 1: Extract Name & Single Contact line
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("# ") and not name:
                name = stripped.lstrip("# ").replace("**", "").strip()
                header_end_idx = idx + 1
                for c_idx in range(idx + 1, len(lines)):
                    c_line = lines[c_idx].strip()
                    if c_line and not c_line.startswith("#"):
                        contact = c_line.replace("**", "").strip()
                        header_end_idx = c_idx + 1
                        break
                break

        writer.add_name_header(name if name else "Candidate Resume", contact)

        # Step 2: Skip past duplicate header lines if structured resume with sections (## ),
        # or start immediately after contact for cover letters / narrative documents
        has_sections = any(l.strip().startswith("## ") for l in lines)
        i = header_end_idx
        if has_sections:
            while i < len(lines) and not lines[i].strip().startswith("## "):
                i += 1

        current_section = ""
        items_in_section = 0
        while i < len(lines):
            line = lines[i].strip()
            i += 1

            if not line:
                continue

            if line.startswith("## "):
                current_section = line.lstrip("## ").replace("**", "").strip()
                writer.add_section_header(current_section)
                items_in_section = 0
                continue

            if line.startswith("### "):
                title_line = line.lstrip("### ").replace("**", "").strip()
                
                # Enforce (Under Development) for project slot 2 if proposed
                clean_title = re.sub(
                    r'\((?:Targeted Implementation / Prototype|Proposed Project|Proposed)\)',
                    '(Under Development)',
                    title_line,
                    flags=re.I
                )
                
                # Check if next line contains dates/location/institution
                dates_str = ""
                loc_str = ""
                if i < len(lines) and (lines[i].strip().startswith("*") or lines[i].strip().startswith("_")):
                    meta = lines[i].strip().strip("*_").strip()
                    parts = [p.strip() for p in meta.split("|")]
                    dates_str = parts[0] if len(parts) > 0 else ""
                    loc_str = parts[1] if len(parts) > 1 else ""
                    i += 1

                has_prior_items = items_in_section > 0
                if current_section == "Professional Experience" or (current_section != "Education" and "|" in title_line):
                    parts = [p.strip() for p in clean_title.split("|")]
                    job_title = parts[0] if len(parts) > 0 else ""
                    company = parts[1] if len(parts) > 1 else ""
                    writer.add_job_header(job_title, company, dates_str, loc_str, add_top_space=has_prior_items)
                else:
                    writer.add_project_header(clean_title, add_top_space=has_prior_items)
                    if dates_str or loc_str:
                        meta_text = f"{dates_str} | {loc_str}" if loc_str and dates_str else (dates_str or loc_str)
                        writer.add_paragraph(meta_text, font_size=9.0)
                items_in_section += 1
                continue

            # Check if skill, certification, or metadata line formatted as: **Category:** item1, item2
            skill_match = re.match(r'^(?:[-*]\s+)?\*\*([^\*:]+):?\*\*\s*:?\s*(.*)$', line)
            if skill_match:
                cat, items = skill_match.groups()
                has_bullet = line.lstrip().startswith(('-', '*'))
                writer.add_skill_line(cat.strip(), items.strip(), has_bullet=has_bullet)
                continue

            if line.startswith("- ") or line.startswith("* "):
                bullet_text = line[2:].strip()
                clean_text = re.sub(r'[*_]', '', bullet_text).strip()
                if clean_text and clean_text != ".":
                    writer.add_bullet(clean_text)
                continue

            # Standard paragraph line (e.g. Professional Summary)
            clean_line = re.sub(r'[*_]', '', line).strip()
            if clean_line and clean_line != ".":
                writer.add_paragraph(clean_line)

        return writer.build_pdf_bytes()
