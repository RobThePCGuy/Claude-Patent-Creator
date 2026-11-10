---
name: index-manager
description: Manage legal-source downloads, index builds, diagnostics and maintenance.
---

# Index Manager

## Find the active data

macOS/Linux:
```bash
"$HOME/patent-creator-venv/bin/patent-creator" health
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\patent-creator.exe" health
```

Read the Storage paths. Defaults are under `$HOME/.local/share/claude-patent-creator/data` on macOS/Linux and `$env:APPDATA\claude-patent-creator\data` on Windows. `PATENT_DATA_DIR` or existing legacy data can change these locations.

For a directory listing that resolves saved configuration on either platform:

macOS/Linux:
```bash
"$HOME/patent-creator-venv/bin/python" -c "from mcp_server.config import apply_config_to_env; apply_config_to_env(); from mcp_server.data_paths import mpep_dir, index_dir; print('PDFs:', mpep_dir()); print(*mpep_dir().glob('*.pdf'), sep='\n'); print('Index:', index_dir()); print(*index_dir().glob('*'), sep='\n')"
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\python.exe" -c "from mcp_server.config import apply_config_to_env; apply_config_to_env(); from mcp_server.data_paths import mpep_dir, index_dir; print('PDFs:', mpep_dir()); print(*mpep_dir().glob('*.pdf'), sep='\n'); print('Index:', index_dir()); print(*index_dir().glob('*'), sep='\n')"
```

## Download and build

macOS/Linux:
```bash
"$HOME/patent-creator-venv/bin/patent-creator" setup --rebuild
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\patent-creator.exe" setup --rebuild
```

Setup downloads missing sources and reprocesses the current files. It does not replace existing PDFs with newer legal editions. For an edition change, obtain the intended official files, verify their editions, replace the relevant files in the reported PDF directory and rebuild. Back up source and index directories before replacing them. A missing PDF can coexist with a usable index after source cleanup, but it must be restored before rebuilding.

## Memory and speed

Build time varies with the machine and corpus. Batch size is configurable:

macOS/Linux:
```bash
"$HOME/patent-creator-venv/bin/patent-creator" config set PATENT_EMBED_BATCH_SIZE 16
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\patent-creator.exe" config set PATENT_EMBED_BATCH_SIZE 16
```

Use 8 if 16 still runs out of memory. Remove the override with `config unset PATENT_EMBED_BATCH_SIZE` to restore the automatic default (256 on CUDA, 32 otherwise). To use CPU, save `PATENT_MPEP_DEVICE` as `cpu` with `config set`; remove it with `config unset PATENT_MPEP_DEVICE` when finished. Restart the build after changing settings.

## Verify

Run `health` with the installed CLI as above. It should report an index and chunk count; resolve any rebuild warnings. Then ask Claude Code to search MPEP for claim definiteness and inspect the source/page references. A successful rebuild is not evidence that the legal text is the latest edition.

For an optional backup without shell-specific date or copy commands:

macOS/Linux:
```bash
"$HOME/patent-creator-venv/bin/python" -c "from datetime import datetime; import shutil; from mcp_server.config import apply_config_to_env; apply_config_to_env(); from mcp_server.data_paths import index_dir; src=index_dir(); dst=src.with_name('index_backup_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')); shutil.copytree(src, dst); print(dst)"
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\python.exe" -c "from datetime import datetime; import shutil; from mcp_server.config import apply_config_to_env; apply_config_to_env(); from mcp_server.data_paths import index_dir; src=index_dir(); dst=src.with_name('index_backup_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')); shutil.copytree(src, dst); print(dst)"
```

Keep the backup until searches work against the rebuilt index.
