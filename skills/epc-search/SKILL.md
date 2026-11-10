---
name: epc-search
description: RAG search across EPC provisions, EPO Guidelines for Examination, and PCT rules for European and international patent law research
tools: Bash, Read, Write
model: sonnet
---

# EPC/PCT Legal Search Skill

Hybrid RAG search across the European Patent Convention (EPC), EPO Guidelines for Examination, and PCT Rules for patent law research.

## When to Use

Invoke this skill when users ask to:
- Find EPC articles or rules on a specific topic
- Search EPO Guidelines for Examination
- Look up indexed PCT rules; use WIPO directly for Administrative Instructions
- Compare EPC requirements with USPTO/MPEP practice
- Research EPO Board of Appeal case law principles
- Understand European patent prosecution procedure
- Find legal basis for EPO examination objections

## What This Skill Does

Provides legal research across European and international patent law:

1. **EPC Search** (European Patent Convention):
   - Articles 1-178 EPC
   - Rules 1-167 EPC (Implementing Regulations)
   - Protocol on Interpretation of Art. 69 EPC
   - Protocol on Centralisation
   - Protocol on Privileges and Immunities

2. **EPO Guidelines Search** (Guidelines for Examination):
   - Part A: Guidelines for Formalities Examination
   - Part B: Guidelines for Search
   - Part C: Guidelines for Procedural Aspects of Substantive Examination
   - Part D: Guidelines for Opposition and Limitation/Revocation
   - Part E: Guidelines for General Procedural Matters
   - Part F: Guidelines for Substantive Examination (The Patent Application)
   - Part G: Guidelines for Patentability
   - Part H: Guidelines for Amendments and Corrections

