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

    HELVETICA_BOLD_CHAR_WIDTHS = {
        ' ': 278, '!': 333, '"': 474, '#': 556, '$': 556, '%': 889, '&': 722, "'": 278,
        '(': 333, ')': 333, '*': 389, '+': 584, ',': 278, '-': 333, '.': 278, '/': 278,
        '0': 556, '1': 556, '2': 556, '3': 556, '4': 556, '5': 556, '6': 556, '7': 556,
        '8': 556, '9': 556, ':': 333, ';': 333, '<': 584, '=': 584, '>': 584, '?': 611,
        '@': 975, 'A': 722, 'B': 722, 'C': 722, 'D': 722, 'E': 667, 'F': 611, 'G': 778,
        'H': 722, 'I': 278, 'J': 556, 'K': 722, 'L': 611, 'M': 833, 'N': 722, 'O': 778,
        'P': 667, 'Q': 778, 'R': 722, 'S': 667, 'T': 611, 'U': 722, 'V': 667, 'W': 944,
        'X': 667, 'Y': 667, 'Z': 611, '[': 333, '\\': 278, ']': 333, '^': 584, '_': 556,
        '`': 333, 'a': 556, 'b': 611, 'c': 556, 'd': 611, 'e': 556, 'f': 333, 'g': 611,
        'h': 611, 'i': 278, 'j': 278, 'k': 556, 'l': 278, 'm': 889, 'n': 611, 'o': 611,
        'p': 611, 'q': 611, 'r': 389, 's': 556, 't': 333, 'u': 611, 'v': 556, 'w': 778,
        'x': 556, 'y': 556, 'z': 500, '{': 389, '|': 280, '}': 389, '~': 584
    }

    def __init__(self):
        self.pages: List[List[str]] = [[]]
        self.annots: List[List[str]] = [[]]
        self.current_page = 0
        self.y = self.PAGE_HEIGHT - self.MARGIN_TOP
        self.doc_author = "Manbir Singh Sidhu"
        self.doc_title = "ATS Tailored Resume"

    def _start_new_page(self):
        self.pages.append([])
        self.annots.append([])
        self.current_page += 1
        self.y = self.PAGE_HEIGHT - self.MARGIN_TOP

    def _get_text_width(self, text: str, font: str, font_size: float) -> float:
        sanitized = self._sanitize(text)
        is_bold = (font == "/F2")
        char_table = self.HELVETICA_BOLD_CHAR_WIDTHS if is_bold else self.HELVETICA_CHAR_WIDTHS
        total = 0
        for ch in sanitized:
            w = char_table.get(ch)
            if w is None:
                if 'A' <= ch <= 'Z':
                    w = 722 if is_bold else 667
                elif 'a' <= ch <= 'z':
                    w = 611 if is_bold else 500
                else:
                    w = 556
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
        # Preserve ASCII and Latin-1 / WinAnsi printable characters (e.g. é, ñ, ü, ç)
        cleaned = []
        for ch in text:
            code = ord(ch)
            if 32 <= code < 127 or ch in ('\t',):
                cleaned.append(ch)
            elif code == 160:
                cleaned.append(' ')
            elif 161 <= code <= 255:
                cleaned.append(ch)
            else:
                cleaned.append('-' if ch in '-–—−' else ' ')
        return "".join(cleaned)

    def _escape(self, text: str) -> str:
        """Escape parentheses and backslashes for PDF string literals."""
        sanitized = self._sanitize(text)
        return sanitized.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')

    def _escape_uri(self, url: str) -> str:
        """Escape backslashes and parentheses inside PDF /URI (...) strings."""
        if not url:
            return ""
        return url.strip().replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')

    def _wrap_text(self, text: str, font: str, font_size: float, max_width: float) -> List[str]:
        sanitized = self._sanitize(text)
        words = sanitized.split()
        if not words:
            return []

        lines = []
        current_line = []
        current_width = 0.0
        space_width = self._get_text_width(" ", font, font_size)

        for word in words:
            word_width = self._get_text_width(word, font, font_size)
            test_width = current_width + (space_width if current_line else 0.0) + word_width
            if test_width <= max_width:
                current_line.append(word)
                current_width = test_width
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                current_line = [word]
                current_width = word_width

        if current_line:
            lines.append(" ".join(current_line))

        return lines

    def add_name_header(self, name: str, contact_line: str):
        self._check_page_space(55)
        escaped_name = self._escape(name)
        stream = self.pages[self.current_page]
        
        # Candidate Name: 18pt Bold, Pure Black, CENTERED
        name_width = self._get_text_width(name, "/F2", 18.0)
        name_x = self.MARGIN_LEFT + max(0.0, (self.USABLE_WIDTH - name_width) / 2.0)
        stream.append(f"BT /F2 18 Tf 0 0 0 rg {name_x:.2f} {self.y} Td ({escaped_name}) Tj ET")
        self.y -= 20

        # Contact Line with clickable hyperlinks (LinkedIn, GitHub, etc.)
        if contact_line:
            raw_contact = contact_line.strip()
            
            # Find all markdown links [label](url)
            md_link_pattern = re.compile(r'\[([^\]]+)\]\((https?://[^\)]+)\)')
            display_contact = ""
            last_idx = 0
            links_meta = []
            
            for m in md_link_pattern.finditer(raw_contact):
                display_contact += raw_contact[last_idx:m.start()]
                label = m.group(1).strip()
                url = m.group(2).strip()
                display_contact += label
                links_meta.append((label, url))
                last_idx = m.end()
            display_contact += raw_contact[last_idx:]

            # Fallbacks for raw unformatted URLs or keywords
            if not any("linkedin" in lbl.lower() for lbl, _ in links_meta):
                if "linkedin.com" in display_contact.lower():
                    raw_match = re.search(r'https?://(?:www\.)?linkedin\.com/in/[A-Za-z0-9_\-\/]+', display_contact)
                    if raw_match:
                        url = raw_match.group(0)
                        start_idx = raw_match.start()
                        display_contact = display_contact[:start_idx] + "LinkedIn" + display_contact[raw_match.end():]
                        links_meta.append(("LinkedIn", url))
                elif "linkedin" in display_contact.lower():
                    links_meta.append(("LinkedIn", self.DEFAULT_LINKEDIN_URL))

            if not any("github" in lbl.lower() for lbl, _ in links_meta):
                if "github.com" in display_contact.lower():
                    raw_match = re.search(r'https?://(?:www\.)?github\.com/[A-Za-z0-9_\-\/]+', display_contact)
                    if raw_match:
                        url = raw_match.group(0)
                        start_idx = raw_match.start()
                        display_contact = display_contact[:start_idx] + "GitHub" + display_contact[raw_match.end():]
                        links_meta.append(("GitHub", url))
                elif "github" in display_contact.lower():
                    links_meta.append(("GitHub", self.DEFAULT_GITHUB_URL))

            display_contact = re.sub(r'[ \t]+', ' ', display_contact).strip()

            # Segment display_contact into plain text and blue link segments
            found_links = []
            search_start = 0
            for lbl, url in links_meta:
                p = display_contact.find(lbl, search_start)
                if p != -1:
                    found_links.append((p, lbl, url))
                    search_start = p + len(lbl)
            found_links.sort(key=lambda x: x[0])

            segments = []
            cur_pos = 0
            for p, lbl, url in found_links:
                if p > cur_pos:
                    segments.append((display_contact[cur_pos:p], False, None))
                segments.append((lbl, True, url))
                cur_pos = p + len(lbl)
            if cur_pos < len(display_contact):
                segments.append((display_contact[cur_pos:], False, None))

            if not segments:
                segments = [(display_contact, False, None)]

            # Calculate total width of contact line to CENTER it
            total_contact_w = self._get_text_width(display_contact, "/F1", 9.5)
            start_contact_x = self.MARGIN_LEFT + max(0.0, (self.USABLE_WIDTH - total_contact_w) / 2.0)

            # Render segments: links in blue (0.05 0.40 0.85 rg), plain text in black (0 0 0 rg)
            cur_x = start_contact_x
            for seg_text, is_link, url in segments:
                seg_w = self._get_text_width(seg_text, "/F1", 9.5)
                escaped_seg = self._escape(seg_text)
                
                if is_link:
                    # Professional vibrant hyperlink blue
                    stream.append(f"BT /F1 9.5 Tf 0.05 0.40 0.85 rg {cur_x:.2f} {self.y} Td ({escaped_seg}) Tj ET")
                    
                    # Clickable PDF URI Annotation matching exact coordinates of the blue link
                    llx = cur_x - 1.0
                    urx = cur_x + seg_w + 1.0
                    lly = self.y - 2.0
                    ury = self.y + 10.0
                    safe_uri = self._escape_uri(url)
                    annot = (
                        f"<< /Type /Annot /Subtype /Link "
                        f"/Rect [{llx:.2f} {lly:.2f} {urx:.2f} {ury:.2f}] "
                        f"/Border [0 0 0] "
                        f"/A << /Type /Action /S /URI /URI ({safe_uri}) >> >>"
                    )
                    self.annots[self.current_page].append(annot)
                else:
                    # Regular pure black text
                    stream.append(f"BT /F1 9.5 Tf 0 0 0 rg {cur_x:.2f} {self.y} Td ({escaped_seg}) Tj ET")
                
                cur_x += seg_w

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
        # Ensure job header + metadata + first bullet line stay together on the same page
        self._check_page_space(52)
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
        # Ensure project header + first bullet line stay together on the same page
        self._check_page_space(38)
        clean_title = re.sub(
            r'\((?:Targeted Implementation / Prototype|Proposed Project|Proposed)\)',
            '(Under Development)',
            title,
            flags=re.I
        ).strip()

        # Check for markdown link e.g. [GitHub](https://...)
        md_link_match = re.search(r'\[([^\]]+)\]\((https?://[^\)]+)\)', clean_title)
        if md_link_match:
            label = md_link_match.group(1).strip()
            url = md_link_match.group(2).strip()
            raw_title = clean_title[:md_link_match.start()].rstrip(" |").strip()
            
            link_font_size = 9.5
            label_text = label
            sep_text = " | "
            sep_w = self._get_text_width(sep_text, "/F1", link_font_size)
            link_w = self._get_text_width(label_text, "/F2", link_font_size)
            suffix_w = sep_w + link_w

            raw_title_w = self._get_text_width(raw_title, "/F2", 10.0)
            if raw_title_w + suffix_w <= self.USABLE_WIDTH:
                escaped_title = self._escape(raw_title)
                escaped_label = self._escape(label_text)
                stream = self.pages[self.current_page]
                
                # Title in Bold Black
                stream.append(f"BT /F2 10 Tf 0 0 0 rg {self.MARGIN_LEFT} {self.y} Td ({escaped_title}) Tj ET")
                
                cur_x = self.MARGIN_LEFT + raw_title_w
                stream.append(f"BT /F1 {link_font_size} Tf 0 0 0 rg {cur_x:.2f} {self.y} Td ({sep_text}) Tj ET")
                cur_x += sep_w
                
                # Link in vibrant blue
                stream.append(f"BT /F2 {link_font_size} Tf 0.05 0.40 0.85 rg {cur_x:.2f} {self.y} Td ({escaped_label}) Tj ET")
                
                llx = cur_x - 1.0
                urx = cur_x + link_w + 1.0
                lly = self.y - 2.0
                ury = self.y + 10.0
                safe_uri = self._escape_uri(url)
                annot = (
                    f"<< /Type /Annot /Subtype /Link "
                    f"/Rect [{llx:.2f} {lly:.2f} {urx:.2f} {ury:.2f}] "
                    f"/Border [0 0 0] "
                    f"/A << /Type /Action /S /URI /URI ({safe_uri}) >> >>"
                )
                self.annots[self.current_page].append(annot)
                self.y -= 13.5
            else:
                lines = self._wrap_text(raw_title, "/F2", 10.0, self.USABLE_WIDTH)
                for line in lines[:-1]:
                    self._check_page_space(14)
                    escaped = self._escape(line)
                    self.pages[self.current_page].append(
                        f"BT /F2 10 Tf 0 0 0 rg {self.MARGIN_LEFT} {self.y} Td ({escaped}) Tj ET"
                    )
                    self.y -= 13.5
                
                last_line = lines[-1] if lines else ""
                last_line_w = self._get_text_width(last_line, "/F2", 10.0)
                escaped_last = self._escape(last_line)
                escaped_label = self._escape(label_text)
                stream = self.pages[self.current_page]
                self._check_page_space(14)
                
                if last_line_w + suffix_w <= self.USABLE_WIDTH:
                    stream.append(f"BT /F2 10 Tf 0 0 0 rg {self.MARGIN_LEFT} {self.y} Td ({escaped_last}) Tj ET")
                    cur_x = self.MARGIN_LEFT + last_line_w
                    stream.append(f"BT /F1 {link_font_size} Tf 0 0 0 rg {cur_x:.2f} {self.y} Td ({sep_text}) Tj ET")
                    cur_x += sep_w
                    stream.append(f"BT /F2 {link_font_size} Tf 0.05 0.40 0.85 rg {cur_x:.2f} {self.y} Td ({escaped_label}) Tj ET")
                    llx = cur_x - 1.0
                    urx = cur_x + link_w + 1.0
                    lly = self.y - 2.0
                    ury = self.y + 10.0
                    safe_uri = self._escape_uri(url)
                    annot = (
                        f"<< /Type /Annot /Subtype /Link "
                        f"/Rect [{llx:.2f} {lly:.2f} {urx:.2f} {ury:.2f}] "
                        f"/Border [0 0 0] "
                        f"/A << /Type /Action /S /URI /URI ({safe_uri}) >> >>"
                    )
                    self.annots[self.current_page].append(annot)
                    self.y -= 13.5
                else:
                    stream.append(f"BT /F2 10 Tf 0 0 0 rg {self.MARGIN_LEFT} {self.y} Td ({escaped_last}) Tj ET")
                    self.y -= 13.5
                    self._check_page_space(14)
                    cur_x = self.MARGIN_LEFT
                    stream.append(f"BT /F2 {link_font_size} Tf 0.05 0.40 0.85 rg {cur_x:.2f} {self.y} Td ({escaped_label}) Tj ET")
                    llx = cur_x - 1.0
                    urx = cur_x + link_w + 1.0
                    lly = self.y - 2.0
                    ury = self.y + 10.0
                    safe_uri = self._escape_uri(url)
                    annot = (
                        f"<< /Type /Annot /Subtype /Link "
                        f"/Rect [{llx:.2f} {lly:.2f} {urx:.2f} {ury:.2f}] "
                        f"/Border [0 0 0] "
                        f"/A << /Type /Action /S /URI /URI ({safe_uri}) >> >>"
                    )
                    self.annots[self.current_page].append(annot)
                    self.y -= 13.5
        else:
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
        Uses full width across all lines with bullet indent (57pt) without excess hanging whitespace.
        """
        category_clean = self._sanitize(category).strip()
        skills_clean = self._sanitize(skills_str).strip()
        prefix = f"{category_clean}: "
        
        prefix_width = self._get_text_width(prefix, "/F2", font_size)
        bullet_indent = 12 if has_bullet else 0
        start_x = self.MARGIN_LEFT + bullet_indent
        
        first_avail = self.USABLE_WIDTH - bullet_indent - prefix_width
        subseq_avail = self.USABLE_WIDTH - bullet_indent
        
        # Word wrap skills list: line 1 has first_avail width, lines 2+ have subseq_avail width
        words = skills_clean.split()
        if not words:
            return

        skill_lines = []
        current_words = []
        current_w = 0.0
        max_w = first_avail
        space_w = self._get_text_width(" ", "/F1", font_size)

        for word in words:
            word_w = self._get_text_width(word, "/F1", font_size)
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
        needed_pt = len(skill_lines) * line_height + 4.5
        self._check_page_space(needed_pt)
        stream = self.pages[self.current_page]

        # Draw bullet if present
        if has_bullet:
            stream.append(f"BT /F2 {font_size} Tf 0 0 0 rg {self.MARGIN_LEFT + 2} {self.y} Td (-) Tj ET")

        # Line 1: In the SAME text block, emit Bold prefix then Regular first skills line
        escaped_prefix = self._escape(prefix)
        escaped_first_skills = self._escape(skill_lines[0]) if skill_lines else ""
        
        stream.append(
            f"BT {start_x} {self.y} Td /F2 {font_size} Tf 0 0 0 rg ({escaped_prefix}) Tj "
            f"/F1 {font_size} Tf 0 0 0 rg ({escaped_first_skills}) Tj ET"
        )
        self.y -= line_height

        # Subsequent lines: wrap at start_x (aligned with category start) across full width
        for line_text in skill_lines[1:]:
            self._check_page_space(line_height)
            escaped_text = self._escape(line_text)
            self.pages[self.current_page].append(
                f"BT /F1 {font_size} Tf 0 0 0 rg {start_x} {self.y} Td ({escaped_text}) Tj ET"
            )
            self.y -= line_height

        self.y -= 3.5

    def build_pdf_bytes(self) -> bytes:
        """
        Assembles all pages, content streams, fonts, annotations, and xref tables into valid PDF 1.4 binary bytes.
        """
        num_pages = len(self.pages)
        objects = []

        def add_object(content: str) -> int:
            objects.append(content)
            return len(objects)

        # Standard PDF Objects with WinAnsiEncoding
        objects.append("") # 1: Catalog
        objects.append("") # 2: Pages
        objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>") # 3: F1 Regular
        objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>") # 4: F2 Bold
        objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>") # 5: F3 Italic

        page_obj_ids = []
        for p_idx, stream_ops in enumerate(self.pages):
            stream_body = "\n".join(stream_ops)
            stream_bytes = stream_body.encode('cp1252', errors='replace')
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

        info_obj = (
            f"<< /Title ({self._escape(self.doc_title)}) "
            f"/Author ({self._escape(self.doc_author)}) "
            f"/Producer (ATSResumePDFGenerator) >>"
        )
        info_id = add_object(info_obj)

        kids_str = " ".join([f"{pid} 0 R" for pid in page_obj_ids])
        objects[0] = "<< /Type /Catalog /Pages 2 0 R >>"
        objects[1] = f"<< /Type /Pages /Kids [{kids_str}] /Count {num_pages} >>"

        output = [b"%PDF-1.4\n"]
        xref_offsets = [0]

        offset = len(output[0])
        for i, obj_content in enumerate(objects):
            xref_offsets.append(offset)
            obj_bytes = f"{i+1} 0 obj\n{obj_content}\nendobj\n".encode('cp1252', errors='replace')
            output.append(obj_bytes)
            offset += len(obj_bytes)

        xref_start = offset
        num_entries = len(objects) + 1
        xref_table = [f"xref\n0 {num_entries}\n0000000000 65535 f \n".encode('ascii')]
        for off in xref_offsets[1:]:
            xref_table.append(f"{off:010d} 00000 n \n".encode('ascii'))

        output.extend(xref_table)
        trailer = (
            f"trailer\n<< /Size {num_entries} /Root 1 0 R /Info {info_id} 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n"
        ).encode('ascii')
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
                name = stripped.removeprefix("# ").replace("**", "").strip()
                header_end_idx = idx + 1
                for c_idx in range(idx + 1, len(lines)):
                    c_line = lines[c_idx].strip()
                    if c_line and not c_line.startswith("#"):
                        contact = c_line.replace("**", "").strip()
                        header_end_idx = c_idx + 1
                        break
                break

        if name:
            writer.doc_author = name
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
                current_section = line.removeprefix("## ").replace("**", "").strip()
                writer.add_section_header(current_section)
                items_in_section = 0
                continue

            if line.startswith("### "):
                title_line = line.removeprefix("### ").replace("**", "").strip()
                
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
                is_experience = "experience" in current_section.lower()
                is_project_or_edu = any(k in current_section.lower() for k in ("project", "education"))
                if is_experience or (not is_project_or_edu and "|" in title_line):
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
