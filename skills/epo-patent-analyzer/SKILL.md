---
name: epo-patent-analyzer
description: Automated analysis of patent applications for EPO compliance with Art. 84 EPC (claims clarity/support), Art. 83 EPC (sufficiency of disclosure), and Rules 42-49 EPC (formalities)
tools: Bash, Read, Write
model: sonnet
---

# EPO Patent Analyzer Skill

The formalities tool receives text and a drawings-present flag, not page or drawing files. Physical layout, margins, paper size, line spacing, drawing quality, request forms, and payments are not inspected. Mark them NOT CHECKED until a separate review of the final documents or records supplies evidence. Report only checks actually run; the checklist below is not a prefilled result.

Automated analysis of patent applications for European Patent Office compliance under the European Patent Convention (EPC).

## When to Use

Invoke this skill when users ask to:
- Review patent claims for EPO Art. 84 compliance
- Check sufficiency of disclosure under Art. 83 EPC
- Analyze EPO formalities under Rules 42-49 EPC
- Convert USPTO-style claims to EPO two-part form
- Prepare for EPO examination or respond to EPO communications
- Validate applications before EP filing or Euro-PCT entry

## What This Skill Does

Performs comprehensive EPO-focused analysis:

1. **Claims Analysis** (Art. 84 EPC):
   - Clarity: identifies unclear or ambiguous terms
   - Conciseness: detects redundant or overlapping claims
   - Support: not assessed by the claims-only analyzer; obtain the description, run `review_epo_specification` for preliminary heuristics, and review each feature manually
   - Two-part form (Rule 43(1) EPC): checks preamble + "characterised in that"
   - Claim categories: product, process, apparatus, use
   - Excluded subject matter: Art. 52(2) and Art. 53 EPC

2. **Sufficiency of Disclosure** (Art. 83 EPC):
   - Reproducibility: can a person skilled in the art reproduce the invention?
   - Breadth of claims vs disclosure: is the full scope enabled?
   - Essential technical features: all present and described?
   - Working examples: at least one concrete embodiment?

