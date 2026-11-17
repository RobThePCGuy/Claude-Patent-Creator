"""Tests for EPO Claims Analyzer (Art. 84 EPC)."""

from mcp_server.epo_claims_analyzer import EPOClaimsAnalyzer


class TestTwoPartForm:
    """Rule 43(1) EPC: two-part form detection."""

    def test_present_no_issue(self, sample_claims_two_part):
        analyzer = EPOClaimsAnalyzer()
        result = analyzer.analyze(sample_claims_two_part)
        issues = [i for i in result["issues"] if i["type"] == "two_part_form"]
        assert len(issues) == 0

    def test_absent_flagged(self, sample_claims_no_two_part):
        analyzer = EPOClaimsAnalyzer()
        result = analyzer.analyze(sample_claims_no_two_part)
        issues = [i for i in result["issues"] if i["type"] == "two_part_form"]
        assert len(issues) > 0

    def test_absent_cites_rule_43(self, sample_claims_no_two_part):
        analyzer = EPOClaimsAnalyzer()
        result = analyzer.analyze(sample_claims_no_two_part)
        issues = [i for i in result["issues"] if i["type"] == "two_part_form"]
        assert "Rule 43" in issues[0]["legal_ref"]


class TestConciseness:
    """Art. 84 EPC: conciseness (claims fees at 16+)."""

    def test_many_claims_triggers_fee_warning(self):
        claims = "\n".join([f"{i+1}. A method step {i+1}." for i in range(20)])
        analyzer = EPOClaimsAnalyzer()
        result = analyzer.analyze(claims)
        fee_issues = [i for i in result["issues"] if i["type"] == "conciseness" and "fee" in i.get("problem", "").lower()]
        assert len(fee_issues) >= 1


