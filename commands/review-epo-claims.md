---
description: Analyze patent claims for EPO Art. 84 EPC compliance - clarity and conciseness heuristics; description support requires separate review
argument-hint: "[optional: clarity | conciseness | support] claims-text"
allowed-tools:
  - review_epo_claims
  - search_patent_law
  - search_mpep
model: claude-sonnet-4-5-20250929
---

# EPO Claims Review

Automated analysis of patent claims for European Patent Office compliance with Art. 84 EPC / Rule 43 EPC / EPO Guidelines Part F.

**Focus Area:** $ARGUMENTS

## What This Command Does

Performs comprehensive EPO claims analysis:

1. **Clarity Analysis** (Art. 84 EPC):
   - Identifies unclear or ambiguous terms
   - Detects relative terms without reference points
   - Checks for consistent terminology throughout claims
   - Validates technical feature definitions

2. **Conciseness Check** (Art. 84 EPC):
   - Detects redundant claims
   - Identifies unnecessarily complex claim structures
   - Checks for duplicate scope between claims
   - Validates claim set economy

3. **Support by Description** (Art. 84 EPC):
   - Not checked by this claims-only analyzer, which receives no description
   - Request the description and use `review_epo_specification` for preliminary support heuristics, followed by manual feature-by-feature review
   - Without that review, report description support as not assessed

4. **Claim Structure** (Rule 43 EPC):
   - Validates two-part form (preamble + characterizing portion) where appropriate
   - Checks independent claim structure
   - Validates dependent claim references
   - Verifies claim categories (product, process, apparatus, use)

5. **Issue Categorization**:
   - **Critical**: Will cause objection under Art. 84 EPC
   - **Important**: May cause objection or limit claim scope
   - **Minor**: Best practice improvements per EPO Guidelines

## Who This Is For

- Patent attorneys preparing EP applications
- Applicants responding to EPO Art. 84 objections
- Practitioners converting US claims to EPO format
- Quality assurance before EP filing or Euro-PCT entry

## Process

### Step 1: Provide Claims

You can provide claims in three ways:

**Option 1: Paste claims directly**
```
/review-epo-claims

> Paste your claims text, then type 'END' on a new line:

1. A system for authenticating users, characterised in that
   the system comprises a distributed ledger configured to
   store and verify credentials.

2. The system according to claim 1, wherein the distributed
   ledger is a blockchain.

END
```

**Option 2: Point to a file**
```
/review-epo-claims path/to/claims.txt
```

**Option 3: Let me read from current conversation**
```
[You paste claims in chat]

/review-epo-claims --from-context
```

### Step 2: Automated Analysis

I'll run the claims through the EPO compliance analyzer:

This checks:
- All terms for clarity (Art. 84 EPC)
- Claim conciseness and economy
- Description support: not assessed by the claims-only tool
- Two-part form structure (Rule 43(1) EPC)
- Claim categories and dependencies
- EPO Guidelines Part F requirements

### Step 3: Generate Report

I'll provide a detailed compliance report with:
- Overall compliance score (0-100)
- Issue count by severity
- Specific issues with locations
- EPC article and rule citations
- EPO Guidelines references
- Suggested fixes

### Step 4: Fix Issues (Optional)

For each critical/important issue, I can:
- Show the problematic text
- Explain the EPO objection basis
- Suggest specific fix
- Apply fix if you approve

## Report Structure

