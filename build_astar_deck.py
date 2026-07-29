"""
Generates `astar_arbitrage_deck.pptx` — a presentation deck explaining how
A* search finds cross-exchange stablecoin arbitrage opportunities.

Slides cover:
  1. Title
  2. What are cryptocurrencies & blockchain execution
  3. What are stablecoins & how they're pegged to fiat
  4. Cross-exchange price differences = arbitrage opportunity
  5. Modelling the problem as a graph
  6. Dijkstra: f(n) = g(n)
  7-9. A* step-by-step frames from the animated demo
  10. The heuristic: slippage from L2 order books
  11. Results / summary

Run: python build_astar_deck.py
Requires: python-pptx, Pillow, matplotlib, numpy, networkx
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ─── Theme (from gss slides filled with script.pptx) ─────────────────────────

NAVY = RGBColor(0x17, 0x34, 0x82)
SKY = RGBColor(0xB6, 0xE3, 0xEE)
MINT = RGBColor(0xEA, 0xF8, 0xF2)
PERIWINKLE = RGBColor(0x64, 0x89, 0xE7)
CARD_GRAY = RGBColor(0xEE, 0xEE, 0xEE)
DARK = RGBColor(0x00, 0x00, 0x00)
MUTED = RGBColor(0x59, 0x59, 0x59)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GOLD = RGBColor(0xF6, 0xC3, 0x44)
RED = RGBColor(0xD3, 0x2F, 0x2F)

NAVY_HEX = "#173482"
SKY_HEX = "#B6E3EE"
MINT_HEX = "#EAF8F2"
FONT = "Helvetica Neue"

SLIDE_W = Inches(10)
SLIDE_H = Inches(5.625)

# ─── Ensure the A* frames exist ──────────────────────────────────────────────

FRAMES_DIR = os.path.join(os.path.dirname(__file__), "docs", "figures", "astar_frames")
if not os.path.exists(FRAMES_DIR):
    print("ERROR: Run 'python scripts/animate_astar_search.py' first to generate frames.")
    sys.exit(1)

# ─── Presentation setup ──────────────────────────────────────────────────────

prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H
BLANK = prs.slide_layouts[6]


def add_slide():
    return prs.slides.add_slide(BLANK)


def set_bg(slide, color=WHITE):
    bg = slide.background
    bg.fill.solid()
    bg.fill.fore_color.rgb = color


def textbox(slide, left, top, width, height, text, size=18, color=DARK, bold=False,
            align=PP_ALIGN.LEFT, italic=False):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    lines = text.split("\n")
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        p.alignment = align
        for run in p.runs:
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.italic = italic
            run.font.name = FONT
            run.font.color.rgb = color
    return box


def accent_bar(slide, color=NAVY):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W, Inches(0.12))
    bar.fill.solid()
    bar.fill.fore_color.rgb = color
    bar.line.fill.background()
    bar.shadow.inherit = False


def slide_title(slide, title, subtitle=None):
    accent_bar(slide)
    textbox(slide, Inches(0.5), Inches(0.28), Inches(9), Inches(0.7), title,
            size=28, color=NAVY, bold=True)
    if subtitle:
        textbox(slide, Inches(0.5), Inches(0.82), Inches(9), Inches(0.45), subtitle,
                size=14, color=MUTED, italic=True)


def bullets(slide, left, top, width, height, items, size=15, color=DARK):
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = f"\u2022  {item}"
        p.space_after = Pt(8)
        for r in p.runs:
            r.font.size = Pt(size)
            r.font.name = FONT
            r.font.color.rgb = color


def card(slide, left, top, width, height, fill=CARD_GRAY):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def centered_picture(slide, path, top, max_width=Inches(9.0), max_height=Inches(3.8)):
    from PIL import Image
    with Image.open(path) as im:
        iw, ih = im.size
    aspect = iw / ih
    width = max_width
    height = Emu(int(width / aspect))
    if height > max_height:
        height = max_height
        width = Emu(int(height * aspect))
    left = Emu(int((SLIDE_W - width) / 2))
    slide.shapes.add_picture(path, left, top, width=width, height=height)


def page_number(slide, n):
    textbox(slide, SLIDE_W - Inches(0.7), SLIDE_H - Inches(0.35), Inches(0.5), Inches(0.3),
            str(n), size=10, color=MUTED, align=PP_ALIGN.RIGHT)


# =====================================================================
# SLIDE 1 — Title
# =====================================================================
s = add_slide()
set_bg(s, NAVY)
textbox(s, Inches(0.7), Inches(1.5), Inches(8.6), Inches(1.1),
        "Cross-Exchange Stablecoin Arbitrage", size=34, color=WHITE, bold=True)
textbox(s, Inches(0.7), Inches(2.5), Inches(8.6), Inches(0.6),
        "Finding profitable paths with A* search on L2 order book data", size=16,
        color=SKY, italic=True)
textbox(s, Inches(0.7), Inches(4.9), Inches(8.6), Inches(0.5),
        "Algorithm Demo \u2022 Kevin Litvin", size=12, color=SKY)
page_number(s, 1)

# =====================================================================
# SLIDE 2 — What is Crypto? (visual-heavy)
# =====================================================================
s = add_slide(); set_bg(s)
slide_title(s, "What are Cryptocurrencies?")
# Three cards across the slide — minimal text
cw, ch, gap = Inches(2.9), Inches(3.0), Inches(0.2)
left0 = Inches(0.45); top0 = Inches(1.35)

card(s, left0, top0, cw, ch, fill=MINT)
textbox(s, left0 + Inches(0.15), top0 + Inches(0.15), cw - Inches(0.3), ch - Inches(0.3),
        "Digital Assets\n\n"
        "Tokens on a distributed\n"
        "ledger \u2014 no bank needed.\n\n"
        "Traded 24/7 globally.",
        size=13, color=DARK)

card(s, left0 + cw + gap, top0, cw, ch, fill=SKY)
textbox(s, left0 + cw + gap + Inches(0.15), top0 + Inches(0.15), cw - Inches(0.3), ch - Inches(0.3),
        "Blockchain Execution\n\n"
        "1. Sign TX with private key\n"
        "2. Broadcast to network\n"
        "3. Validator adds to block\n"
        "4. Confirmed \u2014 immutable",
        size=13, color=DARK)

card(s, left0 + 2*(cw + gap), top0, cw, ch, fill=NAVY)
textbox(s, left0 + 2*(cw + gap) + Inches(0.15), top0 + Inches(0.15), cw - Inches(0.3), ch - Inches(0.3),
        "Exchanges\n\n"
        "Binance, Kraken, Bybit,\n"
        "Coinbase, OKX, Gate.io\n\n"
        "Each runs its own\norder book independently.",
        size=13, color=WHITE)

textbox(s, Inches(0.5), Inches(4.6), Inches(9.0), Inches(0.5),
        "Key insight: same asset can have different prices on different exchanges",
        size=13, color=MUTED, italic=True, align=PP_ALIGN.CENTER)
page_number(s, 2)

# =====================================================================
# SLIDE 3 — What are Stablecoins? (visual)
# =====================================================================
s = add_slide(); set_bg(s)
slide_title(s, "Stablecoins: The \u201CCash\u201D of Crypto")
# Left: 3 bullet points only
bullets(s, Inches(0.6), Inches(1.3), Inches(4.8), Inches(2.0), [
    "Crypto tokens pegged to $1.00 USD",
    "Backed by real reserves (cash, treasuries)",
    "Multiple issuers \u2192 multiple prices",
], size=15)
# Right: stablecoin price cards (large, visual)
card_w, card_h = Inches(4.2), Inches(0.75)
card_left = Inches(5.5)
coins_data = [
    ("USDT  (Tether)", "$1.0001", GOLD),
    ("USDC  (Circle)", "$0.9999", SKY),
    ("DAI    (Maker)", "$0.9997", MINT),
    ("FDUSD (Binance)", "$0.9988", CARD_GRAY),
]
for i, (name, price, fill) in enumerate(coins_data):
    t = Inches(1.3) + Inches(i * 0.95)
    card(s, card_left, t, card_w, Inches(0.7), fill=fill)
    textbox(s, card_left + Inches(0.2), t + Inches(0.1), Inches(2.8), Inches(0.5),
            name, size=13, color=DARK, bold=True)
    textbox(s, card_left + Inches(3.0), t + Inches(0.1), Inches(1.0), Inches(0.5),
            price, size=14, color=NAVY, bold=True)

textbox(s, Inches(0.5), Inches(4.7), Inches(9.0), Inches(0.5),
        "These tiny deviations from $1.00 across exchanges = our arbitrage signal",
        size=13, color=MUTED, italic=True, align=PP_ALIGN.CENTER)
page_number(s, 3)

# =====================================================================
# SLIDE 4 — How Stablecoins Stay Pegged
# =====================================================================
s = add_slide(); set_bg(s)
slide_title(s, "How Do They Stay at $1.00?", "Three pegging mechanisms")
cw, ch, gap = Inches(2.9), Inches(2.8), Inches(0.2)
left0 = Inches(0.45); top0 = Inches(1.4)

card(s, left0, top0, cw, ch, fill=MINT)
textbox(s, left0 + Inches(0.15), top0 + Inches(0.1), cw - Inches(0.3), ch - Inches(0.2),
        "Fiat-Backed\n(USDT, USDC)\n\n"
        "1:1 reserve of USD in\n"
        "bank accounts + T-bills.\n"
        "Redeem anytime for $1.",
        size=12, color=DARK)

card(s, left0 + cw + gap, top0, cw, ch, fill=SKY)
textbox(s, left0 + cw + gap + Inches(0.15), top0 + Inches(0.1), cw - Inches(0.3), ch - Inches(0.2),
        "Over-Collateralized\n(DAI)\n\n"
        "Lock $1.50 of ETH to\n"
        "mint $1.00 of DAI.\n"
        "Auto-liquidates if\n"
        "collateral drops.",
        size=12, color=DARK)

card(s, left0 + 2*(cw + gap), top0, cw, ch, fill=NAVY)
textbox(s, left0 + 2*(cw + gap) + Inches(0.15), top0 + Inches(0.1), cw - Inches(0.3), ch - Inches(0.2),
        "Algorithmic\n(historical)\n\n"
        "Expand/contract supply\n"
        "to maintain peg.\n"
        "High risk \u2014 UST\n"
        "collapsed in 2022.",
        size=12, color=WHITE)
page_number(s, 4)

# =====================================================================
# SLIDE 5 — The Arbitrage Opportunity (less text, more visual)
# =====================================================================
s = add_slide(); set_bg(s)
slide_title(s, "The Arbitrage Opportunity")
# Large visual: price comparison
card(s, Inches(0.5), Inches(1.3), Inches(4.2), Inches(1.5), fill=MINT)
textbox(s, Inches(0.7), Inches(1.4), Inches(3.8), Inches(1.3),
        "Kraken\nUSDC = $0.99990\n(cheap)", size=16, color=DARK, bold=True)

card(s, Inches(5.3), Inches(1.3), Inches(4.2), Inches(1.5), fill=SKY)
textbox(s, Inches(5.5), Inches(1.4), Inches(3.8), Inches(1.3),
        "Binance\nUSDC = $1.00013\n(expensive)", size=16, color=DARK, bold=True)

# Arrow between them
textbox(s, Inches(4.2), Inches(1.7), Inches(1.5), Inches(0.5),
        "\u2192", size=36, color=NAVY, bold=True, align=PP_ALIGN.CENTER)

# Bottom: the trade
card(s, Inches(1.5), Inches(3.2), Inches(7.0), Inches(1.0), fill=NAVY)
textbox(s, Inches(1.7), Inches(3.3), Inches(6.6), Inches(0.8),
        "Buy on Kraken  \u2192  Transfer  \u2192  Sell on Binance  =  +2.3 bps profit",
        size=16, color=WHITE, bold=True, align=PP_ALIGN.CENTER)

textbox(s, Inches(0.5), Inches(4.5), Inches(9.0), Inches(0.7),
        "But: fees + slippage + transfer time can eat the profit.\n"
        "With 5 exchanges \u00D7 4 coins = 20 nodes, 40+ edges \u2014 need an algorithm.",
        size=12, color=MUTED, italic=True, align=PP_ALIGN.CENTER)
page_number(s, 5)

# =====================================================================
# SLIDE 6 — Modelling as a Graph (image-heavy)
# =====================================================================
s = add_slide(); set_bg(s)
slide_title(s, "Model: Weighted Directed Graph")
# Minimal text on left
bullets(s, Inches(0.4), Inches(1.2), Inches(3.5), Inches(3.5), [
    "Node = (exchange, coin)",
    "Trade edge: swap coins\n  on same exchange",
    "Transfer edge: move coin\n  between exchanges",
    "Edge weight = fee in bps",
    "Goal: find lowest-cost\n  cycle back to start",
], size=12)
# Large graph frame on right
frame_path = os.path.join(FRAMES_DIR, "frame_00_step01.png")
if os.path.exists(frame_path):
    s.shapes.add_picture(frame_path, Inches(3.8), Inches(1.1), width=Inches(6.0))
page_number(s, 6)

# =====================================================================
# SLIDE 7 — Dijkstra: f(n) = g(n)
# =====================================================================
s = add_slide(); set_bg(s)
slide_title(s, "Dijkstra: f(n) = g(n)")
textbox(s, Inches(0.6), Inches(1.3), Inches(9.0), Inches(0.6),
        "Expand the node with the lowest accumulated cost so far", size=15, color=DARK)
textbox(s, Inches(3.0), Inches(2.0), Inches(4.0), Inches(0.6),
        "f(n) = g(n)", size=28, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
# Two-column: pros and cons
card(s, Inches(0.5), Inches(2.9), Inches(4.3), Inches(2.0), fill=MINT)
textbox(s, Inches(0.7), Inches(3.0), Inches(3.9), Inches(1.8),
        "\u2713  Guaranteed optimal\n\u2713  Simple to implement\n\u2713  No domain knowledge needed",
        size=14, color=DARK)
card(s, Inches(5.2), Inches(2.9), Inches(4.3), Inches(2.0), fill=RGBColor(0xFF, 0xEB, 0xEE))
textbox(s, Inches(5.4), Inches(3.0), Inches(3.9), Inches(1.8),
        "\u2717  Explores blindly\n\u2717  Ignores slippage risk\n\u2717  Ignores transfer time\n\u2717  Wastes time on thin books",
        size=14, color=DARK)
page_number(s, 7)

# =====================================================================
# SLIDE 8 — A*: f(n) = g(n) + h(n)
# =====================================================================
s = add_slide(); set_bg(s)
slide_title(s, "A*: f(n) = g(n) + h(n)")
textbox(s, Inches(0.6), Inches(1.3), Inches(9.0), Inches(0.6),
        "Add a heuristic that looks ahead at execution quality", size=15, color=DARK)
textbox(s, Inches(2.5), Inches(2.0), Inches(5.0), Inches(0.6),
        "f(n) = g(n) + h(n)", size=28, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
# h(n) breakdown
card(s, Inches(0.5), Inches(2.9), Inches(9.0), Inches(2.2), fill=CARD_GRAY)
textbox(s, Inches(0.8), Inches(3.0), Inches(8.4), Inches(2.0),
        "h(n) = slippage(L2 order book) + \u03C3 \u00B7 \u221A(\u0394t)\n\n"
        "  Slippage:   Walk the ask side for our trade size. Thin book = high cost.\n"
        "  Time risk:  Stablecoin vol (~1.5 bps/min) \u00D7 transfer duration.\n\n"
        "  Deep book + fast transfer \u2192 low h \u2192 A* explores that path first.",
        size=13, color=DARK)
page_number(s, 8)

# =====================================================================
# SLIDES 9-13 — A* Step-by-Step (FULL SLIDE frames)
# =====================================================================
frame_files = sorted(f for f in os.listdir(FRAMES_DIR) if f.endswith(".png"))
# Pick 5 frames: start, early, mid, late, final
if len(frame_files) >= 5:
    pick_indices = [0, 2, len(frame_files)//2, -2, -1]
    demo_frames = [frame_files[i] for i in pick_indices]
else:
    demo_frames = frame_files

step_descriptions = [
    ("A* Step 1: Start Node",
     "Begin at Binance:USDT. Orange = edges just pushed to priority queue."),
    ("A* Step 3: Expanding Neighbors",
     "Cheap, low-slippage paths explored first. Fee labels (bps) on each edge."),
    ("A* Mid-Search",
     "Bybit and Kraken reached. High time-risk paths to OKX deprioritized."),
    ("A* Nearing Completion",
     "Most nodes expanded. Searching for profitable return path to start."),
    ("A* Final: Cycle Found",
     "Red = profitable arbitrage cycle. Total cost shown in info panel."),
]

for i, (fname, (title, desc)) in enumerate(zip(demo_frames, step_descriptions)):
    s = add_slide(); set_bg(s)
    # Minimal title bar — give maximum space to the image
    accent_bar(s)
    textbox(s, Inches(0.3), Inches(0.18), Inches(6.0), Inches(0.5), title,
            size=18, color=NAVY, bold=True)
    textbox(s, Inches(0.3), Inches(0.55), Inches(9.0), Inches(0.35), desc,
            size=11, color=MUTED, italic=True)
    # Full-width frame image
    frame_path = os.path.join(FRAMES_DIR, fname)
    centered_picture(s, frame_path, Inches(0.95), max_width=Inches(9.5), max_height=Inches(4.5))
    page_number(s, 9 + i)

# =====================================================================
# SLIDE 14 — L2 Order Book
# =====================================================================
s = add_slide(); set_bg(s)
slide_title(s, "The L2 Order Book \u2192 Slippage Heuristic")
# Minimal bullets left
bullets(s, Inches(0.5), Inches(1.2), Inches(4.0), Inches(3.5), [
    "20 price levels of depth",
    "Walk asks for our trade size",
    "Binance: ~0 bps slippage\n  (millions of units at top)",
    "Gate.io: ~0.5 bps slippage\n  (only 6K at top level)",
    "Thin book = high h(n)\n  = A* avoids it",
], size=12)
ob_fig_path = os.path.join("docs", "figures", "astar_arbitrage_demo.png")
if os.path.exists(ob_fig_path):
    s.shapes.add_picture(ob_fig_path, Inches(4.2), Inches(1.1), width=Inches(5.6))
page_number(s, 14)

# =====================================================================
# SLIDE 15 — Summary
# =====================================================================
s = add_slide(); set_bg(s)
slide_title(s, "Summary")
bullets(s, Inches(0.6), Inches(1.3), Inches(9.0), Inches(3.0), [
    "Stablecoins = crypto pegged to $1 \u2014 tiny cross-exchange price gaps exist",
    "Model as a graph \u2192 arbitrage = finding a profitable cycle",
    "A* + slippage heuristic guides search toward deep, fast routes",
    "Same optimality as Dijkstra, but focused exploration",
], size=16)
textbox(s, Inches(0.6), Inches(4.0), Inches(9.0), Inches(0.8),
        "Code: scripts/animate_astar_search.py\nUI: streamlit run scripts/ui.py",
        size=12, color=MUTED, italic=True)
page_number(s, 15)

# =====================================================================
# Save
# =====================================================================
output_path = "astar_arbitrage_deck.pptx"
prs.save(output_path)
print(f"Done \u2192 {output_path}  ({len(prs.slides)} slides)")
