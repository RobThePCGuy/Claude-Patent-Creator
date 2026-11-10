"""Safety-critical plugin instructions and the configuration lifecycle they rely on."""

import importlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Direct calls and tools required by the MCP-backed skills each agent invokes.
MCP_AGENTS = {
    "epo-patent-analyzer": {"review_epo_claims", "review_epo_specification", "check_epo_formalities", "search_patent_law", "search_mpep"},
    "epo-patent-drafter": {"search_patent_law", "search_mpep", "search_patents_google", "search_patents_bigquery", "search_patents_by_cpc_bigquery", "get_epo_patent", "get_epo_patent_family", "check_epo_api_status", "review_epo_claims", "review_epo_specification", "check_epo_formalities", "create_block_diagram", "create_flowchart", "render_diagram"},
    "mpep-expert": {"get_mpep_section"},
    "mpep-researcher": {"search_mpep", "get_mpep_section"},
    "patent-analyzer": {"review_patent_claims", "review_specification", "check_formalities", "search_mpep", "get_mpep_section"},
    "patent-illustrator": {"add_diagram_references", "get_diagram_templates"},
    "patent-search-specialist": {"search_patents_google", "search_patents_bigquery", "get_patent_bigquery", "get_patents_bigquery", "search_patents_by_cpc_bigquery", "search_mpep"},
    "pct-application-specialist": {"search_patent_law", "search_mpep", "review_epo_claims", "review_epo_specification", "check_epo_formalities"},
}


@pytest.mark.parametrize("agent,required", MCP_AGENTS.items())
def test_mcp_agent_does_not_exclude_its_required_tools(agent, required):
    frontmatter = (ROOT / "agents" / f"{agent}.md").read_text().split("---", 2)[1]
    allowlist = re.search(r"^tools:\s*(.+)$", frontmatter, re.MULTILINE)
    if allowlist is None:
        return  # Documented inheritance of the connected session's tools.
    allowed = {entry.strip() for entry in allowlist[1].split(",")}
    for tool in required:
        assert any(entry.startswith("mcp__") and (entry.endswith(f"__{tool}") or entry.endswith("__*"))
                   for entry in allowed), f"{agent} excludes {tool}"


def test_campaign_requires_restart_and_result_evidence_before_verification():
    skill = (ROOT / "skills/patent-application-creator/SKILL.md").read_text()
    loop = skill.split("## Phase 4 —", 1)[1].split("**Verification stamps", 1)[0]
    assert loop.index("PATENT_ENABLE_ANTECEDENT_CHECK") < loop.index("Restart Claude Code")
    assert loop.index("Restart Claude Code") < loop.index("`review_patent_claims`")
    assert "`checks_run` MUST include `antecedent_basis`" in loop
    assert "If absent, report the check as skipped" in loop
    assert "stop the verification loop" in loop


def test_saved_antecedent_setting_needs_new_process_and_actual_result(tmp_path, monkeypatch):
    cfg = importlib.import_module("mcp_server.config")
    claims_class = importlib.import_module("mcp_server.claims_analyzer").ClaimsAnalyzer
    monkeypatch.setenv("PATENT_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("PATENT_ENABLE_ANTECEDENT_CHECK", raising=False)
    cfg.apply_config_to_env()  # Existing server process started before enabling.
    claims = "1. An apparatus comprising: the widget attached to said flange."
    cfg.save_value("PATENT_ENABLE_ANTECEDENT_CHECK", "1")
    old_result = claims_class().analyze_claims(claims)
    assert "antecedent_basis" not in old_result["checks_run"]
    assert any(c["check"] == "antecedent_basis" for c in old_result["checks_skipped"])

    # Same startup config bridge as server.main, in a newly started process.
    code = (
        "import json; from mcp_server.config import apply_config_to_env; "
        "from mcp_server.claims_analyzer import ClaimsAnalyzer; "
        "apply_config_to_env(); "
        f"print(json.dumps(ClaimsAnalyzer().analyze_claims({claims!r})))"
    )
    restarted = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                               capture_output=True, text=True, check=True, timeout=15)
    new_result = json.loads(restarted.stdout)
    assert "antecedent_basis" in new_result["checks_run"]
    assert new_result["checks_skipped"] == []
    assert new_result["issues_by_type"]["antecedent_basis"] > 0
