#!/usr/bin/env python3
"""EPO Open Patent Services (OPS) API client for patent search and retrieval.

Provides access to the EPO OPS v3.2 REST API for searching and retrieving
European patent data including bibliographic information, full-text claims,
descriptions, and patent family information.

Authentication uses OAuth2 client credentials flow.
Requires EPO_OPS_KEY and EPO_OPS_SECRET environment variables.

Register for API access at: https://developers.epo.org/
"""

import base64
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    import xmltodict

    XMLTODICT_AVAILABLE = True
except ImportError:
    XMLTODICT_AVAILABLE = False

try:
    from logging_config import get_logger
    from monitoring import track_performance

    logger = get_logger()
except ImportError:
    logger = None

    def track_performance(operation_name: str):
        """Fallback decorator when monitoring is not available"""

        def decorator(func):
            return func

        return decorator


@dataclass
class EPOPatentResult:
    """Represents a patent result from EPO OPS API"""

    publication_number: str
    title: Optional[str]
    abstract: Optional[str]
    applicants: list[str]
    inventors: list[str]
    publication_date: Optional[str]
    filing_date: Optional[str]
    ipc_codes: list[str]
    cpc_codes: list[str]
    family_id: Optional[str]
    kind_code: Optional[str]
    country: Optional[str]
    raw_data: dict[str, Any] = field(default_factory=dict)


class EPOAPIError(Exception):
    """Base exception for EPO OPS API errors"""

    pass


class EPOAuthError(EPOAPIError):
    """Authentication error (invalid or missing credentials)"""

    pass


class EPORateLimitError(EPOAPIError):
    """Rate limit exceeded error"""

    pass


