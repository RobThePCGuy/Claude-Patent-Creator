#!/usr/bin/env python3
"""
Advanced Patent Claims Analyzer
Performs automated analysis of patent claims for 35 USC 112(b) compliance
Based on research from plint, cgupatent/antecedent-check, and PEDANTIC
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
class ClaimIssue(BaseIssue):
    """Represents a specific issue found in a claim"""

    issue_type: str = field(default="")  # antecedent_basis, definiteness, etc.
    claim_number: int = field(default=0)
    location: str = field(default="")  # e.g., "limitation (c)(ii)"
    term: str = field(default="")


class ClaimsAnalyzer(BaseAnalyzer):
    """Automated patent claims analyzer with antecedent basis checking"""

    # Regex patterns based on plint and research
    NEW_ELEMENT_PATTERN = re.compile(
        r"\b(a|an|at least one|one or more|more than one|two or more|"
        r"plurality of|one|two|three|four|five|six|seven|eight|nine|ten)\s+([a-z][a-z\s-]+?)(?=\s+(?:configured|comprising|wherein|that|for|to|with|,|;|\.))",
        re.IGNORECASE,
    )

    THE_ELEMENT_PATTERN = re.compile(
        r"\bthe\s+([a-z][a-z\s-]+?)(?=\s+(?:configured|comprising|wherein|that|for|to|with|is|are|was|were|,|;|\.))",
        re.IGNORECASE,
    )

    SAID_ELEMENT_PATTERN = re.compile(
        r"\bsaid\s+([a-z][a-z\s-]+?)(?=\s+(?:configured|comprising|wherein|that|for|to|with|is|are|was|were|,|;|\.))",
        re.IGNORECASE,
    )

    # Subjective/indefinite terms from MPEP 2173.05(b)
    SUBJECTIVE_TERMS = {
        "subtle": "subjective, lacks objective criteria",
        "minimal": "subjective, lacks quantification",
        "substantial": "subjective unless defined",
        "significant": "subjective unless defined",
        "efficient": "subjective unless defined",
        "optimal": "subjective unless defined",
        "suitable": "subjective unless defined",
        "appropriate": "subjective unless defined",
        "effective": "subjective unless defined",
        "adequate": "subjective unless defined",
        "satisfactory": "subjective unless defined",
        "good": "subjective, lacks objective criteria",
        "better": "subjective, lacks objective criteria",
        "best": "subjective, lacks objective criteria",
        "high": "relative term, lacks quantification",
        "low": "relative term, lacks quantification",
        "large": "relative term, lacks quantification",
        "small": "relative term, lacks quantification",
        "strong": "relative term, lacks quantification",
        "weak": "relative term, lacks quantification",
    }

    # Relative terms that may need quantification
    RELATIVE_TERMS = {
        "about",
        "approximately",
        "substantially",
        "essentially",
        "generally",
        "typically",
        "normally",
        "usually",
    }

    def analyze(self, text: str) -> dict:
        """
        Required implementation of BaseAnalyzer.analyze

        Args:
            text: Full claims section text

        Returns:
            Dictionary with analysis results and issues
        """
        return self.analyze_claims(text)

    def analyze_claims(self, claims_text: str) -> dict:
        """
        Main analysis entry point

        Args:
            claims_text: Full claims section text

        Returns:
            Dictionary with analysis results and issues
        """
        self.issues = []

        # Parse claims into structured format
        claims = self._parse_claims(claims_text)

        # Run all checks
        for claim in claims:
            self._check_antecedent_basis(claim, claims)
            self._check_definiteness(claim)
            self._check_subjective_terms(claim)
            self._check_internal_references(claim)
            self._check_structure(claim)

        # Generate summary
        return self._generate_report(claims)

    def _parse_claims(self, claims_text: str) -> list[dict]:
        """Parse claims text into structured format"""
        claims = []

        # Split by claim numbers (e.g., "1.", "2.", "10.")
        claim_pattern = re.compile(r"(?:^|\n)(\d+)\.\s+(.+?)(?=\n\d+\.|$)", re.DOTALL)
        matches = claim_pattern.findall(claims_text)

        for claim_num, claim_body in matches:
            claim = {
                "number": int(claim_num),
                "text": claim_body.strip(),
                "is_independent": not bool(re.search(r"claim \d+", claim_body, re.IGNORECASE)),
                "depends_on": None,
                "elements": {},
                "limitations": [],
            }

            # Check for dependency
            dep_match = re.search(r"claim (\d+)", claim_body, re.IGNORECASE)
            if dep_match:
                dep_num = int(dep_match.group(1))
                if dep_num != int(claim_num):  # Prevent self-referencing
                    claim["depends_on"] = dep_num

            # Extract limitations (a), (b), (c), etc.
            lim_pattern = re.compile(r"\n\s*([a-z])\)\s+(.+?)(?=\n\s*[a-z]\)|$)", re.DOTALL)
            limitations = lim_pattern.findall(claim_body)
            claim["limitations"] = [(letter, text.strip()) for letter, text in limitations]

            claims.append(claim)

        return claims

    def _check_antecedent_basis(self, claim: dict, all_claims: list[dict]):
        """
        Check for antecedent basis errors

        NOTE: This is a SIMPLIFIED checker that produces false positives.
        It does NOT understand:
        - Preamble scope (e.g., "A computer system" introduces "the system")
        - Contextual references (e.g., "the change" in evaluation contexts)
        - Implicit antecedents from compound nouns

        All findings are marked LOW confidence and require manual verification.
        """
        # Antecedent basis checking is opt-in via environment variable.
        # Known limitations (see PEDANTIC dataset, arxiv.org/html/2505.21342):
        # - Regex approach cannot parse claim structure (preamble vs body vs wherein)
        # - Cannot track antecedent scope across limitations
        # - ML approaches (DeBERTa) achieve only ~14.5% F1 on real USPTO rejections
        # - High false positive rate is inherent to pattern-matching approaches
        #
        # When enabled, all findings are emitted at LOW confidence requiring manual review.
        # Enable with: PATENT_ENABLE_ANTECEDENT_CHECK=1
        import os

        if os.environ.get("PATENT_ENABLE_ANTECEDENT_CHECK", "").strip() not in ("1", "true", "yes"):
            return

        claim_text = claim["text"]
        claim_num = claim["number"]

        # Build element registry from this claim and dependencies
        known_elements = self._build_element_registry(claim, all_claims)

        # Find all "the X" references
        the_matches = self.THE_ELEMENT_PATTERN.finditer(claim_text)
        for match in the_matches:
            element = self._normalize_element(match.group(1))

            if element not in known_elements:
                # Check for plural/singular mismatch
                singular = self._singularize(element)
                plural = self._pluralize(element)

                if singular not in known_elements and plural not in known_elements:
                    self.issues.append(
                        ClaimIssue(
                            severity="IMPORTANT",  # Downgraded from CRITICAL due to low precision
                            issue_type="antecedent_basis",
                            claim_number=claim_num,
                            location=self._find_limitation_location(claim, match.start()),
                            term=f"the {element}",
                            problem=f'POSSIBLE antecedent basis issue: "the {element}" may lack proper introduction',
                            fix=f'MANUAL VERIFICATION REQUIRED: Check if "{element}" is properly introduced earlier. Tool has high false positive rate.',
                            legal_ref="MPEP 2173.05(e)",
                            confidence="LOW",  # Low confidence - manual verification required
                        )
                    )

        # Check "said X" references
        said_matches = self.SAID_ELEMENT_PATTERN.finditer(claim_text)
        for match in said_matches:
            element = self._normalize_element(match.group(1))

            if element not in known_elements:
                self.issues.append(
                    ClaimIssue(
                        severity="IMPORTANT",  # Downgraded from CRITICAL due to low precision
                        issue_type="antecedent_basis",
                        claim_number=claim_num,
                        location=self._find_limitation_location(claim, match.start()),
                        term=f"said {element}",
                        problem=f'POSSIBLE antecedent basis issue: "said {element}" may lack proper introduction',
                        fix=f'MANUAL VERIFICATION REQUIRED: Check if "{element}" is properly introduced earlier. Tool has high false positive rate.',
                        legal_ref="MPEP 2173.05(e)",
                        confidence="LOW",  # Low confidence - manual verification required
                    )
                )

    def _build_element_registry(self, claim: dict, all_claims: list[dict], visited: Optional[set[int]] = None) -> set[str]:
        """Build set of all known elements from claim and its dependencies"""
        if visited is None:
            visited = set()

        known = set()

        # Guard against circular dependency chains
        if claim["number"] in visited:
            return known
        visited.add(claim["number"])

        # Add elements from dependent claims
        if claim["depends_on"]:
            parent = next((c for c in all_claims if c["number"] == claim["depends_on"]), None)
            if parent:
                known.update(self._build_element_registry(parent, all_claims, visited))

        # Extract new elements from this claim
        new_matches = self.NEW_ELEMENT_PATTERN.finditer(claim["text"])
        for match in new_matches:
            element = self._normalize_element(match.group(2))
            known.add(element)

        return known

    def _check_definiteness(self, claim: dict):
        """Check for definiteness issues under 35 USC 112(b)"""
        claim_text = claim["text"].lower()
        claim_num = claim["number"]

        # Check for vague claim scope
        vague_phrases = [
            ("or the like", "open-ended phrase may render claim indefinite"),
            ("such as", "may create ambiguity if not clearly limiting"),
            ("including but not limited to", "may render claim indefinite"),
            ("etc.", "abbreviation renders claim indefinite"),
            ("and/or", 'may create ambiguity (use "at least one of")'),
        ]

        for phrase, reason in vague_phrases:
            if phrase in claim_text:
                self.issues.append(
                    ClaimIssue(
                        severity="IMPORTANT",
                        issue_type="definiteness",
                        claim_number=claim_num,
                        location=self._find_phrase_location(claim, phrase),
                        term=phrase,
                        problem=f'Phrase "{phrase}" - {reason}',
                        fix=f'Remove "{phrase}" or replace with specific language',
                        legal_ref="MPEP 2173.05(d)",
                    )
                )

    def _check_subjective_terms(self, claim: dict):
        """Check for subjective terms that may render claim indefinite"""
        claim_text = claim["text"].lower()
        claim_num = claim["number"]

        for term, reason in self.SUBJECTIVE_TERMS.items():
            # Use word boundaries to avoid partial matches
            pattern = re.compile(r"\b" + term + r"\b", re.IGNORECASE)
            if pattern.search(claim_text):
                self.issues.append(
                    ClaimIssue(
                        severity="IMPORTANT",
                        issue_type="subjective_term",
                        claim_number=claim_num,
                        location=self._find_phrase_location(claim, term),
                        term=term,
                        problem=f'Subjective term "{term}" - {reason}',
                        fix="Replace with objective, measurable criteria or quantitative values",
                        legal_ref="MPEP 2173.05(b)",
                        confidence="HIGH",  # Objective pattern matching - reliable
                    )
                )

    def _check_internal_references(self, claim: dict):
        """Check for problematic internal cross-references"""
        claim_text = claim["text"]
        claim_num = claim["number"]

        # Check for internal cross-references like "as defined in subsection (h)(ii)"
        internal_ref_pattern = re.compile(
            r"as defined in (?:subsection|section|paragraph|limitation)\s+\(([a-z])\)(?:\(([ivx]+)\))?",
            re.IGNORECASE,
        )

        matches = internal_ref_pattern.finditer(claim_text)
        for match in matches:
            self.issues.append(
                ClaimIssue(
                    severity="IMPORTANT",
                    issue_type="internal_reference",
                    claim_number=claim_num,
                    location=self._find_limitation_location(claim, match.start()),
                    term=match.group(0),
                    problem="Internal cross-reference creates confusion and may render claim indefinite",
                    fix="Repeat the relevant limitation language inline instead of cross-referencing",
                    legal_ref="MPEP 2173.05(p)",
                )
            )

    def _check_structure(self, claim: dict):
        """Check claim structure for common issues"""
        claim_text = claim["text"]
        claim_num = claim["number"]

        # Check for overly long claims (may indicate complexity issues)
        word_count = len(claim_text.split())
        if word_count > 500:
            self.issues.append(
                ClaimIssue(
                    severity="MINOR",
                    issue_type="structure",
                    claim_number=claim_num,
                    location="entire claim",
                    term=f"{word_count} words",
                    problem=f"Claim is very long ({word_count} words), which may indicate complexity",
                    fix="Consider breaking into multiple claims or simplifying structure",
                    legal_ref="MPEP 608.01(n)",
                )
            )

        # Check for excessive nested limitations (deep nesting)
        max_depth = self._calculate_nesting_depth(claim_text)
        if max_depth > 4:
            self.issues.append(
                ClaimIssue(
                    severity="MINOR",
                    issue_type="structure",
                    claim_number=claim_num,
                    location="nested limitations",
                    term=f"{max_depth} levels deep",
                    problem=f"Excessive nesting ({max_depth} levels) makes claim difficult to parse",
                    fix="Consider flattening claim structure or breaking into dependent claims",
                    legal_ref="MPEP 608.01(n)",
                )
            )

    def _find_limitation_location(self, claim: dict, char_position: int) -> str:
        """Find which limitation contains the given character position"""
        if not claim["limitations"]:
            return "preamble"

        # Find which limitation text contains the character position
        for letter, text in claim["limitations"]:
            lim_start = claim["text"].find(text)
            if lim_start != -1 and lim_start <= char_position < lim_start + len(text):
                return f"limitation ({letter})"

        return "unknown location"

    def _find_phrase_location(self, claim: dict, phrase: str) -> str:
        """Find which limitation contains the given phrase"""
        for letter, text in claim["limitations"]:
            if phrase.lower() in text.lower():
                return f"limitation ({letter})"

        # Detect preamble by finding the transitional phrase
        claim_lower = claim["text"].lower()
        transitional_phrases = ["comprising:", "consisting of:", "consisting essentially of:",
                                "including:", "wherein:", "characterized by:"]
        preamble_end = len(claim["text"])
        for tp in transitional_phrases:
            pos = claim_lower.find(tp)
            if pos != -1 and pos < preamble_end:
                preamble_end = pos

        if phrase.lower() in claim_lower[:preamble_end]:
            return "preamble"

        return "body"

    def _normalize_element(self, element: str) -> str:
        """Normalize element name for comparison"""
        # Remove extra whitespace, lowercase
        normalized = " ".join(element.lower().split())
        # Remove trailing punctuation
        normalized = normalized.rstrip(".,;:")
        return normalized

    def _singularize(self, word: str) -> str:
        """Simple singularization (not perfect, but handles common cases)"""
        if word.endswith("ies"):
            return word[:-3] + "y"
        elif word.endswith(("ses", "xes", "zes", "ches", "shes")):
            return word[:-2]
        elif word.endswith("s") and not word.endswith("ss"):
            return word[:-1]
        return word

    def _pluralize(self, word: str) -> str:
        """Simple pluralization (not perfect, but handles common cases)"""
        if word.endswith("y") and len(word) >= 2 and word[-2] not in "aeiou":
            return word[:-1] + "ies"
        elif word.endswith(("s", "x", "z", "ch", "sh")):
            return word + "es"
        else:
            return word + "s"

    def _calculate_nesting_depth(self, text: str) -> int:
        """Calculate maximum nesting depth based on parentheses"""
        max_depth = 0
        current_depth = 0

        for char in text:
            if char == "(":
                current_depth += 1
                max_depth = max(max_depth, current_depth)
            elif char == ")":
                current_depth = max(0, current_depth - 1)

        return max_depth

    def _issue_to_dict(self, issue: BaseIssue) -> dict[str, Any]:
        """Convert ClaimIssue to dictionary"""
        if isinstance(issue, ClaimIssue):
            return {
                "severity": issue.severity,
                "type": issue.issue_type,
                "claim": issue.claim_number,
                "location": issue.location,
                "term": issue.term,
                "problem": issue.problem,
                "fix": issue.fix,
                "mpep": issue.mpep_ref,
                "confidence": issue.confidence,
            }
        else:
            # Fallback for base issues (shouldn't happen in this analyzer)
            return super()._issue_to_dict(issue)

    def _generate_report(self, claims: list[dict]) -> dict:
        """Generate comprehensive analysis report"""
        # Sort issues by severity and claim number
        self._sort_issues(secondary_key=lambda x: x.claim_number)

        # Group issues by type
        issues_by_type = defaultdict(list)
        for issue in self.issues:
            if isinstance(issue, ClaimIssue):
                issues_by_type[issue.issue_type].append(issue)

        # Calculate compliance score
        counts = self._count_by_severity()
        compliance_score = self._calculate_compliance_score(
            len(claims), counts["critical"], counts["important"], counts["minor"]
        )

        # Generate summary
        summary = self._generate_claims_summary(claims, counts)

        # Use base report generation
        additional_data = {
            "claim_count": len(claims),
            "independent_count": sum(1 for c in claims if c["is_independent"]),
            "dependent_count": sum(1 for c in claims if not c["is_independent"]),
            "issues_by_type": {k: len(v) for k, v in issues_by_type.items()},
        }

        return self._generate_base_report(
            score_name="compliance_score",
            score_value=compliance_score,
            summary=summary,
            additional_data=additional_data,
        )

    def _generate_claims_summary(self, claims: list[dict], counts: dict[str, int]) -> str:
        """Generate claims-specific summary"""
        if counts["total"] == 0:
            return f"[OK] All {len(claims)} claims are compliant with 35 USC 112(b)"

        parts = []
        if counts["critical"] > 0:
            parts.append(
                f"{counts['critical']} CRITICAL issue{'s' if counts['critical'] != 1 else ''}"
            )
        if counts["important"] > 0:
            parts.append(
                f"{counts['important']} IMPORTANT issue{'s' if counts['important'] != 1 else ''}"
            )
        if counts["minor"] > 0:
            parts.append(f"{counts['minor']} MINOR issue{'s' if counts['minor'] != 1 else ''}")

        return f"[WARNING] Found {', '.join(parts)} requiring attention"

    def _calculate_compliance_score(
        self, claim_count: int, critical: int, important: int, minor: int
    ) -> float:
        """Calculate compliance score (0-100)"""
        if claim_count == 0:
            return 0.0

        # Deduct points based on issue severity, normalized by claim count
        deductions = ((critical * 15) + (important * 5) + (minor * 1)) / max(claim_count, 1)
        score = max(0, 100 - deductions)

        return float(score)


# Example usage
if __name__ == "__main__":
    sample_claims = """
    1. A computer system comprising:
        a) a processor; and
        b) memory storing instructions that cause the processor to process the data.

    2. The system of claim 1, wherein the target section is enhanced.
    """

    analyzer = ClaimsAnalyzer()
    results = analyzer.analyze_claims(sample_claims)

    print(f"Analysis complete: {results['summary']}")
    print(f"Compliance score: {results['compliance_score']}%")

    for issue in results["issues"]:
        print(f"\n[{issue['severity']}] Claim {issue['claim']} {issue['location']}")
        print(f"  Problem: {issue['problem']}")
        print(f"  Fix: {issue['fix']}")
