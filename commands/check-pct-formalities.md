---
description: Check international patent application formalities for PCT compliance (PCT Rules 5-12, Administrative Instructions)
argument-hint: "[optional: request | description | claims | abstract | drawings | all] application-text"
allowed-tools:
  - check_pct_formalities
  - search_patent_law
  - search_mpep
model: claude-sonnet-4-5-20250929
---

# PCT Formalities Check

The formalities tool receives text and a drawings-present flag, not page or drawing files. Physical layout, margins, paper size, line spacing, drawing quality, request forms, and payments are not inspected. Mark them NOT CHECKED until a separate review of the final documents or records supplies evidence. Report only checks actually run; the checklist below is not a prefilled result.

Review supplied text and identify manual checks for formal requirements for a PCT international application under PCT Rules 5-12.

**Check Type:** $ARGUMENTS

## What I'll Check

1. **Request Form** (Rule 4 PCT) - Form PCT/RO/101, designations, priority claims
2. **Description** (Rule 5 PCT) - Required sections, manner of description
3. **Claims** (Rule 6 PCT) - Numbering, form, unity of invention (Rule 13 PCT)
4. **Abstract** (Rule 8 PCT) - preferably 50-150 words in English, figure designation
5. **Drawings** (Rule 11 PCT) - Technical standards, margins, paper size
6. **Sequence Listings** (Rules 5.2 and 13ter PCT) - If applicable (WIPO Standard ST.26)
7. **Physical Requirements** (Rule 11 PCT) - Paper, margins, font, numbering
8. **Unity of Invention** (Rule 13 PCT) - Single general inventive concept
9. **Fees** - International filing fee, search fee, transmittal fee
10. **Language** (Rule 12 PCT) - Accepted languages per Receiving Office

Specified check type focuses on that requirement; otherwise reviews the supplied text and lists outstanding manual checks.

## Process

1. Ask for application sections (or read from file)
2. Check each PCT formality requirement
3. Search indexed PCT rules; consult WIPO directly for Administrative Instructions
4. Generate compliance report with:
   - Requirements checklist per rule
   - Non-compliance issues with rule citations
   - Fix instructions
   - Pre-filing checklist for PCT

## PCT-Specific Requirements

### Request (Rule 4 PCT)

- Form PCT/RO/101
- Title of invention (same as description)
- Applicant details (name, address, nationality, residence)
- Agent/representative details (if applicable)
- Designation of states (all states designated automatically since 2004)
- Priority claims (within 12 months, certified copy required)
- Inventor details
- Choice of International Searching Authority (ISA)
- Reference to deposited biological material (if applicable)

### Description (Rule 5 PCT)

Required sections in order:
1. Title of the invention
2. Technical field
3. Background art
4. Disclosure of the invention (technical problem and solution)
5. Brief description of drawings (if any)
6. Best mode for carrying out the invention
7. Industrial applicability
8. Sequence listing (if applicable, WIPO Standard ST.26 XML format)

### Claims (Rule 6 PCT)

- Numbered consecutively in Arabic numerals
- Clear and concise
- Fully supported by description
- Independent claims: define essential features
- Dependent claims: reference and further limit
- Multiple independent claims allowed (but unity required)
- Unity of invention (Rule 13): single general inventive concept

### Abstract (Rule 8 PCT)

- preferably 50-150 words in English
- Summary of disclosure including technical field, problem, solution
- Must designate most illustrative figure
- Not used for interpreting scope of protection
- May be amended by ISA

### Drawings (Rule 11 PCT)

- A4 paper (29.7cm x 21cm)
- Minimum margins: top 2.5cm, left 2.5cm, right 1.5cm, bottom 1cm
- Usable area: 26.2cm x 17cm
- Black, sufficiently dense, well-defined lines
- Reference signs in description must correspond to drawings
- Figures numbered consecutively (Fig. 1, Fig. 2, ...)

### Physical Requirements (Rule 11 PCT)

- A4 paper, one side only
- Minimum line spacing: 1.5
- Minimum font size: large enough to be reproduced (typically 12pt)
- Page numbering: consecutive, centered at top or bottom
- Left margin: 2.5cm minimum
- Sheet numbering for each element