class EPOClient:
    """Client for EPO Open Patent Services (OPS) API v3.2

    The OPS API provides access to European patent data including published
    applications, granted patents, patent families, and full-text content.

    Requires EPO_OPS_KEY and EPO_OPS_SECRET from https://developers.epo.org/

    Features:
        - OAuth2 authentication with automatic token refresh
        - XML response parsing via xmltodict
        - Rate limiting (0.5s between requests)
        - Retry logic for transient failures
        - CQL (Common Query Language) search syntax
    """

    BASE_URL = "https://ops.epo.org/3.2/rest-services"
    AUTH_URL = "https://ops.epo.org/3.2/auth/accesstoken"
    DEFAULT_TIMEOUT = 30
    REQUEST_DELAY = 0.5  # seconds between requests to respect rate limits
    TOKEN_REFRESH_BUFFER = 30  # seconds before expiry to refresh token

    def __init__(self, key: Optional[str] = None, secret: Optional[str] = None):
        """Initialize EPO OPS API client.

        Args:
            key: EPO OPS consumer key. Falls back to EPO_OPS_KEY env var.
            secret: EPO OPS consumer secret. Falls back to EPO_OPS_SECRET env var.
        """
        self.key = key or os.getenv("EPO_OPS_KEY")
        self.secret = secret or os.getenv("EPO_OPS_SECRET")
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0
        self._last_request_time: float = 0

        if not self.key or not self.secret:
            warning_msg = (
                "WARNING: EPO OPS credentials not configured. "
                "Set EPO_OPS_KEY and EPO_OPS_SECRET environment variables."
            )
            if logger:
                logger.warning(
                    "epo_api_credentials_missing",
                    extra={"setup_url": "https://developers.epo.org/"},
                )
            else:
                print(warning_msg, file=sys.stderr)
                print(
                    "Register for API access at: https://developers.epo.org/",
                    file=sys.stderr,
                )

        if not XMLTODICT_AVAILABLE:
            warning_msg = (
                "WARNING: xmltodict not installed. EPO API responses cannot be parsed. "
                "Install with: pip install xmltodict"
            )
            if logger:
                logger.warning("epo_api_xmltodict_missing")
            else:
                print(warning_msg, file=sys.stderr)

        # Configure session with retries for transient errors
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        if self.key and self.secret and logger:
            logger.info(
                "epo_client_initialized",
                extra={"credentials_configured": True},
            )

    def _authenticate(self) -> None:
        """Get or refresh OAuth2 access token.

        Sends a POST request to the EPO auth endpoint with base64-encoded
        client credentials. Tokens typically last ~20 minutes.

        Raises:
            EPOAuthError: If authentication fails.
        """
        if not self.key or not self.secret:
            raise EPOAuthError(
                "EPO OPS credentials not configured.\n"
                "1. Register at: https://developers.epo.org/\n"
                "2. Create an application to get consumer key and secret\n"
                "3. Set environment variables:\n"
                "   EPO_OPS_KEY=your_consumer_key\n"
                "   EPO_OPS_SECRET=your_consumer_secret"
            )

        # Base64 encode key:secret
        credentials = f"{self.key}:{self.secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = "grant_type=client_credentials"

        if logger:
            logger.debug("epo_api_authenticating")

        try:
            response = self.session.post(
                self.AUTH_URL,
                headers=headers,
                data=data,
                timeout=self.DEFAULT_TIMEOUT,
            )

            if response.status_code == 401:
                if logger:
                    logger.error(
                        "epo_api_auth_failed",
                        extra={"status_code": 401},
                    )
                raise EPOAuthError(
                    "EPO OPS authentication failed (401 Unauthorized).\n"
                    "Your consumer key or secret is invalid.\n"
                    "1. Verify credentials at: https://developers.epo.org/\n"
                    "2. Ensure your application is active\n"
                    "3. Check EPO_OPS_KEY and EPO_OPS_SECRET values"
                )

            response.raise_for_status()

            token_data = response.json()
            self._access_token = token_data["access_token"]
            expires_in = int(token_data.get("expires_in", 1200))
            self._token_expires_at = time.time() + expires_in

            if logger:
                logger.info(
                    "epo_api_authenticated",
                    extra={"expires_in_seconds": expires_in},
                )

        except requests.exceptions.ConnectionError as e:
            if logger:
                logger.error("epo_api_auth_connection_error", extra={"error": str(e)})
            raise EPOAuthError(
                f"Cannot connect to EPO OPS authentication server: {e}\n"
                "Check your internet connection and firewall settings."
            )
        except EPOAuthError:
            raise
        except requests.exceptions.RequestException as e:
            if logger:
                logger.error("epo_api_auth_request_error", extra={"error": str(e)})
            raise EPOAuthError(f"EPO OPS authentication request failed: {e}")

    def _ensure_token(self) -> None:
        """Ensure we have a valid access token, refreshing if necessary."""
        if (
            self._access_token is None
            or time.time() >= self._token_expires_at - self.TOKEN_REFRESH_BUFFER
        ):
            self._authenticate()

    def _rate_limit(self) -> None:
        """Enforce minimum delay between API requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.REQUEST_DELAY:
            time.sleep(self.REQUEST_DELAY - elapsed)
        self._last_request_time = time.time()

    def _request(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        accept: str = "application/xml",
    ) -> dict[str, Any]:
        """Make authenticated request to OPS API.

        Handles token refresh, rate limiting, and XML response parsing.

        Args:
            endpoint: API endpoint path (appended to BASE_URL).
            params: Optional query parameters.
            accept: Accept header value (default: application/xml).

        Returns:
            Parsed response as dictionary.

        Raises:
            EPOAPIError: If the request fails.
            EPORateLimitError: If rate limit is exceeded.
            EPOAuthError: If authentication fails.
        """
        if not XMLTODICT_AVAILABLE:
            raise EPOAPIError(
                "xmltodict is required for EPO API. Install with: pip install xmltodict"
            )

        self._ensure_token()
        self._rate_limit()

        url = f"{self.BASE_URL}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": accept,
        }

        if logger:
            logger.debug(
                "epo_api_request",
                extra={
                    "endpoint": endpoint,
                    "params": params,
                    "timeout": self.DEFAULT_TIMEOUT,
                },
            )

        start_time = time.perf_counter()
        try:
            response = self.session.get(
                url,
                headers=headers,
                params=params,
                timeout=self.DEFAULT_TIMEOUT,
            )
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Handle rate limiting (EPO returns 403 for throttling)
            if response.status_code == 403:
                retry_after = response.headers.get("Retry-After", "60")
                if logger:
                    logger.warning(
                        "epo_api_rate_limited",
                        extra={
                            "status_code": 403,
                            "retry_after": retry_after,
                            "duration_ms": round(duration_ms, 2),
                        },
                    )
                raise EPORateLimitError(
                    f"EPO OPS rate limit exceeded. Retry after {retry_after} seconds.\n"
                    "The OPS API has usage quotas:\n"
                    "- Default: ~200 requests per minute\n"
                    "- Reduce request frequency or wait before retrying"
                )

            # Handle authentication errors (token may have expired)
            if response.status_code == 400 and "invalid_access_token" in response.text.lower():
                if logger:
                    logger.info("epo_api_token_expired_refreshing")
                self._access_token = None
                self._authenticate()
                # Retry the request once with new token
                headers["Authorization"] = f"Bearer {self._access_token}"
                response = self.session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=self.DEFAULT_TIMEOUT,
                )
                duration_ms = (time.perf_counter() - start_time) * 1000

            if response.status_code == 404:
                if logger:
                    logger.info(
                        "epo_api_not_found",
                        extra={
                            "endpoint": endpoint,
                            "duration_ms": round(duration_ms, 2),
                        },
                    )
                return {"error": "not_found", "message": f"Resource not found: {endpoint}"}

            if response.status_code == 500:
                if logger:
                    logger.error(
                        "epo_api_server_error",
                        extra={
                            "status_code": 500,
                            "duration_ms": round(duration_ms, 2),
                        },
                    )
                raise EPOAPIError(
                    "EPO OPS server error (500).\n"
                    "This is a temporary issue on EPO's end.\n"
                    "Try:\n"
                    "1. Wait a few minutes and retry\n"
                    "2. Simplify your query if problem persists\n"
                    "3. Check EPO OPS status at: https://status.epo.org/"
                )

            if response.status_code == 503:
                if logger:
                    logger.error(
                        "epo_api_unavailable",
                        extra={
                            "status_code": 503,
                            "duration_ms": round(duration_ms, 2),
                        },
                    )
                raise EPOAPIError(
                    "EPO OPS temporarily unavailable (503).\n"
                    "The service may be under maintenance.\n"
                    "Try again later."
                )

            # Raise for other HTTP errors
            response.raise_for_status()

            # Parse XML response
            try:
                parsed = xmltodict.parse(response.text)
            except Exception as e:
                if logger:
                    logger.error(
                        "epo_api_xml_parse_error",
                        extra={
                            "error": str(e),
                            "response_length": len(response.text),
                            "duration_ms": round(duration_ms, 2),
                        },
                    )
                raise EPOAPIError(
                    f"Failed to parse EPO OPS XML response: {e}\n"
                    f"Response text (first 500 chars): {response.text[:500]}"
                )

            if logger:
                logger.info(
                    "epo_api_response_success",
                    extra={
                        "status_code": response.status_code,
                        "duration_ms": round(duration_ms, 2),
                        "endpoint": endpoint,
                    },
                )

            return parsed

        except requests.exceptions.Timeout:
            if logger:
                logger.error(
                    "epo_api_timeout",
                    extra={
                        "timeout_seconds": self.DEFAULT_TIMEOUT,
                        "endpoint": endpoint,
                    },
                )
            raise EPOAPIError(
                f"Request timed out after {self.DEFAULT_TIMEOUT}s.\n"
                "EPO OPS did not respond in time.\n"
                "Try:\n"
                "1. Check your internet connection\n"
                "2. Retry the request\n"
                "3. Simplify the query if timeout persists"
            )
        except requests.exceptions.ConnectionError as e:
            if logger:
                logger.error(
                    "epo_api_connection_error",
                    extra={"error": str(e), "endpoint": endpoint},
                )
            raise EPOAPIError(
                f"Connection failed to EPO OPS: {e}\n"
                "Try:\n"
                "1. Check your internet connection\n"
                "2. Verify firewall/proxy settings\n"
                "3. Test connection: curl -I https://ops.epo.org"
            )
        except (EPOAuthError, EPOAPIError, EPORateLimitError):
            raise
        except requests.exceptions.RequestException as e:
            if logger:
                logger.error(
                    "epo_api_request_error",
                    extra={"error": str(e), "url": url},
                )
            raise EPOAPIError(f"EPO OPS request failed: {e}\nURL: {url}")

    @track_performance("epo_api_check_availability")
    def check_availability(self) -> dict[str, Any]:
        """Check if EPO OPS API is configured and available.

        Returns:
            Dictionary with status information:
            - available: bool
            - credentials_configured: bool
            - xmltodict_available: bool
            - error: Optional error message
            - message: Status message
            - response_time_ms: API response time in milliseconds (if available)
        """
        if logger:
            logger.info("epo_api_availability_check_started")

        status: dict[str, Any] = {
            "available": False,
            "credentials_configured": bool(self.key and self.secret),
            "xmltodict_available": XMLTODICT_AVAILABLE,
            "error": None,
            "message": "",
            "response_time_ms": None,
        }

        if not XMLTODICT_AVAILABLE:
            status["message"] = "xmltodict not installed"
            status["error"] = (
                "xmltodict is required for EPO API. "
                "Install with: pip install xmltodict"
            )
            return status

        if not self.key or not self.secret:
            status["message"] = "EPO OPS credentials not configured"
            status["error"] = (
                "Set EPO_OPS_KEY and EPO_OPS_SECRET environment variables.\n"
                "Register at: https://developers.epo.org/"
            )
            if logger:
                logger.warning("epo_api_availability_check_no_credentials")
            return status

        try:
            start_time = time.time()
            # Try authenticating to verify credentials
            self._authenticate()
            elapsed_ms = int((time.time() - start_time) * 1000)

            status["available"] = True
            status["response_time_ms"] = elapsed_ms
            status["message"] = (
                f"EPO OPS API operational (auth response: {elapsed_ms}ms)"
            )

            if logger:
                logger.info(
                    "epo_api_availability_check_success",
                    extra={
                        "response_time_ms": elapsed_ms,
                        "available": True,
                    },
                )

        except EPOAuthError as e:
            status["message"] = "Authentication failed"
            status["error"] = str(e)
            if logger:
                logger.error(
                    "epo_api_availability_check_auth_failed",
                    extra={"error": str(e)},
                )
        except EPOAPIError as e:
            status["message"] = "API request failed"
            status["error"] = str(e)
            if logger:
                logger.error(
                    "epo_api_availability_check_failed",
                    extra={"error": str(e)},
                )
        except Exception as e:
            status["message"] = "Unexpected error"
            status["error"] = f"Unexpected error checking EPO OPS API: {e}"
            if logger:
                logger.error(
                    "epo_api_availability_check_unexpected_error",
                    extra={"error": str(e)},
                    exc_info=True,
                )

        return status

    @track_performance("epo_api_search_published")
    def search_published(
        self,
        query: str,
        range_begin: int = 1,
        range_end: int = 25,
    ) -> list[dict[str, Any]]:
        """Search published EP patents using CQL query syntax.

        Uses the OPS published-data search endpoint with biblio retrieval.

        CQL query examples:
            - ta="neural network"        (title + abstract)
            - ti="machine learning"       (title only)
            - in="Smith"                  (inventor name)
            - pa="Google"                 (applicant/assignee)
            - pd=20240101                 (publication date)
            - cl="semiconductor"          (claims text)
            - ic="G06F"                   (IPC code)

        Args:
            query: CQL query string. For simple keyword searches, wraps
                   automatically in ta="query" (title+abstract search).
            range_begin: First result position (1-based, default 1).
            range_end: Last result position (default 25, max 100).

        Returns:
            List of patent result dictionaries with bibliographic data.
        """
        if logger:
            logger.info(
                "epo_search_published_started",
                extra={
                    "query_length": len(query),
                    "range": f"{range_begin}-{range_end}",
                },
            )

        # If the query does not contain CQL operators, wrap in ta= for title+abstract
        cql_operators = ["=", " and ", " or ", " not ", "ti=", "ta=", "in=", "pa=",
                         "pd=", "cl=", "ic=", "cc=", "ct=", "ab="]
        is_cql = any(op in query.lower() for op in cql_operators)
        search_query = f'ta="{query}"' if not is_cql else query

        # Clamp range to API limits
        range_begin = max(1, range_begin)
        range_end = min(range_end, 100)
        if range_end < range_begin:
            range_end = range_begin

        params = {
            "q": search_query,
            "Range": f"{range_begin}-{range_end}",
        }

        response = self._request("published-data/search/biblio", params=params)

        # Handle error responses
        if isinstance(response, dict) and response.get("error") == "not_found":
            if logger:
                logger.info("epo_search_published_no_results", extra={"query": query})
            return []

        # Parse search results from the XML structure
        results = self._parse_search_results(response)

        if logger:
            logger.info(
                "epo_search_published_completed",
                extra={"result_count": len(results), "query": query[:100]},
            )

        return results

    @track_performance("epo_api_get_patent")
    def get_patent(self, patent_number: str) -> dict[str, Any]:
        """Get bibliographic data for a patent by publication number.

        Args:
            patent_number: Patent number in epodoc format (e.g., "EP1234567",
                          "EP1234567A1", "US10123456"). Country prefix is required.

        Returns:
            Dictionary with bibliographic data, or error dict if not found.
        """
        if logger:
            logger.info(
                "epo_get_patent_started",
                extra={"patent_number": patent_number},
            )

        clean_number = self._normalize_patent_number(patent_number)
        endpoint = f"published-data/publication/epodoc/{clean_number}/biblio"

        response = self._request(endpoint)

        if isinstance(response, dict) and response.get("error") == "not_found":
            return {
                "error": f"Patent {patent_number} not found in EPO OPS",
                "patent_number": patent_number,
            }

        result = self._parse_biblio_response(response)
        result["patent_number"] = patent_number

        if logger:
            logger.info(
                "epo_get_patent_completed",
                extra={
                    "patent_number": patent_number,
                    "title": result.get("title", "")[:50],
                },
            )

        return result

    @track_performance("epo_api_get_claims")
    def get_claims(self, patent_number: str) -> str:
        """Get full claims text for a patent.

        This is particularly valuable for EP patents since BigQuery does not
        contain full-text claims for non-US patents.

        Args:
            patent_number: Patent number in epodoc format (e.g., "EP1234567").

        Returns:
            Claims text as a string, or error message if not found.
        """
        if logger:
            logger.info(
                "epo_get_claims_started",
                extra={"patent_number": patent_number},
            )

        clean_number = self._normalize_patent_number(patent_number)
        endpoint = f"published-data/publication/epodoc/{clean_number}/claims"

        response = self._request(endpoint)

        if isinstance(response, dict) and response.get("error") == "not_found":
            return f"Claims not found for patent {patent_number}"

        claims_text = self._extract_fulltext(response, "claims")

        if logger:
            logger.info(
                "epo_get_claims_completed",
                extra={
                    "patent_number": patent_number,
                    "claims_length": len(claims_text),
                },
            )

        return claims_text

    @track_performance("epo_api_get_description")
    def get_description(self, patent_number: str) -> str:
        """Get full description text for a patent.

        Args:
            patent_number: Patent number in epodoc format (e.g., "EP1234567").

        Returns:
            Description text as a string, or error message if not found.
        """
        if logger:
            logger.info(
                "epo_get_description_started",
                extra={"patent_number": patent_number},
            )

        clean_number = self._normalize_patent_number(patent_number)
        endpoint = f"published-data/publication/epodoc/{clean_number}/description"

        response = self._request(endpoint)

        if isinstance(response, dict) and response.get("error") == "not_found":
            return f"Description not found for patent {patent_number}"

        description_text = self._extract_fulltext(response, "description")

        if logger:
            logger.info(
                "epo_get_description_completed",
                extra={
                    "patent_number": patent_number,
                    "description_length": len(description_text),
                },
            )

        return description_text

    @track_performance("epo_api_get_patent_family")
    def get_patent_family(self, patent_number: str) -> list[dict[str, Any]]:
        """Get patent family members across jurisdictions.

        Patent families link related applications filed in different countries
        for the same invention. Useful for:
        - Finding US equivalents of EP patents (for full claims text)
        - Mapping worldwide patent coverage
        - Cross-referencing prior art

        Args:
            patent_number: Patent number in epodoc format (e.g., "EP1234567").

        Returns:
            List of family member dictionaries with publication info.
        """
        if logger:
            logger.info(
                "epo_get_patent_family_started",
                extra={"patent_number": patent_number},
            )

        clean_number = self._normalize_patent_number(patent_number)
        endpoint = f"family/publication/epodoc/{clean_number}/biblio"

        response = self._request(endpoint)

        if isinstance(response, dict) and response.get("error") == "not_found":
            return [{"error": f"Patent family not found for {patent_number}"}]

        family_members = self._parse_family_response(response)

        if logger:
            jurisdictions = list({m.get("country", "?") for m in family_members})
            logger.info(
                "epo_get_patent_family_completed",
                extra={
                    "patent_number": patent_number,
                    "family_size": len(family_members),
                    "jurisdictions": jurisdictions,
                },
            )

        return family_members

    # -------------------------------------------------------------------------
    # Internal parsing helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _normalize_patent_number(patent_number: str) -> str:
        """Normalize patent number for OPS API epodoc format.

        Strips whitespace and common separators. The OPS epodoc format
        expects something like "EP1234567" or "EP1234567A1".

        Args:
            patent_number: Raw patent number string.

        Returns:
            Cleaned patent number string.
        """
        cleaned = patent_number.strip().replace(" ", "").replace("-", "").replace(".", "")
        return cleaned

    def _parse_search_results(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        """Parse OPS search response XML into a list of patent result dicts.

        Args:
            response: Parsed XML response from search endpoint.

        Returns:
            List of patent result dictionaries.
        """
        results = []

        try:
            # Navigate the XML structure
            # ops:world-patent-data -> ops:biblio-search -> ops:search-result -> exchange-documents
            world_data = response.get("ops:world-patent-data", response)
            search_data = world_data.get("ops:biblio-search", {})
            search_result = search_data.get("ops:search-result", {})

            exchange_docs = search_result.get("exchange-documents", {})
            if not exchange_docs:
                exchange_docs = search_result.get("ops:exchange-documents", {})

            doc_list = exchange_docs.get("exchange-document", [])

            # Ensure doc_list is a list (single results come as dict)
            if isinstance(doc_list, dict):
                doc_list = [doc_list]

            for doc in doc_list:
                parsed = self._parse_single_document(doc)
                if parsed:
                    results.append(parsed)

        except Exception as e:
            if logger:
                logger.error(
                    "epo_parse_search_results_error",
                    extra={"error": str(e)},
                    exc_info=True,
                )

        return results

    def _parse_single_document(self, doc: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Parse a single exchange-document element into a result dict.

        Args:
            doc: Single document element from XML response.

        Returns:
            Parsed patent result dictionary, or None on parse failure.
        """
        try:
            result: dict[str, Any] = {}

            # Extract document ID attributes
            doc_id = doc.get("@country", "") + doc.get("@doc-number", "")
            result["publication_number"] = doc_id
            result["country"] = doc.get("@country", "")
            result["doc_number"] = doc.get("@doc-number", "")
            result["kind_code"] = doc.get("@kind", "")
            result["family_id"] = doc.get("@family-id", "")

            # Navigate to bibliographic-data
            biblio = doc.get("bibliographic-data", {})
            if not biblio:
                return result

            # Title
            result["title"] = self._extract_title(biblio)

            # Abstract
            result["abstract"] = self._extract_abstract(doc)

            # Dates
            result["publication_date"] = self._extract_date(
                biblio, "publication-reference"
            )
            result["filing_date"] = self._extract_date(
                biblio, "application-reference"
            )

            # Inventors
            result["inventors"] = self._extract_parties(biblio, "inventors", "inventor")

            # Applicants
            result["applicants"] = self._extract_parties(
                biblio, "applicants", "applicant"
            )

            # Classifications
            result["ipc_codes"] = self._extract_classifications(biblio, "classifications-ipcr")
            result["cpc_codes"] = self._extract_classifications(biblio, "patent-classifications")

            return result

        except Exception as e:
            if logger:
                logger.debug(
                    "epo_parse_single_document_error",
                    extra={"error": str(e)},
                )
            return None

    @staticmethod
    def _extract_title(biblio: dict[str, Any]) -> Optional[str]:
        """Extract title from bibliographic data, preferring English."""
        try:
            invention_title = biblio.get("invention-title", {})
            if isinstance(invention_title, list):
                # Multiple languages - prefer English
                for title_entry in invention_title:
                    if isinstance(title_entry, dict):
                        lang = title_entry.get("@lang", "")
                        if lang == "en":
                            return title_entry.get("#text", "")
                # Fall back to first title
                if invention_title:
                    first = invention_title[0]
                    if isinstance(first, dict):
                        return first.get("#text", "")
                    return str(first)
            elif isinstance(invention_title, dict):
                return invention_title.get("#text", "")
            elif isinstance(invention_title, str):
                return invention_title
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_abstract(doc: dict[str, Any]) -> Optional[str]:
        """Extract abstract text, preferring English."""
        try:
            abstract_data = doc.get("abstract", {})
            if isinstance(abstract_data, list):
                # Multiple languages - prefer English
                for abs_entry in abstract_data:
                    if isinstance(abs_entry, dict):
                        lang = abs_entry.get("@lang", "")
                        if lang == "en":
                            p_data = abs_entry.get("p", "")
                            if isinstance(p_data, dict):
                                return p_data.get("#text", "")
                            return str(p_data)
                # Fall back to first abstract
                if abstract_data:
                    first = abstract_data[0]
                    if isinstance(first, dict):
                        p_data = first.get("p", "")
                        if isinstance(p_data, dict):
                            return p_data.get("#text", "")
                        return str(p_data)
            elif isinstance(abstract_data, dict):
                p_data = abstract_data.get("p", "")
                if isinstance(p_data, dict):
                    return p_data.get("#text", "")
                elif isinstance(p_data, list):
                    # Multiple paragraphs
                    parts = []
                    for p in p_data:
                        if isinstance(p, dict):
                            parts.append(p.get("#text", ""))
                        else:
                            parts.append(str(p))
                    return " ".join(parts)
                return str(p_data) if p_data else None
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_date(
        biblio: dict[str, Any], reference_type: str
    ) -> Optional[str]:
        """Extract date from a reference element."""
        try:
            ref = biblio.get(reference_type, {})
            if isinstance(ref, list):
                ref = ref[0] if ref else {}
            doc_id = ref.get("document-id", {})
            if isinstance(doc_id, list):
                for d in doc_id:
                    date = d.get("date", {})
                    if date:
                        date_val = date.get("$", date) if isinstance(date, dict) else date
                        return str(date_val)
            elif isinstance(doc_id, dict):
                date = doc_id.get("date", {})
                if date:
                    date_val = date.get("$", date) if isinstance(date, dict) else date
                    return str(date_val)
        except Exception:
            pass
        return None

    @staticmethod
    def _extract_parties(
        biblio: dict[str, Any], group_key: str, item_key: str
    ) -> list[str]:
        """Extract party names (inventors or applicants) from biblio data."""
        names = []
        try:
            parties_group = biblio.get("parties", {}).get(group_key, {})
            if not parties_group:
                return names

            party_list = parties_group.get(item_key, [])
            if isinstance(party_list, dict):
                party_list = [party_list]

            for party in party_list:
                if not isinstance(party, dict):
                    continue
                # Try epodoc format first, then other formats
                for format_key in [
                    "inventor-name",
                    "applicant-name",
                    "name",
                ]:
                    name_data = party.get(format_key, {})
                    if isinstance(name_data, dict):
                        name = name_data.get("name", {})
                        if isinstance(name, dict):
                            name = name.get("$", name.get("#text", ""))
                        if name:
                            names.append(str(name))
                            break
                    elif isinstance(name_data, str) and name_data:
                        names.append(name_data)
                        break
        except Exception:
            pass
        return names

    @staticmethod
    def _extract_classifications(
        biblio: dict[str, Any], classification_key: str
    ) -> list[str]:
        """Extract classification codes from biblio data."""
        codes = []
        try:
            classifications = biblio.get(classification_key, {})
            if not classifications:
                return codes

            # Handle different classification structures
            if classification_key == "classifications-ipcr":
                items = classifications.get("classification-ipcr", [])
            else:
                items = classifications.get("patent-classification", [])

            if isinstance(items, dict):
                items = [items]

            for item in items:
                if not isinstance(item, dict):
                    continue
                # Try to build classification code from parts
                section = item.get("section", "")
                cls = item.get("class", "")
                subclass = item.get("subclass", "")
                main_group = item.get("main-group", "")
                subgroup = item.get("subgroup", "")

                if section and cls:
                    code = f"{section}{cls}{subclass}"
                    if main_group:
                        code += f"{main_group}"
                        if subgroup:
                            code += f"/{subgroup}"
                    codes.append(code)
                elif item.get("text", ""):
                    codes.append(item["text"])
        except Exception:
            pass
        return codes

    def _parse_biblio_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Parse a biblio retrieval response for a single patent.

        Args:
            response: Parsed XML response from biblio endpoint.

        Returns:
            Patent details dictionary.
        """
        result: dict[str, Any] = {}

        try:
            world_data = response.get("ops:world-patent-data", response)
            exchange_docs = world_data.get("exchange-documents", {})
            if not exchange_docs:
                exchange_docs = world_data.get("ops:exchange-documents", {})

            doc = exchange_docs.get("exchange-document", {})
            if isinstance(doc, list):
                doc = doc[0] if doc else {}

            parsed = self._parse_single_document(doc)
            if parsed:
                result = parsed

        except Exception as e:
            if logger:
                logger.error(
                    "epo_parse_biblio_response_error",
                    extra={"error": str(e)},
                    exc_info=True,
                )
            result["parse_error"] = str(e)

        return result

    def _extract_fulltext(
        self, response: dict[str, Any], text_type: str
    ) -> str:
        """Extract full text (claims or description) from OPS response.

        Args:
            response: Parsed XML response from claims/description endpoint.
            text_type: Either "claims" or "description".

        Returns:
            Extracted text as a single string.
        """
        try:
            world_data = response.get("ops:world-patent-data", response)
            ftxt = world_data.get("ftxt:fulltext-documents", {})
            if not ftxt:
                ftxt = world_data.get("ops:fulltext-documents", world_data)

            doc = ftxt.get("ftxt:fulltext-document", {})
            if not doc:
                doc = ftxt.get("fulltext-document", ftxt)

            if isinstance(doc, list):
                # Multiple languages - prefer English
                english_doc = None
                for d in doc:
                    if isinstance(d, dict) and d.get("@lang", "").lower() == "en":
                        english_doc = d
                        break
                doc = english_doc if english_doc else (doc[0] if doc else {})

            if not isinstance(doc, dict):
                return f"Could not parse {text_type} text from response"

            # Extract text from the document body
            body = doc.get(text_type, doc)
            if isinstance(body, dict):
                return self._flatten_text_elements(body)
            elif isinstance(body, str):
                return body
            else:
                return f"Unexpected {text_type} format in response"

        except Exception as e:
            if logger:
                logger.error(
                    "epo_extract_fulltext_error",
                    extra={"text_type": text_type, "error": str(e)},
                )
            return f"Error extracting {text_type}: {e}"

    @staticmethod
    def _flatten_text_elements(element: dict[str, Any]) -> str:
        """Recursively flatten nested XML text elements into plain text.

        Handles <p>, <claim-text>, and other nested elements common in
        EPO OPS full-text responses.

        Args:
            element: Parsed XML element dictionary.

        Returns:
            Flattened text string.
        """
        parts = []

        def _extract(obj: Any, depth: int = 0) -> None:
            if isinstance(obj, str):
                parts.append(obj)
            elif isinstance(obj, dict):
                # Check for direct text content
                if "#text" in obj:
                    parts.append(obj["#text"])
                # Recurse into known text-bearing children
                for key in ["p", "claim-text", "claim", "heading",
                            "patcit", "nplcit", "b", "i", "u", "sup", "sub"]:
                    child = obj.get(key)
                    if child is not None:
                        _extract(child, depth + 1)
                # Add newlines between major sections
                if depth <= 1:
                    parts.append("\n")
            elif isinstance(obj, list):
                for item in obj:
                    _extract(item, depth)
                    if depth <= 1:
                        parts.append("\n")

        _extract(element)

        # Clean up extra whitespace
        text = " ".join(parts)
        text = "\n".join(line.strip() for line in text.split("\n") if line.strip())
        return text

    def _parse_family_response(
        self, response: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Parse patent family response into list of family member dicts.

        Args:
            response: Parsed XML response from family endpoint.

        Returns:
            List of family member dictionaries.
        """
        members = []

        try:
            world_data = response.get("ops:world-patent-data", response)
            family_data = world_data.get("ops:patent-family", {})

            family_members = family_data.get("ops:family-member", [])
            if isinstance(family_members, dict):
                family_members = [family_members]

            for member in family_members:
                if not isinstance(member, dict):
                    continue

                member_info: dict[str, Any] = {
                    "family_id": member.get("@family-id", ""),
                }

                # Extract publication reference
                pub_ref = member.get("publication-reference", {})
                doc_id = pub_ref.get("document-id", {})
                if isinstance(doc_id, list):
                    # Use epodoc format if available
                    for d in doc_id:
                        if isinstance(d, dict) and d.get("@document-id-type") == "epodoc":
                            doc_id = d
                            break
                    else:
                        doc_id = doc_id[0] if doc_id else {}

                if isinstance(doc_id, dict):
                    country = doc_id.get("country", {})
                    if isinstance(country, dict):
                        country = country.get("$", country.get("#text", ""))
                    doc_number = doc_id.get("doc-number", {})
                    if isinstance(doc_number, dict):
                        doc_number = doc_number.get("$", doc_number.get("#text", ""))
                    kind = doc_id.get("kind", {})
                    if isinstance(kind, dict):
                        kind = kind.get("$", kind.get("#text", ""))
                    date = doc_id.get("date", {})
                    if isinstance(date, dict):
                        date = date.get("$", date.get("#text", ""))

                    member_info["country"] = str(country) if country else ""
                    member_info["doc_number"] = str(doc_number) if doc_number else ""
                    member_info["kind_code"] = str(kind) if kind else ""
                    member_info["publication_date"] = str(date) if date else ""
                    member_info["publication_number"] = (
                        f"{member_info['country']}{member_info['doc_number']}"
                    )

                # Extract title from biblio if present
                biblio = member.get("bibliographic-data", {})
                if biblio:
                    member_info["title"] = self._extract_title(biblio)
                else:
                    member_info["title"] = None

                members.append(member_info)

        except Exception as e:
            if logger:
                logger.error(
                    "epo_parse_family_response_error",
                    extra={"error": str(e)},
                    exc_info=True,
                )

        return members


