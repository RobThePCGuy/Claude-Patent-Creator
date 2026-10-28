"""
Non-Patent Literature Search Tools

Searches research papers and web pages for prior art that is not a patent
(journal articles, preprints, standards, product documentation) through
Firecrawl's search API. Needs FIRECRAWL_API_KEY; without it the tool returns
setup instructions and makes no request.

Tools:
    - search_non_patent_literature: Research-paper and web search for NPL prior art

Dependencies:
    - FirecrawlSearch from firecrawl_search module
"""

from typing import Any

import anyio


def register_firecrawl_tools(
    mcp,
    log_info,
    log_error,
    validate_input,
    SearchNonPatentLiteratureInput,
    track_performance,
):
    """Register non-patent literature search tools with the MCP server."""
    from firecrawl_search import FirecrawlNotConfiguredError, FirecrawlSearch

    @mcp.tool()
    @track_performance("tool_search_non_patent_literature")
    async def search_non_patent_literature(
        query: str,
        limit: int = 10,
        research_only: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Search research papers and web pages for non-patent prior art.

        Printed publications (journal articles, conference papers, preprints,
        standards, product manuals, technical web pages) are prior art just
        like patents. Use this alongside search_patents_google, which covers
        patents only.

        The default searches research papers and academic sources, strongest
        in life sciences, physics and computer science. For engineering
        topics, standards, product manuals and technical write-ups, set
        research_only=False to search the whole web.

        Writing queries:
            - Describe the technical idea in plain words, the way a paper
              abstract would ("lithium dendrite suppression with ceramic
              solid electrolyte"), rather than in claim language.
            - Run several searches with synonyms and the field's own terms.

        Results carry a title, URL and short snippet or abstract. They do not
        carry a reliable publication date: open the source and confirm the
        date before relying on a result as prior art.

        Args:
            query: What to search for
            limit: Results to return, 1-20
            research_only: True (default) searches research papers and
                academic sources; False searches the whole web

        Returns:
            Matching publications, best match first
        """
        log_info(
            "search_non_patent_literature called",
            query=query[:100],
            limit=limit,
            research_only=research_only,
        )
        try:
            validated = validate_input(
                SearchNonPatentLiteratureInput,
                query=query,
                limit=limit,
                research_only=research_only,
            )
        except ValueError as e:
            return [{"error": f"Invalid input: {e}"}]

        def _do_search():
            return FirecrawlSearch().search(
                query=validated.query,
                limit=validated.limit,
                research_only=validated.research_only,
            )

        try:
            results = await anyio.to_thread.run_sync(_do_search)
        except FirecrawlNotConfiguredError as e:
            return [{"error": str(e)}]
        except Exception as e:
            # Messages from FirecrawlSearch are already key-redacted and carry
            # no exception chain; no traceback is logged for that reason.
            log_error("search_non_patent_literature_failed", error=str(e))
            return [{"error": str(e)}]

        log_info("search_non_patent_literature: got results", count=len(results))
        if not results and validated.research_only:
            return [
                {
                    "message": "No research papers matched. This does not mean there is no "
                    "non-patent prior art: rephrase the query or retry with research_only=False "
                    "to search the whole web."
                }
            ]
        return results
