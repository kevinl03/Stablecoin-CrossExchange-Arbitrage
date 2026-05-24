# Final Presentation Snapshot — GSS 2026

This folder holds the **latest, send-ready copies** of the GSS 2026 presentation
package. Grab these three files to share with professors, supervisors, or the
conference organizers.

## Files

| File | What it is |
|------|------------|
| `StablecoinArbitrage_GSS2026_Script.md`   | The spoken script with delivery cues, visual notes, Q&A rebuttals, and the timing reference. |
| `StablecoinArbitrage_GSS2026_Script.docx` | Same script formatted as a reviewable Word document (wide margins for comments). |
| `StablecoinArbitrage_GSS2026_Slides.pptx` | The 9-slide presentation deck (16:9), 1.99 MB. |

## How to refresh

After editing the working files (`../script.md`, `../fill_slides_final.py`),
run the helper script from the **repo root**:

```bash
./docs/latex/StablecoinArbitrage_GSS2026/presentation/final/refresh.sh
```

This will:
1. Rebuild `slides_final.pptx` from `fill_slides_final.py`.
2. Regenerate `script_for_review.docx` from `script.md`.
3. Copy both outputs (plus `script.md`) into this folder under the
   send-ready filenames above.

## Provenance

- **Source of truth:** `../script.md` and `../fill_slides_final.py`.
- **Reviews applied:** TP1 (Tania, May 21) + TP3 (Tania, May 23) — see
  `../script_for_review_TP1.docx` and `../script_for_review_TP3.docx`.
- **Paper notation note:** the third heuristic on S6 is labelled `h₃` in this
  talk but corresponds to `h₄` in the paper (`§4.4`). The paper's `h₃` is the
  parallel multi-start strategy (`§4.3`), which is not a per-node heuristic
  and is omitted from the 8-minute slot.
