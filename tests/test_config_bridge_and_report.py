"""Two gaps found by driving the MCP server for real (patent campaign):

1. config.apply_config_to_env() was documented as running at server startup
   but nothing ever called it -- config-file settings (GOOGLE_CLOUD_PROJECT,
   PATENT_ENABLE_ANTECEDENT_CHECK, ...) never reached the MCP server.
2. The analyzer tool layer rebuilds the claims report field-by-field and
   silently dropped checks_skipped, undoing the honesty guarantee of #47 at
   the MCP boundary.

server.py uses flat imports and cannot be imported as a package module in
tests, so those assertions read source text.
"""

from pathlib import Path

MCP_SERVER_DIR = Path(__file__).parent.parent / "mcp_server"


def test_server_main_bridges_config_into_environment():
    src = (MCP_SERVER_DIR / "server.py").read_text(encoding="utf-8")
    main_body = src.split("def main():", 1)[1]
    assert "apply_config_to_env(" in main_body


def test_analyzer_tool_passes_checks_skipped_through():
    src = (MCP_SERVER_DIR / "tools" / "analyzer_tools.py").read_text(encoding="utf-8")
    assert "checks_skipped" in src


def test_claims_analyzer_report_still_provides_checks_skipped():
    from mcp_server.claims_analyzer import ClaimsAnalyzer

    report = ClaimsAnalyzer().analyze_claims("1. An apparatus comprising: a widget.")
    assert "checks_skipped" in report
