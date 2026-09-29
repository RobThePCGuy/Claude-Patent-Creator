"""
Prior Art Search Types and Implementation
Defines data structures for patent prior art search backed by Google BigQuery
Patents Public Data (~100M patents worldwide).
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# Add mcp_server to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import BigQuery search module
try:
    from mcp_server.bigquery_search import BIGQUERY_AVAILABLE, BigQueryPatentSearch
except ImportError:
    BigQueryPatentSearch = None
    BIGQUERY_AVAILABLE = False


# Global searcher instance (lazy-loaded)
_bigquery_searcher: Optional[Any] = None


def _get_bigquery_searcher() -> Any:
    """Get or initialize the BigQuery searcher singleton."""
    global _bigquery_searcher

    if not BIGQUERY_AVAILABLE:
        raise RuntimeError(
            "BigQuery backend not available. Install with:\n"
            "  pip install google-cloud-bigquery db-dtypes\n\n"
            "Then authenticate:\n"
            "  1. Install gcloud: https://cloud.google.com/sdk/docs/install\n"
            "  2. Run: gcloud auth application-default login\n"
            "  3. Sign in with Google (no credit card required)\n"
        )

    if _bigquery_searcher is None:
        if BigQueryPatentSearch is None:
            raise RuntimeError("BigQueryPatentSearch class not available")

        _bigquery_searcher = BigQueryPatentSearch()

        if _bigquery_searcher.client is None:
            raise RuntimeError(
                "BigQuery client not initialized. Please run:\n"
                "  gcloud auth application-default login\n\n"
                "Or set GOOGLE_CLOUD_PROJECT environment variable."
            )

    return _bigquery_searcher


@dataclass
class PriorArtHit:
    """
    Represents a single prior art search result.

    This is the primary result type returned by search_prior_art().
    Contains essential patent information and relevance scoring.
    """

    patent_id: str
    """Patent publication number (e.g., 'US-10123456-B2', 'EP-1234567-A1')"""

    title: str
    """Patent title"""

    snippet: str
    """Relevant text snippet showing why this patent matched the query"""

    score: float
    """Relevance score (0.0-1.0, higher = more relevant)"""

    cpc: Optional[list[str]] = None
    """Cooperative Patent Classification codes (e.g., ['G06F17/30', 'H04L29/08'])"""

    filing_date: Optional[str] = None
    """Filing date in ISO format (YYYY-MM-DD)"""

    grant_date: Optional[str] = None
    """Grant date in ISO format (YYYY-MM-DD), None if application not granted"""

    publication_date: Optional[str] = None
    """Publication date in ISO format (YYYY-MM-DD)"""

    source: Optional[str] = None
    """Data source ('bigquery', 'patentsview', 'uspto', etc.)"""

    country: Optional[str] = None
    """Country code (e.g., 'US', 'EP', 'JP', 'CN')"""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "patent_id": self.patent_id,
            "title": self.title,
            "snippet": self.snippet,
            "score": self.score,
            "cpc": self.cpc,
            "filing_date": self.filing_date,
            "grant_date": self.grant_date,
            "publication_date": self.publication_date,
            "source": self.source,
            "country": self.country,
        }


@dataclass
class PatentDocument:
    """
    Represents a complete patent document with full metadata and content.

    This is returned by get_patent_details() and contains comprehensive
    patent information including full text, claims, and citation data.
    """

    patent_number: str
    """Patent publication number (primary identifier)"""

    title: str
    """Patent title"""

    abstract: str
    """Patent abstract"""

    claims: list[str]
    """List of patent claims (ordered, typically 1-indexed)"""

    country: str
    """Country code (e.g., 'US', 'EP', 'JP')"""

    application_number: Optional[str] = None
    """Application number (e.g., '15/123,456' for US)"""

    description: Optional[str] = None
    """Full specification/description text (can be very large)"""

    assignees: list[str] = field(default_factory=list)
    """List of assignee/applicant organization names"""

    inventors: list[str] = field(default_factory=list)
    """List of inventor names"""

    cpc_codes: list[str] = field(default_factory=list)
    """List of Cooperative Patent Classification codes"""

    filing_date: Optional[str] = None
    """Filing date in ISO format (YYYY-MM-DD)"""

    grant_date: Optional[str] = None
    """Grant date in ISO format (YYYY-MM-DD), None if not granted"""

    publication_date: Optional[str] = None
    """Publication date in ISO format (YYYY-MM-DD)"""

    priority_date: Optional[str] = None
    """Earliest priority date in ISO format (YYYY-MM-DD)"""

    family_id: Optional[str] = None
    """Patent family ID (links related patents across countries)"""

    references_cited: Optional[list[str]] = None
    """List of patent numbers cited by this patent"""

    cited_by: Optional[list[str]] = None
    """List of patent numbers that cite this patent (forward citations)"""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "patent_number": self.patent_number,
            "application_number": self.application_number,
            "title": self.title,
            "abstract": self.abstract,
            "claims": self.claims,
            "description": self.description,
            "assignees": self.assignees,
            "inventors": self.inventors,
            "cpc_codes": self.cpc_codes,
            "filing_date": self.filing_date,
            "grant_date": self.grant_date,
            "publication_date": self.publication_date,
            "priority_date": self.priority_date,
            "family_id": self.family_id,
            "country": self.country,
            "references_cited": self.references_cited,
            "cited_by": self.cited_by,
        }


# ============================================================================
# REAL IMPLEMENTATIONS (BigQuery-backed)
# ============================================================================


def search_prior_art(
    query: str,
    top_k: int = 20,
    country: Optional[str] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    cpc_filter: Optional[list[str]] = None,
    search_fields: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Search for relevant prior art patents using Google BigQuery.

    This function provides REAL patent search backed by BigQuery Patents Public Data
    (~72M+ patents worldwide, 12M+ US patents).

    Args:
        query: Search query (keywords, technical description, natural language)
        top_k: Number of results to return (default: 20, max: 100)
        country: Filter by country code (e.g., "US", "EP", None for all)
        start_year: Filter by filing year >= start_year
        end_year: Filter by filing year <= end_year
        cpc_filter: Filter by CPC classification codes (e.g., ["G06F", "H04L"])
        search_fields: Which fields to search (default: ["title", "abstract", "claims"])

    Returns:
        Dictionary with:
            - success: bool
            - hits: List[dict] (PriorArtHit dictionaries)
            - total_found: int
            - query_info: dict with query metadata
            - backend: "bigquery"

        Or on error:
            - success: False
            - hits: []
            - error: Error message
            - backend: "bigquery"
    """
    # Input validation
    if not query or not query.strip():
        return {
            "success": False,
            "hits": [],
            "error": "Query cannot be empty",
            "backend": "bigquery",
        }

    query = query.strip()

    if len(query) < 3:
        return {
            "success": False,
            "hits": [],
            "error": f"Query too short (minimum 3 characters, got {len(query)})",
            "backend": "bigquery",
        }

    # Cap top_k
    top_k = min(max(1, top_k), 100)

    # Default country to US if not specified
    if country is None:
        country = "US"

    # Default search fields
    if search_fields is None:
        search_fields = ["title", "abstract", "claims"]

    try:
        # Get BigQuery searcher
        searcher = _get_bigquery_searcher()

        # If CPC filter is provided, use CPC search, otherwise use keyword search
        if cpc_filter and len(cpc_filter) > 0:
            # Use CPC search for the first filter only
            raw_results = searcher.search_by_cpc(
                cpc_code=cpc_filter[0],
                limit=top_k,
                country=country,
            )
        else:
            # Execute keyword search
            raw_results = searcher.search_by_keywords(
                query=query,
                country=country,
                limit=top_k,
                offset=0,
                start_year=start_year,
                end_year=end_year,
                search_fields=search_fields,
            )

        # Convert to PriorArtHit objects
        hits = []
        for i, patent_data in enumerate(raw_results):
            # Create snippet from abstract (first 200 chars)
            abstract = patent_data.get("abstract", "")
            snippet = abstract[:200] + "..." if len(abstract) > 200 else abstract

            # Calculate simple relevance score (inverse rank)
            score = 1.0 - (i / max(len(raw_results), 1))

            hit = PriorArtHit(
                patent_id=patent_data.get("patent_number", ""),
                title=patent_data.get("title", ""),
                snippet=snippet,
                score=score,
                cpc=None,  # CPC not included in search results, only in details
                filing_date=patent_data.get("filing_date"),
                grant_date=patent_data.get("grant_date"),
                publication_date=patent_data.get("publication_date"),
                source="bigquery",
                country=patent_data.get("country"),
            )
            hits.append(hit)

        return {
            "success": True,
            "hits": [hit.to_dict() for hit in hits],
            "total_found": len(hits),
            "query_info": {
                "query": query,
                "top_k": top_k,
                "country": country,
                "date_range": f"{start_year}-{end_year}" if start_year or end_year else None,
                "search_fields": search_fields,
            },
            "backend": "bigquery",
        }

    except RuntimeError as e:
        # BigQuery not configured
        return {"success": False, "hits": [], "error": str(e), "backend": "bigquery"}
    except Exception as e:
        # Other errors
        return {
            "success": False,
            "hits": [],
            "error": f"BigQuery search failed: {str(e)}",
            "backend": "bigquery",
        }


