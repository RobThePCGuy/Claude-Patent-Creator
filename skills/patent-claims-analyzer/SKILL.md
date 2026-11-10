---
name: patent-claims-analyzer
description: Automated analysis of patent claims for USPTO compliance with 35 USC 112(b) requirements - antecedent basis, definiteness, claim structure
tools: Bash, Read, Write
model: sonnet
---

# Patent Claims Analyzer Skill

Antecedent checking is disabled by default. Report it as skipped unless `checks_run` includes `antecedent_basis`; retain the reason in `checks_skipped`. Enabling `PATENT_ENABLE_ANTECEDENT_CHECK=1` requires a server restart. Even when enabled, this is a low-confidence pattern check requiring manual review.

Automated analysis of patent claims for USPTO compliance with 35 USC 112(b) requirements.

## When to Use

Invoke this skill when users ask to:
- Review patent claims for definiteness
- Check antecedent basis in claims
- Analyze claim structure
- Find claim drafting issues
- Validate claims before filing
- Fix USPTO office action issues related to claims

## What This Skill Does

Performs comprehensive automated analysis:

1. **Antecedent Basis Checking (opt-in)**:
   - Finds terms used without prior introduction
   - Detects missing "a/an" before first use
   - Identifies improper "said/the" before first use
   - Tracks term references across claims

2. **Definiteness Analysis** (35 USC 112(b)):
   - Identifies subjective/indefinite terms
   - Detects relative terms without reference
   - Finds ambiguous claim language
   - Checks for clear claim boundaries

3. **Claim Structure Validation**:
   - Parses independent vs. dependent claims
   - Validates claim dependencies
   - Checks claim numbering
   - Identifies claim type (method, system, etc.)

4. **Issue Categorization**:
   - **Critical**: Must fix before filing
   - **Important**: May cause rejection
   - **Minor**: Best practice improvements

## Required Data

This skill uses the automated claims analyzer from:
**Location**: `${CLAUDE_PLUGIN_ROOT}/mcp_server/claims_analyzer.py` (plugin source; the pip-installed module is `mcp_server.claims_analyzer`)

## How to Use

When this skill is invoked:

1. **Load the claims analyzer**:
   ```python
   import os
   import sys
   sys.path.insert(0, os.environ.get('CLAUDE_PLUGIN_ROOT', '.'))
   from mcp_server.claims_analyzer import ClaimsAnalyzer

   analyzer = ClaimsAnalyzer()
   ```

2. **Analyze claims**:
   ```python
   claims_text = """
   1. A system comprising:
       a processor;
       a memory; and
       said processor configured to...
   """

   results = analyzer.analyze_claims(claims_text)
   ```

3. **Present analysis**:
   - Show compliance score (0-100)
   - List issues by severity (critical, important, minor)
   - Provide MPEP citations for each issue
   - Suggest specific fixes

## Analysis Output Structure

```python
# Issue objects in results["issues"] (illustrative values):
{
    "severity": "IMPORTANT",  # CRITICAL, IMPORTANT, MINOR, or WARNING
    "type": "definiteness",
    "claim": 1,
    "location": "body",
    "term": "approximately",
    "problem": "Potentially unclear term; review in context",
    "fix": "Consider an objective criterion where needed",
    "mpep": "MPEP 2173.05(b)",
    "confidence": "MEDIUM"
}
```

The report also includes `claim_count`, `independent_count`, `dependent_count`,
`compliance_score`, issue counts, `issues_by_type`, and `summary`.
US reports also include `checks_run`, `checks_skipped`, and `compliance_score_scope`.


## Common Issues Detected

1. **Antecedent Basis Errors (only when enabled)**:
   - Using "said/the" before "a/an" introduction
   - Terms appearing in dependent claims not in parent
   - Missing antecedent in claim body

2. **Definiteness Issues**:
   - Subjective terms: "substantially", "about", "approximately"
   - Relative terms: "large", "small", "thin"
   - Ambiguous language: "and/or", "optionally"

3. **Structure Issues**:
   - Means-plus-function and corresponding specification structure require separate manual review; the analyzer does not check them
   - Improper claim dependencies
   - Missing preamble or transition

## Presentation Format

Present analysis as:

```
CLAIMS ANALYSIS REPORT
======================

Summary:
- Total Claims: 20 (3 independent, 17 dependent)
- Compliance Score: 85/100
- Issues Found: 12 (2 critical, 7 important, 3 minor)

CRITICAL ISSUES (Must Fix):

[Claim 1] Antecedent Basis Error
  Issue: Term 'processor' used with 'said' before introduction
  Location: "said processor configured to..."
  MPEP: 2173.05(e)
  Fix: Change to 'the processor' or introduce with 'a processor' first

[Claim 5] Indefinite Term
  Issue: Subjective term 'substantially' without definition
  Location: "substantially similar to..."
  MPEP: 2173.05(b)
  Fix: Define 'substantially' in specification or use objective criteria

IMPORTANT ISSUES:
...

MINOR ISSUES:
...
```

## Integration with MPEP

For each issue, the skill can:
1. Search MPEP for relevant guidance
2. Provide specific MPEP section citations
3. Show examiner guidance on similar issues
4. Suggest fixes based on USPTO practice

## Tools Available

- **Read**: To load claims from files
- **Bash**: To run Python analyzer
- **Write**: To save analysis reports