### Unity of Invention (Rule 13 PCT)

- Single general inventive concept
- Linking technical feature test
- Special technical features distinguishing from prior art
- If unity lacking: ISA may invite additional search fees

## Report Structure

Illustrative format only. Replace all counts and findings with observed results. Use NOT CHECKED whenever the evidence is unavailable. Never copy example passes into a real report.

```
PCT FORMALITIES COMPLIANCE REPORT
====================================

Application: [Title]
Date: [Date]
Receiving Office: [RO/XX]
International Searching Authority: [ISA/XX]

Summary:
--------
- Requirements Checked: 56
- Compliant: 48
- Non-Compliant: 6
- Warnings: 2

STATUS: CORRECTIONS NEEDED BEFORE FILING

REQUEST (Rule 4 PCT):
======================

[NOT CHECKED] Form PCT/RO/101 complete; verify the actual request and records
[NOT CHECKED] Applicant details (name, address, nationality); verify the actual request and records
[NOT CHECKED] Title matches description; verify the actual request and records
[PASS] All states designated (automatic since 2004)
[FAIL] Priority claim missing certified copy reference
  -> Rule 17.1 PCT: Certified copy of priority
     document must be furnished within 16 months from
     priority date
  -> Fix: Indicate priority document will be furnished
     or request DAS access code
[NOT CHECKED] Inventor designation complete; verify the actual request and records
[NOT CHECKED] ISA selected; verify the actual request and records

DESCRIPTION (Rule 5 PCT):
===========================

[PASS] Title present
[PASS] Technical field identified
[PASS] Background art described
[PASS] Invention disclosed with problem-solution
[PASS] Drawings briefly described
[FAIL] Best mode not clearly identified
  -> Rule 5.1(a)(v) PCT: "best mode contemplated
     by the applicant for carrying out the invention"
  -> Fix: Add paragraph identifying preferred embodiment
     as best mode
[PASS] Industrial applicability stated

CLAIMS (Rule 6 PCT):
======================

[PASS] Numbered consecutively
[PASS] Supported by description
[PASS] Independent claims define essential features
[PASS] Dependent claims properly reference
[WARN] Potential unity issue: Claims 1 and 12 may
  lack common special technical feature
  -> Rule 13.1 PCT: "relate to one invention only
     or to a group of inventions so linked as to form
     a single general inventive concept"
  -> Note: ISA may raise unity objection and invite
     additional search fees

ABSTRACT (Rule 8 PCT):
========================

[PASS] Word count: 138 (preferably 50-150 words in English)
[FAIL] No figure designated
  -> Rules 3.3(a)(iii) and 8.2 PCT: indicate the suggested
     figure in the request; the ISA selects the figure to publish
  -> Manual review: check the suggested figure in the request under Rule 3.3(a)(iii)
[PASS] Technical field indicated
[PASS] Concise summary of disclosure

PHYSICAL REQUIREMENTS (Rule 11 PCT):
======================================

[NOT CHECKED] A4 paper format; inspect final pages/drawings manually
[NOT CHECKED] Margins within specification; inspect final pages/drawings manually
[NOT CHECKED] Line spacing: 1.5 or greater; inspect final pages/drawings manually
[NOT CHECKED] Page numbering; inspect the final documents
  -> Rule 11.7 PCT: Sheets shall be numbered in
     consecutive Arabic numerals
  -> Fix: Number all sheets consecutively
[NOT CHECKED] Text legible and reproducible; inspect final pages/drawings manually

DRAWINGS (Rule 11 PCT):
=========================

[NOT CHECKED] Margins within specification; inspect final pages/drawings manually
[NOT CHECKED] Reference signs consistent with description; inspect final pages/drawings manually
[NOT CHECKED] Figure line quality; inspect the final drawings
  -> Rule 11.13(a), (f) PCT: lines must be reproducible and
     ordinarily drawn with drafting instruments (paraphrase)
  -> If reproduction is unclear, adjust line weight and inspect again

UNITY OF INVENTION (Rule 13 PCT):
====================================

[PASS] Single general inventive concept identified
[NOTE] Claims span system (Cl. 1-10) and method (Cl. 11-20)
  -> These share the special technical feature of [X]
  -> Unity is maintained

FEES CALCULATION (RO/US):
===========================

[NOT CALCULATED] Verify current schedules before estimating or paying.
Record fee code, amount, currency, due date, source URL, and date checked.

KEY DEADLINES:
===============

Use the earliest claimed priority date; if none, the PCT filing date.
Priority + 12 months: Normally file PCT to claim the earlier filing's priority
Priority + 16 months: Priority document deadline (Rule 17.1 alternatives apply)
After priority + 18 months: International publication, normally promptly after expiry
Chapter II demand: Later of priority + 22 months or 3 months from transmittal
of the ISR (or Article 17(2)(a) declaration) and written opinion
Priority + 30 months: US and Japan national phase entry
Priority + 31 months: EPO regional phase entry
Other Offices: Check the current WIPO table and national chapter; exceptions apply.

FILING CHECKLIST:
==================

[x] Request form PCT/RO/101
[x] Description with all Rule 5 sections
[x] Claims (numbered, proper form)
[ ] Abstract with designated figure (NEEDS FIX)
[ ] Drawings (A4 and margins require final-file inspection)
[ ] Page numbering (NEEDS FIX)
[ ] Priority document certified copy
[ ] Fee payment (transmittal + filing + search)
[x] Power of attorney (if using agent)
[ ] Sequence listing in ST.26 XML (if applicable)

NEXT STEPS:
============

1. Fix 6 non-compliance items listed above
2. Address 2 warnings (recommended)
3. Select Receiving Office (RO) and ISA
4. Prepare fee payment
5. File via ePCT (WIPO online filing system)
6. Record each Office's national phase deadline measured from priority, not a later PCT filing
```

