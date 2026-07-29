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
# SLIDE 2 — What are Cryptocurrencies?
# =====================================================================
s = add_slide(); set_bg(s)
slide_title(s, "What are Cryptocurrencies?", "Digital assets that live on a blockchain")
bullets(s, Inches(0.6), Inches(1.4), Inches(5.5), Inches(3.8), [
    "Digital tokens stored on a distributed ledger (blockchain)",
    "Transactions are verified by a network of computers, not a bank",
    "Each transaction is signed cryptographically with your private key",
    "Once confirmed in a block, it\u2019s immutable \u2014 can\u2019t be reversed",
    "Anyone can run a node and verify the entire history",
    "Traded 24/7 on centralized exchanges (Binance, Kraken, etc.)\nand decentralized exchanges (Uniswap, etc.)",
], size=14)
# Right side: simple blockchain diagram
card(s, Inches(6.2), Inches(1.5), Inches(3.5), Inches(3.5), fill=MINT)
textbox(s, Inches(6.4), Inches(1.6), Inches(3.1), Inches(3.3),
        "How a transaction executes:\n\n"
        "1\uFE0F\u20E3  You sign a TX with your key\n\n"
        "2\uFE0F\u20E3  TX broadcast to the network\n\n"
        "3\uFE0F\u20E3  Miners/validators include it\n     in the next block\n\n"
        "4\uFE0F\u20E3  Block gets confirmed \u2014 done",
        size=11, color=DARK)
page_number(s, 2)

# =====================================================================
# SLIDE 3 — What are Stablecoins?
# =====================================================================
s = add_slide(); set_bg(s)
slide_title(s, "What are Stablecoins?", "Crypto tokens pegged to fiat currency (usually $1 USD)")
bullets(s, Inches(0.6), Inches(1.4), Inches(5.5), Inches(3.8), [
    "Designed to always be worth ~$1.00 USD",
    "Backed by reserves: cash, treasuries, or algorithmic mechanisms",
    "Used as the \u201Ccash\u201D of crypto \u2014 traders park profits here",
    "Multiple competing stablecoins: USDT, USDC, DAI, FDUSD",
    "Each trades on many exchanges independently",
    "Price can deviate slightly from $1.00 per exchange\n\u2192 this is where arbitrage lives",
], size=14)
# Right cards showing stablecoins
card(s, Inches(6.2), Inches(1.5), Inches(3.5), Inches(1.0), fill=SKY)
textbox(s, Inches(6.4), Inches(1.6), Inches(3.1), Inches(0.8),
        "USDT (Tether) \u2014 $1.0001\nBacked by cash + treasuries", size=11, color=DARK)
card(s, Inches(6.2), Inches(2.7), Inches(3.5), Inches(1.0), fill=SKY)
textbox(s, Inches(6.4), Inches(2.8), Inches(3.1), Inches(0.8),
        "USDC (Circle) \u2014 $0.9999\nBacked by cash + short-term bonds", size=11, color=DARK)
card(s, Inches(6.2), Inches(3.9), Inches(3.5), Inches(1.0), fill=SKY)
textbox(s, Inches(6.4), Inches(4.0), Inches(3.1), Inches(0.8),
        "DAI (MakerDAO) \u2014 $0.9997\nAlgorithmic + over-collateralized", size=11, color=DARK)
page_number(s, 3)

# =====================================================================
# SLIDE 4 — The Arbitrage Opportunity
# =====================================================================
s = add_slide(); set_bg(s)
slide_title(s, "The Arbitrage Opportunity",
            "Same coin, different exchanges, different prices \u2192 profit")
