"""
fill_slides.py — generate a 9-slide 16:9 PPTX presentation for GSS 2026
Run:  python3 docs/latex/StablecoinArbitrage_GSS2026/presentation/fill_slides.py
Output: docs/latex/.../presentation/slides_filled.pptx
"""

import io, shutil, zipfile, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from PIL import Image

# ── venv path so python-pptx is found ────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "venv312/lib/python3.14/site-packages"))

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from lxml import etree

# ── constants ─────────────────────────────────────────────────────────────────
SW = Inches(13.333)          # slide width  (16:9 widescreen)
SH = Inches(7.5)             # slide height

SFU_RED = RGBColor(0xCC, 0x06, 0x33)
DARK    = RGBColor(0x1A, 0x1A, 0x2E)
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
LGREY   = RGBColor(0xF2, 0xF2, 0xF7)
MGREY   = RGBColor(0x88, 0x88, 0x88)

HDR_H   = Inches(0.55)       # header bar height
HDR_Y   = Inches(0)
FTR_H   = Inches(0.28)
FTR_Y   = SH - FTR_H
CONTENT_Y = HDR_H + Inches(0.15)
CONTENT_H = SH - HDR_H - FTR_H - Inches(0.15)
MARGIN    = Inches(0.35)

# ── paths ─────────────────────────────────────────────────────────────────────
FIGS     = ROOT / "docs/latex/StablecoinArbitrage_CAIAC2026/figures"
TEMPLATE = ROOT / "docs/latex/StablecoinArbitrage_GSS2026/presentation/CdnAI2026_poster_landscape_36x24.pptx"
OUTPUT   = ROOT / "docs/latex/StablecoinArbitrage_GSS2026/presentation/slides_filled.pptx"
TMP      = Path("/tmp/gss_slides_tmp")

AUTHOR   = "Kevin Litvin · Simon Fraser University"
CONF     = "Canadian AI 2026 · GSS"

# ── extract logos from poster template ───────────────────────────────────────
TMP.mkdir(parents=True, exist_ok=True)
_tzip = zipfile.ZipFile(TEMPLATE)
LOGO_PNG = TMP / "logo_cdnai.png"
LOGO_PNG.write_bytes(_tzip.read("ppt/media/image2.png"))   # 967×170 CdnAI banner
_tzip.close()
print(f"  extracted CdnAI logo ({LOGO_PNG.stat().st_size} bytes)")

# ── asset generation helpers ──────────────────────────────────────────────────

def _save_fig(fig, name: str) -> Path:
    p = TMP / name
    fig.savefig(p, dpi=180, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    print(f"  generated {name}")
    return p


def gen_market_chart() -> Path:
    """Animated bar chart: Mastercard / Visa / Stablecoins."""
    fig, ax = plt.subplots(figsize=(10, 5.2))
    labels  = ["Mastercard\n2023", "Visa\n2023", "Stablecoins\n2024"]
    values  = [9, 15, 33]
    colors  = ["#AAAAAA", "#888888", "#CC0633"]
    bars = ax.bar(labels, values, color=colors, width=0.5,
                  edgecolor="white", linewidth=1.5)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.4,
                f"${val}T", ha="center", va="bottom",
                fontsize=22, fontweight="bold",
                color="#CC0633" if val == 33 else "#555555")
    ax.set_ylabel("Annual Transaction Volume (USD Trillion)", fontsize=13)
    ax.set_ylim(0, 40)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="x", labelsize=15)
    ax.tick_params(axis="y", labelsize=12)
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")
    ax.axhline(y=33, color="#CC0633", linestyle="--", alpha=0.4, linewidth=1)
    ax.text(2.4, 33.5, "More than Visa +\nMastercard combined",
            color="#CC0633", fontsize=11, va="bottom", ha="right", style="italic")
    return _save_fig(fig, "slide2_market.png")


