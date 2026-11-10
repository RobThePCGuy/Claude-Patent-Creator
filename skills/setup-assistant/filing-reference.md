# USPTO Filing Reference

This document contains current USPTO filing information for patent application assembly.
Agents and commands MUST reference this document instead of generating filing details from memory.

## Filing System

All new nonprovisional utility patent applications are filed through **USPTO Patent Center** (patentcenter.uspto.gov). EFS-Web was retired in 2023 and is no longer available.

## Document Format Requirements

### Specification, Claims, and Abstract
- **Required format: DOCX**
- Patent Center accepts DOCX natively for specification, claims, and abstract
- Filing in non-DOCX format (e.g., PDF) triggers a **non-DOCX surcharge**
- Convert from Markdown to DOCX before filing (use pandoc or Word)

### Drawings
- **Required format: PDF (black-and-white line art)**
- Utility patent drawings must be black-and-white per 37 CFR 1.84
- Color drawings require a separate petition under 37 CFR 1.84(a)(2) with justification
- Each sheet numbered consecutively within the sight area ("Sheet X of Y")
- Margins: at least 1 inch top, 2.5 cm sides and bottom
- All text in figures must be legible at reduction

### Reference Numerals (37 CFR 1.84(p))
- Every reference numeral appearing in a drawing MUST be mentioned in the specification
- Reference characters not mentioned in the description shall not appear in the drawings
- Consistent numbering: the same element must use the same numeral across all figures

## Fee Schedule

**Do NOT hardcode or estimate fee amounts.** USPTO fees change periodically.

Direct the user to the **live USPTO fee schedule**:
https://www.uspto.gov/learning-and-resources/fees-and-payment/uspto-fee-schedule

Key fee categories for utility nonprovisional filing:
- Basic filing fee (by entity size: micro, small, large)
- Search fee
- Examination fee
- Excess claims fees (each independent claim over 3, each total claim over 20)
- Non-DOCX surcharge (if applicable)

## Entity Size

### Micro Entity (37 CFR 1.29)
- Qualifies for 80% fee reduction
- Gross-income basis: first qualify as a small entity, then satisfy the income, prior-application, and rights-transfer conditions for each relevant applicant/inventor under 37 CFR 1.29(a). The limit is no more than four counted prior applications. Foreign applications, provisional applications, and PCT applications for which the US basic national fee was not paid are excluded; the prior-employment exclusion in 1.29(b) may also apply. Five prior provisional filings alone do not disqualify an inventor.
- A separate institution-of-higher-education basis exists under 1.29(d). Check the applicable basis and certification; do not infer eligibility from inventor status alone.
- Source: [MPEP 509.04](https://www.uspto.gov/web/offices/pac/mpep/s509.html)
- **Current threshold:** Check https://www.uspto.gov/patents/basics/using-legal-services/micro-entity-status

### Small Entity (37 CFR 1.27)
- Qualifies for 60% fee reduction
- A person, qualifying small business, or qualifying nonprofit must satisfy 37 CFR 1.27, including the restrictions on assignment, licensing, and obligations to transfer rights to a non-small entity. Being an individual alone is insufficient. Review all relevant rights holders and obligations before claiming status.
- Source: [MPEP 509.02 and 37 CFR 1.27](https://www.uspto.gov/web/offices/pac/mpep/s509.html)

## Information Disclosure Statement (IDS)

- Filed through Patent Center's **eIDS** (electronic IDS) interface
- **U.S. patents and U.S. patent application publications:** Enter the publication number directly in eIDS. No copies need to be submitted -- the USPTO has these in its own records (37 CFR 1.98(a)(2))
- **Foreign patent documents:** Copies must be submitted
- **Non-patent literature (NPL):** Copies must be submitted
- IDS should be filed within 3 months of filing or before first Office Action to avoid late fees

## Inventor Declaration

- Form PTO/AIA/01
- Patent Center allows electronic signature
- **Can be deferred** under ADS-based postponement rules -- the declaration does not have to be included at the time of filing
- **Warning:** If the declaration is not included at filing, the USPTO may issue a Notice to File Missing Parts with a surcharge for late filing. Advise the inventor to file the declaration at the time of filing to avoid this surcharge (MPEP 602.03)

## Application Data Sheet (ADS)

- Completed within Patent Center during the filing process
- Form PTO/AIA/14
- Includes inventor information, correspondence address, application type, priority claims
