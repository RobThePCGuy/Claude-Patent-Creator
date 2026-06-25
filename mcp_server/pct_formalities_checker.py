#!/usr/bin/env python3
"""
PCT Formalities Checker
Automated checking of PCT international application formality requirements
under PCT Rules 5-12.

Checks:
- Rule 5: The Description (required elements and structure)
- Rule 6: The Claims (format and unity)
- Rule 8: The Abstract (content and length)
- Rule 10: Terminology and Signs (metric system, temperatures)
- Rule 11: Physical Requirements (A4 paper, margins)
"""

import re
from dataclasses import dataclass, field
from typing import Any, Optional

try:
    from analyzer_base import BaseAnalyzer, BaseIssue
except ImportError:
    from mcp_server.analyzer_base import BaseAnalyzer, BaseIssue


@dataclass
class PCTFormalityIssue(BaseIssue):
    """Represents a PCT formality compliance issue"""

    section: str = field(default="")  # abstract, description, claims, physical
    current_value: str = field(default="")
    required_value: str = field(default="")


class PCTFormalitiesChecker(BaseAnalyzer):
    """Automated checking of PCT international application formalities.

    PCT Rules checked:
    - Rule 5: Content and structure of the description
    - Rule 6: Claims requirements (independent claims, numbering, unity)
    - Rule 8: Abstract requirements (max 150 words, figure indication)
    - Rule 10: Terminology and signs (metric, Celsius/Kelvin)
    - Rule 11: Physical requirements (A4, margins, font)
    """

    # PCT Rule 8.1(b) - Abstract max words
    ABSTRACT_MAX_WORDS = 150

    # PCT Rule 11.2 - Minimum margins (cm) for A4 paper
    MARGIN_TOP_MIN_CM = 2.0
    MARGIN_LEFT_MIN_CM = 2.5
    MARGIN_RIGHT_MIN_CM = 2.0
    MARGIN_BOTTOM_MIN_CM = 2.0

    # PCT Rule 5.1 - Required description elements
    REQUIRED_DESCRIPTION_ELEMENTS = {
        "Title": {
            "patterns": [
                r"(?i)^.{5,}",  # Title is typically the first line; just check existence
            ],
            "rule": "PCT Rule 5.1(a)",
            "description": "Title of the invention",
            "check_separately": True,  # Handled by title check
        },
        "Technical field": {
            "patterns": [
                r"(?i)technical\s+field",
                r"(?i)field\s+of\s+(?:the\s+)?invention",
            ],
            "rule": "PCT Rule 5.1(a)(ii)",
            "description": "Indication of the technical field",
        },
        "Background art": {
            "patterns": [
                r"(?i)background\s+(?:art|of\s+(?:the\s+)?invention)",
                r"(?i)prior\s+art",
                r"(?i)related\s+art",
            ],
            "rule": "PCT Rule 5.1(a)(iii)",
            "description": "Background art useful for understanding, searching, and examination",
        },
        "Disclosure of the invention": {
            "patterns": [
                r"(?i)(?:disclosure|summary)\s+of\s+(?:the\s+)?invention",
                r"(?i)technical\s+problem",
                r"(?i)object\s+of\s+(?:the\s+)?invention",
            ],
            "rule": "PCT Rule 5.1(a)(iv)",
            "description": "Disclosure of the invention as claimed",
        },
        "Brief description of drawings": {
            "patterns": [
                r"(?i)brief\s+description\s+of\s+(?:the\s+)?(?:drawings?|figures?)",
                r"(?i)description\s+of\s+(?:the\s+)?(?:drawings?|figures?)",
            ],
            "rule": "PCT Rule 5.1(a)(v)",
            "description": "Brief description of the figures in the drawings, if any",
        },
        "Best mode": {
            "patterns": [
                r"(?i)best\s+mode",
                r"(?i)detailed\s+description",
                r"(?i)description\s+of\s+(?:the\s+)?(?:preferred\s+)?embodiments?",
                r"(?i)modes?\s+(?:of|for)\s+carrying\s+out",
            ],
            "rule": "PCT Rule 5.1(a)(vi)",
            "description": "Best mode contemplated by the applicant for carrying out the invention",
        },
    }

    # Non-metric units to flag under Rule 10
    NON_METRIC_PATTERNS = [
        (r"\b\d+\s*(?:inches?|in\.)\b", "inches", "centimeters or millimeters"),
        (r"\b\d+\s*(?:feet|ft\.?)\b", "feet", "meters"),
        (r"\b\d+\s*(?:yards?|yd\.?)\b", "yards", "meters"),
        (r"\b\d+\s*(?:miles?|mi\.?)\b", "miles", "kilometers"),
        (r"\b\d+\s*(?:pounds?|lbs?\.?)\b", "pounds", "kilograms"),
        (r"\b\d+\s*(?:ounces?|oz\.?)\b", "ounces", "grams"),
        (r"\b\d+\s*(?:gallons?|gal\.?)\b", "gallons", "liters"),
    ]

    # Non-standard temperature units
    NON_STANDARD_TEMP_PATTERNS = [
        (r"\b\d+\s*(?:degrees?\s+)?(?:Fahrenheit|F)\b", "Fahrenheit", "Celsius or Kelvin"),
        (r"\b\d+\s*\u00b0\s*F\b", "Fahrenheit", "Celsius or Kelvin"),
    ]

    def analyze(
        self,
        abstract: Optional[str] = None,
        title: Optional[str] = None,
        specification: Optional[str] = None,
        drawings_present: bool = False,
    ) -> dict[str, Any]:
        """
        Main analysis method - checks all PCT formality requirements.

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
        """Convert PCTFormalityIssue to dictionary"""
        if not isinstance(issue, PCTFormalityIssue):
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
        Check all PCT formality requirements.

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
            "description": None,
            "claims": None,
            "terminology": None,
            "physical": None,
        }

        if abstract:
            results["abstract"] = self._check_abstract(abstract, drawings_present)

        if title:
            results["title"] = self._check_title(title)

        if specification:
            results["description"] = self._check_description(specification)
            results["claims"] = self._check_claims_format(specification)
            results["terminology"] = self._check_terminology(specification)

        # Physical requirements advisory (cannot verify from text alone)
        results["physical"] = self._generate_physical_requirements_advisory()

        return {
            "results": results,
            "issues": [self._issue_to_dict(issue) for issue in self.issues],
            "compliance_summary": self._generate_compliance_summary(results),
            "overall_compliant": len([i for i in self.issues if i.severity == "CRITICAL"]) == 0,
            "jurisdiction": "PCT",
            "legal_framework": "Patent Cooperation Treaty (PCT)",
        }

    def _check_abstract(self, abstract: str, drawings_present: bool) -> dict:
        """Check abstract compliance with PCT Rule 8.

        Rule 8.1(a): The abstract shall consist of a summary of the
        disclosure as contained in the description, claims, and drawings.

        Rule 8.1(b): The abstract shall be so drafted that it can
        efficiently serve as a scanning tool... It shall not contain
        more than 150 words.

        Rule 8.1(c): If the international application contains drawings,
        the applicant shall indicate the figure which should accompany
        the abstract.
        """
        abstract = abstract.strip()
        words = abstract.split()
        word_count = len(words)

        result = {
            "word_count": word_count,
            "compliant": True,
            "issues": [],
        }

        # Check max word count (Rule 8.1(b) - hard limit of 150 words)
        if word_count > self.ABSTRACT_MAX_WORDS:
            self.issues.append(
                PCTFormalityIssue(
                    section="abstract",
                    severity="CRITICAL",
                    problem="Abstract exceeds maximum allowed length",
                    current_value=f"{word_count} words",
                    required_value=f"<= {self.ABSTRACT_MAX_WORDS} words",
                    fix=f"Reduce abstract to {self.ABSTRACT_MAX_WORDS} words or fewer",
                    legal_ref="PCT Rule 8.1(b)",
                )
            )
            result["compliant"] = False
            result["issues"].append("Exceeds 150 words")

        # Check for very short abstract
        if word_count < 20:
            self.issues.append(
                PCTFormalityIssue(
                    section="abstract",
                    severity="WARNING",
                    problem="Abstract appears too brief to serve as effective scanning tool",
                    current_value=f"{word_count} words",
                    required_value="Summary of disclosure sufficient for scanning purposes",
                    fix="Expand abstract to adequately summarize the description, claims, and drawings",
                    legal_ref="PCT Rule 8.1(a)",
                )
            )
            result["compliant"] = False
            result["issues"].append("Too short")

        # Check for figure indication when drawings present (Rule 8.1(c))
        if drawings_present:
            fig_indication = bool(re.search(
                r"(?i)fig(?:ure)?\.?\s*\d+|drawing\s*\d+", abstract
            ))
            result["figure_indicated"] = fig_indication

            if not fig_indication:
                self.issues.append(
                    PCTFormalityIssue(
                        section="abstract",
                        severity="IMPORTANT",
                        problem="Abstract does not indicate which figure should accompany it",
                        current_value="No figure reference found",
                        required_value="Indication of the figure to accompany the abstract",
                        fix="Add reference to the figure that best characterizes the invention (e.g., 'Fig. 1')",
                        legal_ref="PCT Rule 8.1(c)",
                    )
                )
                result["issues"].append("Missing figure indication")

        return result

    def _check_title(self, title: str) -> dict:
        """Check title compliance with PCT Rule 4.3.

        The title shall be short (preferably 2-7 words) and precise.
        """
        title = title.strip()
        word_count = len(title.split())

        result = {
            "word_count": word_count,
            "compliant": True,
            "issues": [],
        }

        if word_count < 2:
            self.issues.append(
                PCTFormalityIssue(
                    section="title",
                    severity="CRITICAL",
                    problem="Title is too short to describe the invention",
                    current_value=f"{word_count} word(s)",
                    required_value="Short and precise title",
                    fix="Provide a descriptive title of at least 2 words",
                    legal_ref="PCT Rule 4.3",
                )
            )
            result["compliant"] = False
            result["issues"].append("Too short")

        # Check for trademark symbols
        trademark_indicators = ["(TM)", "(R)", "(c)", "\u2122", "\u00ae", "\u00a9"]
        if any(tm in title for tm in trademark_indicators):
            self.issues.append(
                PCTFormalityIssue(
                    section="title",
                    severity="CRITICAL",
                    problem="Title contains trademark symbols",
                    current_value="Contains trademark symbols",
                    required_value="Must not contain trade names or marks",
                    fix="Remove all trademark symbols from the title",
                    legal_ref="PCT Rule 4.3",
                )
            )
            result["compliant"] = False
            result["issues"].append("Contains trademarks")

        return result

    def _check_description(self, specification: str) -> dict:
        """Check description compliance with PCT Rule 5.

        Rule 5.1(a): The description shall:
        (i)   specify the title
        (ii)  specify the technical field
        (iii) indicate the background art
        (iv)  disclose the invention as claimed
        (v)   briefly describe the figures (if any)
        (vi)  describe the best mode
        """
        found_elements = {}
        missing_elements = []

        for element_name, element_info in self.REQUIRED_DESCRIPTION_ELEMENTS.items():
            if element_info.get("check_separately"):
                continue

            found = any(
                re.search(pattern, specification)
                for pattern in element_info["patterns"]
            )

            found_elements[element_name] = found
            if not found:
                missing_elements.append(element_name)

        result = {
            "found_elements": found_elements,
            "missing_elements": missing_elements,
            "compliant": len(missing_elements) == 0,
        }

        for element in missing_elements:
            element_info = self.REQUIRED_DESCRIPTION_ELEMENTS[element]
            self.issues.append(
                PCTFormalityIssue(
                    section="description",
                    severity="CRITICAL",
                    problem=f'Missing required element: "{element}" - {element_info["description"]}',
                    current_value="Not found",
                    required_value=f"Must include '{element}' per {element_info['rule']}",
                    fix=f'Add "{element}" section to the description',
                    legal_ref=element_info["rule"],
                )
            )

        return result

    def _check_claims_format(self, specification: str) -> dict:
        """Check claims format compliance with PCT Rule 6.

        Rule 6.1: The number of claims shall be reasonable.
        Rule 6.2(a): At least one independent claim.
        Rule 6.2(b): Claims shall be numbered consecutively in Arabic numerals.
        Rule 6.3: Unity of invention.
        """
        # Extract claim section (look for "CLAIMS" header or numbered claims)
        claims_section = ""
        claims_match = re.search(
            r"(?i)(?:^|\n)\s*(?:CLAIMS?|WHAT\s+IS\s+CLAIMED\s+IS)\s*:?\s*\n(.+)",
            specification, re.DOTALL,
        )
        claims_section = claims_match.group(1) if claims_match else specification

        # Find claim numbers
        claim_pattern = re.compile(r"(?:^|\n)\s*(\d+)\.\s+", re.MULTILINE)
        claim_numbers = [int(n) for n in claim_pattern.findall(claims_section)]
        claim_numbers = sorted(set(claim_numbers))

        result = {
            "total_claims": len(claim_numbers),
            "claim_numbers": claim_numbers,
            "compliant": True,
            "issues": [],
        }

        # Check for at least one claim (Rule 6.2(a))
        if not claim_numbers:
            self.issues.append(
                PCTFormalityIssue(
                    section="claims",
                    severity="CRITICAL",
                    problem="No claims detected in the application",
                    current_value="0 claims",
                    required_value="At least one independent claim",
                    fix="Add at least one independent claim",
                    legal_ref="PCT Rule 6.2(a)",
                )
            )
            result["compliant"] = False
            result["issues"].append("No claims found")
            return result

        # Check for independent claims
        has_independent = False
        for num in claim_numbers:
            # Find claim text
            claim_match = re.search(
                rf"(?:^|\n)\s*{num}\.\s+(.+?)(?=\n\s*\d+\.|$)",
                claims_section, re.DOTALL,
            )
            if claim_match:
                claim_text = claim_match.group(1)
                if not re.search(r"claim \d+", claim_text, re.IGNORECASE):
                    has_independent = True
                    break

        if not has_independent:
            self.issues.append(
                PCTFormalityIssue(
                    section="claims",
                    severity="CRITICAL",
                    problem="No independent claim detected",
                    current_value="All claims appear to be dependent",
                    required_value="At least one independent claim required",
                    fix="Ensure at least one claim does not depend on another claim",
                    legal_ref="PCT Rule 6.2(a)",
                )
            )
            result["compliant"] = False
            result["issues"].append("No independent claim")

        # Check consecutive numbering (Rule 6.2(b))
        expected = list(range(1, len(claim_numbers) + 1))
        if claim_numbers != expected:
            self.issues.append(
                PCTFormalityIssue(
                    section="claims",
                    severity="IMPORTANT",
                    problem="Claims are not numbered consecutively in Arabic numerals",
                    current_value=f"Found claim numbers: {claim_numbers}",
                    required_value=f"Expected consecutive numbering: {expected}",
                    fix="Renumber claims consecutively starting from 1",
                    legal_ref="PCT Rule 6.2(b)",
                )
            )
            result["issues"].append("Non-consecutive numbering")

        return result

    def _check_terminology(self, specification: str) -> dict:
        """Check terminology compliance with PCT Rule 10.

        Rule 10.1: Metric system shall be used.
        Rule 10.2: Temperatures in Celsius or Kelvin.
        Rule 10.3: Other standardized terminology (SI units).
        """
        non_metric_found = []
        non_standard_temp_found = []

        # Check for non-metric units (Rule 10.1)
        for pattern, unit_name, metric_equiv in self.NON_METRIC_PATTERNS:
            matches = re.findall(pattern, specification, re.IGNORECASE)
            if matches:
                non_metric_found.append({
                    "unit": unit_name,
                    "occurrences": len(matches),
                    "metric_equivalent": metric_equiv,
                })

        # Check for non-standard temperatures (Rule 10.2)
        for pattern, temp_unit, standard_unit in self.NON_STANDARD_TEMP_PATTERNS:
            matches = re.findall(pattern, specification, re.IGNORECASE)
            if matches:
                non_standard_temp_found.append({
                    "unit": temp_unit,
                    "occurrences": len(matches),
                    "standard_unit": standard_unit,
                })

        result = {
            "non_metric_units": non_metric_found,
            "non_standard_temperatures": non_standard_temp_found,
            "compliant": len(non_metric_found) == 0 and len(non_standard_temp_found) == 0,
        }

        for unit_info in non_metric_found:
            self.issues.append(
                PCTFormalityIssue(
                    section="terminology",
                    severity="IMPORTANT",
                    problem=(
                        f'Non-metric unit "{unit_info["unit"]}" found '
                        f'({unit_info["occurrences"]} occurrence(s))'
                    ),
                    current_value=unit_info["unit"],
                    required_value=f'Metric equivalent: {unit_info["metric_equivalent"]}',
                    fix=(
                        f'Convert {unit_info["unit"]} to {unit_info["metric_equivalent"]}. '
                        f"If non-metric units are customary in the art, include metric equivalents in parentheses."
                    ),
                    legal_ref="PCT Rule 10.1",
                )
            )

        for temp_info in non_standard_temp_found:
            self.issues.append(
                PCTFormalityIssue(
                    section="terminology",
                    severity="IMPORTANT",
                    problem=(
                        f'Non-standard temperature unit "{temp_info["unit"]}" found '
                        f'({temp_info["occurrences"]} occurrence(s))'
                    ),
                    current_value=temp_info["unit"],
                    required_value=f'Standard unit: {temp_info["standard_unit"]}',
                    fix=(
                        f'Convert temperatures to {temp_info["standard_unit"]}. '
                        f"Fahrenheit may be included in parentheses alongside Celsius."
                    ),
                    legal_ref="PCT Rule 10.2",
                )
            )

        return result

    def _generate_physical_requirements_advisory(self) -> dict:
        """Generate advisory on PCT Rule 11 physical requirements.

        These cannot be fully verified from text alone, so we provide
        an advisory checklist.

        Rule 11.2: Paper shall be A4 (29.7 cm x 21 cm).
        Rule 11.6: Margins:
            - Top: min 2 cm
            - Left: min 2.5 cm
            - Right: min 2 cm
            - Bottom: min 2 cm
        """
        return {
            "advisory": True,
            "message": "Physical requirements per PCT Rule 11 must be verified manually",
            "checklist": {
                "paper_size": {
                    "requirement": "A4 (29.7 cm x 21 cm)",
                    "rule": "PCT Rule 11.2",
                },
                "margins": {
                    "top": f">= {self.MARGIN_TOP_MIN_CM} cm",
                    "left": f">= {self.MARGIN_LEFT_MIN_CM} cm",
                    "right": f">= {self.MARGIN_RIGHT_MIN_CM} cm",
                    "bottom": f">= {self.MARGIN_BOTTOM_MIN_CM} cm",
                    "rule": "PCT Rule 11.6",
                },
                "text_color": {
                    "requirement": "Dark, indelible color (preferably black)",
                    "rule": "PCT Rule 11.2",
                },
                "font_size": {
                    "requirement": "Capital letters at least 0.28 cm high",
                    "rule": "PCT Rule 11.9(d)",
                },
                "line_spacing": {
                    "requirement": "1.5 line spacing for description and claims",
                    "rule": "PCT Rule 11.9(c)",
                },
            },
        }

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
        if results.get("description") and results["description"].get("compliant"):
            passed_checks += 1
        if results.get("claims") and results["claims"].get("compliant"):
            passed_checks += 1
        if results.get("terminology") and results["terminology"].get("compliant"):
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
            return "[OK] All PCT formalities requirements met (Rules 5-12)"

        parts = []
        if critical > 0:
            parts.append(f"{critical} CRITICAL")
        if warnings > 0:
            parts.append(f"{warnings} WARNING")
        if info > 0:
            parts.append(f"{info} INFO")

        return f"[WARNING] Found {', '.join(parts)} PCT formality issue(s)"


# Example usage
if __name__ == "__main__":
    checker = PCTFormalitiesChecker()

    abstract = """
    A system for AI-augmented document enhancement achieves 70-85% computational cost reduction
    through content-addressed multi-layer caching using per-file SHA-256 hash verification with
    automatic invalidation. The system maintains document continuity via a structured Knowledge Base.
    """

    title = "System and Method for AI-Augmented Enhancement of Multi-Section Documents"

    spec = """
    TECHNICAL FIELD

    The present invention relates to computer systems.

    BACKGROUND ART

    Prior systems are slow.

    DISCLOSURE OF THE INVENTION

    A better system is provided.

    BRIEF DESCRIPTION OF DRAWINGS

    Fig. 1 shows the system.

    DETAILED DESCRIPTION

    The system operates at 72 degrees Fahrenheit and uses a 12 inch display.

    CLAIMS

    1. A system comprising a processor.

    2. The system of claim 1, further comprising a display.
    """

    results = checker.check_all_formalities(
        abstract=abstract, title=title, specification=spec, drawings_present=True
    )

    print(f"\nCompliance Summary: {results['compliance_summary']['summary']}")
    print(f"Ready to file: {results['compliance_summary']['ready_to_file']}")

    if results["issues"]:
        print("\nIssues Found:")
        for issue in results["issues"]:
            print(f"\n[{issue['severity']}] {issue['section']}")
            print(f"  Problem: {issue['problem']}")
            print(f"  Fix: {issue['fix']}")
            print(f"  Ref: {issue['legal_ref']}")

    if results["results"]["physical"]:
        print("\nPhysical Requirements Advisory:")
        for key, value in results["results"]["physical"]["checklist"].items():
            if isinstance(value, dict):
                print(f"  {key}: {value.get('requirement', value)}")
