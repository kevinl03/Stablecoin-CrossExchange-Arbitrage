#!/bin/bash
# Compile LaTeX document to PDF
# Usage: ./compile_latex.sh

cd "$(dirname "$0")"

# Check if pdflatex is available
if ! command -v pdflatex &> /dev/null; then
    echo "Error: pdflatex not found. Please install LaTeX first:"
    echo "  brew install --cask mactex"
    echo "  OR use Overleaf: https://www.overleaf.com"
    exit 1
fi

# Check if bibtex is available
if ! command -v bibtex &> /dev/null; then
    echo "Warning: bibtex not found. Bibliography may not compile correctly."
fi

echo "Compiling LaTeX document..."

# First pass: generate aux files
pdflatex -interaction=nonstopmode research_report.tex

# Generate bibliography (if bibtex is available)
if command -v bibtex &> /dev/null; then
    echo "Generating bibliography..."
    bibtex research_report
fi

# Second pass: include bibliography
pdflatex -interaction=nonstopmode research_report.tex

# Third pass: resolve all references
pdflatex -interaction=nonstopmode research_report.tex

# Clean up auxiliary files (optional)
# Uncomment the next line to remove aux files after compilation
# rm -f *.aux *.log *.bbl *.blg *.out *.toc

echo "Compilation complete! Output: research_report.pdf"

