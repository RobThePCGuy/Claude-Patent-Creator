#!/usr/bin/env python3
"""
Hardware detection for automatic PyTorch installation
Detects GPU type and determines correct PyTorch version
"""

import contextlib
import os
import platform
import re
import subprocess


def detect_nvidia_gpu():
    """Detect if NVIDIA GPU is available"""
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_nvidia_compute_capability():
    """Return the LOWEST NVIDIA GPU compute capability as a float, or None.

    nvidia-smi reports one compute_cap per GPU. We return the minimum so the
    oldest card in the system drives wheel selection: any pre-Turing GPU forces
    the whole system onto cu126. Non-numeric lines (warnings, headers) are
    skipped rather than failing detection.

    e.g. GTX 1080 (Pascal) -> 6.1, RTX 3090 (Ampere) -> 8.6, RTX 5090 -> 12.0;
    a mixed 6.1 + 8.6 system -> 6.1. Returns None when nvidia-smi is missing,
    fails, or predates the compute_cap query field (older drivers).
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            caps = []
            for line in result.stdout.splitlines():
                cleaned = line.strip()
                if cleaned:
                    with contextlib.suppress(ValueError):
                        caps.append(float(cleaned))
            if caps:
                return min(caps)
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def get_nvidia_gpu_names():
    """Return NVIDIA GPU product names from nvidia-smi (empty list on failure).

    Unlike compute_cap, the product name is reported even by older nvidia-smi
    builds that predate the compute_cap field, so it can drive wheel selection
    when the numeric compute capability is unavailable.
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except (subprocess.TimeoutExpired, OSError):
        pass
    return []


# Pre-Turing (compute capability < 7.5) NVIDIA product-name patterns: Maxwell,
# Pascal, and Volta. Used only as a fallback when nvidia-smi can't report the
# numeric compute capability. Turing+ names (RTX, GTX 16xx, Tesla T4) are
# intentionally NOT matched, so modern cards keep the cu128 wheel.
_LEGACY_NVIDIA_PATTERNS = (
    r"gtx\s*7(45|50)",  # Maxwell GTX 745 / 750 / 750 Ti
    r"gtx\s*8\d0",  # Maxwell GTX 8xxM mobile (840M / 850M / 860M / 870M / 880M)
    r"gtx\s*9\d{2}",  # Maxwell GTX 9-series incl. mobile (950 / 970 / 960M / 965M)
    r"gtx\s*10[1-8]0",  # Pascal GTX 1050 / 1060 / 1070 / 1080 (Ti)
    r"\bgt\s*10[0-3]0",  # Pascal GT 1010 / 1030
    r"\bmx[1-3]\d0\b",  # Pascal MX150 / MX250 / MX350 (MX450+ is Turing — excluded)
    r"\b9[0-6]0mx?\b",  # Maxwell/Pascal mobile reported without GTX (940M / 940MX)
    r"titan\s*xp\b",  # Pascal Titan Xp
    r"titan\s*x\b",  # Maxwell / Pascal Titan X
    r"titan\s*v\b",  # Volta Titan V
    r"\bv100\b",  # Volta Tesla V100
    r"\bgv100\b",  # Volta Quadro GV100
    r"tesla\s*[mp]\d",  # Tesla M-series (Maxwell) / P-series (Pascal)
    r"quadro\s*[mp]\d{3,}",  # Quadro M / P workstation cards
)


def is_legacy_nvidia_name(name):
    """True if an NVIDIA product name is a pre-Turing (compute < 7.5) card."""
    lowered = name.lower()
    return any(re.search(pattern, lowered) for pattern in _LEGACY_NVIDIA_PATTERNS)


