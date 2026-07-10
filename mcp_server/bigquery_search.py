#!/usr/bin/env python3
"""
BigQuery Patent Search
Fast, cloud-based patent search using Google's Patents Public Data
"""

import os
import platform
import re
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

    # Per-query bytes-billed ceiling; override via PATENT_BIGQUERY_MAX_BYTES_BILLED.
    # Defaults to 350 GiB so a normal keyword prior-art search works out of the
    # box: the default search spans title+abstract+claims, which scans ~325 GiB
    # of the public corpus (~$2.15/query at $6.25/TiB). A free dry-run still
    # estimates each query and fails fast before anything larger is billed.
    DEFAULT_MAX_BYTES_BILLED = 350 * 1024**3
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

    @staticmethod
    def _tokenize_query(query: str) -> list[str]:
        """Split a free-text query into search terms for keyword matching.

        Prior-art search lives or dies on recall, so a multi-word query is
        treated as a set of terms that must each appear in some searched field
        (AND across terms) rather than as one verbatim phrase. Rules:

        * ``"quoted substrings"`` are kept together as exact phrases.
        * Standalone boolean operators (and/or/not) and parentheses are dropped,
          so Boolean-style input degrades gracefully into an all-terms match
          instead of being matched literally (which found nothing).
        * Surrounding punctuation is stripped and duplicate terms removed.

        Returns an ordered, de-duplicated list of lowercase terms.
        """
        if not query:
            return []

        lowered = query.lower()
        phrases = re.findall(r'"([^"]+)"', lowered)
        remainder = re.sub(r'"[^"]+"', " ", lowered)
        remainder = re.sub(r"[()]", " ", remainder)

        words = []
        for word in remainder.split():
            if word in {"and", "or", "not"}:
                continue
            word = word.strip(".,;:'\"-/")
            if word:
                words.append(word)

        ordered = [p.strip() for p in phrases if p.strip()] + words
        seen: set[str] = set()
        terms: list[str] = []
        for term in ordered:
            if term not in seen:
                seen.add(term)
                terms.append(term)
        return terms

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
            bigquery.ScalarQueryParameter("country", "STRING", country),  # type: ignore[union-attr]
            bigquery.ScalarQueryParameter("limit", "INT64", limit),  # type: ignore[union-attr]
            bigquery.ScalarQueryParameter("offset", "INT64", offset),  # type: ignore[union-attr]
        ]

        # Map requested fields to (SQL expression, relevance weight). A title hit
        # is a stronger relevance signal than an abstract/claims hit.
        # claims_localized only carries text for US publications; for EP/WO
        # full-text use epo_api.py.
        field_exprs: list[tuple[str, int]] = []
        if "title" in search_fields:
            field_exprs.append(("LOWER(title_localized[SAFE_OFFSET(0)].text)", 3))
        if "abstract" in search_fields:
            field_exprs.append(("LOWER(abstract_localized[SAFE_OFFSET(0)].text)", 1))
        if "claims" in search_fields and country == "US":
            field_exprs.append(("LOWER(claims_localized[SAFE_OFFSET(0)].text)", 1))

        # Split the query into terms. Each term must appear in at least one
        # searched field (AND across terms, OR across fields), so a natural
        # multi-word query no longer requires one verbatim phrase to match.
        # Wrap a substring in "double quotes" to force exact-phrase matching.
        terms = self._tokenize_query(query)

        # Bail out instead of emitting a predicate-less query that would scan and
        # bill the entire corpus and return everything: this happens for an
        # empty/operator-only query (no terms) or when the only requested field
        # is claims on a non-US country (no field_exprs, since non-US has no
        # claims full-text here).
        if not terms or not field_exprs:
            if LOGGING_AVAILABLE and logger:
                logger.info("bigquery_search_no_predicate", extra=log_extra)
            return []

        relevance_parts: list[str] = []
        for i, term in enumerate(terms):
            pname = f"term{i}"
            # Escape LIKE metacharacters so a term containing % or _ (or the
            # backslash escape char) matches literally instead of acting as a
            # wildcard — otherwise a stray "%" would match every row.
            escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            parameters.append(
                bigquery.ScalarQueryParameter(pname, "STRING", f"%{escaped}%")  # type: ignore[union-attr]
            )
            term_clause = " OR ".join(f"{expr} LIKE @{pname}" for expr, _ in field_exprs)
            conditions.append(f"({term_clause})")
            for expr, weight in field_exprs:
                relevance_parts.append(
                    f"CASE WHEN {expr} LIKE @{pname} THEN {weight} ELSE 0 END"
                )

        relevance_expr = " + ".join(relevance_parts) if relevance_parts else "0"

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
            country_code,
            ({relevance_expr}) AS relevance_score
        FROM `{self.FULL_TABLE_ID}`
        WHERE {where_clause}
        ORDER BY relevance_score DESC, publication_date DESC, publication_number DESC
        LIMIT @limit
        OFFSET @offset
        """

        try:
            results = self._run_query(sql, parameters)

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
                        "relevance_score": row.relevance_score,
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

        try:
            results = self._run_query(
                sql,
                [bigquery.ScalarQueryParameter("patent_number", "STRING", patent_number)],  # type: ignore[union-attr]
            )

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

        try:
            results = self._run_query(
                sql,
                [
                    bigquery.ScalarQueryParameter("cpc_code", "STRING", cpc_code),  # type: ignore[union-attr]
                    bigquery.ScalarQueryParameter("country", "STRING", country),  # type: ignore[union-attr]
                    bigquery.ScalarQueryParameter("limit", "INT64", limit),  # type: ignore[union-attr]
                ],
            )

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

        try:
            results = self._run_query(
                sql,
                [
                    bigquery.ScalarQueryParameter("ipc_code", "STRING", ipc_code),  # type: ignore[union-attr]
                    bigquery.ScalarQueryParameter("country", "STRING", country),  # type: ignore[union-attr]
                    bigquery.ScalarQueryParameter("limit", "INT64", limit),  # type: ignore[union-attr]
                ],
            )

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

        try:
            results = self._run_query(
                sql,
                [
                    bigquery.ScalarQueryParameter("family_id", "INT64", family_id),  # type: ignore[union-attr]
                    bigquery.ScalarQueryParameter("limit", "INT64", limit),  # type: ignore[union-attr]
                ],
            )

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

    def _resolve_max_bytes_billed(self) -> int:
        """Resolve the per-query bytes-billed ceiling (env override or default)."""
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
        return max_bytes

    def _make_job_config(self, parameters: list) -> Any:
        """Build a QueryJobConfig with parameters and the bytes-billed ceiling."""
        return bigquery.QueryJobConfig(  # type: ignore[union-attr]
            query_parameters=parameters,
            maximum_bytes_billed=self._resolve_max_bytes_billed(),
        )

    def _assert_within_budget(self, sql: str, parameters: list) -> None:
        """Estimate the query's scan size with a free dry run and fail loudly if it
        would exceed the bytes-billed ceiling.

        Without this guard an over-budget query is either rejected mid-flight by
        BigQuery with an opaque ``bytesBilledLimitExceeded`` 500 or appears to hang,
        giving the caller no actionable signal. A dry run is free and near-instant, so
        we surface a clear, actionable error *before* spending any query budget.
        """
        if not self.client or bigquery is None:
            return
        max_bytes = self._resolve_max_bytes_billed()
        try:
            dry_config = bigquery.QueryJobConfig(  # type: ignore[union-attr]
                query_parameters=parameters, dry_run=True, use_query_cache=False
            )
            estimate = self.client.query(sql, job_config=dry_config).total_bytes_processed
        except Exception:
            # A failed estimate must never block the search; let the real query run
            # and surface any genuine error itself.
            return
        if estimate is None or estimate <= max_bytes:
            return
        est_gib = estimate / 1024**3
        cap_gib = max_bytes / 1024**3
        suggested = int(estimate * 1.2)
        est_usd = estimate / 1024**4 * 6.25  # on-demand BigQuery: ~$6.25 per TiB scanned
        raise ValueError(
            f"Patent search would scan ~{est_gib:.0f} GiB, exceeding the per-query cost "
            f"cap of {cap_gib:.0f} GiB. Narrow the search (add country / start_year / "
            f"end_year filters or more specific keywords), or raise the cap by setting "
            f"PATENT_BIGQUERY_MAX_BYTES_BILLED={suggested} "
            f"(~{est_gib * 1.2:.0f} GiB, ~${est_usd:.2f} per query at on-demand pricing)."
        )

    def _run_query(self, sql: str, parameters: list) -> Any:
        """Pre-flight the cost, then execute the query and return the row iterator."""
        self._assert_within_budget(sql, parameters)
        job_config = self._make_job_config(parameters)
        if LOGGING_AVAILABLE and OperationTimer:
            with OperationTimer("bigquery_query"):
                return self.client.query(sql, job_config=job_config).result(
                    timeout=self.QUERY_TIMEOUT_SECONDS
                )
        return self.client.query(sql, job_config=job_config).result(
            timeout=self.QUERY_TIMEOUT_SECONDS
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
