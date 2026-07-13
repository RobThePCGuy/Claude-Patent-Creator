"""
Pydantic models for input validation of MCP tools.

Provides type-safe validation with clear error messages.
"""

# pyright: reportCallInDefaultInitializer=false

import re
from typing import Literal, Optional

try:
    from pydantic import BaseModel, Field, ValidationError, conint, constr, field_validator
except ImportError as e:
    raise ImportError(
        "pydantic>=2.12.5 is required. Install with: pip install 'pydantic>=2.12.5'"
    ) from e

_COUNTRY_CODE_RE = re.compile(r"^[A-Za-z]{2}$")


# Search Input Models


class SearchMPEPInput(BaseModel):  # type: ignore[misc]
    """Input validation for MPEP search."""

    query: constr(min_length=1, max_length=1000) = Field(  # type: ignore[valid-type]
        ..., description="Search query text", examples=["35 USC 112 enablement requirements"]
    )
    top_k: conint(ge=1, le=20) = Field(  # type: ignore[valid-type]
        default=5, description="Number of results to return (1-20)"
    )
    retrieve_k: Optional[conint(ge=1, le=100)] = Field(  # type: ignore[valid-type]
        default=None, description="Number of candidates to retrieve before reranking"
    )
    source_filter: Optional[str] = Field(
        default=None,
        description="Filter by source: US (MPEP, 35_USC, 37_CFR, SUBSEQUENT), EPO (EPC, EPC_RULES, EPO_GUIDELINES), PCT (PCT, PCT_RULES)",
    )
    is_statute: Optional[bool] = Field(default=None, description="Filter for statutes only")
    is_regulation: Optional[bool] = Field(default=None, description="Filter for regulations only")
    is_update: Optional[bool] = Field(default=None, description="Filter for updates only")

    @field_validator("source_filter")
    @classmethod
    def validate_source_filter(cls, v: Optional[str]) -> Optional[str]:
        """Validate source filter."""
        if v is not None:
            valid_sources = {
                "MPEP",
                "35_USC",
                "37_CFR",
                "SUBSEQUENT",
                "EPC",
                "EPC_RULES",
                "EPO_GUIDELINES",
                "PCT",
                "PCT_RULES",
            }
            if v not in valid_sources:
                raise ValueError(f"source_filter must be one of {valid_sources}")
        return v


class SearchBigQueryInput(BaseModel):  # type: ignore[misc]
    """Input validation for BigQuery patent search."""

    query: constr(min_length=1, max_length=500) = Field(  # type: ignore[valid-type]
        ...,
        description="Search query keywords",
        examples=["machine learning image recognition"],
    )
    limit: conint(ge=1, le=100) = Field(  # type: ignore[valid-type]
        default=20, description="Maximum number of results (1-100)"
    )
    country: constr(min_length=2, max_length=2) = Field(  # type: ignore[valid-type]
        default="US",
        description="Two-letter country code (US, EP, WO, JP, CN, etc.). Note: claims/description text only available for US patents.",
    )
    start_year: Optional[conint(ge=1, le=2100)] = Field(  # type: ignore[valid-type]
        default=None, description="Filter patents filed on or after this year"
    )
    end_year: Optional[conint(ge=1, le=2100)] = Field(  # type: ignore[valid-type]
        default=None, description="Filter patents filed on or before this year"
    )

    @field_validator("end_year")
    @classmethod
    def validate_year_range(cls, v: Optional[int], info) -> Optional[int]:
        """Validate year range."""
        if v is not None and "start_year" in info.data:
            start_year = info.data["start_year"]
            if start_year is not None and v < start_year:
                raise ValueError("end_year must be >= start_year")
        return v

    @field_validator("country")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        """Restrict to ISO-style two-letter codes; defense-in-depth even
        though this value also flows through BigQuery query parameters."""
        if not _COUNTRY_CODE_RE.match(v):
            raise ValueError("country must be two letters (ISO 3166 alpha-2)")
        return v.upper()


