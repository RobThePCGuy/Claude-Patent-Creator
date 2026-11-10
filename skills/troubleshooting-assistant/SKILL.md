---
name: troubleshooting-assistant
description: Diagnose MCP registration, dependency, search, GPU and index failures.
---

# Troubleshooting Assistant

Record the exact error and reproduce the smallest failing operation. Check the installed environment before changing configuration.

macOS/Linux:
```bash
"$HOME/patent-creator-venv/bin/patent-creator" health
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\patent-creator.exe" health
```

macOS/Linux:
```bash
"$HOME/patent-creator-venv/bin/patent-creator" verify-config
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\patent-creator.exe" verify-config
```

Check registration with `claude mcp list`. After repairs, restart Claude Code and exercise the failing MCP operation again.

## Component diagnostics

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

Use `scripts/test_gpu.py` for an intended CUDA installation, `scripts/test_google_patents.py` for configured SerpApi, or `scripts/test_bigquery.py` only for configured BigQuery. Use the quoted invocation pattern above and report skipped optional components. Live search tests consume service quota.

For credentials saved only with `config set`, prefer the corresponding MCP status/search tools after restarting Claude Code. These standalone diagnostics do not all load saved settings; an unset-key result from a script does not prove that the saved configuration is broken.

## Repairs

- Import failure: reinstall the package in the same venv:

macOS/Linux:
```bash
"$HOME/patent-creator-venv/bin/python" -m pip install --upgrade git+https://github.com/RobThePCGuy/Claude-Patent-Creator.git
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\python.exe" -m pip install --upgrade git+https://github.com/RobThePCGuy/Claude-Patent-Creator.git
```

- Missing or damaged index: follow the **Index Manager** skill. Check the actual Storage paths, then use `setup --rebuild`; rebuilding does not update source editions.
- GPU failure: follow `docs/GPU_SETUP.md` under the plugin root. Avoid choosing a CUDA wheel without checking the GPU architecture.
- Build OOM: save `PATENT_EMBED_BATCH_SIZE` as 16 or 8 with `config set`, then retry. CPU mode is available through `PATENT_MPEP_DEVICE=cpu` saved with `config set`.
- SerpApi failure: call `check_google_patents_status`; check saved key configuration and quota without printing the key.
- BigQuery failure: only if this provider is wanted, follow `/configure-bigquery`.
- Search quality: inspect retrieved source text and metadata, vary the query, and distinguish no matches from a service failure.

Enable debug logging if needed:

macOS/Linux:
```bash
"$HOME/patent-creator-venv/bin/patent-creator" config set PATENT_LOG_LEVEL DEBUG
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\patent-creator.exe" config set PATENT_LOG_LEVEL DEBUG
```

Restart Claude Code to apply settings. Restore normal logging with `config unset PATENT_LOG_LEVEL`. Keep credentials out of diagnostic reports.