3. **PCT Rules Search** (Patent Cooperation Treaty):
   - PCT Articles 1-69
   - PCT Rules 1-96 (Regulations under the PCT)
   - Setup does not download the Administrative Instructions or full WIPO Standards (ST.25, ST.26, ST.36). Incidental mentions in other sources are not the standards themselves. Retrieve these from [WIPO PCT texts](https://www.wipo.int/en/web/pct-system/texts) and [WIPO standards](https://www.wipo.int/en/web/standards).

4. **Cross-Jurisdiction Comparison**:
   - EPC vs 35 USC mapping
   - EPO Guidelines vs MPEP equivalents
   - PCT requirements vs national requirements

## Required Data

**MCP Tools Available**:
- `search_patent_law` - Search EPC, EPO Guidelines, PCT rules with jurisdiction parameter
- `search_mpep` - Search MPEP/35 USC/37 CFR for comparison

## How to Use

When this skill is invoked:

1. **Determine jurisdiction**:
   - EPO: search EPC articles/rules and EPO Guidelines
   - PCT: search indexed articles/rules; obtain Administrative Instructions from WIPO
   - Both: search across all sources
   - Comparison: search EPO + USPTO sources

2. **Execute search**:

   **EPC/EPO Guidelines search**:
   ```python
   results = search_patent_law(
       query="claim clarity requirements",
       jurisdiction="EPO",
       top_k=5
   )
   ```

   **PCT rules search**:
   ```python
   results = search_patent_law(
       query="unity of invention",
       jurisdiction="PCT",
       top_k=5
   )
   ```

   **Cross-jurisdiction comparison**:
   ```python
   epo_results = search_patent_law(query="sufficiency of disclosure", jurisdiction="EPO")
   us_results = search_mpep(query="enablement requirement")
   ```

3. **Present results**:
   - Show relevant provisions with full text
   - Provide article/rule numbers and section references
   - Include EPO Guidelines commentary
   - Note practical implications for prosecution

## Key EPC Provisions Reference

### Patentability

| Article | Topic | Description |
|---------|-------|-------------|
| Art. 52 | Patentable inventions | What can be patented |
| Art. 52(2) | Exclusions | Discoveries, theories, programs "as such" |
| Art. 53 | Exceptions | Morality, plant/animal varieties, medical methods |
| Art. 54 | Novelty | Absolute novelty, no grace period |
| Art. 55 | Non-prejudicial disclosures | 6-month grace for abuse or exhibitions |
| Art. 56 | Inventive step | Problem-solution approach |
| Art. 57 | Industrial applicability | Capable of industrial application |

### The Patent Application

| Article/Rule | Topic | Description |
|-------------|-------|-------------|
| Art. 78 | Requirements | What an EP application must contain |
| Art. 83 | Disclosure | Sufficiency of disclosure |
| Art. 84 | Claims | Clarity, conciseness, support |
| Rule 42 | Description | Content and form of description |
| Rule 43 | Claims | Two-part form, numbering, categories |
| Rule 49(2) | Drawings | Presentation requirements set by the President |
| Rule 47 | Abstract | preferably no more than 150 words, figure designation |

### Examination Procedure

| Article | Topic | Description |
|---------|-------|-------------|
| Art. 90 | Formalities examination | Initial formality check |
| Art. 92 | European search | Search report |
| Art. 94 | Substantive examination | Examination on request |
| Art. 97 | Grant/refusal | Decision on application |
| Art. 99 | Opposition | 9-month opposition period |

## Key PCT Rules Reference

### Application Requirements

| Rule | Topic | Description |
|------|-------|-------------|
| Rule 4 | The request | Form PCT/RO/101 contents |
| Rule 5 | The description | Required sections and order |
| Rule 6 | The claims | Numbering, form, categories |
| Rule 8 | The abstract | Preferably 50-150 English words; figure under Rule 8.2 |
| Rule 11 | Physical requirements | Paper, margins, fonts |
| Rule 12 | Language | Accepted languages |

### Unity and Search

| Rule | Topic | Description |
|------|-------|-------------|
| Rule 13 | Unity of invention | Single general inventive concept |
| Rule 33 | Relevant prior art | ISA search scope |
| Rule 39 | Subject matter not searched | Excluded from ISA search |
| Rule 43 | International search report | Contents and form of ISR |
| Rule 43bis | Written opinion | Written opinion of ISA |

### National Phase

| Rule | Topic | Description |
|------|-------|-------------|
| Rule 49 | National phase | Copy, translation and fee under Article 22 |
| Rule 49.5 | Translation | Contents and physical requirements of translation |
| Rule 49.6 | Reinstatement of rights | Failure to perform Article 22 acts in time; conditions apply |
| Rule 51bis | Certain national requirements | National law compliance |

## EPO Guidelines Structure

| Topic | EPO Guidelines section |
|-------|------------------------|
| Formalities | Part A; A-II filing and filing-date requirements, A-III formal requirements |
| Abstract | F-II, 2 |
| Description | F-II, 4 |
| Drawings | F-II, 5 |
| Sufficiency | F-III |
| Claims | F-IV |
| Two-part form | F-IV, 2.2-2.3 |
| Independent and dependent claims | F-IV, 3.4 |
| Clarity | F-IV, 4 |
| Description support | F-IV, 6 |
| Unity | F-V |
| Priority | F-VI |
| Inventions and exclusions | G-II |
| Industrial application | G-III |
| State of the art | G-IV |
| Non-prejudicial disclosures | G-V |
| Novelty | G-VI |
| Inventive step | G-VII |

Check the [current Guidelines contents](https://www.epo.org/en/legal/guidelines-epc/2026/index.html) before citing a subsection.


## Presentation Format

Present search results as:

```
EPC/EPO LEGAL RESEARCH RESULTS
=================================

Query: "claim clarity requirements"
Jurisdiction: EPO (EPC + Guidelines)

[1] Art. 84 EPC - The Claims
    "The claims shall define the matter for which protection
    is sought. They shall be clear, concise and be supported
    by the description."

    EPO Guidelines F-IV, 4 - Clarity
    "Each claim should be read giving the words the meaning
    and scope which they normally have in the relevant art..."

    Key Points:
    - Claims must be clear on their own (not by reference to spec)
    - Technical terms given their normal meaning in the art
    - Relative terms need objective reference point
    - Functional features must be verifiable

[2] Rule 43(1) EPC - Form and content of claims
    Where appropriate, use a preamble identifying the relevant known
    features and a characterising portion stating the additional
    features for which protection is sought (paraphrase).

    EPO Guidelines F-IV, 2.2-2.3 - Two-part form
    Use two-part form where appropriate; assess the exceptions before rewriting.

---

Related MPEP Comparison:
- MPEP 2173: Claims Must Particularly Point Out and Distinctly Claim
- 35 USC 112(b): Equivalent US clarity requirement
- Key difference: EPO applies stricter objective clarity standard
```

## Cross-Jurisdiction Mapping

| EPO (EPC) | USPTO (35 USC) | PCT |
|-----------|----------------|-----|
| Art. 54 (Novelty) | 35 USC 102 | Art. 33(2) |
| Art. 56 (Inventive step) | 35 USC 103 | Art. 33(3) |
| Art. 83 (Sufficiency) | 35 USC 112(a) Enablement | Rule 5.1(a)(v) |
| Art. 84 (Clarity) | 35 USC 112(b) | Article 6 |
| Art. 84 (Support) | 35 USC 112(a) Written desc. | Article 6 |
| Rule 42 (Description) | MPEP 608 | Rule 5 |
| Rule 43 (Claims) | 37 CFR 1.75 | Rule 6 |
| Rule 47 (Abstract) | 37 CFR 1.72 | Rule 8 |
| Art. 52(2) (Exclusions) | 35 USC 101 | N/A |
| Art. 53(c) (Medical methods) | N/A (allowed in US) | N/A |

## Tools Available

- **Read**: To load legal documents
- **Bash**: To run legal search queries
- **Write**: To save research results and legal memoranda

Legal references: [EPC Rule 47](https://www.epo.org/en/legal/epc/2020/r47.html), [two-part form where appropriate](https://www.epo.org/en/legal/guidelines-epc/2026/f_iv_2_3.html), [Rule 49(2)](https://www.epo.org/en/legal/epc/2020/r49.html), and [President's presentation decision, OJ EPO 2025 A49](https://www.epo.org/en/legal/official-journal/2025/07/a49). Rule 46 was deleted effective 1 February 2023.

PCT map sources: [Rule 43](https://www.wipo.int/en/web/pct-system/texts/rules/r43), [Rule 43bis](https://www.wipo.int/en/web/pct-system/texts/rules/r43bis), [Rule 49](https://www.wipo.int/en/web/pct-system/texts/rules/r49), and [Article 6](https://www.wipo.int/en/web/pct-system/texts/articles/a6).