def get_patent_details(
    patent_id: str,
    include_abstract: bool = False,
    include_claims: bool = True,
    include_description: bool = False,
) -> dict[str, Any]:
    """
    Retrieve a patent document by patent number using Google BigQuery.

    This function provides REAL patent retrieval backed by BigQuery Patents Public Data.
    Text sections are opt-in because each is billed as a full-corpus column
    scan (see BigQueryPatentSearch.get_patent_details); sections not
    requested come back as an empty abstract / None description.

    Args:
        patent_id: Patent publication number (e.g., "US-10123456-B2", "US10123456")
                  Various formats accepted, will be normalized.
        include_abstract: Include the abstract (~201 GiB scan)
        include_claims: Include the claims (~119 GiB scan)
        include_description: Include the full description (~1 TiB scan;
                  exceeds the default cost cap)

    Returns:
        Dictionary with:
            - success: bool
            - document: dict (PatentDocument dictionary) or None
            - message: str
            - backend: "bigquery"

        Or on error:
            - success: False
            - document: None
            - error: Error message
            - backend: "bigquery"
    """
    # Input validation
    if not patent_id or not patent_id.strip():
        return {
            "success": False,
            "document": None,
            "error": "Patent ID cannot be empty",
            "backend": "bigquery",
        }

    # Normalize patent ID
    normalized_id = normalize_patent_id(patent_id)

    try:
        # Get BigQuery searcher
        searcher = _get_bigquery_searcher()

        # Fetch patent details
        patent_data = searcher.get_patent_details(
            normalized_id,
            include_abstract=include_abstract,
            include_claims=include_claims,
            include_description=include_description,
        )

        if patent_data is None:
            return {
                "success": False,
                "document": None,
                "error": f"Patent not found in BigQuery: {normalized_id}",
                "backend": "bigquery",
            }

        # Parse claims text into list (split by claim numbers)
        claims_text = patent_data.get("claims", "")
        claims_list = []
        if claims_text:
            # Simple splitting by numbered claims (1., 2., etc.)
            import re

            claim_parts = re.split(r"\n\s*\d+\.\s+", claims_text)
            claims_list = [c.strip() for c in claim_parts if c.strip()]

        # Convert to PatentDocument
        doc = PatentDocument(
            patent_number=patent_data.get("patent_number", ""),
            application_number=patent_data.get("application_number"),
            title=patent_data.get("title", ""),
            abstract=patent_data.get("abstract", ""),
            claims=claims_list,
            description=patent_data.get("description"),
            assignees=[],  # Not yet extracted from BigQuery
            inventors=[],  # Not yet extracted from BigQuery
            cpc_codes=patent_data.get("cpc_codes", []),
            filing_date=patent_data.get("filing_date"),
            grant_date=patent_data.get("grant_date"),
            publication_date=patent_data.get("publication_date"),
            priority_date=None,  # Not yet available
            family_id=patent_data.get("family_id"),
            country=patent_data.get("country", ""),
            references_cited=None,  # Not yet extracted
            cited_by=None,  # Not yet available
        )

        return {
            "success": True,
            "document": doc.to_dict(),
            "message": "Patent retrieved from BigQuery",
            "backend": "bigquery",
        }

    except RuntimeError as e:
        # BigQuery not configured
        return {"success": False, "document": None, "error": str(e), "backend": "bigquery"}
    except Exception as e:
        # Other errors
        return {
            "success": False,
            "document": None,
            "error": f"BigQuery retrieval failed: {str(e)}",
            "backend": "bigquery",
        }


