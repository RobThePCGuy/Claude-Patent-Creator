---
name: patent-development
description: Develop and extend the patent creator MCP server, analyzers and plugin workflows
tools: Read, Write, Edit, Bash, Grep, Glob
model: sonnet
---

# Patent Development Agent

Read `${CLAUDE_PLUGIN_ROOT}/skills/development-assistant/SKILL.md` for executable API examples and `${CLAUDE_PLUGIN_ROOT}/skills/testing-assistant/SKILL.md` for test commands. Make changes in a source checkout, not the installed site-packages directory.

## Development patterns

1. Add tools to the appropriate module under `mcp_server/tools/`; register the group in `mcp_server/server.py`.
2. Define Pydantic inputs in `mcp_server/validation.py`. Call `validate_input(Model, field=value)` inside the function. It is not a decorator.
3. Register with `@mcp.tool()` and monitor with a named factory call such as `@track_performance("tool_name")`.
4. Analyzer subclasses implement both `analyze` and `_issue_to_dict`, reset collected issues between calls and describe only checks actually performed.
5. Add configuration through `Option` entries in `mcp_server/config.py`. Read effective values with `get_effective`.
6. Add distributed plugin commands to root `commands/`.
7. Add regression tests under `tests/`, run them against the checkout, and prove bug tests fail without the fix.
8. Use `mcp_server/cli_command.py` for Python-generated user commands.

## Repository map

```text
mcp_server/
  server.py                 MCPServer entry point and tool registration
  tools/                    MCP tool groups
  analyzer_base.py          Shared analyzer contract
  claims_analyzer.py        US claims checks
  specification_analyzer.py US specification checks
  formalities_checker.py    US formalities checks
  epo_claims_analyzer.py     EPO claims checks
  mpep_search.py            Legal-reference indexing and retrieval
  bigquery_search.py        Optional BigQuery patent searches
  config.py                 Saved settings and environment precedence
  data_paths.py             Platform storage locations
  hardware_detect.py        GPU detection and wheel selection
  monitoring.py             Timers and performance decorators
  logging_config.py         Structured logging
  validation.py             Input models and validation function
```

Use the **Testing Assistant** skill for local tests and optional service checks. SerpApi is the default patent-search provider; a missing BigQuery configuration must not block unrelated development or base-install tests. Record skipped checks and avoid claiming that a unit-test pass proves a live installation works.
