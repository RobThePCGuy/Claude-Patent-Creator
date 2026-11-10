# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `search_non_patent_literature`: papers and preprints as prior art, from
  OpenAlex, arXiv and Semantic Scholar at once, free with no key. Filters by
  publication date (set `published_before` to the priority date), folds the
  same paper found by several sources into one result, and reports per source
  whether it was searched, so a busy source never reads as "no prior art".
  Optional free keys `OPENALEX_API_KEY` and `SEMANTIC_SCHOLAR_API_KEY`. The
  gap was pointed out by @JuampiHernandez in #104.
- Paper dates are cross-checked with Crossref (free, no key) whenever a
  priority-date cutoff is set. Indexes sometimes list the wrong year (seen
  live: a 2026 paper listed as 2016); a result whose DOI was registered after
  the cutoff and long after its listed date, or whose publisher gives a later
  date, now carries a `date_check` telling the user to confirm it. Papers from
  before 2000 are not flagged for late DOIs (DOIs did not exist yet), and the
  earliest publisher date counts, since online-first is public. Every result
  says where its date came from (`date_source`), and the note counts dates
  that could not be cross-checked. Also flagged: 1970-01-01 (a missing date
  in disguise, caught on 2020-2021 papers), publisher dates years apart
  including the journal issue's, a year inside the DOI later than the listed
  date, and sources that disagree on a merged paper's date. Older papers whose
  DOI came after the cutoff, and whose age rests only on the publisher's print
  date, get a `date_note` saying so.
