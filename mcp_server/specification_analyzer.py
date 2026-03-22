#!/usr/bin/env python3
"""
Specification Analyzer for 35 USC 112(a) Compliance
Checks written description and enablement support for patent claims
"""

import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict

try:
    from analyzer_base import BaseIssue, BaseAnalyzer
except ImportError:
    from mcp_server.analyzer_base import BaseIssue, BaseAnalyzer


@dataclass
class SupportIssue(BaseIssue):
    """Represents a specification support issue"""

    issue_type: str = field(default="")  # written_description, enablement, best_mode
    claim_number: int = field(default=0)
    claim_element: str = field(default="")
    spec_references: List[str] = field(default_factory=list)  # Paragraphs where element appears
    confidence: str = field(default="MEDIUM")  # Override default from BaseIssue


class SpecificationAnalyzer(BaseAnalyzer):
    """Analyzer for specification support of claims per 35 USC 112(a)"""

    def __init__(self):
        super().__init__()
        self.spec_paragraphs: Dict[int, str] = {}
        self.spec_index: Dict[str, List[int]] = defaultdict(list)  # term -> paragraph numbers

    def analyze(self, claims: List[Dict], specification: str) -> Dict[str, Any]:
        """
        Main analysis method - required by BaseAnalyzer

        Args:
            claims: Parsed claims from ClaimsAnalyzer
            specification: Full specification text

        Returns:
            Dictionary with analysis results
        """
        return self.analyze_specification_support(claims, specification)

    def _issue_to_dict(self, issue: BaseIssue) -> Dict[str, Any]:
        """Convert SupportIssue to dictionary"""
        if not isinstance(issue, SupportIssue):
            # Fallback for base issues
            return {
                "severity": issue.severity,
                "type": "",
                "claim": 0,
                "element": "",
                "problem": issue.problem,
                "spec_refs": [],
                "fix": issue.fix,
                "mpep": issue.mpep_ref,
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
            "mpep": issue.mpep_ref,
            "confidence": issue.confidence,
        }

    def analyze_specification_support(self, claims: List[Dict], specification: str) -> Dict:
        """
        Analyze whether specification provides adequate support for claims

        Args:
            claims: Parsed claims from ClaimsAnalyzer
            specification: Full specification text

        Returns:
            Dictionary with analysis results including input validation warnings
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
                    "message": f"Specification appears incomplete (only {word_count} words). "
                    f"Typical utility patents are 20,000-50,000 words. "
                    f"Analysis may be unreliable. Provide full specification text for accurate results.",
                }
            )

        # Parse and index specification
        self._index_specification(specification)

        if len(self.spec_paragraphs) < 10:
            warnings.append(
                {
                    "type": "incomplete_input",
                    "severity": "WARNING",
                    "message": f"Only {len(self.spec_paragraphs)} paragraphs detected. "
                    f"Full specifications typically have 50-200 paragraphs. "
                    f"Many claim elements may appear unsupported due to incomplete input.",
                }
            )

        # Check each claim for support
        for claim in claims:
            if claim["is_independent"]:
                self._check_claim_support(claim)

        return self._generate_report(claims, warnings)

    def _index_specification(self, specification: str):
        """Parse specification into paragraphs and build search index"""
        # Extract numbered paragraphs [0001], [0002], etc.
        para_pattern = re.compile(r"\[(\d+)\]\s*(.+?)(?=\[\d+\]|$)", re.DOTALL)
        matches = para_pattern.findall(specification)

        for para_num, para_text in matches:
            para_num = int(para_num)
            self.spec_paragraphs[para_num] = para_text.strip()

            # Index significant terms (nouns and technical terms)
            # Extract multi-word technical terms
            terms = self._extract_technical_terms(para_text)
            for term in terms:
                self.spec_index[term.lower()].append(para_num)

        # If no numbered paragraphs, try section-based parsing
        if not self.spec_paragraphs:
            self._index_by_sections(specification)

    def _index_by_sections(self, specification: str):
        """Fallback: index by sections if no numbered paragraphs"""
        sections = ["BACKGROUND", "SUMMARY", "BRIEF DESCRIPTION", "DETAILED DESCRIPTION"]

        para_num = 1

        for line in specification.split("\n"):
            line = line.strip()
            if not line:
                continue

            # Check if line is a section header
            is_header = any(section in line.upper() for section in sections)

            if is_header:
                continue

            # Add as paragraph
            self.spec_paragraphs[para_num] = line

            # Index terms
            terms = self._extract_technical_terms(line)
            for term in terms:
                self.spec_index[term.lower()].append(para_num)

            para_num += 1

    def _extract_technical_terms(self, text: str) -> List[str]:
        """Extract technical terms from text for indexing"""
        # Remove common words
        stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "as",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "should",
            "could",
            "may",
            "might",
            "must",
            "can",
            "this",
            "that",
            "these",
            "those",
            "it",
            "its",
            "they",
            "them",
            "their",
        }

        # Extract noun phrases (simplified - in production would use NLP)
        # Pattern for multi-word technical terms
        term_pattern = re.compile(r"\b([a-z][a-z\s-]{2,30}[a-z])\b", re.IGNORECASE)
        matches = term_pattern.findall(text)

        terms = []
        for match in matches:
            # Clean up term
            term = " ".join(match.split())
            term = term.lower()

            # Skip if all stopwords
            words = term.split()
            if not any(w not in stopwords for w in words):
                continue

            # Skip if too short
            if len(term) < 3:
                continue

            terms.append(term)

        return terms

    def _check_claim_support(self, claim: Dict):
        """Check if specification adequately supports a claim"""
        claim_num = claim["number"]
        claim_text = claim["text"]

        # Extract claim elements to check
        elements = self._extract_claim_elements(claim_text)

        # Check each element for specification support
        for element in elements:
            support_paras = self._find_specification_support(element)

            if not support_paras:
                # No support found - CRITICAL issue
                self.issues.append(
                    SupportIssue(
                        severity="CRITICAL",
                        issue_type="written_description",
                        claim_number=claim_num,
                        claim_element=element,
                        problem=f'Claim element "{element}" not found in specification',
                        spec_references=[],
                        fix=f'Add description of "{element}" to specification with sufficient detail',
                        mpep_ref="MPEP 2163 (35 USC 112(a) written description)",
                    )
                )

            elif len(support_paras) == 1:
                # Limited support - may need more detail
                self.issues.append(
                    SupportIssue(
                        severity="IMPORTANT",
                        issue_type="written_description",
                        claim_number=claim_num,
                        claim_element=element,
                        problem=f'Claim element "{element}" has limited description (only Para. {support_paras[0]})',
                        spec_references=[f"[{p:04d}]" for p in support_paras],
                        fix=f'Consider adding more detailed description of "{element}" for stronger support',
                        mpep_ref="MPEP 2163",
                    )
                )

        # Check for enablement (high-level check)
        self._check_enablement(claim)

    def _extract_claim_elements(self, claim_text: str) -> List[str]:
        """Extract key claim elements to verify in specification"""
        elements = []

        # Pattern for "a/an/the [element]" constructions
        element_pattern = re.compile(
            r"\b(?:a|an|the|said)\s+([a-z][a-z\s-]{2,40}?)(?=\s+(?:configured|comprising|wherein|that|for|to|with|is|are|which|having|including|and|connected|coupled|adapted|operable|operatively|communicatively)|(?=[,;.]))",
            re.IGNORECASE,
        )

        matches = element_pattern.finditer(claim_text)
        seen = set()

        for match in matches:
            element = match.group(1).strip()
            element = " ".join(element.split())  # Normalize whitespace
            element_lower = element.lower()

            # Skip very common/generic terms
            generic_terms = {
                "system",
                "method",
                "apparatus",
                "device",
                "computer",
                "processor",
                "memory",
                "module",
                "component",
                "unit",
            }

            if element_lower in generic_terms:
                continue

            # Skip if already seen
            if element_lower in seen:
                continue

            seen.add(element_lower)
            elements.append(element)

        return elements

    def _find_specification_support(self, element: str) -> List[int]:
        """Find paragraphs in specification that support claim element"""
        element_lower = element.lower()

        # Direct match in index
        if element_lower in self.spec_index:
            return sorted(self.spec_index[element_lower])

        # Try partial matches (substring search)
        matching_paras = set()

        # Search for element in paragraph text using word boundaries
        for para_num, para_text in self.spec_paragraphs.items():
            if re.search(r'\b' + re.escape(element_lower) + r'\b', para_text.lower()):
                matching_paras.add(para_num)

        # Try searching for individual words in multi-word elements
        if not matching_paras and " " in element:
            words = element.lower().split()
            significant_words = [word for word in words if len(word) > 3]
            # Require at least 2 significant words to match
            if significant_words:
                for para_num, para_text in self.spec_paragraphs.items():
                    para_lower = para_text.lower()
                    matches = sum(1 for word in significant_words if re.search(r'\b' + re.escape(word) + r'\b', para_lower))
                    if matches >= min(2, len(significant_words)):
                        matching_paras.add(para_num)

        return sorted(list(matching_paras))

    def _check_enablement(self, claim: Dict):
        """Check for potential enablement issues (high-level)"""
        claim_num = claim["number"]
        claim_text = claim["text"]

        # Check for overly broad functional language without structural support
        functional_terms = [
            "configured to",
            "operable to",
            "adapted to",
            "capable of",
            "designed to",
            "arranged to",
        ]

        for term in functional_terms:
            if term in claim_text.lower():
                # Extract the functional limitation
                pattern = re.compile(rf"{term}\s+([^,;\.]+)", re.IGNORECASE)
                matches = pattern.findall(claim_text)

                for func_desc in matches:
                    # Check if this function is described in specification
                    support_paras = self._find_specification_support(func_desc)

                    if not support_paras:
                        self.issues.append(
                            SupportIssue(
                                severity="IMPORTANT",
                                issue_type="enablement",
                                claim_number=claim_num,
                                claim_element=func_desc,
                                problem=f'Functional limitation "{term} {func_desc}" may lack enablement',
                                spec_references=[],
                                fix=f'Add detailed description of how to implement "{func_desc}"',
                                mpep_ref="MPEP 2164 (35 USC 112(a) enablement)",
                            )
                        )

    def _generate_report(self, claims: List[Dict], warnings: Optional[List[Dict]] = None) -> Dict:
        """Generate specification support analysis report with input validation warnings"""

        if warnings is None:
            warnings = []

        # Sort issues by severity and claim number
        self._sort_issues(secondary_key=lambda x: x.claim_number)

        # Count issues by type
        written_desc_issues = [i for i in self.issues if isinstance(i, SupportIssue) and i.issue_type == "written_description"]  # type: ignore[attr-defined]
        enablement_issues = [i for i in self.issues if isinstance(i, SupportIssue) and i.issue_type == "enablement"]  # type: ignore[attr-defined]

        # Use base class counting
        counts = self._count_by_severity()

        return {
            "specification_paragraphs": len(self.spec_paragraphs),
            "indexed_terms": len(self.spec_index),
            "total_issues": counts["total"],
            "critical_issues": counts["critical"],
            "important_issues": counts["important"],
            "written_description_issues": len(written_desc_issues),
            "enablement_issues": len(enablement_issues),
            "input_warnings": warnings,
            "issues": [self._issue_to_dict(issue) for issue in self.issues],
            "summary": self._generate_spec_summary(
                counts["critical"], counts["important"], warnings
            ),
            "compliant": counts["critical"] == 0 and len(warnings) == 0,
            "spec_coverage": self._calculate_coverage(claims),
        }

    def _calculate_coverage(self, claims: List[Dict]) -> Dict:
        """Calculate what percentage of independent claims have specification support"""
        independent_claims = [c for c in claims if c["is_independent"]]
        if not independent_claims:
            return {"percentage": 0, "supported_claims": 0, "total_claims": 0}

        # Count independent claims with no critical issues
        claims_with_critical = set(i.claim_number for i in self.issues if isinstance(i, SupportIssue) and i.severity == "CRITICAL")  # type: ignore[attr-defined]
        supported_claims = len(independent_claims) - len(claims_with_critical)

        return {
            "percentage": int((supported_claims / len(independent_claims)) * 100),
            "supported_claims": supported_claims,
            "total_claims": len(independent_claims),
            "unsupported_claims": list(claims_with_critical),
        }

    def _generate_spec_summary(self, critical: int, important: int, warnings: List[Dict]) -> str:
        """Generate human-readable summary including input warnings"""
        if critical == 0 and important == 0 and len(warnings) == 0:
            return "[OK] Specification provides adequate support for all claims"

        parts = []
        if len(warnings) > 0:
            parts.append(
                f"{len(warnings)} INPUT WARNING{'S' if len(warnings) != 1 else ''} (incomplete specification)"
            )
        if critical > 0:
            parts.append(f"{critical} CRITICAL issue{'s' if critical != 1 else ''}")
        if important > 0:
            parts.append(f"{important} IMPORTANT issue{'s' if important != 1 else ''}")

        return f"[WARNING] Found {', '.join(parts)} in specification support"


# Example usage
if __name__ == "__main__":
    # Sample claim
    sample_claim = {
        "number": 1,
        "text": "A computer system comprising: a) a cache manager; b) a hash generator; c) a novel widget configured to process data.",
        "is_independent": True,
        "depends_on": None,
    }

    # Sample specification
    sample_spec = """
    [0001] The present invention relates to computer systems with caching.

    [0002] The cache manager stores frequently accessed data. The hash generator
    computes cryptographic hashes using SHA-256.

    [0003] The system provides improved performance through content-addressed caching.
    """

    analyzer = SpecificationAnalyzer()
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
