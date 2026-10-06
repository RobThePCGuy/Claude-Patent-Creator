# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start

### As a Claude Code Plugin (Recommended)

```bash
# In Claude Code — add the marketplace and install the plugin
/plugin marketplace add RobThePCGuy/Claude-Patent-Creator
/plugin install claude-patent-creator-standalone@claude-patent-creator
```

### As a pip Package (MCP Server Mode)

```bash
# One-line install (works with or without venv)
pip install git+https://github.com/RobThePCGuy/Claude-Patent-Creator.git && patent-creator setup

# Restart Claude Code

# Test the system
# Ask Claude: "Search MPEP for claim definiteness requirements"
# Ask Claude: "Search for patents about neural networks filed in 2024"
```

**What happens automatically:**
1. Installs package from GitHub
2. Detects GPU (NVIDIA/Apple Silicon/CPU)
3. Uninstalls CPU PyTorch if GPU detected
4. Installs correct PyTorch (CUDA 12.8/MPS/CPU)
5. Restarts setup in subprocess with GPU-enabled PyTorch
6. Downloads MPEP PDFs and builds index with GPU acceleration
7. Registers MCP server with Claude Code

**Optional: Use venv if preferred**
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/macOS
pip install git+https://github.com/RobThePCGuy/Claude-Patent-Creator.git && patent-creator setup
```

**What you can do now:**
- Search 100M+ patents via BigQuery (worldwide)
- Search US patent law (MPEP, 35 USC, 37 CFR)
- Search EPO patent law (EPC, EPO Guidelines) and PCT rules
- Review patent applications for USPTO, EPO, or PCT compliance
- Search EP patents via EPO OPS API (full-text claims/description)
- Generate patent-style technical diagrams
- Create complete patent applications from scratch

---

## Project Overview

**Claude Patent Creator** - An MCP server providing USPTO MPEP-based patent creation guidance using RAG (Retrieval Augmented Generation).

### Core Capabilities

| Feature | Description | Status |
|---------|-------------|--------|
| **MPEP Search** | Search Manual of Patent Examining Procedure + 35 USC + 37 CFR | Ready |
| **Patent Law Search** | Cross-jurisdiction search across US, EPO, and PCT law | Ready |
| **Patent Search** | Search 100M+ worldwide patents via BigQuery | Ready |
| **EPO Patent Search** | Search EP patents via EPO OPS API (full-text claims) | Ready |
| **IPC Search** | Search patents by IPC classification code | Ready |
| **Patent Family Search** | Find related patents across jurisdictions | Ready |
| **US Claims Review** | Automated 35 USC 112(b) compliance checking | Ready |
| **EPO Claims Review** | Art. 84 EPC compliance checking (Art. 123(2) added-matter not implemented) | Partial |
| **US Specification Review** | Written description, enablement, best mode analysis | Ready |
| **EPO Specification Review** | Art. 83 EPC sufficiency of disclosure (Art. 123(2) added-matter not implemented) | Partial |
| **US Formalities Check** | MPEP 608 compliance (abstract, title, drawings) | Ready |
| **EPO Formalities Check** | Rules 42-49 EPC compliance | Ready |
| **PCT Formalities Check** | PCT Rules 5-12 compliance | Ready |
| **Diagram Generation** | Patent-style technical diagrams (Graphviz) | Ready |
| **Patent Creation** | Complete patent application drafting workflow | Ready |

### Technology Stack

```
MCP Python SDK 2.x (MCPServer)
+- RAG Pipeline: FAISS + BM25 + HyDE + Cross-Encoder Reranking
+- Embeddings: BGE-base-en-v1.5 (768-dim)
+- Reranker: MS-MARCO MiniLM-L-6-v2
+- Patent Search: Google BigQuery (100M+ patents worldwide)
+- EPO Search: EPO OPS API v3.2 (EP full-text claims/description)
+- Legal Sources: MPEP + 35 USC + 37 CFR + EPC + EPO Guidelines + PCT Rules
+- Validation: Pydantic v2 with type safety
+- Logging: Structured JSON/human formats
+- GPU Acceleration: PyTorch CUDA 12.8
```

---

## Skills System

Claude will automatically activate specialized skills based on your task. These skills provide deep expertise for specific workflows:

| Skill | Activate When | What It Provides |
|-------|---------------|------------------|
| **setup-assistant** | Installing, configuring, authenticating, or troubleshooting setup | Complete installation lifecycle from pre-checks to first-use validation |
| **development-assistant** | Adding features, creating MCP tools, extending functionality | Feature development lifecycle with templates and best practices |
| **index-manager** | Building, rebuilding, or optimizing the MPEP index | MPEP index lifecycle from PDF downloads to production optimization |
| **troubleshooting-assistant** | Encountering errors, performance issues, or unexpected behavior | Systematic 6-step diagnostic methodology for all components |
| **testing-assistant** | Running tests, validation, or quality assurance | Complete test suite execution and validation workflows |
| **patent-reviewer** | Reviewing patent applications for USPTO compliance | Expert review system with automated compliance checking |
| **patent-claims-analyzer** | Reviewing claims specifically for 35 USC 112(b) | Deep-dive claims analysis (definiteness, antecedent basis, structure) |
| **patent-search** | Searching patents, prior art, or competitive intelligence | BigQuery (100M+) search workflows via MCP tools |
| **bigquery-patent-search** | Quick BigQuery-only patent searching | Keyword, CPC, and patent detail retrieval across 100M+ patents |
| **mpep-search** | Finding MPEP sections, statutes, or regulations | Hybrid RAG search across MPEP, 35 USC, 37 CFR |
| **patent-diagram-generator** | Creating technical diagrams for patents | Graphviz-based diagram generation |
| **patent-application-creator** | Drafting patent applications interactively | Guided end-to-end creation (prior art, claims, spec, diagrams, compliance) |
| **prior-art-search** | Conducting novelty or freedom-to-operate analysis | Prior art search and analysis workflows |
| **epo-patent-analyzer** | Reviewing patents for EPO compliance | Art. 84 (claims), Art. 83 (sufficiency), Rules 42-49 (formalities) |
| **epo-patent-search** | Searching EP patents via EPO OPS + BigQuery | EPO OPS API + BigQuery cross-jurisdiction search |
| **pct-application** | Preparing PCT international applications | PCT Rules 5-12 compliance, unity of invention |
| **epc-search** | Searching EPC, EPO Guidelines, PCT rules | `search_patent_law` with jurisdiction filtering |

Each skill includes its reference documentation in `skills/[skill-name]/SKILL.md`.

---

## Subagents System

For long-running, complex workflows that benefit from context isolation, use specialized subagents that work autonomously:

| Subagent | Use When | Duration | What It Delivers |
|----------|----------|----------|------------------|
| **patent-creator** | Drafting complete patent applications autonomously (markdown + SVG output; DOCX/PDF conversion required before filing) | ~55-80 min | Draft filing package (specification, claims, abstract, diagrams, validation report) |
| **prior-art-searcher** | Conducting comprehensive prior art searches without interruption | 15-30 min | Patentability report (novelty/obviousness analysis, top 10 prior art, claim strategy, IDS list) |

### When to Use Subagents vs Skills

**Use Subagents when:**
- Long-running workflows (10+ minutes)
- User wants to continue other work during execution
- Benefits from uninterrupted focus
- Produces complete deliverable at end

**Use Skills when:**
- Interactive workflows needing user input
- User wants to see progress/ask questions
- Fast operations (<10 minutes)
- Benefits from conversation context

**Example:**
- "Create a patent for my invention, use subagent" -> patent-creator works for 55-80 min independently
- "Help me create a patent interactively" -> patent-reviewer skill guides you step-by-step

Subagents are located in `agents/` at the repo root and have access to all MCP tools.

---

## Slash Commands

Quick-access workflows for common patent tasks:

| Command | Description | Use When |
|---------|-------------|----------|
| `/create-patent` | Draft patent application workflow (6 phases, ~55-80 min, markdown/SVG output) | Drafting a NEW patent application from scratch |
| `/full-review` | Comprehensive parallel review (claims + spec + formalities) | Reviewing an EXISTING complete application |
| `/review-claims` | Claims-only analysis (35 USC 112b) | Focused claims compliance checking |
| `/review-specification` | Specification analysis (35 USC 112a) | Focused specification adequacy review |
| `/review-formalities` | Formalities check (MPEP 608) | Abstract, title, drawings compliance |
| `/review-epo-claims` | EPO Art. 84 claims analysis | EPO claims clarity, conciseness, support |
| `/review-epo-formalities` | EPO Rules 42-49 formalities check | EPO-specific formalities compliance |
| `/check-pct-formalities` | PCT Rules 5-12 formalities check | PCT international application compliance |
| `/create-epo-patent` | EPO patent creation workflow | Create patent targeting EPO filing |
| `/search-epo` | EPO patent search | Search via EPO OPS API + BigQuery |

---

## System Architecture

### Visual Architecture

```
+---------------------------------------------------------+
|                   Claude Code / User                     |
+----------------+----------------------------------------+
                 | MCP Protocol (stdio)
