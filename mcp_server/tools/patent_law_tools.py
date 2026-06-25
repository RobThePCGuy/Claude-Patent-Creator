"""
Cross-Jurisdiction Patent Law Search Tools

Provides the search_patent_law MCP tool for searching patent law across
US (MPEP/USC/CFR), EPO (EPC/Guidelines), and PCT sources in a unified index.

The existing search_mpep tool is preserved for backward compatibility.
This tool adds jurisdiction-aware filtering on top of the same RAG pipeline.
"""

from typing import Any, Optional

# Jurisdiction -> source filter mapping
JURISDICTION_SOURCES = {
    "US": ["MPEP", "35_USC", "37_CFR", "SUBSEQUENT"],
    "EPO": ["EPC", "EPC_RULES", "EPO_GUIDELINES"],
    "PCT": ["PCT", "PCT_RULES"],
}


def register_patent_law_tools(
    mcp,
    mpep_index,
    log_info,
    log_error,
    validate_input,
    SearchPatentLawInput,
    track_performance,
):
    """Register cross-jurisdiction patent law search tools.

    Args:
        mcp: FastMCP server instance
        mpep_index: The unified FAISS+BM25 index (contains US, EPO, PCT sources)
        log_info: Logging function for info messages
        log_error: Logging function for error messages
        validate_input: Input validation function
        SearchPatentLawInput: Pydantic model for search validation
        track_performance: Performance tracking decorator
    """

    @mcp.tool()
    def search_patent_law(
        query: str,
        jurisdiction: Optional[str] = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Search patent law across US (MPEP/USC/CFR), EPO (EPC/Guidelines), and PCT sources.

        This is the recommended tool for cross-jurisdictional legal research.
        Searches a unified index containing all patent law sources.

        Args:
            query: Search query (e.g., "claim definiteness requirements",
                   "sufficiency of disclosure", "unity of invention")
            jurisdiction: Filter by jurisdiction - "US", "EPO", "PCT", or None for all
            top_k: Number of results to return (1-20, default 5)

        Returns:
            List of relevant patent law passages with source, jurisdiction, and content
        """
        log_info(
            "search_patent_law called",
            query=query,
            jurisdiction=jurisdiction,
            top_k=top_k,
        )

        try:
            # Validate inputs
            if SearchPatentLawInput:
                validated = validate_input(
                    SearchPatentLawInput,
                    query=query,
                    jurisdiction=jurisdiction,
                    top_k=top_k,
                )
                query = validated.query
                jurisdiction = validated.jurisdiction
                top_k = validated.top_k

            # Determine source filters based on jurisdiction
            source_filters = None
            if jurisdiction:
                source_filters = JURISDICTION_SOURCES.get(jurisdiction)
                if not source_filters:
                    return [{"error": f"Unknown jurisdiction: {jurisdiction}. Use US, EPO, or PCT."}]

            # Search the unified index
            # If jurisdiction specified, search each source and combine
            # If no jurisdiction, search without filter
            all_results = []

            if source_filters:
                for source in source_filters:
                    try:
                        results = mpep_index.search(
                            query=query,
                            top_k=top_k,
                            source_filter=source,
                        )
                        for r in results:
                            r["jurisdiction"] = jurisdiction
                        all_results.extend(results)
                    except Exception:
                        # Source may not be indexed yet — skip silently
                        pass

                # Sort by score and limit
                all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
                all_results = all_results[:top_k]
            else:
                # Search all sources (no filter)
                all_results = mpep_index.search(
                    query=query,
                    top_k=top_k,
                )
                # Tag each result with its jurisdiction
                for r in all_results:
                    source = r.get("metadata", {}).get("source", r.get("source", ""))
                    if source in JURISDICTION_SOURCES["US"]:
                        r["jurisdiction"] = "US"
                    elif source in JURISDICTION_SOURCES["EPO"]:
                        r["jurisdiction"] = "EPO"
                    elif source in JURISDICTION_SOURCES["PCT"]:
                        r["jurisdiction"] = "PCT"
                    else:
                        r["jurisdiction"] = "US"  # Default for legacy sources

            log_info(
                "search_patent_law completed",
                results_count=len(all_results),
                jurisdiction=jurisdiction,
            )
            return all_results

        except Exception as e:
            log_error("search_patent_law failed", error=str(e), exc_info=True)
            return [{"error": f"Patent law search failed: {str(e)}"}]
