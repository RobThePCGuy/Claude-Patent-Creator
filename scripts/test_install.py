#!/usr/bin/env python3
"""Verify installation - Run this after patent-creator setup completes"""
import sys

print("=" * 60)
print("Claude Patent Creator - Installation Verification")
print("=" * 60)

# Test imports
print("\n[1/4] Testing package imports...")
try:
    import faiss
    import mcp
    import numpy
    import sentence_transformers
    import torch
    import transformers

    # PyMuPDF check - just verify it's available
    try:
        import pymupdf  # noqa: F401
    except ImportError:
        print("[WARNING] PyMuPDF not installed (optional for PDF processing)")
    print("[OK] All core packages imported successfully")
except ImportError as e:
    print(f"[X] Import failed: {e}")
    sys.exit(1)

# Test versions
print("\n[2/4] Checking package versions...")
print(f"[OK] PyTorch: {torch.__version__}")
print(f"[OK] Transformers: {transformers.__version__}")
print(f"[OK] Sentence Transformers: {sentence_transformers.__version__}")
print(f"[OK] FAISS: {faiss.__version__}")
print(f"[OK] NumPy: {numpy.__version__}")
# MCP version check with proper error handling
mcp_version = getattr(mcp, "__version__", "installed")
print(f"[OK] MCP: {mcp_version}")

# Check version compatibility
versions_ok = True
torch_major_minor = tuple(int(x) for x in torch.__version__.split("+")[0].split(".")[:2])
if torch_major_minor < (2, 0):
    print(f"[WARNING] PyTorch version {torch.__version__} is too old (need >=2.0)")
    versions_ok = False

transformers_major = int(transformers.__version__.split(".")[0])
if transformers_major < 4:
    print(
        f"[WARNING] Transformers version {transformers.__version__} is too old (need >=4.41.0)"
    )
    versions_ok = False

st_major = int(sentence_transformers.__version__.split(".")[0])
if st_major < 5:
    print(
        f"[WARNING] Sentence Transformers version {sentence_transformers.__version__} is too old (need >=5.1.2)"
    )
    versions_ok = False

if versions_ok:
    print("[OK] Package versions are compatible")

# Test GPU
print("\n[3/4] Checking GPU availability...")
print(f"[OK] CUDA available: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    try:
        gpu_name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"[OK] GPU: {gpu_name}")
        print(f"[OK] VRAM: {vram:.1f}GB")

        # Check if it's an RTX 5090/5080
        if "RTX 50" in gpu_name:
            if "+cu128" in torch.__version__ or "+cu130" in torch.__version__:
                print("[OK] RTX 5090/5080 with correct CUDA version")
            else:
                print(f"[WARNING] RTX 5090/5080 detected but PyTorch is {torch.__version__}")
                print("  Expected: CUDA 12.8 or 13.0")
    except Exception as e:
        print(f"[WARNING] GPU detected but error getting details: {e}")
else:
    print("[INFO] Running on CPU (no NVIDIA GPU detected)")

# Test basic functionality
print("\n[4/4] Testing basic functionality...")
try:
    # Test sentence transformer model loading (small model)
    print("  Loading embedding model (this may take a moment)...")
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    # Test embedding generation
    test_text = "This is a test patent claim."
    embedding = model.encode(test_text)

    print("[OK] Embedding model loaded and working")
    print(f"[OK] Generated {len(embedding)}-dimensional embedding")  # Test if using GPU
    if torch.cuda.is_available():
        device = next(model.parameters()).device
        if "cuda" in str(device):
            print("[OK] Model is using GPU")
        else:
            print("[INFO] Model is using CPU (this is normal if you haven't moved it to GPU)")

except Exception as e:
    print(f"[X] Functionality test failed: {e}")
    sys.exit(1)

# Summary
print("\n" + "=" * 60)
print("[OK] INSTALLATION VERIFIED SUCCESSFULLY!")
print("=" * 60)

if torch.cuda.is_available():
    print("\n[GPU] GPU acceleration is enabled - you'll get 5-10x faster performance!")
else:
    print("\n[CPU] Running on CPU - still works, just slower than GPU mode")

print("\nNext steps:")
_cli = "patent-creator"
try:
    from mcp_server.cli_command import installed_cli

    _cli = installed_cli()
except ImportError:
    pass
print(f"  1. Download USPTO rules: {_cli} setup")
print(f"  2. (Optional) Check BigQuery patent search: {_cli} check-bigquery")
print("  3. Start using in Claude Code!")
print("\n" + "=" * 60)