Deadline sources: [PCT Article 2(xi)](https://www.wipo.int/en/web/pct-system/texts/articles/a2),
[Rule 17.1](https://www.wipo.int/en/web/pct-system/texts/rules/r17),
[Article 21(2)](https://www.wipo.int/en/web/pct-system/texts/articles/a21),
[Rule 54bis.1](https://www.wipo.int/en/web/pct-system/texts/rules/r54bis),
and [WIPO Office-specific time limits](https://www.wipo.int/en/web/pct-system/texts/time_limits).

## Output

- Section-by-section compliance status
- Issues with PCT rule citations
- Fee calculation per Receiving Office
- Key deadline calendar
- Filing preparation checklist
- Unity of invention assessment

## PCT vs Direct National Filing

| Aspect | PCT | Direct EP | Direct US |
|--------|-----|-----------|-----------|
| Scope | 157 countries | 39 EPC states | US only |
| Decision deadline | Office-specific, usually 30/31 months from priority | Filing date | Filing date |
| Search | ISA report | EP search | USPTO search |
| Cost at filing | Check WIPO and RO/ISA schedules | Check EPO schedule | Check USPTO schedule |
| Advantage | Delays national costs | Faster EP grant | Fastest US grant |

---

**DISCLAIMER:** This tool assists with patent application preparation but does NOT replace legal advice from a registered patent attorney or agent. Always consult with legal counsel before filing. Not affiliated with or endorsed by WIPO or any patent office.

Legal references: [PCT Rule 8.1(b)](https://www.wipo.int/en/web/pct-system/texts/rules/r8) gives a preferred English abstract length, not a hard maximum; [Rule 11.11](https://www.wipo.int/en/web/pct-system/texts/rules/r11) permits indispensable short catchwords, including in flow diagrams.

Retrieve amounts and due dates from the official schedules for the selected route, Office, currency, entity status, and payment date. Record the source URL and date checked with every estimate. Do not reuse a static total.

- [EPO fee schedule](https://www.epo.org/en/applying/fees)
- [WIPO PCT fee schedule](https://www.wipo.int/en/web/pct-system/texts/rules/rtax)
- [USPTO fee schedule](https://www.uspto.gov/learning-and-resources/fees-and-payment/uspto-fee-schedule)

The PCT international filing-fee supplement is based on sheets beyond 30, not claims beyond 15. Electronic reductions depend on the filing format and applicable conditions; using ePCT alone does not fix the reduction. Additional search fees for lack of unity and national-phase claims fees are separate.
