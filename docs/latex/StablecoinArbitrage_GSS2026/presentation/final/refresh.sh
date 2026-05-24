#!/usr/bin/env bash
# Refresh the final/ snapshot from the working files.
# Run from anywhere — paths are resolved relative to this script.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRES="$(dirname "$HERE")"                # …/presentation
ROOT="$(cd "$PRES/../../../.." && pwd)"  # repo root

PY="$ROOT/venv312/bin/python3.14"
if [[ ! -x "$PY" ]]; then
  echo "error: $PY not found. Activate your venv first." >&2
  exit 1
fi

echo "▶ rebuilding slides …"
"$PY" "$PRES/fill_slides_final.py"

echo "▶ regenerating review docx …"
"$PY" "$PRES/export_script_docx.py"

echo "▶ syncing snapshot into final/ …"
cp "$PRES/script.md"               "$HERE/StablecoinArbitrage_GSS2026_Script.md"
cp "$PRES/script_for_review.docx"  "$HERE/StablecoinArbitrage_GSS2026_Script.docx"
cp "$PRES/slides_final.pptx"       "$HERE/StablecoinArbitrage_GSS2026_Slides.pptx"

echo "✓ final/ snapshot refreshed:"
ls -la "$HERE" | grep -E '\.(md|docx|pptx)$'
