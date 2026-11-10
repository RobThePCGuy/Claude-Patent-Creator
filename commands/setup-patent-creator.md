---
description: Run complete setup for Claude Patent Creator (install dependencies, download MPEP, build index)
allowed-tools: Bash, Read, Write
---

# Setup Patent Creator

This is the same setup as `/setup-patent-system`. Read `${CLAUDE_PLUGIN_ROOT}/commands/setup-patent-system.md` and follow it exactly: it installs into `~/patent-creator-venv` (the folder the README uses), runs `patent-creator setup` from there, and confirms the connection to Claude Code before reporting success.

If `~/patent-creator-venv/bin/patent-creator` (Windows: `$HOME\patent-creator-venv\Scripts\patent-creator.exe`) already exists, skip the install and just run its `setup`; downloads and the index are kept, and setup rebuilds only when needed.
