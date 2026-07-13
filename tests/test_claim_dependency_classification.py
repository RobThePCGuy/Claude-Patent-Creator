"""Independent/dependent claim classification (issue #65).

The old classifier called a claim dependent if "claim N" appeared ANYWHERE
in its body. Two real failure modes:

1. Working-copy claim files interleave commentary between claims; the
   parser swallows commentary into the preceding claim's body, so an
   independent claim followed by commentary that mentions another claim
   gets misclassified as dependent. Observed on a real 17-claim set:
   3 independent claims by inspection, analyzer reported 1.

2. A genuine dependency is recited as a reference phrase in the claim's
   preamble ("The method of claim 1, wherein..."), which is the legal form
   (37 CFR 1.75(c)) — not as a bare mention anywhere.
"""

import pytest

from mcp_server.claims_analyzer import ClaimsAnalyzer


@pytest.fixture
def analyzer():
    return ClaimsAnalyzer()


def _parse(analyzer, text):
    return {c["number"]: c for c in analyzer._parse_claims(text)}


def test_dependent_forms_are_recognized(analyzer):
    text = (
        "1. A method comprising a step.\n"
        "2. The method of claim 1, wherein the step repeats.\n"
        "3. The method according to claim 2, wherein the step halts.\n"
        "4. The method as claimed in claim 1, further comprising logging.\n"
        "5. The method of any one of claims 1 to 4, wherein logging is disabled.\n"
    )
    claims = _parse(analyzer, text)
    assert claims[1]["is_independent"]
    for n in (2, 3, 4, 5):
        assert not claims[n]["is_independent"], f"claim {n} should be dependent"
    assert claims[2]["depends_on"] == 1
    assert claims[5]["depends_on"] == 1


def test_independent_claim_followed_by_commentary_stays_independent(analyzer):
    """The exact #65 failure: commentary mentioning other claims gets
    swallowed into the preceding claim's body."""
    text = (
        "1. A method for reconciling marks, comprising refusing a relocation.\n"
        "\n"
        "   [Commentary: this walls off claim 14 of US7747943B2.]\n"
        "\n"
        "8. A computer-implemented method for managing dismissals, comprising\n"
        "   storing an embedding vector.\n"
        "\n"
        "   [Load-bearing vs art: pair of snapshots; compare claims 1 and 3\n"
        "   of the Amazon patent.]\n"
        "\n"
        "14. A computer-implemented method for controlling iterative text\n"
        "   generation under a first budget and a second budget.\n"
    )
    claims = _parse(analyzer, text)
    assert claims[1]["is_independent"]
    assert claims[8]["is_independent"], "commentary must not make claim 8 dependent"
    assert claims[14]["is_independent"]


def test_body_mention_of_claim_terminology_is_not_a_dependency(analyzer):
    """A claim about claims (e.g. patent-drafting software) may use the
    word 'claim' in its own limitations without depending on anything."""
    text = (
        "1. A method comprising displaying claims 1 to 20 of a patent "
        "document on a screen.\n"
    )
    claims = _parse(analyzer, text)
    assert claims[1]["is_independent"]


def test_report_counts_reflect_classification(analyzer):
    text = (
        "1. A method comprising a step.\n"
        "2. The method of claim 1, wherein the step repeats.\n"
        "8. A system comprising a processor.\n"
    )
    report = analyzer.analyze_claims(text)
    assert report["claim_count"] == 3
    assert report["independent_count"] == 2
    assert report["dependent_count"] == 1
