"""The claims report must disclose checks that were skipped.

Antecedent-basis checking is opt-in (high false-positive rate, see
claims_analyzer.py), which is a defensible default — but a report that says
"[OK] All claims are compliant" while silently skipping its headline check
gives false assurance. The report must name skipped checks and how to
enable them.
"""

import pytest

from mcp_server.claims_analyzer import ClaimsAnalyzer

FLAWED_CLAIM = "1. An apparatus comprising: the widget attached to said flange."


@pytest.fixture
def analyzer():
    return ClaimsAnalyzer()


def test_report_discloses_skipped_antecedent_check(analyzer, monkeypatch):
    monkeypatch.delenv("PATENT_ENABLE_ANTECEDENT_CHECK", raising=False)

    report = analyzer.analyze_claims(FLAWED_CLAIM)

    skipped = report["checks_skipped"]
    assert any(c["check"] == "antecedent_basis" for c in skipped)
    assert any("PATENT_ENABLE_ANTECEDENT_CHECK" in c["enable_with"] for c in skipped)
    # The summary must not read as a clean bill of health.
    assert "skipped" in report["summary"].lower()
    assert "PATENT_ENABLE_ANTECEDENT_CHECK" in report["summary"]


def test_no_disclosure_when_check_enabled(analyzer, monkeypatch):
    monkeypatch.setenv("PATENT_ENABLE_ANTECEDENT_CHECK", "1")

    report = analyzer.analyze_claims(FLAWED_CLAIM)

    assert report["checks_skipped"] == []
    assert "skipped" not in report["summary"].lower()
    # And the enabled check actually fires on the flawed claim.
    assert report["issues_by_type"].get("antecedent_basis", 0) >= 1


def test_clean_claims_with_all_checks_enabled_still_report_ok(analyzer, monkeypatch):
    monkeypatch.setenv("PATENT_ENABLE_ANTECEDENT_CHECK", "1")

    report = analyzer.analyze_claims(
        "1. An apparatus comprising: a widget; and a flange attached to the widget."
    )

    assert report["total_issues"] == 0
    assert report["summary"].startswith("[OK]")
