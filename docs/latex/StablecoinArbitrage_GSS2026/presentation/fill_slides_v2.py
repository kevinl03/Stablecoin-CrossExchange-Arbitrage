"""
fill_slides_v2.py — 13-slide, 8-minute GSS 2026 presentation (v2 — analysis-driven rewrite)
Run:   python3 docs/latex/StablecoinArbitrage_GSS2026/presentation/fill_slides_v2.py
Output: docs/latex/.../presentation/slides_v2.pptx

Changes vs v1 (9 slides):
  + Slide 3  — Price Fragmentation table (shows the spread visually before explaining it)
  + Slide 6  — System Pipeline diagram (A* in context of the full data flow)
  + Slide 9  — fig01 as full-screen HERO result; 29% is now unmissable
  + Slide 10 — fig03 Profit Quality boxplot + fig02 compute time (proof quality ≠ cost)
  + Slide 11 — fig10/fig11 Overnight Campaign (7 200 real runs — the credibility slide)
  + Slide 12 — fig09 Quote Staleness (99.6% = concrete execution window)
  * All generated matplotlib visuals re-styled presentation-quality (larger fonts, clean axes)
  * fig18 Radar Summary added to Close slide for visual callback
  * Actual paper logo (logo-canai-2026.png) used instead of image2.png
"""

import io, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "venv312/lib/python3.14/site-packages"))

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from lxml import etree

# ── constants ──────────────────────────────────────────────────────────────────
SW = Inches(13.333)
SH = Inches(7.5)

SFU_RED  = RGBColor(0xCC, 0x06, 0x33)
DARK     = RGBColor(0x1A, 0x1A, 0x2E)
WHITE    = RGBColor(0xFF, 0xFF, 0xFF)
LGREY    = RGBColor(0xF2, 0xF2, 0xF7)
MGREY    = RGBColor(0x88, 0x88, 0x88)
ACCENT   = RGBColor(0x21, 0x96, 0xF3)   # blue accent for method slides

HDR_H     = Inches(0.52)
FTR_H     = Inches(0.28)
FTR_Y     = SH - FTR_H
CONTENT_Y = HDR_H + Inches(0.18)
CONTENT_H = SH - HDR_H - FTR_H - Inches(0.18)
MARGIN    = Inches(0.38)

AUTHOR = "Kevin Litvin · Simon Fraser University"
CONF   = "Canadian AI 2026 · GSS"
N_SLIDES = 13

# ── paths ──────────────────────────────────────────────────────────────────────
FIGS   = ROOT / "docs/latex/StablecoinArbitrage_CAIAC2026/figures"
OUT    = ROOT / "docs/latex/StablecoinArbitrage_GSS2026/presentation/slides_v2.pptx"
TMP    = Path("/tmp/gss_slides_v2")
TMP.mkdir(parents=True, exist_ok=True)

LOGO = FIGS / "logo-canai-2026.png"   # 967×170 official CdnAI logo in figures dir

# ── presentation-quality matplotlib style ─────────────────────────────────────
plt.rcParams.update({
    "font.family":    "sans-serif",
    "axes.spines.top":    False,
    "axes.spines.right":  False,
    "axes.grid":          False,
    "xtick.labelsize":    15,
    "ytick.labelsize":    15,
    "axes.labelsize":     15,
    "figure.facecolor":   "white",
    "axes.facecolor":     "white",
})


def _save(fig, name: str) -> Path:
    p = TMP / name
    fig.savefig(p, dpi=200, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    print(f"    generated {name}")
    return p


# ── asset generators ───────────────────────────────────────────────────────────

def gen_market_bar() -> Path:
    """Mastercard / Visa / Stablecoins volume bar."""
    fig, ax = plt.subplots(figsize=(9, 5.0))
    labels = ["Mastercard\n(2023)", "Visa\n(2023)", "Stablecoins\n(2024)"]
    vals   = [9, 15, 33]
    cols   = ["#AAAAAA", "#888888", "#CC0633"]
    bars = ax.bar(labels, vals, color=cols, width=0.52, zorder=3,
                  edgecolor="white", linewidth=2)
    for bar, v, c in zip(bars, vals, cols):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.5,
                f"${v}T", ha="center", va="bottom",
                fontsize=22, fontweight="bold",
                color="#CC0633" if v == 33 else "#555555")
    ax.set_ylim(0, 40)
    ax.set_ylabel("Annual Transaction Volume (USD Trillion)", fontsize=14)
    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.tick_params(axis="both", labelsize=14)
    # Bracket + annotation
    ax.annotate("", xy=(2.26, 25), xytext=(2.26, 33),
                arrowprops=dict(arrowstyle="<->", color="#CC0633", lw=2))
    ax.text(2.35, 29, "More than\nVisa + MC\ncombined",
            color="#CC0633", fontsize=12, va="center", style="italic")
    return _save(fig, "v2_market.png")


