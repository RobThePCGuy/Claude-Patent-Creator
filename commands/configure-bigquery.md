---
description: Configure Google BigQuery authentication for patent search (100M+ patents)
allowed-tools: Bash
---

# Configure BigQuery Authentication

> **Windows:** use `$HOME\patent-creator-venv\Scripts\python.exe` and `$HOME\patent-creator-venv\Scripts\patent-creator.exe` wherever this page says `~/patent-creator-venv/bin/python` or `~/patent-creator-venv/bin/patent-creator`.

Set up Google Cloud authentication to enable patent search across 100M+ worldwide patents.

## Instructions

1. Verify Google Cloud SDK is installed
2. Run BigQuery authentication setup
3. Authorize browser OAuth flow
4. Verify credentials are saved
5. Test BigQuery connection

## Command

Needs Google's gcloud tool (https://cloud.google.com/sdk/docs/install). Then:

Ask the user to type this in the Claude Code prompt (the `!` runs it in their own terminal session, so the browser sign-in works):

```
! gcloud auth application-default login
```

Then save the project ID (run it yourself in Bash):

```bash
~/patent-creator-venv/bin/patent-creator config set GOOGLE_CLOUD_PROJECT your-project-id
```

Windows: `$HOME\patent-creator-venv\Scripts\patent-creator.exe` in place of `~/patent-creator-venv/bin/patent-creator`. The BigQuery sandbox works without a billing account.

## What This Does

- Opens browser for Google account authorization
- Saves credentials to:
  - Windows: `%APPDATA%\gcloud\application_default_credentials.json`
  - Mac/Linux: `~/.config/gcloud/application_default_credentials.json`
- Verifies access to patents-public-data dataset
- Tests connection with sample query

## Requirements

- Google account (free)
- Google Cloud project (free tier: 1TB queries/month)
- Internet connection

## Verification

After setup, test with:

```bash
~/patent-creator-venv/bin/patent-creator check-bigquery
```

Should return sample patent results.

## Environment Variable

Set your project ID:

Saved with `config set` above; it applies to every new session. An environment variable (`export GOOGLE_CLOUD_PROJECT=...` on Mac/Linux, `$env:GOOGLE_CLOUD_PROJECT="..."` in PowerShell) overrides it for that terminal only.
