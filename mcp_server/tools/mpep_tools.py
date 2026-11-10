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
                **({"mpep_section": r["metadata"]["mpep_section"],
                    "section_title": r["metadata"].get("section_title", "")}
                   if r["metadata"].get("mpep_section") else {}),
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
                **({"source_url": r["metadata"]["source_url"]} if r["metadata"].get("source_url") else {}),
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
        """Retrieve a chapter or section body, with boundary and coverage limits.

        Examples: 600, 608, 608.01(b), 2173.02. Legacy indexes store chapter
        labels; subsection headings are located in their indexed text.
        """
        return retrieve_mpep_section(mpep_index, section_number, max_chunks)


def retrieve_mpep_section(index, section_number: str, max_chunks: int = 50) -> dict[str, Any]:
    """Locate revision-marked body headings, excluding contents and references."""
    import re

    section = section_number.strip()
    if not re.fullmatch(r"\d{3,4}(?:\.\d+)?(?:\([a-z0-9]+\))*", section):
        return {"error": "Use an MPEP section such as 608.01(b), or use search_mpep."}
    if max_chunks < 1:
        return {"error": "max_chunks must be at least 1."}
    chapter = f"MPEP {int(section.split('.')[0]) // 100 * 100}"
    entries = [(i, text, meta) for i, (text, meta) in enumerate(zip(index.chunks, index.metadata))
               if meta.get("source", "MPEP") == "MPEP" and meta.get("section") == chapter]
    entries.sort(key=lambda item: (item[2].get("page", 0), item[0]))
    chapter_request = section == chapter.removeprefix("MPEP ")
    selected = []
    if chapter_request:
        selected = [{"text": t, "metadata": m} for _, t, m in entries]
    else:
        # Rejoin overlapping chunks within each page so split headings and
        # revision markers can be recognized. Retain spans to return citations.
        body, spans, previous_page = "", [], None
        for _, text, meta in entries:
            text = re.sub(r"^\[MPEP \d+\] ?", "", text)
            overlap = 0
            if meta.get("page") == previous_page:
                overlap = next((n for n in range(min(100, len(text), len(body)), 0, -1)
                                if body.endswith(text[:n])), 0)
            else:
                body += "\n"
            start = len(body) - overlap
            body += text[overlap:]
            spans.append((start, len(body), text, meta))
            previous_page = meta.get("page")
        try:
            from mpep_search import MPEP_HEADING_RE
        except ImportError:
            from mcp_server.mpep_search import MPEP_HEADING_RE
        headings = list(MPEP_HEADING_RE.finditer(body))
        first = next((h for h in headings if h.group(1) == section), None)
        if first:
            end = len(body)
            for h in headings:
                number = h.group(1)
                descendant = number.startswith(section + ".") or number.startswith(section + "(")
                if h.start() > first.start() and number != section and not descendant:
                    end = h.start()
                    break
            selected = [{"text": text, "metadata": meta}
                        for start, stop, text, meta in spans
                        if start < end and stop > first.start()]
    if not selected:
        return {"section": section, "chapter": chapter,
                "error": f"Section {section} heading was not found in indexed {chapter} text. "
                         "Try search_mpep with the section number and topic; this does not "
                         "establish that the section is absent from the MPEP."}
    return {
        "section": section, "chapter": chapter,
        "boundary": "exact" if chapter_request else "approximate",
        "coverage": f"Indexed content from {chapter}. " + (
            "Chapter boundary follows the stored chapter label." if chapter_request else
            "Body heading located; includes subsections until the next peer/parent heading. "
            "Chunk boundaries are approximate and can include adjacent text; PDF extraction "
            "and missing headings can leave gaps. This is not guaranteed full section text."
        ),
        "total_chunks": len(selected), "returned_chunks": min(max_chunks, len(selected)),
        "truncated": len(selected) > max_chunks, "chunks": selected[:max_chunks],
    }