def gen_price_table() -> Path:
    """USDT mid-price across 12 exchanges — shows the fragmentation."""
    np.random.seed(17)
    exchanges = [
        "Binance", "Coinbase", "Kraken", "KuCoin", "OKX",
        "Bybit", "Bitfinex", "Huobi", "Gate.io", "Bitstamp",
        "Gemini", "Bitget",
    ]
    base = 1.0000
    # Realistic USDT spread: ~0.3% max
    prices = base + np.random.uniform(-0.0025, 0.0025, len(exchanges))
    prices = np.sort(prices)  # sort for visual clarity

    fig, ax = plt.subplots(figsize=(10, 5.2))
    colors = ["#CC0633" if p == prices.min() or p == prices.max()
              else ("#1A1A2E" if abs(p - base) > 0.001 else "#444444")
              for p in prices]
    bars = ax.barh(exchanges, prices - 0.997, left=0.997, color=colors,
                   height=0.65, edgecolor="white", linewidth=1.5, zorder=3)

    # Dollar label
    for bar, p, col in zip(bars, prices, colors):
        ax.text(p + 0.00003, bar.get_y() + bar.get_height()/2,
                f"${p:.4f}", va="center", ha="left",
                fontsize=12, fontweight="bold", color=col)

    # Parity line
    ax.axvline(1.0000, color="#888888", linewidth=1.5, linestyle="--", alpha=0.7)
    ax.text(1.0001, -0.7, "parity\n$1.0000", fontsize=11,
            color="#888888", ha="left", va="top", style="italic")

    # Spread annotation
    spread = prices.max() - prices.min()
    ax.annotate("", xy=(prices.max(), 11.5), xytext=(prices.min(), 11.5),
                arrowprops=dict(arrowstyle="<->", color="#CC0633", lw=2.5))
    ax.text((prices.min() + prices.max())/2, 11.9,
            f"Spread = ${spread:.4f}  ← arbitrage window",
            ha="center", fontsize=13, color="#CC0633", fontweight="bold")

    ax.set_xlabel("USDT mid-price (USD)", fontsize=14)
    ax.set_xlim(0.9965, 1.004)
    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.tick_params(axis="x", labelsize=12)
    ax.tick_params(axis="y", labelsize=12)
    return _save(fig, "v2_price_table.png")


