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
- Plugin docs no longer promise checks the tools don't run (antecedent basis,
  corresponding structure, description support, best mode, physical page
  checks), and analyzer result fields are documented as returned.
- EPO and PCT guidance corrected against the EPC, EPO Guidelines and PCT
  Regulations: abstract length is a preference, two-part claims are "where
  appropriate", deleted EPC Rule 46 is no longer cited, the PCT abstract figure
  is chosen on the request form, and legal-reference maps point to the right
  rules. Static fee tables now point to the official fee schedules.
- European patent search docs say what the integration returns: OPS results
  are worldwide unless filtered, and register and in-force status must be
  checked in the European Patent Register.
- BigQuery searches keep OR as OR, honour every prior-art filter, and read
  saved settings; cost guidance reflects real scan sizes.
- Setup and the download commands report a failed required download as a
  failure. An optional supplement that fails is named as missing.
- Diagnostic scripts test what they claim; diagram labels that don't match are
  reported; the settings window reads yes/on/1 and an empty batch size
  correctly; health-check commands work in PowerShell and with spaces in paths.
- Workflows use SerpApi first and treat BigQuery as optional; Windows commands
  are valid PowerShell; docs name files and commands that exist.
- The old installers (`install.py`, `scripts/install-gpu.*`) are removed; the
  pip install and `patent-creator setup` replace them.
- Mac output no longer starts with PyTorch's "Redirects" note, and an
  unavailable EPO Guidelines PDF is no longer shown as an error when the
  website copy downloads instead.

- Public unmerged code is no longer treated as undisclosed; history mining
  requires public-access and date evidence, with unknowns preserved.
- PCT calendars use the priority date, put US/JP entry at 30 months and EP
  at 31, and state the alternative Chapter II demand deadline, with WIPO sources.
- Agents that need MCP tools inherit the connected session's tools instead
  of excluding them through built-in-only allowlists.
- EPO/PCT formalities now expose checks run/skipped and scoped verdicts like
  the US checker. Missing inputs, failed checks, and PCT's unverified physical
  requirements cannot produce readiness; unavailable checkers report no checks.
- US/EPO specification review checks dependent claims and includes them in
  support coverage instead of reporting only independent-claim coverage.
- Claims-review scores no longer authorize filing. Enabling antecedent basis
  requires a server/Claude Code restart and an actual claims result naming
  `antecedent_basis` in `checks_run` before the workflow can proceed.
- EPO drafting uses Article 54(5) purpose-limited product claims for new
  second-medical-use filings, with the Swiss-type cutoff and EPO sources.
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
- Setup looked frozen for over half an hour: the CLI imports the server stack
  under a stderr capture, and the logger kept writing into that buffer, so
  every index-build message vanished. Logs now follow the live terminal, the
  build prints a plain progress line with time left every few percent, and
  the time estimate matches the device (25-40 min without an NVIDIA GPU).
- The missing SerpApi key message gives the exact `config set` command for
  this install instead of a project `.env`, and BigQuery is offered as a ready
  fallback only when it is configured. Commands setup prints name the
  installed executable, so they work from a virtual environment.
- A short abstract is advice, not a failure: under 50 words is MPEP
  608.01(b)'s preference. Over 150 words still fails (37 CFR 1.72(b)).
- Status no longer marks 35 USC, 37 CFR and Updates `[X]` after the offered
  PDF cleanup; their text is in the index.
- The plugin's setup command installs into the same `~/patent-creator-venv`
  folder as the README (a normal install, so plugin updates can't break it)
  and walks through turning on patent search.
- European Patent Convention articles were indexed as Implementing
  Regulations (0 article chunks, 4,927 rule chunks): an amendment table on
  page 1 mentions "Implementing Regulations" and the extractor switched
  there. The split now follows the PDF's own bookmarks (1,306 article and
  1,794 rule chunks on the real PDF), so an EPC-only search finds Article 84.
  Indexes built before this are detected; `health` says a rebuild is needed
  and re-running `setup` rebuilds automatically.
- `get_mpep_section` found nothing for a subsection like 608 because labels
  are chapter-level. It now finds the section's heading inside its chapter,
  returns the content in order, and says when boundaries are approximate.
- The EPO Guidelines download uses the current published PDF with a verified
  fallback, and `search_patent_law` says which sources it didn't search even
  when others returned results.
- Saved settings now apply at startup in both the CLI and the server, so a
  saved `GOOGLE_CLOUD_PROJECT`, `PATENT_DATA_DIR` or `PATENT_LOG_FORMAT`
  takes effect (real environment variables and `.env` still win), and
  `config list` reports saved values as saved.
- EPO Guidelines results from the HTML download keep their official page link
  (`source_url`) and Part/Chapter/section locator on every chunk, not only the
  first one of each page.
- The Guidelines HTML download reports progress at least every 20 seconds
  instead of going silent for minutes during a large batch.
- Every recovery message (settings notes, law-search coverage warnings,
  index warnings) names the installed `patent-creator` command, so it runs
  from an unactivated virtual environment.
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