+----------------v----------------------------------------+
|              MCPServer (server.py)                       |
|  +-------------------------------------------------+   |
|  | MCP Tools: 35+ tools for patent review & search |   |
|  +-------------------------------------------------+   |
+--+------+------+------+---------------------+-----+----+
   |      |      |      |                     |     |
   v      v      v      v                     v     v
+----+ +-----+ +----+ +----------+ +-------+ +--------+
|MPEP| | BQ  | |EPO | |US + EPO  | | PCT   | |Diagrams|
|+EPC| |100M+| |OPS | |+ PCT     | |Forms  | |(Graphvz|
|+PCT| |     | |API | |Analyzers | |       | |        |
+--+-+ +--+--+ +--+-+ +----+-----+ +--+----+ +--------+
   |      |       |         |          |
   v      v       v         v          v
+--------------------------------------------------+
|       RAG Pipeline (Hybrid Search)               |
| FAISS Vector + BM25 Lexical + HyDE + Reranking  |
| Sources: MPEP + USC + CFR + EPC + EPO + PCT     |
+--------------------------------------------------+
```

### Directory Structure

```
.claude-plugin/          # Plugin marketplace + manifest
+-- plugin.json          # Plugin identity and component paths
+-- marketplace.json     # Marketplace catalog for distribution

mcp_server/              # Core MCP server and tools
+-- server.py            # MCPServer entry point (main)
+-- mpep_search.py       # US + EPO + PCT hybrid RAG search
+-- bigquery_search.py   # BigQuery patent search (100M+ patents)
+-- epo_api.py           # EPO OPS API v3.2 client
+-- epo_downloaders.py   # EPO/WIPO legal document downloaders
+-- claims_analyzer.py   # 35 USC 112(b) compliance checker
+-- epo_claims_analyzer.py     # Art. 84 EPC compliance checker
+-- specification_analyzer.py  # 112(a) adequacy checker
+-- epo_specification_analyzer.py  # Art. 83 EPC sufficiency checker
+-- formalities_checker.py     # MPEP 608 formalities
+-- epo_formalities_checker.py # Rules 42-49 EPC formalities
+-- pct_formalities_checker.py # PCT Rules 5-12 formalities
+-- diagram_generator.py       # Graphviz diagram tools

commands/                # Slash commands (11)
skills/                  # Specialized skills (15)
agents/                  # Autonomous agents (10)
hooks/                   # Event-driven hooks
scripts/                 # Testing and setup utilities
data/                    # Index storage (git-ignored)
pdfs/                    # MPEP/USC/CFR PDFs (git-ignored)
```

---

## Critical Gotchas

### NumPy 2.x and FAISS Compatibility

**Resolved:** As of faiss-cpu 1.13.0 (Nov 2025), numpy 2.x is fully supported. The project requires `faiss-cpu>=1.13.0` and `numpy>=1.26.0,<3.0.0`.

**Legacy note:** faiss-cpu 1.12.0 and earlier were compiled against numpy 1.x and would crash with `ImportError: numpy.core.multiarray failed to import`. This was fixed upstream in [PR #4523](https://github.com/facebookresearch/faiss/pull/4523).

### PyTorch Installation Order (CRITICAL)

**Problem:** Installing `sentence-transformers` before PyTorch results in CPU-only PyTorch, even on GPU systems.

**Solution:**
```bash
# CORRECT ORDER:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
pip install sentence-transformers  # Now uses existing GPU torch

# WRONG ORDER (results in CPU-only):
pip install sentence-transformers  # Installs CPU torch as dependency
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128  # Won't upgrade
```

**The `install.py` script handles this correctly.** If manually installing, ALWAYS install PyTorch first.

### Windows Path Handling in MCP Config

**Problem:** MCP registration fails with backslashes in Windows paths.

**Solution:**
```bash
# CORRECT (forward slashes):
claude mcp add ... -- "C:/Users/<YOUR_USER>/venv/Scripts/python.exe" "C:/Users/<YOUR_USER>/server.py"

# WRONG (backslashes):
claude mcp add ... -- "C:\Users\<YOUR_USER>\venv\Scripts\python.exe" "C:\Users\<YOUR_USER>\server.py"
```

**The `install.py` script handles this via `path_utils.py`.** Always use `PathFormatter.format_for_claude_mcp()` when constructing paths programmatically.

### Virtual Environment Activation

**Problem:** `ModuleNotFoundError` when running scripts manually.

**Solution:**
```bash
# ALWAYS activate first for manual operations:
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/macOS

# Then run commands:
python scripts/test_gpu.py
patent-creator health
```

**Note:** Claude Code activates venv automatically. This only matters for manual terminal operations.

### NumPy Version Requirements

NumPy 2.x is supported with faiss-cpu >=1.13.0 (enforced in pyproject.toml). If you encounter numpy-related import errors, ensure faiss-cpu is at least 1.13.0:
```bash
pip install "faiss-cpu>=1.13.0"
```

### Git Bash Required on Windows

**Problem:** `claude mcp add` command fails on Windows.

**Solution:**
```bash
# Install Git for Windows (includes Git Bash)
# https://git-scm.com/download/win

# Set environment variable
export CLAUDE_CODE_GIT_BASH_PATH=C:/Program Files/Git/bin/bash.exe

# Or add to .env:
CLAUDE_CODE_GIT_BASH_PATH=C:\dev\Git\bin\bash.exe
```

### Debugging MCP Server Issues

**Enable debug logging:**
```bash
PATENT_LOG_LEVEL=DEBUG patent-creator health
```

**Claude Code MCP logs:**
```
# Linux/macOS
~/.config/claude/logs/mcp.log

# Windows
%APPDATA%\claude\logs\mcp.log
```

**Run Claude Code in debug mode:**
```bash
claude --debug
```

**MCP config file location** (for manual fixes):
```
# Linux/macOS
~/.config/claude/mcp_config.json

# Windows
%APPDATA%\claude\mcp_config.json
```

---

## Quick Reference

### Essential Commands

```bash
# System health check
patent-creator health

# Rebuild MPEP index
patent-creator rebuild-index

# Verify MCP configuration
patent-creator verify-config

# Check BigQuery authentication
patent-creator check-bigquery

# Test GPU
python scripts/test_gpu.py

# Test BigQuery
python scripts/test_bigquery.py

# Full system test
python scripts/test_install.py
```

### Key File Locations

| Item | Location | Description |
|------|----------|-------------|
| **MCP Server** | `mcp_server/server.py` | Main entry point |
| **MPEP Index** | `mcp_server/index/` | FAISS + BM25 index files |
| **MPEP PDFs** | `pdfs/` | Downloaded USPTO documents |
| **Dependencies** | `pyproject.toml` | All package requirements |
| **Configuration** | `.env` | Environment variables |
| **CLI Tool** | `mcp_server/cli.py` | `patent-creator` command |
| **Skills** | `.claude/skills/` | Specialized skill documentation |
| **Subagents** | `agents/` | Autonomous workflow subagents |
| **Commands** | `.claude/commands/` | Slash command definitions |

### Environment Variables

```bash
# Required
GOOGLE_CLOUD_PROJECT=your_project_id
ANTHROPIC_API_KEY=<YOUR_ANTHROPIC_API_KEY>

# EPO OPS API (optional — for EP patent search with full-text claims)
EPO_OPS_KEY=your_epo_consumer_key          # Free at developers.epo.org
EPO_OPS_SECRET=your_epo_consumer_secret

# Optional (with defaults)
PATENT_LOG_LEVEL=INFO              # Logging level
PATENT_LOG_FORMAT=human            # Log format
PATENT_ENABLE_METRICS=true         # Performance tracking
PATENT_MPEP_USE_HYDE=false         # HyDE for MPEP
PATENT_OPERATION_TIMEOUT=300       # Operation timeout (seconds)

# Windows only
CLAUDE_CODE_GIT_BASH_PATH=C:\dev\Git\bin\bash.exe
```

### Version Compatibility Matrix

| Component | Min Version | Max Version | Recommended | Critical Notes |
|-----------|-------------|-------------|-------------|----------------|
| **Python** | 3.9 | 3.14 | 3.11 | 3.14 experimental |
| **PyTorch** | 2.0 | latest | 2.9.1+cu128 | CUDA 12.8 support |
| **sentence-transformers** | 5.1.2 | <6.0 | 5.1.2 | Requires transformers 4.41.0+ |
| **transformers** | 4.57.1 | <5.0 | 4.57.1 | HuggingFace models |
| **NumPy** | 1.26.0 | <3.0 | latest | numpy 2.x supported with faiss-cpu >=1.13.0 |
| **faiss-cpu** | 1.13.0 | latest | 1.13.2 | numpy 2.x support added in 1.13.0 |
| **Pydantic** | 2.10.0 | latest | 2.10.0+ | V2 required |
| **google-cloud-bigquery** | 3.38.0 | latest | 3.38.0+ | Patent search (100M+) |
| **anthropic** | 0.72.1 | latest | 0.72.1+ | Claude API (optional) |
| **openai** | 2.8.0 | latest | 2.8.0+ | OpenAI API (optional) |

### Common Code Patterns

**Add MCP Tool:**
```python
@mcp.tool()
@validate_input(YourInputModel)
@track_performance
def your_tool(param: str) -> dict:
    """Tool description for Claude."""
    return {"result": "data"}
```

**Search MPEP:**
```python
from mcp_server.mpep_search import MPEPIndex
index = MPEPIndex()
index.build_index()  # loads the on-disk index; search() raises until this runs
results = index.search("claim definiteness", top_k=5)
```

**Search BigQuery Patents:**
```python
from mcp_server.bigquery_search import BigQueryPatentSearch
search = BigQueryPatentSearch()
results = search.search_by_keywords("neural networks", limit=10)
```

---

## Getting Help

For detailed guidance on specific tasks, Claude will automatically activate the appropriate skill:

- **Installation issues?** -> setup-assistant skill
- **Want to add a feature?** -> development-assistant skill
- **Something broken?** -> troubleshooting-assistant skill
- **Need to rebuild index?** -> index-manager skill
- **Running tests?** -> testing-assistant skill

Each skill contains comprehensive reference documentation and step-by-step workflows.

---

## Best Practices

1. **Always activate venv for manual operations** (Claude Code handles automatically)
2. **Use `patent-creator` CLI for system operations** (health, rebuild, verify)
3. **Test with `patent-creator health` after changes**
4. **Add performance monitoring to expensive operations** (`@track_performance`)
5. **Use Pydantic validation for all new MCP tools** (type safety + errors)
6. **Include MPEP citations in error messages** when relevant
7. **Maintain backward compatibility** with graceful fallbacks
8. **Test on both CPU and GPU** if modifying search code
9. **Use structured logging** with contextual fields
10. **Follow existing analyzer patterns** when adding new analyzers
11. **Return JSON-serializable types** from MCP tools (dict, list, primitives)
12. **Write detailed docstrings** for MCP tools (Claude sees them)
13. **Use `OperationTimer` for sub-operation profiling**
14. **Check `settings.has_bigquery_configured()` before using BigQuery**
15. **Always use forward slashes in paths** for MCP configuration