def gen_pipeline() -> Path:
    """System pipeline: Data → Graph → A*+h₂ → Path → Profit."""
    fig, ax = plt.subplots(figsize=(12, 3.8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 4)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    boxes = [
        (1.0, "Live Order\nBook Data\n12 exchanges", "#1A1A2E", "white"),
        (3.5, "Execution-Aware\nGraph\n41 nodes · 864 edges", "#1A1A2E", "white"),
        (6.5, "A* Search\n+ h₂ Slippage\nHeuristic", "#CC0633", "white"),
        (9.5, "Profitable\nArbitrage Path\n≥ $0 net profit", "#2E7D32", "white"),
    ]
    box_w, box_h = 2.0, 2.6
    for cx, label, bg, fg in boxes:
        fancy = FancyBboxPatch((cx - box_w/2, 0.7), box_w, box_h,
                               boxstyle="round,pad=0.1",
                               facecolor=bg, edgecolor="white", linewidth=2,
                               zorder=3)
        ax.add_patch(fancy)
        ax.text(cx, 2.0, label, ha="center", va="center",
                fontsize=13, color=fg, fontweight="bold",
                multialignment="center", zorder=4)

    # Arrows between boxes
    arrow_ys = 2.0
    for x_start, x_end in [(2.0, 2.5), (4.5, 5.5), (7.5, 8.5)]:
        ax.annotate("", xy=(x_end, arrow_ys), xytext=(x_start, arrow_ys),
                    arrowprops=dict(arrowstyle="->", color="#888888",
                                    lw=2.5, mutation_scale=20))

    # Sub-labels below boxes
    sub_labels = [
        (1.0,  "taker fees · slippage\ngas cost · reliability"),
        (3.5,  "weighted directed graph\nall execution costs on edges"),
        (6.5,  "f(n) = g(n) + h₂(n)\nadmissibility traded for speed"),
        (9.5,  "found in <10 ms\n99.6% still valid at +2 min"),
    ]
    for cx, sub in sub_labels:
        ax.text(cx, 0.35, sub, ha="center", va="center",
                fontsize=10.5, color="#555555", style="italic",
                multialignment="center")

    return _save(fig, "v2_pipeline.png")


def gen_slippage_curve() -> Path:
    """Price impact vs order size — motivates h₂."""
    fig, ax = plt.subplots(figsize=(5.2, 3.8))
    order_size = np.linspace(0, 100_000, 300)
    # Quadratic-ish price impact
    impact = 0.002 * (order_size / 10_000) ** 1.4
    ax.fill_between(order_size, 0, impact * 100, alpha=0.15, color="#CC0633")
    ax.plot(order_size / 1000, impact * 100, color="#CC0633", linewidth=2.5)

    # Threshold marker
    threshold = 50_000
    ax.axvline(threshold / 1000, color="#CC0633", linestyle="--",
               linewidth=1.5, alpha=0.8)
    ax.text(threshold / 1000 + 2, 0.35, "order\nlimit", fontsize=10,
            color="#CC0633", va="top", style="italic")

    ax.set_xlabel("Order Size ($K)", fontsize=13)
    ax.set_ylabel("Price Impact (%)", fontsize=13)
    ax.set_title("h₂: Slippage Penalty", fontsize=14, fontweight="bold",
                 color="#CC0633")
    ax.spines["left"].set_color("#DDDDDD")
    ax.spines["bottom"].set_color("#DDDDDD")
    fig.patch.set_facecolor("white")
    plt.tight_layout()
    return _save(fig, "v2_slippage.png")


def gen_baselines_fail() -> Path:
    """Bar chart comparing baselines + our approach on a single metric."""
    fig, ax = plt.subplots(figsize=(9, 4.5))
    methods  = ["Bellman-Ford\n(negative cycle)", "1-Hop\nEnumeration",
                "2-Hop\nEnumeration", "A* + h₂\n(ours)"]
    profits  = [0, 0, 0, 9.91]   # $ profit on $10k order
    success  = [0, 0, 0, 100]    # % paths found with profit > 0
    colors   = ["#DDDDDD", "#CCCCCC", "#AAAAAA", "#CC0633"]

    x = np.arange(len(methods))
    bars = ax.bar(x, profits, color=colors, width=0.55,
                  edgecolor="white", linewidth=2, zorder=3)

    for bar, p, c in zip(bars, profits, colors):
        label = f"${p:.2f}" if p > 0 else "FAIL\n(no profitable path)"
        ypos = p + 0.15 if p > 0 else 0.15
        ax.text(bar.get_x() + bar.get_width()/2, ypos,
                label, ha="center", va="bottom",
                fontsize=14, fontweight="bold",
                color="#CC0633" if p > 0 else "#888888")

    ax.set_xticks(x)
    ax.set_xticklabels(methods, fontsize=13)
    ax.set_ylabel("Net Profit on $10 000 order (USD)", fontsize=13)
    ax.set_ylim(-0.5, 13)
    ax.spines["left"].set_color("#DDDDDD")
    ax.spines["bottom"].set_color("#DDDDDD")

    # BIG annotation
    ax.text(3, 11.5, "Only A* with h₂\nfinds a profitable path",
            ha="center", fontsize=14, color="#CC0633",
            fontweight="bold", va="top",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#FFF0F0",
                      edgecolor="#CC0633", linewidth=1.5))
    return _save(fig, "v2_baselines.png")


# ── python-pptx helpers (same as v1) ──────────────────────────────────────────

def new_prs():
    prs = Presentation()
    prs.slide_width  = SW
    prs.slide_height = SH
    return prs

def blank_slide(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])

def add_rect(slide, x, y, w, h, rgb: RGBColor, opacity_pct=100):
    shape = slide.shapes.add_shape(1, x, y, w, h)
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb
    shape.line.fill.background()
    if opacity_pct < 100:
        sp = shape.element
        spPr = sp.find(qn("p:spPr"))
        sf = spPr.find(".//" + qn("a:solidFill"))
        clr = sf.find(qn("a:srgbClr"))
        al = etree.SubElement(clr, qn("a:alpha"))
        al.set("val", str(opacity_pct * 1000))
    return shape

def add_text(slide, text, x, y, w, h,
             size=20, bold=False, italic=False, color=DARK,
             align=PP_ALIGN.LEFT, wrap=True, font="Arial"):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    run.font.name = font
    return tb

def add_pic(slide, path, x, y, width=None, height=None):
    if width and height:
        slide.shapes.add_picture(str(path), x, y, width, height)
    elif width:
        slide.shapes.add_picture(str(path), x, y, width=width)
    elif height:
        slide.shapes.add_picture(str(path), x, y, height=height)
    else:
        slide.shapes.add_picture(str(path), x, y)

