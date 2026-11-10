---
description: One-time setup for the patent creator system - downloads MPEP, builds search index, configures BigQuery
allowed-tools: Bash, Read, Write
---

# Setup Patent Creator System

Complete one-time setup for all patent creator capabilities.

## What This Does

The `patent-creator setup` CLI handles everything automatically:

1. **Detect GPU** and install PyTorch with correct CUDA version
2. **Download MPEP PDFs** (500MB) - USPTO examination manual
3. **Download Legal Sources** - 35 USC, 37 CFR, Federal Register updates
4. **Build Search Index** - FAISS + BM25 hybrid search (5-65 min depending on GPU)
5. **Configure MCP server** registration with Claude Code

**Total Time**: 30-90 minutes (most time is MPEP download and index building)

## Requirements

- **Python 3.10-3.13.** CI tests 3.11 and the full install has been walked end to end on 3.13. 3.14 is untested. Python 3.9 is too old (`pyproject.toml` requires 3.10+).
- **8GB+ RAM** (16GB is more comfortable for index building)
- **About 4GB free disk space**
- **Internet connection** (for downloads)
- **Optional**: NVIDIA GPU (several times faster index building). Apple Silicon builds on the CPU.

## Process

### Step 1: Find Compatible Python

```bash
# Check default
python3 --version 2>&1 || python --version 2>&1

# Windows (py launcher):
py -3.13 --version 2>&1
py -3.12 --version 2>&1
py -3.11 --version 2>&1

# Linux/macOS:
python3.13 --version 2>&1
python3.12 --version 2>&1
python3.11 --version 2>&1
```

Use the first version found in 3.10-3.13. Remember this as `PYTHON_CMD` for all remaining steps. On a Mac, `/usr/bin/python3` is often Apple's 3.9, which is too old.

If no compatible Python is found, tell the user to install Python 3.13 from python.org and open a new terminal.

### Step 2: Create venv and Install Package

```bash
cd ${CLAUDE_PLUGIN_ROOT}
${PYTHON_CMD} -m venv venv
```

Use the venv Python for all remaining commands:
- **Windows**: `${CLAUDE_PLUGIN_ROOT}/venv/Scripts/python`
- **Linux/macOS**: `${CLAUDE_PLUGIN_ROOT}/venv/bin/python`

Install the package:
```bash
${VENV_PYTHON} -m pip install --upgrade pip
${VENV_PYTHON} -m pip install -e .
```

### Step 3: Run Automated Setup

The `patent-creator setup` CLI handles GPU detection, PyTorch installation, MPEP downloads, and index building automatically:

```bash
cd ${CLAUDE_PLUGIN_ROOT}
${VENV_PYTHON} -m mcp_server.cli setup --non-interactive
```

**What this does automatically:**
1. Detects GPU hardware (NVIDIA CUDA, Apple MPS, or CPU)
2. Installs correct PyTorch version (uninstalls CPU version if GPU detected, restarts itself)
3. Downloads MPEP PDFs if missing (~500MB)
4. Downloads 35 USC, 37 CFR, Federal Register updates
5. Builds FAISS + BM25 hybrid search index (5-65 min)
6. Verifies BigQuery configuration (reports if project ID is missing)
7. Registers MCP server with Claude Code, then starts it the way Claude Code will and checks it answers. If that check fails, setup exits non-zero and prints why: read it, fix it, and rerun setup (downloads and index are kept).

Non-interactive setup never installs Graphviz (it changes the computer outside this tool). If the output says Graphviz is missing, ask the user whether to install it and, on a yes, run the printed command (`brew install graphviz`, `winget install graphviz`, or `sudo apt-get install graphviz`).

**This command is long-running** (30-90 minutes). Use a timeout of at least 600000ms (10 minutes) for the Bash call and check output periodically.

### Step 4: Verify Installation

After setup completes, verify:

```bash
${VENV_PYTHON} -c "import torch; print(f'PyTorch {torch.__version__}'); print(f'CUDA available: {torch.cuda.is_available()}')"
```

```bash
cd ${CLAUDE_PLUGIN_ROOT}
${VENV_PYTHON} -m mcp_server.cli health
```

### Step 5: Check BigQuery Status (Optional — enhances patent search)

BigQuery adds 100M+ worldwide patent search. The setup auto-detects existing gcloud credentials.

**If setup output showed `BigQuery: [OK]`** — nothing to do, it works.

**If BigQuery is not configured** — this is fine. MPEP search, claims review, EPO analysis, and all other features work without it. BigQuery just adds prior art search across 100M+ patents.

If the user wants to enable it later, they can run:
```
! gcloud auth application-default login
```
This opens a browser for Google sign-in. No credit card needed (free tier: 1TB/month).

**Do NOT present BigQuery setup as a required step or a failure.** The system is fully functional without it.

## Troubleshooting

### PyTorch CPU-Only Despite GPU

The most common issue. `patent-creator setup` handles this automatically by detecting GPU and reinstalling PyTorch. If it still fails:

```bash
${VENV_PYTHON} -m pip uninstall -y torch torchvision torchaudio
# For RTX 5090/5080 (compute capability >= 10.0):
${VENV_PYTHON} -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
# For older NVIDIA GPUs:
${VENV_PYTHON} -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

### MPEP Download Fails

Retry:
```bash
${VENV_PYTHON} -m mcp_server.cli setup --non-interactive
```
Won't re-download files that already exist. Only downloads missing sources.

### Index Building Out of Memory

Use CPU mode (slower but less memory):
```bash
PATENT_MPEP_DEVICE=cpu ${VENV_PYTHON} -m mcp_server.cli setup --rebuild --non-interactive
```

### BigQuery Not Working

```bash
gcloud auth application-default login
```

## After Setup

The system is ready. Available capabilities:

- `/create-patent` - Create complete patent application
- `/search-prior-art` - Search 100M+ patents
- `/review-claims` - Analyze claims for 112(b) compliance
- `/review-specification` - Check specification for 112(a) support
- `/review-formalities` - Verify MPEP 608 formalities

Tell the user to try: "Search MPEP for claim definiteness requirements"
