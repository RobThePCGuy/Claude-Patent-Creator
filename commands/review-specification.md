---
description: Review patent specification for 35 USC 112(a) compliance (written description and enablement heuristics; best mode requires manual review)
argument-hint: "[optional: written description | enablement | best mode] specification-text claims-text"
allowed-tools:
  - review_specification
  - search_mpep
  - get_mpep_section
model: claude-sonnet-4-5-20250929
---

# Specification Review

Run written-description and enablement heuristics. Best mode is not implemented; a clean result says nothing about it. See [MPEP 2165](https://www.uspto.gov/web/offices/pac/mpep/s2165.html).

**Focus Area:** $ARGUMENTS

## What I'll Check

1. **Written Description (35 USC 112(a))** - Shows you possessed the invention
2. **Enablement (35 USC 112(a))** - Person skilled in art can make/use it
3. **Best Mode (35 USC 112(a))** - Not checked automatically; ask the inventor about their preferred way of carrying out the invention and review the disclosure manually
4. **Claim Support** - All claim elements described

Specified focus area receives extra detail.

## Process

1. Ask for specification (or key sections)
2. Search MPEP for requirements
3. Analyze against 112(a) standards
4. Create claim support matrix
5. Generate report with:
   - Section-by-section analysis
   - MPEP citations
   - Missing disclosures
   - Recommendations

## Output

- Written description adequacy assessment
- Enablement scope analysis
- Claim support matrix
- Specific improvements needed
- MPEP references for findings

---

**DISCLAIMER:** This tool assists with patent application preparation but does NOT replace legal advice from a registered patent attorney. Always consult with legal counsel before filing. Not affiliated with or endorsed by the USPTO.
