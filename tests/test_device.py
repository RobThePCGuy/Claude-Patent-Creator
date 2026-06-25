"""Tests for device selection (mcp_server.utils.device)."""

import sys
import types

import pytest

from mcp_server.utils.device import get_device


def _fake_torch(*, cuda=False, mps=False):
    """Build a stand-in ``torch`` module with configurable accelerators.

    ``mps=None`` simulates an older torch with no ``torch.backends.mps`` at all.
    """
    torch = types.ModuleType("torch")

    torch.cuda = types.SimpleNamespace(
        is_available=lambda: cuda,
        get_device_name=lambda idx: "Fake CUDA Device",
        get_device_properties=lambda idx: types.SimpleNamespace(total_memory=8 * 1024**3),
    )

    backends = types.ModuleType("torch.backends")
    if mps is not None:
        backends.mps = types.SimpleNamespace(is_available=lambda: mps)
    torch.backends = backends
    return torch


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("FORCE_CPU", raising=False)
    monkeypatch.delenv("PATENT_MPEP_DEVICE", raising=False)


def test_force_cpu_env_returns_cpu(monkeypatch):
    monkeypatch.setenv("FORCE_CPU", "1")
    # Even with a CUDA device present, FORCE_CPU must win.
    monkeypatch.setitem(sys.modules, "torch", _fake_torch(cuda=True))
    assert get_device() == "cpu"


def test_patent_mpep_device_cpu_returns_cpu(monkeypatch):
    """The documented PATENT_MPEP_DEVICE=cpu override is honored (issue #23)."""
    monkeypatch.setenv("PATENT_MPEP_DEVICE", "cpu")
    monkeypatch.setitem(sys.modules, "torch", _fake_torch(cuda=True))
    assert get_device() == "cpu"


def test_cuda_available_returns_cuda(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", _fake_torch(cuda=True))
    assert get_device() == "cuda"


def test_mps_available_defaults_to_cpu(monkeypatch):
    """Apple Silicon MPS is gated off by default due to the embedding perf cliff."""
    monkeypatch.setitem(sys.modules, "torch", _fake_torch(cuda=False, mps=True))
    assert get_device() == "cpu"


def test_mps_opt_in_returns_mps(monkeypatch):
    monkeypatch.setenv("PATENT_MPEP_DEVICE", "mps")
    monkeypatch.setitem(sys.modules, "torch", _fake_torch(cuda=False, mps=True))
    assert get_device() == "mps"


def test_no_accelerator_returns_cpu(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", _fake_torch(cuda=False, mps=False))
    assert get_device() == "cpu"


def test_old_torch_without_mps_backend_returns_cpu(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", _fake_torch(cuda=False, mps=None))
    assert get_device() == "cpu"
