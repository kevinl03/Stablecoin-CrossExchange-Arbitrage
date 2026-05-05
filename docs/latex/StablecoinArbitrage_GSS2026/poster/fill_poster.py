"""
Fill the Canadian AI 2026 poster template (CdnAI2026_poster_landscape_36x24.pptx)
with paper content and embed several figures.

Page size: 36 x 24 inches (landscape, EMU 32918400 x 21945600).
Layout (kept from template): four quadrant panels around a tall central callout,
plus the CAIAC and sponsor logos.

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
SRC = ROOT / "CdnAI2026_poster_landscape_36x24.pptx"
DST = ROOT / "poster_filled.pptx"
WORK = Path("/tmp/cdnai_poster_fill")

# Figures live in CAIAC2026/figures (GSS2026/figures is a symlink there).
FIGS = ROOT.parents[1] / "StablecoinArbitrage_CAIAC2026" / "figures"

# Slide canvas: 36 x 24 inches.  EMU = English Metric Unit (914400 / inch).
SLIDE_W_EMU = 36 * 914400  # 32_918_400
SLIDE_H_EMU = 24 * 914400  # 21_945_600


# ============================================================
# Content
# ============================================================

TITLE = "Execution-Aware A* Search for Cross-Exchange Stablecoin Arbitrage"
AUTHORS = "Kevin Litvin    \u2014    Simon Fraser University"

# Document order: top-left, bottom-left, top-right, bottom-right.
SECTION_TITLES = [
    "Motivation & Problem",
    "Heuristics & Baselines",
    "Setup & Dataset",
    "Results & Robustness",
]

SECTION_BODIES: list[list[str]] = [
    # 1. Motivation & Problem (top-left)
    [
        "Cross-exchange stablecoin arbitrage exploits price gaps between centralized exchanges (CEX).",
        "Existing work focuses on negative-cycle detection: it finds opportunities but ignores execution costs.",
        "Real costs matter: trading fees, withdrawal/gas fees, order-book slippage, blockchain transfer time, and venue reliability.",
        "Stablecoins (>$300B market cap) are USD-pegged, so cross-venue routing has a clean USD objective.",
        "Goal: plan executable, profitable trade-and-transfer paths under live market conditions.",
        "Research questions: which heuristics help? how do they shape A* expansions vs. profit?",
    ],
    # 2. Heuristics & Baselines (bottom-left)
    [
        "Three guidance heuristics, each capturing a distinct execution risk dimension.",
        "h_1 (liquidity): penalize shallow books from 24h volume, order size, and remaining time window.",
        "h_3 (chain congestion + reliability): chain transfer time plus a static venue reliability score.",
        "Parallel multi-start (k=3): random A* launches; trades robustness for repeated cost.",
        "Baselines: Dijkstra (h=0), Bellman-Ford negative-cycle, 1-hop, and 2-hop enumeration.",
        "All heuristics act as guidance penalties, not admissible lower bounds.",
    ],
    # 3. Setup & Dataset (top-right)
    [
        "12 CEX via CCXT: Binance, Kraken, KuCoin, Bybit, OKX, Gate.io, Bitget, MEXC, HTX, Coinbase, Crypto.com, Phemex.",
        "9 stablecoin symbols across the venues (USDT, USDC, DAI, TUSD, FDUSD, BUSD, PYUSD, USDP, GUSD).",
        "Nodes = (exchange, coin); edges = intra-exchange trades and same-coin cross-exchange transfers.",
        "Graphs grow from 4 to 12 exchanges; cached snapshots up to 41 nodes / 864 edges.",
        "8-hour overnight campaign with 7,200 search instances across heuristics and order sizes.",
        "Edge weights w(e) = -log(effective_rate(e)) absorb fees, slippage, gas, and chain delay.",
    ],
    # 4. Results & Robustness (bottom-right)
    [
        "h_2 expands 29% fewer nodes than Dijkstra while matching profit within 1% (cached, $10k).",
        "h_1 and h_3 expand 58-87% MORE nodes and earn 30-33% LESS profit: penalties over-steer search.",
        "Overnight (7,200 runs): every A*-based run finds a profitable path.",
        "Quote staleness: 99.6% of paths remain profitable up to 120 s of delay.",
        "Slippage-aware guidance follows the same optimal routes with less wasted exploration.",
    ],
]

# Mini results table for the Results panel (monospaced).
RESULTS_TABLE_HEADER = "Heuristic     Succ.   Profit    Exp.    \u0394"
RESULTS_TABLE_ROWS = [
    "Dijkstra      56.7%   $10.01    359     ---",
    "h_2 (slip.)   56.7%   $9.91     256     -29%",
    "h_1 (liq.)    56.7%   $6.72     568     +58%",
    "h_3 (chain)   56.7%   $7.06     673     +87%",
]

CALLOUT_TITLE = "Method: Execution-Aware A* Search"
CALLOUT_BULLETS = [
    "Directed graph G=(V,E). Nodes are (exchange, stablecoin); edges are intra-exchange trades and cross-exchange transfers (same coin).",
    "Edge weight w(e) = -log r(e). Effective rate r(e) bundles taker fees, withdrawal/gas fees, transfer time, and exchange-reliability risk.",
    "Open-path goal: any node where final USD value > start. No closed cycle required (USD-pegged stablecoins).",
    "A* search with f(n) = g(n) + h(n). h is a domain guidance penalty, not an admissible lower bound.",
]

# Stand-alone equation block (centered, larger font) shown right under the bullets.
CALLOUT_EQUATIONS = [
    "w(e) = -log r(e),    f(n) = g(n) + h(n)",
    "h_2 = lambda_slip * max(0, slippage_bps - theta)",
    "slippage_bps = (VWAP(Q) - P_mid) / P_mid * 10000",
]

CALLOUT_TAKEAWAY = (
    "Slippage-aware guidance prunes high-impact routes early, keeps low-impact "
    "ones intact: same profit as Dijkstra with 29% fewer expansions."
)

FOOTER_LINE_1 = "github.com/kevinl03/Stablecoin-CrossExchange-Arbitrage"
FOOTER_LINE_2 = "Canadian AI 2026  |  GSS Paper ID 306  |  36 x 24 in"


# ============================================================
# Image placements (absolute slide EMU; tuned for the panel boxes)
# ============================================================

IMAGE_PLACEMENTS = [
    # ---- top-left (Motivation) ------------------------------------------------
    {
        "src": FIGS / "fig04_success_rate.png",
        "x": 1_400_000,  "y": 7_500_000,
        "cx": 8_900_000, "cy": 2_200_000,
        "caption": "Success rate by heuristic",
    },
    # ---- bottom-left (Heuristics & Baselines) --------------------------------
    {
        "src": FIGS / "fig01_node_expansion_bar.png",
        "x": 1_400_000,  "y": 14_300_000,
        "cx": 8_900_000, "cy": 2_200_000,
        "caption": "Node expansions per heuristic (cached graph)",
    },
    # ---- top-right (Setup & Dataset) -----------------------------------------
    {
        "src": FIGS / "fig08_graph_scaling_expansions.png",
        "x": 22_400_000, "y": 7_500_000,
        "cx": 8_900_000, "cy": 2_200_000,
        "caption": "Expansions vs. graph size (4-12 exchanges)",
    },
    # ---- bottom-right (Results & Robustness) ---------------------------------
    {
        "src": FIGS / "fig11_overnight_heuristic_comparison.png",
        "x": 22_400_000, "y": 14_300_000,
        "cx": 8_900_000, "cy": 2_200_000,
        "caption": "Overnight (7,200 runs): profit, success, expansions",
    },
    # ---- centre callout ------------------------------------------------------
    {
        "src": FIGS / "FullGraph.png",
        "x": 11_300_000, "y": 13_400_000,
        "cx": 9_500_000, "cy": 3_900_000,
        "caption": "Stablecoin arbitrage graph (subset of 12 venues)",
    },
    {
        "src": FIGS / "CameraReadySuccesfulPathProfit.png",
        "x": 11_300_000, "y": 17_500_000,
        "cx": 9_500_000, "cy": 3_700_000,
        "caption": "A profitable path: kraken:USDT -> kucoin:USDT -> kucoin:TUSD",
    },
]


# ============================================================
# XML helpers
# ============================================================


def xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def make_bullet_para(text: str, sz: int = 2800) -> str:
    t = xml_escape(text)
    return (
        '<a:p>'
        '<a:pPr marL="285750" indent="-285750">'
        f'<a:buSzPts val="{sz + 200}"/>'
        '<a:buChar char="\u2022"/>'
        '</a:pPr>'
        f'<a:r><a:rPr lang="en-US" sz="{sz}" dirty="0">'
        '<a:solidFill><a:schemeClr val="dk1"/></a:solidFill>'
        '<a:latin typeface="Times"/><a:ea typeface="Times"/>'
        '<a:cs typeface="Times"/><a:sym typeface="Times"/></a:rPr>'
        f'<a:t>{t}</a:t></a:r>'
        '</a:p>'
    )


def make_mono_para(text: str, sz: int = 2200, bold: bool = False) -> str:
    t = xml_escape(text)
    b = ' b="1"' if bold else ''
    return (
        '<a:p><a:pPr><a:buNone/></a:pPr>'
        f'<a:r><a:rPr lang="en-US" sz="{sz}"{b} dirty="0">'
        '<a:solidFill><a:schemeClr val="dk1"/></a:solidFill>'
        '<a:latin typeface="Courier New"/><a:ea typeface="Courier New"/>'
        '<a:cs typeface="Courier New"/><a:sym typeface="Courier New"/></a:rPr>'
        f'<a:t>{t}</a:t></a:r></a:p>'
    )


def make_centered_emph(text: str, sz: int = 2600, color: str = "0070C0") -> str:
    t = xml_escape(text)
    return (
        '<a:p><a:pPr algn="ctr"><a:buNone/></a:pPr>'
        f'<a:r><a:rPr lang="en-US" sz="{sz}" b="1" i="1" dirty="0">'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        '<a:latin typeface="Times"/><a:ea typeface="Times"/>'
        '<a:cs typeface="Times"/><a:sym typeface="Times"/></a:rPr>'
        f'<a:t>{t}</a:t></a:r></a:p>'
    )


def make_caption_box(text: str, x: int, y: int, cx: int, cy: int, shape_id: int) -> str:
    """Small italic caption above an image (text box, not part of any group)."""
    t = xml_escape(text)
    return (
        '<p:sp><p:nvSpPr>'
        f'<p:cNvPr id="{shape_id}" name="Caption {shape_id}"/>'
        '<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        '<p:spPr>'
        f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        '<a:noFill/><a:ln><a:noFill/></a:ln>'
        '</p:spPr>'
        '<p:txBody>'
        '<a:bodyPr wrap="square" anchor="ctr" anchorCtr="0"><a:noAutofit/></a:bodyPr>'
        '<a:lstStyle/>'
        '<a:p><a:pPr algn="ctr"><a:buNone/></a:pPr>'
        '<a:r><a:rPr lang="en-US" sz="1900" i="1" dirty="0">'
        '<a:solidFill><a:srgbClr val="555555"/></a:solidFill>'
        '<a:latin typeface="Times"/><a:ea typeface="Times"/>'
        '<a:cs typeface="Times"/><a:sym typeface="Times"/></a:rPr>'
        f'<a:t>{t}</a:t></a:r></a:p>'
        '</p:txBody></p:sp>'
    )


def replace_first(text: str, old: str, new: str) -> str:
    if old not in text:
        raise RuntimeError(f"missing placeholder: {old!r}")
    return text.replace(old, new, 1)


def replace_first_paragraph(text: str, placeholder_inner: str, new_paragraphs_xml: str) -> str:
    """Replace the entire <a:p>...</a:p> that contains the given inner <a:t> text."""
    target = f"<a:t>{placeholder_inner}</a:t>"
    idx = text.find(target)
    if idx < 0:
        raise RuntimeError(f"missing body placeholder: {placeholder_inner!r}")
    p_open = text.rfind("<a:p>", 0, idx)
    if p_open < 0:
        raise RuntimeError("could not find enclosing <a:p>")
    p_close = text.find("</a:p>", idx)
    if p_close < 0:
        raise RuntimeError("could not find enclosing </a:p>")
    p_close += len("</a:p>")
    return text[:p_open] + new_paragraphs_xml + text[p_close:]


def make_pic_xml(rid: str, name: str, x: int, y: int, cx: int, cy: int, shape_id: int) -> str:
    return (
        f'<p:pic><p:nvPicPr>'
        f'<p:cNvPr id="{shape_id}" name="{name}"/>'
        f'<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr>'
        f'<p:nvPr/></p:nvPicPr>'
        f'<p:blipFill><a:blip r:embed="{rid}"/>'
        f'<a:stretch><a:fillRect/></a:stretch></p:blipFill>'
        f'<p:spPr><a:xfrm>'
        f'<a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/>'
        f'</a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>'
        f'</p:pic>'
    )


# ============================================================
# Main
# ============================================================


def fill():
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    with zipfile.ZipFile(SRC) as z:
        z.extractall(WORK)

    slide_xml_path = WORK / "ppt" / "slides" / "slide1.xml"
    rels_path = WORK / "ppt" / "slides" / "_rels" / "slide1.xml.rels"
    media_dir = WORK / "ppt" / "media"
    media_dir.mkdir(exist_ok=True)

    xml = slide_xml_path.read_text(encoding="utf-8")
    rels = rels_path.read_text(encoding="utf-8")

    # 1. Title and authors
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

    # 2. Section titles
    for new_title in SECTION_TITLES:
        xml = replace_first(
            xml,
            "<a:t>SECTION TITLE</a:t>",
            f"<a:t>{xml_escape(new_title)}</a:t>",
        )

    # 3. Callout title
    xml = replace_first(
        xml,
        "<a:t>CALLOUT TITLE / SECTION TITLE</a:t>",
        f"<a:t>{xml_escape(CALLOUT_TITLE)}</a:t>",
    )

    # 4. Bodies for the four standard sections
    for i, bullets in enumerate(SECTION_BODIES):
        body_xml = "".join(make_bullet_para(b, sz=2700) for b in bullets)
        # mini results "table" appended inside the Results panel
        if i == 3:
            body_xml += '<a:p><a:pPr><a:buNone/></a:pPr><a:endParaRPr sz="1200"/></a:p>'
            body_xml += make_mono_para(RESULTS_TABLE_HEADER, sz=2200, bold=True)
            for row in RESULTS_TABLE_ROWS:
                body_xml += make_mono_para(row, sz=2200)
        xml = replace_first_paragraph(xml, "Some text and visuals here \u2026", body_xml)

    # 5. Callout body: bullets + equation block + takeaway line
    callout_first_para = (
        '<a:p><a:pPr><a:buSzPts val="1400"/></a:pPr>'
        '<a:endParaRPr sz="1339"/></a:p>'
    )
    callout_xml = "".join(make_bullet_para(b, sz=2700) for b in CALLOUT_BULLETS)
    callout_xml += '<a:p><a:pPr><a:buNone/></a:pPr><a:endParaRPr sz="1200"/></a:p>'
    for eq in CALLOUT_EQUATIONS:
        callout_xml += make_mono_para(eq, sz=2400, bold=True)
    callout_xml += '<a:p><a:pPr><a:buNone/></a:pPr><a:endParaRPr sz="1200"/></a:p>'
    callout_xml += make_centered_emph(CALLOUT_TAKEAWAY, sz=2400)
    xml = replace_first(xml, callout_first_para, callout_xml)

    # 6. Footer
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

    # 7. Embed images + add captions
    existing_rids = set(re.findall(r'Id="(rId\d+)"', rels))
    next_rid_num = max(int(r[3:]) for r in existing_rids) + 1
    existing_media = {p.name for p in media_dir.iterdir() if p.is_file()}

    pic_xml_blocks: list[str] = []
    next_shape_id = 200

    for k, place in enumerate(IMAGE_PLACEMENTS):
        src_path: Path = place["src"]
        if not src_path.exists():
            print(f"warn: missing figure {src_path}, skipping")
            continue

        # caption ABOVE the image (small italic line)
        cap_text = place.get("caption")
        if cap_text:
            cap_h = 360_000  # ~0.4 inch
            cap_y = max(0, place["y"] - cap_h)
            pic_xml_blocks.append(
                make_caption_box(cap_text, place["x"], cap_y, place["cx"], cap_h, next_shape_id)
            )
            next_shape_id += 1

        # copy media file
        media_name = f"poster_image{k+1}.png"
        i = 1
        while media_name in existing_media:
            media_name = f"poster_image{k+1}_{i}.png"
            i += 1
        existing_media.add(media_name)
        shutil.copy(src_path, media_dir / media_name)

        # add relationship
        rid = f"rId{next_rid_num}"
        next_rid_num += 1
        rels = rels.replace(
            "</Relationships>",
            (
                f'<Relationship Id="{rid}" '
                f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                f'Target="../media/{media_name}"/></Relationships>'
            ),
        )

        # picture element
        pic_xml_blocks.append(
            make_pic_xml(
                rid=rid,
                name=src_path.stem,
                x=place["x"],
                y=place["y"],
                cx=place["cx"],
                cy=place["cy"],
                shape_id=next_shape_id,
            )
        )
        next_shape_id += 1

    if pic_xml_blocks:
        xml = xml.replace("</p:spTree>", "".join(pic_xml_blocks) + "</p:spTree>", 1)

    slide_xml_path.write_text(xml, encoding="utf-8")
    rels_path.write_text(rels, encoding="utf-8")

    # zip up
    if DST.exists():
        DST.unlink()
    with zipfile.ZipFile(DST, "w", zipfile.ZIP_DEFLATED) as zout:
        for path in sorted(WORK.rglob("*")):
            if path.is_file():
                zout.write(path, path.relative_to(WORK))

    print(f"wrote {DST}")


if __name__ == "__main__":
    fill()