class SearchUSPTOInput(BaseModel):  # type: ignore[misc]
    """Input validation for USPTO API search."""

    query: constr(min_length=1, max_length=500) = Field(..., description="Search query text")  # type: ignore[valid-type]
    limit: conint(ge=1, le=100) = Field(  # type: ignore[valid-type]
        default=25, description="Maximum number of results (1-100)"
    )
    start_year: Optional[conint(ge=1, le=2100)] = Field(  # type: ignore[valid-type]
        default=None, description="Filter by filing year start"
    )
    end_year: Optional[conint(ge=1, le=2100)] = Field(  # type: ignore[valid-type]
        default=None, description="Filter by filing year end"
    )
    application_type: Optional[str] = Field(
        default=None, description="Filter by application type (e.g., 'Utility')"
    )
    status: Optional[str] = Field(default=None, description="Filter by patent status")


class GetPatentInput(BaseModel):  # type: ignore[misc]
    """Input validation for getting patent details."""

    patent_number: constr(min_length=1, max_length=50) = Field(  # type: ignore[valid-type]
        ...,
        description="Patent number (e.g., '10123456', 'US10123456')",
        examples=["10123456", "US10123456B2"],
    )

    @field_validator("patent_number")
    @classmethod
    def sanitize_patent_number(cls, v: str) -> str:
        """Remove common formatting characters."""
        return v.replace(",", "").replace(" ", "").replace("-", "").strip()


class CPCSearchInput(BaseModel):  # type: ignore[misc]
    """Input validation for CPC code search."""

    cpc_code: constr(min_length=1, max_length=50) = Field(  # type: ignore[valid-type]
        ...,
        description="CPC classification code or prefix",
        examples=["G06F", "G06F16/", "H04L29/06"],
    )
    limit: conint(ge=1, le=100) = Field(  # type: ignore[valid-type]
        default=20, description="Maximum number of results (1-100)"
    )
    country: constr(min_length=2, max_length=2) = Field(  # type: ignore[valid-type]
        default="US",
        description="Two-letter country code (US, EP, WO, JP, CN, etc.)",
    )

    @field_validator("country")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        if not _COUNTRY_CODE_RE.match(v):
            raise ValueError("country must be two letters (ISO 3166 alpha-2)")
        return v.upper()


class IPCSearchInput(BaseModel):  # type: ignore[misc]
    """Input validation for IPC (International Patent Classification) code search."""

    ipc_code: constr(min_length=1, max_length=50) = Field(  # type: ignore[valid-type]
        ...,
        description="IPC classification code or prefix",
        examples=["G06F", "H04L29/06", "A61K"],
    )
    limit: conint(ge=1, le=100) = Field(  # type: ignore[valid-type]
        default=20, description="Maximum number of results (1-100)"
    )
    country: constr(min_length=2, max_length=2) = Field(  # type: ignore[valid-type]
        default="US",
        description="Two-letter country code (US, EP, WO, JP, CN, etc.)",
    )

    @field_validator("country")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        if not _COUNTRY_CODE_RE.match(v):
            raise ValueError("country must be two letters (ISO 3166 alpha-2)")
        return v.upper()


class FamilySearchInput(BaseModel):  # type: ignore[misc]
    """Input validation for patent family search."""

    family_id: int = Field(
        ...,
        description="Patent family identifier (links related patents across jurisdictions)",
    )
    limit: conint(ge=1, le=100) = Field(  # type: ignore[valid-type]
        default=50, description="Maximum number of results (1-100)"
    )


class SearchPatentLawInput(BaseModel):  # type: ignore[misc]
    """Input validation for cross-jurisdiction patent law search."""

    query: constr(min_length=1, max_length=1000) = Field(  # type: ignore[valid-type]
        ...,
        description="Search query text",
        examples=["claim definiteness requirements", "sufficiency of disclosure"],
    )
    top_k: conint(ge=1, le=20) = Field(  # type: ignore[valid-type]
        default=5, description="Number of results to return (1-20)"
    )
    jurisdiction: Optional[str] = Field(
        default=None,
        description="Filter by jurisdiction: US, EPO, PCT, or None for all",
    )

    @field_validator("jurisdiction")
    @classmethod
    def validate_jurisdiction(cls, v: Optional[str]) -> Optional[str]:
        """Validate jurisdiction filter."""
        if v is not None:
            valid_jurisdictions = {"US", "EPO", "PCT"}
            v = v.upper()
            if v not in valid_jurisdictions:
                raise ValueError(f"jurisdiction must be one of {valid_jurisdictions}")
        return v


