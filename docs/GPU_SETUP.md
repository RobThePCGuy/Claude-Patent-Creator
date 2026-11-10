# GPU Setup Guide

GPU acceleration is optional. Check the reader's actual hardware and installed packages before reporting it as enabled. The supported install is the README's home-folder venv, installed with pip from GitHub, followed by setup. No activation is needed.

## Automatic setup

macOS/Linux:
```bash
"$HOME/patent-creator-venv/bin/patent-creator" setup
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\patent-creator.exe" setup
```

Setup uses `mcp_server/hardware_detect.py` to select PyTorch for detected hardware. It uses the interpreter in this venv. The former standalone installers have been retired; use this route for installation and repairs.

The current selector uses CUDA 12.8 for detected NVIDIA compute capability 7.5 and newer. For older detected NVIDIA GPUs, including a GTX 1080, it selects `torch==2.7.1` and `torchvision==0.22.1` from CUDA 12.6 wheels. Do not replace that selection with an unpinned CUDA 12.8 install: newer CUDA 12.8 PyTorch builds dropped Maxwell and Pascal support. See the [PyTorch architecture-support announcement](https://dev-discuss.pytorch.org/t/cuda-toolkit-version-and-architecture-support-update-maxwell-and-pascal-architecture-support-removed-in-cuda-12-8-and-12-9-builds/3128).

Wheel coverage also depends on the operating system. In particular, old Maxwell cards on Windows may need CPU mode even with the legacy wheel. A detected device is not proof that the installed wheel can execute on it.

If detection chooses incorrectly, `PATENT_TORCH_CUDA` accepts `cu126` or `cu128` through `config set`. Use an override only after identifying the card; remove it with `config unset PATENT_TORCH_CUDA` to restore detection. Then rerun setup.

## Driver requirements

Check the installed NVIDIA driver with `nvidia-smi`. The CUDA version shown there is the driver's supported version, not proof of the PyTorch wheel version. CUDA 13.x requires driver family R580 or newer, not R560. Setup currently selects CUDA 12.x wheels; this guide does not direct users to install CUDA 13. See [NVIDIA's compatibility table and caveats](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html) for driver requirements, including cases that need a newer driver.

## Verify the actual installation

macOS/Linux:
```bash
"$HOME/patent-creator-venv/bin/patent-creator" status
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\patent-creator.exe" status
```

`status` reports CUDA availability, device name and memory. It does not validate kernel compatibility. Run a small operation with the same venv interpreter to test CUDA execution:

macOS/Linux:
```bash
"$HOME/patent-creator-venv/bin/python" -c "import torch; print('PyTorch:', torch.__version__); print('Wheel CUDA:', torch.version.cuda); assert torch.cuda.is_available(), 'CUDA is unavailable'; print('GPU:', torch.cuda.get_device_name(0)); x=torch.ones((32, 32), device='cuda'); y=x @ x; torch.cuda.synchronize(); assert y[0, 0].item() == 32; print('CUDA matrix operation passed')"
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\python.exe" -c "import torch; print('PyTorch:', torch.__version__); print('Wheel CUDA:', torch.version.cuda); assert torch.cuda.is_available(), 'CUDA is unavailable'; print('GPU:', torch.cuda.get_device_name(0)); x=torch.ones((32, 32), device='cuda'); y=x @ x; torch.cuda.synchronize(); assert y[0, 0].item() == 32; print('CUDA matrix operation passed')"
```

A failure means this CUDA operation did not pass. Record its error and resolve the driver/wheel issue or use CPU mode. A pass checks this small operation, not every embedding workload. Afterward, try the actual index build and search. CPU-only systems can skip this CUDA test.

FAISS uses the package's CPU dependency. GPU acceleration here applies to PyTorch embedding work; build time depends on the corpus, model, hardware and batch size. Apple Silicon defaults to CPU embeddings; `mps` is an explicit device option.

## Out of memory

Lower the embedding batch size and retry:

macOS/Linux:
```bash
"$HOME/patent-creator-venv/bin/patent-creator" config set PATENT_EMBED_BATCH_SIZE 16
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\patent-creator.exe" config set PATENT_EMBED_BATCH_SIZE 16
```

Try 8 if needed. Restore the automatic default with `config unset PATENT_EMBED_BATCH_SIZE`. For CPU mode:

macOS/Linux:
```bash
"$HOME/patent-creator-venv/bin/patent-creator" config set PATENT_MPEP_DEVICE cpu
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\patent-creator.exe" config set PATENT_MPEP_DEVICE cpu
```

Rerun setup or the failed rebuild after changing settings. Restart Claude Code to apply saved settings to its server. Remove the device override with `config unset PATENT_MPEP_DEVICE` when it is no longer needed.

## Repairs

If an upgrade changes PyTorch, rerun setup and repeat the CUDA operation test. Read actual failures instead of assuming GPU support was installed. Use the venv interpreter for any package commands; a system `pip` modifies a different environment.

For an installation that is not yet present, follow [README Quick Start](../README.md). For source-checkout diagnostics, see the [Testing Assistant skill](../skills/testing-assistant/SKILL.md).