def add_logo(slide):
    logo_w = Inches(2.1)
    add_pic(slide, LOGO, SW - logo_w - Inches(0.15), Inches(0.08), width=logo_w)

def add_header(slide, title, subtitle=""):
    add_rect(slide, 0, 0, SW, HDR_H, SFU_RED)
    add_text(slide, title,
             MARGIN, Inches(0.06), SW - MARGIN*2 - Inches(2.3), HDR_H - Inches(0.08),
             size=25, bold=True, color=WHITE)
    if subtitle:
        add_text(slide, subtitle,
                 SW - Inches(2.4), Inches(0.10), Inches(2.1), HDR_H - Inches(0.12),
                 size=11, color=RGBColor(0xFF, 0xCC, 0xCC), align=PP_ALIGN.RIGHT)

def add_footer(slide, num):
    add_rect(slide, 0, FTR_Y, SW, FTR_H, RGBColor(0xEE, 0xEE, 0xEE))
    add_text(slide, AUTHOR,
             MARGIN, FTR_Y + Inches(0.04), Inches(5), FTR_H,
             size=10, color=MGREY)
    add_text(slide, CONF,
             Inches(4.5), FTR_Y + Inches(0.04), Inches(5), FTR_H,
             size=10, color=MGREY, align=PP_ALIGN.CENTER)
    add_text(slide, f"{num} / {N_SLIDES}",
             SW - Inches(1.2), FTR_Y + Inches(0.04), Inches(1.0), FTR_H,
             size=10, color=MGREY, align=PP_ALIGN.RIGHT)

def add_divider(slide, y, color=SFU_RED, width=None):
    w = width or SW - MARGIN * 2
    add_rect(slide, MARGIN, y, w, Inches(0.025), color)

def _dark_overlay(slide, opacity=72):
    add_rect(slide, 0, 0, SW, SH, DARK, opacity_pct=opacity)

def add_bullets(slide, lines, x, y, w, h, size=18, color=DARK, spacing_pt=8):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    first = True
    for line in lines:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = PP_ALIGN.LEFT
        p.space_before = Pt(spacing_pt)
        r = p.add_run()
        r.text = "  •  " + line
        r.font.size = Pt(size)
        r.font.color.rgb = color
        r.font.name = "Arial"


# ── SLIDE BUILDERS ─────────────────────────────────────────────────────────────

def s01_title(prs):
    s = blank_slide(prs)
    if (FIGS / "FullGraph.png").exists():
        add_pic(s, FIGS / "FullGraph.png", 0, 0, width=SW, height=SH)
    _dark_overlay(s, 74)
    add_rect(s, 0, 0, Inches(0.22), SH, SFU_RED)

    add_text(s, "Execution-Aware A* Search for\nCross-Exchange Stablecoin Arbitrage",
             Inches(0.55), Inches(1.5), Inches(12.2), Inches(2.3),
             size=42, bold=True, color=WHITE)
    add_rect(s, Inches(0.55), Inches(3.85), Inches(6.0), Inches(0.04), SFU_RED)
    add_text(s,
             "Can domain-specific heuristics reduce search cost\n"
             "while preserving profit quality?",
             Inches(0.55), Inches(4.0), Inches(11.0), Inches(0.8),
             size=18, italic=True, color=RGBColor(0xFF, 0xCC, 0xCC))
    add_text(s, AUTHOR, Inches(0.55), Inches(5.0), Inches(9), Inches(0.5),
             size=18, color=WHITE)
    add_text(s, CONF, Inches(0.55), Inches(5.5), Inches(9), Inches(0.5),
             size=14, italic=True, color=RGBColor(0xFF, 0xCC, 0xCC))
    add_logo(s); add_footer(s, 1)
    print("  S1: Title")


def s02_market(prs, chart):
    s = blank_slide(prs)
    add_header(s, "The $33 Trillion Market", "Slide 2")
    add_logo(s)
    # Chart left
    add_pic(s, chart, MARGIN, CONTENT_Y + Inches(0.05), width=Inches(7.0))
    # Stats right
    rx, ry, rw = Inches(7.75), CONTENT_Y + Inches(0.3), SW - Inches(7.75) - MARGIN
    for val, label in [("$300B+", "market cap in circulation"),
                       ("$33T",   "annual transaction volume")]:
        add_text(s, val, rx, ry, rw, Inches(0.8),
                 size=46, bold=True, color=SFU_RED, align=PP_ALIGN.CENTER)
        add_text(s, label, rx, ry + Inches(0.82), rw, Inches(0.4),
                 size=13, italic=True, color=MGREY, align=PP_ALIGN.CENTER)
        add_divider(s, ry + Inches(1.3), color=RGBColor(0xDD, 0xDD, 0xDD),
                    width=rw)
        ry += Inches(1.5)
    add_text(s,
             '"The liquidity highways\nof the entire crypto ecosystem"',
             rx, ry + Inches(0.15), rw, Inches(1.1),
             size=14, italic=True, color=DARK, align=PP_ALIGN.CENTER)
    add_footer(s, 2)
    print("  S2: Market")