def detect_apple_silicon():
    """Detect if running on Apple Silicon (M1/M2/M3)"""
    if platform.system() != "Darwin":
        return False
    try:
        result = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True, timeout=5
        )
        return "Apple" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_pytorch_install_command():
    """
    Determine correct PyTorch installation command based on hardware

    Returns:
        tuple: (package_spec, index_url or None, description)
    """
    has_nvidia = detect_nvidia_gpu()
    has_apple_silicon = detect_apple_silicon()

    if has_nvidia:
        cu126 = "https://download.pytorch.org/whl/cu126"
        cu128 = "https://download.pytorch.org/whl/cu128"

        # Explicit manual override, useful when auto-detection can't determine the
        # GPU architecture (see the unknown-capability path below) or a user wants
        # to pin a specific build.
        override = os.environ.get("PATENT_TORCH_CUDA", "").strip().lower()
        if override == "cu126":
            return (
                "torch==2.7.1 torchvision==0.22.1",
                cu126,
                "[GPU] NVIDIA GPU detected - installing PyTorch 2.7.1 / CUDA 12.6 "
                "(forced via PATENT_TORCH_CUDA=cu126)",
            )
        if override == "cu128":
            return (
                "torch>=2.0.0",
                cu128,
                "[GPU] NVIDIA GPU detected - installing PyTorch / CUDA 12.8 "
                "(forced via PATENT_TORCH_CUDA=cu128)",
            )

        # cu128 wheels only ship compiled kernels for sm_75+ (Turing and newer).
        # Pre-Turing cards (Pascal sm_61, Volta sm_70, Maxwell sm_5x) hit a
        # "no kernel image is available for execution on the device" error with
        # cu128, so they need the cu126 build of torch 2.7.1 (kernels down to
        # sm_61 on Windows / sm_50 on Linux, through sm_90).
        compute_cap = get_nvidia_compute_capability()
        cu126_reason = None
        if compute_cap is not None:
            if compute_cap < 7.5:
                cu126_reason = f"compute {compute_cap}"
        else:
            # nvidia-smi couldn't report compute_cap (e.g. an older driver whose
            # nvidia-smi predates the field). Defaulting blindly to cu128 would
            # re-break legacy cards, but defaulting to cu126 would break Blackwell
            # (sm_120, absent from the cu126 wheel). nvidia-smi still reports the
            # product *name* on those drivers, so route known pre-Turing cards by
            # name; everything else stays on cu128.
            legacy = [n for n in get_nvidia_gpu_names() if is_legacy_nvidia_name(n)]
            if legacy:
                cu126_reason = f"legacy GPU {legacy[0]!r}, compute capability unavailable"

        if cu126_reason is not None:
            return (
                "torch==2.7.1 torchvision==0.22.1",
                cu126,
                f"[GPU] NVIDIA GPU ({cu126_reason}) detected - installing "
                "PyTorch 2.7.1 with CUDA 12.6 (legacy GPU architecture support)",
            )
        if compute_cap is None:
            # Unknown capability and no recognized legacy name: default to cu128
            # (correct for all current/modern GPUs) but tell the user how to
            # recover if they actually have an unrecognized pre-Turing card.
            return (
                "torch>=2.0.0",
                cu128,
                "[GPU] NVIDIA GPU detected but compute capability could not be "
                "determined - installing CUDA 12.8 (cu128). If you have a "
                "pre-Turing GPU and see 'no kernel image is available', set "
                "PATENT_TORCH_CUDA=cu126.",
            )
        return (
            "torch>=2.0.0",
            cu128,
            "[GPU] NVIDIA GPU detected - installing PyTorch with CUDA 12.8 support",
        )
    elif has_apple_silicon:
        return (
            "torch>=2.0.0",
            None,  # Default PyPI has MPS support
            "[GPU] Apple Silicon detected - installing PyTorch with MPS support",
        )
    else:
        return (
            "torch>=2.0.0",
            "https://download.pytorch.org/whl/cpu",
            "[CPU] No GPU detected - installing PyTorch CPU version",
        )


def check_pytorch_installation():
    """
    Check if PyTorch is installed and if it matches hardware

    Returns:
        dict: Status information about PyTorch installation
    """
    try:
        import torch

        has_nvidia = detect_nvidia_gpu()
        cuda_available = torch.cuda.is_available()

        status = {
            "installed": True,
            "version": torch.__version__,
            "cuda_available": cuda_available,
            "hardware_match": True,
        }

        # Check if NVIDIA GPU present but CUDA not available
        if has_nvidia and not cuda_available:
            status["hardware_match"] = False
            status["warning"] = "NVIDIA GPU detected but PyTorch has no CUDA support"

        # CUDA can report "available" while still lacking compiled kernels for
        # this specific GPU architecture. That manifests at kernel-launch time
        # as "no kernel image is available for execution on the device". Detect
        # it up front by checking the device's compute capability against the
        # architectures this PyTorch build was compiled for.
        if has_nvidia and cuda_available:
            try:
                arch_list = torch.cuda.get_arch_list()
                if arch_list:
                    # Parse the build's compiled architectures into (major, minor)
                    # pairs. PyTorch wheels list baselines (e.g. sm_80, sm_86) and
                    # rely on intra-major backward compatibility, so an exact
                    # sm_XX string match would false-positive on minor versions
                    # not explicitly listed (e.g. sm_89 / RTX 40-series).
                    supported = []
                    for arch in arch_list:
                        m = re.match(r"^(?:sm|compute)_(\d+)(\d)[a-z]?$", arch)
                        if m:
                            supported.append((int(m.group(1)), int(m.group(2))))
                    # Only evaluate compatibility if at least one architecture
                    # parsed; an empty list (unexpected arch_list format) must
                    # not produce a false mismatch and trigger a reinstall loop.
                    # Check every CUDA device: device 0 may be supported while a
                    # second, older GPU in the system is not. A device is
                    # compatible when the build has a kernel with the same major
                    # version and a minor <= the device's minor (NVIDIA guarantees
                    # backward compatibility within a major architecture).
                    if supported:
                        for i in range(torch.cuda.device_count()):
                            major, minor = torch.cuda.get_device_capability(i)
                            compatible = any(
                                a_major == major and a_minor <= minor
                                for a_major, a_minor in supported
                            )
                            if not compatible:
                                status["hardware_match"] = False
                                status["warning"] = (
                                    f"PyTorch {torch.__version__} has no compiled kernels "
                                    f"for GPU {i} ({torch.cuda.get_device_name(i)}, "
                                    f"sm_{major}{minor}); build supports {arch_list}"
                                )
                                break
            except Exception:
                pass

        # Check if Apple Silicon
        if detect_apple_silicon():
            try:
                mps_available = torch.backends.mps.is_available()
                status["mps_available"] = mps_available
            except AttributeError:
                status["mps_available"] = False

        return status

    except ImportError:
        return {
            "installed": False,
            "version": None,
            "cuda_available": False,
            "hardware_match": False,
        }
