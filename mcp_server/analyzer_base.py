"""Base classes for patent analysis tools"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

# Claim reference lists: "claim 1", "claims 1 or 2", "claims 1 to 5", "1-3",
# "claims 1, 2 and 4", "claim 1 or claim 2".
_DASH = "-\u2010\u2011\u2012\u2013\u2014\u2015\u2212"
# A claim number stands alone: in "3D printed", "3-D printed", "20mm", "2nd"
# or "3/4 inch" the number is part of a word or a measurement. A hyphen joined
# straight to a letter marks such a word; "claim 1-claim 3" is still a range,
# and "claim 1 - wherein" or "claim 1 \u2014 wherein" is still claim 1.
_NUMBER = r"(\d+)(?!\w|/\d|[-\u2010\u2011](?!claims?\b)[^\W\d_])"
_REF_FIRST = re.compile(r"\s*" + _NUMBER, re.IGNORECASE)
_REF_NEXT = re.compile(
    r"\s*(?:(,)\s*(?:(or|and)\b)?|\b(or|and)\b|(\bto\b|\bthrough\b|\s*[" + _DASH + r"]\s*(?:claims?\s+)?))"
    r"\s*(?:claims?\s+)?" + _NUMBER,
    re.IGNORECASE,
)
# What may follow a bare comma item ("claims 1, 2 or 3", "claims 1, 2, and 4",
# "claims 1, 3 to 5."): another list word, punctuation or the end. A word
# there ("claim 1, 2 adjacent sensors") means the number counts something.
_ITEM_END = re.compile(
    r"\s*(?:$|[,;:.)]|\b(?:or|and|to|through)\b|[" + _DASH + r"])",
    re.IGNORECASE,
)
# Words that follow a real claim reference ("claims 1 or 2 configured to...",
# "claims 1 to 3, wherein", "claim 1 or 2 characterised in that").
_NEXT_WORD = re.compile(r"\s+([^\W\d_]+)")
_AFTER_REFERENCE = {
    "wherein", "whereby", "which", "that", "where", "when", "in", "further", "comprising",
    "including", "having", "configured", "characterised", "characterized", "adapted",
    "arranged", "operable", "with", "for", "and", "or", "the", "a", "an", "said", "being",
    "also", "additionally", "is", "are", "to", "through", "claim", "claims",
    "consisting", "comprises", "includes", "has", "using", "by", "on", "at", "of", "as",
}
# A unit or a quantity phrase right after a number means it is a measurement
# or a count ("2 mm", "2 or more of the sensors"), not a claim number.
_UNIT_AFTER = re.compile(
    r"(?:\.\d|\s+(?:or|and)\s+(?:more|fewer|less|greater|above|below)\b|\s+of\s+(?:the|said)\b|\s*(?:%|\u00b0|\u00b5m|\u03bcm|"
    r"in(?=\s*(?:[,.;)]|$|thick|wide|long|high|deep|diameter|thickness|width|length|height|depth))|"
    r"(?:nm|um|mm|cm|m|km|inch|inches|ft|feet|mils?|"
    r"mg|g|kg|lbs?|oz|ms|s|sec|seconds?|min|minutes?|h|hours?|hz|khz|mhz|ghz|mv|kv|v|ma|"
    r"kw|mw|w|psi|kpa|mpa|pa|bar|ml|l|mol|db|degrees?|percent|times)\b))",
    re.IGNORECASE,
)


def claim_reference_numbers(text: str, pos: int = 0) -> list[int]:
    """The claim numbers in a reference list starting at text[pos], ranges expanded.

    A multiple-dependent claim ("any one of claims 1 or 2", "claims 1 to 5")
    depends on each listed claim, so callers must see all of them, not only
    the first. When the list ends in a measurement ("claim 1, 2 mm thick",
    "claim 1, 2 or 3 mm", "claims 1-3 cm"), the numbers after the first are
    dimensions, so only the first counts.
    """
    first = _REF_FIRST.match(text, pos)
    if not first:
        return []
    numbers = [int(first.group(1))]
    end = first.end()
    extra: list[int] = []
    closed = False  # an "or"/"and" has been read; a bare comma now ends the list
    bare_from = None  # where the run of items after the last bare comma starts
    while True:
        nxt = _REF_NEXT.match(text, end)
        if not nxt:
            break
        comma, comma_word, word, range_sep, digits = nxt.groups()
        if comma and not comma_word and closed:
            break  # "claims 1 or 2, 3 mm thick": the list ended at "2"
        if comma and not comma_word:
            bare_from = len(extra)
        elif comma_word or word:
            bare_from = None  # "1, 2 or 3": the "or" confirms the list
        value = int(digits)
        if range_sep:  # "1 to 5", "1-3"
            start = (extra or numbers)[-1]
            if start < value <= start + 1000:
                extra.extend(range(start + 1, value + 1))
            else:
                extra.append(value)
        else:
            extra.append(value)
        closed = closed or bool(comma_word or word)
        end = nxt.end()
    if bare_from is not None and not _ITEM_END.match(text, end):
        # "claim 1, 2 adjacent sensors", "claim 1, 2 to 4 adjacent sensors":
        # numbers after a bare comma, followed by a word, count something.
        extra = extra[:bare_from]
    next_word = _NEXT_WORD.match(text, end)
    if extra and next_word and next_word.group(1).lower() not in _AFTER_REFERENCE:
        # "claim 1, 2 or 3 sensors": a noun after the list means the later
        # numbers count something.
        extra = []
    if extra and _UNIT_AFTER.match(text, end):
        extra = []
    return list(dict.fromkeys(numbers + extra))


def claim_opening(body: str) -> str:
    """The opening of a claim, where its claim reference sits: the text before
    the first colon that introduces the body (not one inside a ratio such as
    "2:1"), capped at 300 characters."""
    return re.split(r"(?<!\d):|:(?!\d)", body, maxsplit=1)[0][:300]


def claim_parents(claim: dict) -> list[int]:
    """All parents of a claim: depends_on_all when present, else depends_on."""
    parents = claim.get("depends_on_all")
    if parents:
        return list(parents)
    return [claim["depends_on"]] if claim.get("depends_on") is not None else []


def unsupported_through_chain(claims: list[dict], flagged: set[int]) -> set[int]:
    """Claims that are flagged themselves or inherit a flag through ANY parent.

    A dependent claim contains every limitation of the claim it depends on; a
    multiple-dependent claim must hold under each alternative parent, so one
    flagged branch is enough to flag it.
    """
    # Walk down from each flagged claim to every claim that depends on it,
    # directly or through any chain: one pass, whatever the claim count.
    children: dict[int, list[int]] = {}
    for c in claims:
        for parent in claim_parents(c):
            children.setdefault(parent, []).append(c["number"])
    reached = set(flagged)
    stack = list(flagged)
    while stack:
        for child in children.get(stack.pop(), []):
            if child not in reached:
                reached.add(child)
                stack.append(child)
    return reached & {c["number"] for c in claims}


@dataclass
class BaseIssue:
    """Base dataclass for all analyzer issues

    Attributes:
        severity: CRITICAL, IMPORTANT, or MINOR
        problem: Description of the issue
        fix: Recommended fix
        legal_ref: Legal reference (e.g., "MPEP 2173.05(b)", "Art. 84 EPC", "PCT Rule 6")
        confidence: Confidence level (HIGH, MEDIUM, LOW)
    """

    severity: str
    problem: str
    fix: str
    legal_ref: str
    confidence: str = "HIGH"

    @property
    def mpep_ref(self) -> str:
        """Backward-compatible alias for legal_ref."""
        return self.legal_ref


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
        self.issues: list[BaseIssue] = []

    @abstractmethod
    def analyze(self, *args, **kwargs) -> dict[str, Any]:
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

    def _count_by_severity(self) -> dict[str, int]:
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
        additional_data: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
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
    def _issue_to_dict(self, issue: BaseIssue) -> dict[str, Any]:
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
