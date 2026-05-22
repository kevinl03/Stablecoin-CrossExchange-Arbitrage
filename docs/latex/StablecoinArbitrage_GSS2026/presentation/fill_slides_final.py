"""
fill_slides_final.py — 9-slide final presentation for GSS 2026
Run:   python3 docs/latex/StablecoinArbitrage_GSS2026/presentation/fill_slides_final.py
Output: docs/latex/.../presentation/slides_final.pptx

Structure (matches script.md):
  S1  Title            — FullGraph dark full-bleed
  S2  The Market       — $33T bar chart + stat callouts
  S3  The Problem      — 4 barrier cards + "all baselines fail" punchline
  S4  The Dataset      — FullGraph + 4 stats
  S5  A* Method        — f(n) formula + pipeline diagram
  S6  Three Heuristics — 3 panels + slippage curve
  S7  The Result       — fig01 hero (full-screen 29%)
  S8  Real-World Proof — fig10 overnight (top) + fig09 staleness (bottom)
  S9  Close            — dark FullGraph + three-word summary + fig18 radar
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "venv312/lib/python3.14/site-packages"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import numpy as np
from PIL import Image

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from lxml import etree

# ── constants ──────────────────────────────────────────────────────────────────
SW = Inches(13.333)
SH = Inches(7.5)
N  = 9   # total slides

SFU_RED = RGBColor(0xCC, 0x06, 0x33)
DARK    = RGBColor(0x1A, 0x1A, 0x2E)
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
MGREY   = RGBColor(0x88, 0x88, 0x88)
LGREY   = RGBColor(0xEE, 0xEE, 0xEE)

HDR_H     = Inches(0.52)
FTR_H     = Inches(0.28)
FTR_Y     = SH - FTR_H
CONTENT_Y = HDR_H + Inches(0.18)
MARGIN    = Inches(0.38)

AUTHOR = "Kevin Litvin · Simon Fraser University"
CONF   = "Canadian AI 2026 · GSS"

FIGS = ROOT / "docs/latex/StablecoinArbitrage_CAIAC2026/figures"
OUT  = ROOT / "docs/latex/StablecoinArbitrage_GSS2026/presentation/slides_final.pptx"
TMP  = Path("/tmp/gss_slides_final")
TMP.mkdir(parents=True, exist_ok=True)

LOGO = FIGS / "logo-canai-2026.png"

plt.rcParams.update({
    "font.family": "sans-serif",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": False,
    "figure.facecolor": "white", "axes.facecolor": "white",
})

# ── matplotlib asset generators ────────────────────────────────────────────────

def _save(fig, name):
    p = TMP / name
    fig.savefig(p, dpi=200, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close(fig)
    print(f"    {name}")
    return p


def gen_market():
    fig, ax = plt.subplots(figsize=(9, 5.0))
    labels = ["Mastercard\n(2023)", "Visa\n(2023)", "Stablecoins\n(2024)"]
    vals   = [9, 15, 33]
    cols   = ["#AAAAAA", "#888888", "#CC0633"]
    bars = ax.bar(labels, vals, color=cols, width=0.52, zorder=3,
                  edgecolor="white", linewidth=2)
    for bar, v, c in zip(bars, vals, cols):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.4,
                f"${v}T", ha="center", va="bottom",
                fontsize=22, fontweight="bold",
                color="#CC0633" if v == 33 else "#555555")
    ax.set_ylim(0, 40)
    ax.set_ylabel("Annual Transaction Volume (USD Trillion)", fontsize=14)
    ax.tick_params(labelsize=14)
    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.annotate("", xy=(2.26, 25), xytext=(2.26, 33),
                arrowprops=dict(arrowstyle="<->", color="#CC0633", lw=2))
    ax.text(2.36, 29, "More than\nVisa + MC\ncombined",
            color="#CC0633", fontsize=12, va="center", style="italic")
    return _save(fig, "fin_market.png")


def gen_pipeline():
    fig, ax = plt.subplots(figsize=(12, 3.6))
    ax.set_xlim(0, 12); ax.set_ylim(0, 4); ax.axis("off")
    boxes = [
        (1.0,  "Live Order\nBook Data\n12 exchanges",          "#1A1A2E", "white"),
        (3.5,  "Execution-Aware\nGraph\n41 nodes · 864 edges", "#1A1A2E", "white"),
        (6.5,  "A* Search\n+ h₂ Slippage\nHeuristic",         "#CC0633", "white"),
        (9.5,  "Profitable\nArbitrage Path\n≥ $0 net profit",  "#2E7D32", "white"),
    ]
    bw, bh = 2.0, 2.6
    for cx, label, bg, fg in boxes:
        ax.add_patch(FancyBboxPatch((cx-bw/2, 0.7), bw, bh,
                                    boxstyle="round,pad=0.1",
                                    facecolor=bg, edgecolor="white", linewidth=2, zorder=3))
        ax.text(cx, 2.0, label, ha="center", va="center",
                fontsize=13, color=fg, fontweight="bold",
                multialignment="center", zorder=4)
    for xs, xe in [(2.0, 2.5), (4.5, 5.5), (7.5, 8.5)]:
        ax.annotate("", xy=(xe, 2.0), xytext=(xs, 2.0),
                    arrowprops=dict(arrowstyle="->", color="#888888", lw=2.5, mutation_scale=20))
    sub = [(1.0, "fees · slippage\ngas · reliability"),
           (3.5, "weighted directed\ngraph"),
           (6.5, "f(n)=g(n)+h₂(n)\ngoal-directed"),
           (9.5, "found in <10 ms\n99.6% valid +2 min")]
    for cx, s in sub:
        ax.text(cx, 0.35, s, ha="center", va="center",
                fontsize=10.5, color="#555555", style="italic", multialignment="center")
    fig.patch.set_facecolor("white")
    return _save(fig, "fin_pipeline.png")


def gen_slippage():
    fig, ax = plt.subplots(figsize=(5, 3.6))
    order = np.linspace(0, 100_000, 300)
    impact = 0.002 * (order / 10_000) ** 1.4
    ax.fill_between(order/1000, 0, impact*100, alpha=0.15, color="#CC0633")
    ax.plot(order/1000, impact*100, color="#CC0633", linewidth=2.5)
    ax.axvline(50, color="#CC0633", linestyle="--", linewidth=1.5, alpha=0.8)
    ax.text(52, 0.35, "order\nlimit", fontsize=10, color="#CC0633", va="top", style="italic")
    ax.set_xlabel("Order Size ($K)", fontsize=13)
    ax.set_ylabel("Price Impact (%)", fontsize=13)
    ax.set_title("h₂: Slippage Penalty", fontsize=13, fontweight="bold", color="#CC0633", pad=6)
    ax.spines["left"].set_color("#DDDDDD"); ax.spines["bottom"].set_color("#DDDDDD")
    plt.tight_layout()
    return _save(fig, "fin_slippage.png")


# ── python-pptx helpers ────────────────────────────────────────────────────────

def _prs():
    p = Presentation(); p.slide_width = SW; p.slide_height = SH; return p

def _blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])

def _rect(slide, x, y, w, h, rgb, opacity=100):
    s = slide.shapes.add_shape(1, x, y, w, h)
    s.fill.solid(); s.fill.fore_color.rgb = rgb; s.line.fill.background()
    if opacity < 100:
        sp = s.element; spPr = sp.find(qn("p:spPr"))
        sf = spPr.find(".//" + qn("a:solidFill"))
        clr = sf.find(qn("a:srgbClr"))
        al = etree.SubElement(clr, qn("a:alpha")); al.set("val", str(opacity*1000))
    return s

def _txt(slide, text, x, y, w, h, size=20, bold=False, italic=False,
         color=DARK, align=PP_ALIGN.LEFT, font="Arial", wrap=True):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame; tf.word_wrap = wrap
    p = tf.paragraphs[0]; p.alignment = align
    r = p.add_run(); r.text = text
    r.font.size = Pt(size); r.font.bold = bold
    r.font.italic = italic; r.font.color.rgb = color; r.font.name = font
    return tb

def _bullets(slide, lines, x, y, w, h, size=17, color=DARK, gap=6):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame; tf.word_wrap = True
    first = True
    for line in lines:
        p = tf.paragraphs[0] if first else tf.add_paragraph(); first = False
        p.alignment = PP_ALIGN.LEFT; p.space_before = Pt(gap)
        r = p.add_run(); r.text = "  •  " + line
        r.font.size = Pt(size); r.font.color.rgb = color; r.font.name = "Arial"

def _pic(slide, path, x, y, width=None, height=None):
    if width and height: slide.shapes.add_picture(str(path), x, y, width, height)
    elif width:  slide.shapes.add_picture(str(path), x, y, width=width)
    elif height: slide.shapes.add_picture(str(path), x, y, height=height)
    else:        slide.shapes.add_picture(str(path), x, y)

def _logo(slide):
    _pic(slide, LOGO, SW - Inches(2.15) - Inches(0.15), Inches(0.09), width=Inches(2.15))

def _header(slide, title):
    _rect(slide, 0, 0, SW, HDR_H, SFU_RED)
    _txt(slide, title, MARGIN, Inches(0.07), SW - MARGIN*2 - Inches(2.4), HDR_H - Inches(0.1),
         size=24, bold=True, color=WHITE)

def _footer(slide, num):
    _rect(slide, 0, FTR_Y, SW, FTR_H, LGREY)
    _txt(slide, AUTHOR,       MARGIN, FTR_Y+Inches(0.04), Inches(5), FTR_H, size=10, color=MGREY)
    _txt(slide, CONF,         Inches(4.5), FTR_Y+Inches(0.04), Inches(5), FTR_H,
         size=10, color=MGREY, align=PP_ALIGN.CENTER)
    _txt(slide, f"{num} / {N}", SW-Inches(1.2), FTR_Y+Inches(0.04), Inches(1), FTR_H,
         size=10, color=MGREY, align=PP_ALIGN.RIGHT)

def _dark_overlay(slide, opacity=74):
    _rect(slide, 0, 0, SW, SH, DARK, opacity)

def _divider(slide, y, color=SFU_RED, width=None):
    _rect(slide, MARGIN, y, width or SW-MARGIN*2, Inches(0.025), color)

def _img_ar(path):
    img = Image.open(path); return img.size[0] / img.size[1]


# ── SLIDES ─────────────────────────────────────────────────────────────────────

def s1_title(prs):
    s = _blank(prs)
    fg = FIGS / "FullGraph.png"
    if fg.exists(): _pic(s, fg, 0, 0, width=SW, height=SH)
    _dark_overlay(s, 74)
    _rect(s, 0, 0, Inches(0.22), SH, SFU_RED)

    _txt(s, "Execution-Aware A* Search for\nCross-Exchange Stablecoin Arbitrage",
         Inches(0.55), Inches(1.4), Inches(12.2), Inches(2.3),
         size=42, bold=True, color=WHITE)
    _rect(s, Inches(0.55), Inches(3.75), Inches(6.0), Inches(0.04), SFU_RED)
    _txt(s, "Can domain-specific heuristics reduce search cost\nwhile preserving profit quality?",
         Inches(0.55), Inches(3.9), Inches(11.0), Inches(0.8),
         size=18, italic=True, color=RGBColor(0xFF, 0xCC, 0xCC))
    _txt(s, AUTHOR, Inches(0.55), Inches(4.9), Inches(9), Inches(0.5), size=18, color=WHITE)
    _txt(s, CONF,   Inches(0.55), Inches(5.4), Inches(9), Inches(0.5),
         size=14, italic=True, color=RGBColor(0xFF, 0xCC, 0xCC))
    _logo(s); _footer(s, 1)
    print("  S1 Title")


def s2_market(prs, chart):
    s = _blank(prs)
    _header(s, "The $33 Trillion Market"); _logo(s)
    cy = CONTENT_Y + Inches(0.05)
    _pic(s, chart, MARGIN, cy, width=Inches(7.2))

    rx, rw = Inches(7.8), SW - Inches(7.8) - MARGIN
    ry = cy + Inches(0.3)
    for val, lbl in [("$300B+", "market cap in circulation"), ("$33T", "annual volume")]:
        _txt(s, val, rx, ry, rw, Inches(0.8), size=46, bold=True, color=SFU_RED, align=PP_ALIGN.CENTER)
        _txt(s, lbl, rx, ry+Inches(0.82), rw, Inches(0.4), size=13, italic=True,
             color=MGREY, align=PP_ALIGN.CENTER)
        _divider(s, ry+Inches(1.3), color=RGBColor(0xDD,0xDD,0xDD), width=rw)
        ry += Inches(1.52)
    _txt(s, '"The liquidity highways of\nthe entire crypto ecosystem"',
         rx, ry+Inches(0.2), rw, Inches(1.1), size=14, italic=True, color=DARK,
         align=PP_ALIGN.CENTER)
    _footer(s, 2)
    print("  S2 Market")


def s3_problem(prs):
    s = _blank(prs)
    _header(s, "The Problem: Four Execution Barriers"); _logo(s)

    _txt(s, '"It is 2 AM. USDT is cheaper on Kraken than KuCoin. The math works. Existing systems say: take it."',
         MARGIN, CONTENT_Y+Inches(0.05), SW-MARGIN*2, Inches(0.5),
         size=15, italic=True, color=DARK)
    _divider(s, CONTENT_Y+Inches(0.6))

    cards = [
        ("1  Liquidity",   "Order may exhaust\nbook depth",           "#2196F3"),
        ("2  Slippage ★",  "Large orders move\nprice mid-fill",       "#CC0633"),
        ("3  Latency",     "Settlement may\nmiss the window",         "#FF9800"),
        ("4  Reliability", "Exchanges may\nsuspend withdrawals",      "#2E7D32"),
    ]
    cw = (SW - MARGIN*2 - Inches(0.18)*3) / 4
    ch = Inches(2.5); cy = CONTENT_Y + Inches(0.75)
    for i, (title, body, hex_c) in enumerate(cards):
        cx = MARGIN + i*(cw + Inches(0.18))
        rgb = RGBColor.from_string(hex_c.lstrip("#"))
        _rect(s, cx, cy, cw, ch, rgb)
        _txt(s, title, cx+Inches(0.12), cy+Inches(0.12), cw-Inches(0.24), Inches(0.55),
             size=17, bold=True, color=WHITE)
        _txt(s, body,  cx+Inches(0.12), cy+Inches(0.72), cw-Inches(0.24), ch-Inches(0.8),
             size=14, color=WHITE)

    # Punchline
    py = cy + ch + Inches(0.22)
    _rect(s, MARGIN, py, SW-MARGIN*2, Inches(0.44), RGBColor(0xFF,0xF0,0xF0))
    _txt(s, "Bellman-Ford · 1-hop · 2-hop enumeration — all fail under live market conditions.",
         MARGIN+Inches(0.15), py+Inches(0.07), SW-MARGIN*2-Inches(0.3), Inches(0.38),
         size=15, bold=True, color=SFU_RED, align=PP_ALIGN.CENTER)
    _footer(s, 3)
    print("  S3 Problem")


def s4_dataset(prs):
    s = _blank(prs)
    _header(s, "Dataset: The First Execution-Aware Stablecoin Graph"); _logo(s)
    fg = FIGS / "FullGraph.png"
    if fg.exists(): _pic(s, fg, MARGIN, CONTENT_Y+Inches(0.1), width=Inches(7.2))

    rx, ry, rw = Inches(8.0), CONTENT_Y+Inches(0.2), SW-Inches(8.0)-MARGIN
    for val, lbl in [("12","centralized\nexchanges"), ("9","stablecoin symbols\n(USDT, USDC, DAI…)"),
                     ("41","nodes"), ("864","edges")]:
        _txt(s, val,  rx, ry, Inches(1.2), Inches(0.65), size=38, bold=True, color=SFU_RED)
        _txt(s, lbl,  rx+Inches(1.3), ry+Inches(0.06), rw-Inches(1.3), Inches(0.65), size=13, color=DARK)
        ry += Inches(0.96)
    _divider(s, ry+Inches(0.1))
    _txt(s, "Every edge carries:\ntaker fee · VWAP slippage ·\ngas cost · venue reliability",
         rx, ry+Inches(0.25), rw, Inches(1.2), size=13, color=DARK)
    _footer(s, 4)
    print("  S4 Dataset")


def s5_method(prs, pipeline):
    s = _blank(prs)
    _header(s, "Method: A* Search — Google Maps for Money"); _logo(s)

    _txt(s, "f (n)  =  g(n)  +  h(n)",
         MARGIN, CONTENT_Y+Inches(0.05), SW-MARGIN*2, Inches(0.7),
         size=36, bold=True, color=DARK, align=PP_ALIGN.CENTER, font="Courier New")
    _txt(s, "g(n) = accumulated execution cost so far          h(n) = domain-specific risk estimate ahead",
         MARGIN, CONTENT_Y+Inches(0.75), SW-MARGIN*2, Inches(0.4),
         size=15, italic=True, color=MGREY, align=PP_ALIGN.CENTER)
    _divider(s, CONTENT_Y+Inches(1.22))
    _pic(s, pipeline, MARGIN, CONTENT_Y+Inches(1.35), width=SW-MARGIN*2)
    _footer(s, 5)
    print("  S5 Method")


def s6_heuristics(prs, slippage):
    s = _blank(prs)
    _header(s, "Three Execution-Aware Heuristics"); _logo(s)

    _txt(s, "Each heuristic adds a domain-specific penalty to h(n), steering A* toward paths that are profitable AND executable.",
         MARGIN, CONTENT_Y+Inches(0.05), SW-MARGIN*2, Inches(0.5), size=15, italic=True, color=DARK)
    _divider(s, CONTENT_Y+Inches(0.6))

    pw, ph, py = Inches(2.5), Inches(4.0), CONTENT_Y+Inches(0.72)
    heuristics = [
        ("h₁",   "Liquidity",  "Penalises paths where\norder size exceeds\nbook depth",
         "Is there enough\nmarket depth?",  "#2196F3"),
        ("h₂ ★", "Slippage",   "VWAP penalty:\npen = max(0, VWAP−mid)\n× order size",
         "Will my order\nmove the price?", "#CC0633"),
        ("h₃",   "Chain+Venue","Congestion penalty\n+ venue reliability\ndiscount",
         "Will it settle\nin time?",        "#2E7D32"),
    ]
    for i, (lbl, name, formula, q, hex_c) in enumerate(heuristics):
        cx = MARGIN + i*(pw + Inches(0.2))
        rgb = RGBColor.from_string(hex_c.lstrip("#"))
        _rect(s, cx, py, pw, ph, rgb)
        _txt(s, lbl,     cx+Inches(0.1), py+Inches(0.1),  pw-Inches(0.2), Inches(0.65),
             size=28, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        _txt(s, name,    cx+Inches(0.1), py+Inches(0.75), pw-Inches(0.2), Inches(0.45),
             size=17, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        _txt(s, formula, cx+Inches(0.1), py+Inches(1.22), pw-Inches(0.2), Inches(1.2),
             size=12, color=WHITE, align=PP_ALIGN.CENTER, font="Courier New")
        _txt(s, f'"{q}"', cx+Inches(0.1), py+Inches(2.6), pw-Inches(0.2), Inches(0.85),
             size=13, italic=True, color=RGBColor(0xFF,0xFF,0xAA), align=PP_ALIGN.CENTER)

    # Slippage curve
    rx = MARGIN + Inches(8.1)
    _txt(s, "h₂ in detail:", rx, py, SW-rx-MARGIN, Inches(0.35), size=14, bold=True, color=SFU_RED)
    _pic(s, slippage, rx, py+Inches(0.4), width=SW-rx-MARGIN-Inches(0.1))

    _txt(s, "One of these three will prove decisive.",
         MARGIN, py+ph+Inches(0.18), SW-MARGIN*2, Inches(0.4),
         size=16, bold=True, italic=True, color=SFU_RED, align=PP_ALIGN.CENTER)
    _footer(s, 6)
    print("  S6 Heuristics")


def s7_result(prs):
    s = _blank(prs)
    # Wide red header with the claim
    _rect(s, 0, 0, SW, Inches(0.82), SFU_RED)
    _logo(s)
    _txt(s, "KEY RESULT",
         MARGIN, Inches(0.04), Inches(3.5), Inches(0.36),
         size=13, bold=True, color=RGBColor(0xFF,0xCC,0xCC))
    _txt(s, "h₂ (Slippage Heuristic)  ·  29% fewer node expansions  ·  same profit quality",
         MARGIN, Inches(0.40), SW-MARGIN*2-Inches(2.4), Inches(0.38),
         size=22, bold=True, color=WHITE)

    fig01 = FIGS / "fig01_node_expansion_bar.png"
    if fig01.exists():
        ar = _img_ar(fig01)
        h = Inches(5.4)
        _pic(s, fig01, (SW - Inches(h.inches * ar)) / 2, Inches(0.87), width=Inches(h.inches * ar))
    _footer(s, 7)
    print("  S7 Result")


def s8_proof(prs):
    s = _blank(prs)
    _header(s, "Real-World Proof — 7,200 Live Searches · 8 Hours · Live Market Data"); _logo(s)

    fig10 = FIGS / "fig10_overnight_timeseries.png"
    fig09 = FIGS / "fig09_quote_staleness.png"

    half_h_in = (SH - HDR_H - FTR_H - Inches(0.18) - Inches(0.1)) / 2 / 914400  # inches as float

    # Top: overnight timeseries
    if fig10.exists():
        ar = _img_ar(fig10)
        iw = Inches(min(10.0, half_h_in * ar))
        _pic(s, fig10, MARGIN, CONTENT_Y+Inches(0.05), width=iw)
    # Top-right stat callout
    _txt(s, "100%\nof searches found\na profitable path",
         SW-Inches(2.6), CONTENT_Y+Inches(0.2), Inches(2.3), Inches(1.2),
         size=14, bold=True, color=SFU_RED, align=PP_ALIGN.CENTER)

    # Divider
    mid_y = CONTENT_Y + Inches(half_h_in + 0.08)
    _divider(s, mid_y, color=RGBColor(0xDD,0xDD,0xDD))

    # Bottom: staleness curve
    if fig09.exists():
        ar = _img_ar(fig09)
        iw = Inches(min(10.0, half_h_in * ar))
        _pic(s, fig09, MARGIN, mid_y+Inches(0.1), width=iw)
    # Bottom-right stat callout
    _txt(s, "99.6%\nstill profitable\nat +2 minutes",
         SW-Inches(2.6), mid_y+Inches(0.3), Inches(2.3), Inches(1.1),
         size=14, bold=True, color=SFU_RED, align=PP_ALIGN.CENTER)
    _txt(s, "→ Act within 120 seconds",
         SW-Inches(2.6), mid_y+Inches(1.5), Inches(2.3), Inches(0.5),
         size=13, bold=True, italic=True, color=DARK, align=PP_ALIGN.CENTER)

    _footer(s, 8)
    print("  S8 Real-World Proof")


def s9_close(prs):
    s = _blank(prs)
    fg = FIGS / "FullGraph.png"
    if fg.exists(): _pic(s, fg, 0, 0, width=SW, height=SH)
    _dark_overlay(s, 78)
    _rect(s, 0, 0, Inches(0.22), SH, SFU_RED)

    _txt(s, "Less Exploration.", Inches(0.55), Inches(1.0),
         Inches(6.5), Inches(1.1), size=52, bold=True, color=WHITE)
    _txt(s, "More Execution.",   Inches(0.55), Inches(2.1),
         Inches(6.5), Inches(1.1), size=52, bold=True, color=SFU_RED)
    _txt(s, "Same Profit.",      Inches(0.55), Inches(3.2),
         Inches(6.5), Inches(1.1), size=52, bold=True, color=WHITE)
    _txt(s, "Thank you  ·  Questions?",
         Inches(0.55), Inches(4.5), Inches(6.5), Inches(0.6),
         size=22, italic=True, color=RGBColor(0xFF,0xCC,0xCC))
    _txt(s, "github.com/kevinl03/Stablecoin-CrossExchange-Arbitrage",
         Inches(0.55), Inches(5.2), Inches(7.0), Inches(0.45),
         size=13, color=RGBColor(0xAA,0xAA,0xAA))

    # Radar summary (right side)
    fig18 = FIGS / "fig18_radar_summary.png"
    if fig18.exists():
        rw = Inches(5.4)
        _pic(s, fig18, SW-rw-Inches(0.4), Inches(0.6), width=rw)
        _txt(s, "Method comparison — all metrics",
             SW-Inches(5.6), Inches(0.3), Inches(5.4), Inches(0.35),
             size=11, italic=True, color=RGBColor(0xAA,0xAA,0xAA),
             align=PP_ALIGN.CENTER)
    _logo(s); _footer(s, 9)
    print("  S9 Close")


# ── MAIN ───────────────────────────────────────────────────────────────────────

def build():
    print("step 1/3 — generating visuals …")
    market   = gen_market()
    pipeline = gen_pipeline()
    slippage = gen_slippage()

    print("step 2/3 — building slides …")
    prs = _prs()
    s1_title(prs)
    s2_market(prs, market)
    s3_problem(prs)
    s4_dataset(prs)
    s5_method(prs, pipeline)
    s6_heuristics(prs, slippage)
    s7_result(prs)
    s8_proof(prs)
    s9_close(prs)

    print("step 3/3 — saving …")
    prs.save(str(OUT))
    print(f"\n  → {OUT}  ({OUT.stat().st_size/1e6:.2f} MB)")


if __name__ == "__main__":
    build()
