"""Tests for EPO Formalities Checker (Rules 42-49 EPC)."""

from mcp_server.epo_formalities_checker import EPOFormalitiesChecker


class TestAbstract:
    """Rule 47 EPC: abstract requirements."""

    def test_no_means_said_prohibition(self):
        """EPO does NOT prohibit 'means/said/whereby' in abstracts (unlike USPTO)."""
        checker = EPOFormalitiesChecker()
        abstract = (
            "A means for processing data includes a said processor "
            "whereby computation is performed on input signals. "
            "The processing means employs parallel units for improved "
            "throughput across multiple data channels for real-time analysis."
        )
        result = checker.check_all_formalities(abstract=abstract)
        forbidden_issues = [
            i for i in result["issues"]
            if "forbidden" in i.get("problem", "").lower()
            and any(w in i.get("problem", "").lower() for w in ["means", "said", "whereby"])
        ]
        assert len(forbidden_issues) == 0


