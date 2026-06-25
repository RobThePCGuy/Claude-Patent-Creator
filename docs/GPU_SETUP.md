# GPU Setup Guide

## Your Current Status

✅ **GPU is NOW ENABLED!**

```
Hardware:  NVIDIA GeForce RTX 5090 Laptop GPU (23.9GB VRAM)
Driver:    581.80 (supports CUDA 13.0)
PyTorch:   2.9.0+cu128 (CUDA 12.8) ✓
CUDA:      12.8 ✓
FAISS:     1.12.0 (CPU version - GPU version Linux-only)
Transformers: 4.44.0 ✓
Sentence Transformers: 3.1.0 ✓
NumPy:     1.26.4 ✓
```

## What Was Fixed

1. **Package Compatibility** - Updated to compatible versions (transformers 4.44.0, sentence-transformers 3.1.0, numpy 1.26.4)
2. **PyTorch CUDA** - Installed CUDA-enabled PyTorch 2.9.0+cu128 with automatic GPU detection
3. **Compute Capability Detection** - Automatically detects RTX 5090/5080 (compute 12.0) and installs correct CUDA version
4. **Simplified Installation** - Just run `python install.py` and everything is configured automatically

## Important: FAISS-GPU on Windows

**FAISS-GPU is Linux-only.** The `faiss-gpu-cu12` package only provides wheels for Linux. On Windows, you'll use `faiss-cpu` which still benefits significantly because:

1. **PyTorch GPU acceleration** - Sentence transformers use your GPU for embeddings (5-10x faster)
2. **FAISS runs on CPU** - Vector search still fast, just not GPU-accelerated
3. **You still get major speedup** - Most time is in embedding generation, not vector search

## Performance You'll See

With PyTorch on GPU (even with FAISS on CPU):

| Operation | Before (CPU) | Now (GPU) | Speedup |
|-----------|-------------|-----------|---------|
| Embedding generation | 5-10 sec | 0.5-1 sec | **10x** |
| Index building (MPEP) | 15-20 min | 3-4 min | **5x** |
| Index building (Patents, all 9.2M) | ~270 hours | ~27 hours | **10x** |

**Note:** Full patent corpus indexing (17.6M chunks) takes ~27 hours on RTX 5090 GPU at 1.4s/batch. This is a one-time operation.

## Multi-User GPU Configuration

For servers with multiple users sharing a GPU:

### Control GPU Usage per User

**PowerShell:**
```powershell
# User 1: Use GPU (default)
patent-creator serve

# User 2: Force CPU (don't compete for GPU)
$env:FORCE_CPU=1
patent-creator serve
```

**Linux/macOS:**
```bash
# User 1: Use GPU (default)
patent-creator serve

# User 2: Force CPU
FORCE_CPU=1 patent-creator serve
```

### Select Specific GPUs

**PowerShell:**
```powershell
# Use only GPU 0
$env:CUDA_VISIBLE_DEVICES="0"
patent-creator serve

# Use GPUs 0 and 1
$env:CUDA_VISIBLE_DEVICES="0,1"
patent-creator serve

# Hide all GPUs (CPU mode)
$env:CUDA_VISIBLE_DEVICES=""
patent-creator serve
```

**Linux/macOS:**
```bash
# Use only GPU 0
CUDA_VISIBLE_DEVICES=0 patent-creator serve

# Use GPUs 0 and 1
CUDA_VISIBLE_DEVICES=0,1 patent-creator serve

# Hide all GPUs
CUDA_VISIBLE_DEVICES= patent-creator serve
```

### Permanent Configuration

**Windows (PowerShell):**
```powershell
# Always use GPU (default)
[System.Environment]::SetEnvironmentVariable('FORCE_CPU', '0', 'User')

# Always use CPU
[System.Environment]::SetEnvironmentVariable('FORCE_CPU', '1', 'User')
```

**Linux/macOS:**
```bash
# Add to ~/.bashrc or ~/.zshrc
echo 'export FORCE_CPU=0' >> ~/.bashrc  # Use GPU
echo 'export FORCE_CPU=1' >> ~/.bashrc  # Use CPU
source ~/.bashrc
```

## Verify Your Setup

Run the test script:
```powershell
python scripts/test_gpu.py
```

