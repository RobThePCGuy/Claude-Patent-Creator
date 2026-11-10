---
description: Create a complete EPO-compliant patent application from invention disclosure through filing-ready package
allowed-tools: Bash, Read, Write
---

# Create EPO Patent Application

Guides you through creating a complete European patent application compliant with the EPC.

## What This Command Does

Orchestrates the complete EPO patent application creation process:

1. **Prior Art Search** (15-30 min)
2. **Claims Drafting** (30-60 min)
3. **Specification Writing** (60-120 min)
4. **Diagrams Generation** (15-30 min)
5. **EPO Compliance Checking** (15-20 min)
6. **Final Assembly** (10-15 min)

**Total Time**: 2.5-4.5 hours for complete EP utility patent application

## Process

### Step 1: Gather Invention Information

I'll interview you about your invention:
- What problem does it solve?
- How does it work (high-level)?
- What are the key components or steps?
- What makes it novel/different from the closest prior art?
- Are there any working prototypes or examples?
- Is this a direct EP filing or Euro-PCT national phase entry?

### Step 2: Prior Art Search

I'll search for relevant prior art using:
- **Google Patents via SerpApi** (default, use `country="EP"`); BigQuery is optional
- **EPO OPS API** (European patent register, full-text EP documents)
- **CPC classification** search focused on EPO-heavy technology areas

**Deliverable**: Prior art search report with novelty/inventive step assessment

### Step 3: Draft Claims (EPO Format)

I'll draft claims following EPO requirements:

**Independent Claims** (Rule 43(1) EPC):
- Two-part form: preamble + "characterised in that" + characterizing portion
- Based on closest prior art identified in Step 2
- Clear, concise, supported by description (Art. 84 EPC)

**Dependent Claims**:
- Proper back-references
- Further technical features
- Fallback positions for prosecution

**Claim Categories**:
- Product/apparatus claims
- Method/process claims
- Use claims (where appropriate)
- No method-of-treatment claims (Art. 53(c) EPC)

**Deliverable**: Complete claims section (15-25 claims, EPO two-part form)

### Step 4: Write Specification (Rule 42 EPC)

I'll write the description following EPO section order:

1. **Title** - Clear, concise, matches claims scope
2. **Technical Field** - Art to which the invention relates
3. **Background Art** - Prior art documents with citations (D1, D2...)
4. **Technical Problem** - Problem-solution approach (EPO standard)
5. **Disclosure of the Invention** - How the invention solves the problem
6. **Brief Description of Drawings** - Figure list
7. **Detailed Description** - At least one embodiment in detail
8. **Industrial Applicability** - If not obvious from description

**Key EPO Differences**:
- Problem-solution approach is central
- Prior art must be cited in description
- Best mode not strictly required (unlike USPTO)
- Industrial applicability section may be needed
- Reference signs in claims correspond to description/drawings

**Deliverable**: Complete specification (20-50 pages, EPO format)

### Step 5: Generate Diagrams

I'll create patent figures following Rule 46 EPC:
- No text in drawings (except single words like "water", "steam")
- Reference numbers matching description
- A4 format with EPO margin requirements
- Black lines, sufficiently dense

**Deliverable**: 3-10 patent figures (SVG/PNG)

### Step 6: EPO Compliance Check

I'll validate the complete application:
- Run EPO claims analysis (Art. 84 EPC - clarity, conciseness, support)
- Check description format (Rule 42 EPC)
- Verify formalities (Rules 42-49 EPC)
- Check for excluded subject matter (Art. 52(2), Art. 53 EPC)
- Fix any critical issues found

**Deliverable**: EPO compliance report + fixes

### Step 7: Assemble Filing Package

I'll create the final EP filing package:
- Description (Rule 42 format)
- Claims (Rule 43 two-part form)
- Abstract (Rule 47, max 150 words)
- Drawings (Rule 46 compliant)
- Request for Grant (Form 1001 guidance)
- Priority document references
- Fee calculation

**Deliverable**: EPO-ready filing package

## Output Structure

All files will be organized as:

```
epo-patent-application-[date]/
├── 01-research/
│   ├── invention-disclosure.md
│   ├── prior-art-search-report.md
│   ├── top-10-patents.md
│   ├── novelty-assessment.md
│   └── inventive-step-assessment.md
├── 02-claims/
│   ├── claims-draft.md
│   ├── claims-final.md
│   ├── claims-two-part-form.md
│   └── claims-analysis.md
├── 03-specification/
│   ├── title-abstract.md
│   ├── specification-full.md
│   ├── problem-solution.md
│   └── specification-analysis.md
├── 04-figures/
│   ├── fig1-system-diagram.svg
│   ├── fig2-method-flowchart.svg
│   ├── fig3-component-detail.svg
│   └── figures-description.md
├── 05-compliance/
│   ├── art84-claims-compliance.md
│   ├── rule42-description-compliance.md
│   ├── formalities-check.md
│   └── excluded-subject-matter-check.md
└── 06-filing-package/
    ├── complete-application.md
    ├── form-1001-guidance.md
    ├── fee-calculation.md
    ├── priority-references.md
    └── filing-checklist.md
```

## Requirements

Before running this command:

1. **MPEP/EPC Index Built**:
   - Run `/setup-patent-system` first (one-time)

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

**Filing Route**:
- **Direct EP**: File directly at EPO
- **Euro-PCT**: Enter European regional phase from PCT application

**Scope**:
- **Quick**: Minimal claims + specification outline
- **Standard** (default): Complete application
- **Comprehensive**: Multiple embodiments + extensive examples

**Prior Art Depth**:
- **Basic**: Keywords only (15 min)
- **Standard** (default): Keywords + CPC + EPO OPS (30 min)
- **Thorough**: Extended CPC search + patent family analysis (60 min)

## Example Usage

```
/create-epo-patent

> I'll guide you through creating an EPO patent application.
>
> Filing route?
> 1. Direct EP filing
> 2. Euro-PCT national phase entry
>
> [Select option]
>
> Tell me about your invention...
> [You describe your invention]
>
> [I'll proceed through all 7 steps...]
```

## What You'll Have at the End

A complete, EPO-ready patent application package including:
- Prior art search with EP-focused results
- Novelty and inventive step assessment (EPO problem-solution approach)
- 15-25 claims in two-part form (validated for Art. 84 EPC)
- 20-50 page specification in Rule 42 EPC format
- 3-10 figures compliant with Rule 46 EPC
- Abstract (max 150 words, Rule 47 EPC)
- Form 1001 guidance and fee calculation
- Compliance reports (all EPO checks passed)
- Complete filing package ready to submit

## Next Steps After Command

1. **Review** complete application with European Patent Attorney
2. **File** via EPO Online Filing (eOLF) or postal
3. **Pay** filing and search fees (within 1 month)
4. **Receive** European search report (typically 6-12 months)
5. **Request examination** (within 6 months of search report publication)
6. **Respond** to examination communications (I can help with that too)

## Tips

- **Problem-solution approach**: Central to EPO prosecution - frame everything around the technical problem and its solution
- **Two-part form**: Identify closest prior art early and structure claims accordingly
- **No method-of-treatment**: Unlike USPTO, EPO excludes methods of treatment (Art. 53(c))
- **Technical effect for software**: Computer-implemented inventions must show "further technical effect"
- **Cite prior art in description**: EPO requires prior art references in the background section

---

**DISCLAIMER:** This tool assists with patent application preparation but does NOT replace legal advice from a registered European Patent Attorney. Always consult with legal counsel before filing. Not affiliated with or endorsed by the EPO.
