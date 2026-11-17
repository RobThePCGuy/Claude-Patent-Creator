"""Failure propagation in setup and diagnostics, findings 64-69 and 72-75."""
import builtins
import importlib
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

cli = importlib.import_module('mcp_server.cli')
health = importlib.import_module('mcp_server.health_check')
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(('command', 'failure'), [
    (command, failure)
    for command in ['setup_command', 'download_all_command', 'download_mpep_command']
    for failure in ['extract_mpep_pdfs', 'download_35_usc', 'download_37_cfr', 'download_subsequent_publications']
    if command != 'download_mpep_command' or failure == 'extract_mpep_pdfs'
    if (command, failure) != ('setup_command', 'download_subsequent_publications')
])
def test_download_failure_returns_failure(command, failure, monkeypatch, tmp_path, capsys):
    for name in ['download_mpep_pdfs', 'extract_mpep_pdfs', 'download_35_usc',
                 'download_37_cfr', 'download_subsequent_publications']:
        monkeypatch.setattr(cli, name, lambda *a, _ok=name != failure, **kw: _ok)
    monkeypatch.setattr(cli, 'install_pytorch', lambda: False)
    monkeypatch.setattr(cli, 'check_all_sources', lambda: dict.fromkeys(
        ['mpep', '35_usc', '37_cfr', 'subsequent_pubs'], False))
    monkeypatch.setattr(cli, 'check_mpep_pdfs', lambda: 0)
    monkeypatch.setattr(cli, 'INDEX_DIR', tmp_path)
    monkeypatch.setattr(cli, '_setup_epo_pct_sources', lambda *a: False)
    # If setup incorrectly proceeds, stop before model downloads with a useful failure.
    monkeypatch.setattr(cli, 'MPEPIndex', lambda **kw: pytest.fail('setup built an index after download failure'))
    args = SimpleNamespace(no_hyde=True, rebuild=False, non_interactive=True)
    assert getattr(cli, command)(args) == 1


def block_import(monkeypatch, names):
    original = builtins.__import__
    def blocked(name, *args, **kwargs):
        if name in names:
            raise ImportError(f'{name} deliberately unavailable')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', blocked)


def test_graphviz_health_requires_python_package(monkeypatch):
    block_import(monkeypatch, {'graphviz'})
    monkeypatch.setattr(importlib.import_module('subprocess'), 'run',
                        lambda *a, **kw: SimpleNamespace(returncode=0, stderr='dot version', stdout=''))
    result = health.SystemHealthChecker()._check_graphviz()
    assert result['ready'] is False


def test_graphviz_health_requires_working_dot(monkeypatch):
    subprocess = importlib.import_module('subprocess')
    run = subprocess.run
    monkeypatch.setattr(subprocess, 'run',
                        lambda *a, **kw: run([sys.executable, '-c', 'raise SystemExit(1)'], **kw))
    assert health.SystemHealthChecker()._check_graphviz()['ready'] is False


def test_gpu_diagnostic_really_imports_sentence_transformers(monkeypatch):
    monkeypatch.setenv('FORCE_CPU', 'false')
    block_import(monkeypatch, {'sentence_transformers'})
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(ROOT / 'scripts/test_gpu.py'), run_name='__main__')
    assert exc.value.code == 1


def test_explicit_hyde_api_does_not_silently_fallback(monkeypatch):
    monkeypatch.setenv('HYDE_BACKEND', 'api')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')
    block_import(monkeypatch, {'anthropic', 'openai', 'transformers'})
    hyde = importlib.import_module('mcp_server.hyde')
    with pytest.raises(ValueError):
        hyde.HyDEQueryExpander()
