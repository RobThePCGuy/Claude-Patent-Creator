---
description: Run local diagnostics and selected optional service tests
allowed-tools: Bash
argument-hint: [test-type]
---

# Test Patent Creator

The diagnostic scripts live in the plugin source, not in the pip package. Resolve `${CLAUDE_PLUGIN_ROOT}` to the actual plugin folder first. For a source checkout, use its absolute path. Set `PLUGIN_ROOT` below to that location; the example deliberately includes a space. Keep paths quoted.

macOS/Linux:
```bash
PLUGIN_ROOT="/absolute/path/Patent Plugin"
```

Windows PowerShell:
```powershell
$PLUGIN_ROOT = "C:\absolute\path\Patent Plugin"
```


## Local checks

Run installation diagnostics, then analyzers. Inspect failures and exit status before continuing:

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

## Optional checks

Choose only the component being tested. A missing optional service is a skip, not a failed base installation.

- `gpu`: `scripts/test_gpu.py`, for an intended NVIDIA/CUDA installation.
- `embeddings`: `scripts/test_embedding_speed.py`, for a local model benchmark; it can download model data.
- `bigquery`: `scripts/test_bigquery.py`, only with configured BigQuery credentials. This can consume query quota.
- `analyzers`: `scripts/test_analyzers.py`.
- `all`: local checks plus configured optional components; report skipped components explicitly.

For example, an optional GPU check:

macOS/Linux:
```bash
"$HOME/patent-creator-venv/bin/python" "$PLUGIN_ROOT/scripts/test_gpu.py"
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\python.exe" "$PLUGIN_ROOT/scripts/test_gpu.py"
```

For credentials saved only with `config set`, prefer the corresponding MCP status/search tools after restarting Claude Code. These standalone diagnostics do not all load saved settings; an unset-key result from a script does not prove that the saved configuration is broken.

Replace only the script filename to run another listed diagnostic. Confirm actual search and review behavior in Claude Code as well; diagnostics alone do not verify the complete workflow.
