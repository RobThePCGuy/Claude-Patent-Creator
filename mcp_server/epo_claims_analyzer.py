#!/usr/bin/env python3
"""
EPO Claims Analyzer
Performs automated analysis of patent claims for Art. 84 EPC compliance
(clarity, conciseness, support by the description).

Also checks for Art. 52(2) EPC excluded subject matter and Rule 43(1) EPC
two-part form requirements.

Note: Art. 123(2) EPC (added matter) checking is not yet implemented and
would require comparison between filed and amended versions.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

try:
    from analyzer_base import BaseAnalyzer, BaseIssue
except ImportError:
    from mcp_server.analyzer_base import BaseAnalyzer, BaseIssue


@dataclass
class EPOClaimIssue(BaseIssue):
    """Represents a specific issue found in an EPO claim analysis"""

    issue_type: str = field(default="")  # clarity, conciseness, support, two_part_form, excluded_subject_matter
    claim_number: int = field(default=0)
    location: str = field(default="")  # e.g., "limitation (c)", "preamble"
    term: str = field(default="")


class EPOClaimsAnalyzer(BaseAnalyzer):
    """Automated patent claims analyzer for EPO Art. 84 EPC compliance.

    Checks performed:
    - Two-part form (Rule 43(1) EPC): preamble + characterizing portion
    - Art. 84 clarity: indefinite/subjective terms
    - Art. 84 conciseness: excess claims, excessive independent claims
    - Art. 52(2) excluded subject matter
    - Vague phrases that undermine clarity
    """

    # Regex patterns for claim element extraction (same as US analyzer)
    NEW_ELEMENT_PATTERN = re.compile(
        r"\b(a|an|at least one|one or more|more than one|two or more|"
        r"plurality of|one|two|three|four|five|six|seven|eight|nine|ten)\s+([a-z][a-z\s-]+?)(?=\s+(?:configured|comprising|wherein|that|for|to|with|,|;|\.))",
        re.IGNORECASE,
    )

    # Subjective/indefinite terms (same set as US, cited under Art. 84 EPC)
    # See EPO Guidelines Part F, Chapter IV, 4.6
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

    # Art. 52(2) EPC excluded subject matter patterns
    EXCLUDED_SUBJECT_MATTER = {
        "computer program": "Art. 52(2)(c) EPC - computer programs as such",
        "business method": "Art. 52(2)(c) EPC - schemes, rules and methods for performing mental acts, playing games or doing business",
        "mathematical method": "Art. 52(2)(a) EPC - mathematical methods as such",
        "presentation of information": "Art. 52(2)(d) EPC - presentations of information as such",
        "game": "Art. 52(2)(c) EPC - schemes, rules and methods for playing games",
        "mental act": "Art. 52(2)(c) EPC - schemes, rules and methods for performing mental acts",
    }

    # EPO claims fee threshold (Rule 45 EPC)
    CLAIMS_FEE_THRESHOLD = 15

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
        Main analysis entry point for EPO claims

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
            self._check_two_part_form(claim)
            self._check_clarity(claim)
            self._check_subjective_terms(claim)
            self._check_excluded_subject_matter(claim)
            self._check_vague_phrases(claim)

        # Run conciseness checks on whole claim set
        self._check_conciseness(claims)

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
                "category": self._determine_claim_category(claim_body),
                "limitations": [],
            }

            # Check for dependency
            dep_match = re.search(r"claim (\d+)", claim_body, re.IGNORECASE)
            if dep_match:
                dep_num = int(dep_match.group(1))
                if dep_num != int(claim_num):
                    claim["depends_on"] = dep_num

            # Extract limitations (a), (b), (c), etc.
            lim_pattern = re.compile(r"\n\s*([a-z])\)\s+(.+?)(?=\n\s*[a-z]\)|$)", re.DOTALL)
            limitations = lim_pattern.findall(claim_body)
            claim["limitations"] = [(letter, text.strip()) for letter, text in limitations]

            claims.append(claim)

        return claims

    def _determine_claim_category(self, claim_text: str) -> str:
        """Determine claim category (product, process, apparatus, use)"""
        text_lower = claim_text.lower()
        if re.search(r"^a\s+method\b|^a\s+process\b|^method\s+", text_lower):
            return "process"
        if re.search(r"^use\s+of\b", text_lower):
            return "use"
        if re.search(r"^a\s+device\b|^a\s+system\b|^a\s+apparatus\b|^an\s+apparatus\b", text_lower):
            return "apparatus"
        return "product"

    def _check_two_part_form(self, claim: dict):
        """Check for Rule 43(1) EPC two-part form in independent claims.

        Under Rule 43(1) EPC, independent claims should (wherever appropriate)
        be in two-part form with:
        - A preamble indicating the prior art
        - A characterizing portion beginning with 'characterized in that',
          'characterised in that', or 'wherein the improvement comprises'
        """
        if not claim["is_independent"]:
            return

        claim_text = claim["text"]
        claim_num = claim["number"]

        # Check for characterizing portion
        two_part_patterns = [
            r"characteri[sz]ed\s+in\s+that",
            r"wherein\s+the\s+improvement\s+comprises",
        ]

        has_two_part = any(
            re.search(pattern, claim_text, re.IGNORECASE)
            for pattern in two_part_patterns
        )

        if not has_two_part:
            self.issues.append(
                EPOClaimIssue(
                    severity="IMPORTANT",
                    issue_type="two_part_form",
                    claim_number=claim_num,
                    location="entire claim",
                    term="",
                    problem=(
                        "Independent claim does not use two-part form "
                        "(preamble + 'characterized in that' + characterizing portion)"
                    ),
                    fix=(
                        "Consider restructuring as two-part claim with preamble stating "
                        "prior art features and characterizing portion stating novel features, "
                        "unless two-part form is inappropriate for this type of claim"
                    ),
                    legal_ref="Rule 43(1) EPC",
                    confidence="HIGH",
                )
            )

    def _check_clarity(self, claim: dict):
        """Check for Art. 84 EPC clarity issues (indefiniteness)"""
        claim_text = claim["text"].lower()
        claim_num = claim["number"]

        # Check for vague claim scope
        vague_phrases = [
            ("or the like", "open-ended phrase renders claim unclear"),
            ("such as", "may create ambiguity about claim scope"),
            ("including but not limited to", "may render claim scope unclear"),
            ("etc.", "abbreviation renders claim scope unclear"),
            ("and/or", "may create ambiguity about claim scope"),
        ]

        for phrase, reason in vague_phrases:
            if phrase in claim_text:
                self.issues.append(
                    EPOClaimIssue(
                        severity="IMPORTANT",
                        issue_type="clarity",
                        claim_number=claim_num,
                        location=self._find_phrase_location(claim, phrase),
                        term=phrase,
                        problem=f'Phrase "{phrase}" - {reason}',
                        fix=f'Remove "{phrase}" or replace with specific language',
                        legal_ref="Art. 84 EPC (EPO Guidelines F-IV, 4.6)",
                    )
                )

    def _check_subjective_terms(self, claim: dict):
        """Check for subjective terms that undermine clarity under Art. 84 EPC"""
        claim_text = claim["text"].lower()
        claim_num = claim["number"]

        for term, reason in self.SUBJECTIVE_TERMS.items():
            pattern = re.compile(r"\b" + term + r"\b", re.IGNORECASE)
            if pattern.search(claim_text):
                self.issues.append(
                    EPOClaimIssue(
                        severity="IMPORTANT",
                        issue_type="clarity",
                        claim_number=claim_num,
                        location=self._find_phrase_location(claim, term),
                        term=term,
                        problem=f'Subjective term "{term}" - {reason}',
                        fix="Replace with objective, measurable criteria or quantitative values",
                        legal_ref="Art. 84 EPC (EPO Guidelines F-IV, 4.6)",
                        confidence="HIGH",
                    )
                )

    def _check_excluded_subject_matter(self, claim: dict):
        """Check for Art. 52(2) EPC excluded subject matter.

        Art. 52(2) EPC lists categories that are not regarded as inventions:
        (a) discoveries, scientific theories, mathematical methods
        (b) aesthetic creations
        (c) schemes, rules and methods for performing mental acts, playing
            games or doing business, and programs for computers
        (d) presentations of information

        Art. 52(3) specifies exclusion applies only to the extent the
        application relates to such subject matter 'as such'.
        """
        claim_text = claim["text"].lower()
        claim_num = claim["number"]

        for term, description in self.EXCLUDED_SUBJECT_MATTER.items():
            pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
            if pattern.search(claim_text):
                self.issues.append(
                    EPOClaimIssue(
                        severity="IMPORTANT",
                        issue_type="excluded_subject_matter",
                        claim_number=claim_num,
                        location=self._find_phrase_location(claim, term),
                        term=term,
                        problem=(
                            f'Claim references potentially excluded subject matter: "{term}". '
                            f"{description}. The exclusion applies only 'as such' (Art. 52(3) EPC)."
                        ),
                        fix=(
                            "Ensure the claim defines a technical contribution beyond the excluded "
                            "subject matter itself. Consider emphasizing the technical effect or "
                            "technical implementation aspects."
                        ),
                        legal_ref="Art. 52(2)/(3) EPC",
                        confidence="MEDIUM",
                    )
                )

    def _check_vague_phrases(self, claim: dict):
        """Check for additional vague phrases under Art. 84 EPC"""
        claim_text = claim["text"].lower()
        claim_num = claim["number"]

        # Relative terms that may need quantification
        relative_terms = [
            ("about", "relative term, may lack precision"),
            ("approximately", "relative term, may lack precision"),
            ("substantially", "relative term, may lack precision"),
            ("essentially", "relative term, may lack precision"),
            ("generally", "relative term, may lack precision"),
            ("typically", "relative term, may lack precision"),
            ("normally", "relative term, may lack precision"),
            ("usually", "relative term, may lack precision"),
        ]

        for term, reason in relative_terms:
            pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
            if pattern.search(claim_text):
                self.issues.append(
                    EPOClaimIssue(
                        severity="MINOR",
                        issue_type="clarity",
                        claim_number=claim_num,
                        location=self._find_phrase_location(claim, term),
                        term=term,
                        problem=f'Relative term "{term}" - {reason}',
                        fix="Consider replacing with a precise value or range, or ensure the term is well-understood in the art",
                        legal_ref="Art. 84 EPC (EPO Guidelines F-IV, 4.6)",
                        confidence="MEDIUM",
                    )
                )

    def _check_conciseness(self, claims: list[dict]):
        """Check Art. 84 EPC conciseness requirements.

        Rule 45 EPC: claims fees are due for each claim in excess of 15.
        EPO also expects a reasonable number of independent claims per category.
        """
        total_claims = len(claims)
        independent_claims = [c for c in claims if c["is_independent"]]

        # Check total claim count vs fee threshold
        if total_claims > self.CLAIMS_FEE_THRESHOLD:
            excess = total_claims - self.CLAIMS_FEE_THRESHOLD
            self.issues.append(
                EPOClaimIssue(
                    severity="MINOR",
                    issue_type="conciseness",
                    claim_number=0,
                    location="claim set",
                    term=f"{total_claims} claims",
                    problem=(
                        f"Application has {total_claims} claims, exceeding the {self.CLAIMS_FEE_THRESHOLD}-claim "
                        f"threshold. Additional claims fees will apply for {excess} excess claim(s)."
                    ),
                    fix=(
                        f"Consider reducing to {self.CLAIMS_FEE_THRESHOLD} claims or fewer to avoid "
                        f"additional claims fees, or confirm budget for excess claims fees."
                    ),
                    legal_ref="Rule 45(1) EPC",
                    confidence="HIGH",
                )
            )

        # Check for excessive independent claims in same category
        categories = defaultdict(list)
        for claim in independent_claims:
            categories[claim["category"]].append(claim["number"])

        for category, claim_numbers in categories.items():
            if len(claim_numbers) > 1:
                self.issues.append(
                    EPOClaimIssue(
                        severity="IMPORTANT",
                        issue_type="conciseness",
                        claim_number=claim_numbers[0],
                        location="claim set",
                        term=f"{len(claim_numbers)} independent {category} claims",
                        problem=(
                            f"Multiple independent claims ({', '.join(str(n) for n in claim_numbers)}) "
                            f"in the same category ({category}). Rule 43(2) EPC generally allows "
                            f"only one independent claim per category."
                        ),
                        fix=(
                            "Consider consolidating into a single independent claim per category "
                            "with dependent claims for alternatives, or justify under Rule 43(2)(a)-(c) EPC."
                        ),
                        legal_ref="Rule 43(2) EPC",
                        confidence="HIGH",
                    )
                )

    def _find_phrase_location(self, claim: dict, phrase: str) -> str:
        """Find which limitation contains the given phrase"""
        for letter, text in claim["limitations"]:
            if phrase.lower() in text.lower():
                return f"limitation ({letter})"

        # Detect preamble
        claim_lower = claim["text"].lower()
        transitional_phrases = [
            "comprising:", "consisting of:", "consisting essentially of:",
            "including:", "wherein:", "characterized by:",
            "characterised by:", "characterized in that", "characterised in that",
        ]
        preamble_end = len(claim["text"])
        for tp in transitional_phrases:
            pos = claim_lower.find(tp)
            if pos != -1 and pos < preamble_end:
                preamble_end = pos

        if phrase.lower() in claim_lower[:preamble_end]:
            return "preamble"

        return "body"

    def _issue_to_dict(self, issue: BaseIssue) -> dict[str, Any]:
        """Convert EPOClaimIssue to dictionary"""
        if isinstance(issue, EPOClaimIssue):
            return {
                "severity": issue.severity,
                "type": issue.issue_type,
                "claim": issue.claim_number,
                "location": issue.location,
                "term": issue.term,
                "problem": issue.problem,
                "fix": issue.fix,
                "legal_ref": issue.legal_ref,
                "confidence": issue.confidence,
            }
        else:
            return {
                "severity": issue.severity,
                "type": "",
                "claim": 0,
                "location": "",
                "term": "",
                "problem": issue.problem,
                "fix": issue.fix,
                "legal_ref": issue.legal_ref,
                "confidence": issue.confidence,
            }

    def _generate_report(self, claims: list[dict]) -> dict:
        """Generate comprehensive EPO claims analysis report"""
        # Sort issues by severity and claim number
        self._sort_issues(secondary_key=lambda x: x.claim_number)

        # Group issues by type
        issues_by_type = defaultdict(list)
        for issue in self.issues:
            if isinstance(issue, EPOClaimIssue):
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
            "jurisdiction": "EPO",
            "legal_framework": "European Patent Convention (EPC)",
        }

        return self._generate_base_report(
            score_name="compliance_score",
            score_value=compliance_score,
            summary=summary,
            additional_data=additional_data,
        )

    def _generate_claims_summary(self, claims: list[dict], counts: dict[str, int]) -> str:
        """Generate EPO claims-specific summary"""
        if counts["total"] == 0:
            return f"[OK] All {len(claims)} claims are compliant with Art. 84 EPC"

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

        return f"[WARNING] Found {', '.join(parts)} requiring attention under Art. 84 EPC"

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
    1. A data processing system comprising:
        a) a processor; and
        b) memory storing instructions that cause the processor to process data,
        wherein the system is substantially efficient.

    2. The system of claim 1, wherein the processor executes a computer program.

    3. A method for processing data, the method comprising:
        a) receiving input data; and
        b) generating an optimal output.
    """

    analyzer = EPOClaimsAnalyzer()
    results = analyzer.analyze_claims(sample_claims)

    print(f"Analysis complete: {results['summary']}")
    print(f"Compliance score: {results['compliance_score']}%")

    for issue in results["issues"]:
        print(f"\n[{issue['severity']}] Claim {issue['claim']} {issue['location']}")
        print(f"  Problem: {issue['problem']}")
        print(f"  Fix: {issue['fix']}")
        print(f"  Ref: {issue['legal_ref']}")
