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


# --- Second fresh-user walk -------------------------------------------------


def test_log_lines_reach_the_live_terminal_after_a_captured_import():
    """The CLI imports the server under redirect_stderr; logs made then must
    still reach the real terminal later, or a 35-minute build looks frozen."""
    import contextlib
    import io

    import logging_config

    with contextlib.redirect_stderr(io.StringIO()):
        lg = logging_config.setup_logging(format_type="human")
    live = io.StringIO()
    with contextlib.redirect_stderr(live):
        lg.info("progress-line-probe")
    assert "progress-line-probe" in live.getvalue()


def test_index_build_prints_plain_progress_lines(monkeypatch):
    import importlib

    import numpy as np

    mpep_search = importlib.import_module("mpep_search")
    lines = []
    monkeypatch.setattr(mpep_search, "_log_info", lambda msg, **kw: lines.append(msg))

    class FakeModel:
        def encode(self, texts, **kwargs):
            return np.ones((len(texts), 3), dtype="float32")

    idx = mpep_search.MPEPIndex.__new__(mpep_search.MPEPIndex)
    idx.model, idx.device = FakeModel(), "cpu"
    out = idx._encode_with_progress([f"t{i}" for i in range(100)], batch_size=10, slices=4)

    assert out.shape == (100, 3)
    assert len(lines) >= 4
    assert lines[-1].startswith("Building search index: 100%")
    assert "left" in lines[0]


def test_removed_source_files_are_not_flagged_once_indexed(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "INDEX_DIR", tmp_path)
    monkeypatch.setattr(cli, "_INDEXED_SOURCES", None)
    assert "[X]" in cli._source_line("35 USC:", False)
    import json

    (tmp_path / "mpep_index.faiss").write_bytes(b"x")
    meta = {"metadata": [{"source": "MPEP"}, {"source": "35_USC"}]}
    (tmp_path / "mpep_metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    monkeypatch.setattr(cli, "_INDEXED_SOURCES", None)
    line = cli._source_line("35 USC:", False)
    assert "[X]" not in line and "removed after indexing" in line
    # 37 CFR was never indexed: a missing file is a real gap, not a cleanup
    assert "[X]" in cli._source_line("37 CFR:", False)
    assert "[OK]" in cli._source_line("35 USC:", True)


def test_missing_serpapi_key_message_gives_a_command_that_works():
    from google_patents_search import GooglePatentsSearch

    msg = GooglePatentsSearch.setup_message()
    assert "config set SERPAPI_API_KEY" in msg
    assert ".env" not in msg
    assert "restart Claude Code" in msg


def test_bigquery_is_only_offered_as_ready_when_configured(monkeypatch):
    from tools import google_patents_tools as gpt

    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    assert "once the optional BigQuery setup" in gpt._bigquery_fallback()
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "demo")
    assert "once the optional" not in gpt._bigquery_fallback()


def test_printed_commands_name_the_installed_executable(tmp_path, monkeypatch):
    bin_dir = tmp_path / "venv" / "bin"
    bin_dir.mkdir(parents=True)
    exe = bin_dir / "patent-creator"
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(cli.sys, "executable", str(bin_dir / "python"))
    import cli_command

    monkeypatch.setattr(cli_command.shutil, "which", lambda name: None)
    assert cli._cli() == str(exe)


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


def test_saved_values_are_reported_as_saved_not_as_env(tmp_path):
    _save(tmp_path, {"PATENT_LOG_FORMAT": "human"})
    code = (
        "import sys; sys.path.insert(0, 'mcp_server'); import cli, config; "
        "print(config.get_effective('PATENT_LOG_FORMAT'))"
    )
    out = _run_isolated(tmp_path, code)
    assert out.stdout.strip().splitlines()[-1] == "('human', 'file')"


