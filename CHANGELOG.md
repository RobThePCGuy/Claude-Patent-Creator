# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Consolidated utility-patent-reviewer into Claude-Patent-Creator
- GitHub issue templates (bug report, feature request, question) and PR template
- Code quality tooling config (Ruff lint rules, isort, mypy, pytest, coverage, bandit)
- Spell checking config (`.typos.toml`)
- CONTRIBUTING.md and SECURITY.md

### Fixed
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

## [0.2.0] - 2026-03-22

### Added
- BigQuery patent search (76M+ worldwide patents)
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
