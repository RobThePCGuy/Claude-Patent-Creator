"""Tests for download utilities (mcp_server.downloaders)."""

import io
import ssl
import urllib.request

import pytest

from mcp_server.downloaders import FileDownloader, _create_ssl_context


class _FakeResponse:
    """Minimal stand-in for an HTTP response usable as a context manager."""

    def __init__(self, data: bytes, content_length: int):
        self._buf = io.BytesIO(data)
        self.headers = {"Content-Length": str(content_length)}

    def read(self, size):
        return self._buf.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_create_ssl_context_returns_verifying_context():
    """The context must keep certificate verification ON."""
    ctx = _create_ssl_context()
    assert isinstance(ctx, ssl.SSLContext)
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True


def test_create_ssl_context_uses_certifi_bundle(monkeypatch):
    """When certifi is importable, the context is built from its CA bundle.

    This is what fixes CERTIFICATE_VERIFY_FAILED on python.org macOS Python,
    which ships no system CA bundle (issue #23).
    """
    certifi = pytest.importorskip("certifi")

    captured = {}
    real_create = ssl.create_default_context

    def _spy(*args, **kwargs):
        captured["cafile"] = kwargs.get("cafile")
        return real_create(*args, **kwargs)

    monkeypatch.setattr(ssl, "create_default_context", _spy)
    _create_ssl_context()

    assert captured["cafile"] == certifi.where()


def test_complete_download_succeeds(tmp_path, monkeypatch):
    dest = tmp_path / "file.zip"
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _FakeResponse(b"x" * 100, 100))
    ok = FileDownloader.download_with_progress(
        "https://example.com/file.zip", dest, "test file", timeout_seconds=5
    )
    assert ok is True
    assert dest.read_bytes() == b"x" * 100


def test_truncated_download_fails_and_cleans_up(tmp_path, monkeypatch):
    """A stream shorter than Content-Length must fail and remove the partial file."""
    dest = tmp_path / "file.zip"
    # Advertise 100 bytes but only deliver 50.
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _FakeResponse(b"x" * 50, 100))
    ok = FileDownloader.download_with_progress(
        "https://example.com/file.zip", dest, "test file", timeout_seconds=5
    )
    assert ok is False
    assert not dest.exists()
