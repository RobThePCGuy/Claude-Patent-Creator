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
    # Still not ready: everything but the abstract was skipped.
    assert result["overall_compliant"] is False
    assert result["ready_to_file"] is False
    skipped = {c["check"]: c["reason"] for c in result["checks_skipped"]}
    assert "title" in skipped
    assert "sections" in skipped
    assert "drawing_references" in skipped
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
    assert "[OK]" not in result["summary"]


LONG_ABSTRACT = " ".join(["word"] * 160) + "."


def test_failed_warning_level_check_blocks_complete_input(sample_good_abstract):
    # 37 CFR 1.72(b) caps the abstract at 150 words; over it fails at WARNING level.
    result = make_tools()["check_formalities"](
        abstract=LONG_ABSTRACT,
        title="Signal Processor",
        specification=COMPLETE_SPEC,
        drawings_present=True,
    )
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


@pytest.mark.parametrize("enabled", ["0", "1"])
def test_unparsed_claims_cannot_claim_checks_ran(monkeypatch, enabled):
    monkeypatch.setenv("PATENT_ENABLE_ANTECEDENT_CHECK", enabled)
    result = make_tools()["review_patent_claims"]("An unnumbered claim comprising a widget.")
    assert result["claim_count"] == 0
    assert result["checks_run"] == []
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
    assert "figure_numeral_coverage" in skipped
    assert "figure_numeral_coverage" not in result["checks_run"]


def test_missing_detailed_description_discloses_numeral_skip():
    result = make_tools()["check_formalities"](specification="FIG. 1 shows a system.")
    skipped = {c["check"]: c["reason"] for c in result["checks_skipped"]}
    assert "figure_numeral_coverage" in skipped
    assert "figure_numeral_coverage" not in result["checks_run"]


def test_reusing_checker_does_not_keep_previous_coverage(sample_good_abstract):
    checker = FormalitiesChecker()
    checker.check_all_formalities(sample_good_abstract, "Signal Processor", COMPLETE_SPEC, True)
    result = checker.check_all_formalities()
    assert result["checks_run"] == []
    assert result["compliance_summary"]["ready_to_file"] is False


@pytest.mark.parametrize(
    "tool, inputs",
    [
        ("review_patent_claims", {"claims_text": BEVERAGE_CLAIMS}),
        ("check_formalities", {"abstract": SHORT_ABSTRACT}),
    ],
)
def test_search_fallback_discloses_no_checks_ran(tool, inputs):
    result = make_tools(claims_analyzer=None, formalities_checker=None)[tool](**inputs)
    assert result["checks_run"] == []
    assert result["checks_skipped"]


