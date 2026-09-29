---
description: Analyze patent claims for 35 USC 112(b) compliance - antecedent basis, definiteness, and claim structure
allowed-tools: Bash, Read, Write
---

# Review Patent Claims

Automated analysis of patent claims for USPTO compliance with detailed issue reporting and fixes.

## What This Command Does

Performs comprehensive automated claims analysis:

1. **Antecedent Basis Checking**:
   - Finds terms used without prior introduction
   - Detects "said/the" used before "a/an"
   - Tracks term usage across claims

2. **Definiteness Analysis** (35 USC 112(b)):
   - Identifies subjective/indefinite terms
   - Detects relative terms without reference
   - Finds ambiguous language

3. **Claim Structure Validation**:
   - Parses independent vs. dependent claims
   - Validates dependencies
   - Checks claim numbering

4. **Issue Categorization**:
   - **Critical**: Must fix before filing
   - **Important**: May cause rejection
   - **Minor**: Best practice improvements

## Who This Is For

- Patent attorneys reviewing draft claims
- Inventors before filing
- Responding to 112(b) office action rejections
- Quality assurance before USPTO submission

## Process

### Step 1: Provide Claims

You can provide claims in three ways:

**Option 1: Paste claims directly**
```
/review-claims

> Paste your claims text, then type 'END' on a new line:

What is claimed is:

1. A system comprising:
    a processor;
    a memory; and
    said processor configured to execute instructions.

END
```

**Option 2: Point to a file**
```
/review-claims path/to/claims.txt
```

**Option 3: Let me read from current conversation**
```
[You paste claims in chat]

/review-claims --from-context
```

### Step 2: Automated Analysis

I'll run the claims through the automated analyzer:

```python
from mcp_server.claims_analyzer import ClaimsAnalyzer
analyzer = ClaimsAnalyzer()
results = analyzer.analyze_claims(claims_text)
```

This checks:
- All terms for antecedent basis
- All language for definiteness
- Claim structure and dependencies
- Cross-references and pointers

### Step 3: Generate Report

I'll provide a detailed compliance report with:
- Overall compliance score (0-100)
- Issue count by severity
- Specific issues with locations
- MPEP citations
- Suggested fixes

### Step 4: Fix Issues (Optional)

For each critical/important issue, I can:
- Show the problematic text
- Explain why it's an issue
- Suggest specific fix
- Apply fix if you approve

## Report Structure

```
CLAIMS COMPLIANCE REPORT
========================

Summary:
--------
- Total Claims: 20 (3 independent, 17 dependent)
- Compliance Score: 72/100
- Total Issues: 15 (3 critical, 8 important, 4 minor)

Recommendation: FIX CRITICAL ISSUES BEFORE FILING

CRITICAL ISSUES (Must Fix):
===========================

[Claim 1, Line 3] Antecedent Basis Error
-----------------------------------------
Issue: Term 'processor' used with 'said' before first introduction

Location:
  "said processor configured to execute instructions"
   ^^^^

Problem:
  The term "processor" is used with "said" but was not previously
  introduced with "a" or "an". This violates 35 USC 112(b).

MPEP Citation: MPEP § 2173.05(e) - Antecedent Basis

Fix Suggestion:
  Change "said processor" to "the processor" since it was
  introduced with "a processor" earlier in the claim.

  BEFORE: "said processor configured to..."
  AFTER:  "the processor configured to..."

---

[Claim 5, Line 2] Indefinite Term
----------------------------------
Issue: Subjective term "substantially" without definition

Location:
  "substantially similar to the reference data"
   ^^^^^^^^^^^^

Problem:
  The term "substantially" is subjective and may render the
  claim indefinite under 35 USC 112(b). What degree of
  similarity is "substantial"?

MPEP Citation: MPEP § 2173.05(b) - Subjective Terms

Fix Suggestions:
  Option 1: Define in specification
    Add to spec: "As used herein, 'substantially similar'
    means having at least 95% similarity..."

  Option 2: Use objective criteria
    Change to: "having at least 95% similarity to..."

  Option 3: Remove subjectivity
    Change to: "matching the reference data"

---

[Continue for all critical issues...]

IMPORTANT ISSUES (Should Fix):
==============================

[Claim 3] Weak Antecedent
-------------------------
Issue: Term introduced with "the" instead of "a"

Location: "the communication interface"

While not necessarily indefinite, USPTO examiners prefer
"a communication interface" for first introduction.

Suggested Fix: Change "the" to "a"

---

[Continue for all important issues...]

MINOR ISSUES (Consider Fixing):
===============================

[Claim 10] Style Issue
---------------------
Issue: Using "and/or" can be ambiguous

Location: "processor and/or controller"

While not indefinite, "and/or" can lead to claim
interpretation issues. Consider being more specific.

Suggested Fix: Choose "processor or controller" or
"processor, controller, or both"

---

[Continue for all minor issues...]

CLAIM STRUCTURE ANALYSIS:
=========================

Independent Claims:
  - Claim 1 (system claim): OK
  - Claim 8 (method claim): OK
  - Claim 15 (apparatus claim): OK

Dependent Claims:
  - Claims 2-7 depend from Claim 1: OK
  - Claims 9-14 depend from Claim 8: OK
  - Claims 16-20 depend from Claim 15: OK

Dependency Chain: VALID (no circular dependencies)

MPEP GUIDANCE:
==============

Relevant MPEP Sections:
- MPEP § 2173.05(e) - Antecedent Basis
- MPEP § 2173.05(b) - Subjective Terms
- MPEP § 2111 - Claim Definiteness
- MPEP § 608.01(n) - Antecedent Basis Requirements

NEXT STEPS:
===========

1. FIX all 3 critical issues (required before filing)
2. REVIEW all 8 important issues (recommended fixes)
3. CONSIDER 4 minor issues (optional improvements)
4. RE-RUN analysis after fixes to verify compliance
```