def format_epo_result(result: dict[str, Any], verbose: bool = False) -> str:
    """Format an EPO patent result dictionary for display.

    Args:
        result: Patent result dictionary from EPOClient methods.
        verbose: If True, include additional details.

    Returns:
        Formatted string representation.
    """
    lines = []

    if result.get("title"):
        lines.append(f"Title: {result['title']}")

    pub_num = result.get("publication_number", "")
    if pub_num:
        kind = result.get("kind_code", "")
        display_num = f"{pub_num}{kind}" if kind else pub_num
        lines.append(f"Publication Number: {display_num}")

    if result.get("publication_date"):
        lines.append(f"Publication Date: {result['publication_date']}")

    if result.get("filing_date"):
        lines.append(f"Filing Date: {result['filing_date']}")

    if result.get("country"):
        lines.append(f"Country: {result['country']}")

    if result.get("family_id"):
        lines.append(f"Family ID: {result['family_id']}")

    inventors = result.get("inventors", [])
    if inventors:
        if len(inventors) == 1:
            lines.append(f"Inventor: {inventors[0]}")
        else:
            lines.append(f"Inventors: {', '.join(inventors[:3])}")
            if len(inventors) > 3:
                lines.append(f"  ... and {len(inventors) - 3} more")

    applicants = result.get("applicants", [])
    if applicants:
        if len(applicants) == 1:
            lines.append(f"Applicant: {applicants[0]}")
        else:
            lines.append(f"Applicants: {', '.join(applicants[:3])}")
            if len(applicants) > 3:
                lines.append(f"  ... and {len(applicants) - 3} more")

    if verbose:
        ipc = result.get("ipc_codes", [])
        if ipc:
            lines.append(f"IPC: {', '.join(ipc[:5])}")
        cpc = result.get("cpc_codes", [])
        if cpc:
            lines.append(f"CPC: {', '.join(cpc[:5])}")

    abstract = result.get("abstract")
    if abstract and verbose:
        lines.append(f"Abstract: {abstract[:300]}...")

    return "\n".join(lines)


