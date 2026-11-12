"""The MCP handshake must not wait on the AI libraries.

Claude Code only sees the patent tools once the server answers. When startup
imported torch and sentence-transformers and ran the full health check (both
models plus HuggingFace calls), that took ~3.7s, and a question asked in that
window was answered without the patent tools. These libraries now load on
first index use.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEAVY = ("torch", "sentence_transformers", "faiss")


def test_importing_server_leaves_heavy_ai_libraries_unloaded():
    code = (
        "import sys; import server; "
        f"print([m for m in {HEAVY!r} if m in sys.modules])"
    )
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / "mcp_server")]))
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT / "mcp_server",
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    assert out.stdout.strip().splitlines()[-1] == "[]", out.stdout


def test_server_does_not_run_full_health_check_before_serving():
    source = (ROOT / "mcp_server" / "server.py").read_text(encoding="utf-8")
    assert "check_all_dependencies(" not in source


def test_broken_vector_package_gives_install_guidance(monkeypatch):
    import builtins

    import pytest

    from mcp_server import mpep_search as ms

    monkeypatch.setattr(ms, "SentenceTransformer", None)
    real_import = builtins.__import__

    def broken(name, *args, **kwargs):
        if name == "faiss":
            raise ImportError("simulated broken wheel")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", broken)
    with pytest.raises(ImportError, match="pip install sentence-transformers"):
        ms._load_vector_libs()
