"""
Non-Patent Literature Search Tools

Papers and preprints are prior art too. These tools search free scholarly
indexes (OpenAlex, arXiv, Semantic Scholar) that need no account and cost
nothing per search.

Tools:
    - search_non_patent_literature: Papers and preprints matching keywords,
      optionally limited to those published before the priority date

Dependencies:
    - LiteratureSearch from literature_search module
"""

from typing import Any, Optional

import anyio


def register_literature_tools(
    mcp,
    log_info,
    log_error,
    validate_input,
    SearchLiteratureInput,
    track_performance,
):
    """Register non-patent literature search tools with the MCP server."""
    from literature_search import LiteratureSearch

    @mcp.tool()
    @track_performance("tool_search_non_patent_literature")
    async def search_non_patent_literature(
        query: str,
        limit: int = 20,
        published_before: Optional[str] = None,
        published_after: Optional[str] = None,
        sources: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Search scholarly papers and preprints for non-patent prior art. Free, no key needed.

        Searches OpenAlex (~250M works: journals, conferences, PubMed, arXiv),
        arXiv directly (preprints, often the earliest public version), and
        Semantic Scholar at once, then merges duplicates. Run it alongside the
        patent searches: examiners cite papers as prior art.

        Writing queries:
            - Lead with the invention's distinctive technical terms.
            - Put "double quotes" around exact phrases.
            - Papers use academic vocabulary, not claim language: search
              "lithium dendrite suppression", not "means for inhibiting growth".
            - Run several searches with synonyms.

        Set published_before to the invention's priority date to see only
        papers the indexes date before it. Index dates are sometimes wrong,
        so each result's date is then cross-checked with the publisher's DOI
        record (Crossref, free). A result with "date_check" has a date that
        may be wrong or too close to call: tell the user to confirm it on the
        publisher's page before treating it as prior art. "date_note" is a
        milder remark (an old paper whose DOI came late, usually fine), and
        "date_source" says where each date came from; "index only, not
        cross-checked" dates deserve a look before citing. Each result says
        which sources found it, with a DOI or arXiv id, a link, and the abstract.

        Reading the result:
            - "sources" says, per source, whether it answered. A source that
              failed or was busy was NOT searched; its message says why and
              how to fix it (usually a free key).
            - No results means no match in the sources that answered, never
              proof that no prior art exists. Say which sources were searched.

        Optional free keys (set in .env or the patent-creator config):
            OPENALEX_API_KEY raises OpenAlex's daily allowance (~100 searches
            keyless). SEMANTIC_SCHOLAR_API_KEY makes Semantic Scholar reliable;
            its keyless pool is shared and often busy.

        Args:
            query: Search keywords or "quoted phrases"
            limit: Papers to return after merging, 1-50
            published_before: YYYY-MM-DD; only papers published before this day
            published_after: YYYY-MM-DD; only papers published on or after this day
            sources: Any of "openalex", "arxiv", "semantic_scholar"; default all

        Returns:
            {"results": [papers], "sources": {per-source status}, "note": summary}
        """
        log_info(
            "search_non_patent_literature called",
            query=query[:100],
            limit=limit,
            published_before=published_before,
        )
        try:
            validated = validate_input(
                SearchLiteratureInput,
                query=query,
                limit=limit,
                published_before=published_before,
                published_after=published_after,
                sources=sources,
            )
        except ValueError as e:
            return {"error": f"Invalid input: {e}"}

        before = validated.published_before.isoformat() if validated.published_before else None
        after = validated.published_after.isoformat() if validated.published_after else None

        def _do_search():
            return LiteratureSearch().search(
                query=validated.query,
                limit=validated.limit,
                published_before=before,
                published_after=after,
                sources=validated.sources,
            )

        try:
            result = await anyio.to_thread.run_sync(_do_search)
        except Exception as e:
            # Per-source failures are reported inside the result; reaching here
            # means the search could not run at all.
            log_error("search_non_patent_literature_failed", error=str(e))
            return {"error": f"Literature search failed: {type(e).__name__}: {e}"}

        log_info(
            "search_non_patent_literature: got results",
            count=len(result["results"]),
            sources={k: v["status"] for k, v in result["sources"].items()},
        )
        return result