# Review Input Models


class ReviewClaimsInput(BaseModel):  # type: ignore[misc]
    """Input validation for patent claims review."""

    claims_text: constr(min_length=10, max_length=50000) = Field(  # type: ignore[valid-type]
        ..., description="Patent claims text to analyze"
    )

    @field_validator("claims_text")
    @classmethod
    def validate_claims_format(cls, v: str) -> str:
        """Basic validation of claims text."""
        v = v.strip()
        if not v:
            raise ValueError("claims_text cannot be empty or whitespace")
        return v


class ReviewSpecificationInput(BaseModel):  # type: ignore[misc]
    """Input validation for specification review."""

    claims_text: constr(min_length=10, max_length=50000) = Field(  # type: ignore[valid-type]
        ..., description="Patent claims text"
    )
    specification: constr(min_length=100, max_length=200000) = Field(  # type: ignore[valid-type]
        ..., description="Patent specification text"
    )


class CheckFormalitiesInput(BaseModel):  # type: ignore[misc]
    """Input validation for formalities checking."""

    title: Optional[constr(max_length=500)] = Field(  # type: ignore[valid-type]
        default=None, description="Patent application title"
    )
    abstract: Optional[constr(max_length=5000)] = Field(  # type: ignore[valid-type]
        default=None, description="Patent abstract"
    )
    specification: Optional[constr(max_length=200000)] = Field(  # type: ignore[valid-type]
        default=None, description="Patent specification"
    )
    drawings_present: bool = Field(default=False, description="Whether drawings are included")


class CheckPackageInput(BaseModel):  # type: ignore[misc]
    """Input validation for package consistency checking."""

    directory: constr(min_length=1, max_length=4096) = Field(  # type: ignore[valid-type]
        ..., description="Path to the assembled filing-package directory"
    )


# Diagram Input Models


class RenderDiagramInput(BaseModel):  # type: ignore[misc]
    """Input validation for diagram rendering."""

    dot_code: constr(min_length=10, max_length=50000) = Field(  # type: ignore[valid-type]
        ..., description="Graphviz DOT code for the diagram"
    )
    filename: constr(min_length=1, max_length=100) = Field(  # type: ignore[valid-type]
        default="diagram", description="Output filename (without extension)"
    )
    output_format: Literal["svg", "png", "pdf"] = Field(
        default="svg", description="Output format"
    )
    engine: Literal["dot", "neato", "fdp", "circo", "twopi"] = Field(
        default="dot", description="Graphviz layout engine"
    )

    @field_validator("filename")
    @classmethod
    def sanitize_filename(cls, v: str) -> str:
        """Sanitize filename to prevent path traversal."""
        dangerous_chars = ["/", "\\", "..", "<", ">", ":", '"', "|", "?", "*"]
        for char in dangerous_chars:
            v = v.replace(char, "_")
        return v.strip()


class CreateBlockDiagramInput(BaseModel):  # type: ignore[misc]
    """Input validation for block diagram creation."""

    blocks: list = Field(..., description="List of block definitions")
    connections: list = Field(..., description="List of connections between blocks")
    filename: constr(min_length=1, max_length=100) = Field(  # type: ignore[valid-type]
        default="block_diagram", description="Output filename"
    )
    output_format: Literal["svg", "png", "pdf"] = Field(
        default="svg", description="Output format"
    )


def validate_input(model_class: type[BaseModel], **kwargs):
    """
    Validate input using a Pydantic model.

    Args:
        model_class: Pydantic model class to use for validation
        **kwargs: Input parameters to validate

    Returns:
        Validated model instance

    Raises:
        ValueError: If validation fails with details
    """
    try:
        return model_class(**kwargs)
    except ValidationError as e:
        error_messages = [
            f"{' -> '.join(str(loc) for loc in error['loc'])}: {error['msg']}"
            for error in e.errors()
        ]
        raise ValueError("Input validation failed:\n" + "\n".join(error_messages)) from e
