"""
EPO OPS API Search Tools

Provides MCP tools for searching European patents via the EPO Open Patent
Services (OPS) API v3.2. Supports bibliographic search, full-text claims
and description retrieval, and patent family lookups.

Tools:
    - check_epo_api_status: Check EPO OPS API availability and credential status
    - search_epo_patents: Search European patents via CQL query syntax
    - get_epo_patent: Get EP patent details including full-text claims and description
    - get_epo_patent_family: Get patent family members across all jurisdictions

Dependencies:
    - EPOClient from epo_api module
    - format_epo_result helper from epo_api module
    - Logging and monitoring from logging_config.py and monitoring.py

Note: EPO OPS is the ONLY way to get full-text claims for EP patents.
BigQuery only contains full claims text for US patents.
"""

import threading
from typing import Any

import anyio


def register_epo_tools(
    mcp,
    log_info,
    log_error,
    validate_input,
    track_performance,
):
    """Register EPO OPS API search tools with the MCP server.

    Args:
        mcp: FastMCP server instance
        log_info: Logging function for info messages
        log_error: Logging function for error messages
        validate_input: Input validation function
        track_performance: Performance tracking decorator
    """

    # Thread-safe lazy-loaded EPO client
    _epo_client = None
    _epo_lock = threading.Lock()

    def _ensure_epo_client():
        """Lazy load EPO OPS API client (thread-safe)."""
        nonlocal _epo_client
        if _epo_client is not None:
            return _epo_client
        with _epo_lock:
            # Double-check after acquiring lock
            if _epo_client is None:
                try:
                    from epo_api import EPOClient

                    _epo_client = EPOClient()
                except ImportError as e:
                    raise ValueError(
                        f"EPO API module not available: {e}. "
                        "Ensure epo_api.py is in the mcp_server directory and "
                        "xmltodict is installed: pip install xmltodict"
                    )
                except Exception as e:
                    raise ValueError(f"Failed to initialize EPO client: {e}")
        return _epo_client

    @mcp.tool()
    @track_performance("tool_check_epo_api_status")
    def check_epo_api_status() -> dict[str, Any]:
        """Check EPO OPS API availability, credential status, and quota information.

        Returns connectivity status and whether EPO_OPS_KEY and EPO_OPS_SECRET
        are configured. Use this before attempting EPO searches.
        """
        try:
            log_info("check_epo_api_status_tool_called")

            client = _ensure_epo_client()
            status = client.check_availability()

            return {
                "ready": status.get("available", False),
                "credentials_configured": status.get("credentials_configured", False),
                "xmltodict_available": status.get("xmltodict_available", False),
                "api_url": client.BASE_URL,
                "message": status.get("message", ""),
                "error": status.get("error"),
                "response_time_ms": status.get("response_time_ms"),
                "setup_url": "https://developers.epo.org/",
            }

        except ValueError as e:
            log_error("check_epo_api_status_init_failed", exc_info=True, error=str(e))
            return {
                "ready": False,
                "error": str(e),
                "message": "Failed to initialize EPO client",
                "setup_url": "https://developers.epo.org/",
            }
        except Exception as e:
            log_error("check_epo_api_status_failed", exc_info=True, error=str(e))
            return {
                "ready": False,
                "error": str(e),
                "message": "Failed to check EPO API status",
            }

    @mcp.tool()
    @track_performance("tool_search_epo_patents")
    async def search_epo_patents(query: str, limit: int = 25) -> list[dict[str, Any]]:
        """Search European patents via EPO OPS API using CQL query syntax.

        Returns bibliographic data and abstracts for matching patents.
        Use this for EP patent searches when you need claims/description text
        (not available in BigQuery for EP patents).

        Supports CQL operators:
            - Simple keywords: searched in title + abstract
            - ta="neural network"   (title + abstract)
            - ti="machine learning" (title only)
            - in="Smith"            (inventor)
            - pa="Google"           (applicant)
            - ic="G06F"            (IPC code)
            - pd=20240101          (publication date)

        Args:
            query: Search query (plain keywords or CQL syntax)
            limit: Maximum results to return (default 25, max 100)

        Returns:
            List of patent result dictionaries with bibliographic data.
        """
        log_info(
            "search_epo_patents_tool_called",
            query_length=len(query),
            limit=limit,
        )
        try:
            # Clamp limit
            limit = max(1, min(limit, 100))

            def _do_search():
                client = _ensure_epo_client()

                # Check credentials before making request
                if not client.key or not client.secret:
                    return [{
                        "error": "EPO OPS credentials not configured. "
                                 "Set EPO_OPS_KEY and EPO_OPS_SECRET environment variables.",
                        "setup_url": "https://developers.epo.org/",
                    }]

                results = client.search_published(
                    query=query,
                    range_begin=1,
                    range_end=limit,
                )

                # Format results for MCP output
                from epo_api import format_epo_result

                formatted_results = []
                for i, patent in enumerate(results, 1):
                    formatted_results.append({
                        "rank": i,
                        "publication_number": patent.get("publication_number", ""),
                        "country": patent.get("country", ""),
                        "kind_code": patent.get("kind_code", ""),
                        "family_id": patent.get("family_id", ""),
                        "title": patent.get("title"),
                        "abstract": patent.get("abstract"),
                        "publication_date": patent.get("publication_date"),
                        "filing_date": patent.get("filing_date"),
                        "inventors": patent.get("inventors", []),
                        "applicants": patent.get("applicants", []),
                        "ipc_codes": patent.get("ipc_codes", []),
                        "cpc_codes": patent.get("cpc_codes", []),
                        "formatted": format_epo_result(patent, verbose=False),
                    })

                return formatted_results

            log_info("search_epo_patents: running query in thread")
            results = await anyio.to_thread.run_sync(_do_search)
            log_info(
                "search_epo_patents: got results",
                count=len(results),
                first_patent=(
                    results[0].get("publication_number") if results else None
                ),
            )
            return results

        except ValueError as e:
            log_error(
                "search_epo_patents_validation_failed",
                exc_info=True,
                error=str(e),
            )
            return [{"error": f"Invalid input: {str(e)}"}]
        except Exception as e:
            log_error(
                "search_epo_patents_failed",
                exc_info=True,
                query=query[:100] if isinstance(query, str) else "",
            )
            return [{"error": f"EPO patent search failed: {str(e)}"}]

    @mcp.tool()
    @track_performance("tool_get_epo_patent")
    async def get_epo_patent(patent_number: str) -> dict[str, Any]:
        """Get EP patent details including full-text claims and description via EPO OPS.

        This is the ONLY way to get full-text claims for EP patents (BigQuery only
        has full claims text for US patents). Returns bibliographic data plus
        complete claims and description text.

        Args:
            patent_number: Patent number with country prefix (e.g., "EP1234567",
                          "EP1234567A1"). Country prefix is required.

        Returns:
            Patent details dictionary with biblio, claims text, and description text.
        """
        log_info("get_epo_patent_tool_called", patent_number=patent_number)
        try:

            def _do_get():
                client = _ensure_epo_client()

                if not client.key or not client.secret:
                    return {
                        "error": "EPO OPS credentials not configured. "
                                 "Set EPO_OPS_KEY and EPO_OPS_SECRET environment variables.",
                        "setup_url": "https://developers.epo.org/",
                    }

                # Get bibliographic data
                biblio = client.get_patent(patent_number)

                if biblio.get("error"):
                    return biblio

                # Get full-text claims
                try:
                    claims_text = client.get_claims(patent_number)
                except Exception as claims_err:
                    claims_text = f"Claims not available: {claims_err}"

                # Get full-text description
                try:
                    description_text = client.get_description(patent_number)
                except Exception as desc_err:
                    description_text = f"Description not available: {desc_err}"

                # Combine into single result
                from epo_api import format_epo_result

                result = {
                    "patent_number": patent_number,
                    "publication_number": biblio.get("publication_number", ""),
                    "country": biblio.get("country", ""),
                    "kind_code": biblio.get("kind_code", ""),
                    "family_id": biblio.get("family_id", ""),
                    "title": biblio.get("title"),
                    "abstract": biblio.get("abstract"),
                    "publication_date": biblio.get("publication_date"),
                    "filing_date": biblio.get("filing_date"),
                    "inventors": biblio.get("inventors", []),
                    "applicants": biblio.get("applicants", []),
                    "ipc_codes": biblio.get("ipc_codes", []),
                    "cpc_codes": biblio.get("cpc_codes", []),
                    "claims_text": claims_text,
                    "claims_length": len(claims_text),
                    "description_text": description_text,
                    "description_length": len(description_text),
                    "formatted": format_epo_result(biblio, verbose=True),
                }

                return result

            log_info("get_epo_patent: running queries in thread")
            result = await anyio.to_thread.run_sync(_do_get)

            if result.get("error"):
                log_info(
                    "get_epo_patent: error result",
                    error=result["error"],
                )
            else:
                log_info(
                    "get_epo_patent: got result",
                    # title may be None (EP publication with no English title)
                    title=(result.get("title") or "")[:50],
                    claims_length=result.get("claims_length", 0),
                    description_length=result.get("description_length", 0),
                )

            return result

        except ValueError as e:
            log_error(
                "get_epo_patent_validation_failed",
                exc_info=True,
                error=str(e),
            )
            return {"error": f"Invalid input: {str(e)}"}
        except Exception as e:
            log_error(
                "get_epo_patent_failed",
                exc_info=True,
                patent_number=patent_number,
            )
            return {"error": f"Failed to retrieve patent from EPO: {str(e)}"}

    @mcp.tool()
    @track_performance("tool_get_epo_patent_family")
    async def get_epo_patent_family(patent_number: str) -> list[dict[str, Any]]:
        """Get patent family members across all jurisdictions via EPO OPS.

        Patent families link related applications filed in different countries
        for the same invention. Use this to:
        - Find the US equivalent of an EP patent (for BigQuery full-text access)
        - Map an invention's worldwide patent coverage
        - Cross-reference prior art across jurisdictions

        Args:
            patent_number: Patent number with country prefix (e.g., "EP1234567").

        Returns:
            List of family member dictionaries with publication info and country codes.
        """
        log_info("get_epo_patent_family_tool_called", patent_number=patent_number)
        try:

            def _do_family():
                client = _ensure_epo_client()

                if not client.key or not client.secret:
                    return [{
                        "error": "EPO OPS credentials not configured. "
                                 "Set EPO_OPS_KEY and EPO_OPS_SECRET environment variables.",
                        "setup_url": "https://developers.epo.org/",
                    }]

                members = client.get_patent_family(patent_number)

                # Add summary info
                if members and not members[0].get("error"):
                    jurisdictions = list({m.get("country", "?") for m in members})
                    for member in members:
                        member["source_patent"] = patent_number
                        member["total_family_members"] = len(members)
                        member["jurisdictions"] = jurisdictions

                return members

            log_info("get_epo_patent_family: running query in thread")
            results = await anyio.to_thread.run_sync(_do_family)

            if results and not results[0].get("error"):
                jurisdictions = list({m.get("country", "?") for m in results})
                log_info(
                    "get_epo_patent_family: got results",
                    count=len(results),
                    jurisdictions=jurisdictions,
                )
            else:
                log_info(
                    "get_epo_patent_family: error or no results",
                    error=results[0].get("error") if results else "empty",
                )

            return results

        except ValueError as e:
            log_error(
                "get_epo_patent_family_validation_failed",
                exc_info=True,
                error=str(e),
            )
            return [{"error": f"Invalid input: {str(e)}"}]
        except Exception as e:
            log_error(
                "get_epo_patent_family_failed",
                exc_info=True,
                patent_number=patent_number,
            )
            return [{"error": f"EPO patent family search failed: {str(e)}"}]
