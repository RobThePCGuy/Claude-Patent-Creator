"""Consumer-visible verdicts must distinguish passing checks from missing coverage."""

from types import SimpleNamespace

import pytest

from mcp_server.claims_analyzer import ClaimsAnalyzer
from mcp_server.formalities_checker import FormalitiesChecker
from mcp_server.tools.analyzer_tools import register_analyzer_tools
from mcp_server.validation import (
    CheckFormalitiesInput,
    ReviewClaimsInput,
    ReviewSpecificationInput,
    validate_input,
)

SHORT_ABSTRACT = "A mug heats a beverage using a battery-powered resistive heater."
BEVERAGE_CLAIMS = (
    "1. A beverage container comprising a body defining a liquid chamber and a "
    "resistive heater coupled to the body.\n"
    "2. The beverage container of claim 1, wherein the controller activates the "
    "resistive heater in response to the temperature sensor."
)
COMPLETE_SPEC = (
    "BACKGROUND\nExisting devices.\nSUMMARY\nA processing system.\n"
    "BRIEF DESCRIPTION OF DRAWINGS\nFIG. 1 shows the system.\n"
    "DETAILED DESCRIPTION\nFIG. 1 shows system 100 and processor 110."
)


def make_tools(claims_analyzer=ClaimsAnalyzer, formalities_checker=FormalitiesChecker):
    """Run real wrappers and validation without loading a remote MPEP index."""
    registered = {}

    def tool():
        def register(fn):
            registered[fn.__name__] = fn
            return fn

        return register

    register_analyzer_tools(
        mcp=SimpleNamespace(tool=tool),
        mpep_index=SimpleNamespace(search=lambda *a, **k: []),
        ClaimsAnalyzer=claims_analyzer,
        SpecificationAnalyzer=None,
        FormalitiesChecker=formalities_checker,
        log_info=lambda *a, **k: None,
        log_warning=lambda *a, **k: None,
        log_error=lambda *a, **k: None,
        validate_input=validate_input,
        ReviewClaimsInput=ReviewClaimsInput,
        ReviewSpecificationInput=ReviewSpecificationInput,
        CheckFormalitiesInput=CheckFormalitiesInput,
        track_performance=lambda *a, **k: lambda fn: fn,
        log_operation_result=lambda *a, **k: None,
    )
    return registered


def test_short_abstract_cannot_pass_overall():
    result = make_tools()["check_formalities"](abstract=SHORT_ABSTRACT)
    assert result["abstract"]["compliant"] is False
    assert result["overall_compliant"] is False
    assert result["ready_to_file"] is False
    assert result["checks_run"] == ["abstract"]
    skipped = {c["check"]: c["reason"] for c in result["checks_skipped"]}
    assert "no title supplied" in skipped["title"]
    assert "specification" in skipped["sections"]
    assert "specification" in skipped["drawing_references"]
    assert "abstract_title_overlap" in skipped


@pytest.mark.parametrize("missing", ["abstract", "title", "specification", "drawings_present"])
def test_missing_required_input_prevents_readiness(sample_good_abstract, missing):
    inputs = {
        "abstract": sample_good_abstract,
        "title": "Signal Processor",
        "specification": COMPLETE_SPEC,
        "drawings_present": True,
    }
    inputs.pop(missing)
    result = make_tools()["check_formalities"](**inputs)
    assert result["ready_to_file"] is False
    assert result["overall_compliant"] is False
    assert result["checks_skipped"] or result["issues"]


@pytest.mark.parametrize("blank", [None, "", " \n\t"])
def test_empty_formalities_do_not_claim_success(blank):
    result = make_tools()["check_formalities"](abstract=blank, title=blank, specification=blank)
    assert result["ready_to_file"] is False
    assert result["overall_compliant"] is False
    assert result["checks_run"] == []
    assert "incomplete" in result["summary"].lower()
    assert "[OK]" not in result["summary"]


def test_failed_warning_level_check_blocks_complete_input(sample_good_abstract):
    result = make_tools()["check_formalities"](
        abstract=SHORT_ABSTRACT,
        title="Signal Processor",
        specification=COMPLETE_SPEC,
        drawings_present=True,
    )
    assert result["critical_issues"] == 0
    assert result["overall_compliant"] is False
    assert result["ready_to_file"] is False


def test_complete_inputs_can_pass_automated_checks(sample_good_abstract):
    result = make_tools()["check_formalities"](
        abstract=sample_good_abstract,
        title="Signal Processor",
        specification=COMPLETE_SPEC,
        drawings_present=True,
    )
    assert result["overall_compliant"] is True
    assert result["ready_to_file"] is True
    assert result["checks_skipped"] == []
    assert set(result["checks_run"]) == {
        "abstract",
        "title",
        "sections",
        "drawing_references",
        "figure_numeral_coverage",
        "abstract_title_overlap",
    }
    assert "automated" in result["verdict_scope"].lower()