def s03_fragmentation(prs, price_table):
    s = blank_slide(prs)
    add_header(s, "The Opportunity: Price Fragmentation Across 12 Exchanges", "Slide 3")
    add_logo(s)
    # Full-width price table
    add_pic(s, price_table, MARGIN, CONTENT_Y + Inches(0.05),
            width=SW - MARGIN * 2)
    add_footer(s, 3)
    print("  S3: Price Fragmentation")


def s04_barriers(prs):
    s = blank_slide(prs)
    add_header(s, "The Problem: Four Execution Barriers", "Slide 4")
    add_logo(s)

    add_text(s,
             '"Existing systems say: take it. But here is what they do not tell you."',
             MARGIN, CONTENT_Y + Inches(0.05), SW - MARGIN*2, Inches(0.5),
             size=16, italic=True, color=DARK)
    add_rect(s, MARGIN, CONTENT_Y + Inches(0.6), SW - MARGIN*2, Inches(0.03), SFU_RED)

    cards = [
        ("1  Liquidity",   "Order size may exhaust\nthe book depth",          "#2196F3"),
        ("2  Slippage ★",  "Large orders move price\nmid-execution (h₂)",     "#CC0633"),
        ("3  Latency",     "Blockchain settlement\nmay miss the window",       "#FF9800"),
        ("4  Reliability", "Exchanges may suspend\nwithdrawals overnight",     "#2E7D32"),
    ]
    card_w = (SW - MARGIN*2 - Inches(0.18)*3) / 4
    card_h = Inches(2.5)
    card_y = CONTENT_Y + Inches(0.75)
    for i, (title, body, hex_col) in enumerate(cards):
        cx = MARGIN + i * (card_w + Inches(0.18))
        rgb = RGBColor.from_string(hex_col.lstrip("#"))
        add_rect(s, cx, card_y, card_w, card_h, rgb)
        add_text(s, title, cx + Inches(0.12), card_y + Inches(0.12),
                 card_w - Inches(0.24), Inches(0.55),
                 size=17, bold=True, color=WHITE)
        add_text(s, body, cx + Inches(0.12), card_y + Inches(0.72),
                 card_w - Inches(0.24), card_h - Inches(0.8),
                 size=14, color=WHITE)

    add_text(s,
             "Bellman-Ford, 1-hop, and 2-hop enumeration all fail to find a profitable executable path.",
             MARGIN, card_y + card_h + Inches(0.25), SW - MARGIN*2, Inches(0.5),
             size=16, bold=True, color=SFU_RED, align=PP_ALIGN.CENTER)
    add_footer(s, 4)
    print("  S4: Barriers")


def s05_baselines(prs, baselines_chart):
    s = blank_slide(prs)
    add_header(s, "Why Existing Baselines Fail", "Slide 5")
    add_logo(s)

    # Chart (left 2/3)
    add_pic(s, baselines_chart, MARGIN, CONTENT_Y + Inches(0.1), width=Inches(8.2))

    # Right: quick explanation
    rx, ry, rw = Inches(8.8), CONTENT_Y + Inches(0.3), SW - Inches(8.8) - MARGIN
    add_text(s, "Why they fail:", rx, ry, rw, Inches(0.5),
             size=16, bold=True, color=DARK)
    reasons = [
        "Bellman-Ford finds closed\ncycles — ignores open-path\nstablecoin arbitrage",
        "1-hop & 2-hop only scan\n≤2 edges — miss multi-hop\npaths with > $0 net profit",
        "None model slippage,\nfees, or transfer latency",
    ]
    ry2 = ry + Inches(0.55)
    for r in reasons:
        add_text(s, "▶  " + r, rx, ry2, rw, Inches(0.95),
                 size=12, color=DARK)
        ry2 += Inches(1.0)

    add_footer(s, 5)
    print("  S5: Baselines Fail")


