"""
Fill the CAIAC 2026 poster template (CdnAI2026_poster_landscape_36x24.pptx).

Design philosophy: MINIMAL TEXT, MAXIMUM VISUALS.
  Left col:   "$300B+" hook stat  +  arbitrage network graph
  Centre:     Problem formulation (2 lines) + large rendered equations + profitable-path image
  Right top:  "29%" killer stat + node-expansion bar chart
  Right bot:  QR code (GitHub + video demo) + future work

Page: 36 × 24 inches landscape (EMU 32 918 400 × 21 945 600).

Run from repo root:
    python3 docs/latex/StablecoinArbitrage_GSS2026/poster/fill_poster.py

Output: docs/latex/StablecoinArbitrage_GSS2026/poster/poster_filled.pptx
"""
from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[0]           # .../poster/
REPO = ROOT.parents[3]                               # repo root

# Ensure venv packages (qrcode, etc.) are importable even without `source activate`
_venv_pkg = REPO / "venv312" / "lib" / "python3.12" / "site-packages"
if _venv_pkg.exists() and str(_venv_pkg) not in sys.path:
    sys.path.insert(0, str(_venv_pkg))

SRC  = ROOT / "CdnAI2026_poster_landscape_36x24.pptx"
DST  = ROOT / "poster_filled.pptx"
WORK = Path("/tmp/cdnai_poster_fill")
TMP  = Path("/tmp/cdnai_poster_assets")   # equation PNGs, QR code

# Figures live in CAIAC2026/figures (symlinked from GSS2026/figures)
FIGS = REPO / "docs" / "latex" / "StablecoinArbitrage_CAIAC2026" / "figures"

# Colours (injected text only; we leave template colours untouched)
SFU_RED  = "CC0633"
DARK     = "#1A1A2E"
BLUE_HEX = "#0057A8"
GREY_HEX = "#555555"
LIGHT_BG = "#F2F2F7"


# ─────────────────────────────────────────────────────────────────────────────
# Panel text  (very short — images carry the message)
# ─────────────────────────────────────────────────────────────────────────────

TITLE   = "Execution-Aware A* Search for Cross-Exchange Stablecoin Arbitrage"
AUTHORS = "Kevin Litvin  —  Simon Fraser University"

SECTION_TITLES = [
    "Abstract: the $300B Opportunity",   # top-left
    "Arbitrage Network",                 # bottom-left
    "Key Results",                       # top-right
    "Code & Demo",                       # bottom-right
]

# Top-left: abstract sentences (paper-accurate, concise, no em-dashes)
COL1_TOP_ABSTRACT = (
    "Cross-exchange cryptocurrency arbitrage profits from price discrepancies between venues, "
    "yet existing approaches use negative-cycle detection targeting opportunity identification "
    "rather than execution feasibility. We introduce an execution-aware A* pathfinding framework "
    "applied to stablecoins, an asset class exceeding $300 B in market cap that bridges "
    "cryptocurrency and fiat currency."
)
COL1_TOP_DATASET = (
    "Live market data is collected from 12 major centralized exchanges via CCXT, covering "
    "9 stablecoin symbols (USDT, USDC, DAI, TUSD, FDUSD, and more). The problem is modelled "
    "as a weighted directed graph (up to 41 nodes, 864 edges) where each node is an "
    "(exchange, stablecoin) pair and each edge encodes fees, slippage, gas, transfer delays, "
    "and venue reliability. This novel proprietary CEX dataset spans 7,200 search instances."
)

# Bottom-left: caption + 2 explanatory sentences from the paper
COL1_BOT_CAPTION = (
    "Subgraph of the stablecoin arbitrage network (9 of 12 exchanges shown). "
    "Nodes = (exchange, coin); solid edges = intra-exchange trades; "
    "light edges = same-coin cross-exchange transfers."
)
COL1_BOT_EXPLAIN = (
    "Each intra-exchange edge represents a spot trade and carries a taker fee, order-book slippage "
    "penalty, and venue reliability discount. Each cross-exchange edge represents a stablecoin "
    "withdrawal and carries a gas fee plus an estimated blockchain-confirmation latency."
)

