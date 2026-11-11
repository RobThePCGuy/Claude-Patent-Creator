---
description: Conduct comprehensive prior art search using 7-step methodology across 100M+ patents (Google Patents via SerpApi, or BigQuery) and research papers
allowed-tools: Bash, Read, Write
---

# Search for Prior Art

Professional patent prior art search with patentability assessment.

## What This Command Does

Executes a systematic 7-step prior art search methodology:

1. **Invention Definition** (2-3 min) - Extract key features
2. **Keyword Strategy** (2-3 min) - Build search terms
3. **Broad Search** (3-5 min) - Cast wide net
4. **CPC Identification** (2-3 min) - Find classifications
5. **Deep CPC Search** (5-10 min) - Thorough classification search
6. **Timeline Analysis** (2-3 min) - Technology evolution
7. **Patentability Report** (5-10 min) - Assessment + recommendations

**Total Time**: 25-45 minutes for thorough search

## Who This Is For

- Inventors before filing
- Patent attorneys/agents
- Companies conducting due diligence
- Researchers checking novelty
- Anyone assessing patentability

## Process

### Step 1: Tell Me About Your Invention

I'll ask you:
- What problem does it solve?
- How does it work?
- What are the key features?
- What makes it novel?

Example:
```
> Describe your invention...

User: A blockchain-based authentication system that uses
distributed ledger verification instead of centralized
password databases.

> Got it. Key features I extracted:
> - Blockchain technology
> - Authentication/verification
> - Distributed ledger
> - No centralized database
>
> Is this correct? Any other key features?
```

### Step 2: Keyword Search

I'll search 100M+ patents with Google Patents (`search_patents_google`, free SerpApi key) or, if that isn't set up and BigQuery is, `search_patents_bigquery`, using keywords derived from your description. I'll also search research papers published before your priority date (`search_non_patent_literature`). If no patent search is set up, I'll point you to the free key (README Quick Start, Step 3) and meanwhile run a quick web first screen of Google Patents. I'll label it as that: it can show close patents exist, but it can't show that none do, so the report gives no novelty or patentability verdict until real patent search runs.

```python
# I'll run searches like:
"blockchain authentication"
"distributed ledger verification"
"decentralized identity"
"cryptographic authentication"
```

I'll review 20-30 results per query and identify the most relevant patents.

### Step 3: CPC Classification Search

I'll:
- Extract CPC codes from relevant patents found
- Identify primary classification areas
- Search thoroughly within those classifications

Common CPC codes:
- G06F: Computing/data processing
- H04L: Digital communication
- G06Q: Business methods
- G06N: AI/neural networks

### Step 4: Timeline Analysis

I'll analyze:
- When was this technology first patented?
- How has it evolved over time?
- What are recent developments (last 2 years)?
- Are there filing trends?

### Step 5: Patentability Assessment

I'll evaluate:

**Novelty (35 USC 102)**:
- Is there an exact match in prior art?
- What are the differences?
- Novelty Score: High/Medium/Low

**Non-Obviousness (35 USC 103)**:
- Could references be combined?
- Is there motivation to combine?
- Are there unexpected results?
- Obviousness Risk: High/Medium/Low

### Step 6: Generate Report

I'll create a comprehensive report with:
- Executive summary
- Top 10 most relevant prior art (ranked)
- Detailed analysis of each reference
- Patentability assessment
- Claim strategy recommendations
- IDS list for USPTO filing

## Report Structure

```markdown
# PRIOR ART SEARCH REPORT

## Executive Summary
- Invention: [Description]
- Searcher: Claude Patent Creator
- Date: [Date]
- Databases: Google Patents (SerpApi) or BigQuery, whichever is set up, plus research papers
- Conclusion: [Patentability assessment]

## Patentability Assessment

### Novelty (35 USC 102): HIGH/MEDIUM/LOW
[Detailed analysis]

### Non-Obviousness (35 USC 103): HIGH/MEDIUM/LOW
[Detailed analysis]

## Top 10 Most Relevant Prior Art

### 1. US10123456B2 - [Title] (Relevance: 95%)
**Assignee**: Example Corp
**Filed**: 2018-03-15 | **Granted**: 2019-09-30
**CPC**: G06F21/31, H04L29/06

**Abstract**: [Summary]

**Similarities**:
- [List similarities]

**Differences**:
- [Key differences from your invention]

**Analysis**: [Why this is or isn't blocking]

---

[Continue for all top 10]

## Search Methodology

### Keywords Used
- Primary: [list]
- Synonyms: [list]
- Technical: [list]

### CPC Codes Searched
- [Code 1]: [Description]
- [Code 2]: [Description]

### Search Statistics
- Total patents reviewed: 336
- Relevant patents found: 47
- Top prior art selected: 10

## Claim Strategy Recommendations

### Recommended Approach
1. Focus on: [Novel aspects]
2. Avoid: [Prior art areas]
3. Emphasize: [Differentiating features]

### Suggested Independent Claim
```
A system for [invention], comprising:
   [novel element 1];
   [novel element 2];
   wherein [novel relationship]
