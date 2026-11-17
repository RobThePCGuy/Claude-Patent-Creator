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


def test_handshake_fails_when_nothing_answers(tmp_path):
    server = _script(tmp_path, "import sys, time\nsys.stdin.readline()\ntime.sleep(30)\n")
    ok, detail = cli.mcp_handshake(sys.executable, server, timeout=2)
    assert not ok


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


def test_graphviz_is_never_installed_without_a_yes(monkeypatch):
    monkeypatch.setattr(cli, "_graphviz_ready", lambda: False)
    asked = []

    def boom(*a, **k):
        raise AssertionError("installer ran without consent")

    monkeypatch.setitem(sys.modules, "graphviz_installer", type(sys)("graphviz_installer"))
    sys.modules["graphviz_installer"].ensure_graphviz = boom

    assert cli._setup_graphviz(consent=None) is False
    assert cli._setup_graphviz(consent=lambda hint: asked.append(hint) or False) is False


# --- Second fresh-user walk -------------------------------------------------


def test_short_abstract_is_advice_and_over_150_words_is_a_failure():
    from formalities_checker import FormalitiesChecker

    short = FormalitiesChecker().check_all_formalities(abstract="A mug heats a beverage.")
    assert short["results"]["abstract"]["compliant"] is True
    long = FormalitiesChecker().check_all_formalities(abstract=" ".join(["word"] * 151) + ".")
    assert long["results"]["abstract"]["compliant"] is False


# --- Third fresh-user walk --------------------------------------------------


def _run_isolated(tmp_path, code, extra_env=None):
    import subprocess

    home = tmp_path / "home"
    (home / ".config" / "claude-patent-creator").mkdir(parents=True, exist_ok=True)
    env = {"HOME": str(home), "PATH": os.environ.get("PATH", ""), "APPDATA": str(home)}
    if os.name == "nt":
        env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", "")
    env.update(extra_env or {})
    root = Path(__file__).resolve().parent.parent
    return subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=str(root), timeout=120
    )


def _save(tmp_path, values):
    import json

    if os.name == "nt":
        folder = tmp_path / "home" / "claude-patent-creator"
    else:
        folder = tmp_path / "home" / ".config" / "claude-patent-creator"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "config.json").write_text(json.dumps(values), encoding="utf-8")


def test_saved_settings_reach_the_cli_before_paths_are_computed(tmp_path):
    moved = tmp_path / "moved-data"
    _save(tmp_path, {"GOOGLE_CLOUD_PROJECT": "saved-proj", "PATENT_DATA_DIR": str(moved)})
    code = (
        "import sys, os; sys.path.insert(0, 'mcp_server'); import cli; "
        "print(os.environ.get('GOOGLE_CLOUD_PROJECT')); print(cli.INDEX_DIR)"
    )
    out = _run_isolated(tmp_path, code)
    assert out.returncode == 0, out.stderr
    lines = out.stdout.strip().splitlines()
    assert lines[-2] == "saved-proj"
    assert lines[-1].startswith(str(moved))


def test_a_real_env_var_still_beats_a_saved_setting(tmp_path):
    _save(tmp_path, {"GOOGLE_CLOUD_PROJECT": "saved-proj"})
    code = "import sys, os; sys.path.insert(0, 'mcp_server'); import cli; print(os.environ['GOOGLE_CLOUD_PROJECT'])"
    out = _run_isolated(tmp_path, code, {"GOOGLE_CLOUD_PROJECT": "from-env"})
    assert out.stdout.strip().splitlines()[-1] == "from-env"


def test_setup_rebuilds_an_index_with_a_known_defect(tmp_path, monkeypatch):
    import json

    (tmp_path / "mpep_index.faiss").write_bytes(b"x")
    meta = {"chunks": ["a"], "metadata": [{"source": "EPC_RULES", "section": "EPC"}]}
    (tmp_path / "mpep_metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    monkeypatch.setattr(cli, "INDEX_DIR", tmp_path)
    defects = cli._index_defects()
    assert defects

    meta["metadata"].append({"source": "EPC", "section": "EPC"})
    (tmp_path / "mpep_metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    assert cli._index_defects() == []


def test_saved_settings_reach_the_server_claude_code_starts(tmp_path):
    """Claude Code runs server.py directly, never through the CLI, so the
    server must apply saved settings itself before computing its paths."""
    moved = tmp_path / "moved-data"
    _save(tmp_path, {"PATENT_DATA_DIR": str(moved)})
    code = "import sys; sys.path.insert(0, 'mcp_server'); import server; print(server.INDEX_DIR)"
    out = _run_isolated(tmp_path, code)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().splitlines()[-1].startswith(str(moved))


# --- Fourth fresh-user walk -------------------------------------------------


def test_no_key_fallback_offers_a_labelled_web_first_screen(monkeypatch):
    from tools import google_patents_tools as gpt

    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    msg = gpt._bigquery_fallback()
    assert "not evidence of no prior art" in msg