# Centre callout: 5-bullet methodology summary drawn from Section 3 of the paper
CALLOUT_TITLE = "Method: Execution-Aware A* Search"
CALLOUT_LINES = [
    "Graph G=(V,E): nodes are (exchange, stablecoin) pairs; intra-exchange edges are spot "
    "trades, inter-exchange edges are same-coin cross-venue stablecoin transfers.",
    "Edge weight w(e) = -log r(e); effective rate r(e) = (1-fee)(1-slippage)(1-gas) x "
    "reliability, converting all execution costs into a single multiplicative model.",
    "Open-path goal: any node where final USD value exceeds start capital. No closed cycle "
    "is required because all assets are USD-pegged stablecoins (within +/-2%).",
    "A* with f(n) = g(n) + h(n); terminates when a profitable path is found, the frontier "
    "is exhausted, or depth/time limits are reached. Search is not complete by design.",
    "A parallelized multi-start baseline (k=3 random A* launches) is evaluated alongside "
    "three novel guidance heuristics across 7,200 overnight search instances.",
]

# Top-right: headline stat + two supporting lines
COL3_TOP = [
    "h\u2082 achieves the same profit as Dijkstra in all 7,200 overnight instances",
    "99.6% of discovered paths remain profitable after 120 s of quote delay",
    "h\u2081 and h\u2083 expand 58\u201387% more nodes and earn 30\u201333% less profit",
]

# Bottom-right: QR label + future work (image fills most of the space)
COL3_BOT = [
    "Scan for source code and video demo.",
    "Future work: asynchronous order-book pre-fetching; extension to "
    "DEX / AMM markets (Uniswap, Curve) with continuous pricing invariants.",
]

FOOTER_LINE_1 = "github.com/kevinl03/Stablecoin-CrossExchange-Arbitrage"
FOOTER_LINE_2 = "Canadian AI 2026  |  GSS Paper  |  36 \u00d7 24 in"

# GitHub URL encoded in the QR code
QR_URL = "https://github.com/kevinl03/Stablecoin-CrossExchange-Arbitrage"


# ─────────────────────────────────────────────────────────────────────────────
# QR code only (equations are now native PowerPoint OMML shapes, not images)
# ─────────────────────────────────────────────────────────────────────────────

def render_assets() -> dict[str, Path]:
    """Render the QR code PNG. Returns {name: path}."""
    TMP.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    # QR code
    try:
        import qrcode as _qr
        qr = _qr.QRCode(
            error_correction=_qr.constants.ERROR_CORRECT_H,
            box_size=12, border=3,
        )
        qr.add_data(QR_URL)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#1A1A2E", back_color="white")
        p = TMP / "qr_github.png"
        img.save(p)
        paths["qr"] = p
        print(f"  rendered {p.name}")
    except Exception as e:
        print(f"  warn: QR code skipped ({e})")

    return paths


# ─────────────────────────────────────────────────────────────────────────────
# Natural aspect ratio helpers
# (All image cx/cy are computed from source pixel dimensions so nothing stretches)
# ─────────────────────────────────────────────────────────────────────────────

_NATURAL_AR: dict[str, float] = {
    "CameraReadySuccesfulPathProfit.png": 2158 / 1274,   # 1.694
    "FullGraph.png":                      1926 / 1542,   # 1.249
    "fig01_node_expansion_bar.png":       2119 / 1519,   # 1.395
    "fig08_graph_scaling_expansions.png": 2119 / 1477,   # 1.435
    "fig04_success_rate.png":             2558 / 1553,   # 1.647
}


def natural_cy(fname: str, cx: int) -> int:
    return int(cx / _NATURAL_AR.get(fname, 1.6))


