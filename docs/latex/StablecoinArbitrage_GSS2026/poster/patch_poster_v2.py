"""
patch_poster_v2.py — add new visuals to poster_filled_manual.pptx

Adds three new elements to the poster's right column and right-middle area:
  1.  $33T market bar chart  (right column, upper section, y≈3–7")
  2.  Baselines fail chart   (right column, lower section, y≈10–15")
  3.  System pipeline caption text (below pipeline area)

Run: python3 docs/latex/StablecoinArbitrage_GSS2026/poster/patch_poster_v2.py
Output: poster_filled_manual.pptx (in-place update)
"""

import sys, shutil, zipfile, re
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "venv312/lib/python3.14/site-packages"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch
import numpy as np

POSTER  = ROOT / "docs/latex/StablecoinArbitrage_GSS2026/poster/poster_filled_manual.pptx"
TMP     = Path("/tmp/patch_poster_v2_tmp")
FIGS    = ROOT / "docs/latex/StablecoinArbitrage_CAIAC2026/figures"

EMU = 914_400   # EMU per inch

# ── poster-quality matplotlib style ──────────────────────────────────────────
plt.rcParams.update({
    "font.family":       "sans-serif",
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":         False,
    "figure.facecolor":  "white",
    "axes.facecolor":    "white",
})

def _save(fig, name):
    p = TMP / name
    fig.savefig(p, dpi=220, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    print(f"  generated {name}")
    return p


# ── 1. $33T market bar chart (compact, poster-friendly) ──────────────────────
def gen_market():
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    labels = ["Mastercard", "Visa", "Stablecoins"]
    vals   = [9, 15, 33]
    cols   = ["#AAAAAA", "#888888", "#CC0633"]
    bars = ax.bar(labels, vals, color=cols, width=0.50, zorder=3,
                  edgecolor="white", linewidth=2)
    for bar, v, c in zip(bars, vals, cols):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.4,
                f"${v}T", ha="center", va="bottom",
                fontsize=17, fontweight="bold",
                color="#CC0633" if v == 33 else "#555555")
    ax.set_ylim(0, 40)
    ax.set_ylabel("Annual Transaction Volume (USD Trillion)", fontsize=12)
    ax.tick_params(labelsize=13)
    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.set_title("Stablecoins Surpass Traditional Networks", fontsize=13,
                 fontweight="bold", color="#CC0633", pad=8)
    return _save(fig, "pv2_market.png")


# ── 2. Baselines fail chart (compact) ────────────────────────────────────────
def gen_baselines():
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    methods = ["Bellman-\nFord", "1-Hop\nEnum.", "2-Hop\nEnum.", "A*+h₂\n(ours)"]
    profits = [0, 0, 0, 9.91]
    colors  = ["#CCCCCC", "#BBBBBB", "#AAAAAA", "#CC0633"]
    bars = ax.bar(methods, profits, color=colors, width=0.5,
                  edgecolor="white", linewidth=2, zorder=3)
    for bar, p, c in zip(bars, profits, colors):
        label = f"${p:.2f}" if p > 0 else "FAIL"
        ypos  = p + 0.1 if p > 0 else 0.15
        ax.text(bar.get_x() + bar.get_width()/2, ypos, label,
                ha="center", va="bottom", fontsize=14, fontweight="bold",
                color="#CC0633" if p > 0 else "#999999")
    ax.set_ylabel("Net Profit · $10 000 order (USD)", fontsize=12)
    ax.set_ylim(-0.5, 13)
    ax.tick_params(labelsize=12)
    ax.spines["left"].set_color("#CCCCCC")
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.set_title("Why Existing Approaches Fail", fontsize=13,
                 fontweight="bold", color="#CC0633", pad=8)
    return _save(fig, "pv2_baselines.png")


# ── XML helpers ───────────────────────────────────────────────────────────────

def _img_dims(p: Path):
    img = Image.open(p)
    return img.size  # (w_px, h_px)


def _pic_xml(rid: str, x: int, y: int, cx: int, cy: int, sid: int) -> str:
    return f"""<p:pic xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
    xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
    xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:nvPicPr>
    <p:cNvPr id="{sid}" name="img{sid}"/>
    <p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr>
    <p:nvPr/>
  </p:nvPicPr>
  <p:blipFill>
    <a:blip r:embed="{rid}"/>
    <a:stretch><a:fillRect/></a:stretch>
  </p:blipFill>
  <p:spPr>
    <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
  </p:spPr>
</p:pic>"""


def _sp_xml(text: str, x: int, y: int, cx: int, cy: int, sid: int,
            font_sz_pt: float = 11, bold: bool = False, italic: bool = True,
            color_hex: str = "555555") -> str:
    bold_tag  = "<a:b/>" if bold else ""
    ital_tag  = "<a:i/>" if italic else ""
    sz_hundredths = int(font_sz_pt * 100)
    return f"""<p:sp xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
    xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <p:nvSpPr>
    <p:cNvPr id="{sid}" name="lbl{sid}"/>
    <p:cNvSpPr txBox="1"/>
    <p:nvPr/>
  </p:nvSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
    <a:noFill/>
  </p:spPr>
  <p:txBody>
    <a:bodyPr wrap="square"/>
    <a:lstStyle/>
    <a:p><a:pPr algn="ctr"/>
      <a:r>
        <a:rPr lang="en-US" sz="{sz_hundredths}" {bold_tag} {ital_tag} dirty="0">
          <a:solidFill><a:srgbClr val="{color_hex}"/></a:solidFill>
        </a:rPr>
        <a:t>{text}</a:t>
      </a:r>
    </a:p>
  </p:txBody>
</p:sp>"""


