#!/usr/bin/env python3
"""Test GPU detection and module loading"""

import os

# CRITICAL: Disable user site-packages BEFORE importing anything else
import site
import sys

site.ENABLE_USER_SITE = False
user_site = site.getusersitepackages()
if user_site in sys.path:
    sys.path.remove(user_site)

print("=== Testing GPU Detection ===\n")

# Test 1: Check if torch is available and CUDA works
try:
    import torch

    print("[OK] PyTorch imported successfully")
    print(f"  Version: {torch.__version__}")
    print(f"  CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"  GPU: {torch.cuda.get_device_name(0)}")
        print(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f}GB")
        print(f"  CUDA version: {torch.version.cuda}")
except Exception as e:
    print(f"[FAIL] PyTorch error: {e}")
    sys.exit(1)

# Test 2: Check if sentence-transformers works
try:
    import sentence_transformers  # noqa: F401

    print("\n[OK] sentence-transformers imported successfully")
except Exception as e:
    print(f"\n[FAIL] sentence-transformers error: {e}")
    sys.exit(1)

# Test 3: Check FAISS
try:
    import faiss

    print("[OK] FAISS imported successfully")
    print(f"  Version: {faiss.__version__ if hasattr(faiss, '__version__') else 'unknown'}")

    # Check if FAISS-GPU is available
    try:
        res = faiss.StandardGpuResources()
        print("  FAISS-GPU: Available")
    except Exception:
        print("  FAISS-GPU: Not available (using CPU version)")
except Exception as e:
    print(f"[FAIL] FAISS error: {e}")
    sys.exit(1)

# Test 4: Test the get_device() function
print("\n=== Testing get_device() function ===\n")


def get_device():
    """Test version of get_device()"""
    force_cpu = os.environ.get("FORCE_CPU", "0").lower() in ("1", "true", "yes")

    if force_cpu:
        print("CPU forced via FORCE_CPU environment variable")
        return "cpu"

    if torch.cuda.is_available():
        device = "cuda"
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"GPU detected: {gpu_name} ({gpu_memory:.1f}GB VRAM)")
        return device
    else:
        print("GPU not available, using CPU")
        return "cpu"


device = get_device()
print(f"\nDevice selected: {device}")

# Test 5: Test with FORCE_CPU=1
print("\n=== Testing FORCE_CPU=1 ===\n")
os.environ["FORCE_CPU"] = "1"
device_forced = get_device()
print(f"Device with FORCE_CPU=1: {device_forced}")

print("\n=== All tests passed! ===")
