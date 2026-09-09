"""
USPTO API Search Tools

Provides MCP tools for searching the USPTO Open Data Portal API (live database).
Requires USPTO_API_KEY environment variable for authentication.

Tools:
    - search_uspto_api: Search patents with filters for year range and application type
    - get_uspto_patent: Get detailed patent information by patent number
    - get_recent_uspto_patents: Retrieve recently granted patents
    - check_uspto_api_status: Check USPTO API accessibility and API key validity

Dependencies:
    - USPTOClient from uspto_api module
    - format_patent_result helper from uspto_api module
    - Validation models from validation.py
    - Logging and monitoring from logging_config.py and monitoring.py
"""

from typing import Any, Optional


def register_uspto_tools(
    mcp,
    log_info,
    log_error,
    validate_input,
    SearchUSPTOInput,
    GetPatentInput,
    track_performance,
):
    """Register USPTO API search tools with the MCP server.

    Args:
        mcp: MCPServer instance
        log_info: Logging function for info messages
        log_error: Logging function for error messages
        validate_input: Input validation function
        SearchUSPTOInput: Pydantic model for search validation
        GetPatentInput: Pydantic model for patent retrieval validation
        track_performance: Performance tracking decorator
    """

    # Maintain USPTO client state within register function scope
    uspto_client = None

    def _ensure_uspto_client():
        """Lazy load USPTO API client"""
        nonlocal uspto_client
        if uspto_client is None:
            from uspto_api import USPTOClient

            uspto_client = USPTOClient()
        return uspto_client

    @mcp.tool()
    @track_performance("tool_search_uspto_api")
    def search_uspto_api(
        query: str,
        limit: int = 25,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        application_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Search USPTO Open Data Portal API (live database). Requires USPTO_API_KEY environment variable. Supports year range and application type filters."""
        try:
            # Validate inputs
            validated = validate_input(
                SearchUSPTOInput,
                query=query,
                limit=limit,
                start_year=start_year,
                end_year=end_year,
                application_type=application_type,
                status=status,
            )
            query = validated.query
            limit = validated.limit
            start_year = validated.start_year
            end_year = validated.end_year
            application_type = validated.application_type
            status = validated.status

            log_info("search_uspto_api_tool_called", query_length=len(query), limit=limit)

            client = _ensure_uspto_client()

            # Check if API key is available
            if not client.api_key:
                return [
                    {
                        "error": "No USPTO API key found. Set USPTO_API_KEY environment variable.",
                        "info": "Get your API key at: https://data.uspto.gov/myodp",
                    }
                ]

            # Perform search
            results = client.search_patents_simple(
                query=query,
                limit=min(limit, 100),
                start_year=start_year,
                end_year=end_year,
                application_type=application_type,
                status=status,
            )

            # Format results
            from uspto_api import format_patent_result

            formatted_results = []
            for i, patent in enumerate(results, 1):
                formatted_results.append(
                    {
                        "rank": i,
                        "patent_number": patent.patent_number,
                        "application_number": patent.application_number,
                        "title": patent.title,
                        "filing_date": patent.filing_date,
                        "grant_date": patent.grant_date,
                        "type": patent.application_type,
                        "status": patent.status,
                        "inventors": patent.inventors,
                        "applicants": patent.applicants,
                        "formatted": format_patent_result(patent, verbose=False),
                    }
                )

            return formatted_results

        except ValueError as e:
            log_error("search_uspto_api_validation_failed", exc_info=True, error=str(e))
            return [{"error": f"Invalid input: {str(e)}"}]
        except Exception as e:
            log_error(
                "search_uspto_api_failed",
                exc_info=True,
                query=query[:100] if isinstance(query, str) else "",
            )
            return [{"error": f"USPTO API search failed: {str(e)}"}]

    @mcp.tool()
    @track_performance("tool_get_uspto_patent")
    def get_uspto_patent(patent_number: str) -> dict[str, Any]:
        """Get detailed patent information from USPTO API by patent number (e.g., "11234567" or "US11234567")."""
        try:
            # Validate inputs
            validated = validate_input(GetPatentInput, patent_number=patent_number)
            patent_number = validated.patent_number

            log_info("get_uspto_patent_tool_called", patent_number=patent_number)

            client = _ensure_uspto_client()

            if not client.api_key:
                return {
                    "error": "No USPTO API key found. Set USPTO_API_KEY environment variable.",
                    "info": "Get your API key at: https://data.uspto.gov/myodp",
                }

            # Clean patent number
            clean_number = patent_number.replace("US", "").replace("us", "").replace(",", "")

            # Get patent
            patent = client.get_patent_by_number(clean_number)

            if not patent:
                return {"error": f"Patent {patent_number} not found in USPTO database"}

            from uspto_api import format_patent_result

            result = {
                "patent_number": patent.patent_number,
                "application_number": patent.application_number,
                "title": patent.title,
                "filing_date": patent.filing_date,
                "grant_date": patent.grant_date,
                "type": patent.application_type,
                "status": patent.status,
                "inventors": patent.inventors,
                "applicants": patent.applicants,
                "formatted": format_patent_result(patent, verbose=True),
                "raw_metadata": patent.raw_data.get("applicationMetaData", {}),
            }
            return result

        except ValueError as e:
            log_error("get_uspto_patent_validation_failed", exc_info=True, error=str(e))
            return {"error": f"Invalid input: {str(e)}"}
        except Exception as e:
            log_error("get_uspto_patent_failed", exc_info=True, patent_number=patent_number)
            return {"error": f"Failed to retrieve patent: {str(e)}"}

    @mcp.tool()
    @track_performance("tool_get_recent_uspto_patents")
    def get_recent_uspto_patents(
        days: int = 7, application_type: str = "Utility", limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get recently granted patents from USPTO API. Default: last 7 days of utility patents."""
        try:
            log_info(
                "get_recent_uspto_patents_tool_called",
                days=days,
                application_type=application_type,
                limit=limit,
            )

            client = _ensure_uspto_client()

            if not client.api_key:
                return [
                    {
                        "error": "No USPTO API key found. Set USPTO_API_KEY environment variable.",
                        "info": "Get your API key at: https://data.uspto.gov/myodp",
                    }
                ]

            # Get recent patents
            results = client.get_recent_patents(
                days=days, application_type=application_type, limit=limit
            )

            # Format results
            from uspto_api import format_patent_result

            formatted_results = []
            for i, patent in enumerate(results, 1):
                formatted_results.append(
                    {
                        "rank": i,
                        "patent_number": patent.patent_number,
                        "title": patent.title,
                        "grant_date": patent.grant_date,
                        "filing_date": patent.filing_date,
                        "inventors": patent.inventors,
                        "formatted": format_patent_result(patent),
                    }
                )

            return formatted_results

        except Exception as e:
            log_error("get_recent_uspto_patents_failed", exc_info=True, days=days)
            return [{"error": f"Failed to retrieve recent patents: {str(e)}"}]

    @mcp.tool()
    @track_performance("tool_check_uspto_api_status")
    def check_uspto_api_status() -> dict[str, Any]:
        """Check USPTO API accessibility and API key validity."""
        try:
            log_info("check_uspto_api_status_tool_called")

            client = _ensure_uspto_client()

            if not client.api_key:
                return {
                    "ready": False,
                    "api_key_configured": False,
                    "message": "No USPTO API key found. Set USPTO_API_KEY environment variable.",
                    "setup_url": "https://data.uspto.gov/myodp",
                }

            # Test API connection
            is_working = client.check_api_status()

            return {
                "ready": is_working,
                "api_key_configured": True,
                "api_url": client.BASE_URL,
                "message": ("USPTO API is ready" if is_working else "USPTO API connection failed"),
            }

        except Exception as e:
            log_error("check_uspto_api_status_failed", exc_info=True)
            return {
                "ready": False,
                "error": str(e),
                "message": "Failed to check USPTO API status",
            }