def natural_cx(fname: str, cy: int) -> int:
    return int(cy * _NATURAL_AR.get(fname, 1.6))


def center_x(col_x: int, col_cx: int, img_cx: int) -> int:
    return col_x + (col_cx - img_cx) // 2


# Column anchor x and full width
COL_L_X, COL_C_X, COL_R_X = 1_200_000, 11_350_000, 22_200_000
COL_CX = 9_200_000   # available width for images in each column
FOOTER_Y = 19_891_689  # first pixel of the footer bar — images must end above this


def _place(src_name: str, x: int, y: int, cx: int,
           caption: str | None = None) -> dict:
    cy = natural_cy(src_name, cx)
    assert y + cy < FOOTER_Y, (
        f"{src_name} would overflow footer: {y+cy} >= {FOOTER_Y}"
    )
    return {"src": FIGS / src_name, "x": x, "y": y, "cx": cx, "cy": cy,
            "caption": caption}


def _place_asset(key: str, assets: dict[str, Path],
                 x: int, y: int, cx: int, cy: int,
                 caption: str | None = None) -> dict | None:
    p = assets.get(key)
    if p is None or not p.exists():
        return None
    assert y + cy < FOOTER_Y, f"{key} would overflow footer: {y+cy} >= {FOOTER_Y}"
    return {"src": p, "x": x, "y": y, "cx": cx, "cy": cy, "caption": caption}


# ─────────────────────────────────────────────────────────────────────────────
# XML helpers
# ─────────────────────────────────────────────────────────────────────────────

def xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _run(text: str, sz: int, bold: bool = False, italic: bool = False,
         color: str | None = None) -> str:
    b = ' b="1"' if bold else ""
    i = ' i="1"' if italic else ""
    fill = (
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        if color
        else '<a:solidFill><a:schemeClr val="dk1"/></a:solidFill>'
    )
    return (
        f'<a:r><a:rPr lang="en-US" sz="{sz}"{b}{i} dirty="0">'
        f'{fill}<a:latin typeface="Arial"/>'
        f'</a:rPr><a:t>{xml_escape(text)}</a:t></a:r>'
    )


def make_bullet(text: str, sz: int = 2400, color: str | None = None) -> str:
    return (
        '<a:p>'
        '<a:pPr marL="342900" indent="-342900">'
        '<a:buFont typeface="Arial"/><a:buChar char="\u2022"/>'
        '</a:pPr>'
        f'{_run(text, sz, color=color)}'
        '</a:p>'
    )


def make_plain(text: str, sz: int = 2400, bold: bool = False,
               italic: bool = False, align: str = "l",
               color: str | None = None) -> str:
    algn = f' algn="{align}"' if align != "l" else ""
    return (
        f'<a:p><a:pPr{algn}><a:buNone/></a:pPr>'
        f'{_run(text, sz, bold=bold, italic=italic, color=color)}'
        f'</a:p>'
    )


def spacer(sz: int = 1000) -> str:
    return f'<a:p><a:pPr><a:buNone/></a:pPr><a:endParaRPr sz="{sz}"/></a:p>'


def make_caption(text: str, x: int, y: int, cx: int, cy: int, sid: int) -> str:
    t = xml_escape(text)
    return (
        f'<p:sp><p:nvSpPr>'
        f'<p:cNvPr id="{sid}" name="Cap{sid}"/>'
        f'<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr>'
        f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        f'<a:noFill/><a:ln><a:noFill/></a:ln>'
        f'</p:spPr>'
        f'<p:txBody><a:bodyPr wrap="square" anchor="ctr"/><a:lstStyle/>'
        f'<a:p><a:pPr algn="ctr"><a:buNone/></a:pPr>'
        f'<a:r><a:rPr lang="en-US" sz="1700" i="1" dirty="0">'
        f'<a:solidFill><a:srgbClr val="555555"/></a:solidFill>'
        f'<a:latin typeface="Arial"/></a:rPr>'
        f'<a:t>{t}</a:t></a:r></a:p>'
        f'</p:txBody></p:sp>'
    )


