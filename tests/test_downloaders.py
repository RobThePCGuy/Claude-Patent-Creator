"""Tests for download utilities (mcp_server.downloaders)."""

import ssl

import pytest

from mcp_server.downloaders import _create_ssl_context


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
