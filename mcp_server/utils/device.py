"""GPU/CPU device detection utility"""

import os
import sys


def get_device() -> str:
    """Detect and return the best available device for computation.

    Environment variables:
        FORCE_CPU=1          - Force CPU usage even if a GPU/accelerator is available
        PATENT_MPEP_DEVICE   - Explicit device override. Accepts:
                                 cpu        -> force CPU (alias for FORCE_CPU)
                                 gpu / cuda -> prefer CUDA when available
                                 mps        -> opt in to Apple Silicon MPS
                                               (NOT recommended; see below)
                                 auto / ""  -> auto-detect (default)
        CUDA_VISIBLE_DEVICES - Control which GPUs are visible (PyTorch standard)

    Apple Silicon note:
        MPS (Apple's Metal backend) is detected but deliberately NOT used by
        default. The BGE embedding workload runs roughly 50x slower on MPS than
        on CPU, so CPU is the better default. Set PATENT_MPEP_DEVICE=mps to
        override if you have a specific reason.

    Returns:
        'cuda', 'mps', or 'cpu'.
    """
    device_override = os.environ.get("PATENT_MPEP_DEVICE", "").strip().lower()
    force_cpu = os.environ.get("FORCE_CPU", "0").lower() in ("1", "true", "yes")

    # Explicit CPU request wins over everything.
    if force_cpu or device_override == "cpu":
        reason = "FORCE_CPU" if force_cpu else "PATENT_MPEP_DEVICE=cpu"
        print(f"CPU forced via {reason} environment variable", file=sys.stderr)
        return "cpu"

    try:
        import torch
    except ImportError:
        print("PyTorch not available, using CPU...", file=sys.stderr)
        return "cpu"

    # CUDA (NVIDIA) — the best accelerator when present.
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"GPU detected: {gpu_name} ({gpu_memory:.1f}GB VRAM)", file=sys.stderr)
        return "cuda"

    if device_override in ("gpu", "cuda"):
        print(
            "PATENT_MPEP_DEVICE requested CUDA but no CUDA device is available; "
            "falling back to CPU.",
            file=sys.stderr,
        )

    # Apple Silicon (MPS) — available but deliberately gated. MPS runs the BGE
    # embedding workload dramatically slower than CPU, so CPU is the default
    # unless the user explicitly opts in with PATENT_MPEP_DEVICE=mps.
    mps_backend = getattr(torch.backends, "mps", None)
    mps_available = bool(mps_backend is not None and mps_backend.is_available())
    if mps_available:
        if device_override == "mps":
            print(
                "Apple Silicon MPS selected via PATENT_MPEP_DEVICE=mps "
                "(note: typically much slower than CPU for embeddings).",
                file=sys.stderr,
            )
            return "mps"
        print(
            "Apple Silicon GPU (MPS) detected but using CPU: MPS is dramatically "
            "slower than CPU for this embedding workload. Set PATENT_MPEP_DEVICE=mps "
            "to override.",
            file=sys.stderr,
        )
        return "cpu"

    print("GPU not available, using CPU...", file=sys.stderr)
    return "cpu"
