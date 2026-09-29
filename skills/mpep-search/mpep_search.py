"""
MPEP Search Skill
Provides search and retrieval operations for USPTO MPEP, 35 USC, 37 CFR, and updates.
"""

import sys
from pathlib import Path
from typing import Any, Optional

# Add mcp_server to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from mcp_server.mpep_search import MPEPIndex
except ImportError as e:
    raise ImportError(
        f"Could not import MPEPIndex from mcp_server: {e}\n"
        "Make sure mcp_server is installed and the index is built."
    )


# Global index instance (lazy-loaded)
_mpep_index: Optional[MPEPIndex] = None


def _get_mpep_index() -> MPEPIndex:
    """Get or initialize the MPEP index singleton."""
    global _mpep_index
    if _mpep_index is None:
        _mpep_index = MPEPIndex()  # HyDE follows PATENT_MPEP_USE_HYDE (default off)

        # Load the index (should already be built)
        if not _mpep_index.index_file.exists():
            raise RuntimeError(
                "MPEP index not found. Please run the setup/installation first:\n"
                "  python install.py\n"
                "This will download and index the MPEP, 35 USC, and 37 CFR."
            )

        _mpep_index.build_index(force_rebuild=False)

    return _mpep_index


def search_mpep(
    query: str,
    top_k: int = 5,
    retrieve_k: Optional[int] = None,
    source_filter: Optional[str] = None,
    is_statute: Optional[bool] = None,
    is_regulation: Optional[bool] = None,
    is_update: Optional[bool] = None,
) -> dict[str, Any]:
    """
    Search the MPEP corpus using hybrid RAG (vector + keyword + reranking).

    Args:
        query: Search query string (minimum 3 characters)
        top_k: Number of final results to return (default: 5, max: 20)
        retrieve_k: Number of candidates to retrieve before reranking (default: top_k * 4)
        source_filter: Filter by source type ("MPEP", "35_USC", "37_CFR", "SUBSEQUENT", or None)
        is_statute: Filter for statute content (True/False/None)
        is_regulation: Filter for regulation content (True/False/None)
        is_update: Filter for recent updates (True/False/None)

    Returns:
        Dictionary with:
          - success: bool
          - results: List of search result dictionaries
          - query_info: Metadata about the query

        Or on error:
          - success: False
          - error: Error message
    """
    # Input validation
    if not query or not query.strip():
        return {"success": False, "error": "Query cannot be empty"}

    query = query.strip()

    if len(query) < 3:
        return {
            "success": False,
            "error": f"Query too short (minimum 3 characters, got {len(query)})",
        }

    # Validate source_filter if provided
    if source_filter is not None:
        valid_sources = ["MPEP", "35_USC", "37_CFR", "SUBSEQUENT"]
        if source_filter not in valid_sources:
            return {
                "success": False,
                "error": f"Invalid source_filter '{source_filter}'. Must be one of: {', '.join(valid_sources)}",
            }

    # Cap top_k
    top_k = min(max(1, top_k), 20)

    try:
        # Get the index
        index = _get_mpep_index()

        # Perform search
        raw_results = index.search(
            query=query,
            top_k=top_k,
            retrieve_k=retrieve_k,
            source_filter=source_filter,
            is_statute=is_statute,
            is_regulation=is_regulation,
            is_update=is_update,
        )

        # Format results
        formatted_results = []
        for i, r in enumerate(raw_results):
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

            # Add source-specific fields
            if r["metadata"].get("source") == "SUBSEQUENT":
                result["doc_type"] = r["metadata"].get("doc_type")
                result["fr_citation"] = r["metadata"].get("fr_citation")
                result["effective_date"] = r["metadata"].get("effective_date")

            formatted_results.append(result)

        return {
            "success": True,
            "results": formatted_results,
            "query_info": {
                "query": query,
                "top_k": top_k,
                "retrieve_k": retrieve_k or (top_k * 4),
                "source_filter": source_filter,
                "results_count": len(formatted_results),
            },
        }

    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Search failed: {str(e)}"}


def get_mpep_section(
    section_number: str,
    max_chunks: int = 50,
) -> dict[str, Any]:
    """
    Get all text chunks from a specific MPEP section by number.

    Args:
        section_number: MPEP section number (e.g., "2100", "700", "608.01")
                       Do NOT include "MPEP" prefix, just the number.
        max_chunks: Maximum number of chunks to return (default: 50)

    Returns:
        Dictionary with:
          - success: bool
          - section: The section number requested
          - total_chunks: Total number of chunks found
          - chunks: List of chunk dictionaries (up to max_chunks)

        Or on error:
          - success: False
          - error: Error message
    """
    # Input validation
    if not section_number or not section_number.strip():
        return {"success": False, "error": "Section number cannot be empty"}

    section_number = section_number.strip()

    # Validate that it looks like a section number (digits with optional dots)
    if not all(c.isdigit() or c == "." for c in section_number):
        return {
            "success": False,
            "error": f"Invalid section number format: '{section_number}'. Use numeric format like '2100' or '608.01'",
        }

    try:
        # Get the index
        index = _get_mpep_index()

        # Search for matching chunks
        section_pattern = f"MPEP {section_number}"
        matching_chunks = []

        for chunk, meta in zip(index.chunks, index.metadata):
            if section_pattern in meta["section"]:
                matching_chunks.append({"text": chunk, "metadata": meta})

        if not matching_chunks:
            return {
                "success": False,
                "error": f"No content found for MPEP section {section_number}. The section may not exist or the index may be incomplete.",
            }

        return {
            "success": True,
            "section": section_number,
            "total_chunks": len(matching_chunks),
            "chunks": matching_chunks[:max_chunks],
            "truncated": len(matching_chunks) > max_chunks,
        }

    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Section retrieval failed: {str(e)}"}


def check_index_status() -> dict[str, Any]:
    """
    Check if the MPEP index is available and ready to use.

    Returns:
        Dictionary with status information:
          - ready: bool
          - index_exists: bool
          - total_chunks: int (if ready)
          - message: str
    """
    try:
        index = _get_mpep_index()
        return {
            "ready": True,
            "index_exists": True,
            "total_chunks": len(index.chunks),
            "message": f"MPEP index loaded with {len(index.chunks):,} chunks",
        }
    except RuntimeError as e:
        return {"ready": False, "index_exists": False, "message": str(e)}
    except Exception as e:
        return {
            "ready": False,
            "index_exists": False,
            "message": f"Error checking index status: {str(e)}",
        }
