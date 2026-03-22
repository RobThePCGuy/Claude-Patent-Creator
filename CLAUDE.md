# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start (One-Line Install)

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
- Search 76M+ patents via BigQuery
- Search MPEP, 35 USC, 37 CFR regulations
- Review patent applications for USPTO compliance
- Generate patent-style technical diagrams
- Create complete patent applications from scratch

---

## Project Overview

**Claude Patent Creator** - An MCP server providing USPTO MPEP-based patent creation guidance using RAG (Retrieval Augmented Generation).

### Core Capabilities

| Feature | Description | Status |
|---------|-------------|--------|
| **MPEP Search** | Search Manual of Patent Examining Procedure + 35 USC + 37 CFR | Ready |
| **Patent Search** | Search 76M+ worldwide patents via BigQuery | Ready |
| **Claims Review** | Automated 35 USC 112(b) compliance checking | Ready |
| **Specification Review** | Written description, enablement, best mode analysis | Ready |
| **Formalities Check** | MPEP 608 compliance (abstract, title, drawings) | Ready |
| **Diagram Generation** | Patent-style technical diagrams (Graphviz) | Ready |
| **Patent Creation** | Complete patent application drafting workflow | Ready |

### Technology Stack

```
FastMCP (MCP Server Framework)
+- RAG Pipeline: FAISS + BM25 + HyDE + Cross-Encoder Reranking
+- Embeddings: BGE-base-en-v1.5 (768-dim)
+- Reranker: MS-MARCO MiniLM-L-6-v2
+- Patent Search: Google BigQuery (patents-public-data)
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
| **patent-search** | Searching patents, prior art, or competitive intelligence | BigQuery (76M+) and PatentsView API search workflows |
| **mpep-search** | Finding MPEP sections, statutes, or regulations | Hybrid RAG search across MPEP, 35 USC, 37 CFR |
| **patent-diagrams** | Creating technical diagrams for patents | Graphviz-based diagram generation |
| **prior-art-search** | Conducting novelty or freedom-to-operate analysis | Prior art search and analysis workflows |

Each skill includes detailed reference documentation in `skills/[skill-name]/reference/` directories.

---

## Subagents System

For long-running, complex workflows that benefit from context isolation, use specialized subagents that work autonomously:

| Subagent | Use When | Duration | What It Delivers |
|----------|----------|----------|------------------|
| **patent-creator** | Creating complete USPTO-ready patent applications autonomously | 55-80 min | Complete filing package (specification, claims, abstract, diagrams, validation report) |
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

Subagents are located in `.claude/subagents/` and have access to all MCP tools.

---

## Slash Commands

Quick-access workflows for common patent tasks:

| Command | Description | Use When |
|---------|-------------|----------|
| `/create-patent` | Complete patent creation workflow (6 phases, 55-80 min) | Creating a NEW patent application from scratch |
| `/full-review` | Comprehensive parallel review (claims + spec + formalities) | Reviewing an EXISTING complete application |
| `/review-claims` | Claims-only analysis (35 USC 112b) | Focused claims compliance checking |
| `/review-specification` | Specification analysis (35 USC 112a) | Focused specification adequacy review |
| `/review-formalities` | Formalities check (MPEP 608) | Abstract, title, drawings compliance |

---

## System Architecture

### Visual Architecture

```
+---------------------------------------------------------+
|                   Claude Code / User                     |
+----------------+----------------------------------------+
                 | MCP Protocol (stdio)
+----------------v----------------------------------------+
|              FastMCP Server (server.py)                  |
|  +-------------------------------------------------+   |
|  | MCP Tools: 25+ tools for patent review & search |   |
|  +-------------------------------------------------+   |
+--+----------+----------+--------------------------+----+
   |          |          |                          |
   v          v          v                          v
+------+ +--------+ +----------+         +--------------+
| MPEP | |BigQuery| |Analyzers |         |  Diagrams    |
|Search| | Cloud  | | (Claims, |         |  (Graphviz)  |
|      | |        | |  Spec,   |         |              |
|500MB | |  76M+  | |Formality)|         |   SVG/PNG    |
+--+---+ +---+----+ +----+-----+         +--------------+
   |         |           |
   v         v           v
+--------------------------------------------------+
|       RAG Pipeline (Hybrid Search)               |
| FAISS Vector + BM25 Lexical + HyDE + Reranking  |
+--------------------------------------------------+
```

### Directory Structure

```
mcp_server/              # Core MCP server and tools
+-- server.py            # FastMCP server entry point (main)
+-- mpep_search.py       # MPEP/USC/CFR hybrid RAG search
+-- bigquery_search.py   # BigQuery patent search (76M+ patents)
+-- claims_analyzer.py   # 35 USC 112(b) compliance checker
+-- specification_analyzer.py  # 112(a) adequacy checker
+-- formalities_checker.py     # MPEP 608 formalities
+-- diagram_generator.py       # Graphviz diagram tools
+-- .claude/             # Claude Code integration
    +-- commands/        # Slash commands
    +-- skills/          # Specialized skills with reference docs

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
| **Subagents** | `.claude/subagents/` | Autonomous workflow subagents |
| **Commands** | `.claude/commands/` | Slash command definitions |

### Environment Variables

```bash
# Required
GOOGLE_CLOUD_PROJECT=your_project_id
ANTHROPIC_API_KEY=<YOUR_ANTHROPIC_API_KEY>

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

**See PACKAGE_COMPATIBILITY_2025.md for complete details**

| Component | Min Version | Max Version | Recommended | Critical Notes |
|-----------|-------------|-------------|-------------|----------------|
| **Python** | 3.9 | 3.14 | 3.11 | 3.14 experimental |
| **PyTorch** | 2.0 | latest | 2.9.1+cu128 | CUDA 12.8 support |
| **sentence-transformers** | 5.1.2 | <6.0 | 5.1.2 | Requires transformers 4.41.0+ |
| **transformers** | 4.57.1 | <5.0 | 4.57.1 | HuggingFace models |
| **NumPy** | 1.26.0 | <3.0 | latest | numpy 2.x supported with faiss-cpu >=1.13.0 |
| **faiss-cpu** | 1.13.0 | latest | 1.13.2 | numpy 2.x support added in 1.13.0 |
| **Pydantic** | 2.10.0 | latest | 2.10.0+ | V2 required |
| **google-cloud-bigquery** | 3.38.0 | latest | 3.38.0+ | Patent search (76M+) |
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
results = index.search("claim definiteness", top_k=5)
```

**Search BigQuery Patents:**
```python
from mcp_server.bigquery_search import BigQueryPatentSearch
search = BigQueryPatentSearch()
results = search.search_patents("neural networks", limit=10)
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
