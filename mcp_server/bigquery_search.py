#!/usr/bin/env python3
"""
BigQuery Patent Search
Fast, cloud-based patent search using Google's Patents Public Data
"""

import os
import platform
import sys
from pathlib import Path
from typing import Any, Optional

try:
    from google.api_core.exceptions import NotFound
    from google.cloud import bigquery
    from google.cloud.exceptions import GoogleCloudError

    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False
    bigquery = None
    GoogleCloudError = Exception
    NotFound = Exception

# Import logging and monitoring with fallback
try:
    from logging_config import get_logger
    from monitoring import OperationTimer, track_performance

    logger = get_logger()
    LOGGING_AVAILABLE = True
except ImportError:
    logger = None
    track_performance = None
    OperationTimer = None
    LOGGING_AVAILABLE = False


def _get_gcloud_credentials_path():
    """
    Get the correct gcloud application default credentials path for the current OS

    Returns:
        Path: Platform-specific credentials path
    """
    if platform.system() == "Windows":
        # Windows: %APPDATA%\gcloud\application_default_credentials.json
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "gcloud" / "application_default_credentials.json"
        else:
            return (
                Path.home()
                / "AppData"
                / "Roaming"
                / "gcloud"
                / "application_default_credentials.json"
            )
    else:
        # Linux/macOS: $HOME/.config/gcloud/application_default_credentials.json
        return Path.home() / ".config" / "gcloud" / "application_default_credentials.json"


