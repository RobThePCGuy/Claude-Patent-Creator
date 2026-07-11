"""
Patent Analyzer Tools

Provides automated analysis tools for patent applications:
- Claims analysis per 35 USC 112(b)
- Specification support analysis per 35 USC 112(a)
- Formalities checking per MPEP 608

Tools:
    - review_patent_claims: Analyze claims for definiteness, antecedent basis, etc.
    - review_specification: Analyze specification support for claims
    - check_formalities: Check abstract, title, drawings, and required sections

Dependencies:
    - ClaimsAnalyzer, SpecificationAnalyzer, FormalitiesChecker from analyzer modules
    - mpep_index for retrieving relevant MPEP guidance
"""

from typing import Any, Optional


def register_analyzer_tools(
    mcp,
    mpep_index,
    ClaimsAnalyzer,
    SpecificationAnalyzer,
    FormalitiesChecker,
    log_info,
    log_warning,
    log_error,
    validate_input,
    ReviewClaimsInput,
    ReviewSpecificationInput,
    CheckFormalitiesInput,
    track_performance,
    log_operation_result,
):
    """Register patent analyzer tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        mpep_index: Initialized MPEPIndex for MPEP searches
        ClaimsAnalyzer: Claims analyzer class (None if unavailable)
        SpecificationAnalyzer: Specification analyzer class (None if unavailable)
        FormalitiesChecker: Formalities checker class (None if unavailable)
        log_info: Logging function for info messages
        log_warning: Logging function for warning messages
        log_error: Logging function for error messages
        validate_input: Input validation function
        ReviewClaimsInput: Pydantic model for claims review validation
        ReviewSpecificationInput: Pydantic model for specification review validation
        CheckFormalitiesInput: Pydantic model for formalities check validation
        track_performance: Performance tracking decorator
        log_operation_result: Operation result logging function
    """

    @mcp.tool()
    @track_performance("tool_review_claims")
    def review_patent_claims(claims_text: str) -> dict[str, Any]:
        """Analyze patent claims for 35 USC 112(b) compliance: antecedent basis, definiteness, subjective terms, cross-references, and structure."""
        try:
            # Validate inputs
            validated = validate_input(ReviewClaimsInput, claims_text=claims_text)
            claims_text = validated.claims_text

            log_info("review_claims_started", claims_length=len(claims_text))

            # Run automated analysis
            if ClaimsAnalyzer:
                analyzer = ClaimsAnalyzer()
                analysis_results = analyzer.analyze_claims(claims_text)

                # Also get relevant MPEP guidance for context
                mpep_results = mpep_index.search(
                    "claim definiteness antecedent basis 35 USC 112(b)", top_k=5
                )

                mpep_refs = []
                for r in mpep_results:
                    mpep_refs.append(
                        {
                            "section": r["metadata"]["section"],
                            "page": r["metadata"]["page"],
                            "text": r["text"][:500] + "..." if len(r["text"]) > 500 else r["text"],
                        }
                    )

                result = {
                    "analysis_type": "automated",
                    "claim_count": analysis_results["claim_count"],
                    "independent_claims": analysis_results["independent_count"],
                    "dependent_claims": analysis_results["dependent_count"],
                    "compliance_score": analysis_results["compliance_score"],
                    "total_issues": analysis_results["total_issues"],
                    "critical_issues": analysis_results["critical_issues"],
                    "important_issues": analysis_results["important_issues"],
                    "minor_issues": analysis_results["minor_issues"],
                    "issues_by_type": analysis_results["issues_by_type"],
                    # Skipped-check disclosure must survive the MCP boundary;
                    # dropping it here silently undid the report's honesty.
                    "checks_skipped": analysis_results.get("checks_skipped", []),
                    "summary": analysis_results["summary"],
                    "issues": analysis_results["issues"],
                    "mpep_references": mpep_refs,
                }
                log_operation_result("review_claims", total_issues=result["total_issues"])
                return result

            # Fallback to MPEP search if analyzer not available
            else:
                log_warning("ClaimsAnalyzer not available, falling back to MPEP search")
                results = mpep_index.search(claims_text, top_k=10)

                formatted = []
                for r in results:
                    formatted.append(
                        {
                            "section": r["metadata"]["section"],
                            "page": r["metadata"]["page"],
                            "text": r["text"],
                        }
                    )

                return {
                    "analysis_type": "mpep_search_only",
                    "warning": "Automated analysis unavailable - showing MPEP references only",
                    "relevant_sections": formatted,
                }

        except ValueError as e:
            log_error("review_claims_validation_failed", exc_info=True, error=str(e))
            return {"error": f"Invalid input: {str(e)}"}
        except Exception as e:
            log_error("review_claims_failed", exc_info=True)
            return {"error": f"Claims review failed: {str(e)}"}

    @mcp.tool()
    @track_performance("tool_review_specification")
    def review_specification(claims_text: str, specification: str) -> dict[str, Any]:
        """Analyze specification support for claims per 35 USC 112(a): written description, enablement, and best mode."""
        try:
            # Validate inputs
            validated = validate_input(
                ReviewSpecificationInput, claims_text=claims_text, specification=specification
            )
            claims_text = validated.claims_text
            specification = validated.specification

            log_info(
                "review_specification_started",
                claims_length=len(claims_text),
                spec_length=len(specification),
            )

            # Run automated analysis
            if ClaimsAnalyzer and SpecificationAnalyzer:
                # Parse claims first
                claims_analyzer = ClaimsAnalyzer()
                parsed_claims = claims_analyzer._parse_claims(claims_text)

                # Analyze specification support
                spec_analyzer = SpecificationAnalyzer()
                analysis_results = spec_analyzer.analyze_specification_support(
                    parsed_claims, specification
                )

                # Get relevant MPEP guidance
                mpep_results = mpep_index.search(
                    "written description enablement 35 USC 112(a)", top_k=5
                )

                mpep_refs = []
                for r in mpep_results:
                    mpep_refs.append(
                        {
                            "section": r["metadata"]["section"],
                            "page": r["metadata"]["page"],
                            "text": r["text"][:500] + "..." if len(r["text"]) > 500 else r["text"],
                        }
                    )

                result = {
                    "analysis_type": "automated",
                    "specification_paragraphs": analysis_results["specification_paragraphs"],
                    "indexed_terms": analysis_results["indexed_terms"],
                    "total_issues": analysis_results["total_issues"],
                    "critical_issues": analysis_results["critical_issues"],
                    "important_issues": analysis_results["important_issues"],
                    "written_description_issues": analysis_results["written_description_issues"],
                    "enablement_issues": analysis_results["enablement_issues"],
                    "spec_coverage": analysis_results["spec_coverage"],
                    "summary": analysis_results["summary"],
                    "compliant": analysis_results["compliant"],
                    "issues": analysis_results["issues"],
                    "mpep_references": mpep_refs,
                }
                log_operation_result(
                        "review_specification", total_issues=result["total_issues"]
                    )
                return result

            # Fallback to MPEP search if analyzers not available
            else:
                log_warning("Specification analyzer not available, falling back to MPEP search")
                results = mpep_index.search(
                    "specification written description enablement 35 USC 112", top_k=10
                )

                formatted = []
                for r in results:
                    formatted.append(
                        {
                            "section": r["metadata"]["section"],
                            "page": r["metadata"]["page"],
                            "text": r["text"],
                        }
                    )

                return {
                    "analysis_type": "mpep_search_only",
                    "warning": "Automated analysis unavailable - showing MPEP references only",
                    "guidance": formatted,
                }

        except ValueError as e:
            log_error("review_specification_validation_failed", exc_info=True, error=str(e))
            return {"error": f"Invalid input: {str(e)}"}
        except Exception as e:
            log_error("review_specification_failed", exc_info=True)
            return {"error": f"Specification review failed: {str(e)}"}

    @mcp.tool()
    @track_performance("tool_check_formalities")
    def check_formalities(
        abstract: Optional[str] = None,
        title: Optional[str] = None,
        specification: Optional[str] = None,
        drawings_present: bool = False,
    ) -> dict[str, Any]:
        """Check patent application formalities per MPEP 608: abstract (50-150 words), title (<=500 chars), required sections, and drawing references."""
        try:
            # Validate inputs
            validated = validate_input(
                CheckFormalitiesInput,
                abstract=abstract,
                title=title,
                specification=specification,
                drawings_present=drawings_present,
            )
            abstract = validated.abstract
            title = validated.title
            specification = validated.specification
            drawings_present = validated.drawings_present

            log_info(
                "check_formalities_started",
                has_abstract=abstract is not None,
                has_title=title is not None,
                has_spec=specification is not None,
            )

            # Run automated analysis
            if FormalitiesChecker:
                checker = FormalitiesChecker()
                analysis_results = checker.check_all_formalities(
                    abstract=abstract,
                    title=title,
                    specification=specification,
                    drawings_present=drawings_present,
                )

                # Get relevant MPEP guidance
                mpep_results = mpep_index.search(
                    "formalities abstract title drawings MPEP 608", top_k=5
                )

                mpep_refs = []
                for r in mpep_results:
                    mpep_refs.append(
                        {
                            "section": r["metadata"]["section"],
                            "page": r["metadata"]["page"],
                            "text": r["text"][:500] + "..." if len(r["text"]) > 500 else r["text"],
                        }
                    )

                result = {
                    "analysis_type": "automated",
                    "overall_compliant": analysis_results["overall_compliant"],
                    "ready_to_file": analysis_results["compliance_summary"]["ready_to_file"],
                    "summary": analysis_results["compliance_summary"]["summary"],
                    "critical_issues": analysis_results["compliance_summary"]["critical_issues"],
                    "warnings": analysis_results["compliance_summary"]["warnings"],
                    "info": analysis_results["compliance_summary"]["info"],
                    "abstract": analysis_results["results"]["abstract"],
                    "title": analysis_results["results"]["title"],
                    "drawings": analysis_results["results"]["drawings"],
                    "sections": analysis_results["results"]["sections"],
                    "issues": analysis_results["issues"],
                    "mpep_references": mpep_refs,
                }
                log_operation_result("check_formalities", compliant=result["overall_compliant"])
                return result

            # Fallback to MPEP search if checker not available
            else:
                log_warning("FormalitiesChecker not available, falling back to MPEP search")
                results = mpep_index.search(
                    "formalities abstract title drawings requirements MPEP 608", top_k=10
                )

                formatted = []
                for r in results:
                    formatted.append(
                        {
                            "section": r["metadata"]["section"],
                            "page": r["metadata"]["page"],
                            "text": r["text"],
                        }
                    )

                return {
                    "analysis_type": "mpep_search_only",
                    "warning": "Automated analysis unavailable - showing MPEP references only",
                    "requirements": formatted,
                }

        except ValueError as e:
            log_error("check_formalities_validation_failed", exc_info=True, error=str(e))
            return {"error": f"Invalid input: {str(e)}"}
        except Exception as e:
            log_error("check_formalities_failed", exc_info=True)
            return {"error": f"Formalities check failed: {str(e)}"}
