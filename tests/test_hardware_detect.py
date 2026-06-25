"""Tests for GPU wheel selection (mcp_server.hardware_detect)."""

import pytest

import mcp_server.hardware_detect as hw
from mcp_server.hardware_detect import get_pytorch_install_command, is_legacy_nvidia_name

LEGACY_NAMES = [
    "NVIDIA GeForce GTX 1080 Ti",
    "NVIDIA GeForce GTX 1060 6GB",
    "NVIDIA GeForce GTX 970",
    "NVIDIA GeForce GTX 750 Ti",
    "NVIDIA TITAN Xp",
    "NVIDIA TITAN X (Pascal)",
    "NVIDIA TITAN V",
    "Tesla V100-SXM2-16GB",
    "Quadro P2000",
    "Tesla P100-PCIE-16GB",
    "NVIDIA GeForce MX150",
    # Maxwell mobile parts (common in laptops, frequently paired with old
    # drivers that can't report compute_cap — exactly the fallback path).
    "NVIDIA GeForce GTX 965M",
    "NVIDIA GeForce GTX 960M",
    "NVIDIA GeForce GTX 860M",
    "NVIDIA GeForce GTX 850M",
    "NVIDIA GeForce 940MX",
    "NVIDIA GeForce 940M",
]

MODERN_NAMES = [
    "NVIDIA GeForce RTX 5090",
    "NVIDIA GeForce RTX 4090",
    "NVIDIA GeForce RTX 4060 Laptop GPU",  # 'x060' must not trip the 9x0M pattern
    "NVIDIA GeForce RTX 3090",
    "NVIDIA GeForce RTX 3090 Ti",
    "NVIDIA GeForce RTX 2080 Ti",
    "NVIDIA GeForce GTX 1660 Ti",  # Turing sm_75 — must NOT be treated as legacy
    "NVIDIA GeForce GTX 1650",  # Turing sm_75
    "NVIDIA GeForce MX450",  # Turing — newer than the Pascal MX1/2/3xx
    "Tesla T4",
    "NVIDIA A100-SXM4-40GB",
    "NVIDIA H100 PCIe",
    "NVIDIA L4",
    "Quadro RTX 4000",
    "NVIDIA RTX A6000",
]


@pytest.mark.parametrize("name", LEGACY_NAMES)
def test_legacy_names_detected(name):
    assert is_legacy_nvidia_name(name) is True


@pytest.mark.parametrize("name", MODERN_NAMES)
def test_modern_names_not_legacy(name):
    assert is_legacy_nvidia_name(name) is False


@pytest.fixture(autouse=True)
def _force_nvidia(monkeypatch):
    """Pretend an NVIDIA GPU is present and clear the override env var."""
    monkeypatch.setattr(hw, "detect_nvidia_gpu", lambda: True)
    monkeypatch.setattr(hw, "detect_apple_silicon", lambda: False)
    monkeypatch.delenv("PATENT_TORCH_CUDA", raising=False)


def _set(monkeypatch, *, cap=None, names=()):
    monkeypatch.setattr(hw, "get_nvidia_compute_capability", lambda: cap)
    monkeypatch.setattr(hw, "get_nvidia_gpu_names", lambda: list(names))


def test_modern_capability_routes_cu128(monkeypatch):
    _set(monkeypatch, cap=12.0)
    _, url, _ = get_pytorch_install_command()
    assert "cu128" in url


def test_pre_turing_capability_routes_cu126(monkeypatch):
    _set(monkeypatch, cap=6.1)
    spec, url, _ = get_pytorch_install_command()
    assert "cu126" in url
    assert "2.7.1" in spec


def test_volta_capability_routes_cu126(monkeypatch):
    """Volta (7.0) is < 7.5 and absent from cu128 — it must go to cu126."""
    _set(monkeypatch, cap=7.0)
    _, url, _ = get_pytorch_install_command()
    assert "cu126" in url


def test_unknown_capability_legacy_name_routes_cu126(monkeypatch):
    _set(monkeypatch, cap=None, names=["NVIDIA GeForce GTX 1080"])
    _, url, desc = get_pytorch_install_command()
    assert "cu126" in url
    assert "GTX 1080" in desc


def test_unknown_capability_modern_name_routes_cu128(monkeypatch):
    """Unknown capability + a Blackwell name must NOT be forced onto cu126."""
    _set(monkeypatch, cap=None, names=["NVIDIA GeForce RTX 5090"])
    _, url, desc = get_pytorch_install_command()
    assert "cu128" in url
    assert "could not be determined" in desc


def test_unknown_capability_no_names_routes_cu128(monkeypatch):
    _set(monkeypatch, cap=None, names=[])
    _, url, _ = get_pytorch_install_command()
    assert "cu128" in url


def test_env_override_cu126_beats_modern_card(monkeypatch):
    monkeypatch.setenv("PATENT_TORCH_CUDA", "cu126")
    _set(monkeypatch, cap=12.0)
    _, url, _ = get_pytorch_install_command()
    assert "cu126" in url


def test_env_override_cu128_beats_legacy_card(monkeypatch):
    monkeypatch.setenv("PATENT_TORCH_CUDA", "cu128")
    _set(monkeypatch, cap=6.1)
    _, url, _ = get_pytorch_install_command()
    assert "cu128" in url
