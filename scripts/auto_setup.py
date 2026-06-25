#!/usr/bin/env python3
"""
Automatic GPU/CPU Detection and PyTorch Installation
Detects hardware and installs the correct PyTorch version automatically
"""

import contextlib
import os
import platform
import subprocess
import sys


def run_command(cmd, description="Running command"):
    """Run a command and return success status"""
    print(f"\n{description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr


def check_nvidia_gpu():
    """Check if NVIDIA GPU is available"""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                "nvidia-smi", shell=True, capture_output=True, text=True, timeout=5
            )
        else:
            result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False


def get_compute_capability():
    """Detect GPU compute capability from nvidia-smi"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # nvidia-smi emits one compute_cap per GPU; parse each line and
            # return the MINIMUM so the oldest GPU in the system drives wheel
            # selection (any pre-Turing card forces cu126). Non-numeric lines
            # (warnings, headers) are skipped rather than failing detection.
            caps = []
            for line in result.stdout.splitlines():
                cleaned = line.strip()
                if cleaned:
                    with contextlib.suppress(ValueError):
                        caps.append(float(cleaned))
            if caps:
                return min(caps)
    except Exception:
        pass
    return None


def install_pytorch(gpu_available=False, compute_cap=None):
    """Install appropriate PyTorch version"""

    if not gpu_available:
        print("\n" + "=" * 60)
        print("No NVIDIA GPU detected - Installing CPU version")
        print("=" * 60)
        cmd = f"{sys.executable} -m pip install torch torchvision"
        return run_command(cmd, "Installing PyTorch (CPU)")

    # cu128 wheels only ship kernels for sm_75+ (Turing and newer). Pre-Turing
    # GPUs (Pascal sm_61, Volta sm_70, Maxwell sm_5x) crash at kernel launch with
    # "no kernel image is available for execution on the device", so they need
    # the cu126 build of torch 2.7.1 (kernels down to sm_61 on Windows / sm_50 on
    # Linux, through sm_90).
    override = os.environ.get("PATENT_TORCH_CUDA", "").strip().lower()
    if override == "cu126":
        route_cu126, reason = True, "forced via PATENT_TORCH_CUDA=cu126"
    elif override == "cu128":
        route_cu126, reason = False, "forced via PATENT_TORCH_CUDA=cu128"
    elif compute_cap is not None:
        route_cu126 = compute_cap < 7.5
        reason = f"Compute {compute_cap}"
    else:
        # Unknown capability (older driver without the compute_cap field): route
        # known pre-Turing cards by product name via the shared detector, so a
        # legacy GPU isn't sent to cu128 while Blackwell isn't sent to cu126.
        reason = "compute capability unavailable"
        try:
            from mcp_server.hardware_detect import (
                get_nvidia_gpu_names,
                is_legacy_nvidia_name,
            )

            route_cu126 = any(is_legacy_nvidia_name(n) for n in get_nvidia_gpu_names())
        except Exception:
            route_cu126 = False

    if route_cu126:
        torch_spec = "torch==2.7.1 torchvision==0.22.1"
        cuda_pkg = "cu126"
        cuda_name = "12.6"
        print("\n" + "=" * 60)
        print(f"Legacy NVIDIA GPU detected ({reason}) - Installing CUDA {cuda_name}")
        print("=" * 60)
    else:
        torch_spec = "torch torchvision"
        cuda_pkg = "cu128"  # Turing and newer
        cuda_name = "12.8"
        print("\n" + "=" * 60)
        print(f"NVIDIA GPU detected ({reason}) - Installing CUDA {cuda_name} version")
        print("=" * 60)

    # Uninstall any existing PyTorch first. Quote sys.executable so a venv path
    # containing spaces (e.g. C:\Users\John Doe\venv) survives shell=True.
    subprocess.run(
        f'"{sys.executable}" -m pip uninstall -y torch torchvision torchaudio',
        shell=True,
        capture_output=True,
    )

    cmd = f'"{sys.executable}" -m pip install {torch_spec} --index-url https://download.pytorch.org/whl/{cuda_pkg}'
    return run_command(cmd, f"Installing PyTorch (CUDA {cuda_name})")


def verify_installation():
    """Verify PyTorch installation and GPU detection"""
    print("\n" + "=" * 60)
    print("Verifying installation...")
    print("=" * 60)

    try:
        import torch

        print(f"\n[OK] PyTorch version: {torch.__version__}")

        if torch.cuda.is_available():
            print("[OK] CUDA available: Yes")
            print(f"[OK] GPU: {torch.cuda.get_device_name(0)}")
            print(f"[OK] VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB")
            return True, "GPU"
        else:
            print("[OK] CUDA available: No (using CPU)")
            return True, "CPU"
    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        return False, None


def main():
    """Main auto-setup routine"""
    print("=" * 60)
    print("Claude Patent Creator - Automatic Setup")
    print("=" * 60)
    print("\nDetecting your system configuration...")

    # Detect OS
    os_name = platform.system()
    print(f"[OK] Operating System: {os_name}")

    # Detect GPU
    has_gpu = check_nvidia_gpu()
    compute_cap = None
    if has_gpu:
        compute_cap = get_compute_capability()
        if compute_cap:
            print(f"[OK] NVIDIA GPU detected (Compute Capability {compute_cap})")
        else:
            print("[OK] NVIDIA GPU detected")
    else:
        print("[OK] No NVIDIA GPU detected (will use CPU)")

    # Install PyTorch
    print("\n" + "=" * 60)
    print("Installing PyTorch with optimal settings...")
    print("=" * 60)

    success, output = install_pytorch(has_gpu, compute_cap)

    if not success:
        print("\n[X] Installation failed!")
        print(output)
        return 1

    # Verify
    success, device = verify_installation()

    if success:
        print("\n" + "=" * 60)
        print("[SUCCESS] Setup Complete!")
        print("=" * 60)
        if device == "GPU":
            print("\nYour system is configured to use GPU acceleration (5-10x faster)")
        else:
            print("\nYour system is configured to use CPU")
        print("\nNext steps:")
        print("  1. Run: patent-creator setup")
        print("  2. Optional: run patent-creator check-bigquery")
        return 0
    else:
        print("\n[FAIL] Verification failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