def test_cli_prefers_readable_logs_without_touching_the_setting(tmp_path):
    code = (
        "import sys, os, logging; sys.path.insert(0, 'mcp_server'); import cli; "
        "h = logging.getLogger('claude-patent-creator').handlers[0]; "
        "print(type(h.formatter).__name__); print(os.environ.get('PATENT_LOG_FORMAT'))"
    )
    out = _run_isolated(tmp_path, code)
    lines = out.stdout.strip().splitlines()
    assert lines[-2] == "HumanReadableFormatter"
    assert lines[-1] == "None"


def test_setup_rebuilds_an_index_with_a_known_defect(tmp_path, monkeypatch):
    import json

    (tmp_path / "mpep_index.faiss").write_bytes(b"x")
    meta = {"chunks": ["a"], "metadata": [{"source": "EPC_RULES", "section": "EPC"}]}
    (tmp_path / "mpep_metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    monkeypatch.setattr(cli, "INDEX_DIR", tmp_path)
    defects = cli._index_defects()
    assert defects and "setup --rebuild" in defects[0]

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


def test_every_guidelines_chunk_cites_its_official_page(tmp_path):
    import importlib

    mpep_search = importlib.import_module("mpep_search")
    body = " ".join(f"Claims must be clear and supported by the description, point {i}." for i in range(120))
    text = (
        "EPO GUIDELINES FOR EXAMINATION — 2026\nCoverage: test\n"
        "### 5. Clarity of claims and support by the description\n"
        "Source: https://www.epo.org/en/legal/guidelines-epc/2026/d_v_5.html\n" + body + "\n\n"
        "### 4.1 Form and content\n"
        "Source: https://www.epo.org/en/legal/guidelines-epc/2026/f_iv_4_1.html\n" + body + "\n"
    )
    path = tmp_path / "epo_guidelines.txt"
    path.write_text(text, encoding="utf-8")
    idx = mpep_search.MPEPIndex.__new__(mpep_search.MPEPIndex)
    chunks = idx.extract_text_from_epo_guidelines(path)
    metas = [mpep_search.MPEPIndex._chunk_to_metadata(c) for c in chunks]

    d = [m for m in metas if m.get("source_url", "").endswith("d_v_5.html")]
    f = [m for m in metas if m.get("source_url", "").endswith("f_iv_4_1.html")]
    assert len(d) > 1 and len(f) > 1  # continuation chunks keep the link
    assert all("Part D, Chapter V, 5" in m["section"] for m in d)
    assert all("Part F, Chapter IV, 4.1" in m["section"] for m in f)
    assert all(m["part"] == "Part D" for m in d)
    assert not any("Source:" in c["text"] for c in chunks)


def test_recovery_messages_name_the_installed_command(tmp_path, monkeypatch):
    import cli_command

    bin_dir = tmp_path / "venv" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "patent-creator").write_text("", encoding="utf-8")
    monkeypatch.setattr(cli_command.sys, "executable", str(bin_dir / "python"))
    monkeypatch.setattr(cli_command.shutil, "which", lambda name: None)
    exe = str(bin_dir / "patent-creator")

    out = cli_command.render("Run patent-creator setup --rebuild, or 'patent-creator config list'.")
    assert out == f"Run {exe} setup --rebuild, or '{exe} config list'."
    # names that merely contain the word are left alone
    assert cli_command.render("claude-patent-creator stays") == "claude-patent-creator stays"