class BigQueryPatentSearch:
    """
    Search patents using Google BigQuery Patents Public Data

    This provides access to 100M+ worldwide patents with bibliographic data
    (title, abstract, CPC, IPC, family_id) and full-text claims/description
    for US patents. Much faster than local indexing.
    """

    PROJECT_ID = "patents-public-data"
    DATASET_ID = "patents"
    TABLE_ID = "publications"
    FULL_TABLE_ID = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

    # Per-query bytes-billed ceiling. Defaults to 25 GiB; override via
    # PATENT_BIGQUERY_MAX_BYTES_BILLED.
    DEFAULT_MAX_BYTES_BILLED = 25 * 1024**3
    QUERY_TIMEOUT_SECONDS = 30

    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize BigQuery client

        Args:
            project_id: Optional GCP project ID for billing. If not provided,
                       will use GOOGLE_CLOUD_PROJECT env var or default credentials.
        """
        if not BIGQUERY_AVAILABLE:
            raise ImportError(
                "google-cloud-bigquery not installed. "
                "Install with: pip install google-cloud-bigquery db-dtypes"
            )

        # Determine project for billing — try multiple sources
        self.billing_project = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")

        # Try credentials file for quota_project_id
        if not self.billing_project:
            try:
                import json

                creds_path = _get_gcloud_credentials_path()
                if creds_path.exists():
                    with creds_path.open() as f:
                        creds_data = json.load(f)
                        self.billing_project = creds_data.get("quota_project_id")
            except Exception:
                pass

        # Try gcloud config for default project
        if not self.billing_project:
            try:
                import subprocess

                result = subprocess.run(
                    ["gcloud", "config", "get-value", "project"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip() and result.stdout.strip() != "(unset)":
                    self.billing_project = result.stdout.strip()
            except Exception:
                pass

        # Initialize client
        setup_msg = (
            "BigQuery requires a Google Cloud project ID for billing.\n"
            "Setup (5 minutes, no credit card needed):\n"
            "  1. Install gcloud: https://cloud.google.com/sdk/docs/install\n"
            "  2. Run: gcloud auth login\n"
            "  3. Run: gcloud auth application-default login --project YOUR_PROJECT_ID\n"
            "  4. Or set env var: GOOGLE_CLOUD_PROJECT=your-project-id\n"
            "\n"
            "Free tier: 1TB queries/month"
        )

        if not self.billing_project:
            raise ValueError(
                f"No Google Cloud project ID found.\n{setup_msg}"
            )

        try:
            self.client = bigquery.Client(project=self.billing_project)  # type: ignore[union-attr]

            if LOGGING_AVAILABLE and logger:
                logger.info(
                    "bigquery_client_initialized", extra={"billing_project": self.billing_project}
                )
        except Exception as e:
            raise ValueError(
                f"Could not initialize BigQuery client: {e}\n{setup_msg}"
            ) from e

    def check_availability(self) -> dict[str, Any]:
        """
        Check if BigQuery is available and credentials are configured

        Returns:
            Dictionary with status information
        """
        if not BIGQUERY_AVAILABLE:
            return {
                "available": False,
                "error": "google-cloud-bigquery not installed",
                "install_command": "pip install google-cloud-bigquery db-dtypes",
            }

        if not self.client:
            return {
                "available": False,
                "error": "BigQuery client not initialized",
                "message": "Set GOOGLE_CLOUD_PROJECT environment variable or configure gcloud auth",
            }

        # Verify access using table metadata (no query cost)
        try:
            table = self.client.get_table(self.FULL_TABLE_ID)
            return {
                "available": True,
                "project": self.billing_project,
                "message": "BigQuery patent search ready",
                "total_rows": table.num_rows,
            }
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
                "message": "Could not access patents public data",
            }

    def search_by_keywords(
        self,
        query: str,
        country: str = "US",
        limit: int = 20,
        offset: int = 0,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        search_fields: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """
        Search patents by keyword matching in abstract, title, or claims

        Args:
            query: Search query string
            country: Country code (US, EP, JP, CN, etc.)
            limit: Maximum number of results
            offset: Number of results to skip
            start_year: Filter by filing year >= start_year
            end_year: Filter by filing year <= end_year
            search_fields: Which fields to search in

        Returns:
            List of patent dictionaries
        """
        if search_fields is None:
            search_fields = ["abstract", "title", "claims"]

        if not self.client:
            raise RuntimeError("BigQuery client not initialized")

        # Log search start
        log_extra = {
            "query": query[:100] if query else "",
            "query_length": len(query) if query else 0,
            "country": country,
            "limit": limit,
            "offset": offset,
            "start_year": start_year,
            "end_year": end_year,
            "search_fields": search_fields,
        }

        if LOGGING_AVAILABLE and logger:
            logger.info("bigquery_search_started", extra=log_extra)

        conditions = ["country_code = @country"]
        parameters = [
            bigquery.ScalarQueryParameter("query", "STRING", f"%{query.lower()}%"),  # type: ignore[union-attr]
            bigquery.ScalarQueryParameter("country", "STRING", country),  # type: ignore[union-attr]
            bigquery.ScalarQueryParameter("limit", "INT64", limit),  # type: ignore[union-attr]
            bigquery.ScalarQueryParameter("offset", "INT64", offset),  # type: ignore[union-attr]
        ]

        # claims_localized only carries text for US publications; for EP/WO
        # full-text use epo_api.py.
        search_conditions = []
        if "abstract" in search_fields:
            search_conditions.append("LOWER(abstract_localized[SAFE_OFFSET(0)].text) LIKE @query")
        if "title" in search_fields:
            search_conditions.append("LOWER(title_localized[SAFE_OFFSET(0)].text) LIKE @query")
        if "claims" in search_fields and country == "US":
            search_conditions.append("LOWER(claims_localized[SAFE_OFFSET(0)].text) LIKE @query")

        if search_conditions:
            conditions.append(f"({' OR '.join(search_conditions)})")

        if start_year:
            conditions.append("CAST(filing_date AS INT64) >= @start_yyyymmdd")
            parameters.append(
                bigquery.ScalarQueryParameter("start_yyyymmdd", "INT64", start_year * 10000 + 101)  # type: ignore[union-attr]
            )
        if end_year:
            conditions.append("CAST(filing_date AS INT64) <= @end_yyyymmdd")
            parameters.append(
                bigquery.ScalarQueryParameter("end_yyyymmdd", "INT64", end_year * 10000 + 1231)  # type: ignore[union-attr]
            )

        where_clause = " AND ".join(conditions)

        sql = f"""
        SELECT
            publication_number,
            title_localized[SAFE_OFFSET(0)].text AS title,
            abstract_localized[SAFE_OFFSET(0)].text AS abstract,
            CAST(filing_date AS STRING) AS filing_date,
            CAST(grant_date AS STRING) AS grant_date,
            CAST(publication_date AS STRING) AS publication_date,
            application_number,
            family_id,
            country_code
        FROM `{self.FULL_TABLE_ID}`
        WHERE {where_clause}
        ORDER BY publication_date DESC, publication_number DESC
        LIMIT @limit
        OFFSET @offset
        """

        job_config = self._make_job_config(parameters)

        try:
            # Execute query with timing and timeout (30 seconds)
            if LOGGING_AVAILABLE and OperationTimer:
                with OperationTimer("bigquery_query"):
                    results = self.client.query(sql, job_config=job_config).result(timeout=30)
            else:
                results = self.client.query(sql, job_config=job_config).result(timeout=30)

            # Process results
            patents = []
            for row in results:
                patents.append(
                    {
                        "patent_number": row.publication_number,
                        "application_number": row.application_number,
                        "title": row.title or "",
                        "abstract": row.abstract or "",
                        "filing_date": self._format_date(row.filing_date),
                        "grant_date": self._format_date(row.grant_date),
                        "publication_date": self._format_date(row.publication_date),
                        "country": row.country_code,
                        "family_id": row.family_id,
                    }
                )

            # Log completion with metrics
            completion_extra = {
                **log_extra,
                "results_count": len(patents),
                "bytes_processed": (
                    results.total_bytes_processed
                    if hasattr(results, "total_bytes_processed")
                    else 0
                ),
                "bytes_billed": (
                    results.total_bytes_billed if hasattr(results, "total_bytes_billed") else 0  # type: ignore[attr-defined]
                ),
            }

            if LOGGING_AVAILABLE and logger:
                logger.info("bigquery_search_completed", extra=completion_extra)

            return patents

        except Exception as e:
            error_extra = {**log_extra, "error_type": type(e).__name__, "error_message": str(e)}

            if LOGGING_AVAILABLE and logger:
                logger.error("bigquery_search_failed", extra=error_extra, exc_info=True)
            else:
                print(f"BigQuery search error: {e}", file=sys.stderr)

            raise

    def get_patent_details(self, patent_number: str) -> Optional[dict[str, Any]]:
        """
        Get full details for a specific patent by publication number

        Args:
            patent_number: Patent publication number (e.g., "US10123456B2")

        Returns:
            Patent details dictionary or None if not found
        """
        if not self.client:
            raise RuntimeError("BigQuery client not initialized")

        # Log retrieval start
        log_extra = {"patent_number": patent_number}

        if LOGGING_AVAILABLE and logger:
            logger.info("bigquery_get_patent_started", extra=log_extra)

        sql = f"""
        SELECT
            publication_number,
            title_localized[SAFE_OFFSET(0)].text AS title,
            abstract_localized[SAFE_OFFSET(0)].text AS abstract,
            claims_localized[SAFE_OFFSET(0)].text AS claims,
            description_localized[SAFE_OFFSET(0)].text AS description,
            CAST(filing_date AS STRING) AS filing_date,
            CAST(grant_date AS STRING) AS grant_date,
            CAST(publication_date AS STRING) AS publication_date,
            application_number,
            family_id,
            country_code,
            cpc,
            ipc
        FROM `{self.FULL_TABLE_ID}`
        WHERE publication_number = @patent_number
        LIMIT 1
        """

        job_config = self._make_job_config(
            [bigquery.ScalarQueryParameter("patent_number", "STRING", patent_number)]  # type: ignore[union-attr]
        )

        try:
            # Execute query with timing and timeout (30 seconds)
            if LOGGING_AVAILABLE and OperationTimer:
                with OperationTimer("bigquery_query"):
                    results = self.client.query(sql, job_config=job_config).result(timeout=30)
            else:
                results = self.client.query(sql, job_config=job_config).result(timeout=30)

            # Process results
            for row in results:
                # Extract CPC codes
                cpc_codes = []
                if row.cpc:
                    for cpc in row.cpc:
                        if hasattr(cpc, "code"):
                            cpc_codes.append(cpc.code)

                # Extract IPC codes
                ipc_codes = []
                if row.ipc:
                    for ipc in row.ipc:
                        if hasattr(ipc, "code"):
                            ipc_codes.append(ipc.code)

                patent_data = {
                    "patent_number": row.publication_number,
                    "application_number": row.application_number,
                    "title": row.title or "",
                    "abstract": row.abstract or "",
                    "claims": row.claims or "",
                    "description": row.description or "",
                    "filing_date": self._format_date(row.filing_date),
                    "grant_date": self._format_date(row.grant_date),
                    "publication_date": self._format_date(row.publication_date),
                    "country": row.country_code,
                    "family_id": row.family_id,
                    "cpc_codes": cpc_codes,
                    "ipc_codes": ipc_codes,
                }

                # Log successful retrieval
                completion_extra = {
                    **log_extra,
                    "found": True,
                    "cpc_codes_count": len(cpc_codes),
                    "has_claims": bool(row.claims),
                    "has_description": bool(row.description),
                    "bytes_processed": (
                        results.total_bytes_processed
                        if hasattr(results, "total_bytes_processed")
                        else 0
                    ),
                }

                if LOGGING_AVAILABLE and logger:
                    logger.info("bigquery_get_patent_completed", extra=completion_extra)

                return patent_data

            # Patent not found
            if LOGGING_AVAILABLE and logger:
                logger.warning("bigquery_get_patent_not_found", extra={**log_extra, "found": False})

            return None

        except Exception as e:
            error_extra = {**log_extra, "error_type": type(e).__name__, "error_message": str(e)}

            if LOGGING_AVAILABLE and logger:
                logger.error("bigquery_get_patent_failed", extra=error_extra, exc_info=True)
            else:
                print(f"BigQuery get patent error: {e}", file=sys.stderr)

            return None

    def search_by_cpc(
        self, cpc_code: str, limit: int = 20, country: str = "US"
    ) -> list[dict[str, Any]]:
        """
        Search patents by CPC classification code

        Args:
            cpc_code: CPC code prefix (e.g., "G06F" or "G06F16/")
            limit: Maximum number of results
            country: Country code filter

        Returns:
            List of patent dictionaries
        """
        if not self.client:
            raise RuntimeError("BigQuery client not initialized")

        # Log CPC search start
        log_extra = {"cpc_code": cpc_code, "limit": limit, "country": country}

        if LOGGING_AVAILABLE and logger:
            logger.info("bigquery_cpc_search_started", extra=log_extra)

        sql = f"""
        SELECT
            publication_number,
            title_localized[SAFE_OFFSET(0)].text AS title,
            abstract_localized[SAFE_OFFSET(0)].text AS abstract,
            CAST(filing_date AS STRING) AS filing_date,
            CAST(publication_date AS STRING) AS publication_date,
            application_number,
            country_code
        FROM `{self.FULL_TABLE_ID}`
        WHERE
            country_code = @country
            AND EXISTS (
                SELECT 1 FROM UNNEST(cpc) AS cpc_entry
                WHERE STARTS_WITH(cpc_entry.code, @cpc_code)
            )
        ORDER BY publication_date DESC, publication_number DESC
        LIMIT @limit
        """

        job_config = self._make_job_config(
            [
                bigquery.ScalarQueryParameter("cpc_code", "STRING", cpc_code),  # type: ignore[union-attr]
                bigquery.ScalarQueryParameter("country", "STRING", country),  # type: ignore[union-attr]
                bigquery.ScalarQueryParameter("limit", "INT64", limit),  # type: ignore[union-attr]
            ]
        )

        try:
            # Execute query with timing and timeout (30 seconds)
            if LOGGING_AVAILABLE and OperationTimer:
                with OperationTimer("bigquery_query"):
                    results = self.client.query(sql, job_config=job_config).result(timeout=30)
            else:
                results = self.client.query(sql, job_config=job_config).result(timeout=30)

            # Process results
            patents = []
            for row in results:
                patents.append(
                    {
                        "patent_number": row.publication_number,
                        "application_number": row.application_number,
                        "title": row.title or "",
                        "abstract": row.abstract or "",
                        "filing_date": self._format_date(row.filing_date),
                        "publication_date": self._format_date(row.publication_date),
                        "country": row.country_code,
                    }
                )

            # Log completion with metrics
            completion_extra = {
                **log_extra,
                "results_count": len(patents),
                "bytes_processed": (
                    results.total_bytes_processed
                    if hasattr(results, "total_bytes_processed")
                    else 0
                ),
                "bytes_billed": (
                    results.total_bytes_billed if hasattr(results, "total_bytes_billed") else 0  # type: ignore[attr-defined]
                ),
            }

            if LOGGING_AVAILABLE and logger:
                logger.info("bigquery_cpc_search_completed", extra=completion_extra)

            return patents

        except Exception as e:
            error_extra = {**log_extra, "error_type": type(e).__name__, "error_message": str(e)}

            if LOGGING_AVAILABLE and logger:
                logger.error("bigquery_cpc_search_failed", extra=error_extra, exc_info=True)
            else:
                print(f"BigQuery CPC search error: {e}", file=sys.stderr)

            raise

    def search_by_ipc(
        self, ipc_code: str, limit: int = 20, country: str = "US"
    ) -> list[dict[str, Any]]:
        """
        Search patents by IPC (International Patent Classification) code.

        IPC is valuable for older patents (pre-2013, before CPC adoption) and
        non-US patents that may have IPC but lack CPC codes.

        Args:
            ipc_code: IPC code prefix (e.g., "G06F", "H04L29/06")
            limit: Maximum number of results
            country: Country code filter (US, EP, WO, JP, CN, etc.)

        Returns:
            List of patent dictionaries
        """
        if not self.client:
            raise RuntimeError("BigQuery client not initialized")

        log_extra = {"ipc_code": ipc_code, "limit": limit, "country": country}

        if LOGGING_AVAILABLE and logger:
            logger.info("bigquery_ipc_search_started", extra=log_extra)

        sql = f"""
        SELECT
            publication_number,
            title_localized[SAFE_OFFSET(0)].text AS title,
            abstract_localized[SAFE_OFFSET(0)].text AS abstract,
            CAST(filing_date AS STRING) AS filing_date,
            CAST(publication_date AS STRING) AS publication_date,
            application_number,
            country_code
        FROM `{self.FULL_TABLE_ID}`
        WHERE
            country_code = @country
            AND EXISTS (
                SELECT 1 FROM UNNEST(ipc) AS ipc_entry
                WHERE STARTS_WITH(ipc_entry.code, @ipc_code)
            )
        ORDER BY publication_date DESC, publication_number DESC
        LIMIT @limit
        """

        job_config = self._make_job_config(
            [
                bigquery.ScalarQueryParameter("ipc_code", "STRING", ipc_code),  # type: ignore[union-attr]
                bigquery.ScalarQueryParameter("country", "STRING", country),  # type: ignore[union-attr]
                bigquery.ScalarQueryParameter("limit", "INT64", limit),  # type: ignore[union-attr]
            ]
        )

        try:
            if LOGGING_AVAILABLE and OperationTimer:
                with OperationTimer("bigquery_query"):
                    results = self.client.query(sql, job_config=job_config).result(timeout=30)
            else:
                results = self.client.query(sql, job_config=job_config).result(timeout=30)

            patents = []
            for row in results:
                patents.append(
                    {
                        "patent_number": row.publication_number,
                        "application_number": row.application_number,
                        "title": row.title or "",
                        "abstract": row.abstract or "",
                        "filing_date": self._format_date(row.filing_date),
                        "publication_date": self._format_date(row.publication_date),
                        "country": row.country_code,
                    }
                )

            completion_extra = {
                **log_extra,
                "results_count": len(patents),
                "bytes_processed": (
                    results.total_bytes_processed
                    if hasattr(results, "total_bytes_processed")
                    else 0
                ),
            }

            if LOGGING_AVAILABLE and logger:
                logger.info("bigquery_ipc_search_completed", extra=completion_extra)

            return patents

        except Exception as e:
            error_extra = {**log_extra, "error_type": type(e).__name__, "error_message": str(e)}

            if LOGGING_AVAILABLE and logger:
                logger.error("bigquery_ipc_search_failed", extra=error_extra, exc_info=True)
            else:
                print(f"BigQuery IPC search error: {e}", file=sys.stderr)

            raise

    def search_patent_family(
        self, family_id: int, limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        Search for all patent publications sharing a family_id.

        Patent families link related patents filed across multiple jurisdictions.
        This enables cross-jurisdiction analysis: find an EP/WO patent by
        title/abstract, then use family_id to locate the US family member
        for full claims text (only available for US patents in BigQuery).

        Args:
            family_id: Patent family identifier
            limit: Maximum number of results

        Returns:
            List of patent dictionaries across all jurisdictions
        """
        if not self.client:
            raise RuntimeError("BigQuery client not initialized")

        log_extra = {"family_id": family_id, "limit": limit}

        if LOGGING_AVAILABLE and logger:
            logger.info("bigquery_family_search_started", extra=log_extra)

        sql = f"""
        SELECT
            publication_number,
            title_localized[SAFE_OFFSET(0)].text AS title,
            abstract_localized[SAFE_OFFSET(0)].text AS abstract,
            CAST(filing_date AS STRING) AS filing_date,
            CAST(grant_date AS STRING) AS grant_date,
            CAST(publication_date AS STRING) AS publication_date,
            application_number,
            family_id,
            country_code,
            kind_code
        FROM `{self.FULL_TABLE_ID}`
        WHERE family_id = @family_id
        ORDER BY country_code, publication_date DESC
        LIMIT @limit
        """

        job_config = self._make_job_config(
            [
                bigquery.ScalarQueryParameter("family_id", "INT64", family_id),  # type: ignore[union-attr]
                bigquery.ScalarQueryParameter("limit", "INT64", limit),  # type: ignore[union-attr]
            ]
        )

        try:
            if LOGGING_AVAILABLE and OperationTimer:
                with OperationTimer("bigquery_query"):
                    results = self.client.query(sql, job_config=job_config).result(timeout=30)
            else:
                results = self.client.query(sql, job_config=job_config).result(timeout=30)

            patents = []
            for row in results:
                patents.append(
                    {
                        "patent_number": row.publication_number,
                        "application_number": row.application_number,
                        "title": row.title or "",
                        "abstract": row.abstract or "",
                        "filing_date": self._format_date(row.filing_date),
                        "grant_date": self._format_date(row.grant_date),
                        "publication_date": self._format_date(row.publication_date),
                        "country": row.country_code,
                        "kind_code": row.kind_code or "",
                        "family_id": row.family_id,
                    }
                )

            completion_extra = {
                **log_extra,
                "results_count": len(patents),
                "jurisdictions": list({p["country"] for p in patents}),
            }

            if LOGGING_AVAILABLE and logger:
                logger.info("bigquery_family_search_completed", extra=completion_extra)

            return patents

        except Exception as e:
            error_extra = {**log_extra, "error_type": type(e).__name__, "error_message": str(e)}

            if LOGGING_AVAILABLE and logger:
                logger.error("bigquery_family_search_failed", extra=error_extra, exc_info=True)
            else:
                print(f"BigQuery family search error: {e}", file=sys.stderr)

            raise

    def _make_job_config(self, parameters: list) -> Any:
        """Build a QueryJobConfig with parameters and the bytes-billed ceiling."""
        max_bytes = self.DEFAULT_MAX_BYTES_BILLED
        env_value = os.environ.get("PATENT_BIGQUERY_MAX_BYTES_BILLED")
        if env_value:
            try:
                parsed = int(env_value)
            except ValueError:
                parsed = 0
            if parsed > 0:
                max_bytes = parsed
            elif LOGGING_AVAILABLE and logger:
                logger.warning(
                    "patent_bigquery_max_bytes_billed_invalid",
                    extra={"value": env_value, "fallback_bytes": max_bytes},
                )
        return bigquery.QueryJobConfig(  # type: ignore[union-attr]
            query_parameters=parameters,
            maximum_bytes_billed=max_bytes,
        )

    def _format_date(self, date_int: Optional[int]) -> Optional[str]:
        """Convert YYYYMMDD integer to YYYY-MM-DD string"""
        if not date_int:
            return None

        try:
            date_str = str(date_int)
            if len(date_str) == 8:
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
            return date_str
        except Exception:
            return None


def check_bigquery_available() -> dict[str, Any]:
    """
    Check if BigQuery is available and configured

    Returns:
        Status dictionary
    """
    if not BIGQUERY_AVAILABLE:
        return {
            "available": False,
            "error": "google-cloud-bigquery not installed",
            "install_command": "pip install google-cloud-bigquery db-dtypes",
        }

    try:
        searcher = BigQueryPatentSearch()
        return searcher.check_availability()
    except Exception as e:
        return {"available": False, "error": str(e)}
