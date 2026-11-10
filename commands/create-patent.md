---
description: Draft a complete patent application from invention disclosure through assembly of a draft filing package (markdown + SVG output; DOCX/PDF conversion required before filing)
allowed-tools: Agent, Bash, Read, Write
---

# Create Patent Application

Orchestrates the complete patent application drafting process using autonomous subagents.

## What This Command Does

Orchestrates the complete patent application creation process:

1. **Prior Art Search** (15-30 min)
2. **Claims Drafting** (30-60 min)
3. **Specification Writing** (60-120 min)
4. **Diagrams Generation** (15-30 min)
5. **Compliance Checking** (15-20 min)
6. **Final Assembly** (10-15 min)

**Estimated Time**: 2.5-4.5 hours for complete utility patent application

> **Note:** Time estimates are approximate. Actual duration depends on invention complexity, search depth, and system load. These are not guarantees.

## Process

### Step 1: Gather Invention Information

I'll interview you about your invention:
- What problem does it solve?
- How does it work (high-level)?
- What are the key components or steps?
- What makes it novel/different?
- Are there any working prototypes or examples?

### Step 2: Prior Art Search

I'll use the **Patent Researcher** agent to:
- Conduct systematic 7-step search
- Search Google Patents through SerpApi, or BigQuery if configured
- Identify top 10 most relevant prior art
- Assess patentability (novelty + obviousness)
- Recommend claim strategy

**Deliverable**: Prior art search report with patentability assessment

### Step 3: Draft Claims

I'll use the **Patent Drafter** agent to:
- Write 1-3 independent claims
- Add 10-20 dependent claims
- Distinguish from prior art
- Check antecedent basis and definiteness
- Validate claim structure

**Deliverable**: Complete claims section (20-25 claims)

### Step 4: Write Specification

I'll use the **Patent Drafter** agent to:
- Create title and abstract
- Write field and background sections
- Draft summary of invention
- Write detailed description with embodiments
- Include examples and advantages
- Verify all claims are supported

**Deliverable**: Complete specification (20-50 pages)

### Step 5: Generate Diagrams

I'll use the **Patent Illustrator** agent to:
- Create flowcharts for method claims
- Generate block diagrams for system claims
- Add patent-style reference numbers (10, 20, 30...)
- Export in USPTO-compatible formats

**Deliverable**: 3-10 patent figures (SVG/PNG/PDF)

### Step 6: Compliance Check

I'll validate the application:
- Run claims analyzer (35 USC 112(b))
- Check specification support (35 USC 112(a))
- Verify formalities (MPEP 608)
- Fix any critical issues found

**Deliverable**: Compliance report + fixes

### Step 7: Assemble and Validate Draft Package

**IMPORTANT:** Read `${CLAUDE_PLUGIN_ROOT}/skills/setup-assistant/filing-reference.md` before generating any filing instructions. Do NOT estimate fee amounts from memory -- direct the user to the live USPTO fee schedule. All filing is through Patent Center (not EFS-Web). Spec/claims/abstract must be DOCX format for filing (this workflow outputs markdown; conversion is a manual post-step).

I'll create the draft package:
- Specification document (markdown -- requires DOCX conversion before filing)
- Claims document (markdown -- requires DOCX conversion before filing)
- Abstract (markdown -- requires DOCX conversion before filing)
- Figures (SVG -- requires PDF conversion to black-and-white line art per 37 CFR 1.84 before filing)
- IDS list (U.S. patents/pubs via eIDS -- no copies needed)
- Filing checklist referencing current Patent Center procedures

**Package Validation (hard-fail / soft-fail):**

Before declaring the draft complete, validate the output package:

*Hard-fail conditions (must be resolved before marking drafting complete):*
- Any file listed in the output tree below is missing from disk
- Any reference numeral in a figure is not mentioned in the specification text (37 CFR 1.84(p))
- Any reference numeral in the specification has no corresponding figure element
- Abstract is outside 50-150 word range
- Claims have unresolved CRITICAL compliance issues

*Soft-fail conditions (warn the user, do not block completion):*
- DOCX versions of spec/claims/abstract do not exist (expected -- conversion is a manual post-step)
- PDF versions of figures do not exist (expected -- conversion is a manual post-step)
- IMPORTANT-level compliance issues remain (note in report for user review)

The final status message MUST distinguish between "drafting complete" and "filing-ready":
- **Drafting complete** = all markdown/SVG files produced, validated, no hard-fail issues
- **Filing-ready** = DOCX and PDF conversions done, all documents in Patent Center format (this workflow does NOT achieve this automatically)

**Deliverable**: Draft filing package (markdown + SVG) with validation report

## Output Structure

All files will be organized as:

```
patent-application-[date]/
├── 01-research/
│   ├── invention-disclosure.md
│   ├── prior-art-search-report.md
│   └── patentability-assessment.md
├── 02-claims/
│   ├── claims-draft.md
│   └── claims-final.md
├── 03-specification/
│   └── specification-full.md
├── 04-figures/
│   ├── fig1-[description].svg
│   ├── fig2-[description].svg
│   ├── fig3-[description].svg
│   └── figures-description.md
├── 05-compliance/
│   ├── claims-compliance.md
│   ├── spec-compliance.md
│   └── formalities-check.md
└── 06-filing-package/
    ├── filing-checklist.md
    ├── ids-list.md
    └── validation-report.md
```

> **Note:** Title and abstract are included within `specification-full.md`. Compliance analysis is in `05-compliance/`. DOCX and PDF versions are not produced by this workflow -- convert markdown to DOCX and SVG to PDF as manual post-steps before filing through Patent Center.

## Requirements

Before running this command:

1. **MPEP Index Built**:
   - Run `/setup-patent-system` first (one-time)
   - Or manually: `"$HOME/patent-creator-venv/bin/patent-creator" setup` (Windows: `& "$HOME\patent-creator-venv\Scripts\patent-creator.exe" setup`)

2. **Patent Search Configured**:
   - SerpApi is the default. Save `SERPAPI_API_KEY` with the installed CLI's `config set` command as shown in `/setup-patent-system`.
   - BigQuery is an optional alternative, configured through `/configure-bigquery`.
   - Use `check_google_patents_status` first, then `search_patents_google` when SerpApi is configured. BigQuery is optional: call any `*_bigquery` tool only after `check_bigquery_status` confirms it is available. Without BigQuery, read the returned patent links for details, CPC codes and family members; use Google Patents keyword/CPC queries for follow-up searches. Mark unavailable details, family coverage and classification searches as unverified. If neither provider is configured, explain that patent search needs setup; do not report an empty search as evidence of no prior art.

3. **Graphviz Installed** (for diagrams):
   - Windows: `choco install graphviz`
   - Linux: `sudo apt install graphviz`
   - Mac: `brew install graphviz`

## Options

You can customize the process:

**Type of Application**:
- **Provisional**: Lighter requirements, faster (90-120 min)
- **Utility** (default): Full formal requirements (2.5-4 hours)

**Scope**:
- **Quick**: Minimal claims + specification outline
- **Standard** (default): Complete application
- **Comprehensive**: Multiple embodiments + extensive examples

**Prior Art Depth**:
- **Basic**: Keywords only (15 min)
- **Standard** (default): 7-step methodology (30 min)
- **Thorough**: Extended CPC search (60 min)

**Execution Mode**:
- **Autonomous** (default): Runs all phases without interruption; delivers complete draft at the end
- **Guided**: Pauses for your review at four checkpoints:
  1. After prior art search -- review patentability assessment before proceeding
  2. After claims drafting -- review claim scope and structure
  3. After specification -- review completeness and accuracy
  4. Before final assembly -- review figures and compliance before packaging

## Example Usage

```
/create-patent

> I'll guide you through creating a patent application.
>
> What type of application?
> 1. Provisional (faster, lighter requirements)
> 2. Utility (complete draft, formal requirements)
>
> [Select option]
>
> Tell me about your invention...
> [You describe your invention]
>
> [I'll proceed through all 7 steps...]
```

## Tips

- **Prepare in advance**: Have invention description ready
- **Be specific**: More detail = better patent
- **Review drafts**: By default, the workflow runs autonomously. Request "guided mode" for review gates at key checkpoints (see Options)
- **Ask questions**: Any time during the process
- **Save frequently**: Each section saved as we complete it

## What You'll Have at the End

A complete draft patent application package in markdown and SVG format, including:
- Prior art search with top references
- Patentability assessment (preliminary -- see caveats in report)
- 8-20+ claims (validated for 112(b))
- Multi-page specification (validated for 112(a))
- 3-10 technical figures with reference numbers (SVG format)
- Abstract (50-150 words)
- IDS list for USPTO disclosure
- Compliance reports (all critical checks passed)
- Validation report confirming output completeness

## What Still Requires Manual Steps

After this workflow completes, the following steps remain before filing:
1. **Convert specification, claims, and abstract from markdown to DOCX** (use pandoc or Microsoft Word) -- Patent Center requires DOCX; non-DOCX format triggers a surcharge
2. **Convert SVG figures to black-and-white PDF** (per 37 CFR 1.84) -- use Inkscape, a browser, or similar tool
3. **Human review** of all drafted content for technical accuracy
4. **Attorney review** recommended before filing (prior art assessment is preliminary, not a legal opinion)
5. **File through Patent Center** (patentcenter.uspto.gov) -- see filing checklist for current procedures
6. **Pay filing fees** -- see the live USPTO fee schedule (fees change periodically; this tool does not estimate amounts)

## Next Steps After Command

1. **Review** the draft application for accuracy
2. **Make edits** if needed (I can help)
3. **Convert** to DOCX/PDF for filing (see above)
4. **File** through Patent Center
5. **Respond to office actions** (I can help with that too)
