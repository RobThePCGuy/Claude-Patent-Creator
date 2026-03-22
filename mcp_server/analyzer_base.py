"""Base classes for patent analysis tools"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class BaseIssue:
    """Base dataclass for all analyzer issues

    Attributes:
        severity: CRITICAL, IMPORTANT, or MINOR
        problem: Description of the issue
        fix: Recommended fix
        mpep_ref: MPEP section reference
        confidence: Confidence level (HIGH, MEDIUM, LOW)
    """

    severity: str
    problem: str
    fix: str
    mpep_ref: str
    confidence: str = "HIGH"


class BaseAnalyzer(ABC):
    """Abstract base class for all patent analyzers

    Provides common functionality:
    - Issue collection and sorting
    - Severity-based counting
    - Report generation structure
    - Summary generation
    """

    SEVERITY_ORDER = {"CRITICAL": 0, "IMPORTANT": 1, "WARNING": 2, "MINOR": 3, "INFO": 4}

    def __init__(self):
        """Initialize analyzer with empty issues list"""
        self.issues: List[BaseIssue] = []

    @abstractmethod
    def analyze(self, *args, **kwargs) -> Dict[str, Any]:
        """Main analysis method - override in subclass

        Should populate self.issues and call _generate_report()

        Returns:
            Analysis report dictionary
        """
        pass

    def _sort_issues(self, secondary_key=None):
        """Sort issues by severity (and optional secondary key)

        Args:
            secondary_key: Optional lambda function for secondary sort
        """
        if secondary_key:
            self.issues.sort(key=lambda x: (self.SEVERITY_ORDER[x.severity], secondary_key(x)))
        else:
            self.issues.sort(key=lambda x: self.SEVERITY_ORDER[x.severity])

    def _count_by_severity(self) -> Dict[str, int]:
        """Count issues by severity level

        Returns:
            Dict with critical, important, minor, and total counts
        """
        critical = sum(1 for i in self.issues if i.severity == "CRITICAL")
        important = sum(1 for i in self.issues if i.severity == "IMPORTANT")
        minor = sum(1 for i in self.issues if i.severity == "MINOR")

        return {
            "critical": critical,
            "important": important,
            "minor": minor,
            "total": critical + important + minor,
        }

    def _generate_base_report(
        self,
        score_name: str,
        score_value: float,
        summary: str,
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate standard report structure

        Args:
            score_name: Name of the score field (e.g., 'compliance_score', 'coverage_score')
            score_value: Numeric score value
            summary: Analysis summary text
            additional_data: Optional dict of additional fields to include

        Returns:
            Complete report dictionary
        """
        counts = self._count_by_severity()

        report = {
            "total_issues": counts["total"],
            "critical_issues": counts["critical"],
            "important_issues": counts["important"],
            "minor_issues": counts["minor"],
            "issues": [self._issue_to_dict(issue) for issue in self.issues],
            "summary": summary,
            score_name: score_value,
        }

        if additional_data:
            report.update(additional_data)

        return report

    @abstractmethod
    def _issue_to_dict(self, issue: BaseIssue) -> Dict[str, Any]:
        """Convert issue to dictionary - override in subclass

        Each subclass may have different fields to serialize

        Args:
            issue: Issue instance to convert

        Returns:
            Dictionary representation of issue
        """
        pass

    def _generate_summary(self, score_name: str, score_value: float, context: str = "") -> str:
        """Generate analysis summary text

        Args:
            score_name: Name of the score (for display)
            score_value: Score value
            context: Additional context for the summary

        Returns:
            Formatted summary string
        """
        counts = self._count_by_severity()

        if counts["total"] == 0:
            return f"[OK] {context}No issues found. {score_name.replace('_', ' ').title()}: {score_value:.1f}%"

        summary_parts = [f"Found {counts['total']} issue{'s' if counts['total'] != 1 else ''}"]

        if counts["critical"] > 0:
            summary_parts.append(f"{counts['critical']} CRITICAL")
        if counts["important"] > 0:
            summary_parts.append(f"{counts['important']} IMPORTANT")
        if counts["minor"] > 0:
            summary_parts.append(f"{counts['minor']} MINOR")

        severity_text = ", ".join(summary_parts[1:]) if len(summary_parts) > 1 else ""
        summary = f"{summary_parts[0]}: {severity_text}. "

        if context:
            summary += f"{context} "

        summary += f"{score_name.replace('_', ' ').title()}: {score_value:.1f}%"

        return summary
