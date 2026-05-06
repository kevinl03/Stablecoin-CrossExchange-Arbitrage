"""
Fill the Canadian AI 2026 poster template (CdnAI2026_poster_landscape_36x24.pptx)
with paper content and embed key figures.

3-column "Three-Column Flow" layout:
  Col 1 (Left):   Context & Motivation  /  Four Execution Challenges
  Col 2 (Centre): Technical Core — graph model, heuristics, profitable-path diagram
  Col 3 (Right):  Results & The "Win"  /  Scaling & Future Work

Page size: 36 x 24 inches (landscape, EMU 32 918 400 x 21 945 600).

Run from the repo root:
    python3 docs/latex/StablecoinArbitrage_GSS2026/poster/fill_poster.py

Output: docs/latex/StablecoinArbitrage_GSS2026/poster/poster_filled.pptx
"""
from __future__ import annotations

import os
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

# Slide canvas: 36 × 24 inches.  1 inch = 914 400 EMU.
SLIDE_W = 36 * 914_400   # 32 918 400
SLIDE_H = 24 * 914_400   # 21 945 600

# SFU red — used for headings and the killer-stat box.
SFU_RED = "CC0633"
DARK    = "1A1A2E"   # near-black body text
GREY    = "555555"   # caption / secondary text
BLUE    = "0070C0"   # equation accent

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

# ── Column 1, top: abstract / motivation ─────────────────────────────────────
COL1_TOP: list[str] = [
    "Cross-exchange stablecoin arbitrage exploits price discrepancies across "
    "centralized exchanges in a $300B+ market.",
    "Prior work detects opportunities via negative-cycle algorithms — but ignores "
    "execution: fees, slippage, withdrawal delays, and venue reliability.",
    "We shift focus to EXECUTION FEASIBILITY: compute trade-and-transfer paths that "
    "remain profitable after ALL real-world costs.",
    "Stablecoins are ideal: USD-pegged assets with a clear scalar profit objective "
    "across 12 major exchanges and 9 coin symbols.",
    "We run 7,200 overnight search instances and compare A* heuristics against "
    "Dijkstra and multi-start baselines.",
    "Code: github.com/kevinl03/Stablecoin-CrossExchange-Arbitrage",
]

# ── Column 1, bottom: four execution challenges ───────────────────────────────
COL1_BOT: list[str] = [
    "① LIQUIDITY — Order-book depth is insufficient for full fills at the quoted "
    "price; partial fills reduce effective profit.",
    "② SLIPPAGE — Large orders shift the VWAP above the mid-price; the effective "
    "rate r(e) captures this via slippage_bps.",
    "③ LATENCY — Blockchain transfers take minutes to hours; market prices move "
    "against the open leg while funds are in transit.",
    "④ RELIABILITY — Exchange downtime, withdrawal halts, and API failures derail "
    "planned routes mid-execution.",
    "Together these four factors mean that opportunity-detection methods overstate "
    "real profit — sometimes by more than 40%.",
]

# ── Column 2, centre callout: technical core ─────────────────────────────────
CALLOUT_TITLE = "Method: Execution-Aware A* Search"

CALLOUT_BULLETS: list[str] = [
    "GRAPH MODEL — Nodes are (exchange, stablecoin) pairs. "
    "Intra-exchange edges are trades; inter-exchange edges are same-coin transfers.",
    "EDGE WEIGHT — w(e) = -log r(e). Effective rate r(e) bundles taker fees, "
    "withdrawal/gas fees, chain-transfer time, and venue-reliability discount.",
    "GOAL — Any node where USD value exceeds the start amount (no closed cycle needed; "
    "stablecoins are USD-pegged).",
    "SEARCH — A* with f(n) = g(n) + h(n). Each heuristic is a domain-specific guidance "
    "penalty (not an admissible lower bound).",
]

CALLOUT_HEURISTICS: list[str] = [
    "h\u2081  (Liquidity)   Penalise shallow 24-h order books relative to order size.",
    "h\u2082  (Slippage)    \u2605 NOVEL: lambda \u00d7 max(0, slippage_bps \u2212 \u03b8). Prunes high-impact routes.",
    "h\u2083  (Chain)       Chain congestion time + static venue-reliability penalty.",
]

CALLOUT_EQUATIONS: list[str] = [
    "w(e) = -log r(e)       r(e) = (1-fee)(1-slippage)(1-gas)(reliability)",
    "f(n) = g(n) + h(n)     h\u2082 = \u03bb\u22c5max(0, slippage_bps \u2212 \u03b8)",
    "slippage_bps = (VWAP(Q) - P_mid) / P_mid \u00d7 10\u2074",
]

