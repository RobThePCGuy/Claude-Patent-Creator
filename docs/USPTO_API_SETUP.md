# USPTO Open Data Portal API Setup

> **Commands on this page** assume `patent-creator` is on your PATH. With the README's install, type `~/patent-creator-venv/bin/patent-creator` instead (Windows PowerShell: `& "$HOME\patent-creator-venv\Scripts\patent-creator.exe"`). Keys and settings are easiest to save with `patent-creator config set KEY VALUE`; an environment variable overrides a saved value.

Complete guide for setting up the USPTO Open Data Portal API to access 11M+ patents in real-time.

## Overview

The USPTO API provides live access to the patent database, allowing you to search recent patents and retrieve specific patents by number without downloading the full corpus.

## Why Use the USPTO API?

- **Real-time data**: Access patents granted in the last few days
- **No download**: Search 11M+ patents without the 15GB local corpus
- **Specific lookups**: Get patents by number (e.g., US11234567)
- **Always current**: Live connection to USPTO's database

## Setup Steps

### 1. Create USPTO Account

1. Go to [data.uspto.gov/myodp](https://data.uspto.gov/myodp)
2. Click "I don't have a MyUSPTO account"
3. Complete registration
4. Verify your email address

### 2. Verify with ID.me

1. Return to [data.uspto.gov/myodp](https://data.uspto.gov/myodp)
2. Click "Verify MyUSPTO account with ID.me"
3. Complete identity verification
   - **US users**: Standard online verification
   - **International users**: May require video call verification

### 3. Generate API Key

1. Log in to [data.uspto.gov/myodp](https://data.uspto.gov/myodp)
2. Click "Generate New API Key"
3. Copy your API key (save it securely)

### 4. Set Environment Variable

Set the `USPTO_API_KEY` environment variable with your key.

**See [ENVIRONMENT_VARIABLES.md](ENVIRONMENT_VARIABLES.md) for platform-specific instructions.**

Quick reference:

**Windows:**
```powershell
[System.Environment]::SetEnvironmentVariable('USPTO_API_KEY', 'your_key_here', 'User')
```

**Linux/macOS:**
```bash
echo 'export USPTO_API_KEY="your_key_here"' >> ~/.bashrc
source ~/.bashrc
```

### 5. Verify Connection

Restart Claude Code, then ask it: "Check the USPTO API status". That runs the `check_uspto_api_status` tool, which reports whether the key is set and whether the USPTO answered. (`patent-creator status` checks the local install only, not the USPTO.)

## Usage

Once configured, the USPTO API is used automatically for:
- Recent patent lookups
- Patent number queries
- Live database searches

## Rate Limits

- **~100 requests per minute** (USPTO enforced)
- Spread out large batch operations
- Local corpus has no rate limits (alternative for bulk searches)

## Comparison with Other Options

| Feature | USPTO API | PatentsView API | Local Corpus |
|---------|-----------|-----------------|--------------|
| Patents | 11M+ (live) | US patents (current) | 9.2M (1976-present) |
| Setup | 5 min (ID.me) | 2 min | ~27 hrs (indexing) |
| Storage | None | None | 15-20GB |
| Best For | Recent patents | Advanced filtering | Semantic search |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| API key not detected | Verify environment variable: `echo $USPTO_API_KEY` (Linux/Mac) or `$env:USPTO_API_KEY` (Windows) |
| `403 Forbidden` | API key invalid. Regenerate at data.uspto.gov/myodp |
| `429 Rate Limit` | Slow down requests. Wait before retrying. |
| ID.me verification fails | Contact USPTO support or try video verification |

## Support

- **USPTO Support**: https://developer.uspto.gov/
- **MyUSPTO Account**: https://myaccount.uspto.gov/
- **ID.me Help**: https://help.id.me/

## Notes

- **International users**: ID.me verification may require additional steps
- **Privacy**: Queries are sent to USPTO servers
- **Alternative**: BigQuery patent search covers 100M+ patents worldwide; set `GOOGLE_CLOUD_PROJECT` to use it
