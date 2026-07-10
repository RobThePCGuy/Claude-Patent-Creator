# Setting Environment Variables

This guide shows how to set environment variables for API keys on different platforms.

> **Easier: use the built-in config command.** Instead of editing environment
> variables you can store settings in a config file the server reads:
>
> ```bash
> patent-creator config list                 # every setting, its value, and source
> patent-creator config set GOOGLE_CLOUD_PROJECT my-project-id
> patent-creator config set PATENT_BIGQUERY_MAX_BYTES_BILLED 268435456000   # ~250 GiB
> patent-creator config path                 # where the file lives
> ```
>
> Resolution order is **environment variable > config file > default**, so an
> explicitly-set environment variable always wins. The settings below can all be
> managed this way, and `config` works even before the rest of the stack is installed.

## Windows (PowerShell)

Set permanently for your user account:

```powershell
[System.Environment]::SetEnvironmentVariable('VARIABLE_NAME', 'your_value_here', 'User')
```

**Verify:**
```powershell
$env:VARIABLE_NAME
```

**Note:** Restart any open terminals/applications for changes to take effect.

## Linux/macOS

### Bash

Add to `~/.bashrc` for persistence:

```bash
echo 'export VARIABLE_NAME="your_value_here"' >> ~/.bashrc
source ~/.bashrc
```

### Zsh

Add to `~/.zshrc` for persistence:

```bash
echo 'export VARIABLE_NAME="your_value_here"' >> ~/.zshrc
source ~/.zshrc
```

### Fish

Add to Fish config for persistence:

```bash
echo 'set -gx VARIABLE_NAME "your_value_here"' >> ~/.config/fish/config.fish
source ~/.config/fish/config.fish
```

### Temporary (Current Session Only)

```bash
export VARIABLE_NAME="your_value_here"
```

## Verify Setup

Check that the variable is set:

```bash
# Linux/macOS
echo $VARIABLE_NAME

# Windows PowerShell
$env:VARIABLE_NAME
```

## Common Variables for This Project

- `GOOGLE_CLOUD_PROJECT` - GCP project for BigQuery patent search billing
- `USPTO_API_KEY` - USPTO Open Data Portal API key (optional)
- `EPO_OPS_KEY` / `EPO_OPS_SECRET` - EPO OPS API credentials (optional)
- `HYDE_BACKEND` - Set to `api` to use Anthropic/OpenAI for HyDE query expansion
- `PATENT_BIGQUERY_MAX_BYTES_BILLED` - Override the per-query BigQuery cost ceiling, in bytes
  (default: 25 GiB). A broad keyword search across the full patents corpus can scan several
  hundred GiB. When the estimated scan exceeds this ceiling, the search **fails fast with an
  actionable error** (estimated size, suggested ceiling, and approximate cost) via a free
  dry-run estimate, instead of running an expensive query or appearing to hang. To run such a
  search, raise the ceiling (e.g. `429496729600` for ~400 GiB, roughly $2/query at on-demand
  pricing) or narrow the search with `country` / `start_year` / `end_year` filters or more
  specific keywords.
