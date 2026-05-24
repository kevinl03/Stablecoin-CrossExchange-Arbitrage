"""
export_script_docx.py — parse script.md and produce a review-friendly Word document.
Run: python3 docs/latex/StablecoinArbitrage_GSS2026/presentation/export_script_docx.py

The parser reads script.md directly, so the docx is always in sync with the script.
"""

import sys, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "venv312/lib/python3.14/site-packages"))

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

SRC = Path(__file__).parent / "script.md"
OUT = Path(__file__).parent / "script_for_review.docx"

# ── colours ────────────────────────────────────────────────────────────────────
SFU_RED   = RGBColor(0xCC, 0x06, 0x33)
DARK      = RGBColor(0x1A, 0x1A, 0x2E)
MGREY     = RGBColor(0x88, 0x88, 0x88)
DGREY     = RGBColor(0x44, 0x44, 0x44)

# ── xml helpers ────────────────────────────────────────────────────────────────

def _shd(cell_or_para, hex_fill: str):
    """Apply background shading to a table cell or paragraph."""
    if hasattr(cell_or_para, "_tc"):          # table cell
        tc = cell_or_para._tc
        tcPr = tc.get_or_add_tcPr()
        el = OxmlElement("w:shd")
        el.set(qn("w:val"), "clear")
        el.set(qn("w:color"), "auto")
        el.set(qn("w:fill"), hex_fill)
        tcPr.append(el)
    else:                                     # paragraph
        pPr = cell_or_para._p.get_or_add_pPr()
        el = OxmlElement("w:shd")
        el.set(qn("w:val"), "clear")
        el.set(qn("w:color"), "auto")
        el.set(qn("w:fill"), hex_fill)
        pPr.append(el)


def _left_border(para, hex_color: str, width: int = 18):
    pPr = para._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), str(width))
    left.set(qn("w:space"), "6")
    left.set(qn("w:color"), hex_color)
    pBdr.append(left)
    pPr.append(pBdr)


def _hr(doc):
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bot = OxmlElement("w:bottom")
    bot.set(qn("w:val"), "single"); bot.set(qn("w:sz"), "4")
    bot.set(qn("w:space"), "1");    bot.set(qn("w:color"), "CCCCCC")
    pBdr.append(bot)
    pPr.append(pBdr)
    p.paragraph_format.space_after = Pt(4)


