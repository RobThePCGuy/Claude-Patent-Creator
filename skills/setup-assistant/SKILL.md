---
name: setup-assistant
description: Guides through installation, configuration, and first-time setup of the Claude Patent Creator system.
---

# Setup Assistant Skill

Expert system for installing, configuring, and setting up the Claude Patent Creator MCP server.

## When to Use

Installing first time, setting up new environment, configuring authentication, troubleshooting installation, migrating to new machine, updating dependencies, verifying health.

## Quick Setup (5 Minutes)

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/macOS

# 2. Run installer
python install.py

# 3. Restart Claude Code

# 4. Test
# Ask Claude: "Search MPEP for claim definiteness"
```

## Complete Setup Lifecycle

### Phase 1: Pre-Installation Checks

**Requirements:**
- Python 3.10-3.13 (CI tests 3.11; 3.13 walked end to end)
- 8GB+ RAM (16GB recommended)
- 5GB free disk
- Optional: NVIDIA GPU with CUDA 12.x

**Verify:**
```bash
python3 --version  # Should show 3.10-3.13
nvidia-smi        # Optional: Check GPU
```

### Phase 2: Virtual Environment

```bash
# Create venv
python -m venv venv

# Activate
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/macOS

# Verify
which python  # Should show venv path
```

**Important:** Always activate venv before running scripts!

### Phase 3: Dependency Installation

**Automated (Recommended):**
```bash
python install.py
# Handles: PyTorch order, GPU detection, MCP registration
```

**Manual (Advanced):**
```bash
# Install PyTorch FIRST (critical!)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

# Then install package (includes all dependencies)
pip install -e .
```

**Why PyTorch order matters:** If installed after sentence-transformers, you get CPU-only version.

### Phase 4: BigQuery Authentication (Optional)

BigQuery adds 100M+ patent search but is NOT required. MPEP search, claims review, EPO analysis, and all other features work without it.

The setup auto-detects existing gcloud credentials. If already authenticated, BigQuery works automatically.

**If the user wants to enable BigQuery later:**
```bash
# One command — opens browser for Google sign-in (free, no credit card)
! gcloud auth application-default login
```

**Do NOT present BigQuery as a failure or required step.** It is a bonus feature.

### Phase 5: MCP Server Registration

**Automated:**
```bash
python install.py  # Handles registration automatically
```

**Manual:**
```bash
# Get paths
patent-creator verify-config

# Register (use forward slashes!)
claude mcp add --transport stdio claude-patent-creator --scope user -- \
  "C:/path/to/venv/Scripts/python.exe" \
  "C:/path/to/mcp_server/server.py"

# Verify
claude mcp list
```

**Critical:** Restart Claude Code after registration!

### Phase 6: Configuration Files

Create `.env`:

```bash
# Required
GOOGLE_CLOUD_PROJECT=your_project_id
ANTHROPIC_API_KEY=<YOUR_ANTHROPIC_API_KEY>

# Optional
PATENT_LOG_LEVEL=INFO
PATENT_LOG_FORMAT=human

# Windows only
CLAUDE_CODE_GIT_BASH_PATH=C:\dev\Git\bin\bash.exe
```

### Phase 7: Health Check

```bash
patent-creator health
```

### Phase 8: Present Results

**Setup is complete when MPEP index is built and MCP server is registered.** BigQuery and EPO OPS are optional enhancements.

Present a clean summary table showing what's ready. Do NOT dump manual setup instructions for optional features. The system is fully functional for:
- MPEP/USC/CFR/EPC/PCT legal search
- Claims analysis (US + EPO)
- Specification analysis (US + EPO)
- Formalities checking (US + EPO + PCT)
- Patent diagram generation
- Patent application drafting

If BigQuery is also configured, mention patent search as available. If not, do NOT present it as a failure — just omit it from the "ready" list.

**Test with:**
```
"Search MPEP for claim definiteness requirements"
```

**If this works -> Setup complete. Tell the user they're ready.**

## Common Setup Issues

| Issue | Solution |
|-------|----------|
| PyTorch CPU-only | Reinstall PyTorch FIRST |
| MCP not loading | Restart Claude Code, verify with `claude mcp list` |
| Path errors | Use forward slashes (/) not backslashes (\\) |
| BigQuery fails | Re-auth: `gcloud auth application-default login` |
| Index not found | Build: `patent-creator rebuild-index` |
| Import errors | Activate venv |

## Platform-Specific Notes

### Windows
- PowerShell: Use `venv\Scripts\activate`
- Git Bash required for MCP commands
- Paths: Always forward slashes in MCP config
- CUDA: Install NVIDIA drivers + toolkit

### Linux
- venv: `source venv/bin/activate`
- FAISS-GPU: Available on Linux only
- Permissions: May need sudo

### macOS
- Apple Silicon: Use MPS (auto-detected)
- Intel: Use CPU or external GPU
- Homebrew: May need for dependencies

## Update & Maintenance

### Updating Dependencies
```bash
venv\Scripts\activate
pip install -e . --upgrade
python scripts/test_install.py
```

### Rebuilding Index
```bash
patent-creator rebuild-index
# Wait 5-15 minutes
```

### Re-registering MCP
```bash
claude mcp remove claude-patent-creator
python install.py
# Restart Claude Code
```

## Quick Reference

### Essential Commands
```bash
# Setup
python install.py
patent-creator health
claude mcp list

# Testing
python scripts/test_install.py
python scripts/test_gpu.py
python scripts/test_bigquery.py

# Maintenance
patent-creator rebuild-index
patent-creator verify-config
```

### Critical Files
- `.env` - Environment variables
- `requirements.txt` - Dependencies
- `mcp_server/index/` - MPEP search index
- `pdfs/` - MPEP PDF files