def test_short_guidelines_pages_are_kept_and_unknown_pages_get_no_stale_locator(tmp_path):
    import importlib

    mpep_search = importlib.import_module("mpep_search")
    long_body = " ".join(f"Decision text {i}." for i in range(80))
    text = (
        "### VII. Decisions\n"
        "Source: https://www.epo.org/en/legal/guidelines-epc/2026/d_vii.html\n" + long_body + "\n"
        "### Chapter VIII – Decisions\n"
        "Source: https://www.epo.org/en/legal/guidelines-epc/2026/d_viii.html\n"
        "General remarks on decisions appear in E-IX.\n"
        "### Index for Computer-Implemented Inventions\n"
        "Source: https://www.epo.org/en/legal/guidelines-epc/2026/j.html\n" + long_body + "\n"
        "### Chapter V – Annex\n"
        "Source: https://www.epo.org/en/legal/guidelines-epc/2026/c_va.html\n" + long_body + "\n"
    )
    path = tmp_path / "epo_guidelines.txt"
    path.write_text(text, encoding="utf-8")
    idx = mpep_search.MPEPIndex.__new__(mpep_search.MPEPIndex)
    metas = [mpep_search.MPEPIndex._chunk_to_metadata(c) for c in idx.extract_text_from_epo_guidelines(path)]
    by_page = {}
    for m in metas:
        by_page.setdefault(m["source_url"].rsplit("/", 1)[-1], []).append(m)

    assert "d_viii.html" in by_page  # a one-sentence page is still searchable
    assert all("Part D" not in m["section"] for m in by_page["j.html"])
    assert all(m["part"] == "EPO Guidelines" for m in by_page["j.html"])
    assert all("Part C, Chapter V, Annex" in m["section"] for m in by_page["c_va.html"])


def test_health_fixes_name_commands_that_exist():
    import inspect

    import health_check

    source = inspect.getsource(health_check)
    assert "--rebuild-index" not in source  # setup has no such option
    assert '"fix": "patent-creator' not in source


def test_install_advice_names_this_installs_python(tmp_path, monkeypatch):
    import cli_command

    monkeypatch.setattr(cli_command.sys, "executable", str(tmp_path / "venv" / "bin" / "python"))
    out = cli_command.render("Install with: pip install graphviz")
    assert out == f"Install with: {tmp_path / 'venv' / 'bin' / 'python'} -m pip install graphviz"
    # already-qualified commands are left alone
    assert cli_command.render("python -m pip install x") == "python -m pip install x"


def test_no_user_facing_bare_install_advice_left():
    """Every 'pip install' a user is told to run goes through cli_command.render."""
    import re

    root = Path(__file__).resolve().parent.parent / "mcp_server"
    offenders = []
    for path in root.rglob("*.py"):
        if path.name == "cli_command.py":
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            wrapped = re.compile(r"render|_rc\(")
            if re.search(r'"[^"]*(?<!-m )pip install', line) and not wrapped.search(line) and not line.lstrip().startswith("#"):
                ctx = "\n".join(path.read_text(encoding="utf-8").splitlines()[max(0, n - 4) : n])
                if not wrapped.search(ctx):
                    offenders.append(f"{path.name}:{n}")
    assert offenders == []


def test_paths_with_spaces_paste_into_each_shell(monkeypatch):
    import cli_command

    monkeypatch.setattr(cli_command.os, "name", "nt")
    assert cli_command._quote(r"C:\Users\Rob Smith\v\Scripts\python.exe") == r'& "C:\Users\Rob Smith\v\Scripts\python.exe"'
    monkeypatch.setattr(cli_command.os, "name", "posix")
    assert cli_command._quote("/Users/Rob Smith/v/bin/python") == '"/Users/Rob Smith/v/bin/python"'
    assert cli_command._quote("/Users/rob/v/bin/python") == "/Users/rob/v/bin/python"


def test_embed_batch_size_setting_is_honoured(monkeypatch):
    import importlib

    mpep_search = importlib.import_module("mpep_search")
    idx = mpep_search.MPEPIndex.__new__(mpep_search.MPEPIndex)
    idx.device = "cuda"
    monkeypatch.delenv("PATENT_EMBED_BATCH_SIZE", raising=False)
    assert idx._embed_batch_size() == 256
    monkeypatch.setenv("PATENT_EMBED_BATCH_SIZE", "16")
    assert idx._embed_batch_size() == 16
    monkeypatch.setenv("PATENT_EMBED_BATCH_SIZE", "lots")
    assert idx._embed_batch_size() == 256


def test_no_key_fallback_offers_a_labelled_web_first_screen(monkeypatch):
    from tools import google_patents_tools as gpt

    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    msg = gpt._bigquery_fallback()
    assert "patents.google.com" in msg
    assert "not evidence of no prior art" in msg