def _rel_xml(rid: str, img_name: str) -> str:
    return (f'<Relationship Id="{rid}" '
            f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            f'Target="../media/{img_name}"/>')


# ── patch ─────────────────────────────────────────────────────────────────────

def patch():
    TMP.mkdir(parents=True, exist_ok=True)

    # Generate new charts
    market_path    = gen_market()
    baselines_path = gen_baselines()

    # Unpack poster
    shutil.rmtree(TMP / "pptx", ignore_errors=True)
    with zipfile.ZipFile(POSTER) as z:
        z.extractall(TMP / "pptx")

    slide_xml_path = TMP / "pptx/ppt/slides/slide1.xml"
    rels_path      = TMP / "pptx/ppt/slides/_rels/slide1.xml.rels"
    media_dir      = TMP / "pptx/ppt/media"

    slide_xml = slide_xml_path.read_text(encoding="utf-8")
    rels_xml  = rels_path.read_text(encoding="utf-8")

    # ── find next available rId and shape id ─────────────────────────────────
    existing_rids = set(re.findall(r'Id="(rId\d+)"', rels_xml))
    existing_ids  = set(int(x) for x in re.findall(r'id="(\d+)"', slide_xml))

    def next_rid():
        n = 1
        while f"rId{n}" in existing_rids:
            n += 1
        existing_rids.add(f"rId{n}")
        return f"rId{n}"

    def next_sid():
        n = max(existing_ids or {0}) + 1
        existing_ids.add(n)
        return n

    # ── copy images ───────────────────────────────────────────────────────────
    mkt_img  = "pv2_market.png"
    base_img = "pv2_baselines.png"
    shutil.copy(market_path,    media_dir / mkt_img)
    shutil.copy(baselines_path, media_dir / base_img)
    print(f"  copied {mkt_img}, {base_img}")

    # ── assign rIds ───────────────────────────────────────────────────────────
    rid_mkt  = next_rid()
    rid_base = next_rid()

    # ── layout constants ─────────────────────────────────────────────────────
    # Poster is 35" x 24".
    # Right column starts at x ≈ 24" = 21,945,600 EMU
    # Available right column width: ~10.5" = 9,601,200 EMU
    # Upper section (right col) : y = 3"–8"  → place market chart here
    # Lower section (right col) : y = 10"–16" → place baselines chart here

    RC_X   = int(24.2 * EMU)    # 24.2" right column start
    RC_W   = int(10.0 * EMU)    # 10" wide

    # Market chart: right column, y = 3.2" to 7.5"
    mkt_y  = int(3.2  * EMU)
    mkt_h  = int(4.3  * EMU)
    mkt_cx = int(9.8  * EMU)
    mkt_ar = _img_dims(market_path)[0] / _img_dims(market_path)[1]
    mkt_cy = round(mkt_cx / mkt_ar)

    # Baselines chart: right column, y = 10.0" to 15.0"
    base_y  = int(10.0 * EMU)
    base_cx = int(9.8  * EMU)
    base_ar = _img_dims(baselines_path)[0] / _img_dims(baselines_path)[1]
    base_cy = round(base_cx / base_ar)

    # ── caption label helper ─────────────────────────────────────────────────
    cap_h  = int(0.45 * EMU)
    cap_sz = 10.5

    # ── build new XML fragments ───────────────────────────────────────────────
    sid1 = next_sid(); sid1c = next_sid()
    sid2 = next_sid(); sid2c = next_sid()

    new_xml = ""

    # Market chart + caption
    new_xml += _pic_xml(rid_mkt, RC_X, mkt_y, mkt_cx, mkt_cy, sid1)
    new_xml += _sp_xml(
        "Fig. M — Stablecoin transaction volume vs. Mastercard &amp; Visa (2024)",
        RC_X, mkt_y + mkt_cy + int(0.05*EMU), RC_W, cap_h, sid1c,
        font_sz_pt=cap_sz, bold=False, italic=True, color_hex="555555")

    # Baselines chart + caption
    new_xml += _pic_xml(rid_base, RC_X, base_y, base_cx, base_cy, sid2)
    new_xml += _sp_xml(
        "Fig. B — Net profit under live conditions: existing baselines vs. A*+h₂",
        RC_X, base_y + base_cy + int(0.05*EMU), RC_W, cap_h, sid2c,
        font_sz_pt=cap_sz, bold=False, italic=True, color_hex="555555")

    # ── inject pictures before </p:spTree> ───────────────────────────────────
    slide_xml = slide_xml.replace("</p:spTree>", new_xml + "\n</p:spTree>")
    slide_xml_path.write_text(slide_xml, encoding="utf-8")

    # ── inject relationships ──────────────────────────────────────────────────
    rels_xml = rels_xml.replace(
        "</Relationships>",
        _rel_xml(rid_mkt,  mkt_img) + "\n" +
        _rel_xml(rid_base, base_img) + "\n" +
        "</Relationships>")
    rels_path.write_text(rels_xml, encoding="utf-8")

    # ── repack ────────────────────────────────────────────────────────────────
    POSTER.unlink()
    with zipfile.ZipFile(POSTER, "w", zipfile.ZIP_DEFLATED) as zout:
        root = TMP / "pptx"
        for f in root.rglob("*"):
            if f.is_file():
                zout.write(f, f.relative_to(root))
    print(f"\nwrote {POSTER}  ({POSTER.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    patch()
