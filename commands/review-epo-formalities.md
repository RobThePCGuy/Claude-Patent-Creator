---
description: Check patent application formalities for EPO compliance (Rules 42-49 EPC, EPO Guidelines Part A)
argument-hint: "[optional: description | claims | abstract | drawings | all] application-text"
allowed-tools:
  - check_epo_formalities
  - search_patent_law
  - search_mpep
model: claude-sonnet-4-5-20250929
---

# EPO Formalities Check

The formalities tool receives text and a drawings-present flag, not page or drawing files. Physical layout, margins, paper size, line spacing, drawing quality, request forms, and payments are not inspected. Mark them NOT CHECKED until a separate review of the final documents or records supplies evidence. Report only checks actually run; the checklist below is not a prefilled result.

Review supplied text and identify manual checks for formal requirements for a European patent application under EPC Rules 42-49.

**Check Type:** $ARGUMENTS

## What I'll Check

1. **Description** (Rule 42 EPC) - Required sections, disclosure sufficiency, unity
2. **Claims** (Rule 43 EPC) - Two-part form, numbering, fees for excess claims
3. **Abstract** (Rule 47 EPC) - Preferably no more than 150 words, single figure designation, content
4. **Drawings** (Rule 49(2) EPC and the President's presentation decision) - Technical quality, reference signs, margins
5. **Request for Grant** (Rule 41 EPC) - Form 1001, designation of states, priorities
6. **Translation Requirements** - Language of proceedings (Rule 6 EPC)
7. **Fees** - Filing fee, search fee, designation fee, claims fee (> 15 claims)

Specified check type focuses on that requirement; otherwise reviews the supplied text and lists outstanding manual checks.

## Process

1. Ask for application sections (or read from file)
2. Check each EPO formality requirement
3. Search EPC rules and EPO Guidelines for standards
4. Generate compliance report with:
   - Requirements checklist per rule
   - Non-compliance issues
   - Fix instructions with rule citations
   - Pre-filing checklist for EPO

## EPO-Specific Requirements

### Description (Rule 42 EPC)

Required sections in order:
- Title of the invention
- Technical field
- Background art (with citation of prior art documents)
- Disclosure of the invention (technical problem and solution)
- Brief description of drawings (if any)
- Detailed description of at least one embodiment
- Industrial applicability (if not obvious)

### Claims (Rule 43 EPC)

- Two-part form for independent claims where appropriate (preamble + "characterised in that")
- Clear reference to description and drawings
- No drawings or graphs in claims
- Numbered consecutively in Arabic numerals
- Fee applies for each claim beyond 15 (Rule 45 EPC)
- Fee applies for each claim beyond 50

### Abstract (Rule 47 EPC)

- Preferably no more than 150 words
- Must indicate technical field
- Must include concise summary of disclosure
- Must designate most illustrative figure (if drawings exist)
- No commercial statements
- Single paragraph preferred

### Drawings (Rule 49(2) EPC and the President's presentation decision)

- Minimum margins: top 2.5cm, left 2.5cm, right 1.5cm, bottom 1cm
- Use only indispensable short keywords in drawings; explain other details in the description
- Reference signs in description must match drawings
- Figures numbered consecutively (Fig. 1, Fig. 2, ...)
- A4 paper size (21cm x 29.7cm)
- Clear, reproducible lines; electronic drawings may also use colour or greyscale under OJ EPO 2025 A49

### Request for Grant (Rule 41 EPC)

- EPO Form 1001
- Applicant details (name, address, nationality)
- Title of invention
- Designation of Contracting States (all states designated by default)
- Priority claims (convention priority within 12 months)
- Inventor designation
- Representative details (if applicable)

## Report Structure

Illustrative format only. Replace all counts and findings with observed results. Use NOT CHECKED whenever the evidence is unavailable. Never copy example passes into a real report.

```
EPO FORMALITIES COMPLIANCE REPORT
===================================

Application: [Title]
Date: [Date]
Filing Route: Direct EP / Euro-PCT

Summary:
--------
- Requirements Checked: 42
- Compliant: 35
- Non-Compliant: 5
- Warnings: 2

STATUS: CORRECTIONS NEEDED BEFORE FILING

DESCRIPTION (Rule 42 EPC):
============================

[PASS] Title present and descriptive
[PASS] Technical field identified
[FAIL] Background art section missing prior art citations
  -> Rule 42(1)(b): "indicate the background art which,
     as far as known to the applicant, can be regarded as
     useful to understand the invention"
  -> Fix: Add at least 2-3 prior art document citations
[PASS] Problem-solution format used
[PASS] At least one embodiment described in detail
[WARN] Industrial applicability not explicitly stated
  -> Rule 42(1)(f): Required if not obvious from description

CLAIMS (Rule 43 EPC):
======================

[PASS] Claims numbered consecutively
[REVIEW] Independent claim 1 not in two-part form
  -> Rule 43(1): two-part form applies where appropriate
  -> Determine whether the invention and prior art suit this form before rewriting
[PASS] Dependent claims properly reference parent claims
[PASS] 15 or fewer claims (no excess claims fee)
[PASS] No drawings or graphs in claims

ABSTRACT (Rule 47 EPC):
=========================

[PASS] Word count: 127 (preferably no more than 150 words)
[FAIL] No figure designated as most illustrative
  -> Rule 47(4): indicate the figure, or exceptionally figures,
     to publish with the abstract when drawings are present
  -> Fix: Add "Figure to accompany abstract: Fig. 1"
[PASS] Technical field indicated
[PASS] No commercial statements

DRAWINGS (Rule 49(2) EPC and the President's presentation decision):
=========================

[NOT CHECKED] Margins within specification; inspect final pages/drawings manually
[NOT CHECKED] Reference signs consistent; inspect final pages/drawings manually
[NOT CHECKED] Drawing labels
  -> Inspect whether each short keyword is indispensable under Article 1(2)(j)
     of the President's presentation decision (OJ EPO 2025 A49).
  -> A short label is not automatically prohibited.

REQUEST FOR GRANT (Rule 41 EPC):
==================================

[NOT CHECKED] Applicant details complete; verify the actual request and records
[NOT CHECKED] Title matches description; verify the actual request and records
[NOT CHECKED] Priority claim within 12 months; verify the actual request and records
[NOT CHECKED] Inventor designation filed; verify the actual request and records

FEES CALCULATION:
==================

[NOT CALCULATED] Verify current schedules before estimating or paying.
Record fee code, amount, currency, due date, source URL, and date checked.

FILING CHECKLIST:
==================

[x] Form 1001 (Request for Grant)
[x] Description with all required sections
[x] Claims (numbered, proper form)
[ ] Abstract with designated figure (NEEDS FIX)
[ ] Drawings (A4 and margins require final-file inspection)
[x] Priority document (if claiming priority)
[x] Power of attorney (if using representative)
[ ] Filing fee payment
[ ] Search fee payment

NEXT STEPS:
============

1. Fix 5 non-compliance items listed above
2. Address 2 warnings (recommended)
3. Verify fees and prepare payment
4. File via EPO Online Filing 2.0
5. Note: Examination request due within 6 months of search report
```

## Output

- Section-by-section compliance status
- Issues with EPC rule citations
- Required vs optional items
- Fee calculation based on claim count
- Filing preparation checklist
- EPO-specific deadlines and requirements

## EPO vs USPTO Formalities

| Requirement | USPTO | EPO |
|-------------|-------|-----|
| Abstract length | 150 words max | Preferably no more than 150 words |
| Claims fee threshold | > 3 independent / > 20 total | > 15 total / > 50 total |
| Description format | MPEP 608 sections | Rule 42 EPC sections |
| Claim form | Open format | Two-part form where appropriate (Rule 43) |
| Drawings text | Limited text allowed | Use only indispensable short keywords in drawings; explain other details in the description |
| Paper size | Letter or A4 | A4 only |
| Filing language | English | English, French, or German |
| Priority period | 12 months | 12 months |

---

**DISCLAIMER:** This tool assists with patent application preparation but does NOT replace legal advice from a registered European Patent Attorney. Always consult with legal counsel before filing. Not affiliated with or endorsed by the EPO.

Legal references: [EPC Rule 47](https://www.epo.org/en/legal/epc/2020/r47.html), [two-part form where appropriate](https://www.epo.org/en/legal/guidelines-epc/2026/f_iv_2_3.html), [Rule 49(2)](https://www.epo.org/en/legal/epc/2020/r49.html), and [President's presentation decision, OJ EPO 2025 A49](https://www.epo.org/en/legal/official-journal/2025/07/a49). Rule 46 was deleted effective 1 February 2023.

Retrieve amounts and due dates from the official schedules for the selected route, Office, currency, entity status, and payment date. Record the source URL and date checked with every estimate. Do not reuse a static total.

- [EPO fee schedule](https://www.epo.org/en/applying/fees)
- [WIPO PCT fee schedule](https://www.wipo.int/en/web/pct-system/texts/rules/rtax)
- [USPTO fee schedule](https://www.uspto.gov/learning-and-resources/fees-and-payment/uspto-fee-schedule)

The PCT international filing-fee supplement is based on sheets beyond 30, not claims beyond 15. Electronic reductions depend on the filing format and applicable conditions; using ePCT alone does not fix the reduction. Additional search fees for lack of unity and national-phase claims fees are separate.
