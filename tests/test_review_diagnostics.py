"""Failure propagation in setup and diagnostics, findings 64-69 and 72-75."""
import builtins
import importlib
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

cli = importlib.import_module('mcp_server.cli')
cfg = importlib.import_module('mcp_server.config')
gui = importlib.import_module('mcp_server.config_gui')
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
    assert 'All downloads complete' not in capsys.readouterr().err


class _ReachedIndexBuildError(Exception):
    pass


def test_setup_continues_without_optional_subsequent_publications(monkeypatch, tmp_path, capsys):
    for name in ['download_mpep_pdfs', 'extract_mpep_pdfs', 'download_35_usc', 'download_37_cfr']:
        monkeypatch.setattr(cli, name, lambda *a, **kw: True)
    monkeypatch.setattr(cli, 'download_subsequent_publications', lambda *a, **kw: False)
    monkeypatch.setattr(cli, 'install_pytorch', lambda: False)
    monkeypatch.setattr(cli, 'check_all_sources', lambda: dict.fromkeys(
        ['mpep', '35_usc', '37_cfr', 'subsequent_pubs'], False))
    monkeypatch.setattr(cli, 'check_mpep_pdfs', lambda: 0)
    monkeypatch.setattr(cli, 'INDEX_DIR', tmp_path)
    monkeypatch.setattr(cli, '_setup_epo_pct_sources', lambda *a: False)

    def reached(**kw):
        raise _ReachedIndexBuildError

    monkeypatch.setattr(cli, 'MPEPIndex', reached)
    args = SimpleNamespace(no_hyde=True, rebuild=False, non_interactive=True)
    with pytest.raises(_ReachedIndexBuildError):
        cli.setup_command(args)
    err = capsys.readouterr().err
    assert 'Subsequent Publications missing' in err
    assert 'All downloads complete' not in err


def test_empty_batch_size_restores_default(monkeypatch, tmp_path):
    monkeypatch.setenv('PATENT_CONFIG_DIR', str(tmp_path))
    monkeypatch.delenv('PATENT_EMBED_BATCH_SIZE', raising=False)
    cfg.save_values({'PATENT_EMBED_BATCH_SIZE': '16'})
    changes, errors = gui._plan_save([(cfg.OPTIONS_BY_KEY['PATENT_EMBED_BATCH_SIZE'], '', '16')])
    assert not errors
    cfg.save_values(changes)
    assert cfg.get_effective('PATENT_EMBED_BATCH_SIZE') == ('', 'default')
    assert cfg.validate('PATENT_BIGQUERY_MAX_BYTES_BILLED', '') is not None


@pytest.mark.parametrize('value', ['1', 'yes', 'on'])
def test_gui_checkbox_honors_boolean_aliases(value, monkeypatch, tmp_path):
    monkeypatch.setenv('PATENT_CONFIG_DIR', str(tmp_path))
    monkeypatch.setenv('FORCE_CPU', value)
    values = []
    class Widget:
        def __init__(self, *a, **kw):
            pass
        def __getattr__(self, name):
            return lambda *a, **kw: None
    def boolean_var(*, value):
        values.append(value)
        return Widget()
    tk = SimpleNamespace(Tk=Widget, Canvas=Widget, BooleanVar=boolean_var, StringVar=Widget)
    tk.ttk = SimpleNamespace(**dict.fromkeys(
        ['Frame', 'Label', 'Entry', 'Button', 'Checkbutton', 'Combobox', 'LabelFrame', 'Notebook', 'Scrollbar'], Widget))
    tk.messagebox = SimpleNamespace(showerror=lambda *a: None)
    monkeypatch.setitem(sys.modules, 'tkinter', tk)
    assert gui.launch() == 0
    assert values[-1] is True


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
    assert result['python_package'] is False


def test_graphviz_health_requires_working_dot(monkeypatch):
    subprocess = importlib.import_module('subprocess')
    run = subprocess.run
    monkeypatch.setattr(subprocess, 'run',
                        lambda *a, **kw: run([sys.executable, '-c', 'raise SystemExit(1)'], **kw))
    assert health.SystemHealthChecker()._check_graphviz()['ready'] is False