```

## IDS List (For USPTO Filing)

1. US10123456B2
2. US10234567A1
3. US10345678B1
...
[Complete list]

## Conclusion

[Overall patentability assessment and next steps]
```

## Output Files

All results saved to:
```
prior-art-search-[date]/
├── search-report.md              # Complete report
├── top-10-patents.md             # Detailed top 10 analysis
├── ids-list.md                   # USPTO disclosure list
├── claim-strategy.md             # Recommendations
└── search-data/
    ├── keyword-results.json      # Raw keyword search results
    ├── cpc-results.json          # Raw CPC search results
    └── timeline-analysis.json    # Filing trends data
```

## Requirements

**Must Have** (one of):
1. **A free SerpApi key** (recommended): README Quick Start, Step 3.
2. **BigQuery**: a Google Cloud project, `gcloud auth application-default login`, and `~/patent-creator-venv/bin/patent-creator config set GOOGLE_CLOUD_PROJECT your-project-id`. Needed for the CPC classification step; without it that step runs as keyword searches and the report says so.

**Optional**:
- USPTO API key (for additional coverage)

## Search Depth Options

**Quick Search** (15-20 min):
- Steps 1-3 only
- Keyword search only
- Basic patentability check

**Standard Search** (25-35 min, default):
- All 7 steps
- Keyword + CPC search
- Full patentability assessment

**Thorough Search** (45-60 min):
- Extended CPC search
- Multiple classification areas
- Historical analysis
- Competitive landscape

## After the Search

Based on the results, I can help you:

1. **High Patentability**:
   - Proceed with `/create-patent` command
   - Draft claims distinguishing from prior art
   - File patent application

2. **Medium Patentability**:
   - Refine invention to avoid prior art
   - Narrow scope to novel aspects
   - Consider provisional filing while developing

3. **Low Patentability**:
   - Identify what needs to change
   - Find white space opportunities
   - Consider alternative IP strategies

## Example Usage

```
/search-prior-art

> Tell me about your invention in detail...

User: I have an AI system that uses neural networks to
diagnose medical conditions from X-ray images. It uses
a custom CNN architecture with attention mechanisms...

> Got it. I'll search for prior art related to:
> - AI medical diagnosis
> - Neural networks for X-ray analysis
> - CNN architectures
> - Attention mechanisms in medical imaging
>
> Starting 7-step search process...
>
> [Step 1] Defined invention features: [list]
> [Step 2] Built keyword strategy: [queries]
> [Step 3] Broad search found 47 relevant patents
> [Step 4] Identified CPC codes: G06N3/08, A61B6/00, G06T7/00
> [Step 5] Deep CPC search reviewing 150 patents...
> [Step 6] Timeline analysis complete
> [Step 7] Generating comprehensive report...
>
> SEARCH COMPLETE
>
> Patentability Assessment:
> - Novelty: MEDIUM (no exact matches, similar approaches exist)
> - Non-Obviousness: MEDIUM-HIGH (custom architecture is novel)
>
> Top blocking patent: US10234567 (85% similar)
> Key difference: Your attention mechanism approach
>
> Recommendation: PROCEED with patent filing
> Focus claims on: Custom attention mechanism architecture
>
> Full report saved to: prior-art-search-2024-01-15/
```

## Tips for Best Results

1. **Be Specific**: More detail = better search
2. **Include Alternatives**: Mention different approaches you considered
3. **Technical Terms**: Use industry-standard terminology
4. **Context**: Explain what problem you're solving
5. **Scope**: Define how broadly you want coverage

## Next Steps

After receiving your search report:

1. **Review** the top 10 prior art
2. **Assess** patentability conclusions
3. **Decide** whether to proceed with patent filing
4. **Use** `/create-patent` if patentability is favorable
5. **Refine** invention if needed based on findings
