# Paper Reduction and Template Conversion Plan

## Current State Assessment

### What's Already Done ✅
- **Content Migration**: The `sec/` folder has been copied from `StablecoinArbitrage_CanadianAI2026/` to `StablecoinArbitrage_CAIAC2026/`
  - All section files (0_abstract.tex through 6_Conclusion.tex, Appendix.tex, etc.) are present and match the original
  - Figures folder has been copied (23 PNG files)
  - Preamble.tex, formulae.tex, references.bib are present
- **Template Setup**: `main.tex` has been partially converted to CAIAC2026 format
  - Uses `\documentclass[10pt]{cai26}` (correct PMLR template)
  - Structure is set up with proper section inputs
  - Abstract and keywords sections are configured

### What Needs to Be Done 🔧

#### 1. Branch Creation
- Create new branch called "migration" for this work
- Currently on branch: `issue-35-migrate-to-caiac-format`

#### 2. Author Anonymization (Critical for Double-Blind Review)
- **Remove Hang Ma as co-author** (only provided review feedback, not research contribution)
- **Anonymize author block** in `main.tex`:
  - Current: `Kevin Litvin\upstairs{\affilone,*}, Hang Ma\upstairs{\affilone}`
  - Current: `{\small \upstairs{\affilone} Simon Fraser University}`
  - Replace with anonymous format per PMLR template requirements
- **Check for identifying information** throughout paper text
- **Add Acknowledgments section** (blank for review, to be filled for camera-ready)

#### 3. Template Completion
- Verify `main.tex` uses correct PMLR template structure
- Ensure bibliography format is correct (`\printbibliography[heading=subbibintoc]`)
- Check that all required packages are in preamble
- Verify figure/table formatting matches PMLR style

#### 4. Content Reduction (19 pages → 16 pages: 12 main + 4 appendix)
- **Current**: 19 pages total (18 main + 1 appendix)
- **Target**: 16 pages total (12 main + 4 appendix)
- **Note**: Single-column format (PMLR) typically uses 30-40% more space than two-column (CVPR), so may need more aggressive reduction

#### 5. Content Reduction Strategy

##### High-Priority Content (Keep, possibly condense)
- Abstract (keep as-is)
- Introduction: Condense by ~20%
- Problem Formulation: Keep core, move detailed example to appendix (~25% reduction)
- Novel Heuristics: Keep all 4 heuristics, condense explanations by ~15%
- Main experimental results: Keep overnight test, heuristic comparison, key findings

##### Medium-Priority Content (Condense significantly)
- **Related Work** (`sec/2_related_work.tex`): Reduce by ~40%
  - Merge similar subsections (currently 8 subsections)
  - Focus on 3-4 key related work categories
  - Remove detailed comparisons, keep positioning statement
  
- **Results Section** (`sec/5.5_Results.tex`): Condense by ~30%
  - **Keep**: Overnight test (core contribution), deterministic comparison, baseline comparison
  - **Condense**: Sensitivity analysis (move detailed figures to appendix, keep summary)
  - **Condense**: Quote staleness (keep key finding, reduce detail)
  - **Condense**: Graph scaling (keep table, reduce discussion)
  - **Move**: Monte Carlo details to appendix

##### Low-Priority Content (Move to Appendix or Remove)
- Detailed sensitivity analysis figures (fig12-15): Move to appendix
- Detailed baseline ablation studies: Condense to 1-2 paragraphs
- Demonstrative example details: Move detailed walkthrough to appendix
- Some experimental methodology details: Move hyperparameter tables to appendix
- UI description (already in appendix): Keep but may condense

##### Figures Strategy
- **Keep in main text**: Cover graph, successful path, overnight results (fig10-11), key heuristic comparison
- **Move to appendix**: Sensitivity analysis figures (fig12-15), graph scaling figures (fig07-08), some detailed comparison figures
- **Remove or combine**: Some redundant bar charts can be combined

#### 6. Appendix Expansion
- Expand from 1 page to 4 pages with:
  - Detailed sensitivity analysis figures and tables
  - Detailed baseline comparison tables
  - Demonstrative example walkthrough
  - Hyperparameter configuration details
  - Additional experimental methodology details
  - Some detailed results tables

## Implementation Steps

