"""
Fill the Canadian AI 2026 poster template (CdnAI2026_poster_landscape_36x24.pptx)
with paper content and embed key figures.

3-column "Three-Column Flow" layout:
  Col 1 (Left):   Context & Motivation  /  Four Execution Challenges
  Col 2 (Centre): Technical Core — graph model, heuristics, equations, profitable-path diagram
  Col 3 (Right):  Results & The "Win"  /  Scaling & Future Work

Page size: 36 × 24 inches (landscape, EMU 32 918 400 × 21 945 600).

Run from the repo root:
    python3 docs/latex/StablecoinArbitrage_GSS2026/poster/fill_poster.py

Output: docs/latex/StablecoinArbitrage_GSS2026/poster/poster_filled.pptx
"""
from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[0]
SRC  = ROOT / "CdnAI2026_poster_landscape_36x24.pptx"
DST  = ROOT / "poster_filled.pptx"
WORK = Path("/tmp/cdnai_poster_fill")

# Figures live in CAIAC2026/figures (GSS2026/figures is a symlink there).
FIGS = ROOT.parents[1] / "StablecoinArbitrage_CAIAC2026" / "figures"
EQ_TMP = Path("/tmp/cdnai_poster_equations")   # rendered equation PNGs

# Slide canvas: 36 × 24 inches.  1 inch = 914 400 EMU.
SLIDE_W = 36 * 914_400   # 32 918 400
SLIDE_H = 24 * 914_400   # 21 945 600

# SFU red and accent colours for injected text only
# (we do NOT globally replace the template's red to avoid affecting the footer/logos)
SFU_RED = "CC0633"
DARK    = "1A1A2E"
GREY    = "555555"
BLUE    = "0057A8"


# ─────────────────────────────────────────────────────────────────────────────
# Content
# ─────────────────────────────────────────────────────────────────────────────

TITLE   = "Execution-Aware A* Search for Cross-Exchange Stablecoin Arbitrage"
AUTHORS = "Kevin Litvin  —  Simon Fraser University"

SECTION_TITLES = [
    "Context & Motivation",        # top-left
    "Four Execution Challenges",   # bottom-left
    "Results & Impact",            # top-right
    "Scaling & Future Work",       # bottom-right
]

# ── Column 1, top: abstract / motivation ──────────────────────────────────────
COL1_TOP: list[str] = [
    "Cross-exchange stablecoin arbitrage exploits price discrepancies across "
    "centralized exchanges — a $300 B+ market.",
    "Prior work uses negative-cycle detection to find opportunities, but ignores "
    "EXECUTION: fees, slippage, withdrawal delays, and venue reliability.",
    "We shift focus: compute trade-and-transfer paths that remain profitable after "
    "ALL real-world costs are applied.",
    "Stablecoins are ideal: USD-pegged assets with a clean scalar profit objective "
    "across 12 major exchanges and 9 coin symbols.",
    "We model the problem as weighted directed graph search and run 7,200 overnight "
    "search instances comparing A* heuristics vs. Dijkstra.",
    "Code + data: github.com/kevinl03/Stablecoin-CrossExchange-Arbitrage",
]

# ── Column 1, bottom: four execution challenges ───────────────────────────────
COL1_BOT: list[str] = [
    "The shift: from OPPORTUNITY DETECTION to EXECUTION FEASIBILITY.",
    "① LIQUIDITY — Insufficient order-book depth causes partial fills and adverse "
    "price impact at the quoted rate.",
    "② SLIPPAGE — Large orders shift the VWAP above mid-price; the effective rate r(e) "
    "captures this via slippage_bps.",
    "③ LATENCY — Blockchain transfers take minutes to hours; market prices can move "
    "against the open leg while funds are in transit.",
    "④ RELIABILITY — Exchange downtime, withdrawal halts, and API failures can derail "
    "planned routes mid-execution.",
    "Together these factors mean opportunity-detection methods overstate real profit "
    "by up to 40% in live conditions.",
]

# ── Column 2, centre callout: technical core ─────────────────────────────────
CALLOUT_TITLE = "Method: Execution-Aware A* Search"