def make_label(text: str, x: int, y: int, cx: int, cy: int, sid: int,
               sz: int = 2800, color: str = SFU_RED, bold: bool = True,
               align: str = "ctr") -> str:
    """Free-floating text box for section sub-labels."""
    return (
        f'<p:sp><p:nvSpPr>'
        f'<p:cNvPr id="{sid}" name="Lbl{sid}"/>'
        f'<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr>'
        f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        f'<a:noFill/><a:ln><a:noFill/></a:ln>'
        f'</p:spPr>'
        f'<p:txBody>'
        f'<a:bodyPr wrap="square" anchor="ctr" anchorCtr="1"/>'
        f'<a:lstStyle/>'
        f'<a:p><a:pPr algn="{align}"><a:buNone/></a:pPr>'
        f'<a:r><a:rPr lang="en-US" sz="{sz}" b="{"1" if bold else "0"}" dirty="0">'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        f'<a:latin typeface="Arial"/></a:rPr>'
        f'<a:t>{xml_escape(text)}</a:t></a:r></a:p>'
        f'</p:txBody></p:sp>'
    )


def make_pic(rid: str, name: str, x: int, y: int,
             cx: int, cy: int, sid: int) -> str:
    """Picture element with no aspect-ratio lock (fillRect fills cx×cy exactly)."""
    return (
        f'<p:pic><p:nvPicPr>'
        f'<p:cNvPr id="{sid}" name="{name}"/>'
        f'<p:cNvPicPr/><p:nvPr/></p:nvPicPr>'
        f'<p:blipFill><a:blip r:embed="{rid}"/>'
        f'<a:stretch><a:fillRect/></a:stretch></p:blipFill>'
        f'<p:spPr><a:xfrm>'
        f'<a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/>'
        f'</a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>'
        f'</p:pic>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# Office Math Markup Language (OMML) — native PowerPoint equation shapes
# ─────────────────────────────────────────────────────────────────────────────

_NS_A14 = 'xmlns:a14="http://schemas.microsoft.com/office/drawing/2010/main"'
_NS_M   = 'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"'


def _mr(t: str, sty: str = "i") -> str:
    """Single OMML math run (italic by default)."""
    return (f'<m:r><m:rPr><m:sty m:val="{sty}"/></m:rPr>'
            f'<m:t>{xml_escape(t)}</m:t></m:r>')

def _mp(t: str) -> str: return _mr(t, "p")   # plain / upright
def _mi(t: str) -> str: return _mr(t, "i")   # italic


def _msub(base: str, sub: str) -> str:
    """OMML subscript: base_sub."""
    return (f'<m:sSub><m:sSubPr><m:ctrlPr/></m:sSubPr>'
            f'<m:e>{base}</m:e><m:sub>{sub}</m:sub></m:sSub>')


# ── Pre-built OMML blocks ────────────────────────────────────────────────────
# U+2212 = minus sign, U+22C5 = dot operator, U+03B2/BB/B8/B3/C1 = Greek

_EQ_W = (                      # w(e) = −log r(e)
    _mi("w") + _mp("(") + _mi("e") + _mp(") = \u2212") +
    _mp("log\u2009") + _mi("r") + _mp("(") + _mi("e") + _mp(")")
)
_EQ_FN = (                     # f(n) = g(n) + h(n)
    _mi("f") + _mp("(") + _mi("n") + _mp(") = ") +
    _mi("g") + _mp("(") + _mi("n") + _mp(") + ") +
    _mi("h") + _mp("(") + _mi("n") + _mp(")")
)
_EQ_H1 = (                     # h_1 = β · max(0, 1 − V_24h / Q_ord)
    _msub(_mi("h"), _mp("1")) + _mp(" = ") +
    _mi("\u03b2") + _mp(" \u22c5 max(0, 1\u2212") +
    _msub(_mi("V"), _mp("24h")) + _mp("/") +
    _msub(_mi("Q"), _mp("ord")) + _mp(")")
)
_EQ_H2 = (                     # h_2 = λ · max(0, S_bps − θ)
    _msub(_mi("h"), _mp("2")) + _mp(" = ") +
    _mi("\u03bb") + _mp(" \u22c5 max(0, ") +
    _msub(_mi("S"), _mp("bps")) + _mp(" \u2212 ") +
    _mi("\u03b8") + _mp(")")
)
_EQ_H3 = (                     # h_3 = γ · (t_chain + ρ_venue)
    _msub(_mi("h"), _mp("3")) + _mp(" = ") +
    _mi("\u03b3") + _mp(" \u22c5 (") +
    _msub(_mi("t"), _mp("chain")) + _mp(" + ") +
    _msub(_mi("\u03c1"), _mp("venue")) + _mp(")")
)


def make_eq_box(math_blocks: list[str], label: str | None,
                x: int, y: int, cx: int, cy: int, sid: int,
                sz: int = 2800) -> str:
    """PowerPoint text-box shape with one or more OMML equation blocks
    and an optional italic label paragraph below the math."""
    math_paras = ""
    for block in math_blocks:
        math_paras += (
            f'<a:p>'
            f'<a:pPr algn="ctr"><a:buNone/>'
            f'<a:defRPr sz="{sz}"><a:latin typeface="Cambria Math"/></a:defRPr>'
            f'</a:pPr>'
            f'<a14:m {_NS_A14}>'
            f'<m:oMathPara {_NS_M}>'
            f'<m:oMathParaPr><m:jc m:val="ctr"/></m:oMathParaPr>'
            f'<m:oMath>{block}</m:oMath>'
            f'</m:oMathPara></a14:m>'
            f'</a:p>'
        )

    label_para = ""
    if label:
        is_star = "\u2605" in label
        lcolor  = SFU_RED if is_star else "555555"
        lbold   = "1"     if is_star else "0"
        label_para = (
            f'<a:p><a:pPr algn="ctr"><a:buNone/></a:pPr>'
            f'<a:r><a:rPr lang="en-US" sz="2100" i="1" b="{lbold}" dirty="0">'
            f'<a:solidFill><a:srgbClr val="{lcolor}"/></a:solidFill>'
            f'<a:latin typeface="Arial"/></a:rPr>'
            f'<a:t>{xml_escape(label)}</a:t></a:r></a:p>'
        )

    return (
        f'<p:sp><p:nvSpPr>'
        f'<p:cNvPr id="{sid}" name="MathEq{sid}"/>'
        f'<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr>'
        f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        f'<a:solidFill><a:srgbClr val="F2F2F7"/></a:solidFill>'
        f'<a:ln w="19050">'
        f'<a:solidFill><a:srgbClr val="{SFU_RED}"/></a:solidFill></a:ln>'
        f'</p:spPr>'
        f'<p:txBody>'
        f'<a:bodyPr wrap="square" anchor="ctr" anchorCtr="1"/>'
        f'<a:lstStyle/>'
        f'{math_paras}{label_para}'
        f'</p:txBody></p:sp>'
    )


def replace_first(xml: str, old: str, new: str) -> str:
    if old not in xml:
        raise RuntimeError(f"placeholder not found: {old!r}")
    return xml.replace(old, new, 1)


def replace_first_paragraph(xml: str, inner: str, new_paras: str) -> str:
    target = f"<a:t>{inner}</a:t>"
    idx = xml.find(target)
    if idx < 0:
        raise RuntimeError(f"paragraph text not found: {inner!r}")
    p_open  = xml.rfind("<a:p>", 0, idx)
    p_close = xml.find("</a:p>", idx) + len("</a:p>")
    return xml[:p_open] + new_paras + xml[p_close:]


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def fill() -> None:
    print("step 1/4 — rendering equations & QR code …")
    assets = render_assets()

    print("step 2/4 — unpacking template …")
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

    # ── Title & authors ────────────────────────────────────────────────────────
    xml = replace_first(xml,
        "Project Title: an Exciting Project with Even More Exciting Results",
        xml_escape(TITLE))
    # Reduce title font from 5737 (~57pt) to 5000 (~50pt) — one step smaller
    xml = xml.replace('sz="5737"', 'sz="5000"', 1)
    xml = replace_first(xml,
        "Author Author, Author Author, Author Author, Author Author, and Author Author",
        xml_escape(AUTHORS))

    # ── Section title bars ────────────────────────────────────────────────────
    for title in SECTION_TITLES:
        xml = replace_first(xml,
            "<a:t>SECTION TITLE</a:t>",
            f"<a:t>{xml_escape(title)}</a:t>")

    # ── Centre callout title ──────────────────────────────────────────────────
    xml = replace_first(xml,
        "<a:t>CALLOUT TITLE / SECTION TITLE</a:t>",
        f"<a:t>{xml_escape(CALLOUT_TITLE)}</a:t>")

    # ── Panel bodies (order TL → BL → TR → BR) ───────────────────────────────

    # TL: abstract paragraph + dataset paragraph (no floating stat boxes)
    body_tl = (
        make_plain(COL1_TOP_ABSTRACT, sz=2400)
        + spacer(900)
        + make_plain(COL1_TOP_DATASET, sz=2400)
    )
    xml = replace_first_paragraph(xml, "Some text and visuals here \u2026", body_tl)

    # BL: caption + two explanatory sentences from the paper
    body_bl = (
        make_plain(COL1_BOT_CAPTION, sz=2200, italic=True)
        + spacer(700)
        + make_plain(COL1_BOT_EXPLAIN, sz=2200)
    )
    xml = replace_first_paragraph(xml, "Some text and visuals here \u2026", body_bl)

    # TR: killer stat headline + supporting bullets
    body_tr = (
        make_plain("\u2605  29% Fewer Node Expansions  \u2605",
                   sz=4200, bold=True, align="ctr", color=SFU_RED)
        + make_plain("Same profit as Dijkstra across all 7,200 instances",
                     sz=2600, bold=True, align="ctr")
        + spacer(800)
        + "".join(make_bullet(t, sz=2300) for t in COL3_TOP)
    )
    xml = replace_first_paragraph(xml, "Some text and visuals here \u2026", body_tr)

    # BR: QR label + future work
    body_br = (
        make_plain(COL3_BOT[0], sz=2800, bold=True, align="ctr", color=SFU_RED)
        + spacer(600)
        + make_bullet(COL3_BOT[1], sz=2300)
    )
    xml = replace_first_paragraph(xml, "Some text and visuals here \u2026", body_br)

    # ── Centre callout body: 3 concise lines then equations (as images below) ──
    callout_first_para = (
        '<a:p><a:pPr><a:buSzPts val="1400"/></a:pPr>'
        '<a:endParaRPr sz="1339"/></a:p>'
    )
    callout_xml = (
        "".join(make_bullet(t, sz=2400) for t in CALLOUT_LINES)
        + spacer(800)
        + make_plain("Cost function and three novel heuristics \u25bc",
                     sz=2700, bold=True, color=SFU_RED, align="ctr")
    )
    xml = replace_first(xml, callout_first_para, callout_xml)

    # ── Footer ─────────────────────────────────────────────────────────────────
    xml = replace_first(xml,
        "[Footer: links, additional logos (e.g., funding),",
        xml_escape(FOOTER_LINE_1))
    xml = replace_first(xml,
        "QR codes etc., remove box if not needed]",
        xml_escape(FOOTER_LINE_2))

    print("step 3/4 — placing images …")

    # ─────────────────────────────────────────────────────────────────────────
    # Build all shapes to inject
    # ─────────────────────────────────────────────────────────────────────────
    shapes: list[str] = []     # XML fragments to append before </p:spTree>
    sid = 300                  # shape-id counter (avoid collision with template)

    # Relationship helpers
    existing_rids  = set(re.findall(r'Id="(rId\d+)"', rels))
    next_rid_num   = max(int(r[3:]) for r in existing_rids) + 1
    existing_media: set[str] = {p.name for p in media_dir.iterdir() if p.is_file()}
    media_counter  = [0]

    def _embed(src: Path) -> str:
        """Copy src into media dir and add a relationship; return the rId."""
        nonlocal next_rid_num
        mc = media_counter[0]
        media_counter[0] += 1
        media_name = f"pi_{mc}_{src.name}"
        while media_name in existing_media:
            mc += 1
            media_name = f"pi_{mc}_{src.name}"
        existing_media.add(media_name)
        shutil.copy(src, media_dir / media_name)
        rid = f"rId{next_rid_num}"
        next_rid_num += 1
        nonlocal rels
        rels = rels.replace(
            "</Relationships>",
            f'<Relationship Id="{rid}" '
            f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            f'Target="../media/{media_name}"/></Relationships>',
        )
        return rid

    def add_pic(src: Path, x: int, y: int, cx: int, cy: int,
                caption: str | None = None) -> None:
        nonlocal sid
        if not src.exists():
            print(f"  skip (missing): {src.name}")
            return
        rid = _embed(src)
        shapes.append(make_pic(rid, src.stem, x, y, cx, cy, sid))
        sid += 1
        if caption:
            cap_y = y + cy + 35_000
            shapes.append(make_caption(caption, x, cap_y, cx, 370_000, sid))
            sid += 1

    def add_label(text: str, x: int, y: int, cx: int, cy: int,
                  **kw) -> None:
        nonlocal sid
        shapes.append(make_label(text, x, y, cx, cy, sid, **kw))
        sid += 1

    def add_eq_box(math_blocks: list[str], label: str | None,
                   x: int, y: int, cx: int, cy: int, sz: int = 2800) -> None:
        nonlocal sid
        shapes.append(make_eq_box(math_blocks, label, x, y, cx, cy, sid, sz=sz))
        sid += 1

    # (No floating stat boxes in the left column — abstract text fills the panel body)

    # ── FullGraph in bottom-left: pushed down to within ~1 mm of footer ──────
    # Natural AR = 1926/1542 = 1.249.  Margin 100 000 EMU (~1 mm) from footer.
    fg_cx  = COL_CX
    fg_cy  = natural_cy("FullGraph.png", fg_cx)
    fg_y   = FOOTER_Y - fg_cy - 100_000
    fg_end = fg_y + fg_cy          # = FOOTER_Y - 100_000
    add_pic(FIGS / "FullGraph.png",
            x=COL_L_X, y=fg_y, cx=fg_cx, cy=fg_cy,
            caption="Stablecoin arbitrage graph: 9 of 12 exchanges shown")

    # ── Centre column: intro sentence + OMML equation boxes ──────────────────
    # 5-bullet callout text ends at roughly y=8 500 000; equations start at 9 300 000.
    eq_cx      = COL_CX
    eq_gap     = 100_000
    label_cy   = 450_000
    eq_y_start = 9_300_000

    # Intro sentence between callout heading and first equation
    add_label(
        "The edge weight w(e) encodes all execution costs; each heuristic below "
        "provides domain guidance to steer A* toward low-cost, profitable paths.",
        x=COL_C_X, y=eq_y_start - 650_000, cx=eq_cx, cy=550_000,
        sz=2300, color="333333", bold=False, align="ctr",
    )

    # ── Main cost-function box: w(e) and f(n) on two stacked lines ────────────
    main_cy = 1_050_000
    add_eq_box([_EQ_W, _EQ_FN], None,
               x=COL_C_X, y=eq_y_start, cx=eq_cx, cy=main_cy, sz=2800)

    # "Three Novel Heuristics" sub-label
    label_y = eq_y_start + main_cy + eq_gap
    add_label("Three Novel Heuristics",
              x=COL_C_X, y=label_y, cx=eq_cx, cy=label_cy,
              sz=2700, color=SFU_RED, bold=True)

    # ── h₁ / h₂ / h₃ boxes ────────────────────────────────────────────────────
    h_cy   = 1_000_000   # cy per heuristic box
    heur_defs = [
        (_EQ_H1, "Liquidity depth penalty"),
        (_EQ_H2, "\u2605 Slippage-aware  \u2014  Novel Contribution \u2605"),
        (_EQ_H3, "Chain congestion + venue reliability"),
    ]
    eq_y = label_y + label_cy + eq_gap
    for eq_block, lbl in heur_defs:
        add_eq_box([eq_block], lbl,
                   x=COL_C_X, y=eq_y, cx=eq_cx, cy=h_cy, sz=2800)
        eq_y += h_cy + eq_gap
    # eq_y is now just past the last heuristic box

    # ── Centre column: profitable path, bottom-aligned with FullGraph ─────────
    path_cx = COL_CX
    path_cy = natural_cy("CameraReadySuccesfulPathProfit.png", path_cx)
    path_y  = fg_end - path_cy    # bottom edge matches FullGraph bottom edge
    if path_y < eq_y + 120_000:   # guard against overlap with equations
        path_y = eq_y + 120_000
    cx_off = center_x(COL_C_X, COL_CX, path_cx)
    add_pic(FIGS / "CameraReadySuccesfulPathProfit.png",
            x=cx_off, y=path_y, cx=path_cx, cy=path_cy,
            caption="Fig. 1b - A profitable path: Kraken -> KuCoin (USDT -> TUSD)")

    # ── Right top: node-expansion bar chart ───────────────────────────────────
    # Constrain to top-right panel height so it doesn't overlap the QR code.
    # Top panel content runs ~y=4,000,000 to ~10,700,000; chart starts at y=7,500,000.
    bar_y  = 7_500_000
    bar_cy = 3_100_000                                         # ≈ 3.4" — fits top panel
    bar_cx = natural_cx("fig01_node_expansion_bar.png", bar_cy)   # maintain AR (≈ 4.3M)
    bar_x  = center_x(COL_R_X, COL_CX, bar_cx)                # centre in column
    add_pic(FIGS / "fig01_node_expansion_bar.png",
            x=bar_x, y=bar_y, cx=bar_cx, cy=bar_cy,
            caption="Fig. 2a — Node expansions per heuristic (cached graph, $10 k order)")

    # ── Right bottom: QR code (large, centered) ───────────────────────────────
    qr_p = assets.get("qr")
    if qr_p and qr_p.exists():
        qr_size = 4_800_000   # ~5.25" square
        qr_x = center_x(COL_R_X, COL_CX, qr_size)
        qr_y = FOOTER_Y - qr_size - 1_200_000   # near-bottom, above footer
        add_pic(qr_p, x=qr_x, y=qr_y, cx=qr_size, cy=qr_size,
                caption="Scan for source code & video demo")

    # ─────────────────────────────────────────────────────────────────────────
    # Inject all shapes
    # ─────────────────────────────────────────────────────────────────────────
    if shapes:
        xml = xml.replace("</p:spTree>", "".join(shapes) + "</p:spTree>", 1)

    print("step 4/4 — writing output …")
    slide_path.write_text(xml, encoding="utf-8")
    rels_path.write_text(rels, encoding="utf-8")

    if DST.exists():
        DST.unlink()
    with zipfile.ZipFile(DST, "w", zipfile.ZIP_DEFLATED) as zout:
        for path in sorted(WORK.rglob("*")):
            if path.is_file():
                zout.write(path, path.relative_to(WORK))

    print(f"wrote {DST}  ({DST.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    fill()
