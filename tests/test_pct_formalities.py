"""Tests for PCT Formalities Checker (PCT Rules 5-12)."""

from mcp_server.pct_formalities_checker import PCTFormalitiesChecker


class TestAbstract:
    """PCT Rule 8: abstract requirements."""

    def test_long_abstract_flagged(self):
        checker = PCTFormalitiesChecker()
        long_abstract = " ".join(["word"] * 200) + "."
        result = checker.check_all_formalities(abstract=long_abstract)
        issues = [i for i in result["issues"] if i["section"] == "abstract"]
        assert any("150" in i.get("problem", "") or "exceed" in i.get("problem", "").lower() or "long" in i.get("problem", "").lower() for i in issues)

    def test_abstract_cites_rule_8(self):
        checker = PCTFormalitiesChecker()
        result = checker.check_all_formalities(abstract=" ".join(["word"] * 200))
        issues = [i for i in result["issues"] if i["section"] == "abstract"]
        assert any("Rule 8" in i["legal_ref"] for i in issues)


class TestDescription:
    """PCT Rule 5: description requirements."""

    def test_all_elements_present_no_issues(self):
        checker = PCTFormalitiesChecker()
        good_spec = """
TECHNICAL FIELD
The invention relates to data processing.

BACKGROUND ART
Prior systems are slow.

DISCLOSURE OF THE INVENTION
A faster method is provided.

BRIEF DESCRIPTION OF DRAWINGS
FIG. 1 shows the system.

DETAILED DESCRIPTION
The system processes data efficiently.

BEST MODE
The preferred embodiment uses a GPU.
"""
        result = checker.check_all_formalities(specification=good_spec)
        desc_issues = [i for i in result["issues"] if i["section"] == "description"]
        assert len(desc_issues) == 0

    def test_missing_elements_flagged(self):
        checker = PCTFormalitiesChecker()
        result = checker.check_all_formalities(specification="This is a brief spec about data.")
        desc_issues = [i for i in result["issues"] if i["section"] == "description"]
        assert len(desc_issues) > 0

    def test_missing_element_cites_rule_5(self):
        checker = PCTFormalitiesChecker()
        result = checker.check_all_formalities(specification="This is a brief spec.")
        desc_issues = [i for i in result["issues"] if i["section"] == "description"]
        assert any("Rule 5" in i["legal_ref"] for i in desc_issues)


class TestOutputFormat:
    def test_uses_legal_ref_key(self):
        checker = PCTFormalitiesChecker()
        result = checker.check_all_formalities(abstract="Short.")
        for issue in result["issues"]:
            assert "legal_ref" in issue


def test_abstract_figure_is_a_manual_check_not_a_defect():
    """The abstract figure is designated on the request form (PCT Rules
    3.3(a)(iii) and 8.2), which the checker never sees."""
    result = PCTFormalitiesChecker().check_all_formalities(
        abstract="A charger couples power through a coil 12 to a receiver 14 in an implant. " * 3,
        drawings_present=True,
    )
    flat = str(result)
    assert "Abstract does not indicate which figure" not in flat
    skipped = [c["check"] for c in result["checks_skipped"]]
    assert "abstract figure designation" in skipped