CALLOUT_BULLETS: list[str] = [
    "GRAPH MODEL — Nodes are (exchange, stablecoin) pairs. Intra-exchange edges are "
    "trades; inter-exchange edges are same-coin cross-venue transfers.",
    "EDGE WEIGHT — w(e) = -log r(e). Effective rate r(e) bundles taker fees, "
    "gas/withdrawal costs, chain-transfer time, and venue-reliability discount.",
    "GOAL — Any node where USD value exceeds the start amount (stablecoins are "
    "USD-pegged: no closed cycle required).",
    "SEARCH — A* with f(n) = g(n) + h(n). Each heuristic is a domain-specific "
    "guidance penalty, not an admissible lower bound.",
]

CALLOUT_HEURISTICS: list[str] = [
    "h\u2081  (Liquidity)    Penalise shallow 24-h order books relative to order size.",
    "h\u2082  (Slippage)  \u2605  NOVEL: prunes high market-impact routes early, preserving "
    "low-impact paths at equal profit.",
    "h\u2083  (Chain)       Chain-congestion time + static venue-reliability penalty.",
]

CALLOUT_TAKEAWAY = (
    "h\u2082 achieves the same profit as Dijkstra with 29% fewer node expansions — "
    "verified across 7,200 overnight instances on a unique CEX stablecoin dataset."
)

# Equations rendered as PNG (see render_equations()); text here is only for
# matplotlib mathtext — NOT embedded verbatim.
EQUATION_STRINGS = [
    r"$w(e) = -\log\, r(e)$",
    r"$f(n) = g(n) + h(n)$",
    r"$h_2 = \lambda \cdot \max\!\left(0,\; \mathrm{slippage}_{bps} - \theta\right)$",
]

# ── Column 3, top: results ─────────────────────────────────────────────────────
COL3_TOP: list[str] = [
    "Every A*-based run across 7,200 overnight instances finds a profitable path.",
    "Quote staleness: 99.6% of paths remain profitable up to 120 s of quote delay.",
    "h\u2081 and h\u2083 expand 58-87% MORE nodes and earn 30-33% LESS profit: "
    "aggressive penalties over-steer search.",
]

RESULTS_TABLE_HEADER = "Heuristic    Profit    Expansions  \u0394Exp"
RESULTS_TABLE_ROWS = [
    "Dijkstra     $10.01    359         ---",
    "h\u2082 Slippage  $9.91     256         -29%  \u2605",
    "h\u2081 Liq.      $6.72     568        +58%",
    "h\u2083 Chain     $7.06     673        +87%",
    "Multi-start  $9.88     3\u00d7359       ---",
]

# ── Column 3, bottom: scaling & future work ───────────────────────────────────
COL3_BOT: list[str] = [
    "Graph scaling (4 \u2192 12 exchanges): h\u2082 maintains its expansion advantage at every "
    "graph size — the gap widens as the graph grows.",
    "h\u2082 is robust to order-size variation ($1k \u2013 $100k): the slippage penalty keeps "
    "search focused on liquid, low-impact paths.",
    "Overnight stability: profit stays consistent across 7,200 runs with minimal "
    "variance — the A* framework is stable under live market conditions.",
    "FUTURE: asynchronous order-book pre-fetching to eliminate quote staleness.",
    "FUTURE: extension to DEX/AMM markets (Uniswap, Curve) with continuous "
    "pricing — replacing discrete fee tables with AMM invariants.",
]

FOOTER_LINE_1 = "github.com/kevinl03/Stablecoin-CrossExchange-Arbitrage"
FOOTER_LINE_2 = "Canadian AI 2026  |  GSS Paper  |  Poster: 36 \u00d7 24 in"


# ─────────────────────────────────────────────────────────────────────────────
# Image placements  (absolute slide EMU coordinates)
# ─────────────────────────────────────────────────────────────────────────────
# Column safe-zones (from template XML group transforms):
#   Left col:   x ~  1 200 000, cx ~ 9 200 000, top-y ~ 4 000 000
#   Centre col: x ~ 11 350 000, cx ~ 9 200 000, top-y ~ 4 000 000
#   Right col:  x ~ 22 200 000, cx ~ 9 200 000, top-y ~ 4 000 000
#   Footer bar: y ~ 19 891 689  →  all images must end before y = 19 700 000.
#
# Equation images are added programmatically in build_equation_placements().

def _ar(name: str) -> float:
    """Natural pixel aspect ratio (w/h) from the known table."""
    table = {
        "CameraReadySuccesfulPathProfit.png": 2158 / 1274,
        "fig04_success_rate.png":             2558 / 1553,
        "fig08_graph_scaling_expansions.png": 2119 / 1477,
        "fig01_node_expansion_bar.png":       2119 / 1519,
    }
    return table.get(name, 1.6)


