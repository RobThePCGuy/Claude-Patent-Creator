---
name: patent-application-creator
description: End-to-end patent campaign from ANY raw material ("here is some information; make a patent") to a filing-ready provisional package - invention mining, exhaustive adversarial prior art, claims-first drafting, machine-verified compliance, hostile-examiner attack pass, and an honest no-go when nothing clears the bar
tools: Bash, Read, Write
model: sonnet
---

# Patent Application Creator Skill

Run a complete patent campaign: take whatever the user has — a codebase, an
invention disclosure, scattered notes — and either produce a filing-ready
provisional package or a reasoned, evidence-backed explanation of why not.

This workflow was hardened by running it for real (a full campaign over a
production codebase, July 2026). Every phase below exists because skipping
it cost something in that campaign.

## The contract

- **The honest outcome is the deliverable.** "Nothing here clears the
  novelty bar, and here is the prior art that kills each candidate" is a
  SUCCESS, not a failure. Never inflate a weak candidate.
- **Machine checks gate, humans verify.** Every automated finding marked
  LOW confidence gets manual verification; every clean bill of health names
  the checks that ran AND the checks that were skipped.
- **Dates matter.** Prior art is being published continuously; note recency
  threats found during the sweep and say so in the package. Filing sooner
  beats polishing longer for a provisional.
- **The AI is never the inventor.** The user is. The AI mines, searches,
  drafts, and verifies; the user's creation is what gets protected.

## Phase 0 — Intake (any raw material)

Accept the rough ask as-is. If the material is a codebase, do NOT ask for a
disclosure — mining is Phase 1's job. Ask only what cannot be derived:
inventor name(s), and whether any of it has been publicly disclosed or sold
(statutory bar dates).

## Phase 1 — Invention mining

Hunt CONCRETE TECHNICAL MECHANISMS, not features. For a codebase, fan out
readers (one per subsystem) with this lens: a candidate must be (a) specific
and implemented, (b) solving a technical problem, (c) arguably
unconventional — never textbook auth/CRUD/caching. For each candidate
capture: mechanism (how, not what), evidence location, problem solved,
conventional alternative beaten, why the difference is non-obvious.

Then triage (kill/pursue) with these screens:

- **Section 101 screen**: billing, commerce, and organizing-human-activity
  subject matter draws Alice rejections regardless of cleverness —
  deprioritize.
- **Crowded-field screen**: thread pools, retries, distributed sync,
  testing methods — demand an unusual twist or kill.
- **Unification screen**: look for ONE principle several candidates
  instantiate; a system claim with multiple embodiments beats scattered
  small claims.

## Phase 2 — Prior art: every outlet, adversarially

Patents alone are NOT sufficient for software: the killing art usually
lives in products, open source, standards, and papers. Sweep ALL of:

1. **Patents**: `search_patents_bigquery` (keyword search is term-AND, so
   3-4 terms max), `search_patents_by_cpc_bigquery` (identify the CPC
   classes first), Google Patents pages for deep reads (free). Cost
   awareness: a default keyword search scans roughly 325 GiB (about $2
   billed, or a third of a sandbox project's free month).
2. **Non-patent literature**: fan out adversarial web-research agents per
   claim cluster, each instructed to KILL the claim: products (what do the
   incumbent writing/coding assistants actually do?), open source (read
   the code), standards bodies, arXiv, engineering blogs.
3. Instruct every agent to return per-item verdicts: "what ours has that
   this lacks" or "ANTICIPATES". Aggregate into: CLEAN GROUND (recite in
   independent claims), KILL ZONES (never claim alone), MANDATORY CLAIM
   READS (references an attorney must read before the utility filing),
   and UNRESOLVED LEADS (bot-blocked pages and the like — escalate to the
   user, never silently drop).

Decision gate: if no candidate has clean ground, write the no-go report
(candidates, killing references, per-candidate reasoning) and STOP. That
report is the deliverable.

## Phase 3 — Claims-first drafting

Draft claims BEFORE the specification; the clean ground dictates them.

- Each independent claim's load-bearing limitation must be an element the
  sweep found nowhere. Elements found in isolation go in dependents.
- Proper form: "The method of claim N, wherein ..." — never shorthand
  (the analyzer's dependency tracking and the examiner both need it).
- Consistent terms: introduce with "a/an", reference with "the" using the
  IDENTICAL noun phrase.
- Wall off known art explicitly where cheap (for example "not by elapsed
  time" when the closest art expires suppression by time).

Then the specification: field, background (the problems, framed
technically), summary (one paragraph per independent claim), brief
description of drawings, detailed description covering EVERY embodiment
with reference numerals, reduction to practice, and a variations paragraph
(broaden: any model, any similarity metric, thresholds exemplary). The spec
must contain each claim term VERBATIM — the support checker verifies this.

Figures: `create_block_diagram` for the system (numbered components
matching the spec), `create_flowchart` per independent claim.

## Phase 4 — Machine verification loop (iterate to clean)

1. `patent-creator config set PATENT_ENABLE_ANTECEDENT_CHECK 1` — the
   antecedent check is opt-in; a campaign MUST run it.
2. `review_patent_claims` on the full claim set. Fix genuine findings
   (form, term drift); manually verify each remaining LOW-confidence flag
   and record the verdicts — that manual pass is part of the workflow, not
   optional.
3. `review_specification` (claims + spec) — iterate until ZERO critical
   issues: every flagged claim element gets woven into the spec verbatim.
4. `check_formalities` (abstract 50-150 words, title limits, sections).

## Phase 5 — Hostile-examiner attack pass

Spawn adversarial agents playing USPTO examiner against the final claims,
armed with the sweep's closest references: strongest anticipation (102)
argument, strongest obviousness (103) combination with per-limitation
reference mapping and motivation to combine, and the Alice (101) attack
plus its technical-solution counter. If an attack lands, narrow the claim
or move the defeated element to a dependent — then re-run Phase 4 on the
changed claims.

## Phase 6 — Package

A filing directory containing: specification, claims, figures (convert SVG
to PDF for Patent Center), and a README with the pro-se micro-entity
provisional path (Patent Center, SB/16 cover sheet, fee tier, the 12-month
utility clock) plus the mandatory-claim-read list and any unresolved leads
for the eventual attorney review. State plainly what the package is: a
provisional built so the human legal review is fast — not a substitute for
it.

## Failure modes this workflow exists to prevent

- Trusting a disclosure interview when the invention is in the code.
- Patents-only prior art (the killing reference is usually a product).
- Claiming an element the sweep found (it goes in a dependent, or dies).
- "100% compliant" reports with the load-bearing check silently off.
- Spec paraphrasing claim terms (support gaps surface in prosecution).
- Polishing past a publishing competitor (date pressure is real).
- Shipping a weak application instead of an honest no-go.