def test_claims_skip_is_up_front_and_not_a_compliance_claim(monkeypatch):
    monkeypatch.delenv("PATENT_ENABLE_ANTECEDENT_CHECK", raising=False)
    result = make_tools()["review_patent_claims"](BEVERAGE_CLAIMS)
    summary = result["summary"]
    assert "compliant" not in summary.lower()
    assert summary.startswith("[INCOMPLETE]")
    assert "[OK]" not in summary
    assert summary.index("antecedent_basis") < summary.index("No issues found")
    assert "PATENT_ENABLE_ANTECEDENT_CHECK=1" in summary
    assert set(result["checks_run"]) == {
        "definiteness",
        "subjective_terms",
        "internal_references",
        "structure",
    }
    assert result["compliance_score_scope"] == "checks_run_only"


def test_enabled_claim_checks_report_actual_coverage(monkeypatch):
    monkeypatch.setenv("PATENT_ENABLE_ANTECEDENT_CHECK", "1")
    result = make_tools()["review_patent_claims"](BEVERAGE_CLAIMS)
    assert "antecedent_basis" in result["checks_run"]
    assert result["checks_skipped"] == []
    assert "compliant" not in result["summary"].lower()


@pytest.mark.parametrize("enabled", ["0", "1"])
def test_unparsed_claims_cannot_claim_checks_ran(monkeypatch, enabled):
    monkeypatch.setenv("PATENT_ENABLE_ANTECEDENT_CHECK", enabled)
    result = make_tools()["review_patent_claims"]("An unnumbered claim comprising a widget.")
    assert result["claim_count"] == 0
    assert result["checks_run"] == []
    assert len(result["checks_skipped"]) == 5
    assert "no numbered claims" in result["summary"].lower()
    assert "[OK]" not in result["summary"]


def test_no_figure_references_does_not_silently_pass_drawing_coverage(sample_good_abstract):
    result = make_tools()["check_formalities"](
        abstract=sample_good_abstract,
        title="Signal Processor",
        specification=COMPLETE_SPEC.replace("FIG. 1", "The drawing"),
        drawings_present=False,
    )
    assert result["ready_to_file"] is False
    skipped = {c["check"]: c["reason"] for c in result["checks_skipped"]}
    assert "no figure references" in skipped["figure_numeral_coverage"]
    assert "no drawings supplied" in skipped["drawings"]
    assert "drawing_references" in result["checks_run"]
    assert "figure_numeral_coverage" not in result["checks_run"]


def test_missing_detailed_description_discloses_numeral_skip():
    result = make_tools()["check_formalities"](specification="FIG. 1 shows a system.")
    skipped = {c["check"]: c["reason"] for c in result["checks_skipped"]}
    assert "detailed description" in skipped["figure_numeral_coverage"]
    assert "figure_numeral_coverage" not in result["checks_run"]


def test_reusing_checker_does_not_keep_previous_coverage(sample_good_abstract):
    checker = FormalitiesChecker()
    checker.check_all_formalities(sample_good_abstract, "Signal Processor", COMPLETE_SPEC, True)
    result = checker.check_all_formalities()
    assert result["checks_run"] == []
    assert result["compliance_summary"]["ready_to_file"] is False


@pytest.mark.parametrize(
    "tool, inputs, count",
    [
        ("review_patent_claims", {"claims_text": BEVERAGE_CLAIMS}, 5),
        ("check_formalities", {"abstract": SHORT_ABSTRACT}, 6),
    ],
)
def test_search_fallback_discloses_no_checks_ran(tool, inputs, count):
    result = make_tools(claims_analyzer=None, formalities_checker=None)[tool](**inputs)
    assert result["analysis_type"] == "mpep_search_only"
    assert result["checks_run"] == []
    assert len(result["checks_skipped"]) == count
    assert all("unavailable" in c["reason"] for c in result["checks_skipped"])


@pytest.mark.parametrize("missing_prerequisite", ["sentence", "title_words"])
def test_unperformed_overlap_comparison_blocks_readiness(
    sample_good_abstract, missing_prerequisite
):
    abstract = (
        sample_good_abstract.replace(".", "")
        if missing_prerequisite == "sentence"
        else sample_good_abstract
    )
    title = "AI" if missing_prerequisite == "title_words" else "Signal Processor"
    result = make_tools()["check_formalities"](
        abstract=abstract,
        title=title,
        specification=COMPLETE_SPEC,
        drawings_present=True,
    )
    assert result["ready_to_file"] is False
    skipped = {c["check"]: c["reason"] for c in result["checks_skipped"]}
    assert "abstract_title_overlap" in skipped
    assert "abstract_title_overlap" not in result["checks_run"]