### Phase 1: Branch and Verification
1. Create "migration" branch (requires git_write permission)
2. Verify all content is properly migrated (compare key files)
3. Test compilation with PMLR template to get baseline page count

### Phase 2: Anonymization (Critical - Must Do First)
1. Remove Hang Ma from author block
2. Replace author block with anonymous format
3. Remove "Simon Fraser University" affiliation
4. Check paper text for any identifying information
5. Add blank Acknowledgments section (for review)

### Phase 3: Template Completion
1. Verify `main.tex` structure matches PMLR template exactly
2. Check bibliography setup
3. Verify all packages are compatible
4. Test compilation

### Phase 4: Content Reduction
1. **Related Work**: Reduce by ~40% (merge subsections, remove details)
2. **Introduction**: Condense by ~20%
3. **Problem Formulation**: Reduce by ~25% (move example to appendix)
4. **Novel Heuristics**: Condense by ~15%
5. **Results**: Condense by ~30% (move sensitivity details to appendix)
6. **Baselines**: Condense significantly (1-2 paragraphs)

### Phase 5: Figure Reorganization
1. Move sensitivity figures (fig12-15) to appendix
2. Move graph scaling figures (fig07-08) to appendix
3. Keep core results figures in main text
4. Update figure references in text

### Phase 6: Appendix Expansion
1. Add moved content to appendix
2. Organize appendix sections
3. Ensure appendix is self-contained

### Phase 7: Final Verification
1. Compile and verify page count: 12 pages main + 4 pages appendix = 16 pages total
2. Verify anonymization is complete
3. Check all figure/table references
4. Final formatting pass for PMLR style

## Key Files to Modify

### Primary Files
- `docs/latex/StablecoinArbitrage_CAIAC2026/main.tex` - Anonymize authors, verify template
- `docs/latex/StablecoinArbitrage_CAIAC2026/sec/2_related_work.tex` - Major reduction (~40%)
- `docs/latex/StablecoinArbitrage_CAIAC2026/sec/1_intro.tex` - Condense (~20%)
- `docs/latex/StablecoinArbitrage_CAIAC2026/sec/3_problem_formulation.tex` - Reduce (~25%)
- `docs/latex/StablecoinArbitrage_CAIAC2026/sec/4_Novel_Heuristics.tex` - Condense (~15%)
- `docs/latex/StablecoinArbitrage_CAIAC2026/sec/5.5_Results.tex` - Condense (~30%)
- `docs/latex/StablecoinArbitrage_CAIAC2026/sec/5.2_baseline.tex` - Condense significantly
- `docs/latex/StablecoinArbitrage_CAIAC2026/sec/Appendix.tex` - Expand to 4 pages

### Supporting Files
- `docs/latex/StablecoinArbitrage_CAIAC2026/preamble.tex` - Verify package compatibility
- `docs/latex/StablecoinArbitrage_CAIAC2026/references.bib` - Verify format

## Risk Mitigation

- **Template conversion may add pages**: Single-column typically uses 30-40% more space. May need to cut 5-6 pages instead of 3.
- **Content reduction must preserve core contributions**: Focus on removing redundancy, not core findings
- **Appendix must be self-contained**: Moved content should still be comprehensible
- **Test compilation frequently**: PMLR template may have different package requirements
- **Anonymization is critical**: Papers that fail anonymization are desk-rejected without review

## Success Criteria

- ✅ Paper compiles successfully with PMLR template
- ✅ Main text is exactly 12 pages (including references)
- ✅ Appendix is exactly 4 pages
- ✅ All core contributions and key results remain in main text
- ✅ Paper is properly anonymized for double-blind review (no author names, affiliations, or identifying info)
- ✅ Hang Ma removed as co-author (only acknowledgment if desired)
- ✅ All figures/tables are properly formatted for PMLR style
- ✅ Bibliography format matches PMLR requirements

## Notes

- The CAIAC2026 folder already exists with migrated content - we're working in this folder
- Current branch: `issue-35-migrate-to-caiac-format`
- Target branch: `migration` (to be created)
- Original paper: `StablecoinArbitrage_CanadianAI2026/` (CVPR template, 19 pages)
- Target paper: `StablecoinArbitrage_CAIAC2026/` (PMLR template, 16 pages)