```
EPO CLAIMS COMPLIANCE REPORT
==============================

Summary:
--------
- Total Claims: 15 (2 independent, 13 dependent)
- Compliance Score: 68/100
- Total Issues: 11 (2 critical, 6 important, 3 minor)

Recommendation: FIX CRITICAL ISSUES BEFORE EP FILING

CRITICAL ISSUES (Will Cause Art. 84 Objection):
=================================================

[Claim 1, Line 4] Lack of Clarity
-----------------------------------
Issue: Term "substantially planar" used without objective criterion

Location:
  "a substantially planar surface for mounting"
   ^^^^^^^^^^^^^

Problem:
  The term "substantially planar" lacks clarity under Art. 84 EPC.
  The EPO requires clear, objective claim language. Unlike USPTO
  practice, the EPO applies a stricter standard for terms of degree.

EPC Citation: Art. 84 EPC - Clarity requirement
EPO Guidelines: F-IV, 4.6 - Relative terms

Fix Suggestion:
  Option 1: Define with objective criteria
    Change to: "a surface having a flatness deviation of less than 0.1mm"

  Option 2: Reference a standard
    Change to: "a planar surface as measured per ISO 1101"

---

[Claim 1] Missing Two-Part Form
---------------------------------
Issue: Independent claim does not use two-part form

Problem:
  Under Rule 43(1) EPC, independent claims, where appropriate,
  contain a statement of prior art features (preamble) and
  a characterizing portion introduced by "characterised in that"
  or "characterised by".

EPC Citation: Rule 43(1) EPC
EPO Guidelines: F-IV, 2.2-2.3 - Two-part form

Fix Suggestion:
  BEFORE: "1. A system comprising: a processor; a memory; ..."
  AFTER:  "1. A system comprising a processor and a memory,
           characterised in that [novel features]..."

---

[Continue for all critical issues...]

IMPORTANT ISSUES (Should Fix):
================================

[Manual review example, only after reading the description]
[Claim 5] Unsupported Generalization
--------------------------------------
Issue: Claim broader than description supports

Location: "any communication protocol"

The description only discloses TCP/IP and Bluetooth.
Claiming "any communication protocol" extends beyond
the disclosure. Art. 84 EPC requires claims to be
supported by the description.

EPC Citation: Art. 84 EPC - Support requirement
EPO Guidelines: F-IV, 6.2 - Breadth of claims

Suggested Fix: Change to "a communication protocol
selected from TCP/IP and Bluetooth"

---

[Continue for all important issues...]

MINOR ISSUES (Consider Fixing):
=================================

[Claim 8] Style Issue
----------------------
Issue: US-style "comprising" without "characterised in that"

While not strictly required for all claims, EPO examiners
prefer the two-part form for independent claims when
closest prior art is identifiable.

EPO Guidelines: F-IV, 3.2

Suggested Fix: Consider restructuring with two-part form

---

[Continue for all minor issues...]

EPO-SPECIFIC GUIDANCE:
========================

Key Differences from USPTO Practice:
- Two-part form where appropriate (Rule 43(1) EPC)
- Stricter clarity standard (no "substantially" without definition)
- Claims must be supported by description (Art. 84)
- Method of treatment claims excluded (Art. 53(c) EPC)
- Computer-implemented inventions must show technical effect
- No means-plus-function by default (functional features must be clear)

Relevant EPC Provisions:
- Art. 52 EPC - Patentable inventions
- Art. 53 EPC - Exceptions to patentability
- Art. 69 EPC - Extent of protection
- Art. 84 EPC - Claims (clarity, conciseness, support)
- Rule 42 EPC - Content of the description
- Rule 43 EPC - Form and content of claims

NEXT STEPS:
============

1. FIX all 2 critical issues (required before EP filing)
2. REVIEW all 6 important issues (recommended fixes)
3. CONSIDER 3 minor issues (optional improvements)
4. RE-RUN analysis after fixes to verify compliance
```

## Interactive Fixing

After the report, I can interactively help you fix issues:

```
> Found 2 critical issues. Would you like me to help fix them?

Yes

> Issue 1/2: [Claim 1] Lack of clarity - "substantially planar"
>
> Current: "a substantially planar surface for mounting"
> Suggested: "a surface having a flatness deviation of less than 0.1mm"
>
> Apply this fix? (y/n/skip)

y

> Fix applied. Issue 2/2...
```

## Output Files

Results saved to:
```
epo-claims-review-[date]/
├── analysis-report.md          # Full compliance report
├── critical-issues.md          # Critical issues only
├── suggested-fixes.md          # All suggested fixes
├── claims-original.txt         # Your original claims
├── claims-fixed.txt            # Fixed version (if requested)
└── epc-citations.md            # Relevant EPC/EPO Guidelines sections
```

## Key EPO vs USPTO Differences

| Aspect | USPTO | EPO |
|--------|-------|-----|
| Claim form | Open (comprising) | Two-part form where appropriate (Rule 43) |
| Clarity standard | Reasonable certainty | Strict objective clarity |
| Terms of degree | Allowed with spec support | Must have objective reference |
| Functional features | Means-plus-function | Must be clear per se |
| Method of treatment | Allowed | Excluded (Art. 53(c)) |
| Software claims | Patent-eligible if technical | Must show "further technical effect" |
| Support | 112(a) written description | Art. 84 - claims supported by description |

## Compliance Score

A score describes only the automated checks that ran. It is not filing
clearance, even at 100. Lead with `checks_run` and `checks_skipped` when the
result supplies them, retaining each skip reason. If coverage fields are
absent, say coverage is unreported and name known limitations; never infer
that every check ran from a score or an empty issues list.

Art. 123(2) added-matter review is not implemented; record it as skipped.

**90-100**: Few issues detected by the automated checks that ran
**75-89**: Good - Minor issues to address
**60-74**: Fair - Important issues likely to draw Art. 84 objection
**< 60**: Poor - Significant revision needed before EP filing

## Tips

1. **Assess two-part form**: Use it where appropriate; record reasons for a different form
2. **Be precise**: EPO examiners apply stricter clarity standards than USPTO
3. **Check support**: Every claim feature must be in the description
4. **Avoid US-isms**: "Means for", "whereby", broad functional language
5. **Category matters**: Product, process, apparatus, use - each has specific rules

## Integration

This command uses:
- **EPO Patent Analyzer** skill for automated checking
- **EPC Search** skill for legal guidance
- **EPO Patent Drafter** agent for fixing issues (if requested)

---

**DISCLAIMER:** This tool assists with patent application preparation but does NOT replace legal advice from a registered European Patent Attorney. Always consult with legal counsel before filing. Not affiliated with or endorsed by the EPO.
