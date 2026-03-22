#!/usr/bin/env python3
"""
Patent Application Formalities Checker
Automated checking of MPEP 608 formality requirements
"""

import re
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

try:
    from analyzer_base import BaseIssue, BaseAnalyzer
except ImportError:
    from mcp_server.analyzer_base import BaseIssue, BaseAnalyzer


@dataclass
class FormalityIssue(BaseIssue):
    """Represents a formality compliance issue"""

    section: str = field(default="")  # abstract, title, drawings, etc.
    current_value: str = field(default="")
    required_value: str = field(default="")


class FormalitiesChecker(BaseAnalyzer):
    """Automated checking of patent application formalities per MPEP 608"""

    # MPEP 608.01(b) - Abstract requirements
    ABSTRACT_MIN_WORDS = 50
    ABSTRACT_MAX_WORDS = 150
    ABSTRACT_MAX_LINES = 15

    # 37 CFR 1.72(a) - Title requirements
    TITLE_MAX_CHARS = 500
    TITLE_RECOMMENDED_CHARS = 100

    # 37 CFR 1.84 - Drawings requirements
    REQUIRED_DRAWING_ELEMENTS = ["reference numerals", "figure numbers", "lead lines"]

    def analyze(
        self,
        abstract: Optional[str] = None,
        title: Optional[str] = None,
        specification: Optional[str] = None,
        drawings_present: bool = False,
    ) -> Dict[str, Any]:
        """
        Main analysis method - checks all formality requirements

        Args:
            abstract: Abstract text
            title: Title text
            specification: Full specification text
            drawings_present: Whether drawings are included

        Returns:
            Dictionary with formality check results
        """
        return self.check_all_formalities(abstract, title, specification, drawings_present)

    def _issue_to_dict(self, issue: BaseIssue) -> Dict[str, Any]:
        """Convert FormalityIssue to dictionary"""
        if not isinstance(issue, FormalityIssue):
            # Fallback for base issues
            return {
                "section": "",
                "severity": issue.severity,
                "problem": issue.problem,
                "current": "",
                "required": "",
                "fix": issue.fix,
                "mpep": issue.mpep_ref,
                "confidence": issue.confidence,
            }
        return {
            "section": issue.section,
            "severity": issue.severity,
            "problem": issue.problem,
            "current": issue.current_value,
            "required": issue.required_value,
            "fix": issue.fix,
            "mpep": issue.mpep_ref,
            "confidence": issue.confidence,
        }

    def check_all_formalities(
        self,
        abstract: Optional[str] = None,
        title: Optional[str] = None,
        specification: Optional[str] = None,
        drawings_present: bool = False,
    ) -> Dict:
        """
        Check all formality requirements

        Args:
            abstract: Abstract text
            title: Title text
            specification: Full specification text
            drawings_present: Whether drawings are included

        Returns:
            Dictionary with formality check results
        """
        self.issues = []

        results: Dict[str, Any] = {
            "abstract": None,
            "title": None,
            "drawings": None,
            "sections": None,
        }

        if abstract:
            results["abstract"] = self._check_abstract(abstract)

        if title:
            results["title"] = self._check_title(title)

        if specification:
            results["sections"] = self._check_specification_sections(specification)
            results["drawings"] = self._check_drawing_references(specification, drawings_present)

        return {
            "results": results,
            "issues": [self._issue_to_dict(issue) for issue in self.issues],
            "compliance_summary": self._generate_compliance_summary(results),
            "overall_compliant": len([i for i in self.issues if i.severity == "CRITICAL"]) == 0,
        }

    def _check_abstract(self, abstract: str) -> Dict:
        """Check abstract compliance with MPEP 608.01(b)"""
        # Remove leading/trailing whitespace
        abstract = abstract.strip()

        # Count words
        words = abstract.split()
        word_count = len(words)

        # Count lines (approximate based on character count and typical line length)
        lines = abstract.split("\n")
        line_count = len(lines)

        # Check for patent claim language (should avoid)
        forbidden_terms = ["means", "said", "whereby"]
        found_forbidden = [term for term in forbidden_terms if re.search(rf"\b{re.escape(term)}\b", abstract, re.IGNORECASE)]

        result = {
            "word_count": word_count,
            "line_count": line_count,
            "compliant": True,
            "issues": [],
        }

        # Check word count
        if word_count < self.ABSTRACT_MIN_WORDS:
            self.issues.append(
                FormalityIssue(
                    section="abstract",
                    severity="WARNING",
                    problem="Abstract is too short",
                    current_value=f"{word_count} words",
                    required_value=f"{self.ABSTRACT_MIN_WORDS}-{self.ABSTRACT_MAX_WORDS} words",
                    fix=f"Expand abstract to at least {self.ABSTRACT_MIN_WORDS} words",
                    mpep_ref="MPEP 608.01(b)",
                )
            )
            result["compliant"] = False
            result["issues"].append("Too short")

        elif word_count > self.ABSTRACT_MAX_WORDS:
            self.issues.append(
                FormalityIssue(
                    section="abstract",
                    severity="WARNING",
                    problem="Abstract exceeds recommended length",
                    current_value=f"{word_count} words",
                    required_value=f"{self.ABSTRACT_MIN_WORDS}-{self.ABSTRACT_MAX_WORDS} words",
                    fix=f"Reduce abstract to {self.ABSTRACT_MAX_WORDS} words or less",
                    mpep_ref="MPEP 608.01(b)",
                )
            )
            result["compliant"] = False
            result["issues"].append("Too long")

        # Check line count
        if line_count > self.ABSTRACT_MAX_LINES:
            self.issues.append(
                FormalityIssue(
                    section="abstract",
                    severity="WARNING",
                    problem=f"Abstract exceeds {self.ABSTRACT_MAX_LINES} lines",
                    current_value=f"{line_count} lines",
                    required_value=f"<= {self.ABSTRACT_MAX_LINES} lines",
                    fix="Condense abstract to fit within 15 lines",
                    mpep_ref="MPEP 608.01(b)",
                )
            )
            result["compliant"] = False
            result["issues"].append("Too many lines")

        # Check for forbidden terms
        if found_forbidden:
            self.issues.append(
                FormalityIssue(
                    section="abstract",
                    severity="INFO",
                    problem="Abstract contains patent claim phraseology",
                    current_value=f'Contains: {", ".join(found_forbidden)}',
                    required_value='Should avoid "means", "said", "whereby"',
                    fix=f'Remove or rephrase to avoid: {", ".join(found_forbidden)}',
                    mpep_ref="MPEP 608.01(b)",
                )
            )
            result["issues"].append("Contains claim language")

        # Check paragraph structure (should be single paragraph)
        if "\n\n" in abstract:
            self.issues.append(
                FormalityIssue(
                    section="abstract",
                    severity="INFO",
                    problem="Abstract should be a single paragraph",
                    current_value="Multiple paragraphs",
                    required_value="Single paragraph",
                    fix="Combine into single paragraph",
                    mpep_ref="MPEP 608.01(b)",
                )
            )
            result["issues"].append("Multiple paragraphs")

        return result

    def _check_title(self, title: str) -> Dict:
        """Check title compliance with 37 CFR 1.72(a)"""
        title = title.strip()

        char_count = len(title)
        word_count = len(title.split())

        result = {
            "character_count": char_count,
            "word_count": word_count,
            "compliant": True,
            "issues": [],
        }

        # Check maximum length
        if char_count > self.TITLE_MAX_CHARS:
            self.issues.append(
                FormalityIssue(
                    section="title",
                    severity="CRITICAL",
                    problem="Title exceeds maximum length",
                    current_value=f"{char_count} characters",
                    required_value=f"<= {self.TITLE_MAX_CHARS} characters",
                    fix=f"Shorten title by {char_count - self.TITLE_MAX_CHARS} characters",
                    mpep_ref="37 CFR 1.72(a)",
                )
            )
            result["compliant"] = False
            result["issues"].append("Exceeds max length")

        # Recommend shorter title
        elif char_count > self.TITLE_RECOMMENDED_CHARS:
            self.issues.append(
                FormalityIssue(
                    section="title",
                    severity="INFO",
                    problem="Title is longer than recommended",
                    current_value=f"{char_count} characters",
                    required_value=f"<= {self.TITLE_RECOMMENDED_CHARS} characters (recommended)",
                    fix=f"Consider shortening by {char_count - self.TITLE_RECOMMENDED_CHARS} characters",
                    mpep_ref="MPEP 606",
                )
            )
            result["issues"].append("Could be shorter")

        # Check for articles at start (should capitalize)
        if title.lower().startswith(("a ", "an ", "the ")):
            self.issues.append(
                FormalityIssue(
                    section="title",
                    severity="INFO",
                    problem="Title starts with article",
                    current_value=f'Starts with "{title.split()[0]}"',
                    required_value="Articles should be capitalized in title",
                    fix="Ensure proper capitalization",
                    mpep_ref="MPEP 606",
                )
            )
            result["issues"].append("Starts with article")

        # Check for trademarked terms
        trademark_indicators = ["(TM)", "(R)", "(c)"]
        if any(tm in title for tm in trademark_indicators):
            self.issues.append(
                FormalityIssue(
                    section="title",
                    severity="WARNING",
                    problem="Title contains trademark symbols",
                    current_value="Contains (TM), (R), or (c)",
                    required_value="Should not include trademark symbols",
                    fix="Remove trademark symbols from title",
                    mpep_ref="MPEP 608.01(b)",
                )
            )
            result["compliant"] = False
            result["issues"].append("Contains trademarks")

        return result

    def _check_specification_sections(self, specification: str) -> Dict:
        """Check for required specification sections per 37 CFR 1.77"""
        required_sections = {
            "BACKGROUND": r"(?i)BACKGROUND(?:\s+OF)?(?:\s+THE)?(?:\s+INVENTION)?",
            "SUMMARY": r"(?i)(?:BRIEF\s+)?SUMMARY(?:\s+OF)?(?:\s+THE)?(?:\s+INVENTION)?",
            "BRIEF DESCRIPTION OF DRAWINGS": r"(?i)BRIEF\s+DESCRIPTION\s+OF\s+(?:THE\s+)?DRAWINGS?",
            "DETAILED DESCRIPTION": r"(?i)DETAILED\s+DESCRIPTION(?:\s+OF)?(?:\s+THE)?(?:\s+INVENTION)?",
        }

        found_sections = {}
        missing_sections = []

        for section_name, pattern in required_sections.items():
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

        # Add issues for missing sections
        for section in missing_sections:
            self.issues.append(
                FormalityIssue(
                    section="specification",
                    severity="CRITICAL",
                    problem=f"Missing required section: {section}",
                    current_value="Not found",
                    required_value="Must include all required sections",
                    fix=f'Add "{section}" section to specification',
                    mpep_ref="37 CFR 1.77",
                )
            )

        return result

    def _check_drawing_references(self, specification: str, drawings_present: bool) -> Dict:
        """Check drawing references and compliance"""

        # Extract figure references from specification
        fig_pattern = re.compile(
            r"FIGS?(?:URES?)?\.?\s*(\d+[A-Z]?(?:\([a-z]\))?(?:\s*-\s*\d+[A-Z]?)?)",
            re.IGNORECASE,
        )
        referenced_figures = set(fig_pattern.findall(specification))

        result = {
            "figures_referenced": sorted(list(referenced_figures)),
            "figure_count": len(referenced_figures),
            "drawings_provided": drawings_present,
            "compliant": True,
            "issues": [],
        }

        if referenced_figures:
            if not drawings_present:
                self.issues.append(
                    FormalityIssue(
                        section="drawings",
                        severity="CRITICAL",
                        problem=f"Specification references {len(referenced_figures)} figure(s) but drawings not provided",
                        current_value="No drawings",
                        required_value=f'Must include figures: {", ".join(sorted(referenced_figures))}',
                        fix="Create and include all referenced figures per 37 CFR 1.84",
                        mpep_ref="37 CFR 1.81",
                    )
                )
                result["compliant"] = False
                result["issues"].append("Missing drawings")

            # Check for BRIEF DESCRIPTION OF DRAWINGS section
            if not re.search(r"(?i)BRIEF\s+DESCRIPTION\s+OF\s+(?:THE\s+)?DRAWINGS?", specification):
                self.issues.append(
                    FormalityIssue(
                        section="drawings",
                        severity="CRITICAL",
                        problem='Figures referenced but "Brief Description of Drawings" section missing',
                        current_value="Section not found",
                        required_value='Must include "Brief Description of Drawings" section',
                        fix='Add "Brief Description of Drawings" section listing all figures',
                        mpep_ref="37 CFR 1.77(b)(3)",
                    )
                )
                result["compliant"] = False
                result["issues"].append("Missing figure description section")

        return result

    def _generate_compliance_summary(self, results: Dict) -> Dict:
        """Generate overall compliance summary"""
        total_checks = 0
        passed_checks = 0
        critical_issues = 0
        warnings = 0
        info = 0

        for issue in self.issues:
            total_checks += 1
            if issue.severity == "CRITICAL":
                critical_issues += 1
            elif issue.severity == "WARNING":
                warnings += 1
            else:
                info += 1

        # Count passed checks from results
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
            return "[OK] All formalities requirements met"

        parts = []
        if critical > 0:
            parts.append(f"{critical} CRITICAL")
        if warnings > 0:
            parts.append(f"{warnings} WARNING")
        if info > 0:
            parts.append(f"{info} INFO")

        return f"[WARNING] Found {', '.join(parts)} formality issue(s)"


# Example usage
if __name__ == "__main__":
    checker = FormalitiesChecker()

    # Test abstract
    abstract = """
    A system for AI-augmented document enhancement achieves 70-85% computational cost reduction
    through content-addressed multi-layer caching using per-file SHA-256 hash verification with
    automatic invalidation. The system maintains document continuity via a structured Knowledge Base.
    """

    # Test title
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
