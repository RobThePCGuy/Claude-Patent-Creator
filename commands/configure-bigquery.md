---
description: Configure optional Google BigQuery patent search
allowed-tools: Bash
---

# Configure BigQuery

SerpApi is the default patent-search provider. Use this command only when the user wants BigQuery. It requires a Google Cloud project, the BigQuery API and Application Default Credentials. Query charges depend on usage; the sandbox has limits.

Install Google's `gcloud` tool if needed: https://cloud.google.com/sdk/docs/install.
Ask the user to run this in their own terminal so browser sign-in can finish:

```text
gcloud auth application-default login
```

Save the project ID:

macOS/Linux:
```bash
"$HOME/patent-creator-venv/bin/patent-creator" config set GOOGLE_CLOUD_PROJECT "your-project-id"
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\patent-creator.exe" config set GOOGLE_CLOUD_PROJECT "your-project-id"
```

Verify authentication and dataset/table access:

macOS/Linux:
```bash
"$HOME/patent-creator-venv/bin/patent-creator" check-bigquery
```

Windows PowerShell:
```powershell
& "$HOME\patent-creator-venv\Scripts\patent-creator.exe" check-bigquery
```

This check reads table metadata. It does not run a sample patent search or return patent results. To test a real query, use `search_patents_bigquery` through MCP after `check_bigquery_status` succeeds; it can consume BigQuery quota. Restart Claude Code after changing saved settings.
