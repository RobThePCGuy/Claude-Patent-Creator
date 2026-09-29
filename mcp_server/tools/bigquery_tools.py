"""
BigQuery Patent Search Tools

Provides MCP tools for fast, cloud-based patent searching using Google BigQuery.
Searches across 100M+ worldwide patents with full text indexing for US patents.

Tools:
    - check_bigquery_status: Verify BigQuery availability and configuration
    - search_patents_bigquery: Fast keyword search across patent database
    - get_patent_bigquery: Retrieve patent details by publication number
    - get_patents_bigquery: Retrieve details for up to 50 patents in one query
    - search_patents_by_cpc_bigquery: Search patents by CPC classification code
    - search_patents_by_ipc_bigquery: Search patents by IPC classification code
    - search_patent_family_bigquery: Find related patents across jurisdictions

Dependencies:
    - BigQueryPatentSearch from bigquery_search module
    - Validation models from validation.py
    - Logging and monitoring from logging_config.py and monitoring.py
"""

import threading
from typing import Any, Optional

import anyio


def register_bigquery_tools(
    mcp,
    log_info,
    log_error,
    log_warning,
    validate_input,
    SearchBigQueryInput,
    GetPatentInput,
    CPCSearchInput,
    track_performance,
    IPCSearchInput=None,
    FamilySearchInput=None,
):
    """Register BigQuery patent search tools with the MCP server.

    Args:
        mcp: MCPServer instance
        log_info: Logging function for info messages
        log_error: Logging function for error messages
        log_warning: Logging function for warning messages
        validate_input: Input validation function
        SearchBigQueryInput: Pydantic model for BigQuery search validation
        GetPatentInput: Pydantic model for get patent validation
        CPCSearchInput: Pydantic model for CPC search validation
        track_performance: Performance tracking decorator
    """

    # Thread-safe lazy-loaded BigQuery searcher
    _bigquery_searcher = None
    _bigquery_lock = threading.Lock()

    def _ensure_bigquery_searcher():
        """Lazy load BigQuery patent searcher (thread-safe)"""
        nonlocal _bigquery_searcher
        if _bigquery_searcher is not None:
            return _bigquery_searcher
        with _bigquery_lock:
            # Double-check after acquiring lock
            if _bigquery_searcher is None:
                try:
                    from bigquery_search import BigQueryPatentSearch

                    _bigquery_searcher = BigQueryPatentSearch()
                except ImportError as e:
                    raise ValueError(
                        f"BigQuery not available: {e}. "
                        "Install with: pip install google-cloud-bigquery db-dtypes"
                    )
                except Exception as e:
                    raise ValueError(f"Failed to initialize BigQuery: {e}")

        return _bigquery_searcher

    @mcp.tool()
    def check_bigquery_status() -> dict[str, Any]:
        """Check if Google BigQuery patent search is available and configured."""
        log_info("check_bigquery_status called")
        try:
            from bigquery_search import check_bigquery_available

            result = check_bigquery_available()
            log_info(
                "check_bigquery_status result",
                available=result.get("available"),
                keys=list(result.keys()),
            )
            return result
        except ImportError as e:
            log_error("check_bigquery_status import error", exc_info=True, error=str(e))
            return {
                "available": False,
                "error": "google-cloud-bigquery not installed",
                "install_command": "pip install google-cloud-bigquery db-dtypes",
            }
        except Exception as e:
            log_error("check_bigquery_status exception", exc_info=True, error=str(e))
            return {"available": False, "error": str(e)}

    @mcp.tool()
    async def search_patents_bigquery(
        query: str,
        limit: int = 20,
        country: str = "US",
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Search patents using Google BigQuery (fast, cloud-based, 100M+ patents).

        This is the RECOMMENDED method for patent prior art search. No local indexing required.
        Searches across 100M+ worldwide patents or 12M+ US patents with full text.

        Args:
            query: Search keywords or phrase
            limit: Maximum results to return (default 20, max 100)
            country: Country code (US, EP, JP, CN, etc.)
            start_year: Filter by filing year >= start_year
            end_year: Filter by filing year <= end_year

        Returns:
            List of matching patents with title, abstract, dates, etc.
        """
        log_info(
            "search_patents_bigquery called",
            query=query,
            limit=limit,
            country=country,
            start_year=start_year,
            end_year=end_year,
        )
        try:
            # Validate inputs
            validated = validate_input(
                SearchBigQueryInput,
                query=query,
                limit=limit,
                country=country,
                start_year=start_year,
                end_year=end_year,
            )
            query = validated.query
            limit = validated.limit
            country = validated.country
            start_year = validated.start_year
            end_year = validated.end_year

            def _do_search():
                searcher = _ensure_bigquery_searcher()
                return searcher.search_by_keywords(
                    query=query,
                    country=country,
                    limit=min(limit, 100),
                    start_year=start_year,
                    end_year=end_year,
                )

            log_info("search_patents_bigquery: running query in thread")
            results = await anyio.to_thread.run_sync(_do_search)
            log_info(
                "search_patents_bigquery: got results",
                count=len(results),
                first_patent=results[0].get("patent_number") if results else None,
            )
            return results

        except ValueError as e:
            log_error("search_patents_bigquery ValueError", exc_info=True, error=str(e))
            return [{"error": str(e)}]
        except Exception as e:
            log_error("search_patents_bigquery exception", exc_info=True, error=str(e))
            return [{"error": f"BigQuery search failed: {str(e)}"}]

    @mcp.tool()
    async def get_patent_bigquery(
        patent_number: str,
        include_abstract: bool = False,
        include_claims: bool = True,
        include_description: bool = False,
    ) -> dict[str, Any]:
        """
        Get patent details from BigQuery by publication number.

        Always returns bibliographic data (title, dates, family_id, country,
        CPC/IPC codes). Text sections are opt-in because BigQuery bills each
        as a scan of that column across the whole corpus, even for one
        patent: claims ~119 GiB (default on), abstract ~201 GiB (search
        results already include it), description ~1 TiB (exceeds the default
        cost cap; only request it when the full text is essential).
        Sections not requested are omitted from the result.

        For more than one patent, use get_patents_bigquery: a batch of up to
        50 costs the same as one lookup.

        Args:
            patent_number: Patent publication number (e.g., "US10123456B2", "EP1234567A1")
            include_abstract: Include the abstract
            include_claims: Include the claims text
            include_description: Include the full description

        Returns:
            Patent details: bibliographic fields plus the requested sections
        """
        log_info("get_patent_bigquery called", patent_number=patent_number)
        try:
            # Validate inputs
            validated = validate_input(GetPatentInput, patent_number=patent_number)
            patent_number = validated.patent_number

            def _do_get():
                searcher = _ensure_bigquery_searcher()
                return searcher.get_patent_details(
                    patent_number,
                    include_abstract=include_abstract,
                    include_claims=include_claims,
                    include_description=include_description,
                )

            log_info("get_patent_bigquery: running query in thread")
            result = await anyio.to_thread.run_sync(_do_get)

            if not result:
                log_info("get_patent_bigquery: no result found")
                return {"error": f"Patent {patent_number} not found in BigQuery"}

            log_info("get_patent_bigquery: got result", title=result.get("title", "")[:50])
            return result

        except ValueError as e:
            log_error("get_patent_bigquery ValueError", exc_info=True, error=str(e))
            return {"error": str(e)}
        except Exception as e:
            log_error("get_patent_bigquery exception", exc_info=True, error=str(e))
            return {"error": f"Failed to retrieve patent: {str(e)}"}

    @mcp.tool()
    async def get_patents_bigquery(
        patent_numbers: list[str],
        include_abstract: bool = False,
        include_claims: bool = True,
        include_description: bool = False,
    ) -> dict[str, Any]:
        """
        Get details for up to 50 patents from BigQuery in one query.

        Costs the same as a single get_patent_bigquery call with the same
        include_* flags (BigQuery bills per column scanned, not per patent),
        so use this whenever you need details for several patents, e.g. the
        top hits of a prior-art search. Same section options and costs as
        get_patent_bigquery.

        Args:
            patent_numbers: Publication numbers (e.g., ["US10123456B2", "EP1234567A1"])
            include_abstract: Include abstracts
            include_claims: Include claims text
            include_description: Include full descriptions

        Returns:
            {"patents": {number: details}, "not_found": [numbers]}
        """
        log_info("get_patents_bigquery called", count=len(patent_numbers))
        try:
            numbers = [
                validate_input(GetPatentInput, patent_number=n).patent_number
                for n in patent_numbers
            ]

            def _do_get():
                searcher = _ensure_bigquery_searcher()
                return searcher.get_patents_details(
                    numbers,
                    include_abstract=include_abstract,
                    include_claims=include_claims,
                    include_description=include_description,
                )

            patents = await anyio.to_thread.run_sync(_do_get)
            return {
                "patents": patents,
                "not_found": [n for n in dict.fromkeys(numbers) if n not in patents],
            }

        except ValueError as e:
            log_error("get_patents_bigquery ValueError", exc_info=True, error=str(e))
            return {"error": str(e)}
        except Exception as e:
            log_error("get_patents_bigquery exception", exc_info=True, error=str(e))
            return {"error": f"Failed to retrieve patents: {str(e)}"}

    @mcp.tool()
    async def search_patents_by_cpc_bigquery(
        cpc_code: str, limit: int = 20, country: str = "US"
    ) -> list[dict[str, Any]]:
        """
        Search patents by CPC classification code using BigQuery.

        Args:
            cpc_code: CPC code or prefix (e.g., "G06F", "G06F16/", "H04L29/06")
            limit: Maximum results (default 20, max 100)
            country: Country code filter

        Returns:
            List of patents matching the CPC code
        """
        log_info(
            "search_patents_by_cpc_bigquery called", cpc_code=cpc_code, limit=limit, country=country
        )
        try:
            # Validate inputs
            validated = validate_input(
                CPCSearchInput, cpc_code=cpc_code, limit=limit, country=country
            )
            cpc_code = validated.cpc_code
            limit = validated.limit
            country = validated.country

            def _do_search():
                searcher = _ensure_bigquery_searcher()
                return searcher.search_by_cpc(
                    cpc_code=cpc_code, limit=min(limit, 100), country=country
                )

            log_info("search_patents_by_cpc_bigquery: running query in thread")
            results = await anyio.to_thread.run_sync(_do_search)
            log_info("search_patents_by_cpc_bigquery: got results", count=len(results))
            return results

        except ValueError as e:
            log_error("search_patents_by_cpc_bigquery ValueError", exc_info=True, error=str(e))
            return [{"error": str(e)}]
        except Exception as e:
            log_error("search_patents_by_cpc_bigquery exception", exc_info=True, error=str(e))
            return [{"error": f"CPC search failed: {str(e)}"}]

    @mcp.tool()
    async def search_patents_by_ipc_bigquery(
        ipc_code: str, limit: int = 20, country: str = "US"
    ) -> list[dict[str, Any]]:
        """
        Search patents by IPC (International Patent Classification) code using BigQuery.

        IPC is valuable for older patents (pre-2013, before CPC) and non-US patents
        that may have IPC but lack CPC codes.

        Args:
            ipc_code: IPC code or prefix (e.g., "G06F", "H04L29/06", "A61K")
            limit: Maximum results (default 20, max 100)
            country: Country code filter (US, EP, WO, JP, CN, etc.)

        Returns:
            List of patents matching the IPC code
        """
        log_info(
            "search_patents_by_ipc_bigquery called", ipc_code=ipc_code, limit=limit, country=country
        )
        try:
            if IPCSearchInput:
                validated = validate_input(
                    IPCSearchInput, ipc_code=ipc_code, limit=limit, country=country
                )
                ipc_code = validated.ipc_code
                limit = validated.limit
                country = validated.country

            def _do_search():
                searcher = _ensure_bigquery_searcher()
                return searcher.search_by_ipc(
                    ipc_code=ipc_code, limit=min(limit, 100), country=country
                )

            log_info("search_patents_by_ipc_bigquery: running query in thread")
            results = await anyio.to_thread.run_sync(_do_search)
            log_info("search_patents_by_ipc_bigquery: got results", count=len(results))
            return results

        except ValueError as e:
            log_error("search_patents_by_ipc_bigquery ValueError", exc_info=True, error=str(e))
            return [{"error": str(e)}]
        except Exception as e:
            log_error("search_patents_by_ipc_bigquery exception", exc_info=True, error=str(e))
            return [{"error": f"IPC search failed: {str(e)}"}]

    @mcp.tool()
    async def search_patent_family_bigquery(
        family_id: int, limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        Find all patent publications sharing a family ID across jurisdictions.

        Patent families link related patents filed in multiple countries. Use this to:
        - Find the US family member of an EP/WO patent (for full claims text)
        - Map an invention's worldwide patent coverage
        - Cross-reference prior art across jurisdictions

        Args:
            family_id: Patent family identifier (from get_patent_bigquery results)
            limit: Maximum results (default 50, max 100)

        Returns:
            List of related patents across all jurisdictions with country codes
        """
        log_info("search_patent_family_bigquery called", family_id=family_id, limit=limit)
        try:
            if FamilySearchInput:
                validated = validate_input(
                    FamilySearchInput, family_id=family_id, limit=limit
                )
                family_id = validated.family_id
                limit = validated.limit

            def _do_search():
                searcher = _ensure_bigquery_searcher()
                return searcher.search_patent_family(
                    family_id=family_id, limit=min(limit, 100)
                )

            log_info("search_patent_family_bigquery: running query in thread")
            results = await anyio.to_thread.run_sync(_do_search)
            jurisdictions = list({p["country"] for p in results})
            log_info(
                "search_patent_family_bigquery: got results",
                count=len(results),
                jurisdictions=jurisdictions,
            )
            return results

        except ValueError as e:
            log_error("search_patent_family_bigquery ValueError", exc_info=True, error=str(e))
            return [{"error": str(e)}]
        except Exception as e:
            log_error("search_patent_family_bigquery exception", exc_info=True, error=str(e))
            return [{"error": f"Family search failed: {str(e)}"}]
