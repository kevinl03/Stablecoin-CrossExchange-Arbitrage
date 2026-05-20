"""
One-shot patch for poster_filled_manual.pptx:
  • Replace the "???" section title  → "Graph Scaling"
  • Replace the "subtitle." line     → real subtitle
  • Replace placeholder bullet       → two paper-sourced bullets
  • Embed fig08_graph_scaling_expansions.png in that section

Run from the repo root:
  python3 docs/latex/StablecoinArbitrage_GSS2026/poster/patch_manual_poster.py
"""

import shutil, zipfile, os, re
from pathlib import Path

# ── paths ────────────────────────────────────────────────────────────────────
REPO   = Path(__file__).resolve().parents[4]
POSTER = REPO / "docs/latex/StablecoinArbitrage_GSS2026/poster/poster_filled_manual.pptx"
FIG    = REPO / "docs/latex/StablecoinArbitrage_CAIAC2026/figures/fig08_graph_scaling_expansions.png"
TMP    = REPO / "docs/latex/StablecoinArbitrage_GSS2026/poster/_patch_tmp"

# ── content ──────────────────────────────────────────────────────────────────
SECTION_TITLE = "Graph Scaling"
SUBTITLE      = "Node Expansions vs. Network Size (4\u201312 Exchanges)"

# Drawn directly from the paper's experiments section and Table 2
BULLET_1 = (
    "Dijkstra expansions stay flat (341\u2192395) as the graph scales from "
    "4 to 12 exchanges (19\u219241\u00a0nodes, 161\u2192864\u00a0edges); "
    "penalty heuristics h\u2081 and h\u2083 scale substantially worse."
)
BULLET_2 = (
    "At 12 exchanges h\u2081 expands 768 nodes and h\u2083 expands 910 nodes "
    "\u2014 94% and 130% more than Dijkstra\u2019s 395, indicating penalty "
    "terms compound as venue count grows."
)

# Image natural aspect ratio 2119:1477 \u2248 1.435
IMG_CX   = 6_500_000          # EMU  (\u22487.1 inches)
IMG_AR   = 2119 / 1477
IMG_CY   = round(IMG_CX / IMG_AR)

# Position: centred inside the ??? content box (x=457200, y=3657600, cx=13716000)
BOX_X, BOX_Y, BOX_CX = 457_200, 3_657_600, 13_716_000
IMG_X    = BOX_X + (BOX_CX - IMG_CX) // 2   # horizontally centred
IMG_Y    = 5_400_000                          # ~1.9" below box top, after text
NEW_RID  = "rId14"
NEW_IMG  = "image12.png"


def xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


def make_bullet_para(text: str) -> str:
    return (
        '<a:p>'
        '<a:pPr marL="342900" indent="-342900">'
        '<a:buFont typeface="Arial"/><a:buChar char="\u2022"/>'
        '</a:pPr>'
        '<a:r>'
        '<a:rPr lang="en-US" sz="2300" dirty="0">'
        '<a:solidFill><a:schemeClr val="dk1"/></a:solidFill>'
        '<a:latin typeface="Arial"/>'
        '</a:rPr>'
        f'<a:t>{xml_escape(text)}</a:t>'
        '</a:r>'
        '</a:p>'
    )


def make_pic_xml(rid: str, x: int, y: int, cx: int, cy: int, sid: int) -> str:
    return (
        f'<p:pic>'
        f'<p:nvPicPr>'
        f'<p:cNvPr id="{sid}" name="fig08_scaling"/>'
        f'<p:cNvPicPr/><p:nvPr/>'
        f'</p:nvPicPr>'
        f'<p:blipFill>'
        f'<a:blip r:embed="{rid}"/>'
        f'<a:stretch><a:fillRect/></a:stretch>'
        f'</p:blipFill>'
        f'<p:spPr>'
        f'<a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        f'</p:spPr>'
        f'</p:pic>'
    )


