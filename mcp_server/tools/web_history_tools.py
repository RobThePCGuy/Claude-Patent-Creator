"""
Web History Tool

Tools:
    - check_web_history: earliest archived capture of a web page, for dating
      public disclosures (product pages, demos, docs, repositories)

Dependencies:
    - web_history module (Internet Archive CDX index; free, no key)
"""

from typing import Any

import anyio


def register_web_history_tools(mcp, log_info, log_error, track_performance):
    """Register the web history tool with the MCP server."""
    from web_history import WebHistoryError, web_history

    @mcp.tool()
    @track_performance("tool_check_web_history")
    async def check_web_history(url: str, match: str = "exact", limit: int = 5) -> dict[str, Any]:
        """
        When was a web page first public? Looks it up in the Internet Archive. Free, no key.

        Use it in the disclosure audit to date the inventor's own product
        pages, demos, docs and public repositories, and to date web prior art.
        Web fetch tools are often refused by web.archive.org; this asks the
        archive's index directly.

        A capture proves the page was public NO LATER than that date. It may
        have been public earlier, because the archive only records when it
        visited. No capture is not evidence the page was never public.

        Args:
            url: The page, for example "example.com/product" or "https://example.com/"
            match: "exact" (this page), "prefix" (this page and everything under it),
                "host" (the whole host) or "domain" (the host and its subdomains)
            limit: How many of the earliest captures to return (1-25, one per day)

        Returns:
            first_captures (earliest first, each with an archive link to open),
            latest_capture, and a plain-English "meaning" of what the dates prove
        """
        log_info("check_web_history called", match=match)
        try:
            return await anyio.to_thread.run_sync(lambda: web_history(url, match=match, limit=limit))
        except ValueError as e:
            return {"error": f"Invalid input: {e}"}
        except WebHistoryError as e:
            log_error("check_web_history_failed", error=str(e))
            return {"error": str(e)}