You should see:
```
[OK] PyTorch imported successfully
  Version: 2.9.0+cu128
  CUDA available: True
  GPU: NVIDIA GeForce RTX 5090 Laptop GPU
  VRAM: 23.9GB
  CUDA version: 12.8
```

Or use the status command:
```powershell
patent-creator status
```

## If You Need to Reinstall GPU Support

> **Note:** These manual commands are for advanced users only. Claude Code automatically manages the virtual environment during normal usage. Manual venv activation is only needed when running these direct CLI commands.

**Quick Method (Windows):**
```powershell
# Activate venv first (required for manual operations)
venv\Scripts\activate

# Then run the helper script
.\install-gpu.bat
```

**Quick Method (Linux/macOS):**
```bash
# Activate venv first (required for manual operations)
source venv/bin/activate

# Then run the helper script
chmod +x install-gpu.sh
./install-gpu.sh
```

**Manual Method:**
```powershell
# Activate venv (required for manual pip commands)
venv\Scripts\activate

# Remove CPU PyTorch
pip uninstall torch torchvision torchaudio

# Install CUDA 12.8 version (recommended for your driver)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

# Verify
python scripts/test_gpu.py
```

**⚠️ Important:** Running `pip install -r requirements.txt` will replace CUDA PyTorch with CPU version!
Always run `install-gpu.bat` (or `.sh`) after any pip install commands.

## CUDA Version Selection

Your driver (581.80) supports:

| CUDA Version | PyTorch Index URL | Driver Requirement | Status |
|--------------|-------------------|-------------------|--------|
| CUDA 12.6 | `https://download.pytorch.org/whl/cu126` | ≥R535 | ✓ Supported |
| CUDA 12.8 | `https://download.pytorch.org/whl/cu128` | ≥R555 | ✓ **Installed** |
| CUDA 13.0 | `https://download.pytorch.org/whl/cu130` | ≥R560 | ✓ Supported |

### GPU architecture and wheel selection

The CUDA wheel is chosen automatically from your GPU's **compute capability**
(detected via `nvidia-smi`), because the `cu128` wheels only ship compiled
kernels for **Turing (sm_75) and newer**:

| GPU architecture | Example cards | Compute capability | PyTorch wheel |
|------------------|---------------|--------------------|---------------|
| Blackwell / Ada / Ampere / Turing | RTX 50/40/30 series, RTX 20 series | ≥ 7.5 | `cu128` |
| Pascal / Volta / Maxwell | GTX 10 series, Titan X, Tesla V100 | < 7.5 | `cu126` (torch 2.7.1) |

Pre-Turing cards routed to `cu128` crash at kernel launch with
`CUDA error: no kernel image is available for execution on the device`. The
`cu126` build of torch 2.7.1 ships kernels down to **`sm_61` (Pascal)** on
Windows — and **`sm_50` (Maxwell)** on Linux — through `sm_90`, so Pascal and
Volta cards are sent there automatically.

> **Maxwell on Windows:** the Windows `cu126` wheel omits `sm_50`/`sm_52`, so a
> Maxwell card (GTX 9xx, GTX 745/750) may still report "no kernel image" on
> Windows. `patent-creator status` will flag the mismatch rather than failing
> silently. Linux `cu126` wheels do include Maxwell.

**If `nvidia-smi` can't report compute capability** (older drivers predate the
field), the wheel is chosen from the GPU's product *name* instead: recognized
pre-Turing cards still get `cu126`, and everything else defaults to `cu128`. You
can always force the choice with `PATENT_TORCH_CUDA=cu126` or
`PATENT_TORCH_CUDA=cu128`.

## Troubleshooting

### "CUDA out of memory" errors

Your RTX 5090 has 24GB VRAM, which is plenty. If you see this error:

1. Close other GPU applications
2. Check `nvidia-smi` to see GPU memory usage
3. Reduce batch size if building very large indices

### GPU not detected after installation