def patch():
    # ── unpack ────────────────────────────────────────────────────────────────
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)
    with zipfile.ZipFile(POSTER, "r") as z:
        z.extractall(TMP)

    # ── copy figure into media ────────────────────────────────────────────────
    media_dir = TMP / "ppt" / "media"
    media_dir.mkdir(exist_ok=True)
    shutil.copy(FIG, media_dir / NEW_IMG)
    print(f"  copied {FIG.name} → media/{NEW_IMG}")

    # ── patch slide1.xml ──────────────────────────────────────────────────────
    slide_path = TMP / "ppt" / "slides" / "slide1.xml"
    xml = slide_path.read_text(encoding="utf-8")

    # 1. Replace "???" title
    old_title = "<a:t>???</a:t>"
    new_title = f"<a:t>{xml_escape(SECTION_TITLE)}</a:t>"
    assert old_title in xml, "Could not find '???' title text"
    xml = xml.replace(old_title, new_title, 1)
    print("  patched: ??? → section title")

    # 2. Replace "subtitle." with actual subtitle
    old_sub = "<a:t>subtitle.</a:t>"
    new_sub = f"<a:t>{xml_escape(SUBTITLE)}</a:t>"
    assert old_sub in xml, "Could not find 'subtitle.' text"
    xml = xml.replace(old_sub, new_sub, 1)
    print("  patched: subtitle. → real subtitle")

    # 3. Replace placeholder bullet + add a second bullet
    #    The placeholder paragraph ends with:  ...What should go here :o </a:t></a:r></a:p>
    #    We replace just the <a:t> content and splice in a second bullet after </a:p>
    old_bullet_text = "<a:t>What should go here :o </a:t>"
    new_bullet_text = f"<a:t>{xml_escape(BULLET_1)}</a:t>"
    assert old_bullet_text in xml, "Could not find placeholder bullet text"
    xml = xml.replace(old_bullet_text, new_bullet_text, 1)

    # Append second bullet immediately after the closing </a:p> of bullet 1
    # We can find it reliably because bullet 1 now ends uniquely
    marker = new_bullet_text + "</a:r></a:p>"
    assert marker in xml, "Could not locate end of first bullet paragraph"
    xml = xml.replace(
        marker,
        marker + make_bullet_para(BULLET_2),
        1
    )
    print("  patched: placeholder bullet → two paper-sourced bullets")

    # 4. Inject the <p:pic> image element before </p:spTree>
    #    Determine a safe shape id (max existing id + 1)
    existing_ids = [int(m) for m in re.findall(r'id="(\d+)"', xml)]
    new_sid = max(existing_ids) + 1 if existing_ids else 200

    pic_xml = make_pic_xml(NEW_RID, IMG_X, IMG_Y, IMG_CX, IMG_CY, new_sid)
    assert "</p:spTree>" in xml, "Cannot find </p:spTree> anchor"
    xml = xml.replace("</p:spTree>", pic_xml + "</p:spTree>", 1)
    print(f"  injected fig08 pic (sid={new_sid}, x={IMG_X}, y={IMG_Y}, cx={IMG_CX}, cy={IMG_CY})")

    slide_path.write_text(xml, encoding="utf-8")

    # ── patch slide1.xml.rels ─────────────────────────────────────────────────
    rels_path = TMP / "ppt" / "slides" / "_rels" / "slide1.xml.rels"
    rels = rels_path.read_text(encoding="utf-8")
    new_rel = (
        f'<Relationship Id="{NEW_RID}" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
        f'Target="../media/{NEW_IMG}"/>'
    )
    rels = rels.replace("</Relationships>", new_rel + "</Relationships>")
    rels_path.write_text(rels, encoding="utf-8")
    print(f"  added relationship {NEW_RID} → media/{NEW_IMG}")

    # ── repack ────────────────────────────────────────────────────────────────
    out = POSTER.with_stem(POSTER.stem)   # overwrite in-place
    tmp_zip = POSTER.with_suffix(".tmp.pptx")
    with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for fpath in sorted(TMP.rglob("*")):
            if fpath.is_file():
                zout.write(fpath, fpath.relative_to(TMP))
    tmp_zip.replace(POSTER)
    shutil.rmtree(TMP)
    print(f"\n  wrote {POSTER}  ({POSTER.stat().st_size/1e6:.2f} MB)")


if __name__ == "__main__":
    patch()
