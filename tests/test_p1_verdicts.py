"""P1 regression tests: missing coverage must never become filing clearance."""

import importlib
from types import SimpleNamespace

import pytest

EPO = importlib.import_module("mcp_server.epo_formalities_checker").EPOFormalitiesChecker
PCT = importlib.import_module("mcp_server.pct_formalities_checker").PCTFormalitiesChecker
VALIDATION = importlib.import_module("mcp_server.validation")
REGISTER = importlib.import_module("mcp_server.tools.epo_analyzer_tools").register_epo_analyzer_tools


def make_tools(available=True):
    registered = {}

    def tool():
        def register(fn):
            registered[fn.__name__] = fn
            return fn
        return register

    REGISTER(
        mcp=SimpleNamespace(tool=tool),
        mpep_index=SimpleNamespace(search=lambda *a, **k: []),
        EPOClaimsAnalyzer=None, EPOSpecificationAnalyzer=None,
        EPOFormalitiesChecker=EPO if available else None,
        PCTFormalitiesChecker=PCT if available else None,
        log_info=lambda *a, **k: None, log_warning=lambda *a, **k: None,
        log_error=lambda *a, **k: None, validate_input=VALIDATION.validate_input,
        ReviewClaimsInput=VALIDATION.ReviewClaimsInput,
        ReviewSpecificationInput=VALIDATION.ReviewSpecificationInput,
        CheckFormalitiesInput=VALIDATION.CheckFormalitiesInput,
        track_performance=lambda *a, **k: lambda fn: fn,
        log_operation_result=lambda *a, **k: None,
    )
    return registered


@pytest.mark.parametrize("jurisdiction", ["epo", "pct"])
@pytest.mark.parametrize("blank", [None, "", " \n\t"])
def test_missing_application_never_ready(jurisdiction, blank):
    result = make_tools()[f"check_{jurisdiction}_formalities"](
        abstract=blank, title=blank, specification=blank
    )
    assert result["ready_to_file"] is False
    assert result["overall_compliant"] is False
    assert result["checks_run"] == []
    assert result["checks_skipped"]
    assert result["summary"].startswith("[INCOMPLETE]")
    assert "requirements met" not in result["summary"]


@pytest.mark.parametrize("jurisdiction", ["epo", "pct"])
def test_partial_application_discloses_exact_coverage(jurisdiction, sample_good_abstract):
    result = make_tools()[f"check_{jurisdiction}_formalities"](abstract=sample_good_abstract)
    assert result["checks_run"] == ["abstract"]
    skipped = {c["check"]: c["reason"] for c in result["checks_skipped"]}
    assert skipped["title"] == "no title supplied"
    assert "specification" in skipped["sections" if jurisdiction == "epo" else "description"]
    assert result["ready_to_file"] is False
    assert "not a filing clearance" in result["verdict_scope"]


@pytest.mark.parametrize("jurisdiction", ["epo", "pct"])
def test_unavailable_checker_reports_no_checks(jurisdiction):
    result = make_tools(False)[f"check_{jurisdiction}_formalities"](title="Signal processor")
    assert result["ready_to_file"] is False
    assert result["overall_compliant"] is False
    assert result["checks_run"] == []
    assert all("unavailable" in c["reason"] for c in result["checks_skipped"])
    assert result["checks_skipped"]


def complete_inputs(sample_good_abstract, sample_epo_specification):
    return {
        "abstract": sample_good_abstract,
        "title": "Signal processor",
        "specification": sample_epo_specification + "\nCLAIMS\n1. A signal processor.\n",
        "drawings_present": True,
    }


def test_epo_complete_checks_can_pass(sample_good_abstract, sample_epo_specification):
    result = make_tools()["check_epo_formalities"](
        **complete_inputs(sample_good_abstract, sample_epo_specification)
    )
    assert result["ready_to_file"] is True
    assert result["overall_compliant"] is True
    assert result["checks_skipped"] == []
    assert set(result["checks_run"]) == {"abstract", "title", "sections", "drawing_references", "claims_fees"}
    assert "not a filing clearance" in result["verdict_scope"]


