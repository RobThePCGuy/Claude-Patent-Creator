"""
EPO and PCT Analyzer Tools

Provides automated analysis tools for European and international patent applications:
- EPO claims analysis per Art. 84 EPC
- EPO specification support analysis per Art. 83 EPC
- EPO formalities checking per Rules 42-49 EPC
- PCT formalities checking per Rules 5-12

Tools:
    - review_epo_claims: Analyze claims for Art. 84 EPC compliance
    - review_epo_specification: Analyze specification for Art. 83 EPC sufficiency
    - check_epo_formalities: Check EPO formalities per Rules 42-49 EPC
    - check_pct_formalities: Check PCT formalities per Rules 5-12

Dependencies:
    - EPOClaimsAnalyzer, EPOSpecificationAnalyzer, EPOFormalitiesChecker, PCTFormalitiesChecker
    - mpep_index for retrieving relevant legal guidance
"""

from typing import Any, Optional


def register_epo_analyzer_tools(
    mcp,
    mpep_index,
    EPOClaimsAnalyzer,
    EPOSpecificationAnalyzer,
    EPOFormalitiesChecker,
    PCTFormalitiesChecker,
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
    """Register EPO and PCT analyzer tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        mpep_index: Initialized MPEPIndex for legal document searches
        EPOClaimsAnalyzer: EPO claims analyzer class (None if unavailable)
        EPOSpecificationAnalyzer: EPO specification analyzer class (None if unavailable)
        EPOFormalitiesChecker: EPO formalities checker class (None if unavailable)
        PCTFormalitiesChecker: PCT formalities checker class (None if unavailable)
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
    @track_performance("tool_review_epo_claims")
    def review_epo_claims(claims_text: str) -> dict[str, Any]:
        """Analyze patent claims for Art. 84 EPC compliance: clarity, conciseness, support, two-part form (Rule 43(1) EPC), and Art. 52(2) excluded subject matter."""
        try:
            # Validate inputs
            validated = validate_input(ReviewClaimsInput, claims_text=claims_text)
            claims_text = validated.claims_text

            log_info("review_epo_claims_started", claims_length=len(claims_text))

            if EPOClaimsAnalyzer:
                analyzer = EPOClaimsAnalyzer()
                analysis_results = analyzer.analyze_claims(claims_text)

                # Get relevant EPC guidance for context
                mpep_results = mpep_index.search(
                    "Art. 84 EPC claims clarity conciseness support European patent", top_k=5
                )

                epc_refs = []
                for r in mpep_results:
                    epc_refs.append(
                        {
                            "section": r["metadata"]["section"],
                            "page": r["metadata"]["page"],
                            "text": r["text"][:500] + "..." if len(r["text"]) > 500 else r["text"],
                        }
                    )

                result = {
                    "analysis_type": "automated",
                    "jurisdiction": "EPO",
                    "claim_count": analysis_results["claim_count"],
                    "independent_claims": analysis_results["independent_count"],
                    "dependent_claims": analysis_results["dependent_count"],
                    "compliance_score": analysis_results["compliance_score"],
                    "total_issues": analysis_results["total_issues"],
                    "critical_issues": analysis_results["critical_issues"],
                    "important_issues": analysis_results["important_issues"],
                    "minor_issues": analysis_results["minor_issues"],
                    "issues_by_type": analysis_results["issues_by_type"],
                    "summary": analysis_results["summary"],
                    "issues": analysis_results["issues"],
                    "epc_references": epc_refs,
                }
                log_operation_result("review_epo_claims", total_issues=result["total_issues"])
                return result

            else:
                log_warning("EPOClaimsAnalyzer not available, falling back to legal document search")
                results = mpep_index.search(
                    "Art. 84 EPC claims clarity conciseness", top_k=10
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
                    "analysis_type": "legal_search_only",
                    "jurisdiction": "EPO",
                    "warning": "Automated EPO analysis unavailable - showing EPC references only",
                    "relevant_sections": formatted,
                }

        except ValueError as e:
            log_error("review_epo_claims_validation_failed", exc_info=True, error=str(e))
            return {"error": f"Invalid input: {str(e)}"}
        except Exception as e:
            log_error("review_epo_claims_failed", exc_info=True)
            return {"error": f"EPO claims review failed: {str(e)}"}

    @mcp.tool()
    @track_performance("tool_review_epo_specification")
    def review_epo_specification(claims_text: str, specification: str) -> dict[str, Any]:
        """Analyze specification for Art. 83 EPC sufficiency of disclosure and Rule 42 EPC required sections."""
        try:
            # Validate inputs
            validated = validate_input(
                ReviewSpecificationInput, claims_text=claims_text, specification=specification
            )
            claims_text = validated.claims_text
            specification = validated.specification

            log_info(
                "review_epo_specification_started",
                claims_length=len(claims_text),
                spec_length=len(specification),
            )

            if EPOClaimsAnalyzer and EPOSpecificationAnalyzer:
                # Parse claims first using the EPO claims analyzer
                claims_analyzer = EPOClaimsAnalyzer()
                parsed_claims = claims_analyzer._parse_claims(claims_text)

                # Analyze specification support
                spec_analyzer = EPOSpecificationAnalyzer()
                analysis_results = spec_analyzer.analyze_specification_support(
                    parsed_claims, specification
                )

                # Get relevant EPC guidance
                mpep_results = mpep_index.search(
                    "Art. 83 EPC sufficiency disclosure Rule 42 description", top_k=5
                )

                epc_refs = []
                for r in mpep_results:
                    epc_refs.append(
                        {
                            "section": r["metadata"]["section"],
                            "page": r["metadata"]["page"],
                            "text": r["text"][:500] + "..." if len(r["text"]) > 500 else r["text"],
                        }
                    )

                result = {
                    "analysis_type": "automated",
                    "jurisdiction": "EPO",
                    "specification_paragraphs": analysis_results["specification_paragraphs"],
                    "indexed_terms": analysis_results["indexed_terms"],
                    "total_issues": analysis_results["total_issues"],
                    "critical_issues": analysis_results["critical_issues"],
                    "important_issues": analysis_results["important_issues"],
                    "sufficiency_issues": analysis_results["sufficiency_issues"],
                    "section_issues": analysis_results["section_issues"],
                    "spec_coverage": analysis_results["spec_coverage"],
                    "summary": analysis_results["summary"],
                    "compliant": analysis_results["compliant"],
                    "issues": analysis_results["issues"],
                    "epc_references": epc_refs,
                }
                log_operation_result(
                        "review_epo_specification", total_issues=result["total_issues"]
                    )
                return result

            else:
                log_warning("EPO specification analyzer not available, falling back to legal document search")
                results = mpep_index.search(
                    "Art. 83 EPC sufficiency disclosure description requirements", top_k=10
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
                    "analysis_type": "legal_search_only",
                    "jurisdiction": "EPO",
                    "warning": "Automated EPO analysis unavailable - showing EPC references only",
                    "guidance": formatted,
                }

        except ValueError as e:
            log_error("review_epo_specification_validation_failed", exc_info=True, error=str(e))
            return {"error": f"Invalid input: {str(e)}"}
        except Exception as e:
            log_error("review_epo_specification_failed", exc_info=True)
            return {"error": f"EPO specification review failed: {str(e)}"}

    @mcp.tool()
    @track_performance("tool_check_epo_formalities")
    def check_epo_formalities(
        abstract: Optional[str] = None,
        title: Optional[str] = None,
        specification: Optional[str] = None,
        drawings_present: bool = False,
    ) -> dict[str, Any]:
        """Check EPO formalities per Rules 42-49 EPC: abstract (Rule 47, <=150 words, reference signs), title (Rule 44), description sections (Rule 42), drawings (Rule 46), and claims fees (Rule 45)."""
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
                "check_epo_formalities_started",
                has_abstract=abstract is not None,
                has_title=title is not None,
                has_spec=specification is not None,
            )

            if EPOFormalitiesChecker:
                checker = EPOFormalitiesChecker()
                analysis_results = checker.check_all_formalities(
                    abstract=abstract,
                    title=title,
                    specification=specification,
                    drawings_present=drawings_present,
                )

                # Get relevant EPC guidance
                mpep_results = mpep_index.search(
                    "EPO formalities Rule 42 47 abstract description European patent", top_k=5
                )

                epc_refs = []
                for r in mpep_results:
                    epc_refs.append(
                        {
                            "section": r["metadata"]["section"],
                            "page": r["metadata"]["page"],
                            "text": r["text"][:500] + "..." if len(r["text"]) > 500 else r["text"],
                        }
                    )

                result = {
                    "analysis_type": "automated",
                    "jurisdiction": "EPO",
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
                    "claims_fees": analysis_results["results"]["claims_fees"],
                    "issues": analysis_results["issues"],
                    "epc_references": epc_refs,
                }
                log_operation_result("check_epo_formalities", compliant=result["overall_compliant"])
                return result

            else:
                log_warning("EPOFormalitiesChecker not available, falling back to legal document search")
                results = mpep_index.search(
                    "EPO formalities abstract title drawings Rules 42-49 EPC", top_k=10
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
                    "analysis_type": "legal_search_only",
                    "jurisdiction": "EPO",
                    "warning": "Automated EPO analysis unavailable - showing EPC references only",
                    "requirements": formatted,
                }

        except ValueError as e:
            log_error("check_epo_formalities_validation_failed", exc_info=True, error=str(e))
            return {"error": f"Invalid input: {str(e)}"}
        except Exception as e:
            log_error("check_epo_formalities_failed", exc_info=True)
            return {"error": f"EPO formalities check failed: {str(e)}"}

    @mcp.tool()
    @track_performance("tool_check_pct_formalities")
    def check_pct_formalities(
        abstract: Optional[str] = None,
        title: Optional[str] = None,
        specification: Optional[str] = None,
        drawings_present: bool = False,
    ) -> dict[str, Any]:
        """Check PCT formalities per Rules 5-12: abstract (Rule 8, <=150 words), description (Rule 5), claims (Rule 6), terminology (Rule 10, metric/Celsius), and physical requirements (Rule 11, A4/margins)."""
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
                "check_pct_formalities_started",
                has_abstract=abstract is not None,
                has_title=title is not None,
                has_spec=specification is not None,
            )

            if PCTFormalitiesChecker:
                checker = PCTFormalitiesChecker()
                analysis_results = checker.check_all_formalities(
                    abstract=abstract,
                    title=title,
                    specification=specification,
                    drawings_present=drawings_present,
                )

                # Get relevant PCT guidance
                mpep_results = mpep_index.search(
                    "PCT Rule 5 6 8 description claims abstract international application", top_k=5
                )

                pct_refs = []
                for r in mpep_results:
                    pct_refs.append(
                        {
                            "section": r["metadata"]["section"],
                            "page": r["metadata"]["page"],
                            "text": r["text"][:500] + "..." if len(r["text"]) > 500 else r["text"],
                        }
                    )

                result = {
                    "analysis_type": "automated",
                    "jurisdiction": "PCT",
                    "overall_compliant": analysis_results["overall_compliant"],
                    "ready_to_file": analysis_results["compliance_summary"]["ready_to_file"],
                    "summary": analysis_results["compliance_summary"]["summary"],
                    "critical_issues": analysis_results["compliance_summary"]["critical_issues"],
                    "warnings": analysis_results["compliance_summary"]["warnings"],
                    "info": analysis_results["compliance_summary"]["info"],
                    "abstract": analysis_results["results"]["abstract"],
                    "title": analysis_results["results"]["title"],
                    "description": analysis_results["results"]["description"],
                    "claims": analysis_results["results"]["claims"],
                    "terminology": analysis_results["results"]["terminology"],
                    "physical_requirements": analysis_results["results"]["physical"],
                    "issues": analysis_results["issues"],
                    "pct_references": pct_refs,
                }
                log_operation_result("check_pct_formalities", compliant=result["overall_compliant"])
                return result

            else:
                log_warning("PCTFormalitiesChecker not available, falling back to legal document search")
                results = mpep_index.search(
                    "PCT formalities abstract description claims Rules 5-12 international", top_k=10
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
                    "analysis_type": "legal_search_only",
                    "jurisdiction": "PCT",
                    "warning": "Automated PCT analysis unavailable - showing PCT references only",
                    "requirements": formatted,
                }

        except ValueError as e:
            log_error("check_pct_formalities_validation_failed", exc_info=True, error=str(e))
            return {"error": f"Invalid input: {str(e)}"}
        except Exception as e:
            log_error("check_pct_formalities_failed", exc_info=True)
            return {"error": f"PCT formalities check failed: {str(e)}"}
