---
name: development-assistant
description: Extend MCP tools, analyzers, configuration and plugin commands using the current repository APIs.
---

# Development Assistant

Work in a source checkout. Use the **Testing Assistant** skill for development installation, pytest and lint commands. Beginner installs use pip from GitHub and the home-folder venv instead.

## MCP tools

Tool groups live in `mcp_server/tools/` and are registered by `mcp_server/server.py`. Follow `register_analyzer_tools` in `mcp_server/tools/analyzer_tools.py` for dependency injection and registration. Add inputs to `mcp_server/validation.py` when appropriate.

`validate_input` is a function called inside the tool body. `track_performance` is a decorator factory that takes an operation name. This complete registration example uses both:

```python
from mcp_server.monitoring import track_performance
from mcp_server.validation import ReviewClaimsInput, validate_input


def register_example_tools(mcp):
    @mcp.tool()
    @track_performance("example_claim_length")
    def example_claim_length(claims_text: str) -> dict:
        """Count characters in validated claims text; this is not a legal review."""
        validated = validate_input(ReviewClaimsInput, claims_text=claims_text)
        return {"characters": len(validated.claims_text)}
```

Register a new group from the server alongside existing groups. Avoid duplicate tool names. Use named operations such as `@track_performance("example_claim_length")` for other monitored functions too; `OperationTimer` in `mcp_server/monitoring.py` measures individual steps.

## Analyzers

`BaseAnalyzer` requires both `analyze` and `_issue_to_dict`. This small example checks only whether content is empty:

```python
from dataclasses import asdict

from mcp_server.analyzer_base import BaseAnalyzer, BaseIssue


class EmptyContentAnalyzer(BaseAnalyzer):
    def analyze(self, content: str) -> dict:
        self.issues = []
        if not content.strip():
            self.issues.append(BaseIssue(
                severity="IMPORTANT",
                problem="Content is empty",
                fix="Supply the content to review",
                legal_ref="Not a legal assessment",
            ))
        return {
            "issues": [self._issue_to_dict(issue) for issue in self.issues],
            "checks_performed": ["nonempty content"],
        }

    def _issue_to_dict(self, issue: BaseIssue) -> dict:
        return asdict(issue)
```

Reset issues on each invocation, serialize actual findings, and report only checks performed. There is no `_generate_recommendations` helper on `BaseAnalyzer`; produce recommendations from issue fixes if your report needs them.

## Configuration

`mcp_server/config.py` defines `Option` entries in `OPTIONS`, validates values and stores settings in a JSON config file. It does not expose `AppSettings` or `get_settings`.

To read an existing option:

```python
from mcp_server.config import get_effective

log_level, source = get_effective("PATENT_LOG_LEVEL")
```

For a new option, add an `Option` to `OPTIONS`, read it with `get_effective`, and test validation plus environment/file/default precedence. For code that reads environment variables at import time, call `apply_config_to_env()` first, as the CLI and server do. Never log secret values.

Python code printing user-facing commands must use `mcp_server.cli_command.render`, `installed_cli` or `python_command` so instructions target the active installation and platform.

## Plugin commands and repository map

Create new command Markdown files under the root `commands/` directory. For example, a new `commands/your-command.md` should have `description` frontmatter followed by workflow instructions. A `.claude/commands/` file would be local to a project rather than part of this plugin.

| Work | Existing implementation |
|---|---|
| Tool registration | `mcp_server/server.py`, `mcp_server/tools/analyzer_tools.py` |
| Claims analysis | `mcp_server/claims_analyzer.py`, `mcp_server/analyzer_base.py` |
| Legal-reference retrieval | `mcp_server/mpep_search.py` |
| BigQuery | `mcp_server/bigquery_search.py` |
| Configuration and storage | `mcp_server/config.py`, `mcp_server/data_paths.py` |
| GPU selection | `mcp_server/hardware_detect.py` |
| Monitoring and logging | `mcp_server/monitoring.py`, `mcp_server/logging_config.py` |
| Automated regression tests | `tests/` |
| Manual diagnostics | `scripts/` |
| Plugin packaging | `.claude-plugin/plugin.json`, `commands/`, `skills/`, `agents/` |

Read the current implementation before extending it, write tests for observable behavior, run pytest and Ruff, and document limitations alongside results.