def test_epo_failed_noncritical_component_blocks_ready(sample_good_abstract, sample_epo_specification):
    inputs = complete_inputs(sample_good_abstract, sample_epo_specification)
    # Excess length is advisory under Rule 47(3), not a failed component.
    inputs["abstract"] = "A sensor (10)."
    result = make_tools()["check_epo_formalities"](**inputs)
    assert result["critical_issues"] == 0
    assert result["abstract"]["compliant"] is False
    assert result["ready_to_file"] is False


def test_epo_missing_claims_cannot_pass_fee_check(sample_good_abstract, sample_epo_specification):
    inputs = complete_inputs(sample_good_abstract, sample_epo_specification)
    inputs["specification"] = sample_epo_specification
    result = make_tools()["check_epo_formalities"](**inputs)
    assert result["ready_to_file"] is False
    assert "claims_fees" not in result["checks_run"]
    assert any(c["check"] == "claims_fees" for c in result["checks_skipped"])


@pytest.mark.parametrize("checker", [EPO, PCT])
def test_checker_reuse_drops_previous_coverage(checker, sample_good_abstract):
    instance = checker()
    instance.check_all_formalities(abstract=sample_good_abstract)
    result = instance.check_all_formalities()
    assert result["checks_run"] == []
    assert result["compliance_summary"]["ready_to_file"] is False


def test_pct_physical_advisory_is_skipped_not_passed(sample_good_abstract, sample_epo_specification):
    result = make_tools()["check_pct_formalities"](
        **complete_inputs(sample_good_abstract, sample_epo_specification)
    )
    assert result["critical_issues"] == 0
    assert result["physical_requirements"]["advisory"] is True
    assert "physical" not in result["checks_run"]
    assert any(c["check"] == "physical" for c in result["checks_skipped"])
    assert result["ready_to_file"] is False
    assert result["overall_compliant"] is False


@pytest.mark.parametrize("module,classname", [
    ("specification_analyzer", "SpecificationAnalyzer"),
    ("epo_specification_analyzer", "EPOSpecificationAnalyzer"),
])
def test_dependent_claims_receive_support_review_and_coverage(module, classname):
    analyzer = getattr(importlib.import_module(f"mcp_server.{module}"), classname)()
    claims = [
        {"number": 1, "text": "A system comprising a receiver.", "is_independent": True},
        {"number": 2, "text": "The system of claim 1, comprising a frobnicator.", "is_independent": False},
        {"number": 3, "text": "The system of claim 2, comprising a quuxifier.", "is_independent": False},
    ]
    report = analyzer.analyze_specification_support(claims, "[0001] A receiver.\n[0002] A receiver.")
    assert {i["claim"] for i in report["issues"] if i["severity"] == "CRITICAL"} >= {2, 3}
    assert report["compliant"] is False
    assert report["spec_coverage"]["total_claims"] == 3
    assert report["spec_coverage"]["supported_claims"] == 1
    assert report["spec_coverage"]["percentage"] == 33
    assert set(report["spec_coverage"]["unsupported_claims"]) == {2, 3}


def test_epo_numbered_description_is_not_claims(sample_good_abstract, sample_epo_specification):
    inputs = complete_inputs(sample_good_abstract, sample_epo_specification)
    inputs["specification"] = (
        sample_epo_specification
        + "\nAn example operating sequence is:\n1. Turn on the power.\n2. Read the signal.\n"
    )
    result = make_tools()["check_epo_formalities"](**inputs)
    assert result["ready_to_file"] is False
    assert result["overall_compliant"] is False
    assert result["claims_fees"]["total_claims_detected"] == 0
    assert "claims_fees" not in result["checks_run"]
    assert any(c["check"] == "claims_fees" for c in result["checks_skipped"])


@pytest.mark.parametrize("header", ["CLAIMS", "Claims:", "WHAT IS CLAIMED IS:"])
def test_epo_claim_count_excludes_description_steps(header, sample_epo_specification):
    result = EPO().check_all_formalities(specification=(
        sample_epo_specification
        + "\n1. Turn on the power.\n2. Read the signal.\n"
        + f"\n{header}\n1. A signal processor.\n"
    ))
    assert result["results"]["claims_fees"]["total_claims_detected"] == 1
    assert "claims_fees" in result["checks_run"]