CALLOUT_TAKEAWAY = (
    "Slippage-aware h\u2082 prunes high-cost routes early, preserving low-cost ones: "
    "same profit as Dijkstra with 29% fewer node expansions."
)

# ── Column 3, top: results ────────────────────────────────────────────────────
# Killer stat is injected as a large bold shape; section body has the table.
COL3_TOP_INTRO: list[str] = [
    "Every A*-based run across 7,200 overnight instances finds a profitable path.",
    "Quote staleness: 99.6% of paths remain profitable up to 120 s of delay.",
    "h\u2081 and h\u2083 expand 58-87% MORE nodes and earn 30-33% LESS profit: "
    "aggressive penalties over-steer search.",
]

RESULTS_TABLE_HEADER = "Heuristic    Profit    Expansions  \u0394Exp"
RESULTS_TABLE_ROWS = [
    "Dijkstra     $10.01    359         ---",
    "h\u2082 (Slippage) $9.91  256         -29%  \u2605",
    "h\u2081 (Liq.)    $6.72    568        +58%",
    "h\u2083 (Chain)   $7.06    673        +87%",
    "Multi-start  $9.88    3\u00d7359       ---",
]

# ── Column 3, bottom: scaling & future work ───────────────────────────────────
COL3_BOT: list[str] = [
    "Graph scaling (4 \u2192 12 exchanges): h\u2082 maintains its expansion advantage at every "
    "graph size — the gap widens as the graph grows.",
    "h\u2082 is robust to order-size variation ($1k \u2013 $100k): slippage penalty keeps the "
    "search focused on liquid, low-impact paths.",
    "Overnight robustness: profit stays consistent across all 7,200 runs with minimal "
    "variance — the A* framework is stable in live conditions.",
    "FUTURE WORK: asynchronous order-book pre-fetching to reduce staleness; extension "
    "to DEX/AMM markets (Uniswap, Curve) with continuous pricing functions.",
    "FUTURE WORK: reinforcement-learning route selection and multi-currency baskets "
    "beyond stablecoins.",
]

FOOTER_LINE_1 = "github.com/kevinl03/Stablecoin-CrossExchange-Arbitrage"
FOOTER_LINE_2 = "Canadian AI 2026  |  GSS Paper  |  Poster: 36 \u00d7 24 in"


# ─────────────────────────────────────────────────────────────────────────────
# Image placements  (absolute slide EMU coordinates)
# ─────────────────────────────────────────────────────────────────────────────
# Approximate panel safe-zones (derived from template XML group transforms):
#   Left col content   x ~  970 000, y ~ 3 985 000 / 10 760 000, cx ~ 9 840 000
#   Right col content  x ~ 21 955 000 (same widths)
#   Centre callout     x ~ 11 135 000, y ~ 3 985 000, cx ~ 9 840 000, cy ~ 17 530 000

