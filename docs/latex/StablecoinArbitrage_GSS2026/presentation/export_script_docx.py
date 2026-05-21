"""
export_script_docx.py — convert script.md to a review-friendly .docx
Run: python3 docs/latex/StablecoinArbitrage_GSS2026/presentation/export_script_docx.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "venv312/lib/python3.14/site-packages"))

from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import re

SRC  = Path(__file__).parent / "script.md"
OUT  = Path(__file__).parent / "script_for_review.docx"

# ── colour palette ────────────────────────────────────────────────────────────
SFU_RED   = RGBColor(0xCC, 0x06, 0x33)
DARK      = RGBColor(0x1A, 0x1A, 0x2E)
DIRN_GREY = RGBColor(0x55, 0x55, 0x55)
SLIDE_BG  = RGBColor(0xF2, 0xF2, 0xF7)
VISUAL_BG = RGBColor(0xFF, 0xF3, 0xE0)
QA_BG     = RGBColor(0xE8, 0xF5, 0xE9)


# ── helpers ───────────────────────────────────────────────────────────────────

def set_para_shading(para, hex_fill: str):
    """Add background shading to a paragraph."""
    pPr = para._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    pPr.append(shd)


def set_left_border(para, hex_color: str, width_pts: int = 18):
    """Add a coloured left border (like a blockquote bar)."""
    pPr = para._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), str(width_pts))
    left.set(qn("w:space"), "6")
    left.set(qn("w:color"), hex_color)
    pBdr.append(left)
    pPr.append(pBdr)


def add_hr(doc):
    """Thin horizontal rule."""
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "CCCCCC")
    pBdr.append(bottom)
    pPr.append(pBdr)
    p.paragraph_format.space_after = Pt(4)


def add_table_from_rows(doc, headers: list[str], rows: list[list[str]],
                        col_widths: list[float] | None = None):
    """Add a styled table."""
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    # Header row
    hdr_row = t.rows[0]
    for i, h in enumerate(headers):
        cell = hdr_row.cells[i]
        cell.text = h
        run = cell.paragraphs[0].runs[0]
        run.font.bold = True
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), "CC0633")
        tcPr.append(shd)
    # Data rows
    for ri, row_data in enumerate(rows):
        row = t.add_row()
        fill = "F2F2F7" if ri % 2 == 0 else "FFFFFF"
        for i, cell_text in enumerate(row_data):
            cell = row.cells[i]
            cell.text = cell_text
            run = cell.paragraphs[0].runs[0]
            run.font.size = Pt(10)
            tc = cell._tc
            tcPr = tc.get_or_add_tcPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), fill)
            tcPr.append(shd)
    if col_widths:
        for i, w in enumerate(col_widths):
            for row in t.rows:
                row.cells[i].width = Inches(w)
    doc.add_paragraph()


# ── style setup ───────────────────────────────────────────────────────────────

def setup_styles(doc):
    styles = doc.styles

    def ensure(name, base="Normal"):
        if name in [s.name for s in styles]:
            return styles[name]
        s = styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        s.base_style = styles[base]
        return s

    # Slide header
    sh = ensure("SlideHeader")
    sh.font.name = "Arial"
    sh.font.size = Pt(16)
    sh.font.bold = True
    sh.font.color.rgb = SFU_RED
    sh.paragraph_format.space_before = Pt(18)
    sh.paragraph_format.space_after  = Pt(4)
    sh.paragraph_format.keep_with_next = True

    # Spoken word
    sp = ensure("Spoken")
    sp.font.name = "Georgia"
    sp.font.size = Pt(12)
    sp.font.italic = True
    sp.font.color.rgb = DARK
    sp.paragraph_format.space_before = Pt(4)
    sp.paragraph_format.space_after  = Pt(6)
    sp.paragraph_format.left_indent  = Inches(0.3)

    # Stage direction
    dr = ensure("Direction")
    dr.font.name = "Arial"
    dr.font.size = Pt(10)
    dr.font.italic = True
    dr.font.color.rgb = DIRN_GREY
    dr.paragraph_format.space_before = Pt(2)
    dr.paragraph_format.space_after  = Pt(2)
    dr.paragraph_format.left_indent  = Inches(0.3)

    # Visual spec note
    vis = ensure("Visual")
    vis.font.name = "Arial"
    vis.font.size = Pt(10)
    vis.font.color.rgb = RGBColor(0x6D, 0x40, 0x00)
    vis.paragraph_format.space_before = Pt(2)
    vis.paragraph_format.space_after  = Pt(6)
    vis.paragraph_format.left_indent  = Inches(0.3)

    # Pause / beat
    pb = ensure("Pause")
    pb.font.name = "Arial"
    pb.font.size = Pt(10)
    pb.font.bold = True
    pb.font.color.rgb = RGBColor(0x22, 0x77, 0xCC)
    pb.paragraph_format.space_before = Pt(2)
    pb.paragraph_format.space_after  = Pt(2)
    pb.paragraph_format.left_indent  = Inches(0.3)

    # Q&A question header
    qa = ensure("QAHeader")
    qa.font.name = "Arial"
    qa.font.size = Pt(13)
    qa.font.bold = True
    qa.font.color.rgb = RGBColor(0x1B, 0x5E, 0x20)
    qa.paragraph_format.space_before = Pt(14)
    qa.paragraph_format.space_after  = Pt(4)

    # One-liner label
    ol = ensure("Oneliner")
    ol.font.name = "Arial"
    ol.font.size = Pt(10)
    ol.font.bold = True
    ol.font.color.rgb = RGBColor(0x1B, 0x5E, 0x20)
    ol.paragraph_format.left_indent  = Inches(0.3)
    ol.paragraph_format.space_after  = Pt(2)

    # Body text for full answers
    ba = ensure("FullAnswer")
    ba.font.name = "Arial"
    ba.font.size = Pt(11)
    ba.font.color.rgb = DARK
    ba.paragraph_format.left_indent  = Inches(0.3)
    ba.paragraph_format.space_after  = Pt(8)

    # Timing table note
    nt = ensure("Note")
    nt.font.name = "Arial"
    nt.font.size = Pt(10)
    nt.font.italic = True
    nt.font.color.rgb = DIRN_GREY
    nt.paragraph_format.space_after  = Pt(4)


# ── main build ────────────────────────────────────────────────────────────────

def build():
    doc = Document()

    # Page margins — generous for reviewer comments
    section = doc.sections[0]
    section.page_width  = Inches(8.5)
    section.page_height = Inches(11)
    section.left_margin   = Inches(1.0)
    section.right_margin  = Inches(2.2)   # wide right margin for comments
    section.top_margin    = Inches(1.0)
    section.bottom_margin = Inches(1.0)

    setup_styles(doc)

    # ── Title block ──────────────────────────────────────────────────────────
    t = doc.add_heading("Presentation Script — GSS 2026", level=1)
    t.runs[0].font.color.rgb = SFU_RED

    doc.add_heading(
        '"Execution-Aware A* Search for Cross-Exchange Stablecoin Arbitrage"',
        level=2)

    p = doc.add_paragraph("Kevin Litvin · Canadian AI 2026 Graduate Student Symposium")
    p.runs[0].font.bold = True
    p = doc.add_paragraph("8 minutes presented + 4 minutes Q&A")
    p.runs[0].font.italic = True
    p.runs[0].font.color.rgb = DIRN_GREY

    add_hr(doc)

    # ── How to use ───────────────────────────────────────────────────────────
    doc.add_heading("How to Use This Document", level=3)
    notes = [
        ("Italic text", "= your spoken words — read or memorize them."),
        ("[SLIDE: …]", "= advance to or reference the named slide."),
        ("[PAUSE]", "= stop speaking for 1–2 full seconds. Do not fill it."),
        ("[BEAT]", "= half-second breath before continuing."),
        ("[DIRECTION: …]", "= physical or delivery cue — not spoken."),
        ("Target pace", "~125 words per minute. Total spoken words: ~940."),
    ]
    t = doc.add_table(rows=1, cols=2)
    t.style = "Table Grid"
    t.rows[0].cells[0].text = "Marker"
    t.rows[0].cells[1].text = "Meaning"
    for cell in t.rows[0].cells:
        cell.paragraphs[0].runs[0].font.bold = True
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), "1A1A2E")
        tcPr.append(shd)
        cell.paragraphs[0].runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    for marker, meaning in notes:
        row = t.add_row()
        row.cells[0].text = marker
        row.cells[1].text = meaning
        row.cells[0].paragraphs[0].runs[0].font.bold = True
    t.columns[0].width = Inches(1.8)
    t.columns[1].width = Inches(4.5)
    doc.add_paragraph()

    # ── Judging criteria ─────────────────────────────────────────────────────
    doc.add_heading("Judging Criteria", level=3)
    add_table_from_rows(
        doc,
        ["Criterion", "Weight"],
        [
            ["Research clarity & significance", "25%"],
            ["Content accuracy & technical depth", "25%"],
            ["Narrative flow & organization", "20%"],
            ["Audience engagement & delivery", "15%"],
            ["Visual aid quality", "10%"],
            ["Q&A preparedness", "5%"],
        ],
        col_widths=[4.5, 1.0],
    )

    add_hr(doc)

    # ── SLIDES ───────────────────────────────────────────────────────────────
    slides = [
        {
            "header": "SLIDE 1 · Title · 0:00 – 0:55",
            "slide_cue": "[SLIDE: Title slide — your name, paper title, GSS 2026 logo, FullGraph.png as full-bleed background image]",
            "visual": "Use FullGraph.png as the slide background at low opacity. The audience sees a dense, beautiful network before you speak. Immediate curiosity — 'what is that?' — before a single word.",
            "content": [
                ("direction", "Walk to centre. Make eye contact with three different people. Let two full seconds of silence pass. Do not start talking immediately."),
                ("spoken",    "Before I start — quick show of hands."),
                ("direction", "Raise your own hand as you ask."),
                ("spoken",    "How many of you have ever sent money internationally — transferred between banks, used Wise, PayPal, anything like that?"),
                ("pause",     "[PAUSE — scan the room, nod.]"),
                ("spoken",    "Every one of those transfers was routed through a system trying to find the cheapest, fastest path through a global financial network."),
                ("pause",     "[BEAT]"),
                ("spoken",    "What I'm going to show you today is essentially Google Maps... for thirty-three trillion dollars."),
                ("direction", "Let that number land. Do not continue immediately. Hold eye contact."),
            ],
        },
        {
            "header": "SLIDE 2 · The Market · 0:55 – 1:45",
            "slide_cue": "[SLIDE: Bar chart — Mastercard $8T | Visa $15T | Stablecoins $33T (animated, reveal one bar at a time). USDT and USDC logos beside the stablecoin bar.]",
            "visual": "The bars should animate in one at a time, left to right, on click. The stablecoin bar should be noticeably taller — the contrast is the whole point.",
            "content": [
                ("spoken",  "Stablecoins — USDT, USDC, DAI. Digital dollars. Cryptocurrencies pegged one-to-one with fiat, sitting at the intersection of traditional finance and the crypto world."),
                ("spoken",  "Last year, stablecoins processed thirty-three trillion dollars in transaction volume."),
                ("pause",   "[PAUSE]"),
                ("spoken",  "More than Visa. More than Mastercard. Combined."),
                ("pause",   "[BEAT]"),
                ("spoken",  "Three hundred billion dollars in market capitalization. They are the liquidity highways of the entire crypto ecosystem — the bridge every trader crosses when moving capital between assets, exchanges, or borders."),
                ("spoken",  "So here is the question this research asks: those highways are fragmented across twelve independent exchanges, each pricing the same assets slightly differently at the same instant. Can we build a system smart enough to find and execute a profitable path through that fragmentation — accounting for every real-world cost?"),
                ("pause",   "[BEAT]"),
                ("spoken",  "That is what we set out to answer."),
            ],
        },
        {
            "header": "SLIDE 3 · The Problem · 1:45 – 2:55",
            "slide_cue": "[SLIDE: Split image — LEFT: clean A→B profitable cycle. RIGHT: same path with four red warning icons appearing one at a time: a fee tag, a price impact curve, a clock, an exchange suspension warning.]",
            "visual": "The left half shows what existing systems see — a clean arbitrage cycle. The right half reveals the execution reality. Animate the four icons on click, synchronized with the four spoken challenges.",
            "content": [
                ("direction", "Step slightly forward. This is where tension builds."),
                ("spoken",  "Imagine you are a quant trader. It is two in the morning. You are watching prices across twelve different exchanges and you see it — USDT is trading fractionally cheaper on Kraken than it is selling for on KuCoin. The gap is real. The math works."),
                ("spoken",  "Existing systems would tell you: there is an arbitrage opportunity here. Take it."),
                ("pause",   "[BEAT]"),
                ("spoken",  "But here is what those systems do not tell you."),
                ("direction","Count on fingers — slow, deliberate, one beat after each."),
                ("spoken",  "First — the taker fee at each exchange eats into your margin.\n\nSecond — your order size is large enough that buying on Kraken moves the price against you before your fill is complete. That is called slippage. Dynamic, live, and invisible to static models.\n\nThird — the blockchain transfer between exchanges takes time. The window may close while you are waiting for confirmations.\n\nFourth — an exchange might suspend withdrawals entirely. We have seen this happen overnight, without warning."),
                ("pause",   "[PAUSE]"),
                ("spoken",  "Liquidity. Slippage. Latency. Reliability."),
                ("pause",   "[BEAT]"),
                ("spoken",  "Bellman-Ford finds the cycle. One-hop and two-hop enumeration find the cycle. In our experiments, all three baselines fail entirely — they cannot identify a profitable executable path under these conditions. We needed something different."),
            ],
        },
        {
            "header": "SLIDE 4 · The Graph · 2:55 – 3:40",
            "slide_cue": "[SLIDE: FullGraph.png — full slide, clean, with one highlighted path glowing through it. Label: '12 exchanges · 41 nodes · 864 edges · Live market data']",
            "visual": "Use the actual FullGraph.png image from the paper at full resolution. Overlay a single coloured path through the graph. The four label terms appear as small annotations.",
            "content": [
                ("direction","Gesture toward the slide. Let the image carry the weight here."),
                ("spoken",  "This is our dataset. The actual network we built."),
                ("spoken",  "Every dot is a trading pair on one of twelve exchanges. Every line is a possible trade or cross-exchange transfer — and it carries the complete real-world cost of that action: the taker fee, the live slippage estimate from the order book, the gas cost, and the venue's reliability score."),
                ("spoken",  "To our knowledge, this is the first execution-aware graph dataset built specifically for stablecoin arbitrage research."),
                ("pause",   "[PAUSE]"),
                ("spoken",  "The question is: which path through this network, starting from any node, ends with more dollars than you started with — and can actually be executed?"),
            ],
        },
        {
            "header": "SLIDE 5 · A* Search · 3:40 – 4:30",
            "slide_cue": "[SLIDE: Side-by-side animation. LEFT: 'Dijkstra' — nodes light up in a broad expanding wave. RIGHT: 'A* with h₂' — a narrow directed beam. Node expansion counter under each. Right counter stops at ~70% of the left.]",
            "visual": "This is the single most important visual in the deck. The 29% reduction must be SEEN before it is said. Animate on click: both panels expand simultaneously.",
            "content": [
                ("spoken",  "Our core algorithm is A* search — the same search strategy that powers GPS navigation and game AI. The key insight: instead of exploring every possible path, A* uses an evaluation function, f of n equals g of n plus h of n, to decide which node to expand next."),
                ("spoken",  "g of n is the cost of the path so far. h of n is our heuristic — a domain-specific estimate of the execution risk ahead. Together they steer the search toward paths that are not just short, but feasible."),
                ("spoken",  "Think of it like Google Maps during rush hour. It does not just find the shortest route. It weights the toll, the traffic density, the road reliability. It steers you toward the path you can actually take — not just the one that looks best on a map."),
                ("spoken",  "That is exactly what we are doing. Except the map is a live financial network, and the traffic is real-time order-book data."),
            ],
        },
        {
            "header": "SLIDE 6 · Three Heuristics · 4:30 – 5:25",
            "slide_cue": "[SLIDE: Three vertical panels. h₁: Liquidity — 'Is there enough market depth?' | h₂ ★: Slippage — 'Does my order move the price?' | h₃: Chain + Venue — 'Will it settle in time?' Reveal one panel at a time on click.]",
            "visual": "Keep each panel clean: one icon, one line, the heuristic formula in small text below. Mark h₂ with a star — it is the novel contribution and the one that works.",
            "content": [
                ("spoken",  "We designed three guidance heuristics. Each one estimates a different dimension of execution risk, and each adds that estimate to the priority function — steering A* away from paths that look profitable but cannot be executed."),
                ("direction","Reveal each panel as you name it. One breath between each. Do not rush through them."),
                ("spoken",  "Heuristic one: Liquidity. Is there enough market depth in this venue to support our order size right now, without exhausting the book?\n\nHeuristic two: Slippage. This is our novel contribution. Using live order-book data, we compute the volume-weighted average price of filling our order — and penalize paths where that price diverges too far from the mid-price. It is dynamic. It updates with the market.\n\nHeuristic three: Chain congestion and exchange reliability. How long will the blockchain transfer take? And how operationally reliable is this particular venue?"),
                ("pause",   "[BEAT]"),
                ("spoken",  "One of these three will prove decisive."),
            ],
        },
        {
            "header": "SLIDE 7 · The Result · 5:25 – 6:20",
            "slide_cue": "[SLIDE: TOP: fig01_node_expansion_bar.png — bar chart (Dijkstra vs h₁ vs h₂ vs h₃), h₂ highlighted in SFU red, '−29%' annotation. BOTTOM: CameraReadySuccesfulPathProfit.png — actual found profitable path, labelled with the profit amount.]",
            "visual": "The bar chart is the evidence. The found path image is the proof of life — it makes the abstract concrete. The profit label should be large and readable from the back of the room.",
            "content": [
                ("direction","Slow down. Every sentence here gets its own breath. This is the payoff."),
                ("spoken",  "Here is what we found."),
                ("pause",   "[PAUSE]"),
                ("spoken",  "Our slippage-aware heuristic — h-two — achieved the same profit quality as the Dijkstra baseline. Within one percent."),
                ("pause",   "[PAUSE]"),
                ("spoken",  "But it did so using twenty-nine percent fewer node expansions."),
                ("pause",   "[BEAT]"),
                ("spoken",  "Same destination. Same profit. Twenty-nine percent less work."),
                ("pause",   "[PAUSE]"),
                ("spoken",  "And this —"),
                ("direction","Gesture to the bottom image on the slide."),
                ("spoken",  "— is a real path our system found. Kraken to KuCoin, USDT to TUSD. Nine dollars and ninety-one cents profit on a ten-thousand dollar order. Found in under ten milliseconds of search time."),
                ("spoken",  "We ran this across an eight-hour overnight campaign — seven thousand two hundred search instances, live market data, continuous operation. Every A* run in that campaign found a profitable path. When we re-evaluated those paths two minutes later, accounting for quotes that had gone stale — ninety-nine point six percent were still profitable."),
                ("spoken",  "That is not a simulation artifact. That is a system working under real market conditions."),
            ],
        },
        {
            "header": "SLIDE 8 · Why It Matters · 6:20 – 7:25",
            "slide_cue": "[SLIDE: Left half — price divergence chart showing the same stablecoin at two different prices across two exchanges during market stress. Right half — bullet points on geopolitical scenarios.]",
            "visual": "The price divergence chart makes the abstract tangible. Show an actual divergence event — not hypothetical. If you have one from your overnight data, use it.",
            "content": [
                ("direction","Energy rises here. This is the vision. Speak with conviction."),
                ("spoken",  "Now you might be thinking — this is a niche trading problem. Why does it belong at an AI conference?"),
                ("pause",   "[BEAT]"),
                ("spoken",  "Consider what happens to stablecoin markets during moments of geopolitical shock. A war breaks out. A government announces an exchange freeze. A major venue halts withdrawals overnight. These are the moments when price discrepancies across independent exchanges spike — not by fractions of a percent, but by meaningful margins, in real time."),
                ("spoken",  "A system that can navigate those disruptions — twenty-nine percent more efficiently than the baseline — is not just a trading tool. It is a lens for understanding how fragmented financial markets behave under stress. That is a research question with implications well beyond cryptocurrency."),
                ("spoken",  "And the framework we built here is a foundation. Decentralized exchanges — Uniswap, Curve — are the natural next frontier. Continuous pricing invariants, automated market makers, on-chain liquidity: a richer search space that demands exactly this kind of execution-aware pathfinding."),
                ("spoken",  "The market is expanding. The navigation tools need to scale with it."),
            ],
        },
        {
            "header": "SLIDE 9 · Close · 7:25 – 8:00",
            "slide_cue": "[SLIDE: FullGraph.png again — full bleed, same opening image — but now a single glowing path runs through it. Text overlay, centred, large: 'Less Exploration. More Execution. Same Profit.']",
            "visual": "This is the visual callback. The audience saw this graph at the start, before you spoke. Now it has meaning. The single glowing path is the answer to the question you opened with.",
            "content": [
                ("direction","Return to centre. Slow your pace to below your normal speaking speed. This is the callback."),
                ("spoken",  "We started with a question: how do you find the most profitable, actually executable path through a thirty-three trillion dollar market?"),
                ("spoken",  "The answer: model the ecosystem as a graph. Encode every real-world cost as an edge weight. Apply A* search, guided by a slippage-aware heuristic that steers search toward paths the market can actually support."),
                ("pause",   "[PAUSE]"),
                ("spoken",  "Less exploration. More execution. Same profit."),
                ("pause",   "[PAUSE — two full seconds. Make eye contact. Do not add anything.]"),
                ("spoken",  "Thank you."),
                ("direction","Hold the silence after 'Thank you.' Do not add '...any questions?' Let the room respond."),
            ],
        },
    ]

    for slide in slides:
        # Slide header
        p = doc.add_paragraph(slide["header"], style="SlideHeader")
        set_left_border(p, "CC0633", 24)

        # Slide cue (dark monospaced note)
        cue_p = doc.add_paragraph()
        cue_p.paragraph_format.left_indent = Inches(0.3)
        cue_p.paragraph_format.space_after = Pt(4)
        run = cue_p.add_run(slide["slide_cue"])
        run.font.name = "Courier New"
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
        set_para_shading(cue_p, "E8EAF6")

        # Visual note
        vis_p = doc.add_paragraph(style="Visual")
        set_left_border(vis_p, "FF9800", 12)
        set_para_shading(vis_p, "FFF8E1")
        run = vis_p.add_run("▶ Visual: ")
        run.font.bold = True
        run.font.color.rgb = RGBColor(0xE6, 0x51, 0x00)
        run2 = vis_p.add_run(slide["visual"])
        run2.font.color.rgb = RGBColor(0x6D, 0x40, 0x00)

        doc.add_paragraph()  # breathing space

        # Content lines
        for kind, text in slide["content"]:
            if kind == "spoken":
                for line in text.split("\n\n"):
                    line = line.strip()
                    if not line:
                        continue
                    p = doc.add_paragraph(style="Spoken")
                    run = p.add_run(f'"{line}"')
                    run.font.italic = True
                    run.font.color.rgb = DARK
            elif kind == "direction":
                p = doc.add_paragraph(style="Direction")
                run = p.add_run(f"[DIRECTION: {text}]")
                run.font.color.rgb = DIRN_GREY
            elif kind == "pause":
                p = doc.add_paragraph(style="Pause")
                run = p.add_run(text)
                run.font.color.rgb = RGBColor(0x22, 0x77, 0xCC)

        add_hr(doc)

    # ── Q&A section ──────────────────────────────────────────────────────────
    doc.add_page_break()
    h = doc.add_heading("Q&A Rebuttal Preparation", level=1)
    h.runs[0].font.color.rgb = RGBColor(0x1B, 0x5E, 0x20)

    p = doc.add_paragraph(
        "Lead with the one-line opener every time. Elaborate only if the questioner follows up. "
        "Aim for 30–45 seconds per answer.", style="Note")

    qa_blocks = [
        {
            "q": "Q1 — Why A* and not Bellman-Ford or negative cycle detection?",
            "opener": "Bellman-Ford solves a different problem. It finds closed cycles that look profitable on paper — it does not model whether you can execute them.",
            "answer": "Traditional arbitrage systems use negative cycle detection — they look for closed loops where the product of exchange rates exceeds one. But that framing has two problems for our setting. First, it ignores execution costs entirely: fees, slippage, transfer delays, and exchange reliability are not in that model. Second, it requires a closed loop — returning to your starting asset — which is unnecessary when all assets are dollar-pegged stablecoins. Our open-path formulation is fundamentally different: we are looking for any path that ends with more USD value than we started with, accounting for all real costs. A* with goal-directed early termination is the right tool for that problem. Bellman-Ford, one-hop, and two-hop enumeration all fail in our experiments.",
        },
        {
            "q": "Q2 — Is a 29% reduction in node expansions practically significant in live trading?",
            "opener": "The significance is not just speed — it is that the heuristic is steering search more intelligently, toward paths the market can actually support.",
            "answer": "A 29% reduction while matching profit within 1% tells us something important: h₂'s slippage estimate is genuinely informative. It is guiding A* toward the same high-quality routes as Dijkstra, but exploring fewer dead ends along the way. In a real deployment, this translates to lower computational cost at scale — thousands of searches per day — and faster termination in time-sensitive windows.",
        },
        {
            "q": "Q3 — Are your heuristics admissible? Do they guarantee optimal paths?",
            "opener": "No — they are guidance penalties, not admissible lower bounds. We trade optimality guarantees for execution-aware steering, and we are explicit about that in the paper.",
            "answer": "Admissibility would require our heuristics to never overestimate the true remaining cost. Because they are domain-specific calibrations tuned to execution risk — not worst-case bounds — they can overestimate, meaning A* may not return the globally optimal path. We accept that trade-off deliberately. In real-time arbitrage, finding a good executable path quickly is more valuable than proving it is optimal. The fact that h₂ matches Dijkstra's profit within 1% across 7,200 instances suggests the practical cost of inadmissibility is negligible in this domain.",
        },
        {
            "q": "Q4 — What are the main limitations of this work?",
            "opener": "Three honest ones: centralized exchanges only, planning not live execution, and heuristic weights require domain tuning.",
            "answer": "First, this is a CEX-only study — the extension to decentralized exchanges and AMMs is future work. Second, our system is a path planner: it finds routes in simulation but does not place live orders. Bridging the planning-execution gap is a significant open problem. Third, the lambda parameters in our heuristics were tuned empirically on our dataset; transferring them to a different exchange set or asset class would require retuning.",
        },
        {
            "q": "Q5 — How do you handle the problem of stale market quotes?",
            "opener": "We ran a dedicated experiment: 99.6% of found paths remain profitable after two minutes, which defines a practical execution window.",
            "answer": "After finding a profitable path, we re-evaluated it using fresh market data at delays of 5, 30, 60, 120, and 300 seconds. Up to 120 seconds, 99.6% of paths remained profitable. Beyond 120 seconds the success rate begins to degrade — which tells us something real about how long these discrepancies persist.",
        },
        {
            "q": "Q6 — Your paper shows 56.7% success on the cached graph. But you said every run found a profitable path?",
            "opener": "Those are two different experiments — good catch.",
            "answer": "The 56.7% figure is from the cached-graph study: we tested thirty fixed starting nodes, and 17 of them had a profitable path reachable from that specific starting point. The overnight campaign is different: we ran 7,200 searches with varied starting conditions across eight hours of live market data, and in each of those instances, A* found a profitable path. The success rate is 100% because we were not restricted to a fixed set of potentially unprofitable starting nodes.",
        },
        {
            "q": "Q7 — Could a system like this be used for market manipulation?",
            "opener": "Arbitrage is generally market-stabilizing — it pushes prices toward equilibrium across venues, not away from it.",
            "answer": "Our system finds naturally occurring price discrepancies between independent exchanges. It does not place orders that move prices in a coordinated way, and the capital scale we test — $1,000 to $100,000 — is orders of magnitude below what would be required to meaningfully influence a market with $300 billion in capitalization. The research is intended as a planning and analysis framework, not a deployment-ready trading system.",
        },
    ]

    for block in qa_blocks:
        p = doc.add_paragraph(block["q"], style="QAHeader")
        set_left_border(p, "1B5E20", 18)

        p2 = doc.add_paragraph(style="Oneliner")
        set_para_shading(p2, "E8F5E9")
        r = p2.add_run("One-liner: ")
        r.font.bold = True
        r.font.color.rgb = RGBColor(0x1B, 0x5E, 0x20)
        r2 = p2.add_run(f'"{block["opener"]}"')
        r2.font.italic = True
        r2.font.color.rgb = DARK

        p3 = doc.add_paragraph(block["answer"], style="FullAnswer")

    add_hr(doc)

    # ── Timing table ─────────────────────────────────────────────────────────
    doc.add_page_break()
    doc.add_heading("Timing Reference", level=2)
    add_table_from_rows(
        doc,
        ["Section", "Slide", "Target End", "Running Total"],
        [
            ["Hook",          "Title",                 "0:55",  "0:55"],
            ["The Market",    "$33T Bar Chart",         "1:45",  "1:45"],
            ["The Problem",   "Split Warning Icons",    "2:55",  "2:55"],
            ["The Graph",     "FullGraph",              "3:40",  "3:40"],
            ["A* Method",     "Side-by-Side Animation", "4:30",  "4:30"],
            ["Heuristics",    "Three Panels",           "5:25",  "5:25"],
            ["Result",        "Bar Chart + Path",       "6:20",  "6:20"],
            ["Impact",        "World Map + Divergence", "7:25",  "7:25"],
            ["Close",         "FullGraph + Glowing Path","8:00", "8:00"],
        ],
        col_widths=[2.0, 2.5, 1.2, 1.2],
    )

    p = doc.add_paragraph(
        "Practice tip: Record yourself once with a timer. Target 7:45–8:10. "
        "The [PAUSE] and [DIRECTION] markers consume approximately 50 seconds — "
        "do not skip them, they are not dead time.", style="Note")

    # ── Save ─────────────────────────────────────────────────────────────────
    doc.save(str(OUT))
    print(f"wrote {OUT}  ({OUT.stat().st_size / 1e3:.1f} KB)")


if __name__ == "__main__":
    build()
