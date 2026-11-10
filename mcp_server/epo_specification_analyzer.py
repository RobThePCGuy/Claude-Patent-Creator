#!/usr/bin/env python3
"""
EPO Specification Analyzer
Checks specification for Art. 83 EPC sufficiency of disclosure
and Rule 42 EPC required sections.

Art. 83 EPC: The European patent application shall disclose the invention
in a manner sufficiently clear and complete for it to be carried out by
a person skilled in the art.

Note: Art. 123(2) EPC (added matter) checking is not yet implemented.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

try:
    from analyzer_base import BaseAnalyzer, BaseIssue
except ImportError:
    from mcp_server.analyzer_base import BaseAnalyzer, BaseIssue


@dataclass
class EPOSpecSupportIssue(BaseIssue):
    """Represents an EPO specification support issue"""

    issue_type: str = field(default="")  # sufficiency, written_description, section_missing
    claim_number: int = field(default=0)
    claim_element: str = field(default="")
    spec_references: list[str] = field(default_factory=list)
    confidence: str = field(default="MEDIUM")


class EPOSpecificationAnalyzer(BaseAnalyzer):
    """Analyzer for EPO specification compliance.

    Checks:
    - Art. 83 EPC sufficiency of disclosure
    - Rule 42 EPC required description sections:
        (a) Technical field
        (b) Background art
        (c) Disclosure of the invention (technical problem + solution)
        (d) Brief description of drawings
        (e) Detailed description (at least one way of carrying out)
        (f) Industrial applicability (if not obvious)
    """

    # Rule 42(1) EPC required sections
    REQUIRED_SECTIONS = {
        "Technical field": {
            "patterns": [
                r"(?i)technical\s+field",
                r"(?i)field\s+of\s+(?:the\s+)?invention",
            ],
            "rule": "Rule 42(1)(a) EPC",
            "description": "Indication of the technical field to which the invention relates",
        },
        "Background art": {
            "patterns": [
                r"(?i)background\s+(?:art|of\s+(?:the\s+)?invention)",
                r"(?i)prior\s+art",
                r"(?i)related\s+art",
            ],
            "rule": "Rule 42(1)(b) EPC",
            "description": "Background art known to the applicant, with document citations",
        },
        "Disclosure of the invention": {
            "patterns": [
                r"(?i)(?:disclosure|summary)\s+of\s+(?:the\s+)?invention",
                r"(?i)technical\s+problem",
                r"(?i)object\s+of\s+(?:the\s+)?invention",
            ],
            "rule": "Rule 42(1)(c) EPC",
            "description": "Disclosure of the invention (technical problem and solution)",
        },
        "Brief description of drawings": {
            "patterns": [
                r"(?i)brief\s+description\s+of\s+(?:the\s+)?(?:drawings?|figures?)",
                r"(?i)description\s+of\s+(?:the\s+)?(?:drawings?|figures?)",
            ],
            "rule": "Rule 42(1)(d) EPC",
            "description": "Brief description of the figures in the drawings, if any",
        },
        "Detailed description": {
            "patterns": [
                r"(?i)detailed\s+description",
                r"(?i)description\s+of\s+(?:the\s+)?(?:preferred\s+)?embodiments?",
                r"(?i)modes?\s+(?:of|for)\s+carrying\s+out\s+(?:the\s+)?invention",
                r"(?i)best\s+mode",
            ],
            "rule": "Rule 42(1)(e) EPC",
            "description": "Detailed description of at least one way of carrying out the invention",
        },
        "Industrial applicability": {
            "patterns": [
                r"(?i)industrial\s+applicab",
                r"(?i)(?:technical\s+)?application\s+(?:of|in)\s+industry",
            ],
            "rule": "Rule 42(1)(f) EPC",
            "description": "Indication of how the invention can be made and used in industry",
        },
    }

    def __init__(self):
        super().__init__()
        self.spec_paragraphs: dict[int, str] = {}
        self.spec_index: dict[str, list[int]] = defaultdict(list)

    def analyze(self, claims: list[dict], specification: str) -> dict[str, Any]:
        """
        Main analysis method - required by BaseAnalyzer

        Args:
            claims: Parsed claims (list of claim dicts)
            specification: Full specification text

        Returns:
            Dictionary with analysis results
        """
        return self.analyze_specification_support(claims, specification)

    def _issue_to_dict(self, issue: BaseIssue) -> dict[str, Any]:
        """Convert EPOSpecSupportIssue to dictionary"""
        if not isinstance(issue, EPOSpecSupportIssue):
            return {
                "severity": issue.severity,
                "type": "",
                "claim": 0,
                "element": "",
                "problem": issue.problem,
                "spec_refs": [],
                "fix": issue.fix,
                "legal_ref": issue.legal_ref,
                "confidence": issue.confidence,
            }
        return {
            "severity": issue.severity,
            "type": issue.issue_type,
            "claim": issue.claim_number,
            "element": issue.claim_element,
            "problem": issue.problem,
            "spec_refs": issue.spec_references,
            "fix": issue.fix,
            "legal_ref": issue.legal_ref,
            "confidence": issue.confidence,
        }

    def analyze_specification_support(self, claims: list[dict], specification: str) -> dict:
        """
        Analyze whether specification meets Art. 83 EPC sufficiency
        and Rule 42 EPC structural requirements.

        Args:
            claims: Parsed claims from a claims analyzer
            specification: Full specification text

        Returns:
            Dictionary with analysis results
        """
        self.issues = []
        self.spec_paragraphs = {}
        self.spec_index = defaultdict(list)

        # Validate input completeness
        warnings = []
        word_count = len(specification.split())

        if word_count < 1000:
            warnings.append(
                {
                    "type": "incomplete_input",
                    "severity": "WARNING",
                    "message": (
                        f"Specification appears incomplete (only {word_count} words). "
                        f"Typical European patent applications are 10,000-40,000 words. "
                        f"Analysis may be unreliable. Provide full specification text for accurate results."
                    ),
                }
            )

        # Check Rule 42 EPC required sections
        self._check_required_sections(specification)

        # Parse and index specification
        self._index_specification(specification)

        if len(self.spec_paragraphs) < 10:
            warnings.append(
                {
                    "type": "incomplete_input",
                    "severity": "WARNING",
                    "message": (
                        f"Only {len(self.spec_paragraphs)} paragraphs detected. "
                        f"Full specifications typically have 50-200 paragraphs. "
                        f"Many claim elements may appear unsupported due to incomplete input."
                    ),
                }
            )

        # Check every claim, including limitations added by dependent claims
        for claim in claims:
            self._check_claim_support(claim)

        return self._generate_report(claims, warnings)

    def _check_required_sections(self, specification: str):
        """Check for Rule 42 EPC required description sections"""
        for section_name, section_info in self.REQUIRED_SECTIONS.items():
            found = any(
                re.search(pattern, specification)
                for pattern in section_info["patterns"]
            )

            if not found:
                # Industrial applicability is only required if not obvious
                severity = "IMPORTANT" if section_name == "Industrial applicability" else "CRITICAL"

                self.issues.append(
                    EPOSpecSupportIssue(
                        severity=severity,
                        issue_type="section_missing",
                        claim_number=0,
                        claim_element="",
                        problem=f'Missing required section: "{section_name}" - {section_info["description"]}',
                        spec_references=[],
                        fix=f'Add a "{section_name}" section to the description per {section_info["rule"]}',
                        legal_ref=section_info["rule"],
                        confidence="HIGH",
                    )
                )

    def _index_specification(self, specification: str):
        """Parse specification into paragraphs and build search index"""
        # Extract numbered paragraphs [0001], [0002], etc.
        para_pattern = re.compile(r"\[(\d+)\]\s*(.+?)(?=\[\d+\]|$)", re.DOTALL)
        matches = para_pattern.findall(specification)

        for para_num, para_text in matches:
            para_num = int(para_num)
            self.spec_paragraphs[para_num] = para_text.strip()

            terms = self._extract_technical_terms(para_text)
            for term in terms:
                self.spec_index[term.lower()].append(para_num)

        # Fallback: parse by sections if no numbered paragraphs
        if not self.spec_paragraphs:
            self._index_by_sections(specification)

    def _index_by_sections(self, specification: str):
        """Fallback: index by sections if no numbered paragraphs"""
        sections = [
            "TECHNICAL FIELD", "BACKGROUND", "SUMMARY", "DISCLOSURE",
            "BRIEF DESCRIPTION", "DETAILED DESCRIPTION", "INDUSTRIAL APPLICABILITY",
        ]

        para_num = 1
        for line in specification.split("\n"):
            line = line.strip()
            if not line:
                continue

            is_header = any(section in line.upper() for section in sections)
            if is_header:
                continue

            self.spec_paragraphs[para_num] = line

            terms = self._extract_technical_terms(line)
            for term in terms:
                self.spec_index[term.lower()].append(para_num)

            para_num += 1

    def _extract_technical_terms(self, text: str) -> list[str]:
        """Extract technical terms from text for indexing"""
        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "from", "as", "is", "are", "was",
            "were", "be", "been", "being", "have", "has", "had", "do",
            "does", "did", "will", "would", "should", "could", "may",
            "might", "must", "can", "this", "that", "these", "those",
            "it", "its", "they", "them", "their",
        }

        term_pattern = re.compile(r"\b([a-z][a-z\s-]{2,30}[a-z])\b", re.IGNORECASE)
        matches = term_pattern.findall(text)

        terms = []
        for match in matches:
            term = " ".join(match.split()).lower()
            words = term.split()
            if not any(w not in stopwords for w in words):
                continue
            if len(term) < 3:
                continue
            terms.append(term)

        return terms

    def _check_claim_support(self, claim: dict):
        """Check if specification provides Art. 83 EPC sufficiency for a claim"""
        claim_num = claim["number"]
        claim_text = claim["text"]

        # Extract claim elements
        elements = self._extract_claim_elements(claim_text)

        # Check each element for specification support
        for element in elements:
            support_paras = self._find_specification_support(element)

            if not support_paras:
                self.issues.append(
                    EPOSpecSupportIssue(
                        severity="CRITICAL",
                        issue_type="sufficiency",
                        claim_number=claim_num,
                        claim_element=element,
                        problem=f'Claim element "{element}" not found in description',
                        spec_references=[],
                        fix=(
                            f'Add description of "{element}" to the specification with sufficient '
                            f"detail for a person skilled in the art to carry out the invention"
                        ),
                        legal_ref="Art. 83 EPC",
                    )
                )
            elif len(support_paras) == 1:
                self.issues.append(
                    EPOSpecSupportIssue(
                        severity="IMPORTANT",
                        issue_type="sufficiency",
                        claim_number=claim_num,
                        claim_element=element,
                        problem=(
                            f'Claim element "{element}" has limited description '
                            f"(only Para. {support_paras[0]})"
                        ),
                        spec_references=[f"[{p:04d}]" for p in support_paras],
                        fix=(
                            f'Consider adding more detailed description of "{element}" '
                            f"for stronger Art. 83 support"
                        ),
                        legal_ref="Art. 83 EPC",
                    )
                )

        # Check for sufficiency of functional claims
        self._check_functional_sufficiency(claim)

    def _extract_claim_elements(self, claim_text: str) -> list[str]:
        """Extract key claim elements to verify in specification"""
        elements = []

        element_pattern = re.compile(
            r"\b(?:a|an|the|said)\s+([a-z][a-z\s-]{2,40}?)(?=\s+(?:configured|comprising|wherein|that|for|to|with|is|are|which|having|including|and|connected|coupled|adapted|operable|operatively|communicatively)|(?=[,;.]))",
            re.IGNORECASE,
        )

        matches = element_pattern.finditer(claim_text)
        seen = set()

        for match in matches:
            element = match.group(1).strip()
            element = " ".join(element.split())
            element_lower = element.lower()

            generic_terms = {
                "system", "method", "apparatus", "device", "computer",
                "processor", "memory", "module", "component", "unit",
                "means", "step", "element",
            }

            if element_lower in generic_terms:
                continue
            if element_lower in seen:
                continue

            seen.add(element_lower)
            elements.append(element)

        return elements

    def _find_specification_support(self, element: str) -> list[int]:
        """Find paragraphs in specification that support claim element"""
        element_lower = element.lower()

        # Direct match in index
        if element_lower in self.spec_index:
            return sorted(self.spec_index[element_lower])

        # Substring search in paragraph text
        matching_paras = set()
        for para_num, para_text in self.spec_paragraphs.items():
            if re.search(r'\b' + re.escape(element_lower) + r'\b', para_text.lower()):
                matching_paras.add(para_num)

        # Multi-word partial matching
        if not matching_paras and " " in element:
            words = element.lower().split()
            significant_words = [word for word in words if len(word) > 3]
            if significant_words:
                for para_num, para_text in self.spec_paragraphs.items():
                    para_lower = para_text.lower()
                    matches = sum(
                        1 for word in significant_words
                        if re.search(r'\b' + re.escape(word) + r'\b', para_lower)
                    )
                    if matches >= min(2, len(significant_words)):
                        matching_paras.add(para_num)

        return sorted(matching_paras)

    def _check_functional_sufficiency(self, claim: dict):
        """Check Art. 83 sufficiency for functional claim language"""
        claim_num = claim["number"]
        claim_text = claim["text"]

        functional_terms = [
            "configured to", "operable to", "adapted to",
            "capable of", "designed to", "arranged to",
        ]

        for term in functional_terms:
            if term in claim_text.lower():
                pattern = re.compile(rf"{term}\s+([^,;\.]+)", re.IGNORECASE)
                matches = pattern.findall(claim_text)

                for func_desc in matches:
                    support_paras = self._find_specification_support(func_desc)

                    if not support_paras:
                        self.issues.append(
                            EPOSpecSupportIssue(
                                severity="IMPORTANT",
                                issue_type="sufficiency",
                                claim_number=claim_num,
                                claim_element=func_desc,
                                problem=(
                                    f'Functional limitation "{term} {func_desc}" may lack '
                                    f"sufficient disclosure for a skilled person to carry out"
                                ),
                                spec_references=[],
                                fix=f'Add detailed description of how to implement "{func_desc}"',
                                legal_ref="Art. 83 EPC",
                            )
                        )

    def _generate_report(self, claims: list[dict], warnings: Optional[list[dict]] = None) -> dict:
        """Generate EPO specification support analysis report"""
        if warnings is None:
            warnings = []

        # Sort issues by severity and claim number
        self._sort_issues(secondary_key=lambda x: x.claim_number)

        # Count issues by type
        sufficiency_issues = [
            i for i in self.issues
            if isinstance(i, EPOSpecSupportIssue) and i.issue_type == "sufficiency"
        ]
        section_issues = [
            i for i in self.issues
            if isinstance(i, EPOSpecSupportIssue) and i.issue_type == "section_missing"
        ]

        counts = self._count_by_severity()

        return {
            "specification_paragraphs": len(self.spec_paragraphs),
            "indexed_terms": len(self.spec_index),
            "total_issues": counts["total"],
            "critical_issues": counts["critical"],
            "important_issues": counts["important"],
            "sufficiency_issues": len(sufficiency_issues),
            "section_issues": len(section_issues),
            "input_warnings": warnings,
            "issues": [self._issue_to_dict(issue) for issue in self.issues],
            "summary": self._generate_spec_summary(
                counts["critical"], counts["important"], warnings
            ),
            "compliant": counts["critical"] == 0 and len(warnings) == 0,
            "spec_coverage": self._calculate_coverage(claims),
            "jurisdiction": "EPO",
            "legal_framework": "European Patent Convention (EPC)",
        }

    def _calculate_coverage(self, claims: list[dict]) -> dict:
        """Calculate support coverage across all supplied claims"""
        claim_numbers = {c["number"] for c in claims}
        if not claim_numbers:
            return {"percentage": 0, "supported_claims": 0, "total_claims": 0}

        claims_with_critical = {
            i.claim_number for i in self.issues
            if isinstance(i, EPOSpecSupportIssue) and i.severity == "CRITICAL" and i.issue_type == "sufficiency"
        }
        claims_with_critical &= claim_numbers
        supported_claims = len(claim_numbers) - len(claims_with_critical)

        return {
            "percentage": int((supported_claims / len(claim_numbers)) * 100),
            "supported_claims": supported_claims,
            "total_claims": len(claim_numbers),
            "unsupported_claims": list(claims_with_critical),
        }

    def _generate_spec_summary(self, critical: int, important: int, warnings: list[dict]) -> str:
        """Generate human-readable summary"""
        if critical == 0 and important == 0 and len(warnings) == 0:
            return "[OK] Specification provides sufficient disclosure under Art. 83 EPC"

        parts = []
        if len(warnings) > 0:
            parts.append(
                f"{len(warnings)} INPUT WARNING{'S' if len(warnings) != 1 else ''} (incomplete specification)"
            )
        if critical > 0:
            parts.append(f"{critical} CRITICAL issue{'s' if critical != 1 else ''}")
        if important > 0:
            parts.append(f"{important} IMPORTANT issue{'s' if important != 1 else ''}")

        return f"[WARNING] Found {', '.join(parts)} in Art. 83 EPC sufficiency analysis"


# Example usage
if __name__ == "__main__":
    sample_claim = {
        "number": 1,
        "text": "A computer system comprising: a) a cache manager; b) a hash generator; c) a novel widget configured to process data.",
        "is_independent": True,
        "depends_on": None,
    }

    sample_spec = """
    TECHNICAL FIELD

    [0001] The present invention relates to computer systems with caching.

    BACKGROUND ART

    [0002] Prior systems use basic caching mechanisms.

    DISCLOSURE OF THE INVENTION

    [0003] The cache manager stores frequently accessed data. The hash generator
    computes cryptographic hashes using SHA-256.

    DETAILED DESCRIPTION

    [0004] The system provides improved performance through content-addressed caching.
    """

    analyzer = EPOSpecificationAnalyzer()
    results = analyzer.analyze_specification_support([sample_claim], sample_spec)

    print(f"\nAnalysis: {results['summary']}")
    print(f"Specification coverage: {results['spec_coverage']['percentage']}%")
    print(
        f"Indexed {results['indexed_terms']} terms from {results['specification_paragraphs']} paragraphs"
    )

    if results["issues"]:
        print("\nIssues Found:")
        for issue in results["issues"]:
            print(f"\n[{issue['severity']}] Claim {issue['claim']}: {issue['element']}")
            print(f"  Problem: {issue['problem']}")
            if issue["spec_refs"]:
                print(f"  Found in: {', '.join(issue['spec_refs'])}")
            print(f"  Fix: {issue['fix']}")
            print(f"  Ref: {issue['legal_ref']}")
