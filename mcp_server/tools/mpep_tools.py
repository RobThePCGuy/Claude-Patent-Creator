"""
MPEP (Manual of Patent Examining Procedure) Search Tools

Provides MCP tools for searching and retrieving content from the USPTO MPEP manual.

Tools:
    - search_mpep: Hybrid search (FAISS + BM25) with filters
    - get_mpep_section: Retrieve all chunks from a specific MPEP section

Dependencies:
    - mpep_index: MPEPIndex instance for search operations
    - Validation models from validation.py
    - Logging and monitoring from logging_config.py and monitoring.py
"""

from typing import Any, Optional


def register_mpep_tools(
    mcp,
    mpep_index,
    log_info,
    log_error,
    validate_input,
    SearchMPEPInput,
    track_performance,
    log_operation_result,
):
    """Register MPEP search tools with the MCP server.

    Args:
        mcp: MCPServer instance
        mpep_index: Initialized MPEPIndex for search operations
        log_info: Logging function for info messages
        log_error: Logging function for error messages
        validate_input: Input validation function
        SearchMPEPInput: Pydantic model for search validation
        track_performance: Performance tracking decorator
        log_operation_result: Operation result logging function
    """

    @mcp.tool()
    @track_performance("tool_search_mpep")
    def search_mpep(
        query: str,
        top_k: int = 5,
        retrieve_k: Optional[int] = None,
        source_filter: Optional[str] = None,
        is_statute: Optional[bool] = None,
        is_regulation: Optional[bool] = None,
        is_update: Optional[bool] = None,
    ) -> list[dict[str, Any]]:
        """Search USPTO MPEP manual for relevant information.

        Hybrid search (FAISS + BM25) with optional filters for source type (MPEP/35_USC/37_CFR/SUBSEQUENT),
        statutes, regulations, and updates. Returns ranked results with relevance scores and citation metadata.
        """
        try:
            # Validate inputs
            validated = validate_input(
                SearchMPEPInput,
                query=query,
                top_k=top_k,
                retrieve_k=retrieve_k,
                source_filter=source_filter,
                is_statute=is_statute,
                is_regulation=is_regulation,
                is_update=is_update,
            )
            query = validated.query
            top_k = validated.top_k
            retrieve_k = validated.retrieve_k
            source_filter = validated.source_filter

            log_info("search_mpep_tool_called", query_length=len(query), top_k=top_k)

            top_k = min(top_k, 20)  # Cap at 20 results
            results = mpep_index.search(
                query,
                top_k,
                retrieve_k=retrieve_k,
                source_filter=source_filter,
                is_statute=is_statute,
                is_regulation=is_regulation,
                is_update=is_update,
            )
        except ValueError as e:
            log_error("search_mpep_validation_failed", exc_info=True, error=str(e))
            return [{"error": f"Invalid input: {str(e)}"}]
        except Exception as e:
            log_error("search_mpep_failed", exc_info=True, query=query[:100])
            return [{"error": f"Search failed: {str(e)}"}]

        # Format results with citation metadata and source type
        formatted_results = []
        for i, r in enumerate(results):
            result = {
                "rank": i + 1,
                "source": r["metadata"].get("source", "MPEP"),
                "section": r["metadata"]["section"],
                "file": r["metadata"]["file"],
                "page": r["metadata"]["page"],
                "has_statute": r["metadata"].get("has_statute", False),
                "has_mpep_ref": r["metadata"].get("has_mpep_ref", False),
                "has_rule_ref": r["metadata"].get("has_rule_ref", False),
                "is_statute": r["metadata"].get("is_statute", False),
                "is_regulation": r["metadata"].get("is_regulation", False),
                "is_update": r["metadata"].get("is_update", False),
                "relevance_score": round(r["relevance_score"], 3),
                "text": r["text"],
            }

            # Add source-specific fields if present
            if r["metadata"].get("source") == "SUBSEQUENT":
                result["doc_type"] = r["metadata"].get("doc_type")
                result["fr_citation"] = r["metadata"].get("fr_citation")
                result["effective_date"] = r["metadata"].get("effective_date")

            formatted_results.append(result)

        log_operation_result("search_mpep", results_count=len(formatted_results))
        return formatted_results

    @mcp.tool()
    def get_mpep_section(section_number: str, max_chunks: int = 50) -> dict[str, Any]:
        """Get all text chunks from a specific MPEP section number (e.g., "2100", "700", "608")."""
        # Find all chunks from the specified section
        section_pattern = f"MPEP {section_number}"
        matching_chunks = [
            {"text": chunk, "metadata": meta}
            for chunk, meta in zip(mpep_index.chunks, mpep_index.metadata)
            if section_pattern in meta["section"]
        ]

        if not matching_chunks:
            return {"error": f"No content found for MPEP section {section_number}"}

        # Return requested number of chunks
        return {
            "section": section_number,
            "total_chunks": len(matching_chunks),
            "chunks": matching_chunks[:max_chunks],
        }
