#!/usr/bin/env python3
"""
Fast MCP entry point for Claude Patent Creator.

Registers all 23 MCP tools immediately with a lazy proxy for MPEPIndex,
then starts accepting connections in <1 second. Heavy model/index loading
(SentenceTransformer, CrossEncoder, FAISS, BM25) is deferred to the first
tool invocation that actually needs the index.

This avoids the ~6s startup of server.py's main() which eagerly loads
ML models, builds indexes, and runs health checks before calling mcp.run().
"""

import os
import sys
from pathlib import Path

# Ensure mcp_server dir is on path for sibling imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env if available (same as server.py)
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path, override=True)
except ImportError:
    pass


# ---------------------------------------------------------------------------
# LazyMPEPIndex — transparent proxy that defers heavy initialization
# ---------------------------------------------------------------------------

class LazyMPEPIndex:
    """Proxy that constructs and initializes MPEPIndex on first attribute access.

    Tool registration functions capture this proxy as a closure variable but
    never access attributes during registration — only when a tool is actually
    invoked. At that point, __getattr__ triggers the real MPEPIndex construction
    (which loads SentenceTransformer, CrossEncoder, FAISS index, BM25 index).
    """

    def __getattr__(self, name):
        # First real access — load the heavy index
        instance = self._load()
        return getattr(instance, name)

    def _load(self):
        """Construct MPEPIndex, build index, and replace self transparently."""
        import time

        print("LazyMPEPIndex: Loading MPEP index (first use)...", file=sys.stderr)
        start = time.time()

        from mpep_search import MPEPIndex

        use_hyde = os.environ.get("PATENT_MPEP_USE_HYDE", "false").lower() == "true"
        instance = MPEPIndex(use_hyde=use_hyde)
        instance.build_index(force_rebuild=False)

        elapsed = time.time() - start
        print(f"LazyMPEPIndex: Ready in {elapsed:.1f}s", file=sys.stderr)

        # Replace proxy's class so future attribute access goes direct
        object.__setattr__(self, "__class__", instance.__class__)
        object.__setattr__(self, "__dict__", instance.__dict__)
        return self


# ---------------------------------------------------------------------------
# Fast MCP server setup — lightweight imports only
# ---------------------------------------------------------------------------

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("claude-patent-creator")

# Logging helpers (lightweight — no ML imports)
try:
    from logging_config import get_logger
    from monitoring import track_performance, log_operation_result

    logger = get_logger()
    BEST_PRACTICES_AVAILABLE = True
except ImportError:
    logger = None  # type: ignore[assignment]
    track_performance = None  # type: ignore[assignment]
    log_operation_result = None  # type: ignore[assignment]
    BEST_PRACTICES_AVAILABLE = False

# Validation models (lightweight — just pydantic)
try:
    from validation import (
        SearchMPEPInput,
        SearchBigQueryInput,
        SearchUSPTOInput,
        GetPatentInput,
        CPCSearchInput,
        ReviewClaimsInput,
        ReviewSpecificationInput,
        CheckFormalitiesInput,
        RenderDiagramInput,
        validate_input,
        PYDANTIC_AVAILABLE,
    )
except ImportError:
    validate_input = None  # type: ignore[assignment]
    SearchMPEPInput = None  # type: ignore[assignment]
    SearchBigQueryInput = None  # type: ignore[assignment]
    SearchUSPTOInput = None  # type: ignore[assignment]
    GetPatentInput = None  # type: ignore[assignment]
    CPCSearchInput = None  # type: ignore[assignment]
    ReviewClaimsInput = None  # type: ignore[assignment]
    ReviewSpecificationInput = None  # type: ignore[assignment]
    CheckFormalitiesInput = None  # type: ignore[assignment]
    RenderDiagramInput = None  # type: ignore[assignment]
    PYDANTIC_AVAILABLE = False

# Analyzer classes (lightweight — no ML at import time)
try:
    from claims_analyzer import ClaimsAnalyzer
    from formalities_checker import FormalitiesChecker
    from specification_analyzer import SpecificationAnalyzer
except ImportError:
    ClaimsAnalyzer = None  # type: ignore[assignment]
    FormalitiesChecker = None  # type: ignore[assignment]
    SpecificationAnalyzer = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def _log_info(message, **kwargs):
    if logger:
        logger.info(message, extra=kwargs)
    else:
        print(message, file=sys.stderr)


def _log_warning(message, **kwargs):
    if logger:
        logger.warning(message, extra=kwargs)
    else:
        print(f"WARNING: {message}", file=sys.stderr)


