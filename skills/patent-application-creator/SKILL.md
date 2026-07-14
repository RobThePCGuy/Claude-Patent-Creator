---
name: patent-application-creator
description: End-to-end patent campaign from ANY raw material ("here is some information; make a patent") to a filing-ready provisional package - invention mining, worth-it economics (design-around cost, detectability), exhaustive adversarial prior art, claims-first drafting, machine-verified compliance, hostile-examiner attack pass, and an honest no-go when nothing clears the bar or the fence is not worth the money
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
  SUCCESS, not a failure. So is "this is patentable but not worth your
  money — file nothing, or publish defensively." Never inflate a weak
  candidate.
- **The campaign guards the user's money, not just their filing.** The
  population this tool serves cannot afford a technically perfect package
  for a commercially worthless patent. The worth-it question is asked
  BEFORE the expensive phases and re-asked every time the claims narrow —
  a campaign that only discovers "small fence" at the end has already
  spent the user's budget answering the wrong question.
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
(statutory bar dates). Then AUDIT the inventor's own public footprint —
released products, demos, public repositories, marketing pages — and record
first-disclosure dates: the inventor's own disclosures start the US
grace-period clock and can immediately forfeit foreign rights. Do this
before drafting, not after.

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

**Language discipline (non-negotiable).** Sweep results support only
statements of the form "no anticipation found in [outlets searched] as of
[date]" backed by a dated element-by-element chart. Never write "nobody",
"no art exists", "swept clean", or "survives" as facts — an agent's read of
a repository is a snapshot of an evolving codebase, and a second read weeks
later can contradict it. And a date rule that is easy to get wrong under
urgency: **published third-party art can never be outrun.** Anything
already public is prior art against any later filing, grace period or not;
filing-urgency arguments apply only to disclosures that have not happened
yet.

Decision gate: if no candidate has clean ground, write the no-go report
(candidates, killing references, per-candidate reasoning) and STOP. That
report is the deliverable. Then re-run the worth-it screen on each
survivor AT ITS POST-SWEEP WIDTH: the clean ground is always narrower
than the Phase 1 candidate, and the question is whether the SMALLER
fence still costs a competitor anything. A survivor that is now avoidable
by an obvious variant goes in the no-go report too — with its design-around
named, and with the defensive-publication alternative stated (near-free,
permanent, kills later third-party patents on the same mechanism).

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
- **Track the shrinking yard.** Every wall-off and every narrowing
  amendment (here and again after the Phase 5 attack pass) makes the
  claim easier to design around. After the attack pass settles the final
  claim shape, re-run the worth-it screen one last time on what actually
  survived; record the verdict (design-around cost, detectability,
  provisional-vs-defensive-publication recommendation) in the package
  README so the user decides about the patent they can GET, not the one
  they imagined.

Then the specification: field, background (the problems, framed
technically), summary (one paragraph per independent claim), brief
description of drawings, detailed description covering EVERY embodiment
with reference numerals, reduction to practice, and a variations paragraph
(broaden: any model, any similarity metric, thresholds exemplary). The spec
must contain each claim term VERBATIM — the support checker verifies this.

**Source-verified claims (mandatory).** Every limitation of every claim
must be verified against the IMPLEMENTATION itself — open the code — not
against a mining agent's summary and not against header comments, which go
stale (a real campaign found a contract doc describing closest-match
relocation while the executable body below it contained an ambiguity-
refusal gate; the claim drafted from the summary was wrong in a way that
contradicted the specification). The reduction to practice is the tiebreak
for what claims, spec, and figures must all say — and they must all say
the SAME algorithm, or each variant must be expressly a separate
embodiment. Never claim behavior the implementation does not have (a
"valid result of a preservation-type plan" reclassification that the code
never performs is new matter waiting to be rejected).

**Terminal-state completeness.** Any specification asserting deterministic
termination, bounded retries, or guaranteed outcomes must enumerate EVERY
terminal state and every budget transition — including the unglamorous
ones (mechanical exhaustion, global overrun backstops) — and the figure
must show every branch with labeled edges.

Figures: `create_block_diagram` for the system (numbered components
matching the spec), `render_diagram` with hand-written DOT per independent
claim so decision branches carry Yes/No edge labels (`create_flowchart`
does not label edges), with reference numerals on every node.

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