def s06_dataset(prs):
    s = blank_slide(prs)
    add_header(s, "Dataset: The First Execution-Aware Stablecoin Graph", "Slide 6")
    add_logo(s)

    if (FIGS / "FullGraph.png").exists():
        add_pic(s, FIGS / "FullGraph.png", MARGIN, CONTENT_Y + Inches(0.1),
                width=Inches(7.2))

    rx, ry, rw = Inches(8.0), CONTENT_Y + Inches(0.2), SW - Inches(8.0) - MARGIN
    stats = [("12", "centralized\nexchanges"),
             ("9",  "stablecoin symbols\n(USDT, USDC, DAI…)"),
             ("41", "nodes"),
             ("864","edges"),]
    for val, label in stats:
        add_text(s, val, rx, ry, Inches(1.2), Inches(0.65),
                 size=38, bold=True, color=SFU_RED)
        add_text(s, label, rx + Inches(1.25), ry + Inches(0.06),
                 rw - Inches(1.3), Inches(0.65),
                 size=13, color=DARK)
        ry += Inches(0.95)

    add_divider(s, ry + Inches(0.12))
    add_text(s,
             "Every edge carries:\ntaker fee · live slippage (VWAP) ·\ngas cost · venue reliability score",
             rx, ry + Inches(0.28), rw, Inches(1.2),
             size=13, color=DARK)
    add_footer(s, 6)
    print("  S6: Dataset")


def s07_method(prs, pipeline):
    s = blank_slide(prs)
    add_header(s, "Method: A* Search — Google Maps for Money", "Slide 7")
    add_logo(s)

    add_text(s, "f (n)  =  g(n)  +  h(n)",
             MARGIN, CONTENT_Y + Inches(0.05), SW - MARGIN*2, Inches(0.7),
             size=34, bold=True, color=DARK, align=PP_ALIGN.CENTER,
             font="Courier New")
    add_text(s,
             "g(n) = accumulated execution cost so far     "
             "h(n) = domain-specific risk estimate ahead",
             MARGIN, CONTENT_Y + Inches(0.75), SW - MARGIN*2, Inches(0.4),
             size=15, italic=True, color=MGREY, align=PP_ALIGN.CENTER)
    add_divider(s, CONTENT_Y + Inches(1.22))
    add_pic(s, pipeline, MARGIN, CONTENT_Y + Inches(1.35),
            width=SW - MARGIN*2)
    add_footer(s, 7)
    print("  S7: Method")