def gen_astar_comparison() -> Path:
    """Side-by-side Dijkstra vs A* node expansion comparison."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5.2))
    np.random.seed(42)

    def draw_graph(ax, n_explored, title, color, n_total=35):
        # Draw all nodes as small grey dots
        pos = {}
        rows, cols = 7, 5
        for i in range(rows):
            for j in range(cols):
                nid = i * cols + j
                pos[nid] = (j * 2, -i * 1.6)
                c = color if nid < n_explored else "#DDDDDD"
                alpha = 0.85 if nid < n_explored else 0.3
                ax.scatter(*pos[nid], s=320, c=c, zorder=5,
                           alpha=alpha, edgecolors="white", linewidths=1.2)

        # Draw a "path" through some explored nodes
        path_nodes = [0, 1, 6, 7, 12, 13, 18]
        for i in range(len(path_nodes) - 1):
            x0, y0 = pos[path_nodes[i]]
            x1, y1 = pos[path_nodes[i+1]]
            ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                        arrowprops=dict(arrowstyle="->", color="#CC0633",
                                        lw=2.5, connectionstyle="arc3,rad=0.1"))

        ax.set_xlim(-1, 9)
        ax.set_ylim(-12, 1.5)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(title, fontsize=17, fontweight="bold", pad=12,
                     color="#1A1A2E")
        # Expansion counter
        ax.text(4, -11.5, f"Nodes expanded: {n_explored}",
                ha="center", fontsize=15,
                color=color if color != "#888888" else "#555555",
                fontweight="bold")

    draw_graph(ax1, 30, "Dijkstra (baseline)", "#888888")
    draw_graph(ax2, 21, "A★ with h₂ (slippage)", "#CC0633")

    # Big delta annotation
    fig.text(0.5, 0.04, "−29% fewer node expansions · same profit",
             ha="center", fontsize=16, fontweight="bold", color="#CC0633")

    fig.patch.set_facecolor("white")
    return _save_fig(fig, "slide5_astar.png")


def gen_heuristics_card() -> Path:
    """Three-panel heuristics card visual."""
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.5))
    cards = [
        ("h₁", "Liquidity", "Is there enough\nmarket depth?",
         "#2196F3", "📊"),
        ("h₂ ★", "Slippage", "Will my order\nmove the price?",
         "#CC0633", "📉"),
        ("h₃", "Chain + Venue", "Will it settle\nin time?",
         "#4CAF50", "⛓"),
    ]
    for ax, (label, name, desc, col, icon) in zip(axes, cards):
        ax.set_facecolor("#F8F8F8")
        rect = patches.FancyBboxPatch((0.05, 0.05), 0.9, 0.9,
                                      boxstyle="round,pad=0.03",
                                      facecolor="#F8F8F8",
                                      edgecolor=col, linewidth=3,
                                      transform=ax.transAxes, zorder=1)
        ax.add_patch(rect)
        ax.text(0.5, 0.82, label, transform=ax.transAxes,
                ha="center", fontsize=28, fontweight="bold", color=col)
        ax.text(0.5, 0.62, name, transform=ax.transAxes,
                ha="center", fontsize=16, fontweight="bold", color="#1A1A2E")
        ax.text(0.5, 0.35, desc, transform=ax.transAxes,
                ha="center", fontsize=13, color="#444444",
                multialignment="center")
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.axis("off")
    fig.patch.set_facecolor("white")
    plt.tight_layout(pad=1.2)
    return _save_fig(fig, "slide6_heuristics.png")


def gen_impact_chart() -> Path:
    """Price divergence illustration across two exchanges."""
    fig, ax = plt.subplots(figsize=(9, 4.2))
    t = np.linspace(0, 100, 400)
    base = 1.0 + 0.0003 * np.sin(t * 0.3) + 0.0001 * np.random.randn(400)
    shock_idx = 220
    spread = np.zeros(400)
    spread[shock_idx:] = (np.linspace(0, 0.008, 180))
    np.random.seed(7)
    noise = 0.0004 * np.random.randn(400)

    price_a = base + noise
    price_b = base - spread + noise[::-1] * 0.5

    ax.plot(t, price_a * 1000, color="#1A1A2E", linewidth=2.0,
            label="Exchange A (e.g. Kraken)")
    ax.plot(t, price_b * 1000, color="#CC0633", linewidth=2.0,
            label="Exchange B (e.g. KuCoin)")
    ax.axvline(x=t[shock_idx], color="#FF9800", linewidth=2,
               linestyle="--", alpha=0.8)
    ax.text(t[shock_idx] + 1, 1001, "Market shock\n(exchange freeze)",
            fontsize=11, color="#FF9800", va="top")

    ax.fill_between(t[shock_idx:], price_a[shock_idx:] * 1000,
                    price_b[shock_idx:] * 1000, alpha=0.15, color="#CC0633")
    ax.text(80, 999.6, "Arbitrage\nwindow", fontsize=11,
            color="#CC0633", ha="center", style="italic")

    ax.set_xlabel("Time (arbitrary units)", fontsize=12)
    ax.set_ylabel("USDT price (× $1000 = $1.000)", fontsize=12)
    ax.legend(fontsize=11, framealpha=0.9)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_ylim(999.0, 1002.0)
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")
    return _save_fig(fig, "slide8_impact.png")


# ── python-pptx helpers ───────────────────────────────────────────────────────

def new_prs() -> Presentation:
    prs = Presentation()
    prs.slide_width  = SW
    prs.slide_height = SH
    return prs


def blank_slide(prs: Presentation):
    blank_layout = prs.slide_layouts[6]   # index 6 = blank
    return prs.slides.add_slide(blank_layout)


def add_rect(slide, x, y, w, h, fill_rgb: RGBColor, alpha=None):
    from pptx.enum.shapes import MSO_SHAPE_TYPE
    shape = slide.shapes.add_shape(1, x, y, w, h)   # 1 = MSO_SHAPE.RECTANGLE
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_rgb
    shape.line.fill.background()
    return shape


def add_text(slide, text: str, x, y, w, h,
             font_size=24, bold=False, color: RGBColor = DARK,
             align=PP_ALIGN.LEFT, italic=False, wrap=True):
    txBox = slide.shapes.add_textbox(x, y, w, h)
    tf = txBox.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    run.font.name = "Arial"
    return txBox


def add_picture(slide, img_path: Path,
                x, y, width=None, height=None) -> None:
    if width and height:
        slide.shapes.add_picture(str(img_path), x, y, width, height)
    elif width:
        slide.shapes.add_picture(str(img_path), x, y, width=width)
    elif height:
        slide.shapes.add_picture(str(img_path), x, y, height=height)
    else:
        slide.shapes.add_picture(str(img_path), x, y)


def add_header(slide, title: str, subtitle: str = ""):
    """Red header bar with white title."""
    add_rect(slide, 0, 0, SW, HDR_H, SFU_RED)
    add_text(slide, title,
             MARGIN, Inches(0.05), SW - MARGIN * 2 - Inches(2.0), HDR_H - Inches(0.1),
             font_size=26, bold=True, color=WHITE, align=PP_ALIGN.LEFT)
    if subtitle:
        add_text(slide, subtitle,
                 SW - Inches(2.2), Inches(0.09), Inches(2.0), HDR_H - Inches(0.15),
                 font_size=12, bold=False, color=RGBColor(0xFF, 0xCC, 0xCC),
                 align=PP_ALIGN.RIGHT)


def add_footer(slide, slide_num: int, total: int = 9):
    """Light footer bar."""
    add_rect(slide, 0, FTR_Y, SW, FTR_H, RGBColor(0xEE, 0xEE, 0xEE))
    add_text(slide, AUTHOR,
             MARGIN, FTR_Y + Inches(0.04), Inches(5), FTR_H,
             font_size=10, color=MGREY, align=PP_ALIGN.LEFT)
    add_text(slide, CONF,
             Inches(4.5), FTR_Y + Inches(0.04), Inches(5), FTR_H,
             font_size=10, color=MGREY, align=PP_ALIGN.CENTER)
    add_text(slide, f"{slide_num} / {total}",
             SW - Inches(1.2), FTR_Y + Inches(0.04), Inches(1.0), FTR_H,
             font_size=10, color=MGREY, align=PP_ALIGN.RIGHT)


def add_logo(slide):
    """Canadian AI logo top-right corner."""
    logo_h = Inches(0.38)
    logo_w = Inches(2.15)   # maintain 967:170 ≈ 5.7 ratio
    add_picture(slide, LOGO_PNG,
                SW - logo_w - Inches(0.15), Inches(0.09), width=logo_w)


def add_bullet_box(slide, lines: list[str],
                   x, y, w, h,
                   font_size=20, color: RGBColor = DARK):
    txBox = slide.shapes.add_textbox(x, y, w, h)
    tf = txBox.text_frame
    tf.word_wrap = True
    first = True
    for line in lines:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = PP_ALIGN.LEFT
        p.space_before = Pt(6)
        run = p.add_run()
        run.text = "  •  " + line
        run.font.size = Pt(font_size)
        run.font.color.rgb = color
        run.font.name = "Arial"


def add_divider(slide, y, color: RGBColor = SFU_RED):
    add_rect(slide, MARGIN, y, SW - MARGIN * 2, Inches(0.025), color)


# ── SLIDE BUILDERS ────────────────────────────────────────────────────────────

def slide_01_title(prs):
    """Title slide — FullGraph background, title, author, logos."""
    s = blank_slide(prs)

    # Dark overlay + graph background
    fullgraph = FIGS / "FullGraph.png"
    if fullgraph.exists():
        add_picture(s, fullgraph, 0, 0, width=SW, height=SH)
    # Semi-transparent dark overlay
    add_rect(s, 0, 0, SW, SH, RGBColor(0x1A, 0x1A, 0x2E))
    # Need to lower opacity — do it via XML
    overlay = s.shapes[-1]
    sp = overlay.element
    spPr = sp.find(qn("p:spPr"))
    solidFill = spPr.find(".//" + qn("a:solidFill"))
    srgbClr = solidFill.find(qn("a:srgbClr"))
    alpha_elem = etree.SubElement(srgbClr, qn("a:alpha"))
    alpha_elem.set("val", "72000")   # ~72% opacity

    # SFU red accent bar (left side)
    add_rect(s, 0, 0, Inches(0.25), SH, SFU_RED)

    # Title
    title_y = Inches(1.8)
    add_text(s,
             "Execution-Aware A* Search for\nCross-Exchange Stablecoin Arbitrage",
             Inches(0.65), title_y, Inches(12.0), Inches(2.2),
             font_size=42, bold=True, color=WHITE, align=PP_ALIGN.LEFT)

    # Subtitle / research question
    add_text(s,
             "Can domain-specific heuristics reduce search cost while maintaining profit quality?",
             Inches(0.65), Inches(4.1), Inches(11.0), Inches(0.7),
             font_size=18, bold=False, color=RGBColor(0xFF, 0xCC, 0xCC),
             align=PP_ALIGN.LEFT, italic=True)

    # Divider
    add_rect(s, Inches(0.65), Inches(4.85), Inches(6.0), Inches(0.04), SFU_RED)

    # Author / conference
    add_text(s, AUTHOR,
             Inches(0.65), Inches(5.05), Inches(9.0), Inches(0.5),
             font_size=18, bold=False, color=WHITE, align=PP_ALIGN.LEFT)
    add_text(s, CONF,
             Inches(0.65), Inches(5.55), Inches(9.0), Inches(0.5),
             font_size=15, bold=False, color=RGBColor(0xFF, 0xCC, 0xCC),
             align=PP_ALIGN.LEFT)

    # Logo
    add_logo(s)
    add_footer(s, 1)
    print("  slide 1: Title")


def slide_02_market(prs, chart_path: Path):
    """$33T bar chart slide."""
    s = blank_slide(prs)
    add_header(s, "The $33 Trillion Market", "Slide 2")
    add_logo(s)

    # Left: chart
    add_picture(s, chart_path,
                MARGIN, CONTENT_Y + Inches(0.1),
                width=Inches(7.2))

    # Right: key stats
    rx = Inches(7.9)
    ry = CONTENT_Y + Inches(0.4)
    rw = SW - rx - MARGIN
    add_text(s, "$300B+", rx, ry, rw, Inches(0.85),
             font_size=48, bold=True, color=SFU_RED, align=PP_ALIGN.CENTER)
    add_text(s, "market cap in circulation", rx, ry + Inches(0.85), rw, Inches(0.45),
             font_size=14, color=MGREY, align=PP_ALIGN.CENTER, italic=True)

    add_divider(s, ry + Inches(1.5))

    add_text(s, "$33T", rx, ry + Inches(1.7), rw, Inches(0.85),
             font_size=48, bold=True, color=SFU_RED, align=PP_ALIGN.CENTER)
    add_text(s, "annual transaction volume", rx, ry + Inches(2.55), rw, Inches(0.45),
             font_size=14, color=MGREY, align=PP_ALIGN.CENTER, italic=True)

    add_divider(s, ry + Inches(3.1))

    add_text(s,
             '"They are the liquidity highways of the entire crypto ecosystem."',
             rx, ry + Inches(3.3), rw, Inches(1.2),
             font_size=14, color=DARK, align=PP_ALIGN.CENTER, italic=True)

    add_footer(s, 2)
    print("  slide 2: Market")


def slide_03_problem(prs):
    """The problem — 4 execution challenges."""
    s = blank_slide(prs)
    add_header(s, "The Problem: Execution Feasibility", "Slide 3")
    add_logo(s)

    # Setup story text
    story = (
        '"Imagine you are a quant trader. It is 2 AM. You see USDT trading '
        "cheaper on Kraken than on KuCoin. The math works. Existing systems "
        'say: take it."'
    )
    add_text(s, story, MARGIN, CONTENT_Y + Inches(0.05),
             SW - MARGIN * 2, Inches(0.85),
             font_size=16, italic=True, color=DARK, align=PP_ALIGN.LEFT)

    # "But here is the catch" divider
    add_rect(s, MARGIN, CONTENT_Y + Inches(1.0),
             SW - MARGIN * 2, Inches(0.03), SFU_RED)
    add_text(s, "But existing systems don't tell you about the four execution barriers:",
             MARGIN, CONTENT_Y + Inches(1.1), SW - MARGIN * 2, Inches(0.45),
             font_size=16, bold=True, color=DARK)

    # Four challenge cards
    challenges = [
        ("1. Liquidity",   "Your order size may\nexhaust the book",         "#2196F3"),
        ("2. Slippage ★",  "Large orders move the\nprice mid-execution",    "#CC0633"),
        ("3. Latency",     "Blockchain settlement\nmay miss the window",    "#FF9800"),
        ("4. Reliability", "Exchanges may suspend\nwithdrawals overnight",   "#4CAF50"),
    ]
    card_w = (SW - MARGIN * 2 - Inches(0.2) * 3) / 4
    card_h = Inches(2.1)
    card_y = CONTENT_Y + Inches(1.65)
    for i, (title, body, col) in enumerate(challenges):
        cx = MARGIN + i * (card_w + Inches(0.2))
        rgb = RGBColor.from_string(col.lstrip("#"))
        # Card background
        card_bg = slide_03_card(s, cx, card_y, card_w, card_h, rgb, title, body)

    # Bottom punch line
    add_text(s,
             "Bellman-Ford, 1-hop, and 2-hop baselines fail entirely. "
             "We need execution-aware pathfinding.",
             MARGIN, card_y + card_h + Inches(0.25),
             SW - MARGIN * 2, Inches(0.55),
             font_size=16, bold=True, color=SFU_RED, align=PP_ALIGN.CENTER)

    add_footer(s, 3)
    print("  slide 3: Problem")


def slide_03_card(slide, x, y, w, h, rgb, title, body):
    add_rect(slide, x, y, w, h, rgb)
    # title
    add_text(slide, title, x + Inches(0.12), y + Inches(0.12),
             w - Inches(0.24), Inches(0.55),
             font_size=17, bold=True, color=WHITE, align=PP_ALIGN.LEFT)
    add_text(slide, body, x + Inches(0.12), y + Inches(0.7),
             w - Inches(0.24), h - Inches(0.75),
             font_size=14, color=WHITE, align=PP_ALIGN.LEFT)


def slide_04_graph(prs):
    """Full-bleed graph slide."""
    s = blank_slide(prs)
    add_header(s, "The Dataset: A Novel Execution-Aware Graph", "Slide 4")
    add_logo(s)

    fullgraph = FIGS / "FullGraph.png"
    if fullgraph.exists():
        # Left: graph image
        img_w = Inches(7.0)
        add_picture(s, fullgraph, MARGIN, CONTENT_Y + Inches(0.1),
                    width=img_w)

    # Right: stats
    rx = MARGIN + Inches(7.3)
    ry = CONTENT_Y + Inches(0.3)
    rw = SW - rx - MARGIN

    stats = [
        ("12", "centralized exchanges"),
        ("9",  "stablecoin symbols\n(USDT, USDC, DAI…)"),
        ("41", "nodes (exchange, coin pairs)"),
        ("864","edges with live cost data"),
    ]
    for val, label in stats:
        add_text(s, val, rx, ry, rw, Inches(0.65),
                 font_size=40, bold=True, color=SFU_RED, align=PP_ALIGN.LEFT)
        add_text(s, label, rx + Inches(1.2), ry + Inches(0.08),
                 rw - Inches(1.2), Inches(0.6),
                 font_size=14, color=DARK, align=PP_ALIGN.LEFT)
        ry += Inches(1.05)

    add_divider(s, ry + Inches(0.1))
    add_text(s,
             "★ First execution-aware graph dataset built\n   for stablecoin arbitrage research.",
             rx, ry + Inches(0.25), rw, Inches(0.9),
             font_size=14, bold=True, color=SFU_RED, align=PP_ALIGN.LEFT)

    add_footer(s, 4)
    print("  slide 4: Graph")


def slide_05_astar(prs, astar_path: Path):
    """A* method + side-by-side comparison."""
    s = blank_slide(prs)
    add_header(s, "Method: A* — Google Maps for Money", "Slide 5")
    add_logo(s)

    # Top: one-line method description
    add_text(s,
             "f(n) = g(n) + h(n)   ·   g(n): cost so far   ·   h(n): execution risk estimate",
             MARGIN, CONTENT_Y + Inches(0.05),
             SW - MARGIN * 2, Inches(0.5),
             font_size=17, bold=True, color=DARK, align=PP_ALIGN.CENTER)

    add_divider(s, CONTENT_Y + Inches(0.62))

    # Comparison image
    add_picture(s, astar_path,
                MARGIN, CONTENT_Y + Inches(0.78),
                width=SW - MARGIN * 2)

    add_footer(s, 5)
    print("  slide 5: A*")


def slide_06_heuristics(prs, heuristics_path: Path):
    """Three heuristic cards."""
    s = blank_slide(prs)
    add_header(s, "Three Novel Guidance Heuristics", "Slide 6")
    add_logo(s)

    add_text(s,
             "Each heuristic adds a domain-specific penalty to h(n), steering A* toward "
             "paths that are not just profitable — but executable under live market conditions.",
             MARGIN, CONTENT_Y + Inches(0.05),
             SW - MARGIN * 2, Inches(0.6),
             font_size=16, italic=True, color=DARK, align=PP_ALIGN.CENTER)

    add_picture(s, heuristics_path,
                MARGIN, CONTENT_Y + Inches(0.75),
                width=SW - MARGIN * 2)

    add_text(s,
             "One of these three will prove decisive.",
             MARGIN, CONTENT_Y + Inches(5.0),
             SW - MARGIN * 2, Inches(0.5),
             font_size=17, bold=True, color=SFU_RED, align=PP_ALIGN.CENTER,
             italic=True)

    add_footer(s, 6)
    print("  slide 6: Heuristics")


def slide_07_result(prs):
    """Key result — 29% bar chart + profitable path image."""
    s = blank_slide(prs)
    add_header(s, "Key Result: 29% Fewer Node Expansions", "Slide 7")
    add_logo(s)

    bar = FIGS / "fig01_node_expansion_bar.png"
    path_img = FIGS / "CameraReadySuccesfulPathProfit.png"

    # Left: bar chart
    if bar.exists():
        add_picture(s, bar,
                    MARGIN, CONTENT_Y + Inches(0.1),
                    width=Inches(7.2))

    # Right: found path + stats
    rx = Inches(7.9)
    ry = CONTENT_Y + Inches(0.1)
    rw = SW - rx - MARGIN

    add_text(s, "Same profit. 29% less work.",
             rx, ry, rw, Inches(0.65),
             font_size=20, bold=True, color=SFU_RED, align=PP_ALIGN.CENTER)

    if path_img.exists():
        add_picture(s, path_img,
                    rx, ry + Inches(0.75), width=rw)

    # Stats box
    stats_y = ry + Inches(2.8)
    bullets = [
        "h₂ matches Dijkstra profit within 1%",
        "7,200 overnight searches · 100% found a path",
        "99.6% still profitable after 120 s",
    ]
    add_bullet_box(s, bullets, rx, stats_y, rw, Inches(2.0),
                   font_size=13, color=DARK)

    add_footer(s, 7)
    print("  slide 7: Result")


def slide_08_impact(prs, impact_path: Path):
    """Why it matters — geopolitical angle."""
    s = blank_slide(prs)
    add_header(s, "Why It Matters: Markets Under Stress", "Slide 8")
    add_logo(s)

    # Left: impact chart
    add_picture(s, impact_path,
                MARGIN, CONTENT_Y + Inches(0.15),
                width=Inches(7.2))

    # Right: bullet points
    rx = Inches(7.9)
    ry = CONTENT_Y + Inches(0.3)
    rw = SW - rx - MARGIN

    add_text(s, "Price discrepancies spike during:",
             rx, ry, rw, Inches(0.45),
             font_size=16, bold=True, color=DARK)

    scenarios = [
        "Exchange freezes & withdrawal halts",
        "Geopolitical shocks & government bans",
        "Regulatory announcements",
        "Sudden liquidity crises",
    ]
    add_bullet_box(s, scenarios, rx, ry + Inches(0.5), rw, Inches(1.8),
                   font_size=14, color=DARK)

    add_divider(s, ry + Inches(2.45))

    add_text(s,
             "A 29% more efficient router is not just a\n"
             "trading tool — it is a lens for understanding\n"
             "how fragmented markets behave under stress.",
             rx, ry + Inches(2.65), rw, Inches(1.5),
             font_size=15, color=DARK, align=PP_ALIGN.LEFT, italic=True)

    add_divider(s, ry + Inches(4.2))
    add_text(s, "Next: DEX / AMM markets (Uniswap, Curve)",
             rx, ry + Inches(4.4), rw, Inches(0.5),
             font_size=14, bold=True, color=SFU_RED)

    add_footer(s, 8)
    print("  slide 8: Impact")


def slide_09_close(prs):
    """Closing slide — FullGraph callback."""
    s = blank_slide(prs)

    fullgraph = FIGS / "FullGraph.png"
    if fullgraph.exists():
        add_picture(s, fullgraph, 0, 0, width=SW, height=SH)

    # Dark overlay
    add_rect(s, 0, 0, SW, SH, RGBColor(0x1A, 0x1A, 0x2E))
    overlay = s.shapes[-1]
    sp = overlay.element
    spPr = sp.find(qn("p:spPr"))
    solidFill = spPr.find(".//" + qn("a:solidFill"))
    srgbClr = solidFill.find(qn("a:srgbClr"))
    alpha_elem = etree.SubElement(srgbClr, qn("a:alpha"))
    alpha_elem.set("val", "72000")

    add_rect(s, 0, 0, Inches(0.25), SH, SFU_RED)

    # Three-word close
    add_text(s, "Less Exploration.", Inches(0.65), Inches(1.8),
             Inches(12), Inches(1.2),
             font_size=56, bold=True, color=WHITE, align=PP_ALIGN.LEFT)
    add_text(s, "More Execution.", Inches(0.65), Inches(2.95),
             Inches(12), Inches(1.2),
             font_size=56, bold=True, color=SFU_RED, align=PP_ALIGN.LEFT)
    add_text(s, "Same Profit.", Inches(0.65), Inches(4.1),
             Inches(12), Inches(1.2),
             font_size=56, bold=True, color=WHITE, align=PP_ALIGN.LEFT)

    add_text(s, "Thank you.  |  Questions?",
             Inches(0.65), Inches(5.5), Inches(10), Inches(0.6),
             font_size=22, color=RGBColor(0xFF, 0xCC, 0xCC),
             align=PP_ALIGN.LEFT, italic=True)

    add_text(s, "github.com/kevinl03/Stablecoin-CrossExchange-Arbitrage",
             Inches(0.65), Inches(6.2), Inches(10), Inches(0.5),
             font_size=14, color=RGBColor(0xAA, 0xAA, 0xAA),
             align=PP_ALIGN.LEFT)

    add_logo(s)
    add_footer(s, 9)
    print("  slide 9: Close")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def build():
    print("step 1/3 — generating supporting visuals …")
    chart_path     = gen_market_chart()
    astar_path     = gen_astar_comparison()
    heuristics_path= gen_heuristics_card()
    impact_path    = gen_impact_chart()

    print("step 2/3 — building slides …")
    prs = new_prs()
    slide_01_title(prs)
    slide_02_market(prs, chart_path)
    slide_03_problem(prs)
    slide_04_graph(prs)
    slide_05_astar(prs, astar_path)
    slide_06_heuristics(prs, heuristics_path)
    slide_07_result(prs)
    slide_08_impact(prs, impact_path)
    slide_09_close(prs)

    print("step 3/3 — saving …")
    prs.save(str(OUTPUT))
    size_mb = OUTPUT.stat().st_size / 1e6
    print(f"\nwrote {OUTPUT}  ({size_mb:.2f} MB)")


if __name__ == "__main__":
    build()
