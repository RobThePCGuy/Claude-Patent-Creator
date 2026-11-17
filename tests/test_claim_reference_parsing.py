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


class TestMultipleDependentParents:
    TEXT = (
        "1. A widget comprising a frame with a handle.\n"
        "2. A widget comprising a wheel with a hub.\n"
        "3. The widget of any one of claims 1 or 2, wherein the frame is steel.\n"
        "4. The widget of claims 1 to 3, further comprising a brake.\n"
        "5. The widget of claims 1, 2 and 4, wherein the brake is hydraulic."
    )

    def test_us_parser_keeps_every_parent(self):
        claims = {c["number"]: c for c in ClaimsAnalyzer()._parse_claims(self.TEXT)}
        assert claims[3]["depends_on"] == 1 and claims[3]["depends_on_all"] == [1, 2]
        assert claims[4]["depends_on_all"] == [1, 2, 3]
        assert claims[5]["depends_on_all"] == [1, 2, 4]
        assert claims[1]["depends_on_all"] == []

    def test_epo_parser_keeps_every_parent(self):
        claims = {c["number"]: c for c in EPOClaimsAnalyzer()._parse_claims(self.TEXT)}
        assert claims[3]["depends_on_all"] == [1, 2]
        assert claims[4]["depends_on_all"] == [1, 2, 3]

    def test_unsupported_non_first_parent_flags_the_dependent(self):
        from mcp_server.analyzer_base import unsupported_through_chain

        claims = ClaimsAnalyzer()._parse_claims(self.TEXT)
        # Only claim 2 (the second alternative of claim 3) lacks support.
        assert unsupported_through_chain(claims, {2}) == {2, 3, 4, 5}
        assert unsupported_through_chain(claims, set()) == set()

    def test_antecedent_basis_must_hold_under_each_parent(self, monkeypatch):
        monkeypatch.setenv("PATENT_ENABLE_ANTECEDENT_CHECK", "1")
        result = ClaimsAnalyzer().analyze_claims(self.TEXT)
        terms = {i["term"] for i in result["issues"] if i["claim"] == 3}
        # "the frame" has basis in claim 1 but not under the claim-2 alternative.
        assert "the frame" in terms

    def test_antecedent_basis_found_in_every_parent_is_accepted(self, monkeypatch):
        monkeypatch.setenv("PATENT_ENABLE_ANTECEDENT_CHECK", "1")
        text = (
            "1. A widget comprising a frame with a handle.\n"
            "2. A widget comprising a frame with a hub.\n"
            "3. The widget of claims 1 or 2, wherein the frame is steel."
        )
        result = ClaimsAnalyzer().analyze_claims(text)
        assert not [i for i in result["issues"] if i["claim"] == 3]


    def test_measurement_after_reference_is_not_a_parent(self):
        text = (
            "1. A widget comprising a frame with a handle.\n"
            "2. A widget comprising a wheel with a hub.\n"
            "3. The widget of claim 1, 2 mm thick, wherein the frame is steel.\n"
            "4. The widget of claim 1, 2.5 mm wide, wherein the frame is steel.\n"
            "5. The widget of claims 1-3 cm long, wherein the frame is steel."
        )
        for parser in (ClaimsAnalyzer()._parse_claims, EPOClaimsAnalyzer()._parse_claims):
            claims = {c["number"]: c for c in parser(text)}
            assert claims[3]["depends_on_all"] == [1]
            assert claims[4]["depends_on_all"] == [1]
            assert claims[5]["depends_on_all"] == [1]

    def test_every_multiple_dependent_form_keeps_all_parents(self):
        forms = {
            "of claim 1 or claim 2, wherein the frame is steel": [1, 2],
            "of claims 1 or 2 configured to detect light": [1, 2],
            "of claims 1, 2 or 3, wherein the frame is steel": [1, 2, 3],
            "of any one of claims 1-3.": [1, 2, 3],
            "according to claims 1 to 3 characterised in that the frame is steel": [1, 2, 3],
            "of claim 1, 2 or 3 mm thick": [1],
            "of claim 1, 2 in thickness": [1],
            "of claims 1 or 2 in combination with a handle": [1, 2],
            "of claims 1 or 2, 3 mm thick": [1, 2],
            "of claim 1, 3D printed from polymer": [1],
            "of claim 1, 20mm thick": [1],
            "of claim 1, 20th order filter": [1],
            "of claim 1, 3/4 inch thick": [1],
            "of claim 1, 3-D printed from polymer": [1],
            "of claim 1-claim 3, wherein": [1, 2, 3],
            "of claim 1-Claim 3, wherein": [1, 2, 3],
            "of claim 1, 2 or more of the sensors being mounted": [1],
            "of claim 1, 3 of the sensors being mounted": [1],
            "of claim 1, 2 adjacent sensors sharing a housing": [1],
            "of claim 1, 2 to 4 adjacent sensors sharing a housing": [1],
            "of claim 1, 2 or 3 sensors being mounted on the frame": [1],
            "of claims 1, 2 to 3, wherein": [1, 2, 3],
            "of claims 1, 2, and 3, wherein": [1, 2, 3],
            "of claim 1 \u2014 wherein the frame is steel": [1],
            "of claim 1 - wherein the frame is steel": [1],
            "of claims 1\u20113.": [1, 2, 3],
            "of claims 1\u20143.": [1, 2, 3],
        }
        for tail, parents in forms.items():
            text = "1. A widget.\n2. A widget.\n3. A widget.\n4. The widget " + tail
            for parser in (ClaimsAnalyzer()._parse_claims, EPOClaimsAnalyzer()._parse_claims):
                claim = {c["number"]: c for c in parser(text)}[4]
                assert claim["depends_on_all"] == parents, tail

    def test_epo_prose_mention_of_claims_is_not_a_dependency(self):
        text = "1. A frame.\n2. A wheel.\n3. A processor comprising: a memory storing the text of claims 1 or 2; and a display."
        claim = {c["number"]: c for c in EPOClaimsAnalyzer()._parse_claims(text)}[3]
        assert claim["is_independent"] is True and claim["depends_on_all"] == []

    def test_ratio_in_opening_keeps_the_reference(self):
        text = (
            "1. A 2:1 multiplexer comprising an input and an output.\n"
            "2. The 2:1 multiplexer according to claim 1, wherein the output is buffered."
        )
        for parser in (ClaimsAnalyzer()._parse_claims, EPOClaimsAnalyzer()._parse_claims):
            claim = {c["number"]: c for c in parser(text)}[2]
            assert claim["is_independent"] is False and claim["depends_on_all"] == [1]


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