def _log_error(message, exc_info=False, **kwargs):
    if logger:
        logger.error(message, extra=kwargs, exc_info=exc_info)
    else:
        print(f"ERROR: {message}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Register all tools — proxy is captured by closure, not accessed yet
# ---------------------------------------------------------------------------

mpep_index = LazyMPEPIndex()
patent_corpus_index = None  # Not used in current deployment

from tools.mpep_tools import register_mpep_tools  # noqa: E402
from tools.analyzer_tools import register_analyzer_tools  # noqa: E402
from tools.uspto_search_tools import register_uspto_tools  # noqa: E402
from tools.bigquery_tools import register_bigquery_tools  # noqa: E402
from tools.prior_art_tools import register_prior_art_tools  # noqa: E402
from tools.diagram_tools import register_diagram_tools  # noqa: E402
from tools.system_tools import register_system_tools  # noqa: E402

register_mpep_tools(
    mcp=mcp,
    mpep_index=mpep_index,
    log_info=_log_info,
    log_error=_log_error,
    validate_input=validate_input,
    SearchMPEPInput=SearchMPEPInput,
    track_performance=track_performance,
    log_operation_result=log_operation_result,
    PYDANTIC_AVAILABLE=PYDANTIC_AVAILABLE,
    BEST_PRACTICES_AVAILABLE=BEST_PRACTICES_AVAILABLE,
)

register_analyzer_tools(
    mcp=mcp,
    mpep_index=mpep_index,
    ClaimsAnalyzer=ClaimsAnalyzer,
    SpecificationAnalyzer=SpecificationAnalyzer,
    FormalitiesChecker=FormalitiesChecker,
    log_info=_log_info,
    log_warning=_log_warning,
    log_error=_log_error,
    validate_input=validate_input,
    ReviewClaimsInput=ReviewClaimsInput,
    ReviewSpecificationInput=ReviewSpecificationInput,
    CheckFormalitiesInput=CheckFormalitiesInput,
    track_performance=track_performance,
    log_operation_result=log_operation_result,
    PYDANTIC_AVAILABLE=PYDANTIC_AVAILABLE,
    BEST_PRACTICES_AVAILABLE=BEST_PRACTICES_AVAILABLE,
)

register_uspto_tools(
    mcp=mcp,
    log_info=_log_info,
    log_error=_log_error,
    validate_input=validate_input,
    SearchUSPTOInput=SearchUSPTOInput,
    GetPatentInput=GetPatentInput,
    track_performance=track_performance,
    PYDANTIC_AVAILABLE=PYDANTIC_AVAILABLE,
    BEST_PRACTICES_AVAILABLE=BEST_PRACTICES_AVAILABLE,
)

register_bigquery_tools(
    mcp=mcp,
    log_info=_log_info,
    log_error=_log_error,
    log_warning=_log_warning,
    validate_input=validate_input,
    SearchBigQueryInput=SearchBigQueryInput,
    GetPatentInput=GetPatentInput,
    CPCSearchInput=CPCSearchInput,
    track_performance=track_performance,
    PYDANTIC_AVAILABLE=PYDANTIC_AVAILABLE,
    BEST_PRACTICES_AVAILABLE=BEST_PRACTICES_AVAILABLE,
)

register_prior_art_tools(
    mcp=mcp,
    patent_corpus_index=patent_corpus_index,
    log_info=_log_info,
    log_error=_log_error,
    log_warning=_log_warning,
    track_performance=track_performance,
    BEST_PRACTICES_AVAILABLE=BEST_PRACTICES_AVAILABLE,
)

register_diagram_tools(
    mcp=mcp,
    log_info=_log_info,
    log_error=_log_error,
    log_warning=_log_warning,
    validate_input=validate_input,
    RenderDiagramInput=RenderDiagramInput,
    track_performance=track_performance,
    PYDANTIC_AVAILABLE=PYDANTIC_AVAILABLE,
    BEST_PRACTICES_AVAILABLE=BEST_PRACTICES_AVAILABLE,
)

register_system_tools(
    mcp=mcp,
    mpep_index=mpep_index,
    patent_corpus_index=patent_corpus_index,
    log_info=_log_info,
    log_error=_log_error,
    BEST_PRACTICES_AVAILABLE=BEST_PRACTICES_AVAILABLE,
)


# ---------------------------------------------------------------------------
# Start server immediately — no argparse, no health checks, no model loading
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
