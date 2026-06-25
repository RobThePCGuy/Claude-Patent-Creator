#!/usr/bin/env python3
"""
EPO Formalities Checker
Automated checking of EPO formality requirements under Rules 42-49 EPC.

Checks:
- Rule 47 EPC: Form and content of the abstract
- Rule 42 EPC: Content of the description
- Rule 43 EPC: Form and content of claims
- Rule 46 EPC: Form of drawings
- Rule 45 EPC: Claims fees (claims in excess of 15)
"""

import re
from dataclasses import dataclass, field
from typing import Any, Optional

try:
    from analyzer_base import BaseAnalyzer, BaseIssue
except ImportError:
    from mcp_server.analyzer_base import BaseAnalyzer, BaseIssue


@dataclass
class EPOFormalityIssue(BaseIssue):
    """Represents an EPO formality compliance issue"""

    section: str = field(default="")  # abstract, title, drawings, claims, description
    current_value: str = field(default="")
    required_value: str = field(default="")


class EPOFormalitiesChecker(BaseAnalyzer):
    """Automated checking of EPO patent application formalities per Rules 42-49 EPC.

    Unlike the USPTO formalities checker, the EPO abstract does NOT prohibit
    terms like 'means', 'said', or 'whereby'. The EPO abstract must be a concise
    summary preferably of 150 words or less, with reference signs in parentheses.
    """

    # Rule 47 EPC - Abstract requirements
    ABSTRACT_PREFERRED_MAX_WORDS = 150

    # Claims fee threshold (Rule 45(1) EPC)
    CLAIMS_FEE_THRESHOLD = 15

    # Rule 42 EPC required description sections
    REQUIRED_SECTIONS = {
        "Technical field": r"(?i)technical\s+field|field\s+of\s+(?:the\s+)?invention",
        "Background art": r"(?i)background\s+(?:art|of\s+(?:the\s+)?invention)|prior\s+art|related\s+art",
        "Disclosure of the invention": r"(?i)(?:disclosure|summary)\s+of\s+(?:the\s+)?invention|technical\s+problem|object\s+of\s+(?:the\s+)?invention",
        "Brief description of drawings": r"(?i)brief\s+description\s+of\s+(?:the\s+)?(?:drawings?|figures?)|description\s+of\s+(?:the\s+)?(?:drawings?|figures?)",
        "Detailed description": r"(?i)detailed\s+description|description\s+of\s+(?:the\s+)?(?:preferred\s+)?embodiments?|modes?\s+(?:of|for)\s+carrying\s+out",
    }

    def analyze(
        self,
        abstract: Optional[str] = None,
        title: Optional[str] = None,
        specification: Optional[str] = None,
        drawings_present: bool = False,
    ) -> dict[str, Any]:
        """
        Main analysis method - checks all EPO formality requirements.

        Args:
            abstract: Abstract text
            title: Title text
            specification: Full specification text
            drawings_present: Whether drawings are included

        Returns:
            Dictionary with formality check results
        """
        return self.check_all_formalities(abstract, title, specification, drawings_present)

    def _issue_to_dict(self, issue: BaseIssue) -> dict[str, Any]:
        """Convert EPOFormalityIssue to dictionary"""
        if not isinstance(issue, EPOFormalityIssue):
            return {
                "section": "",
                "severity": issue.severity,
                "problem": issue.problem,
                "current": "",
                "required": "",
                "fix": issue.fix,
                "legal_ref": issue.legal_ref,
                "confidence": issue.confidence,
            }
        return {
            "section": issue.section,
            "severity": issue.severity,
            "problem": issue.problem,
            "current": issue.current_value,
            "required": issue.required_value,
            "fix": issue.fix,
            "legal_ref": issue.legal_ref,
            "confidence": issue.confidence,
        }

    def check_all_formalities(
        self,
        abstract: Optional[str] = None,
        title: Optional[str] = None,
        specification: Optional[str] = None,
        drawings_present: bool = False,
    ) -> dict:
        """
        Check all EPO formality requirements.

        Args:
            abstract: Abstract text
            title: Title text
            specification: Full specification text
            drawings_present: Whether drawings are included

        Returns:
            Dictionary with formality check results
        """
        self.issues = []

        results: dict[str, Any] = {
            "abstract": None,
            "title": None,
            "drawings": None,
            "sections": None,
            "claims_fees": None,
        }

        if abstract:
            results["abstract"] = self._check_abstract(abstract)

        if title:
            results["title"] = self._check_title(title)

        if specification:
            results["sections"] = self._check_description_sections(specification)
            results["drawings"] = self._check_drawings(specification, drawings_present)
            results["claims_fees"] = self._check_claims_fees(specification)

        return {
            "results": results,
            "issues": [self._issue_to_dict(issue) for issue in self.issues],
            "compliance_summary": self._generate_compliance_summary(results),
            "overall_compliant": len([i for i in self.issues if i.severity == "CRITICAL"]) == 0,
            "jurisdiction": "EPO",
            "legal_framework": "European Patent Convention (EPC)",
        }

    def _check_abstract(self, abstract: str) -> dict:
        """Check abstract compliance with Rule 47 EPC.

        Rule 47(1) EPC: The abstract shall contain a concise summary of the
        disclosure as contained in the description, claims and drawings.
        It shall indicate the technical field and include the principal
        technical solution and principal use(s) of the invention.

        Rule 47(2) EPC: The abstract shall preferably not contain more than
        150 words.

        Rule 47(3) EPC: The abstract shall contain reference signs in
        parentheses referring to the features of the drawings.

        Note: Unlike USPTO (MPEP 608.01(b)), EPO does NOT prohibit claim
        language like 'means', 'said', 'whereby' in the abstract.
        """
        abstract = abstract.strip()
        words = abstract.split()
        word_count = len(words)

        result = {
            "word_count": word_count,
            "compliant": True,
            "issues": [],
        }

        # Check word count (Rule 47(2) - preferably <=150 words)
        if word_count > self.ABSTRACT_PREFERRED_MAX_WORDS:
            self.issues.append(
                EPOFormalityIssue(
                    section="abstract",
                    severity="WARNING",
                    problem="Abstract exceeds preferred maximum length",
                    current_value=f"{word_count} words",
                    required_value=f"Preferably <= {self.ABSTRACT_PREFERRED_MAX_WORDS} words",
                    fix=f"Reduce abstract to {self.ABSTRACT_PREFERRED_MAX_WORDS} words or less",
                    legal_ref="Rule 47(2) EPC",
                )
            )
            result["compliant"] = False
            result["issues"].append("Too long")

        # Check for reference signs in parentheses (Rule 47(3) EPC)
        ref_sign_pattern = re.compile(r"\(\d+[a-z]?\)")
        has_ref_signs = bool(ref_sign_pattern.search(abstract))
        result["has_reference_signs"] = has_ref_signs

        if not has_ref_signs:
            self.issues.append(
                EPOFormalityIssue(
                    section="abstract",
                    severity="IMPORTANT",
                    problem="Abstract does not contain reference signs in parentheses",
                    current_value="No reference signs found",
                    required_value="Reference signs corresponding to drawings, in parentheses",
                    fix="Add reference numerals from drawings in parentheses, e.g., 'processor (10)'",
                    legal_ref="Rule 47(3) EPC",
                )
            )
            result["issues"].append("Missing reference signs")

        # Check for technical field indication (Rule 47(1) EPC)
        # Simple heuristic: abstract should mention what the invention relates to
        if word_count < 20:
            self.issues.append(
                EPOFormalityIssue(
                    section="abstract",
                    severity="WARNING",
                    problem="Abstract appears too brief to adequately summarize the invention",
                    current_value=f"{word_count} words",
                    required_value="Concise summary indicating technical field, solution, and use",
                    fix="Expand abstract to include technical field, principal solution, and principal use",
                    legal_ref="Rule 47(1) EPC",
                )
            )
            result["compliant"] = False
            result["issues"].append("Too short")

        # Check paragraph structure (should be single paragraph)
        if "\n\n" in abstract:
            self.issues.append(
                EPOFormalityIssue(
                    section="abstract",
                    severity="INFO",
                    problem="Abstract should preferably be a single paragraph",
                    current_value="Multiple paragraphs",
                    required_value="Single paragraph",
                    fix="Combine into single paragraph",
                    legal_ref="Rule 47(1) EPC",
                )
            )
            result["issues"].append("Multiple paragraphs")

        return result

    def _check_title(self, title: str) -> dict:
        """Check title compliance with Rule 44 EPC.

        The title shall clearly and concisely indicate the subject matter
        of the invention. It shall not contain trade names.
        """
        title = title.strip()
        char_count = len(title)
        word_count = len(title.split())

        result = {
            "character_count": char_count,
            "word_count": word_count,
            "compliant": True,
            "issues": [],
        }

        # Check for empty or very short title
        if word_count < 2:
            self.issues.append(
                EPOFormalityIssue(
                    section="title",
                    severity="CRITICAL",
                    problem="Title is too short to indicate the subject matter",
                    current_value=f"{word_count} word(s)",
                    required_value="Clear and concise indication of subject matter",
                    fix="Provide a descriptive title that indicates the technical subject matter",
                    legal_ref="Rule 44(1) EPC",
                )
            )
            result["compliant"] = False
            result["issues"].append("Too short")

        # Check for trademark symbols
        trademark_indicators = ["(TM)", "(R)", "(c)", "\u2122", "\u00ae", "\u00a9"]
        if any(tm in title for tm in trademark_indicators):
            self.issues.append(
                EPOFormalityIssue(
                    section="title",
                    severity="CRITICAL",
                    problem="Title contains trade name or trademark symbols",
                    current_value="Contains trademark symbols",
                    required_value="Must not contain trade names or marks",
                    fix="Remove all trademark symbols and trade names from title",
                    legal_ref="Rule 44(2) EPC",
                )
            )
            result["compliant"] = False
            result["issues"].append("Contains trademarks")

        # Check for very long title (not a hard rule but EPO prefers concise)
        if word_count > 15:
            self.issues.append(
                EPOFormalityIssue(
                    section="title",
                    severity="INFO",
                    problem="Title is longer than typical for EPO applications",
                    current_value=f"{word_count} words",
                    required_value="Concise indication of subject matter",
                    fix="Consider shortening the title while maintaining clarity",
                    legal_ref="Rule 44(1) EPC",
                )
            )
            result["issues"].append("Could be shorter")

        return result

    def _check_description_sections(self, specification: str) -> dict:
        """Check for Rule 42 EPC required description sections"""
        found_sections = {}
        missing_sections = []

        for section_name, pattern in self.REQUIRED_SECTIONS.items():
            if re.search(pattern, specification):
                found_sections[section_name] = True
            else:
                found_sections[section_name] = False
                missing_sections.append(section_name)

        result = {
            "found_sections": found_sections,
            "missing_sections": missing_sections,
            "compliant": len(missing_sections) == 0,
        }

        for section in missing_sections:
            self.issues.append(
                EPOFormalityIssue(
                    section="description",
                    severity="CRITICAL",
                    problem=f"Missing required description section: {section}",
                    current_value="Not found",
                    required_value=f"Must include '{section}' section",
                    fix=f'Add "{section}" section to the description',
                    legal_ref="Rule 42(1) EPC",
                )
            )

        return result

    def _check_drawings(self, specification: str, drawings_present: bool) -> dict:
        """Check drawing compliance with Rule 46 EPC.

        Rule 46 EPC requirements:
        - Drawings on A4 paper
        - Durable, black, sufficiently dense lines
        - Cross-sections shown by hatching
        - Reference signs used in drawings must correspond to description
        """
        # Extract figure references from specification
        fig_pattern = re.compile(
            r"FIGS?(?:URES?)?\.?\s*(\d+[A-Z]?(?:\([a-z]\))?(?:\s*-\s*\d+[A-Z]?)?)",
            re.IGNORECASE,
        )
        referenced_figures = set(fig_pattern.findall(specification))

        result = {
            "figures_referenced": sorted(referenced_figures),
            "figure_count": len(referenced_figures),
            "drawings_provided": drawings_present,
            "compliant": True,
            "issues": [],
        }

        if referenced_figures:
            if not drawings_present:
                self.issues.append(
                    EPOFormalityIssue(
                        section="drawings",
                        severity="CRITICAL",
                        problem=(
                            f"Description references {len(referenced_figures)} figure(s) "
                            f"but drawings not provided"
                        ),
                        current_value="No drawings",
                        required_value=f'Must include figures: {", ".join(sorted(referenced_figures))}',
                        fix="Create and include all referenced figures per Rule 46 EPC",
                        legal_ref="Rule 46 EPC",
                    )
                )
                result["compliant"] = False
                result["issues"].append("Missing drawings")

            # Check for Brief Description of Drawings section
            if not re.search(
                r"(?i)(?:brief\s+)?description\s+of\s+(?:the\s+)?(?:drawings?|figures?)",
                specification,
            ):
                self.issues.append(
                    EPOFormalityIssue(
                        section="drawings",
                        severity="CRITICAL",
                        problem='Figures referenced but "Brief description of drawings" section missing',
                        current_value="Section not found",
                        required_value='Must include "Brief description of drawings" section',
                        fix='Add "Brief description of drawings" section per Rule 42(1)(d) EPC',
                        legal_ref="Rule 42(1)(d) EPC",
                    )
                )
                result["compliant"] = False
                result["issues"].append("Missing figure description section")

        return result

    def _check_claims_fees(self, specification: str) -> dict:
        """Check claims count against fee threshold (Rule 45(1) EPC).

        Additional claims fees apply for each claim beyond 15.
        """
        # Count claims in specification
        claim_pattern = re.compile(r"(?:^|\n)\s*(\d+)\.\s+", re.MULTILINE)
        claim_matches = claim_pattern.findall(specification)

        # Deduplicate and count unique claim numbers
        claim_numbers = sorted({int(n) for n in claim_matches})
        total_claims = len(claim_numbers)

        result = {
            "total_claims_detected": total_claims,
            "fee_threshold": self.CLAIMS_FEE_THRESHOLD,
            "excess_claims": max(0, total_claims - self.CLAIMS_FEE_THRESHOLD),
            "fees_apply": total_claims > self.CLAIMS_FEE_THRESHOLD,
        }

        if total_claims > self.CLAIMS_FEE_THRESHOLD:
            excess = total_claims - self.CLAIMS_FEE_THRESHOLD
            self.issues.append(
                EPOFormalityIssue(
                    section="claims",
                    severity="MINOR",
                    problem=(
                        f"Application has {total_claims} claims, exceeding the "
                        f"{self.CLAIMS_FEE_THRESHOLD}-claim threshold"
                    ),
                    current_value=f"{total_claims} claims",
                    required_value=f"<= {self.CLAIMS_FEE_THRESHOLD} claims (no additional fee)",
                    fix=(
                        f"Additional claims fees will apply for {excess} excess claim(s). "
                        f"Consider reducing claim count or confirm budget."
                    ),
                    legal_ref="Rule 45(1) EPC",
                )
            )

        return result

    def _generate_compliance_summary(self, results: dict) -> dict:
        """Generate overall compliance summary"""
        critical_issues = 0
        warnings = 0
        info = 0

        for issue in self.issues:
            if issue.severity == "CRITICAL":
                critical_issues += 1
            elif issue.severity in ("WARNING", "IMPORTANT"):
                warnings += 1
            else:
                info += 1

        passed_checks = 0
        if results.get("abstract") and results["abstract"].get("compliant"):
            passed_checks += 1
        if results.get("title") and results["title"].get("compliant"):
            passed_checks += 1
        if results.get("sections") and results["sections"].get("compliant"):
            passed_checks += 1
        if results.get("drawings") and results["drawings"].get("compliant"):
            passed_checks += 1

        return {
            "critical_issues": critical_issues,
            "warnings": warnings,
            "info": info,
            "ready_to_file": critical_issues == 0,
            "summary": self._format_summary(critical_issues, warnings, info),
        }

    def _format_summary(self, critical: int, warnings: int, info: int) -> str:
        """Format human-readable summary"""
        if critical == 0 and warnings == 0 and info == 0:
            return "[OK] All EPO formalities requirements met (Rules 42-49 EPC)"

        parts = []
        if critical > 0:
            parts.append(f"{critical} CRITICAL")
        if warnings > 0:
            parts.append(f"{warnings} WARNING")
        if info > 0:
            parts.append(f"{info} INFO")

        return f"[WARNING] Found {', '.join(parts)} EPO formality issue(s)"