if __name__ == "__main__":
    """Test EPO OPS API client"""

    print("=" * 60)
    print("EPO OPS API CLIENT TEST")
    print("=" * 60)

    # Check xmltodict availability
    if not XMLTODICT_AVAILABLE:
        print("\nERROR: xmltodict not installed. Install with: pip install xmltodict")
        sys.exit(1)

    # Initialize client
    client = EPOClient()

    # Check API availability
    print("\nChecking API availability...")
    status = client.check_availability()

    if not status["available"]:
        print(f"\nAPI not available: {status.get('error', 'Unknown error')}")
        print("\nTo use the EPO OPS API:")
        print("1. Register at: https://developers.epo.org/")
        print("2. Create an application")
        print("3. Set environment variables:")
        print("   EPO_OPS_KEY=your_consumer_key")
        print("   EPO_OPS_SECRET=your_consumer_secret")
        sys.exit(1)

    print(f"[OK] {status['message']}")

    # Test search
    print("\n" + "=" * 60)
    print("TEST: Search for 'machine learning' patents")
    print("=" * 60)

    try:
        results = client.search_published("machine learning", range_end=5)
        print(f"\nFound {len(results)} patents:")
        for i, patent in enumerate(results, 1):
            print(f"\n--- Patent {i} ---")
            print(format_epo_result(patent, verbose=True))

    except EPOAPIError as e:
        print(f"Search failed: {e}")
