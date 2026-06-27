"""Regression tests for plural claim-reference parsing.

Dependent claims are routinely written in the plural — "claims 1 to 5",
"claims 1 and 2" (the standard multiple-dependent form, especially at the
EPO/PCT). The original ``claim \\d+`` pattern only matched the singular
"claim N", so those dependent claims were mislabeled as independent. That
produced wrong independent/dependent counts, false EPO Rule 43(2) issues,
and — in the PCT checker — masked genuine "no independent claim" defects.
"""

from mcp_server.claims_analyzer import ClaimsAnalyzer
from mcp_server.epo_claims_analyzer import EPOClaimsAnalyzer
from mcp_server.pct_formalities_checker import PCTFormalitiesChecker


class TestPluralDependencyUS:
    def test_plural_reference_is_dependent(self):
        text = (
            "1. A widget comprising a frame and a wheel.\n"
            "2. The widget of claim 1, wherein the wheel is round.\n"
            "3. A widget according to claims 1 to 2, further comprising a brake.\n"
            "4. The widget of any one of claims 1 and 3, wherein the brake is hydraulic."
        )
        claims = {c["number"]: c for c in ClaimsAnalyzer()._parse_claims(text)}

        assert claims[1]["is_independent"] is True
        # Singular and both plural forms must register as dependent.
        assert claims[2]["is_independent"] is False and claims[2]["depends_on"] == 1
        assert claims[3]["is_independent"] is False and claims[3]["depends_on"] == 1
        assert claims[4]["is_independent"] is False and claims[4]["depends_on"] == 1

    def test_independent_claim_without_reference_stays_independent(self):
        text = "1. A method comprising receiving data and processing the data."
        claims = ClaimsAnalyzer()._parse_claims(text)
        assert claims[0]["is_independent"] is True
        assert claims[0]["depends_on"] is None


class TestPluralDependencyEPO:
    def test_plural_reference_is_dependent(self):
        text = (
            "1. A device comprising a sensor.\n"
            "2. Device according to claims 1 to 1, characterized by a display."
        )
        claims = EPOClaimsAnalyzer()._parse_claims(text)
        assert claims[0]["is_independent"] is True
        assert claims[1]["is_independent"] is False
        assert claims[1]["depends_on"] == 1


class TestPCTIndependentDetection:
    def test_all_dependent_via_plural_form_is_flagged(self):
        """A claim set where every claim depends on others — expressed with the
        plural form — must still raise the 'no independent claim' defect."""
        spec = (
            "CLAIMS\n"
            "1. The method of claims 2 to 3, wherein A occurs.\n"
            "2. The method of claims 1 and 3, wherein B occurs.\n"
            "3. The method of claims 1 to 2, wherein C occurs."
        )
        checker = PCTFormalitiesChecker()
        checker._check_claims_format(spec)
        assert any("independent" in issue.problem.lower() for issue in checker.issues)

    def test_real_independent_claim_not_flagged(self):
        spec = (
            "CLAIMS\n"
            "1. A method, comprising step A.\n"
            "2. The method of claims 1 to 1, further comprising step B."
        )
        checker = PCTFormalitiesChecker()
        checker._check_claims_format(spec)
        assert not any("independent" in issue.problem.lower() for issue in checker.issues)