# Aspect-ratio-correct cx for a given cy:
def _cx(name: str, cy: int) -> int:
    return int(cy * _ar(name))


# Aspect-ratio-correct cy for a given cx:
def _cy(name: str, cx: int) -> int:
    return int(cx / _ar(name))


_F = FIGS   # shorthand

IMAGE_PLACEMENTS = [
    # ── Col 1 bottom — success-rate bar (fills whitespace) ────────────────────
    # y=13_500_000 → end 13_500_000+5_575_757=19_075_757 < footer 19_891_689 ✓
    {
        "src": _F / "fig04_success_rate.png",
        "x":  1_200_000, "y": 13_500_000,
        "cx": 9_200_000, "cy": _cy("fig04_success_rate.png", 9_200_000),
        "caption": "Fig. 3 — Success rate and profit by heuristic",
    },
    # ── Col 3 top — node expansion bar chart ──────────────────────────────────
    {
        "src": _F / "fig01_node_expansion_bar.png",
        "x":  22_200_000, "y": 8_700_000,
        "cx":  9_200_000, "cy": 2_500_000,
        "caption": "Fig. 2a — Node expansions per heuristic (cached graph, $10 k order)",
    },
    # ── Col 3 bottom — graph scaling (4 → 12 exchanges) ─────────────────────
    {
        "src": _F / "fig08_graph_scaling_expansions.png",
        "x":  22_200_000, "y": 13_700_000,
        "cx":  9_200_000, "cy": 2_600_000,
        "caption": "Fig. 2b — Expansions vs. graph size (4 → 12 exchanges)",
    },
    # ── Col 2 centre — main visual: the profitable path ───────────────────────
    #   Natural AR 1.69; placed BELOW equations (see y below).
    #   Equations occupy y ≈ 10 700 000 – 13 050 000; path starts at 13 300 000.
    {
        "src": _F / "CameraReadySuccesfulPathProfit.png",
        "x":  11_350_000, "y": 13_500_000,
        "cx":  9_200_000, "cy": _cy("CameraReadySuccesfulPathProfit.png", 9_200_000),
        "caption": "Fig. 1b — Discovered profitable path: Kraken \u2192 KuCoin \u2192 KuCoin (USDT \u2192 TUSD)",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Equation rendering (matplotlib mathtext → transparent PNG)
# ─────────────────────────────────────────────────────────────────────────────

def render_equations() -> list[Path]:
    """Render each equation as a high-DPI PNG with a white background.
    Returns the list of paths in equation order."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    EQ_TMP.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for i, latex in enumerate(EQUATION_STRINGS):
        fig = plt.figure(figsize=(9.5, 0.85))
        fig.patch.set_facecolor("#F2F2F7")   # very light grey box

        # Thin border via a patch
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_axis_off()
        rect = mpatches.FancyBboxPatch(
            (0.005, 0.05), 0.99, 0.90,
            boxstyle="round,pad=0.02",
            linewidth=1.5,
            edgecolor="#CC0633",
            facecolor="#F2F2F7",
            transform=ax.transAxes,
        )
        ax.add_patch(rect)
        ax.text(
            0.5, 0.5, latex,
            transform=ax.transAxes,
            ha="center", va="center",
            fontsize=28, color="#1A1A2E",
        )
        p = EQ_TMP / f"eq{i+1}.png"
        fig.savefig(p, dpi=220, bbox_inches="tight",
                    facecolor="#F2F2F7", edgecolor="none", pad_inches=0.05)
        plt.close(fig)
        paths.append(p)

    return paths


def build_equation_placements(eq_paths: list[Path]) -> list[dict]:
    """Return image-placement dicts for the three equation PNGs in the centre column."""
    placements = []
    x  = 11_350_000
    cy = 820_000          # ≈ 0.9" per equation row
    gap = 100_000
    y0 = 10_600_000       # start just below estimated end of callout text

    for i, p in enumerate(eq_paths):
        y = y0 + i * (cy + gap)
        placements.append({
            "src": p,
            "x": x, "y": y,
            "cx": 9_200_000, "cy": cy,
            "caption": None,
        })
    return placements


# ─────────────────────────────────────────────────────────────────────────────
# XML helpers
# ─────────────────────────────────────────────────────────────────────────────

def xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _run(text: str, sz: int, bold: bool = False, italic: bool = False,
         color: str | None = None, face: str = "Arial") -> str:
    b = ' b="1"' if bold else ""
    i = ' i="1"' if italic else ""
    fill = (
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        if color else
        '<a:solidFill><a:schemeClr val="dk1"/></a:solidFill>'
    )
    return (
        f'<a:r><a:rPr lang="en-US" sz="{sz}"{b}{i} dirty="0">'
        f'{fill}<a:latin typeface="{face}"/>'
        f'</a:rPr><a:t>{xml_escape(text)}</a:t></a:r>'
    )


def make_bullet_para(text: str, sz: int = 2400,
                     bold: bool = False, color: str | None = None) -> str:
    r = _run(text, sz, bold=bold, color=color)
    return (
        '<a:p>'
        '<a:pPr marL="342900" indent="-342900">'
        '<a:buFont typeface="Arial"/><a:buChar char="\u2022"/>'
        '</a:pPr>'
        f'{r}</a:p>'
    )


def make_plain_para(text: str, sz: int = 2400, bold: bool = False,
                    italic: bool = False, align: str = "l",
                    color: str | None = None, face: str = "Arial") -> str:
    algn = f' algn="{align}"' if align != "l" else ""
    r = _run(text, sz, bold=bold, italic=italic, color=color, face=face)
    return f'<a:p><a:pPr{algn}><a:buNone/></a:pPr>{r}</a:p>'


def make_mono_para(text: str, sz: int = 2000, bold: bool = False) -> str:
    return make_plain_para(text, sz=sz, bold=bold, face="Courier New")


def make_spacer(sz: int = 1200) -> str:
    return f'<a:p><a:pPr><a:buNone/></a:pPr><a:endParaRPr sz="{sz}"/></a:p>'


def make_caption_box(text: str, x: int, y: int,
                     cx: int, cy: int, sid: int) -> str:
    t = xml_escape(text)
    return (
        f'<p:sp><p:nvSpPr>'
        f'<p:cNvPr id="{sid}" name="Caption{sid}"/>'
        f'<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr>'
        f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        f'<a:noFill/><a:ln><a:noFill/></a:ln>'
        f'</p:spPr>'
        f'<p:txBody>'
        f'<a:bodyPr wrap="square" anchor="ctr"/><a:lstStyle/>'
        f'<a:p><a:pPr algn="ctr"><a:buNone/></a:pPr>'
        f'<a:r><a:rPr lang="en-US" sz="1700" i="1" dirty="0">'
        f'<a:solidFill><a:srgbClr val="{GREY}"/></a:solidFill>'
        f'<a:latin typeface="Arial"/></a:rPr>'
        f'<a:t>{t}</a:t></a:r></a:p>'
        f'</p:txBody></p:sp>'
    )


def make_label_box(text: str, x: int, y: int,
                   cx: int, cy: int, sid: int,
                   sz: int = 2600, color: str = SFU_RED,
                   border: bool = False) -> str:
    """Floating text box — used for section sub-labels injected as shapes."""
    border_xml = (
        f'<a:ln w="19050">'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill></a:ln>'
        if border else
        '<a:ln><a:noFill/></a:ln>'
    )
    return (
        f'<p:sp><p:nvSpPr>'
        f'<p:cNvPr id="{sid}" name="Label{sid}"/>'
        f'<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr>'
        f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        f'<a:noFill/>{border_xml}'
        f'</p:spPr>'
        f'<p:txBody>'
        f'<a:bodyPr wrap="square" anchor="ctr" anchorCtr="1"/>'
        f'<a:lstStyle/>'
        f'<a:p><a:pPr algn="ctr"><a:buNone/></a:pPr>'
        f'<a:r><a:rPr lang="en-US" sz="{sz}" b="1" dirty="0">'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        f'<a:latin typeface="Arial"/></a:rPr>'
        f'<a:t>{xml_escape(text)}</a:t></a:r></a:p>'
        f'</p:txBody></p:sp>'
    )


def make_pic_xml(rid: str, name: str,
                 x: int, y: int, cx: int, cy: int, sid: int) -> str:
    # No noChangeAspect lock — fillRect stretches the image to fill cx×cy exactly.
    return (
        f'<p:pic><p:nvPicPr>'
        f'<p:cNvPr id="{sid}" name="{name}"/>'
        f'<p:cNvPicPr/>'
        f'<p:nvPr/></p:nvPicPr>'
        f'<p:blipFill><a:blip r:embed="{rid}"/>'
        f'<a:stretch><a:fillRect/></a:stretch></p:blipFill>'
        f'<p:spPr><a:xfrm>'
        f'<a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/>'
        f'</a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>'
        f'</p:pic>'
    )


def replace_first(xml: str, old: str, new: str) -> str:
    if old not in xml:
        raise RuntimeError(f"placeholder not found: {old!r}")
    return xml.replace(old, new, 1)


def replace_first_paragraph(xml: str, inner_text: str, new_paras: str) -> str:
    """Replace the complete <a:p>…</a:p> that contains <a:t>inner_text</a:t>."""
    target = f"<a:t>{inner_text}</a:t>"
    idx = xml.find(target)
    if idx < 0:
        raise RuntimeError(f"paragraph text not found: {inner_text!r}")
    p_open  = xml.rfind("<a:p>", 0, idx)
    p_close = xml.find("</a:p>", idx) + len("</a:p>")
    return xml[:p_open] + new_paras + xml[p_close:]


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def fill() -> None:
    # ── Step 0: pre-render equations ─────────────────────────────────────────
    print("rendering equations …")
    eq_paths = render_equations()
    all_placements = build_equation_placements(eq_paths) + IMAGE_PLACEMENTS

    # ── Step 1: unzip template ────────────────────────────────────────────────
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    with zipfile.ZipFile(SRC) as z:
        z.extractall(WORK)

    slide_path = WORK / "ppt" / "slides" / "slide1.xml"
    rels_path  = WORK / "ppt" / "slides" / "_rels" / "slide1.xml.rels"
    media_dir  = WORK / "ppt" / "media"
    media_dir.mkdir(exist_ok=True)

    xml  = slide_path.read_text(encoding="utf-8")
    rels = rels_path.read_text(encoding="utf-8")

    # NOTE: We do NOT globally replace template colours here to avoid accidentally
    # recolouring footer icons, logos, and other template elements.

    # ── Step 2: title & authors ───────────────────────────────────────────────
    xml = replace_first(
        xml,
        "Project Title: an Exciting Project with Even More Exciting Results",
        xml_escape(TITLE),
    )
    xml = replace_first(
        xml,
        "Author Author, Author Author, Author Author, Author Author, and Author Author",
        xml_escape(AUTHORS),
    )

    # ── Step 3: section titles (document order: TL, BL, TR, BR) ──────────────
    for title in SECTION_TITLES:
        xml = replace_first(
            xml,
            "<a:t>SECTION TITLE</a:t>",
            f"<a:t>{xml_escape(title)}</a:t>",
        )

    # ── Step 4: centre callout title ──────────────────────────────────────────
    xml = replace_first(
        xml,
        "<a:t>CALLOUT TITLE / SECTION TITLE</a:t>",
        f"<a:t>{xml_escape(CALLOUT_TITLE)}</a:t>",
    )

    # ── Step 5: panel bodies (TL → BL → TR → BR) ─────────────────────────────

    # Panel 1 — top-left: Context & Motivation
    body_tl = "".join(make_bullet_para(b, sz=2400) for b in COL1_TOP)
    xml = replace_first_paragraph(xml, "Some text and visuals here \u2026", body_tl)

    # Panel 2 — bottom-left: Four Execution Challenges
    body_bl = (
        make_plain_para(
            "The shift: OPPORTUNITY DETECTION \u2192 EXECUTION FEASIBILITY",
            sz=2500, bold=True, color=SFU_RED,
        )
        + make_spacer(1000)
        + "".join(make_bullet_para(b, sz=2400) for b in COL1_BOT[1:])
    )
    xml = replace_first_paragraph(xml, "Some text and visuals here \u2026", body_bl)

    # Panel 3 — top-right: Results & Impact
    body_tr = (
        make_plain_para(
            "\u2605  h\u2082 reduces node expansions by 29%"
            " while matching Dijkstra\u2019s profit  \u2605",
            sz=3000, bold=True, align="ctr", color=SFU_RED,
        )
        + make_spacer(800)
        + "".join(make_bullet_para(b, sz=2400) for b in COL3_TOP)
        + make_spacer(800)
        + make_mono_para(RESULTS_TABLE_HEADER, sz=1900, bold=True)
        + make_mono_para("\u2500" * 46, sz=1900)
        + "".join(make_mono_para(row, sz=1900) for row in RESULTS_TABLE_ROWS)
    )
    xml = replace_first_paragraph(xml, "Some text and visuals here \u2026", body_tr)

    # Panel 4 — bottom-right: Scaling & Future Work
    body_br = "".join(make_bullet_para(b, sz=2400) for b in COL3_BOT)
    xml = replace_first_paragraph(xml, "Some text and visuals here \u2026", body_br)

    # ── Step 6: centre callout body ───────────────────────────────────────────
    # Equations are rendered as images below; text only has bullets + heuristics + takeaway.
    callout_first_para = (
        '<a:p><a:pPr><a:buSzPts val="1400"/></a:pPr>'
        '<a:endParaRPr sz="1339"/></a:p>'
    )
    callout_xml = (
        "".join(make_bullet_para(b, sz=2400) for b in CALLOUT_BULLETS)
        + make_spacer(900)
        + make_plain_para("Heuristics", sz=2700, bold=True, color=SFU_RED)
        + "".join(make_bullet_para(h, sz=2400) for h in CALLOUT_HEURISTICS)
        + make_spacer(900)
        + make_plain_para("Key Equations  \u25bc", sz=2700, bold=True, color=SFU_RED)
        + make_spacer(900)
        + make_plain_para(CALLOUT_TAKEAWAY, sz=2300, italic=True,
                          align="ctr", color=BLUE)
    )
    xml = replace_first(xml, callout_first_para, callout_xml)

    # ── Step 7: footer ────────────────────────────────────────────────────────
    xml = replace_first(
        xml,
        "[Footer: links, additional logos (e.g., funding),",
        xml_escape(FOOTER_LINE_1),
    )
    xml = replace_first(
        xml,
        "QR codes etc., remove box if not needed]",
        xml_escape(FOOTER_LINE_2),
    )

    # ── Step 8: inject "KEY EQUATIONS" label above equations in centre column ─
    extra_shapes: list[str] = [
        make_label_box(
            "Key Cost Equations",
            x=11_350_000, y=10_300_000, cx=9_200_000, cy=500_000,
            sid=290, sz=2700, color=SFU_RED, border=False,
        )
    ]

    # ── Step 9: embed images ──────────────────────────────────────────────────
    existing_rids  = set(re.findall(r'Id="(rId\d+)"', rels))
    next_rid       = max(int(r[3:]) for r in existing_rids) + 1
    existing_media: set[str] = {p.name for p in media_dir.iterdir() if p.is_file()}
    next_sid = 300

    for k, place in enumerate(all_placements):
        src: Path = place["src"]
        if not src.exists():
            print(f"  warn: missing {src.name}, skipping")
            continue

        # caption BELOW the image (only if specified)
        cap = place.get("caption")
        if cap:
            cap_h = 380_000
            cap_y = place["y"] + place["cy"] + 40_000
            extra_shapes.append(
                make_caption_box(cap, place["x"], cap_y, place["cx"], cap_h, next_sid)
            )
            next_sid += 1

        # copy media
        media_name = f"poster_fig{k+1}.png"
        i = 1
        while media_name in existing_media:
            media_name = f"poster_fig{k+1}_{i}.png"
            i += 1
        existing_media.add(media_name)
        shutil.copy(src, media_dir / media_name)

        # relationship
        rid = f"rId{next_rid}"
        next_rid += 1
        rels = rels.replace(
            "</Relationships>",
            (
                f'<Relationship Id="{rid}" '
                f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                f'Target="../media/{media_name}"/></Relationships>'
            ),
        )

        extra_shapes.append(
            make_pic_xml(rid, src.stem,
                         place["x"], place["y"], place["cx"], place["cy"], next_sid)
        )
        next_sid += 1

    if extra_shapes:
        xml = xml.replace("</p:spTree>",
                          "".join(extra_shapes) + "</p:spTree>", 1)

    # ── Step 10: write output ─────────────────────────────────────────────────
    slide_path.write_text(xml, encoding="utf-8")
    rels_path.write_text(rels, encoding="utf-8")

    if DST.exists():
        DST.unlink()
    with zipfile.ZipFile(DST, "w", zipfile.ZIP_DEFLATED) as zout:
        for path in sorted(WORK.rglob("*")):
            if path.is_file():
                zout.write(path, path.relative_to(WORK))

    print(f"wrote {DST}")


if __name__ == "__main__":
    fill()