## Interactive Fixing

After the report, I can interactively help you fix issues:

```
> Found 3 critical issues. Would you like me to help fix them?

Yes

> Issue 1/3: [Claim 1] Antecedent basis error
>
> Current: "said processor configured to..."
> Suggested: "the processor configured to..."
>
> Apply this fix? (y/n/skip)

y

> Fix applied. Issue 2/3...
```

## Output Files

Results saved to:
```
claims-review-[date]/
├── analysis-report.md          # Full compliance report
├── critical-issues.md          # Critical issues only
├── suggested-fixes.md          # All suggested fixes
├── claims-original.txt         # Your original claims
├── claims-fixed.txt           # Fixed version (if requested)
└── mpep-citations.md          # Relevant MPEP sections
```

## Analysis Capabilities

### Antecedent Basis Checking

Detects:
- Missing "a/an" before first use
- "Said/the" used before introduction
- Terms in dependent claims not in parent
- Inconsistent term usage

Example:
```
WRONG: "A system comprising a processor and said memory"
       (memory not introduced)

RIGHT: "A system comprising a processor and a memory"
```

### Definiteness Analysis

Detects:
- Subjective terms: "substantially", "about", "approximately"
- Relative terms: "large", "small", "thin", "fast"
- Ambiguous language: "and/or", "optionally"
- Vague references: "suitable", "appropriate"

Example:
```
INDEFINITE: "a substantially planar surface"
BETTER:     "a surface having a flatness tolerance of < 0.1mm"
```

### Means-Plus-Function

Detects:
- Means-plus-function elements
- Checks for corresponding structure in specification

Example:
```
"means for processing data"
→ Requires specification to disclose structure for processing
```

## Compliance Score

**90-100**: Excellent - Ready to file
**75-89**: Good - Minor issues to address
**60-74**: Fair - Important issues to fix
**< 60**: Poor - Critical issues must be fixed

## Requirements

**Python Environment**:
- Python 3.9+
- Access to ${CLAUDE_PLUGIN_ROOT}
- Claims analyzer module

**No external dependencies** - runs locally

## After Analysis

Based on your compliance score:

**90+**:
- Claims are USPTO-ready
- Proceed with filing

**75-89**:
- Review important issues
- Consider fixes
- Re-analyze after changes

**60-74**:
- Fix critical issues (required)
- Address important issues (recommended)
- Re-analyze to verify

**< 60**:
- Significant revision needed
- Fix all critical and important issues
- Consider claim restructuring

## Example Usage

```
/review-claims

> Paste your claims text, then type 'END' on a new line:

What is claimed is:

1. A blockchain authentication system comprising:
    a distributed ledger configured to store credentials;
    a processor in communication with said distributed ledger;
    wherein said processor is configured to verify user identity.

2. The system of claim 1, wherein the credentials are encrypted.

END

> Analyzing claims...
>
> ANALYSIS COMPLETE
>
> Compliance Score: 85/100 (Good)
> Issues Found: 2 (0 critical, 2 important, 0 minor)
>
> IMPORTANT ISSUES:
>
> [Claim 1] Term "credentials" introduced with "the" in claim 2
>   but first appears in claim 1
>   Suggestion: Ensure "credentials" is clearly introduced
>
> [Claim 1] "verify user identity" - consider more specific language
>   "identity" can be ambiguous
>   Suggestion: Define what constitutes identity verification
>
> Overall: Claims are in good shape. Address the 2 important
> issues for stronger protection.
>
> Full report saved to: claims-review-2024-01-15/
```

## Tips

1. **Run early**: Check claims during drafting, not just before filing
2. **Iterate**: Fix issues and re-analyze
3. **Understand why**: Read MPEP citations to learn
4. **Be specific**: More specific = less indefinite
5. **Consistent terms**: Use same terminology throughout

## Integration

This command uses:
- **Claims Analyzer** skill for automated checking
- **MPEP Expert** agent for legal guidance (if needed)
- **Patent Drafter** agent for fixing issues (if requested)