**Verification stamps carry content hashes, and edits invalidate them.**
Every recorded check result must state the SHA-256 (or equivalent) of the
exact artifact text it checked. Any subsequent edit — adding one claim,
touching one sentence — invalidates every stamp on that artifact; re-run
the checks before packaging. A README that says "verified" about an
artifact edited after its verification is the single most damaging
falsehood a package can carry, because a reviewer who catches it stops
trusting everything else. (This is the same input-fingerprint discipline
the campaign's own subject matter implements for AI scans; apply it to
yourself.)

## Phase 5 — Two red teams, not one

**5a. Hostile-examiner attack pass (claims).** Spawn adversarial agents
playing USPTO examiner against the final claims, armed with the sweep's
closest references: strongest anticipation (102) argument, strongest
obviousness (103) combination with per-limitation reference mapping and
motivation to combine, and the Alice (101) attack plus its
technical-solution counter. If an attack lands, narrow the claim or move
the defeated element to a dependent — then re-run Phase 4 on the changed
claims.

**5b. Package red team (the whole artifact).** Attacking the claims is not
enough: a package can have perfect claims and still be unfit to file.
First run the deterministic gate: `check_package` on the assembled
directory. It recomputes every content-hash verification stamp (an edit
after a recorded check is a critical failure), cross-checks claim counts
against every "N claims" assertion, flags readiness language beside draft
markers, catches commentary inside filing copies, and sanity-checks
dates. Fix every critical before spending reviewer effort. Then hand
the ASSEMBLED package — every file, nothing else — to a fresh adversarial
reviewer with zero campaign context, tasked to find: internal
contradictions between README, claims, spec, and figures; statements of
verification that the artifacts themselves contradict; stamps that predate
edits; date errors; strategy commentary that must not be filed; sweeping
prior-art characterizations; and unsupported claim language. Nothing may
be described as filing-ready until the package red team passes. (A real
campaign's package — claims attacked and hardened — was caught by exactly
this kind of fresh-eyes review with a stale "not yet compliance-checked"
header beside a README saying "verified," a claim added after its recorded
check, and three artifacts describing three different reconciliation
algorithms. The claims red team caught none of that, because none of it
was a claims problem.)

## Phase 6 — Package

**Working copies and filing copies are separate files, and the filing
copies are generated mechanically.** Filing documents contain claims and
disclosure text only — zero bracketed strategy notes, zero checker scores,
zero "vs art" commentary, zero next-steps sections, zero restriction
strategy. Backgrounds make no categorical admissions about prior art
("known to the inventor" phrasing, not "no system does X"). Generate the
filing copy by stripping the working copy with a script, then diff-check
that nothing but claims/disclosure text remains.

A filing directory containing: specification and claims (filing copies),
figures (converted to PDF meeting Patent Center requirements — letter/A4,
embedded fonts, visually inspected after conversion; printing SVGs from a
browser is not a QC process), the SB/16 cover sheet data (inventor
residence, correspondence address), micro-entity certification if claimed
(note: gross-income basis also requires small-entity eligibility, the
counted-application limit, and qualification of ownership-interest
holders), and a README with the pro-se provisional path and the 12-month
utility clock, plus the mandatory-claim-read list and unresolved leads for
the eventual attorney review. State plainly what the package is: a
provisional built so the human legal review is fast — not a substitute for
it — and state its verification status with content-hashed stamps, never
with the word "verified" alone.

## Failure modes this workflow exists to prevent

- Trusting a disclosure interview when the invention is in the code.
- Patents-only prior art (the killing reference is usually a product).
- Claiming an element the sweep found (it goes in a dependent, or dies).
- "100% compliant" reports with the load-bearing check silently off.
- Spec paraphrasing claim terms (support gaps surface in prosecution).
- Polishing past a publishing competitor (date pressure is real).
- Shipping a weak application instead of an honest no-go.
- A README that says "verified" about artifacts edited after the check
  (stamps without content hashes are lies waiting to be discovered).
- Claims drafted from an agent's summary instead of the source, or from a
  stale header comment instead of the executable body.
- Claims, specification, and figures describing three different versions
  of the same algorithm.
- Claim language describing behavior the implementation does not have.
- "Deterministic termination" asserted without enumerating every terminal
  state.
- "File before X" urgency about art that is already published (it cannot
  be outrun; only future art can).
- Strategy commentary, checker scores, and novelty absolutes left inside
  documents headed for the Patent Office.
- Attacking only the claims and never the assembled package.
- Spending the budget proving a claim patentable without ever asking
  whether the resulting fence is worth owning — worth-it is asked at
  triage, re-asked when the sweeps narrow the ground, and re-asked when
  the attack pass narrows the claims.
