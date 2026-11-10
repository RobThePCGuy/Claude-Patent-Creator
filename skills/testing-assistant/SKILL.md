---
name: testing-assistant
description: Run regression tests, local diagnostics and configured service checks.
---

# Testing Assistant

## Source regression suite

Run from a source checkout. Install its development dependencies into the README venv first. This is an editable development install; beginner installs should keep the normal GitHub pip route.

macOS/Linux:
```bash
"$HOME/patent-creator-venv/bin/python" -m pip install -e ".[dev]"
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\python.exe" -m pip install -e ".[dev]"
```

Use the checkout's modules even if the interpreter has another editable install:

macOS/Linux:
```bash
PYTHONPATH=.:mcp_server "$HOME/patent-creator-venv/bin/python" -m pytest -q
"$HOME/patent-creator-venv/bin/python" -m ruff check .
```

Windows PowerShell:
```powershell
$env:PYTHONPATH = ".;mcp_server"
& "$HOME\patent-creator-venv\Scripts\python.exe" -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Regression tests failed" }
& "$HOME\patent-creator-venv\Scripts\python.exe" -m ruff check .
if ($LASTEXITCODE -ne 0) { throw "Lint failed" }
```

Review every failure. Do not replace regression tests with an installation diagnostic or claim success based on printed progress alone.

## Installed-package diagnostics

The diagnostic scripts live in the plugin source, not in the pip package. Resolve `${CLAUDE_PLUGIN_ROOT}` to the actual plugin folder first. For a source checkout, use its absolute path. Set `PLUGIN_ROOT` below to that location; the example deliberately includes a space. Keep paths quoted.

macOS/Linux:
```bash
PLUGIN_ROOT="/absolute/path/Patent Plugin"
```

Windows PowerShell:
```powershell
$PLUGIN_ROOT = "C:\absolute\path\Patent Plugin"
```


macOS/Linux:
```bash
"$HOME/patent-creator-venv/bin/python" "$PLUGIN_ROOT/scripts/test_install.py"
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\python.exe" "$PLUGIN_ROOT/scripts/test_install.py"
```

macOS/Linux:
```bash
"$HOME/patent-creator-venv/bin/python" "$PLUGIN_ROOT/scripts/test_analyzers.py"
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\python.exe" "$PLUGIN_ROOT/scripts/test_analyzers.py"
```

Check the exit status after each command. On PowerShell, use `$LASTEXITCODE`; on macOS/Linux, use `$?` immediately after the command. No venv activation is required.

Additional scripts that exist in `scripts/`:

| Script | When to run |
|---|---|
| `test_gpu.py` | CUDA is intended; CPU-only systems can skip |
| `test_embedding_speed.py` | Benchmark model embedding; may download model data |
| `test_google_patents.py` | SerpApi is configured; consumes search quota |
| `test_bigquery.py` | BigQuery is configured; can consume query quota |
| `test_literature_search.py` | Check live research-paper services |
| `test_epo_analyzers.py` | Exercise EPO analyzers |

Run these with the same quoted script-path pattern. BigQuery is optional and must not gate a SerpApi-only installation. Report unavailable services as skipped. Index regression tests are in `tests/` and run with pytest.

For credentials saved only with `config set`, prefer the corresponding MCP status/search tools after restarting Claude Code. These standalone diagnostics do not all load saved settings; an unset-key result from a script does not prove that the saved configuration is broken.

## Manual verification

In Claude Code, search MPEP and inspect citations, search patents with the configured provider, review synthetic claims and generate a diagram if Graphviz is available. Record what was actually tested and what failed or was skipped. Never prefill a checklist as passed.

## Adding tests

Put regression tests in `tests/`. Assert observable results for valid input, invalid input and relevant failure paths. For a bug fix, run the test with the fix removed to establish that it catches the original defect, then restore the fix and rerun.