```powershell
# Check if CUDA is available
python -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"

# If False, reinstall PyTorch CUDA version
pip uninstall torch torchvision
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

### "no kernel image is available for execution on the device"

Your PyTorch build has no compiled kernels for your GPU's architecture —
typically a pre-Turing card (GTX 10-series and older, compute capability < 7.5)
that received a `cu128` build. Reinstall the `cu126` build (kernels `sm_61`–`sm_90`
on Windows, `sm_50`–`sm_90` on Linux):

```powershell
pip uninstall -y torch torchvision
pip install torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu126
```

Or set `PATENT_TORCH_CUDA=cu126` before `patent-creator setup` to force the
legacy wheel — handy when auto-detection can't read your GPU's compute
capability.

Confirm your GPU's architecture is now supported:

```powershell
python -c "import torch; print(torch.cuda.get_arch_list())"
```

`patent-creator setup` selects the correct wheel automatically, so this is only
needed for manual installs.

### Multiple Python installations conflict

The fix in `server.py` disables user site-packages to prevent conflicts. If you still have issues:

```powershell
# Check Python paths
python -c "import sys; print('\n'.join(sys.path))"

# Should NOT include: ...
```

## Next Steps

Your GPU is ready! You can now:

> **Note:** When using Claude Code, you don't need to activate the virtual environment manually. These commands are for advanced direct CLI usage only.

```powershell
# For advanced users running commands directly (activate venv first):
# venv\Scripts\activate  (Windows) or source venv/bin/activate (Linux/macOS)

# Build the MPEP index with GPU acceleration
patent-creator setup

# Or rebuild if you already have one
patent-creator setup --rebuild

```

The GPU will automatically be used. You'll see:
```
GPU detected: NVIDIA GeForce RTX 5090 Laptop GPU (23.9GB VRAM)
```

## What Changed in the Code

### 1. `mcp_server/server.py`
- Added user site-packages disabling at top of file
- Enhanced `get_device()` with `FORCE_CPU` support
- Better GPU detection messages with VRAM display

### 2. `requirements.txt`
- Updated to PyTorch 2.9.0 information
- Added faiss-gpu-cu12/cu11 installation instructions (Linux)
- Noted old faiss-gpu package is archived
- Added Windows FAISS limitations
- Added RTX 5090 compatibility notes

## Troubleshooting: CUDA Out of Memory

If you hit OOM errors during index building with large MPEP datasets:

**Option 1: Force CPU for indexing**
```bash
CUDA_VISIBLE_DEVICES="" patent-creator rebuild-index
```
This runs index building on CPU (slower but no VRAM limit). GPU is still used for searches afterward.

**Option 2: Reduce batch size**
```bash
EMBED_BATCH_SIZE=16 patent-creator rebuild-index
```
Default batch size may be too large for GPUs with less VRAM. Try 16 or 8.

## macOS / Apple Silicon

On Apple Silicon (M-series) Macs, the embedding and reranker models run on **CPU
by default** — and that is intentional. Apple's Metal (MPS) backend runs the
BGE-base embedding workload roughly **50x slower** than CPU, so CPU is the
faster choice here. The setup auto-detects this and stays on CPU.

If you have a specific reason to use MPS anyway, opt in explicitly:
```bash
PATENT_MPEP_DEVICE=mps patent-creator setup --rebuild --non-interactive
```

To force CPU explicitly (either of these works):
```bash
FORCE_CPU=1 patent-creator setup --rebuild --non-interactive
# or, equivalently:
PATENT_MPEP_DEVICE=cpu patent-creator setup --rebuild --non-interactive
```

### `SSL: CERTIFICATE_VERIFY_FAILED` when downloading MPEP

If the MPEP download fails with `[SSL: CERTIFICATE_VERIFY_FAILED] ... unable to
get local issuer certificate`, you are almost certainly on the python.org macOS
build of Python, which ships OpenSSL **without** a system CA bundle. The
downloader now verifies against the bundled `certifi` CA store automatically, so
this should resolve itself. If you are on an older build, you can also run the
one-time fix that ships with the installer:
```bash
/Applications/Python\ 3.11/Install\ Certificates.command
```

## Support

If you encounter issues:
1. Run `nvidia-smi` to verify driver version
2. Run `python scripts/test_gpu.py` for detailed diagnostics
3. Check [PyTorch CUDA compatibility](https://pytorch.org/get-started/locally/)
4. Check NVIDIA driver compatibility for your CUDA version

---

**Status:** GPU Enabled ✓ | PyTorch CUDA ✓ | Ready to use!