IMAGE_PLACEMENTS = [
    # ── Centre callout — Figure 1b: the profitable path (MAIN VISUAL) ──────────
    {
        "src":     FIGS / "CameraReadySuccesfulPathProfit.png",
        "x":  11_350_000, "y": 13_600_000,
        "cx":  9_500_000, "cy":  5_200_000,
        "caption": "Fig. 1b — Discovered profitable path: Kraken \u2192 KuCoin \u2192 KuCoin",
    },
    # ── Centre callout — full arbitrage subgraph (9 of 12 exchanges) ────────────
    {
        "src":     FIGS / "FullGraph.png",
        "x":  11_350_000, "y": 19_100_000,
        "cx":  9_500_000, "cy":  2_500_000,
        "caption": "Fig. 1a — Stablecoin arbitrage subgraph (9 of 12 exchanges)",
    },
    # ── Right top — node expansions bar chart (h1 h2 h3 vs Dijkstra) ────────────
    {
        "src":     FIGS / "fig01_node_expansion_bar.png",
        "x":  22_300_000, "y":  8_400_000,
        "cx":  9_400_000, "cy":  2_300_000,
        "caption": "Fig. 2a — Node expansions per heuristic (cached graph, $10 k order)",
    },
    # ── Right bottom — graph scaling: expansions vs. exchange count ──────────────
    {
        "src":     FIGS / "fig08_graph_scaling_expansions.png",
        "x":  22_300_000, "y": 15_700_000,
        "cx":  9_400_000, "cy":  2_700_000,
        "caption": "Fig. 2b — Expansions vs. graph size (4 \u2192 12 exchanges)",
    },
    # ── Right bottom — quote-staleness robustness ────────────────────────────────
    {
        "src":     FIGS / "fig09_quote_staleness.png",
        "x":  22_300_000, "y": 18_700_000,
        "cx":  9_400_000, "cy":  2_700_000,
        "caption": "Fig. 2c — Path profitability vs. quote age (0 \u2013 300 s delay)",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# XML helpers
# ─────────────────────────────────────────────────────────────────────────────

def xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _run(text: str, sz: int, bold: bool = False, italic: bool = False,
         color: str | None = None, face: str = "Arial") -> str:
    b = ' b="1"' if bold else ""
    i = ' i="1"' if italic else ""
    if color:
        fill = f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
    else:
        fill = '<a:solidFill><a:schemeClr val="dk1"/></a:solidFill>'
    return (
        f'<a:r><a:rPr lang="en-US" sz="{sz}"{b}{i} dirty="0">'
        f'{fill}'
        f'<a:latin typeface="{face}"/>'
        f'</a:rPr><a:t>{xml_escape(text)}</a:t></a:r>'
    )


def make_bullet_para(text: str, sz: int = 2400,
                     bold: bool = False, color: str | None = None) -> str:
    r = _run(text, sz, bold=bold, color=color)
    return (
        '<a:p>'
        '<a:pPr marL="342900" indent="-342900">'
        f'<a:buFont typeface="Arial"/><a:buChar char="\u2022"/>'
        '</a:pPr>'
        f'{r}'
        '</a:p>'
    )


def make_plain_para(text: str, sz: int = 2400,
                    bold: bool = False, italic: bool = False,
                    align: str = "l", color: str | None = None,
                    face: str = "Arial") -> str:
    algn = f' algn="{align}"' if align != "l" else ""
    r = _run(text, sz, bold=bold, italic=italic, color=color, face=face)
    return f'<a:p><a:pPr{algn}><a:buNone/></a:pPr>{r}</a:p>'


def make_mono_para(text: str, sz: int = 2000, bold: bool = False) -> str:
    return make_plain_para(text, sz=sz, bold=bold, face="Courier New")


def make_spacer(sz: int = 1200) -> str:
    return f'<a:p><a:pPr><a:buNone/></a:pPr><a:endParaRPr sz="{sz}"/></a:p>'


def make_caption_box(text: str, x: int, y: int, cx: int, cy: int, sid: int) -> str:
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


def make_textbox(text: str, x: int, y: int, cx: int, cy: int, sid: int,
                 sz: int = 4800, bold: bool = True, italic: bool = False,
                 align: str = "ctr", color: str = SFU_RED,
                 bg: str | None = None) -> str:
    """Inject a free-floating text box — used for the killer-stat headline."""
    algn = f' algn="{align}"'
    b = ' b="1"' if bold else ""
    i = ' i="1"' if italic else ""
    if bg:
        fill_xml = f'<a:solidFill><a:srgbClr val="{bg}"/></a:solidFill>'
    else:
        fill_xml = "<a:noFill/>"
    return (
        f'<p:sp><p:nvSpPr>'
        f'<p:cNvPr id="{sid}" name="KillerStat{sid}"/>'
        f'<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr>'
        f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        f'{fill_xml}'
        f'<a:ln w="19050"><a:solidFill><a:srgbClr val="{color}"/></a:solidFill></a:ln>'
        f'</p:spPr>'
        f'<p:txBody>'
        f'<a:bodyPr wrap="square" anchor="ctr" anchorCtr="1" insFit="normAutofit"/>'
        f'<a:lstStyle/>'
        f'<a:p><a:pPr{algn}><a:buNone/></a:pPr>'
        f'<a:r><a:rPr lang="en-US" sz="{sz}"{b}{i} dirty="0">'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        f'<a:latin typeface="Arial"/></a:rPr>'
        f'<a:t>{xml_escape(text)}</a:t></a:r></a:p>'
        f'</p:txBody></p:sp>'
    )


def make_pic_xml(rid: str, name: str,
                 x: int, y: int, cx: int, cy: int, sid: int) -> str:
    return (
        f'<p:pic><p:nvPicPr>'
        f'<p:cNvPr id="{sid}" name="{name}"/>'
        f'<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr>'
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
        raise RuntimeError(f"paragraph inner text not found: {inner_text!r}")
    p_open  = xml.rfind("<a:p>", 0, idx)
    p_close = xml.find("</a:p>", idx) + len("</a:p>")
    return xml[:p_open] + new_paras + xml[p_close:]


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def fill() -> None:
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

    # ── Replace template-red CD3E3D with SFU Red CC0633 in section title bars ──
    xml = xml.replace("CD3E3D", SFU_RED)

    # ── 1. Title & authors ────────────────────────────────────────────────────
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

    # ── 2. Section titles (4 panels, document order: TL, BL, TR, BR) ─────────
    for title in SECTION_TITLES:
        xml = replace_first(
            xml,
            "<a:t>SECTION TITLE</a:t>",
            f"<a:t>{xml_escape(title)}</a:t>",
        )

    # ── 3. Centre callout title ───────────────────────────────────────────────
    xml = replace_first(
        xml,
        "<a:t>CALLOUT TITLE / SECTION TITLE</a:t>",
        f"<a:t>{xml_escape(CALLOUT_TITLE)}</a:t>",
    )

    # ── 4. Panel bodies (template body placeholder text: "Some text and visuals here …") ──
    # Panels come in document order: TL → BL → TR → BR.

    # Panel 1 — top-left: Context & Motivation
    body_tl = "".join(make_bullet_para(b, sz=2400) for b in COL1_TOP)
    xml = replace_first_paragraph(xml, "Some text and visuals here \u2026", body_tl)

    # Panel 2 — bottom-left: Four Execution Challenges
    body_bl = (
        make_plain_para("The shift from OPPORTUNITY DETECTION to EXECUTION FEASIBILITY:",
                        sz=2400, bold=True, color=SFU_RED)
        + make_spacer(1000)
        + "".join(make_bullet_para(b, sz=2400) for b in COL1_BOT)
    )
    xml = replace_first_paragraph(xml, "Some text and visuals here \u2026", body_bl)

    # Panel 3 — top-right: Results & Impact
    # Starts with bold headline, then spacer, intro bullets, then table.
    body_tr = (
        make_plain_para(
            '\u2605  h\u2082 reduces node expansions by 29% while matching Dijkstra\'s profit  \u2605',
            sz=3200, bold=True, align="ctr", color=SFU_RED,
        )
        + make_spacer(1000)
        + "".join(make_bullet_para(b, sz=2400) for b in COL3_TOP_INTRO)
        + make_spacer(1000)
        + make_mono_para(RESULTS_TABLE_HEADER, sz=2000, bold=True)
        + make_mono_para("\u2500" * 46, sz=2000)
        + "".join(make_mono_para(row, sz=2000) for row in RESULTS_TABLE_ROWS)
    )
    xml = replace_first_paragraph(xml, "Some text and visuals here \u2026", body_tr)

    # Panel 4 — bottom-right: Scaling & Future Work
    body_br = "".join(make_bullet_para(b, sz=2400) for b in COL3_BOT)
    xml = replace_first_paragraph(xml, "Some text and visuals here \u2026", body_br)

    # ── 5. Centre callout body ────────────────────────────────────────────────
    callout_first_para = (
        '<a:p><a:pPr><a:buSzPts val="1400"/></a:pPr>'
        '<a:endParaRPr sz="1339"/></a:p>'
    )
    callout_xml = (
        "".join(make_bullet_para(b, sz=2400) for b in CALLOUT_BULLETS)
        + make_spacer(1000)
        + make_plain_para("Heuristics", sz=2600, bold=True, color=SFU_RED)
        + "".join(make_bullet_para(h, sz=2400) for h in CALLOUT_HEURISTICS)
        + make_spacer(1000)
        + make_plain_para("Key Equations", sz=2600, bold=True, color=SFU_RED)
        + "".join(make_mono_para(eq, sz=2100, bold=True) for eq in CALLOUT_EQUATIONS)
        + make_spacer(1000)
        + make_plain_para(CALLOUT_TAKEAWAY, sz=2400, italic=True, align="ctr", color=BLUE)
    )
    xml = replace_first(xml, callout_first_para, callout_xml)

    # ── 6. Footer ─────────────────────────────────────────────────────────────
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

    # ── 7. Embed figures + captions ───────────────────────────────────────────
    existing_rids = set(re.findall(r'Id="(rId\d+)"', rels))
    next_rid = max(int(r[3:]) for r in existing_rids) + 1
    existing_media: set[str] = {p.name for p in media_dir.iterdir() if p.is_file()}

    extra_shapes: list[str] = []
    next_sid = 300

    for k, place in enumerate(IMAGE_PLACEMENTS):
        src: Path = place["src"]
        if not src.exists():
            print(f"  warn: missing {src.name}, skipping")
            continue

        # caption BELOW the image
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
        xml = xml.replace("</p:spTree>", "".join(extra_shapes) + "</p:spTree>", 1)

    # ── 8. Write output ───────────────────────────────────────────────────────
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