def search_semantic_similar(
    seed_patent: str, top_k: int = 20, country: Optional[str] = None, min_similarity: float = 0.7
) -> dict[str, Any]:
    """
    Find patents semantically similar to a seed patent (Priority 2 - NOT YET IMPLEMENTED).

    This feature requires Google's pre-computed patent embeddings which are not
    yet implemented in BigQueryPatentSearch.

    Args:
        seed_patent: Publication number of seed patent (e.g., "US10123456B2")
        top_k: Number of similar patents to return (default: 20, max: 100)
        country: Filter by country code (default: "US")
        min_similarity: Minimum cosine similarity threshold 0.0-1.0 (default: 0.7)

    Returns:
        Dictionary with error message indicating feature not implemented
    """
    return {
        "success": False,
        "results": [],
        "error": "Semantic similarity search not yet implemented. Use search_prior_art() for keyword-based search.",
        "backend": "bigquery_embeddings",
        "feature_status": "planned",
    }


def search_hybrid_multistage(
    query: str,
    top_k: int = 20,
    country: Optional[str] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    cpc_filter: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Multi-stage hybrid search: Keyword -> Semantic -> Rerank (Priority 2 - NOT YET IMPLEMENTED).

    This feature would combine keyword search for broad recall with semantic filtering,
    but is not yet implemented in BigQueryPatentSearch.

    Until that lands, this function delegates to keyword search and sets
    `degraded: True` on the response so the caller knows.

    Args:
        query: Search query string
        top_k: Final number of results (default: 20, max: 100)
        country: Filter by country code (default: "US")
        start_year: Filter by filing year >= start_year
        end_year: Filter by filing year <= end_year
        cpc_filter: Filter by CPC classification codes

    Returns:
        Dictionary with search results plus `degraded` and `degraded_reason`
        fields so callers can detect that they got keyword search rather
        than the requested multi-stage retrieval.
    """
    response = search_prior_art(
        query=query,
        top_k=top_k,
        country=country,
        start_year=start_year,
        end_year=end_year,
        cpc_filter=cpc_filter,
        search_fields=["title", "abstract", "claims"],
    )
    response["degraded"] = True
    response["degraded_reason"] = (
        "search_hybrid_multistage is not implemented; results returned by "
        "search_prior_art (keyword only)."
    )
    return response


def check_backend_availability() -> dict[str, Any]:
    """
    Check if BigQuery backend is configured and available.

    Returns:
        Dictionary with:
            - available: bool
            - backend: "bigquery"
            - message: str
            - details: dict (optional)
    """
    if not BIGQUERY_AVAILABLE:
        return {
            "available": False,
            "backend": "bigquery",
            "error": "google-cloud-bigquery not installed",
            "message": (
                "BigQuery Python client not installed. Install with:\n"
                "  pip install google-cloud-bigquery db-dtypes"
            ),
            "setup_required": [
                "Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install",
                "Authenticate: gcloud auth application-default login",
                "Install Python client: pip install google-cloud-bigquery db-dtypes",
            ],
        }

    try:
        # Try to create searcher
        searcher = _get_bigquery_searcher()

        # Check availability
        availability = searcher.check_availability()

        if availability.get("available"):
            return {
                "available": True,
                "backend": "bigquery",
                "message": "BigQuery patent search ready",
                "details": {
                    "project": availability.get("project"),
                    "us_patents": availability.get("us_patents"),
                    "coverage": "100M+ worldwide patents, 12M+ US patents",
                },
            }
        else:
            return {
                "available": False,
                "backend": "bigquery",
                "error": availability.get("error", "Unknown error"),
                "message": availability.get("message", "BigQuery not accessible"),
                "setup_required": [
                    "Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install",
                    "Authenticate: gcloud auth application-default login",
                    "Set GOOGLE_CLOUD_PROJECT env var (optional)",
                ],
            }

    except RuntimeError as e:
        return {
            "available": False,
            "backend": "bigquery",
            "error": str(e),
            "message": "BigQuery not configured",
            "setup_required": [
                "Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install",
                "Authenticate: gcloud auth application-default login",
                "Install Python client: pip install google-cloud-bigquery db-dtypes",
            ],
        }
    except Exception as e:
        return {
            "available": False,
            "backend": "bigquery",
            "error": str(e),
            "message": f"BigQuery availability check failed: {str(e)}",
        }


# ============================================================================
# Helper Functions
# ============================================================================


def normalize_patent_id(patent_id: str) -> str:
    """
    Strip spaces and commas from a patent ID.

    BigQuery stores "US-1234567-B2" (hyphenated) and matches exactly;
    BigQueryPatentSearch.get_patent_details() maps any common form to that
    via to_publication_number(), so this only needs to remove noise.

    Examples:
        "US-10123456-B2" -> "US-10123456-B2"
        "US 10,123,456" -> "US10123456"
        "US10123456B2" -> "US10123456B2"

    Args:
        patent_id: Patent ID in various formats

    Returns:
        Normalized patent ID string
    """
    # Remove spaces, commas, and standardize
    normalized = patent_id.strip().replace(" ", "").replace(",", "")

    # BigQuery accepts various formats, so we'll keep it simple
    # Just remove extraneous characters and let BigQuery handle it
    return normalized


def format_date(date_str: Optional[str]) -> Optional[str]:
    """
    Format date string to ISO format YYYY-MM-DD.

    Args:
        date_str: Date in various formats (YYYYMMDD, YYYY-MM-DD, etc.)

    Returns:
        ISO-formatted date string or None
    """
    if not date_str:
        return None

    # Remove any non-digit characters
    digits_only = "".join(c for c in date_str if c.isdigit())

    if len(digits_only) == 8:
        # YYYYMMDD format
        return f"{digits_only[:4]}-{digits_only[4:6]}-{digits_only[6:8]}"
    elif "-" in date_str and len(date_str) == 10:
        # Already in YYYY-MM-DD format
        return date_str

    return None


# ============================================================================
# Type Exports
# ============================================================================

__all__ = [
    "PriorArtHit",
    "PatentDocument",
    "search_prior_art",
    "get_patent_details",
    "search_semantic_similar",  # Priority 2: Semantic search
    "search_hybrid_multistage",  # Priority 2: Multi-stage retrieval
    "check_backend_availability",
    "normalize_patent_id",
    "format_date",
]