bullets(s, Inches(0.6), Inches(1.4), Inches(9.0), Inches(3.8), [
    "USDC on Binance: $1.00013   |   USDC on Kraken: $0.99990",
    "Spread = 2.3 basis points (bps) \u2014 small but real with volume",
    "Buy cheap on Kraken \u2192 transfer to Binance \u2192 sell high",
    "Must account for: trading fees, withdrawal fees, transfer time, slippage",
    "Question: with 5 exchanges \u00D7 4 stablecoins = 20+ nodes and 40+ edges,\n"
    "how do we find the cheapest profitable cycle?",
    "Answer: model it as a graph problem and use path-finding algorithms",
], size=14)
page_number(s, 4)

# =====================================================================
# SLIDE 5 — Modelling as a Graph
# =====================================================================
s = add_slide(); set_bg(s)
slide_title(s, "Modelling as a Weighted Directed Graph",
            "Nodes = (exchange, coin) pairs    Edges = trades or transfers")
bullets(s, Inches(0.6), Inches(1.4), Inches(4.5), Inches(3.8), [
    "Node: a stablecoin sitting on a specific exchange",
    "Trade edge (intra-exchange):\n  same exchange, swap USDT\u2192USDC\n  cost = taker fee (0.8-2.5 bps)",
    "Transfer edge (cross-exchange):\n  same coin, move between exchanges\n  cost = withdrawal fee + gas",
    "Goal: find a cycle starting and ending\n  at the same node with net profit > 0",
], size=13)
# Show a frame from the animation as the graph example
frame_path = os.path.join(FRAMES_DIR, "frame_00_step01.png")
if os.path.exists(frame_path):
    slide_pic = s.shapes.add_picture(frame_path, Inches(5.2), Inches(1.3),
                                      width=Inches(4.5))
page_number(s, 5)

# =====================================================================
# SLIDE 6 — Dijkstra: f(n) = g(n)
# =====================================================================
s = add_slide(); set_bg(s)
slide_title(s, "Baseline: Dijkstra\u2019s Algorithm",
            "f(n) = g(n) \u2014 expand nodes by lowest accumulated cost")