# Example usage
if __name__ == "__main__":
    checker = EPOFormalitiesChecker()

    abstract = """
    A system for AI-augmented document enhancement achieves 70-85% computational cost reduction
    through content-addressed multi-layer caching using per-file SHA-256 hash verification with
    automatic invalidation. The system maintains document continuity via a structured Knowledge Base.
    """

    title = "System and Method for AI-Augmented Enhancement of Multi-Section Documents"

    results = checker.check_all_formalities(abstract=abstract, title=title, drawings_present=False)

    print(f"\nCompliance Summary: {results['compliance_summary']['summary']}")
    print(f"Ready to file: {results['compliance_summary']['ready_to_file']}")

    if results["results"]["abstract"]:
        print(
            f"\nAbstract: {results['results']['abstract']['word_count']} words - "
            f"{'[OK] Compliant' if results['results']['abstract']['compliant'] else '[WARNING] Issues found'}"
        )

    if results["results"]["title"]:
        print(
            f"Title: {results['results']['title']['character_count']} chars - "
            f"{'[OK] Compliant' if results['results']['title']['compliant'] else '[WARNING] Issues found'}"
        )

    if results["issues"]:
        print("\nIssues Found:")
        for issue in results["issues"]:
            print(f"\n[{issue['severity']}] {issue['section']}")
            print(f"  Problem: {issue['problem']}")
            print(f"  Fix: {issue['fix']}")
            print(f"  Ref: {issue['legal_ref']}")
