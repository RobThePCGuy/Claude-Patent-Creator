---
description: Rebuild MPEP search index (needed after MPEP updates or corruption)
allowed-tools: Bash
---

# Rebuild MPEP Index

> **Windows:** use `$HOME\patent-creator-venv\Scripts\python.exe` and `$HOME\patent-creator-venv\Scripts\patent-creator.exe` wherever this page says `~/patent-creator-venv/bin/python` or `~/patent-creator-venv/bin/patent-creator`.

Rebuild the hybrid search index (FAISS + BM25) from MPEP PDFs.

## Instructions

1. Verify MPEP PDFs are present (${CLAUDE_PLUGIN_ROOT}/pdfs)
2. Run rebuild command
3. Wait for completion (about 5 minutes with an NVIDIA GPU, 25-40 minutes otherwise; a progress line appears every few percent)
4. Verify index health

## Command

```bash
~/patent-creator-venv/bin/patent-creator setup --rebuild
# Windows: $HOME\patent-creator-venv\Scripts\patent-creator.exe setup --rebuild
```

## What This Does

- Deletes existing index files
- Re-extracts text from all MPEP PDFs
- Generates embeddings (BGE-base-en-v1.5)
- Builds FAISS vector index
- Builds BM25 keyword index
- Creates metadata mappings
- Verifies index integrity

## When to Rebuild

- MPEP PDFs updated
- Index corruption detected
- Slow or irrelevant search results
- After changing embedding model
- GPU newly available (for faster building)

## Time Estimates

- RTX 3060 GPU: 5-10 minutes
- RTX 4090 GPU: 3-5 minutes
- CPU only: 35-65 minutes
- Apple Silicon (M1/M2): 15-25 minutes
