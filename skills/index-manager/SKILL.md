---
name: index-manager
description: Manages MPEP index lifecycle including downloads, building, maintenance, and optimization.
---

# Index Manager Skill

Expert system for managing MPEP search index lifecycle: PDF downloads, index building, maintenance, updates, optimization.

**FOR CLAUDE:** All dependencies installed, system operational.
- Go directly to appropriate phase
- Scripts/tools in mcp_server/
- Use patent-creator CLI when available
- Only run diagnostics if operations fail

## When to Use

Building/rebuilding MPEP index, corruption/missing files, optimization, adding content, troubleshooting.

## Index Lifecycle

```
PDFs Not Present -> Download (2-5 min, 500MB)
  -> Extract & Parse (500MB data)
  -> Generate Embeddings (5-10 min GPU, 35-65 min CPU)
  -> Build FAISS + BM25 Indexes
  -> Index Ready (mcp_server/index/)
  -> Maintenance (Verify -> Optimize -> Update)
```

Paths below assume the README install (`~/patent-creator-venv`) and default data folder. `~/patent-creator-venv/bin/patent-creator health` prints the actual locations under "Storage" (Windows: `%APPDATA%\claude-patent-creator\data`; `PATENT_DATA_DIR` moves it). Below, `PC=~/patent-creator-venv/bin/patent-creator`, `PY=~/patent-creator-venv/bin/python`, `DATA=~/.local/share/claude-patent-creator/data`.

## Phase 1: Source PDFs

**Check status:** `$PC health` (lists each source; `[--] removed after indexing` is fine: the PDFs are only needed to rebuild).

```bash
ls "$DATA/pdfs"   # mpep-*.pdf, consolidated_laws.pdf, consolidated_rules.pdf, EPO/PCT files
$PC download-all  # fetch any missing US sources
```

**Verify integrity:**
```bash
$PY -c "
import fitz, os
from pathlib import Path
for pdf in Path(os.path.expanduser('~/.local/share/claude-patent-creator/data/pdfs')).glob('*.pdf'):
    try:
        doc = fitz.open(pdf); print(f'[OK] {pdf.name}: {len(doc)} pages'); doc.close()
    except Exception as e:
        print(f'[X] {pdf.name}: ERROR - {e}')
"
```

## Phase 2: Index Building

```bash
$PC setup --rebuild   # downloads anything missing, then rebuilds
```

Takes about 5 minutes with an NVIDIA GPU and 25-40 minutes otherwise (Apple Silicon builds on the CPU). A progress line with time left appears every few percent. `PATENT_MPEP_DEVICE=cpu` forces the CPU if the GPU runs out of memory. Chunking and batch size are fixed in code; `build_index()` takes only `force_rebuild`.

## Phase 3: Verification

```bash
ls -lh "$DATA/index"   # mpep_index.faiss, mpep_metadata.json, mpep_bm25.json
$PC health             # Index: Built [OK], chunk count, and any "needs a rebuild" warning
```

Then ask Claude: "Search MPEP for claim definiteness". Results show the chapter, PDF file and page.

## Phase 4: Maintenance

Rebuild after an MPEP revision, if health reports a problem, or when health says the index needs a rebuild (setup also does this automatically when it detects a known defect).

```bash
cp -r "$DATA/index" "$DATA/index_backup_$(date +%Y%m%d)"   # optional backup
$PC setup --rebuild
$PC health
```

## Phase 5: Content Updates

Re-running `$PC setup` downloads any source that is missing; `$PC setup --rebuild` re-indexes everything. Incremental updates are not supported.

## Troubleshooting

- OOM errors during build
- Build taking too long
- Corrupted index files
- Search returning no results

## Performance Tuning

- Embedding generation speed (GPU vs CPU)
- Search latency optimization
- Index size reduction
- Batch size tuning

## Quick Reference

| Command | Purpose |
|---------|---------|
| `~/patent-creator-venv/bin/patent-creator download-mpep` | Download MPEP PDFs |
| `~/patent-creator-venv/bin/patent-creator rebuild-index` | Build/rebuild search index |
| `~/patent-creator-venv/bin/patent-creator health` | Check index health |
| `ls -lh mcp_server/index/` | View index files |

**Best Practices:**
1. Backup before rebuild
2. Verify PDFs before building
3. Use GPU for 10x faster builds
4. Test after rebuild
5. Keep PDFs until verified
6. Weekly health checks
