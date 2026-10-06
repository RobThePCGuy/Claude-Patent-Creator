"""
Google Patents Search Tools

Worldwide full-text patent search (claims and description included) through
SerpApi's Google Patents API. One search credit per call: 250 free a month,
then a few cents each, versus ~341 GiB (~$2) for a BigQuery keyword search.

Tools:
    - check_google_patents_status: Key configured? Searches left this month?
    - search_patents_google: Full-text keyword search, worldwide by default

Dependencies:
    - GooglePatentsSearch from google_patents_search module
"""

from typing import Any, Optional

import anyio


def register_google_patents_tools(
    mcp,
    log_info,
    log_error,
    validate_input,
    SearchGooglePatentsInput,
    track_performance,
):
    """Register Google Patents search tools with the MCP server."""
    from google_patents_search import (
        GooglePatentsNotConfiguredError,
        GooglePatentsQuotaError,
        GooglePatentsSearch,
    )

    @mcp.tool()
    @track_performance("tool_check_google_patents_status")
    def check_google_patents_status() -> dict[str, Any]:
        """Check whether Google Patents search is set up and how many searches are left.

        Does not use a search credit.
        """
        searcher = GooglePatentsSearch()
        if not searcher.is_configured():
            return {
                "ready": False,
                "message": GooglePatentsSearch.setup_message(),
                "fallback": "search_patents_bigquery (about $2 a search past Google's free monthly TiB)",
            }
        try:
            return {"ready": True, **searcher.account()}
        except Exception as e:
            # account() raises key-redacted messages with no chain; no traceback logged.
            log_error("check_google_patents_status_failed", error=str(e))
            return {"ready": False, "error": str(e)}

    @mcp.tool()
    @track_performance("tool_search_patents_google")
    async def search_patents_google(
        query: str,
        limit: int = 20,
        country: Optional[str] = None,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Search Google Patents full text worldwide. RECOMMENDED for prior-art keyword search.

        Matches words anywhere in the patent, including the claims and the
        description, across US, EP, WO, JP, CN, KR and other offices, and stays
        current. Costs one search credit per call (free plan: 250 a month), so
        prefer limit=100 over several smaller calls. Each result is one
        publication; a family can appear more than once (e.g. US and EP).

        Writing queries:
            - All words must match. Put "double quotes" around exact phrases.
            - Lead with the invention's distinctive terms. Common words
              ("device", "system", "heart valve") match thousands of patents and
              can push the closest art below the first page.
            - Run several searches with synonyms; there is no stemming.

        Results carry a matching snippet, not the full abstract or claims. Get
        full claims with get_patents_bigquery (US) or get_epo_patent (EP).

        If no key is configured this returns setup instructions; fall back to
        search_patents_bigquery (about $2 a search past the free monthly TiB).

        Args:
            query: Search keywords or "quoted phrases"
            limit: Results to return, 1-100 (same cost either way)
            country: Two-letter office code to restrict (e.g. "US"); omit for worldwide
            start_year: Filed on or after this year
            end_year: Filed on or before this year

        Returns:
            Matching publications, best match first
        """
        log_info("search_patents_google called", query=query[:100], limit=limit, country=country)
        try:
            validated = validate_input(
                SearchGooglePatentsInput,
                query=query,
                limit=limit,
                country=country,
                start_year=start_year,
                end_year=end_year,
            )
        except ValueError as e:
            return [{"error": f"Invalid input: {e}"}]

        def _do_search():
            return GooglePatentsSearch().search(
                query=validated.query,
                country=validated.country,
                limit=validated.limit,
                start_year=validated.start_year,
                end_year=validated.end_year,
            )

        try:
            results = await anyio.to_thread.run_sync(_do_search)
        except (GooglePatentsNotConfiguredError, GooglePatentsQuotaError) as e:
            return [{"error": str(e), "fallback": "search_patents_bigquery"}]
        except Exception as e:
            # Messages from GooglePatentsSearch are already key-redacted and
            # carry no exception chain; no traceback is logged for that reason.
            log_error("search_patents_google_failed", error=str(e))
            return [{"error": str(e), "fallback": "search_patents_bigquery"}]

        log_info("search_patents_google: got results", count=len(results))
        return results