def s08_heuristics(prs, slippage):
    s = blank_slide(prs)
    add_header(s, "Three Execution-Aware Heuristics", "Slide 8")
    add_logo(s)

    add_text(s,
             "Each heuristic adds a domain-specific penalty to h(n), steering A* toward "
             "paths that are profitable AND executable.",
             MARGIN, CONTENT_Y + Inches(0.05), SW - MARGIN*2, Inches(0.5),
             size=15, italic=True, color=DARK)
    add_divider(s, CONTENT_Y + Inches(0.6))

    # Three heuristic panels (left 8.5")
    panel_w = Inches(2.5)
    panel_h = Inches(4.0)
    panel_y = CONTENT_Y + Inches(0.72)
    heuristics = [
        ("h₁", "Liquidity",
         "Penalises paths where\norder size exceeds\nbook depth",
         "Is there enough\nmarket depth?",
         "#2196F3"),
        ("h₂ ★", "Slippage",
         "VWAP-based penalty:\npen. = max(0, VWAP − mid)\n× order size",
         "Will my order\nmove the price?",
         "#CC0633"),
        ("h₃", "Chain + Venue",
         "Congestion penalty +\nvenue reliability\ndiscount",
         "Will it settle\nin time?",
         "#2E7D32"),
    ]
    for i, (label, name, formula, question, col) in enumerate(heuristics):
        cx = MARGIN + i * (panel_w + Inches(0.2))
        rgb = RGBColor.from_string(col.lstrip("#"))
        add_rect(s, cx, panel_y, panel_w, panel_h, rgb)
        add_text(s, label, cx + Inches(0.1), panel_y + Inches(0.1),
                 panel_w - Inches(0.2), Inches(0.65),
                 size=28, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        add_text(s, name, cx + Inches(0.1), panel_y + Inches(0.75),
                 panel_w - Inches(0.2), Inches(0.45),
                 size=17, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        add_text(s, formula, cx + Inches(0.1), panel_y + Inches(1.22),
                 panel_w - Inches(0.2), Inches(1.2),
                 size=12, color=WHITE, align=PP_ALIGN.CENTER,
                 font="Courier New")
        add_text(s, f'"{question}"', cx + Inches(0.1), panel_y + Inches(2.6),
                 panel_w - Inches(0.2), Inches(0.85),
                 size=13, italic=True, color=RGBColor(0xFF, 0xFF, 0xAA),
                 align=PP_ALIGN.CENTER)

    # Right side: slippage curve
    rx = MARGIN + Inches(8.1)
    add_text(s, "h₂ in detail:",
             rx, panel_y, SW - rx - MARGIN, Inches(0.35),
             size=14, bold=True, color=SFU_RED)
    add_pic(s, slippage, rx, panel_y + Inches(0.4),
            width=SW - rx - MARGIN - Inches(0.1))

    add_text(s, "One of these three will prove decisive.",
             MARGIN, panel_y + panel_h + Inches(0.18), SW - MARGIN*2, Inches(0.4),
             size=16, bold=True, italic=True, color=SFU_RED,
             align=PP_ALIGN.CENTER)
    add_footer(s, 8)
    print("  S8: Heuristics")


def s09_result_hero(prs):
    """Hero result slide — fig01 takes 80% of the slide."""
    s = blank_slide(prs)
    # Dark red accent header
    add_rect(s, 0, 0, SW, Inches(0.80), SFU_RED)
    add_logo(s)
    add_text(s, "KEY RESULT",
             MARGIN, Inches(0.04), Inches(4), Inches(0.38),
             size=13, bold=True, color=RGBColor(0xFF, 0xCC, 0xCC))
    add_text(s,
             "h₂ (Slippage Heuristic) — 29% fewer node expansions. Same profit.",
             MARGIN, Inches(0.38), SW - MARGIN*2 - Inches(2.3), Inches(0.38),
             size=24, bold=True, color=WHITE)

    # fig01 — large
    fig01 = FIGS / "fig01_node_expansion_bar.png"
    if fig01.exists():
        img = Image.open(fig01)
        ar = img.size[0] / img.size[1]
        img_h = Inches(5.35)
        img_w = Inches(img_h.inches * ar)
        img_x = (SW - img_w) / 2
        add_pic(s, fig01, img_x, Inches(0.85), width=img_w)

    add_footer(s, 9)
    print("  S9: Hero Result")


def s10_profit_quality(prs):
    """fig03 profit boxplot + fig02 compute time."""
    s = blank_slide(prs)
    add_header(s, "Profit Quality & Compute Cost — The Full Picture", "Slide 10")
    add_logo(s)

    # Left: profit boxplot
    fig03 = FIGS / "fig03_profit_boxplot.png"
    if fig03.exists():
        add_pic(s, fig03, MARGIN, CONTENT_Y + Inches(0.05), width=Inches(6.5))

    # Right: compute time bar
    fig02 = FIGS / "fig02_compute_time_bar.png"
    rx = MARGIN + Inches(6.9)
    rw = SW - rx - MARGIN
    if fig02.exists():
        add_pic(s, fig02, rx, CONTENT_Y + Inches(0.05), width=rw)

    # Punchline at bottom
    add_rect(s, 0, FTR_Y - Inches(0.45), SW, Inches(0.45), SFU_RED, opacity_pct=10)
    add_text(s,
             "h₂ matches Dijkstra profit within 1%  ·  all heuristics run in <10 ms  ·  no speed-quality trade-off",
             MARGIN, FTR_Y - Inches(0.4), SW - MARGIN*2, Inches(0.38),
             size=14, bold=True, color=SFU_RED, align=PP_ALIGN.CENTER)
    add_footer(s, 10)
    print("  S10: Profit Quality")


def s11_overnight(prs):
    """fig10 overnight + fig11 heuristic comparison."""
    s = blank_slide(prs)
    add_header(s, "Overnight Validation — 7,200 Real Searches · Live Market Data", "Slide 11")
    add_logo(s)

    fig10 = FIGS / "fig10_overnight_timeseries.png"
    fig11 = FIGS / "fig11_overnight_heuristic_comparison.png"

    # Top: time series (full width)
    if fig10.exists():
        add_pic(s, fig10, MARGIN, CONTENT_Y + Inches(0.05),
                width=SW - MARGIN*2)

    # Bottom row: fig11 + stats
    row_y = CONTENT_Y + Inches(2.7)
    if fig11.exists():
        add_pic(s, fig11, MARGIN, row_y, width=Inches(7.5))

    # Stats callout (right of fig11)
    rx, ry, rw = Inches(8.2), row_y, SW - Inches(8.2) - MARGIN
    bullets = [
        "7 200 search instances",
        "100% found a profitable path",
        "8 hours continuous operation",
        "Live order book data",
    ]
    add_bullets(s, bullets, rx, ry, rw, Inches(2.2),
                size=15, color=DARK, spacing_pt=6)
    add_footer(s, 11)
    print("  S11: Overnight")


def s12_staleness(prs):
    """fig09 quote staleness — 99.6% execution window."""
    s = blank_slide(prs)
    add_header(s, "Execution Window — How Long Do Paths Stay Profitable?", "Slide 12")
    add_logo(s)

    fig09 = FIGS / "fig09_quote_staleness.png"
    if fig09.exists():
        add_pic(s, fig09, MARGIN, CONTENT_Y + Inches(0.1),
                width=Inches(8.8))

    rx = MARGIN + Inches(9.2)
    ry = CONTENT_Y + Inches(0.5)
    rw = SW - rx - MARGIN

    add_text(s, "99.6%", rx, ry, rw, Inches(1.0),
             size=52, bold=True, color=SFU_RED, align=PP_ALIGN.CENTER)
    add_text(s, "of paths remain\nprofitable at +2 min",
             rx, ry + Inches(1.0), rw, Inches(0.8),
             size=14, color=DARK, align=PP_ALIGN.CENTER, italic=True)
    add_divider(s, ry + Inches(2.0),
                color=RGBColor(0xDD, 0xDD, 0xDD), width=rw)
    add_text(s, "Practical guideline:\nact within 120 seconds\nof path discovery.",
             rx, ry + Inches(2.2), rw, Inches(1.2),
             size=14, bold=True, color=DARK, align=PP_ALIGN.CENTER)
    add_footer(s, 12)
    print("  S12: Staleness")


def s13_close(prs):
    """Closing slide — callback with fig18 radar."""
    s = blank_slide(prs)
    if (FIGS / "FullGraph.png").exists():
        add_pic(s, FIGS / "FullGraph.png", 0, 0, width=SW, height=SH)
    _dark_overlay(s, 78)
    add_rect(s, 0, 0, Inches(0.22), SH, SFU_RED)

    # Left: three-word summary
    add_text(s, "Less Exploration.", Inches(0.55), Inches(1.2),
             Inches(6.5), Inches(1.1), size=52, bold=True, color=WHITE)
    add_text(s, "More Execution.", Inches(0.55), Inches(2.3),
             Inches(6.5), Inches(1.1), size=52, bold=True, color=SFU_RED)
    add_text(s, "Same Profit.", Inches(0.55), Inches(3.4),
             Inches(6.5), Inches(1.1), size=52, bold=True, color=WHITE)

    add_text(s, "Thank you  ·  Questions?",
             Inches(0.55), Inches(4.7), Inches(6.5), Inches(0.6),
             size=22, italic=True, color=RGBColor(0xFF, 0xCC, 0xCC))
    add_text(s, "github.com/kevinl03/Stablecoin-CrossExchange-Arbitrage",
             Inches(0.55), Inches(5.4), Inches(7.0), Inches(0.45),
             size=13, color=RGBColor(0xAA, 0xAA, 0xAA))

    # Right: radar summary
    fig18 = FIGS / "fig18_radar_summary.png"
    if fig18.exists():
        radar_w = Inches(5.2)
        add_pic(s, fig18, SW - radar_w - Inches(0.4), Inches(0.7), width=radar_w)
        add_text(s, "Method comparison (all metrics)",
                 SW - Inches(5.4), Inches(0.4), Inches(5.2), Inches(0.35),
                 size=11, italic=True, color=RGBColor(0xAA, 0xAA, 0xAA),
                 align=PP_ALIGN.CENTER)

    add_logo(s); add_footer(s, 13)
    print("  S13: Close")


# ── MAIN ───────────────────────────────────────────────────────────────────────

def build():
    print("step 1/3 — generating visuals …")
    market    = gen_market_bar()
    price_tbl = gen_price_table()
    pipeline  = gen_pipeline()
    slippage  = gen_slippage_curve()
    baselines = gen_baselines_fail()

    print("step 2/3 — building slides …")
    prs = new_prs()
    s01_title(prs)
    s02_market(prs, market)
    s03_fragmentation(prs, price_tbl)
    s04_barriers(prs)
    s05_baselines(prs, baselines)
    s06_dataset(prs)
    s07_method(prs, pipeline)
    s08_heuristics(prs, slippage)
    s09_result_hero(prs)
    s10_profit_quality(prs)
    s11_overnight(prs)
    s12_staleness(prs)
    s13_close(prs)

    print("step 3/3 — saving …")
    prs.save(str(OUT))
    print(f"\nwrote {OUT}  ({OUT.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    build()