- Optional stdio handshake workaround and troubleshooting guidance for the
  Claude Code `-32022` negotiation error (#102, reported by @DanielTillett).
- Consolidated utility-patent-reviewer into Claude-Patent-Creator
- GitHub issue templates (bug report, feature request, question) and PR template
- Code quality tooling config (Ruff lint rules, isort, mypy, pytest, coverage, bandit)
- Spell checking config (`.typos.toml`)
- CONTRIBUTING.md and SECURITY.md

### Fixed
- Setup registered the wrong Python on venv installs: it followed the venv's
  `python` link back to the system interpreter, which cannot import `mcp`, so
  Claude Code failed to connect while setup, `health` and `verify-config` all
  reported success. Registration keeps the venv path, and setup and
  `verify-config` now start the server and complete a real MCP handshake
  before saying it is connected. Found by a fresh-user install walk.
- `health` and `serve` refused to run after the PDF cleanup that setup itself
  offers; they now need only the built index, and setup no longer
  re-downloads and rebuilds when the PDFs were removed on purpose.
- Setup asks before installing Graphviz with the system package manager and
  never installs it unattended; the diagram tools' error gives the exact
  install command.
- `check_formalities` no longer reports `ready_to_file` when parts were not
  supplied or a component check failed, and lists checks run and skipped.
  `review_patent_claims` leads with skipped checks and no longer calls claims
  "compliant" when the antecedent-basis check did not run.
- Stale command suggestions (`scripts/setup_bigquery_auth.py`, `install.py`,
  `status --verbose`) point at commands that exist.

- Paper search spaces its Semantic Scholar requests at least 1.1 s apart
  across the whole server and retries a refused one with exponential
  backoff (1, 2, 4 s plus jitter), as Semantic Scholar requires, so back-to-back
  searches stay under the 1 request/second key limit instead of losing that
  source's results.
- Reject invalid explicit BigQuery spending caps before any query instead of
  silently substituting the 350 GiB default (#101).
- Bind patent family IDs as strings for the BigQuery public-data schema (#97).
- Annotate project-local diagram outputs while retaining path confinement (#98).
- Parse multi-hit EPO search wrappers and prefer family docdb country/kind fields
  (#99, #100). Reports and detailed reproductions for #97–#101 by @DanielTillett.
- `downloaders`: MPEP/USPTO downloads now verify TLS against the bundled `certifi`
  CA store, fixing `SSL: CERTIFICATE_VERIFY_FAILED` on python.org macOS Python (#23)
- `utils/device`: honor the documented `PATENT_MPEP_DEVICE` env var (`cpu`/`gpu`/
  `mps`), which was referenced in docs but never read; `FORCE_CPU` still works (#23)
- `utils/device`: detect Apple Silicon (MPS) and stay on CPU by default — MPS runs
  the BGE embedding workload ~50x slower; opt in with `PATENT_MPEP_DEVICE=mps` (#23)
- `hardware_detect`/`auto_setup`: when `nvidia-smi` can't report compute capability
  (older drivers), select the CUDA wheel by GPU product name so legacy cards still
  get cu126 without forcing Blackwell onto cu126; add `PATENT_TORCH_CUDA=cu126|cu128`
  manual override; correct the cu126 Maxwell/Windows kernel-coverage claim (#26 follow-up)
- `analyzer_base`: WARNING/INFO severity levels now in SEVERITY_ORDER (prevents KeyError)
- `base_index`: Guard against FAISS returning -1 for unfound results
- `base_index`: Guard against empty candidates in reranker
- `claims_analyzer`: Circular dependency guard prevents infinite recursion
- `claims_analyzer`: Self-referencing claim prevention
- `claims_analyzer`: Fixed `_singularize()` and `_pluralize()` edge cases
- `claims_analyzer`: Normalized compliance scoring per claim count
- `claims_analyzer`: Better preamble and limitation location detection
- `specification_analyzer`: State reset on each analysis call (prevents stale data)
- `specification_analyzer`: Word-boundary matching prevents false positives
- `specification_analyzer`: Coverage calculated on independent claims only
- `specification_analyzer`: Expanded element extraction patterns
- `formalities_checker`: Word-boundary regex for forbidden term detection
- `formalities_checker`: Better figure reference regex (handles FIGS, sub-figures, ranges)
- `evaluation`: Division-by-zero protection in comparison
- `downloaders`: URL scheme validation (HTTP/HTTPS only)
- `downloaders`: Partial file cleanup on download failure
- `patent_corpus`: Safe integer parsing for TSV fields
- `diagram_generator`: defusedxml for SVG parsing, quoted node IDs, tspan handling

### Changed
- README Quick Start rewritten for first-time users: prerequisites first, a
  virtual-environment install with copyable Mac/Linux and Windows lines, the
  plugin as its own step, and a free SerpApi key for patent search. One
  supported Python range (3.10-3.13) across the README, setup command and
  skills. Removed two settings nothing reads (`PATENT_ENABLE_METRICS`,
  `PATENT_OPERATION_TIMEOUT`).

## [0.2.0] - 2026-03-22

### Added
- BigQuery patent search (100M+ worldwide patents)
- 13 specialized skills for Claude Code
- 10 autonomous agents for long-running workflows
- 11 slash commands for common patent tasks
- Monitoring and performance tracking (`@track_performance`)
- Structured logging (JSON/human formats)
- Pydantic v2 input validation for all MCP tools
- Modular tools architecture (`mcp_server/tools/`)
- Hardware detection for GPU/CPU PyTorch installation
- Dependabot configuration for automated dependency updates

### Fixed
- Import errors, Unicode crashes, and stale version checks
- NumPy 2.x compatibility (faiss-cpu >=1.13.0)
- macOS Apple Silicon FAISS segfault
- CLI ModuleNotFoundError
- Lazy loading, security hardening, config fixes

## [0.1.0] - 2025-11-15

### Added
- Initial release
- MPEP/35 USC/37 CFR hybrid RAG search (FAISS + BM25 + HyDE + cross-encoder reranking)
- Claims analyzer (35 USC 112(b) compliance)
- Specification analyzer (35 USC 112(a) adequacy)
- Formalities checker (MPEP 608 compliance)
- Diagram generation (Graphviz-based)
- USPTO API integration
- PatentsView search integration
- CLI tool (`patent-creator`)
- MCP server with 25+ tools