def _table(doc, headers, rows, col_widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = h
        c.paragraphs[0].runs[0].font.bold = True
        c.paragraphs[0].runs[0].font.size = Pt(10)
        c.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _shd(c, "CC0633")
    for ri, row_data in enumerate(rows):
        fill = "F2F2F7" if ri % 2 == 0 else "FFFFFF"
        row = t.add_row()
        for i, txt in enumerate(row_data):
            c = row.cells[i]
            c.text = txt
            c.paragraphs[0].runs[0].font.size = Pt(10)
            _shd(c, fill)
    if col_widths:
        for i, w in enumerate(col_widths):
            for row in t.rows:
                row.cells[i].width = Inches(w)
    doc.add_paragraph()


# ── styles ─────────────────────────────────────────────────────────────────────

def _style(doc, name, base="Normal",
           font_name="Arial", font_pt=12, bold=False, italic=False,
           color=DARK, space_before=0, space_after=6, indent=0.0):
    styles = doc.styles
    if name in [s.name for s in styles]:
        return styles[name]
    s = styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
    s.base_style = styles[base]
    s.font.name  = font_name
    s.font.size  = Pt(font_pt)
    s.font.bold  = bold
    s.font.italic = italic
    s.font.color.rgb = color
    s.paragraph_format.space_before = Pt(space_before)
    s.paragraph_format.space_after  = Pt(space_after)
    if indent:
        s.paragraph_format.left_indent = Inches(indent)
    return s


def setup_styles(doc):
    _style(doc, "SlideHeader", font_pt=16, bold=True, color=SFU_RED,
           space_before=18, space_after=4)
    _style(doc, "Spoken",      font_name="Georgia", font_pt=12, italic=True,
           color=DARK, space_before=4, space_after=6, indent=0.3)
    _style(doc, "Direction",   font_pt=10, italic=True, color=MGREY,
           space_before=2, space_after=2, indent=0.3)
    _style(doc, "PauseBeat",   font_pt=10, bold=True,
           color=RGBColor(0x22, 0x77, 0xCC),
           space_before=2, space_after=2, indent=0.3)
    _style(doc, "Visual",      font_pt=10,
           color=RGBColor(0x6D, 0x40, 0x00),
           space_before=2, space_after=6, indent=0.3)
    _style(doc, "SlideCue",    font_name="Courier New", font_pt=9,
           color=DGREY, space_before=2, space_after=4, indent=0.3)
    _style(doc, "QAHeader",    font_pt=13, bold=True,
           color=RGBColor(0x1B, 0x5E, 0x20),
           space_before=14, space_after=4)
    _style(doc, "QAOpener",    font_pt=10, bold=True,
           color=RGBColor(0x1B, 0x5E, 0x20),
           space_before=2, space_after=2, indent=0.3)
    _style(doc, "QABody",      font_pt=11, color=DARK,
           space_before=2, space_after=8, indent=0.3)
    _style(doc, "Note",        font_pt=10, italic=True, color=MGREY,
           space_before=4, space_after=4)


# ── line classifier ────────────────────────────────────────────────────────────

def classify(line: str):
    """Return (kind, text) for a single markdown line."""
    s = line.strip()
    if not s:
        return ("blank", "")
    if re.match(r"^#{1,2} ", s):
        return ("h1", s.lstrip("# "))
    if re.match(r"^### ", s):
        return ("h3", s.lstrip("# "))
    if re.match(r"^---+$", s):
        return ("hr", "")
    if s.startswith("> **Visual:**"):
        return ("visual", s[len("> **Visual:**"):].strip())
    if re.match(r"^>\s", s):
        return ("blockquote", s[2:].strip())
    if re.match(r"^\`\[SLIDE:", s):
        inner = re.sub(r"^\`\[", "[", re.sub(r"\]\`$", "]", s))
        return ("slidecue", inner)
    if re.match(r"^\`\[DIRECTION:", s):
        inner = re.sub(r"^\`\[", "[", re.sub(r"\]\`$", "]", s))
        return ("direction", inner)
    if re.match(r"^\`\[(PAUSE|BEAT)", s):
        inner = re.sub(r"^\`\[", "[", re.sub(r"\]\`$", "]", s))
        return ("pause", inner)
    if re.match(r"^\*\"", s) or re.match(r'^"', s):
        # spoken word — strip surrounding *"..."* or "..."
        text = re.sub(r"^\*\"", "", re.sub(r"\"\*$", "", s))
        text = re.sub(r'^"', "", re.sub(r'"$', "", text))
        return ("spoken", text)
    if re.match(r"^\*\*One-line opener:\*\*", s):
        text = re.sub(r"^\*\*One-line opener:\*\*\s*\*\"?", "", s).rstrip("\"*")
        return ("qaopener", text)
    if re.match(r"^\*\*Full answer:\*\*", s):
        text = re.sub(r"^\*\*Full answer:\*\*\s*", "", s)
        return ("qabody", text)
    if re.match(r"^\|", s):
        return ("table_row", s)
    if re.match(r"^\*\*Practice tip", s):
        return ("note", re.sub(r"^\*\*Practice tip.*?\*\*", "", s).strip())
    return ("body", s)


# ── section detector ───────────────────────────────────────────────────────────

SLIDE_RE  = re.compile(r"^SLIDE (\d+) · (.+?) · (.+)$")
QA_RE     = re.compile(r"^Q(\d+) — (.+)")
TIMING_RE = re.compile(r"^Timing Reference")
VISUAL_RE = re.compile(r"^Slide Visual Guide")
CHANGES_RE = re.compile(r"^What Changed")


# ── document builder ───────────────────────────────────────────────────────────

def build():
    lines = SRC.read_text().splitlines()
    doc = Document()

    section = doc.sections[0]
    section.page_width    = Inches(8.5)
    section.page_height   = Inches(11)
    section.left_margin   = Inches(1.0)
    section.right_margin  = Inches(2.2)   # wide for reviewer comments
    section.top_margin    = Inches(1.0)
    section.bottom_margin = Inches(1.0)

    setup_styles(doc)

    # ── document title block ───────────────────────────────────────────────────
    h = doc.add_heading("Presentation Script — GSS 2026", level=1)
    h.runs[0].font.color.rgb = SFU_RED

    state = "preamble"          # preamble | slides | qa | timing | visual | changes
    i = 0
    table_buf: list[list[str]] = []

    def flush_table():
        nonlocal table_buf
        if not table_buf:
            return
        # First row is headers, remaining are data
        headers = [c.strip(" |") for c in table_buf[0].split("|") if c.strip(" |")]
        rows = []
        for row_line in table_buf[2:]:   # skip separator row
            cells = [c.strip() for c in row_line.split("|") if c.strip()]
            if cells:
                rows.append(cells)
        col_w = 8.2 / max(len(headers), 1)
        _table(doc, headers, rows, [col_w] * len(headers))
        table_buf = []

    while i < len(lines):
        raw = lines[i]
        kind, text = classify(raw)
        i += 1

        # ── table accumulator ─────────────────────────────────────────────────
        if kind == "table_row":
            table_buf.append(raw.strip())
            continue
        else:
            flush_table()

        # ── blank / hr ────────────────────────────────────────────────────────
        if kind == "blank":
            continue
        if kind == "hr":
            _hr(doc)
            continue

        # ── top-level headings ────────────────────────────────────────────────
        if kind == "h1":
            clean = re.sub(r"\*+", "", text).strip()

            if SLIDE_RE.match(clean):
                state = "slides"
                m = SLIDE_RE.match(clean)
                label = f"SLIDE {m.group(1)} · {m.group(2)} · {m.group(3)}"
                p = doc.add_paragraph(label, style="SlideHeader")
                _left_border(p, "CC0633", 24)

            elif re.match(r"^Q&A Rebuttal", clean):
                state = "qa"
                doc.add_page_break()
                h2 = doc.add_heading(clean, level=1)
                h2.runs[0].font.color.rgb = RGBColor(0x1B, 0x5E, 0x20)
                note = doc.add_paragraph(
                    "Lead with the one-line opener every time. "
                    "Aim for 30–45 seconds per answer.", style="Note")

            elif TIMING_RE.search(clean):
                state = "timing"
                doc.add_page_break()
                doc.add_heading(clean, level=2)

            elif VISUAL_RE.search(clean):
                state = "visual"
                doc.add_heading(clean, level=2)

            elif CHANGES_RE.search(clean):
                state = "changes"
                doc.add_heading(clean, level=2)

            else:
                # Generic H1/H2
                h_level = 1 if raw.startswith("# ") else 2
                hh = doc.add_heading(clean, level=h_level)
                if hh.runs:
                    hh.runs[0].font.color.rgb = DARK

            continue

        # ── h3 (sub-headings and Q headers) ───────────────────────────────────
        if kind == "h3":
            clean = re.sub(r"\*+", "", text).strip()
            if state == "qa" and QA_RE.match(clean):
                p = doc.add_paragraph(clean, style="QAHeader")
                _left_border(p, "1B5E20", 18)
            else:
                doc.add_heading(clean, level=3)
            continue

        # ── slide content ──────────────────────────────────────────────────────
        if state == "slides":
            if kind == "slidecue":
                p = doc.add_paragraph(style="SlideCue")
                _shd(p, "E8EAF6")
                p.paragraph_format.left_indent = Inches(0.3)
                run = p.add_run(text)
                run.font.name = "Courier New"; run.font.size = Pt(9)
                run.font.color.rgb = DGREY
            elif kind == "visual":
                p = doc.add_paragraph(style="Visual")
                _left_border(p, "FF9800", 12)
                _shd(p, "FFF8E1")
                r1 = p.add_run("▶ Visual: ")
                r1.font.bold = True
                r1.font.color.rgb = RGBColor(0xE6, 0x51, 0x00)
                r2 = p.add_run(text)
                r2.font.color.rgb = RGBColor(0x6D, 0x40, 0x00)
            elif kind == "blockquote":
                p = doc.add_paragraph(style="Visual")
                _left_border(p, "FF9800", 8)
                _shd(p, "FFF8E1")
                p.add_run(text).font.color.rgb = RGBColor(0x6D, 0x40, 0x00)
            elif kind == "direction":
                p = doc.add_paragraph(style="Direction")
                p.add_run(text).font.color.rgb = MGREY
            elif kind == "pause":
                p = doc.add_paragraph(style="PauseBeat")
                p.add_run(text).font.color.rgb = RGBColor(0x22, 0x77, 0xCC)
            elif kind == "spoken":
                # Multi-paragraph spoken chunks (split by blank lines within *)
                for chunk in text.split("\\n\\n"):
                    chunk = chunk.strip()
                    if chunk:
                        p = doc.add_paragraph(style="Spoken")
                        p.add_run(f'"{chunk}"')
            elif kind == "body":
                clean = re.sub(r"\*+", "", text)
                if clean:
                    p = doc.add_paragraph(clean)
                    p.paragraph_format.left_indent = Inches(0.3)
                    if p.runs:
                        p.runs[0].font.size = Pt(11)
            continue

        # ── Q&A content ───────────────────────────────────────────────────────
        if state == "qa":
            if kind == "qaopener":
                p = doc.add_paragraph(style="QAOpener")
                _shd(p, "E8F5E9")
                r = p.add_run("One-liner:  ")
                r.font.bold = True
                r.font.color.rgb = RGBColor(0x1B, 0x5E, 0x20)
                r2 = p.add_run(f'"{text}"')
                r2.font.italic = True
                r2.font.color.rgb = DARK
            elif kind == "qabody":
                p = doc.add_paragraph(text, style="QABody")
            elif kind == "body":
                clean = re.sub(r"\*+", "", text)
                if clean:
                    doc.add_paragraph(clean, style="QABody")
            continue

        # ── timing / visual guide / changes: fall through to body ─────────────
        if kind == "body":
            clean = re.sub(r"\*+", "", text).strip()
            if clean:
                doc.add_paragraph(clean, style="Note" if state == "timing" else "Normal")

    flush_table()

    doc.save(str(OUT))
    print(f"wrote {OUT}  ({OUT.stat().st_size / 1e3:.1f} KB)")


if __name__ == "__main__":
    build()