3. **Formalities** (Rules 42-49 EPC):
   - Description format (Rule 42): required sections in correct order
   - Claims form (Rule 43): two-part form, numbering, references
   - Drawings (Rule 49(2) and the President's decision): manual inspection of margins, indispensable keywords, and reference signs
   - Abstract (Rule 47): preferably no more than 150 words, figure designation
   - Physical requirements: A4, margins, fonts

4. **Issue Categorization**:
   - **Critical**: Will cause objection under EPC
   - **Important**: May cause objection or limit scope
   - **Minor**: Best practice per EPO Guidelines

## Required Data

This skill uses the EPO compliance analyzers and the EPC/EPO Guidelines search:

**MCP Tools Available**:
- `review_epo_claims` - Art. 84 EPC compliance checking
- `review_epo_specification` - Art. 83 EPC sufficiency analysis
- `check_epo_formalities` - Rules 42-49 EPC formalities
- `search_patent_law` - Search EPC, EPO Guidelines, PCT rules

## How to Use

When this skill is invoked:

1. **Determine analysis scope**:
   - Full application review (claims + description + formalities)
   - Claims-only review (Art. 84 EPC)
   - Sufficiency-only review (Art. 83 EPC)
   - Formalities-only review (Rules 42-49 EPC)

2. **Run appropriate analyzers**:
   - For claims: check clarity, conciseness, and two-part form; description support requires separate review
   - For sufficiency: check reproducibility, scope vs disclosure, examples
   - For formalities: run the available text heuristics and list manual checks

3. **Present analysis**:
   - Show compliance score (0-100)
   - List issues by severity (critical, important, minor)
   - Provide EPC article/rule citations for each issue
   - Reference EPO Guidelines sections
   - Suggest specific fixes

## Analysis Output Structure

```python
# Issue objects in results["issues"] (illustrative values):
{
    "severity": "IMPORTANT",  # CRITICAL, IMPORTANT, MINOR, or WARNING
    "type": "clarity",
    "claim": 1,
    "location": "body",
    "term": "approximately",
    "problem": "Potentially unclear term; review in context",
    "fix": "Consider an objective criterion where needed",
    "legal_ref": "Art. 84 EPC",
    "confidence": "MEDIUM"
}
```

The report also includes `claim_count`, `independent_count`, `dependent_count`,
`compliance_score`, issue counts, `issues_by_type`, and `summary`.


## Common EPO Issues Detected

1. **Clarity Issues (Art. 84 EPC)**:
   - Relative terms without objective reference
   - Inconsistent terminology between claims and description
   - Functional features not clearly defined
   - "Means for" language without clear structural support

2. **Support Issues (Art. 84 EPC), separate description review required**:
   - Claims broader than description discloses
   - Unsupported generalizations from specific examples
   - Missing essential technical features
   - Claim scope exceeding experimental evidence

3. **Sufficiency Issues (Art. 83 EPC)**:
   - Insufficient detail for reproduction
   - Claims too broad relative to examples
   - Missing critical parameters or conditions
   - Undue burden on skilled person

4. **Formality Issues (Rules 42-49 EPC)**:
   - Missing required description sections
   - Abstract exceeding the preferred 150 words (advisory)
   - Non-indispensable text in drawings (manual inspection)
   - Claims not in two-part form where appropriate

## Presentation Format

Present analysis as:

```
EPO COMPLIANCE ANALYSIS REPORT
================================

Jurisdiction: European Patent Office (EPC)
Analysis Date: [Date]

Summary:
- Total Claims: 15 (2 independent, 13 dependent)
- Compliance Score: 72/100
- Issues Found: 8 (2 critical, 4 important, 2 minor)

CLAIMS ANALYSIS (Art. 84 EPC):

  Clarity:
  [Claim 1] CRITICAL - "substantially uniform" lacks objective definition
    Art. 84 EPC / EPO Guidelines F-IV, 4.6
    Fix: Define with measurable criterion (e.g., "within 5% deviation")

  Support (manual review with description, not claims-tool output):
  [Claim 3] IMPORTANT - "any wireless protocol" exceeds disclosure
    Art. 84 EPC / EPO Guidelines F-IV, 6.2
    Fix: Limit to disclosed protocols (Bluetooth, Wi-Fi, NFC)

  Two-Part Form:
  [Claim 1] REVIEW - Not in two-part form; assess appropriateness before rewriting
    Rule 43(1) EPC / EPO Guidelines F-IV, 2.2-2.3
    If appropriate: identify closest prior art and split known and distinguishing features

SUFFICIENCY ANALYSIS (Art. 83 EPC):

  [PASS] At least one embodiment fully described
  [WARN] Claims 8-10 cover embodiment not exemplified
    Art. 83 EPC / EPO Guidelines F-III, 3
    Consider: Add working example for thermal processing variant

FORMALITIES (Rules 42-49 EPC):

  [PASS] Description sections in correct order (Rule 42)
  [WARN] Abstract: 167 words (preferably no more than 150 words) (Rule 47)
  [NOT CHECKED] Drawings: indispensable keywords and proper margins (Rule 49(2) and the President's decision); inspect final pages/drawings manually
  [FAIL] No figure designated for abstract (Rule 47(4))
```

## Key EPO vs USPTO Differences

| Aspect | USPTO (35 USC) | EPO (EPC) |
|--------|----------------|-----------|
| Claim clarity | Reasonable certainty (112(b)) | Strict objective clarity (Art. 84) |
| Claim form | Open format | Two-part form where appropriate (Rule 43) |
| Support | Written description (112(a)) | Supported by description (Art. 84) |
| Enablement | Enable POSITA (112(a)) | Sufficiency of disclosure (Art. 83) |
| Best mode | Required (112(a)) | Not required |
| Terms of degree | Allowed with spec support | Must have objective reference |
| Software | Patent-eligible if technical | Must show "further technical effect" |
| Medical methods | Allowed | Excluded (Art. 53(c)) |
| Novelty | 102 (1-year grace period) | Art. 54 (absolute novelty, no grace period) |
| Obviousness | 103 (obvious to POSITA) | Art. 56 (inventive step, problem-solution) |

## Integration with EPC Search

For each issue, the skill can:
1. Search EPC provisions and EPO Guidelines for relevant guidance
2. Provide specific article, rule, and Guidelines section citations
3. Show EPO Board of Appeal case law on similar issues
4. Suggest fixes based on EPO prosecution practice

## Tools Available

- **Read**: To load application from files
- **Bash**: To run EPO compliance analyzers
- **Write**: To save analysis reports

Legal references: [EPC Rule 47](https://www.epo.org/en/legal/epc/2020/r47.html), [two-part form where appropriate](https://www.epo.org/en/legal/guidelines-epc/2026/f_iv_2_3.html), [Rule 49(2)](https://www.epo.org/en/legal/epc/2020/r49.html), and [President's presentation decision, OJ EPO 2025 A49](https://www.epo.org/en/legal/official-journal/2025/07/a49). Rule 46 was deleted effective 1 February 2023.
