"""Word-count preferences must not become hard filing prohibitions."""

import pytest

from mcp_server.epo_formalities_checker import EPOFormalitiesChecker
from mcp_server.pct_formalities_checker import PCTFormalitiesChecker


@pytest.mark.parametrize(
    ("checker_class", "reference"),
    [(EPOFormalitiesChecker, "Rule 47(3) EPC"), (PCTFormalitiesChecker, "PCT Rule 8.1(b)")],
)
def test_abstract_over_preferred_length_is_advisory(checker_class, reference):
    checker = checker_class()
    abstract = "A sensor (10) measures temperature. " + "measurement " * 150
    if isinstance(checker, PCTFormalitiesChecker):
        section = checker._check_abstract(abstract, drawings_present=False)
    else:
        section = checker._check_abstract(abstract)
    length_issues = [issue for issue in checker.issues if issue.legal_ref == reference]
    assert len(length_issues) == 1
    assert length_issues[0].severity == "WARNING"
    assert "prefer" in length_issues[0].required_value.lower()
    assert section["compliant"] is True
