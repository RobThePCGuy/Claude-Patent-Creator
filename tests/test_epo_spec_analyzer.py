"""Tests for EPO Specification Analyzer (Art. 83 EPC)."""

from mcp_server.epo_specification_analyzer import EPOSpecificationAnalyzer


class TestRule42Sections:
    """Rule 42 EPC: required description sections."""

    def test_all_sections_present_no_issues(self, sample_epo_specification):
        analyzer = EPOSpecificationAnalyzer()
        claims = [{"number": 1, "text": "A data processing system.", "is_independent": True, "depends_on": None}]
        result = analyzer.analyze(claims, sample_epo_specification)
        section_issues = [i for i in result["issues"] if i["type"] == "section_missing"]
        assert len(section_issues) == 0

    def test_missing_sections_flagged(self):
        analyzer = EPOSpecificationAnalyzer()
        claims = [{"number": 1, "text": "A data processing system.", "is_independent": True, "depends_on": None}]
        result = analyzer.analyze(claims, "This is a short specification.")
        section_issues = [i for i in result["issues"] if i["type"] == "section_missing"]
        assert len(section_issues) > 0

    def test_missing_section_cites_rule_42(self):
        analyzer = EPOSpecificationAnalyzer()
        claims = [{"number": 1, "text": "A system.", "is_independent": True, "depends_on": None}]
        result = analyzer.analyze(claims, "Brief text only.")
        section_issues = [i for i in result["issues"] if i["type"] == "section_missing"]
        assert any("Rule 42" in i["legal_ref"] for i in section_issues)

