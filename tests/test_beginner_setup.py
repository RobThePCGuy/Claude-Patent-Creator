"""Guards for problems a fresh-user install walk hit on a real Mac.

1. Setup registered the base interpreter instead of the venv's python
   (Path.resolve() follows the venv symlink), so Claude Code could not
   connect, while verify-config still said "Configuration is correct".
2. health/serve demanded the MPEP PDFs even though setup offers to delete
   them and the server only needs the built index.
3. Setup installed Graphviz through the system package manager unasked.
"""

import argparse
import os
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "mcp_server"))

import cli  # noqa: E402
from path_utils import PathFormatter, interpreter_path  # noqa: E402

needs_symlinks = pytest.mark.skipif(os.name == "nt", reason="symlink creation needs admin on Windows")


@needs_symlinks
def test_registration_keeps_the_venv_python_link(tmp_path):
    venv_python = tmp_path / "venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    venv_python.symlink_to(sys.executable)

    python_str, _ = PathFormatter.format_for_claude_mcp(venv_python, tmp_path / "server.py")

    assert python_str == str(venv_python).replace("\\", "/")
    assert interpreter_path(venv_python) == str(venv_python)
    assert str(venv_python.resolve()) != python_str


def _script(tmp_path, body):
    path = tmp_path / "fake_server.py"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return str(path)


def test_handshake_succeeds_only_on_a_real_initialize_answer(tmp_path):
    server = _script(
        tmp_path,
        """
        import json, sys
        req = json.loads(sys.stdin.readline())
        print(json.dumps({"jsonrpc": "2.0", "id": req["id"],
                          "result": {"serverInfo": {"name": "demo"}}}), flush=True)
        sys.stdin.read()
        """,
    )
    ok, detail = cli.mcp_handshake(sys.executable, server, timeout=30)
    assert ok, detail
    assert detail == "demo"


def test_handshake_reports_why_a_server_cannot_start(tmp_path):
    server = _script(
        tmp_path,
        """
        import sys
        print('Error: mcp 2.x not found. Install with: pip install "mcp>=2.0.0,<3.0.0"', file=sys.stderr)
        sys.exit(1)
        """,
    )
    ok, detail = cli.mcp_handshake(sys.executable, server, timeout=30)
    assert not ok
    assert "mcp 2.x not found" in detail


def test_handshake_fails_when_nothing_answers(tmp_path):
    server = _script(tmp_path, "import sys, time\nsys.stdin.readline()\ntime.sleep(30)\n")
    ok, detail = cli.mcp_handshake(sys.executable, server, timeout=2)
    assert not ok
    assert "no answer" in detail


def test_index_alone_is_enough_to_be_ready(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "INDEX_DIR", tmp_path)
    assert not cli._index_ready()
    (tmp_path / "mpep_index.faiss").write_bytes(b"x")
    assert not cli._index_ready()
    (tmp_path / "mpep_metadata.json").write_text("{}", encoding="utf-8")
    assert cli._index_ready()


def test_serve_starts_without_pdfs_when_the_index_exists(tmp_path, monkeypatch):
    (tmp_path / "mpep_index.faiss").write_bytes(b"x")
    (tmp_path / "mpep_metadata.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(cli, "INDEX_DIR", tmp_path)
    started = {}

    def fake_run(cmd, **kwargs):
        started["cmd"] = cmd

        class R:
            returncode = 0

        return R()

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    assert cli.run_server(argparse.Namespace(no_hyde=False, rebuild_index=False)) == 0
    assert started["cmd"][-1].endswith("server.py")


def test_graphviz_is_never_installed_without_a_yes(monkeypatch):
    monkeypatch.setattr(cli, "_graphviz_ready", lambda: False)
    asked = []

    def boom(*a, **k):
        raise AssertionError("installer ran without consent")

    monkeypatch.setitem(sys.modules, "graphviz_installer", type(sys)("graphviz_installer"))
    sys.modules["graphviz_installer"].ensure_graphviz = boom

    assert cli._setup_graphviz(consent=None) is False
    assert cli._setup_graphviz(consent=lambda hint: asked.append(hint) or False) is False
    assert asked and "graphviz" in asked[0]


def test_graphviz_installs_after_a_yes(monkeypatch):
    monkeypatch.setattr(cli, "_graphviz_ready", lambda: False)
    ran = []
    monkeypatch.setitem(sys.modules, "graphviz_installer", type(sys)("graphviz_installer"))
    sys.modules["graphviz_installer"].ensure_graphviz = lambda: ran.append(1) or (True, "ok")

    assert cli._setup_graphviz(consent=lambda hint: True) is True
    assert ran