def test_health_pip_uses_shared_platform_renderer(monkeypatch):
    commands = importlib.import_module('cli_command')
    monkeypatch.setattr(commands, 'python_command', lambda: '& "C:\\Users\\Rob Smith\\python.exe"')
    assert health._pip() == '& "C:\\Users\\Rob Smith\\python.exe" -m pip'


def test_gpu_diagnostic_really_imports_sentence_transformers(monkeypatch):
    monkeypatch.setenv('FORCE_CPU', 'false')
    block_import(monkeypatch, {'sentence_transformers'})
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(ROOT / 'scripts/test_gpu.py'), run_name='__main__')
    assert exc.value.code == 1


def fake_install_dependencies(monkeypatch, st_version='5.1.2', transformers_version='4.57.6'):
    model = SimpleNamespace(encode=lambda text: [0.0] * 3)
    modules = {
        'torch': SimpleNamespace(__version__='2.6.0', cuda=SimpleNamespace(is_available=lambda: False)),
        'transformers': SimpleNamespace(__version__=transformers_version),
        'sentence_transformers': SimpleNamespace(__version__=st_version, SentenceTransformer=lambda *a, **kw: model),
        'faiss': SimpleNamespace(__version__='1.13.2'),
        'numpy': SimpleNamespace(__version__='2.0.0'), 'mcp': SimpleNamespace(__version__='2.0.0'),
    }
    for key, value in modules.items():
        monkeypatch.setitem(sys.modules, key, value)


def test_install_requires_pymupdf(monkeypatch):
    fake_install_dependencies(monkeypatch)
    block_import(monkeypatch, {'pymupdf'})
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(ROOT / 'scripts/test_install.py'), run_name='__main__')
    assert exc.value.code == 1


@pytest.mark.parametrize(('st', 'transformers'), [('5.1.1', '4.57.6'), ('5.1.2', '4.57.5')])
def test_install_rejects_incompatible_versions(st, transformers, monkeypatch):
    fake_install_dependencies(monkeypatch, st, transformers)
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(ROOT / 'scripts/test_install.py'), run_name='__main__')
    assert exc.value.code == 1


@pytest.mark.parametrize('failure', ['version', 'server_import'])
def test_install_requires_compatible_mcp_server(failure, monkeypatch):
    fake_install_dependencies(monkeypatch)
    if failure == 'version':
        monkeypatch.setitem(sys.modules, 'mcp', SimpleNamespace(__version__='1.26.0'))
    else:
        block_import(monkeypatch, {'mcp.server.mcpserver'})
    with pytest.raises(SystemExit) as exc:
        runpy.run_path(str(ROOT / 'scripts/test_install.py'), run_name='__main__')
    assert exc.value.code == 1


@pytest.mark.parametrize('device', ['cpu', 'cuda'])

def test_benchmark_recommends_fastest_successful_batch(device, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(cuda=SimpleNamespace(
        is_available=lambda: device == 'cuda', get_device_name=lambda n: 'Test GPU',
        get_device_properties=lambda n: SimpleNamespace(total_memory=8 * 1024**3))))
    successful_batch = 16 if device == 'cpu' else 64
    def encode(texts, batch_size, **kw):
        if batch_size != successful_batch:
            raise RuntimeError('out of memory')
        return [[0.0]] * len(texts)
    monkeypatch.setitem(sys.modules, 'sentence_transformers', SimpleNamespace(
        SentenceTransformer=lambda *a, **kw: SimpleNamespace(encode=encode)))
    result = runpy.run_path(str(ROOT / 'scripts/test_embedding_speed.py'))
    result['test_embedding_speed']()
    output = capsys.readouterr().out.split('RECOMMENDATION')[-1]
    assert f'batch_size={successful_batch}' in output
    assert 'batch_size=32' not in output


def test_explicit_hyde_api_does_not_silently_fallback(monkeypatch):
    monkeypatch.setenv('HYDE_BACKEND', 'api')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')
    block_import(monkeypatch, {'anthropic', 'openai', 'transformers'})
    hyde = importlib.import_module('mcp_server.hyde')
    with pytest.raises(ValueError, match='API'):
        hyde.HyDEQueryExpander()