bullets(s, Inches(0.6), Inches(1.4), Inches(9.0), Inches(1.8), [
    "g(n) = total fees paid to reach node n from start",
    "Always picks the cheapest-so-far node to expand next",
    "Guaranteed optimal but explores blindly in all directions",
    "Doesn\u2019t know that a 300-second transfer will expose us to price risk",
], size=14)
# Equation
textbox(s, Inches(3.0), Inches(3.5), Inches(4.0), Inches(0.5),
        "f(n) = g(n)", size=24, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
textbox(s, Inches(1.5), Inches(4.1), Inches(7.0), Inches(1.0),
        "Problem: Dijkstra treats a 0.3bp fee edge to OKX (5-min transfer, thin book)\n"
        "the same as a 0.3bp fee edge to Bybit (45-sec transfer, deep book)",
        size=12, color=MUTED, italic=True, align=PP_ALIGN.CENTER)
page_number(s, 6)

# =====================================================================
# SLIDE 7 — A* Search: f(n) = g(n) + h(n)
# =====================================================================
s = add_slide(); set_bg(s)
slide_title(s, "A* Search: f(n) = g(n) + h(n)",
            "Add a heuristic that estimates slippage + time-decay risk")
bullets(s, Inches(0.6), Inches(1.4), Inches(9.0), Inches(1.5), [
    "h(n) = estimated future cost from L2 order book slippage + volatility exposure",
    "A* expands the node with lowest f = actual cost so far + estimated cost ahead",
    "Prioritizes paths through deep-liquidity exchanges, avoids thin books",
], size=14)
textbox(s, Inches(2.0), Inches(3.2), Inches(6.0), Inches(0.5),
        "f(n) = g(n) + h(n)", size=24, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
textbox(s, Inches(0.6), Inches(3.9), Inches(9.0), Inches(1.2),
        "h(n) = slippage(L2 book, trade_size) + \u03C3 \u00B7 \u221A(\u0394t)\n\n"
        "Slippage: walk the ask side of the order book for our trade size\n"
        "Time risk: stablecoin volatility (\u223C1.5 bps/min) \u00D7 transfer duration",
        size=12, color=MUTED)
page_number(s, 7)

# =====================================================================
# SLIDES 8-10 — A* Step-by-Step (key frames)
# =====================================================================
frame_files = sorted(f for f in os.listdir(FRAMES_DIR) if f.endswith(".png"))
# Pick 3 representative frames: start, middle, end (cycle found)
demo_frames = []
if len(frame_files) >= 3:
    demo_frames = [frame_files[0], frame_files[len(frame_files)//2], frame_files[-1]]
elif frame_files:
    demo_frames = frame_files[:3]

step_descriptions = [
    ("Step 1: Start at Binance:USDT",
     "A* begins at our starting node. Orange edges show all neighbors being pushed to the priority queue with their f(n) values."),
    ("Mid-Search: Expanding Through the Graph",
     "A* has explored the cheap, low-slippage paths first (Binance\u2192Bybit). High time-risk transfers to OKX/Gate.io are deprioritized by h(n)."),
    ("Final: Profitable Cycle Discovered",
     "Red path = the cycle with lowest total real cost. The heuristic guided the search away from thin-book exchanges."),
]

for i, (fname, (title, desc)) in enumerate(zip(demo_frames, step_descriptions)):
    s = add_slide(); set_bg(s)
    slide_title(s, title, desc)
    frame_path = os.path.join(FRAMES_DIR, fname)
    centered_picture(s, frame_path, Inches(1.4), max_width=Inches(7.5), max_height=Inches(3.9))
    page_number(s, 8 + i)

# =====================================================================
# SLIDE 11 — The L2 Order Book & Slippage
# =====================================================================
s = add_slide(); set_bg(s)
slide_title(s, "The Heuristic: L2 Order Book Slippage",
            "How h(n) estimates execution cost before we actually trade")
bullets(s, Inches(0.6), Inches(1.4), Inches(5.0), Inches(3.8), [
    "Every exchange provides Level 2 (L2) data:\n  20 levels of bids and asks with quantities",
    "For a $50K trade, we walk the ask levels:\n  Level 1: 236K units @ 1.00013\n  Level 2: 766K units @ 1.00014\n  \u2192 our order fills entirely at level 1",
    "Slippage = avg fill price \u2212 best ask\n  Binance: ~0.00 bps (deep)\n  Gate.io: ~0.47 bps (thin)",
    "Thin books \u2192 large h(n) \u2192 A* avoids them",
], size=12)
# Order book figure
ob_fig_path = os.path.join("docs", "figures", "astar_arbitrage_demo.png")
if os.path.exists(ob_fig_path):
    s.shapes.add_picture(ob_fig_path, Inches(5.3), Inches(1.3), width=Inches(4.5))
page_number(s, 11)

# =====================================================================
# SLIDE 12 — Summary
# =====================================================================
s = add_slide(); set_bg(s)
slide_title(s, "Summary")
bullets(s, Inches(0.6), Inches(1.3), Inches(9.0), Inches(3.8), [
    "Stablecoins trade at slightly different prices across exchanges",
    "We model the cross-exchange landscape as a weighted directed graph",
    "A* with an L2-slippage heuristic finds profitable cycles faster than blind search",
    "The heuristic is admissible: slippage + time-volatility never overestimates",
    "Result: same optimal path as Dijkstra, but guided toward deep-liquidity routes",
], size=15)
textbox(s, Inches(0.6), Inches(4.3), Inches(9.0), Inches(0.8),
        "Code: scripts/animate_astar_search.py    |    UI: streamlit run scripts/ui.py",
        size=12, color=MUTED, italic=True)
page_number(s, 12)

# =====================================================================
# Save
# =====================================================================
output_path = "astar_arbitrage_deck.pptx"
prs.save(output_path)
print(f"Done \u2192 {output_path}  ({len(prs.slides)} slides)")
