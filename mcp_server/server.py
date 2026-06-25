#!/usr/bin/env python3
"""
MPEP RAG MCP Server
Provides intelligent retrieval from the Manual of Patent Examining Procedure

This is the main entry point for the MCP server. Tool definitions are organized
in the tools/ subdirectory for better maintainability.
"""

import os
import platform
import site
import sys
import zipfile
from pathlib import Path
from typing import Any

# macOS Apple Silicon: prevent FAISS OpenMP segfault (must precede torch/faiss imports)
# See: https://github.com/RobThePCGuy/Claude-Patent-Creator/issues/1
if platform.system() == "Darwin":
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# Load environment variables from .env file FIRST
try:
    from dotenv import load_dotenv

    # Load from mcp_server/.env file
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path, override=True)
except ImportError:
    pass  # dotenv not required

# CRITICAL: Disable user site-packages BEFORE importing third-party packages
site.ENABLE_USER_SITE = False
user_site = site.getusersitepackages()
if user_site in sys.path:
    sys.path.remove(user_site)

# FastMCP for building MCP servers
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("Error: mcp package not found. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

from logging_config import get_logger
from monitoring import log_operation_result, track_performance
from validation import (
    CheckFormalitiesInput,
    CPCSearchInput,
    FamilySearchInput,
    GetPatentInput,
    IPCSearchInput,
    RenderDiagramInput,
    ReviewClaimsInput,
    ReviewSpecificationInput,
    SearchBigQueryInput,
    SearchMPEPInput,
    SearchPatentLawInput,
    SearchUSPTOInput,
    validate_input,
)

# Import health check system
try:
    from health_check import SystemHealthChecker
except ImportError:
    SystemHealthChecker = None

# Import automated patent analyzers
try:
    from claims_analyzer import ClaimsAnalyzer
    from formalities_checker import FormalitiesChecker
    from specification_analyzer import SpecificationAnalyzer
except ImportError:
    ClaimsAnalyzer = None
    FormalitiesChecker = None
    SpecificationAnalyzer = None

# Local modules (imported after the site-packages/env setup above)
from downloaders import FileDownloader
from mpep_search import MPEPIndex

# Initialize MCP server
mcp = FastMCP("claude-patent-creator")

# Initialize logger
logger = get_logger()

# Global variables
MPEP_DIR = Path(__file__).parent.parent / "pdfs"
INDEX_DIR = Path(__file__).parent / "index"
mpep_index: Any = None

# Ensure directories exist
MPEP_DIR.mkdir(parents=True, exist_ok=True)
INDEX_DIR.mkdir(parents=True, exist_ok=True)

# USPTO download URLs
MPEP_DOWNLOAD_URL = "https://www.uspto.gov/web/offices/pac/mpep/e9r-01-2024.zip"
USC_35_DOWNLOAD_URL = "https://www.uspto.gov/web/offices/pac/mpep/consolidated_laws.pdf"
CFR_37_DOWNLOAD_URL = "https://www.uspto.gov/web/offices/pac/mpep/consolidated_rules.pdf"
SUBSEQUENT_PUBS_URL = "https://www.uspto.gov/web/offices/pac/mpep/subsequent-publications.pdf"
USC_35_FILE = "consolidated_laws.pdf"
CFR_37_FILE = "consolidated_rules.pdf"
SUBSEQUENT_PUBS_FILE = "subsequent_publications.pdf"


# ============================================================================
# LAZY LOADING PROXY
# ============================================================================


class LazyMPEPIndex:
    """Proxy that defers MPEPIndex initialization until first attribute access.

    Tool registration captures this proxy by closure but never touches its
    attributes until a tool is actually invoked, at which point __getattr__
    builds the real MPEPIndex. The double-checked lock guards against
    concurrent first-uses both triggering an index build.
    """

    def __init__(self, use_hyde: bool = True):
        import threading

        # __dict__ writes here bypass __getattr__ during init.
        self.__dict__["_instance"] = None
        self.__dict__["_use_hyde"] = use_hyde
        self.__dict__["_load_lock"] = threading.Lock()

    def _load(self):
        import time

        instance = self.__dict__["_instance"]
        if instance is not None:
            return instance

        with self.__dict__["_load_lock"]:
            instance = self.__dict__["_instance"]
            if instance is not None:
                return instance

            _log_info("LazyMPEPIndex: Loading MPEP index (first use)...")
            start = time.time()
            instance = MPEPIndex(use_hyde=self.__dict__["_use_hyde"])
            instance.build_index(force_rebuild=False)
            elapsed = time.time() - start
            _log_info(f"LazyMPEPIndex: Ready in {elapsed:.1f}s")
            self.__dict__["_instance"] = instance
            return instance

    def __getattr__(self, name):
        return getattr(self._load(), name)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _log_info(message: str, **kwargs):
    """Log info message with fallback to stderr."""
    if logger:
        logger.info(message, extra=kwargs)
    else:
        print(message, file=sys.stderr)


def _log_warning(message: str, **kwargs):
    """Log warning message with fallback to stderr."""
    if logger:
        logger.warning(message, extra=kwargs)
    else:
        print(f"WARNING: {message}", file=sys.stderr)


def _log_error(message: str, exc_info: bool = False, **kwargs):
    """Log error message with fallback to stderr."""
    if logger:
        logger.error(message, extra=kwargs, exc_info=exc_info)
    else:
        print(f"ERROR: {message}", file=sys.stderr)


def _log_debug(message: str, **kwargs):
    """Log debug message with fallback to stderr."""
    if logger:
        logger.debug(message, extra=kwargs)


def download_mpep_pdfs(url: str = MPEP_DOWNLOAD_URL, dest_dir: Path = MPEP_DIR) -> bool:
    """Download MPEP PDFs from USPTO website"""
    zip_path = dest_dir / "mpep-pdfs.zip"
    manual_instructions = (
        "1. Go to https://www.uspto.gov/web/offices/pac/mpep/index.html\n"
        "2. Download MPEP PDF files (mpep-0100.pdf through mpep-2900.pdf)\n"
        f"3. Place them in: {dest_dir.absolute()}"
    )
    return FileDownloader.download_with_progress(
        url=url,
        dest_path=zip_path,
        file_description="MPEP PDFs",
        timeout_seconds=300,
        use_mb=True,
        manual_instructions=manual_instructions,
    )


def extract_mpep_pdfs(dest_dir: Path = MPEP_DIR) -> bool:
    """Extract MPEP PDFs from downloaded zip file"""
    zip_path = dest_dir / "mpep-pdfs.zip"
    if not zip_path.exists():
        print(f"[X] Zip file not found: {zip_path}", file=sys.stderr)
        return False

    print(f"\nExtracting MPEP PDFs to {dest_dir.absolute()}", file=sys.stderr)
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            pdf_files = [f for f in zip_ref.namelist() if f.endswith(".pdf")]
            for i, file in enumerate(pdf_files, 1):
                zip_ref.extract(file, dest_dir)
                print(f"\rExtracting: {i}/{len(pdf_files)} files", end="", file=sys.stderr)
            print(f"\n[OK] Extracted {len(pdf_files)} PDF files", file=sys.stderr)
        zip_path.unlink()
        return True
    except Exception as e:
        print(f"\n[X] Extraction failed: {e}", file=sys.stderr)
        return False


def check_mpep_pdfs(dest_dir: Path = MPEP_DIR) -> int:
    """Check how many MPEP PDFs are available"""
    return len(list(dest_dir.glob("mpep-*.pdf")))


def download_35_usc(dest_dir: Path = MPEP_DIR) -> bool:
    """Download 35 USC Consolidated Patent Laws PDF"""
    return FileDownloader.download_with_progress(
        url=USC_35_DOWNLOAD_URL,
        dest_path=dest_dir / USC_35_FILE,
        file_description="35 USC Consolidated Patent Laws",
        timeout_seconds=120,
        use_mb=False,
    )


def download_37_cfr(dest_dir: Path = MPEP_DIR) -> bool:
    """Download 37 CFR Consolidated Patent Rules PDF"""
    return FileDownloader.download_with_progress(
        url=CFR_37_DOWNLOAD_URL,
        dest_path=dest_dir / CFR_37_FILE,
        file_description="37 CFR Consolidated Patent Rules",
        timeout_seconds=120,
        use_mb=False,
    )


def download_subsequent_publications(dest_dir: Path = MPEP_DIR) -> bool:
    """Download Subsequent Publications PDF"""
    return FileDownloader.download_with_progress(
        url=SUBSEQUENT_PUBS_URL,
        dest_path=dest_dir / SUBSEQUENT_PUBS_FILE,
        file_description="Subsequent Publications",
        timeout_seconds=120,
        use_mb=False,
    )


def check_all_sources(dest_dir: Path = MPEP_DIR) -> dict[str, bool]:
    """Check which source documents are available"""
    from epo_downloaders import (
        EPC_FILE,
        EPO_GUIDELINES_FILE,
        PCT_GUIDELINES_FILE,
        PCT_RULES_FILE,
        PCT_TREATY_FILE,
    )

    us_sources = {
        "mpep": check_mpep_pdfs(dest_dir) > 0,
        "35_usc": (dest_dir / USC_35_FILE).exists(),
        "37_cfr": (dest_dir / CFR_37_FILE).exists(),
        "subsequent_pubs": (dest_dir / SUBSEQUENT_PUBS_FILE).exists(),
    }
    epo_pct_sources = {
        "epc": (dest_dir / EPC_FILE).exists(),
        "epo_guidelines": (dest_dir / EPO_GUIDELINES_FILE).exists(),
        "pct_treaty": (dest_dir / PCT_TREATY_FILE).exists(),
        "pct_rules": (dest_dir / PCT_RULES_FILE).exists(),
        "pct_guidelines": (dest_dir / PCT_GUIDELINES_FILE).exists(),
    }
    return {**us_sources, **epo_pct_sources}


# ============================================================================
# TOOL REGISTRATION
# ============================================================================

# Import tool registration functions
from tools.analyzer_tools import register_analyzer_tools  # noqa: E402
from tools.bigquery_tools import register_bigquery_tools  # noqa: E402
from tools.diagram_tools import register_diagram_tools  # noqa: E402
from tools.epo_analyzer_tools import register_epo_analyzer_tools  # noqa: E402
from tools.epo_search_tools import register_epo_tools  # noqa: E402
from tools.mpep_tools import register_mpep_tools  # noqa: E402
from tools.patent_law_tools import register_patent_law_tools  # noqa: E402
from tools.system_tools import register_system_tools  # noqa: E402
from tools.uspto_search_tools import register_uspto_tools  # noqa: E402


def _register_all_tools():
    """Register all MCP tools with the current mpep_index (eager or lazy)."""
    register_mpep_tools(
        mcp=mcp,
        mpep_index=mpep_index,
        log_info=_log_info,
        log_error=_log_error,
        validate_input=validate_input,
        SearchMPEPInput=SearchMPEPInput,
        track_performance=track_performance,
        log_operation_result=log_operation_result,
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
    )

    # EPO/PCT analyzers
    try:
        from epo_claims_analyzer import EPOClaimsAnalyzer
        from epo_formalities_checker import EPOFormalitiesChecker
        from epo_specification_analyzer import EPOSpecificationAnalyzer
        from pct_formalities_checker import PCTFormalitiesChecker

        register_epo_analyzer_tools(
            mcp=mcp,
            mpep_index=mpep_index,
            EPOClaimsAnalyzer=EPOClaimsAnalyzer,
            EPOSpecificationAnalyzer=EPOSpecificationAnalyzer,
            EPOFormalitiesChecker=EPOFormalitiesChecker,
            PCTFormalitiesChecker=PCTFormalitiesChecker,
            log_info=_log_info,
            log_warning=_log_warning,
            log_error=_log_error,
            validate_input=validate_input,
            ReviewClaimsInput=ReviewClaimsInput,
            ReviewSpecificationInput=ReviewSpecificationInput,
            CheckFormalitiesInput=CheckFormalitiesInput,
            track_performance=track_performance,
            log_operation_result=log_operation_result,
        )
    except ImportError as e:
        _log_warning(f"EPO/PCT analyzer tools not available: {e}")

    register_uspto_tools(
        mcp=mcp,
        log_info=_log_info,
        log_error=_log_error,
        validate_input=validate_input,
        SearchUSPTOInput=SearchUSPTOInput,
        GetPatentInput=GetPatentInput,
        track_performance=track_performance,
    )

    register_epo_tools(
        mcp=mcp,
        log_info=_log_info,
        log_error=_log_error,
        validate_input=validate_input,
        track_performance=track_performance,
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
        IPCSearchInput=IPCSearchInput,
        FamilySearchInput=FamilySearchInput,
    )

    register_diagram_tools(
        mcp=mcp,
        log_info=_log_info,
        log_error=_log_error,
        log_warning=_log_warning,
        validate_input=validate_input,
        RenderDiagramInput=RenderDiagramInput,
        track_performance=track_performance,
    )

    register_patent_law_tools(
        mcp=mcp,
        mpep_index=mpep_index,
        log_info=_log_info,
        log_error=_log_error,
        validate_input=validate_input,
        SearchPatentLawInput=SearchPatentLawInput,
        track_performance=track_performance,
    )

    register_system_tools(
        mcp=mcp,
        mpep_index=mpep_index,
        log_info=_log_info,
        log_error=_log_error,
    )


# ============================================================================
# CLI ARGUMENT PARSING AND HANDLERS
# ============================================================================


def _parse_args():
    """Parse command line arguments"""
    import argparse

    parser = argparse.ArgumentParser(description="MPEP RAG MCP Server")
    parser.add_argument("--rebuild-index", action="store_true", help="Force rebuild of the index")
    parser.add_argument(
        "--download-mpep", action="store_true", help="Download MPEP PDFs from USPTO"
    )
    parser.add_argument("--download-all", action="store_true", help="Download all sources")
    parser.add_argument("--download-statutes", action="store_true", help="Download 35 USC")
    parser.add_argument("--download-regulations", action="store_true", help="Download 37 CFR")
    parser.add_argument(
        "--download-updates", action="store_true", help="Download Subsequent Publications"
    )
    parser.add_argument(
        "--download-epo", action="store_true", help="Download EPO sources (EPC + EPO Guidelines)"
    )
    parser.add_argument(
        "--download-pct", action="store_true", help="Download PCT sources (Treaty + Rules + Guidelines)"
    )
    parser.add_argument(
        "--mpep-url", type=str, default=MPEP_DOWNLOAD_URL, help="Custom MPEP download URL"
    )
    parser.add_argument("--no-hyde", action="store_true", help="Disable HyDE query expansion")
    return parser.parse_args()


def _handle_mpep_download(mpep_url):
    """Handle MPEP PDF download"""
    pdf_count = check_mpep_pdfs()
    if pdf_count > 0:
        response = input(f"\n{pdf_count} MPEP PDFs already exist. Download anyway? (y/N): ")
        if response.lower() != "y":
            print("Skipping download", file=sys.stderr)
            pdf_count = check_mpep_pdfs()
            print(f"\n[OK] Found {pdf_count} MPEP PDF files", file=sys.stderr)
            print("\nReady to build index. Run with --rebuild-index to continue.", file=sys.stderr)
            sys.exit(0)
    if download_mpep_pdfs(mpep_url):
        extract_mpep_pdfs()
    pdf_count = check_mpep_pdfs()
    print(f"\n[OK] Found {pdf_count} MPEP PDF files", file=sys.stderr)
    if pdf_count == 0:
        print("\n[X] No MPEP PDFs found. Cannot build index.", file=sys.stderr)
        sys.exit(1)
    print("\nReady to build index. Run with --rebuild-index to continue.", file=sys.stderr)
    sys.exit(0)


def _handle_additional_downloads(args):
    """Handle downloads for 35 USC, 37 CFR, Subsequent Publications, EPO, and PCT"""
    sources_status = check_all_sources()
    downloads_performed = []

    # US sources — skip download if file already present
    if args.download_all or args.download_statutes:
        if sources_status["35_usc"]:
            print(f"\n[OK] 35 USC already exists at {MPEP_DIR / USC_35_FILE}", file=sys.stderr)
        elif download_35_usc():
            downloads_performed.append("35 USC")

    if args.download_all or args.download_regulations:
        if sources_status["37_cfr"]:
            print(f"\n[OK] 37 CFR already exists at {MPEP_DIR / CFR_37_FILE}", file=sys.stderr)
        elif download_37_cfr():
            downloads_performed.append("37 CFR")

    if args.download_all or args.download_updates:
        if sources_status["subsequent_pubs"]:
            print(
                f"\n[OK] Subsequent Publications already exists at {MPEP_DIR / SUBSEQUENT_PUBS_FILE}",
                file=sys.stderr,
            )
        elif download_subsequent_publications():
            downloads_performed.append("Subsequent Publications")

    # EPO sources (epo_downloaders skips existing files internally)
    if args.download_all or args.download_epo:
        from epo_downloaders import check_epo_pct_sources, download_all_epo_documents

        epo_status = check_epo_pct_sources(MPEP_DIR)
        if epo_status.get("epc") and epo_status.get("epo_guidelines"):
            print("\n[OK] EPO sources already present", file=sys.stderr)
        else:
            print("\nDownloading EPO sources...", file=sys.stderr)
            epo_results = download_all_epo_documents(MPEP_DIR)
            for name, success in epo_results.items():
                if success:
                    downloads_performed.append(f"EPO:{name}")

    # PCT sources (epo_downloaders skips existing files internally)
    if args.download_all or args.download_pct:
        from epo_downloaders import check_epo_pct_sources as _check_pct
        from epo_downloaders import download_all_pct_documents

        pct_status = _check_pct(MPEP_DIR)
        if pct_status.get("pct_treaty") and pct_status.get("pct_rules"):
            print("\n[OK] PCT sources already present", file=sys.stderr)
        else:
            print("\nDownloading PCT sources...", file=sys.stderr)
            pct_results = download_all_pct_documents(MPEP_DIR)
            for name, success in pct_results.items():
                if success:
                    downloads_performed.append(f"PCT:{name}")

    if downloads_performed:
        print(f"\n[OK] Successfully downloaded: {', '.join(downloads_performed)}", file=sys.stderr)
        print(
            "\nNote: These sources are not yet indexed. Run with --rebuild-index to include them.",
            file=sys.stderr,
        )
    else:
        print("\n[OK] All requested sources already present", file=sys.stderr)

    # Refresh status after downloads
    sources_status = check_all_sources()

    print("\nCurrent source status:", file=sys.stderr)
    print("  --- US Sources ---", file=sys.stderr)
    print(f"  MPEP PDFs: {'[OK]' if sources_status['mpep'] else '[X]'}", file=sys.stderr)
    print(f"  35 USC:    {'[OK]' if sources_status['35_usc'] else '[X]'}", file=sys.stderr)
    print(f"  37 CFR:    {'[OK]' if sources_status['37_cfr'] else '[X]'}", file=sys.stderr)
    print(f"  Updates:   {'[OK]' if sources_status['subsequent_pubs'] else '[X]'}", file=sys.stderr)
    print("  --- EPO Sources ---", file=sys.stderr)
    print(f"  EPC:       {'[OK]' if sources_status.get('epc') else '[X]'}", file=sys.stderr)
    print(f"  EPO Guide: {'[OK]' if sources_status.get('epo_guidelines') else '[X]'}", file=sys.stderr)
    print("  --- PCT Sources ---", file=sys.stderr)
    print(f"  PCT Treaty:{'[OK]' if sources_status.get('pct_treaty') else '[X]'}", file=sys.stderr)
    print(f"  PCT Rules: {'[OK]' if sources_status.get('pct_rules') else '[X]'}", file=sys.stderr)
    print(f"  PCT Guide: {'[OK]' if sources_status.get('pct_guidelines') else '[X]'}", file=sys.stderr)
    sys.exit(0)


def _check_prerequisites(rebuild_index):
    """Check that prerequisites are met before starting server"""
    pdf_count = check_mpep_pdfs()
    index_exists = (INDEX_DIR / "mpep_index.faiss").exists() and (
        INDEX_DIR / "mpep_metadata.json"
    ).exists()

    if not index_exists and pdf_count == 0:
        print("\n[X] No MPEP PDFs and no existing index found.", file=sys.stderr)
        print("\nTo get started:", file=sys.stderr)
        print("  1. python mcp_server/server.py --download-mpep", file=sys.stderr)
        print("  2. python mcp_server/server.py --rebuild-index", file=sys.stderr)
        sys.exit(1)

    if pdf_count == 0 and rebuild_index:
        print("\n[X] No MPEP PDFs found.", file=sys.stderr)
        print("\nOptions:", file=sys.stderr)
        print("1. Run with --download-mpep to download automatically", file=sys.stderr)
        print("2. Manually download PDFs and place in project root", file=sys.stderr)
        sys.exit(1)


def _run_health_checks():
    """Run pre-flight health checks and display warnings"""
    if not SystemHealthChecker:
        return

    print("\nRunning pre-flight health checks...", file=sys.stderr)
    checker = SystemHealthChecker()
    health_status = checker.check_all_dependencies(verbose=False)

    warnings = []
    if not health_status["uspto_api"].get("available", False):
        warnings.append("USPTO API not configured - live patent search disabled")
    if health_status["gpu_status"].get("status") != "available":
        warnings.append(
            f"GPU not available: {health_status['gpu_status'].get('details', 'Using CPU mode')}"
        )

    if warnings:
        print("\n[WARNING] Warnings:", file=sys.stderr)
        for warning in warnings:
            print(f"  - {warning}", file=sys.stderr)
        print("\nServer will start with limited functionality.", file=sys.stderr)
        print("Run 'patent-creator status --verbose' for details.\n", file=sys.stderr)
    else:
        print("[OK] All systems operational\n", file=sys.stderr)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


def main():
    """Main entry point"""
    args = _parse_args()

    # Handle download requests
    if args.download_mpep:
        _handle_mpep_download(args.mpep_url)

    if (
        args.download_all
        or args.download_statutes
        or args.download_regulations
        or args.download_updates
        or args.download_epo
        or args.download_pct
    ):
        _handle_additional_downloads(args)

    # Check prerequisites
    _check_prerequisites(args.rebuild_index)

    # Initialize MPEP index
    global mpep_index
    use_hyde = not args.no_hyde

    if args.rebuild_index:
        # Eager loading for index rebuild
        _log_info("Initializing MPEP index (eager)...", use_hyde=use_hyde)
        mpep_index = MPEPIndex(use_hyde=use_hyde)
        mpep_index.build_index(force_rebuild=True)
    else:
        # Lazy loading for normal MCP server startup (<1s connect time)
        _log_info("Initializing MPEP index (lazy — loads on first tool use)...", use_hyde=use_hyde)
        mpep_index = LazyMPEPIndex(use_hyde=use_hyde)

    # Register all MCP tools (proxy is captured by closure, not accessed yet)
    _register_all_tools()

    # Run health checks
    _run_health_checks()

    # Run the MCP server
    _log_info("Starting MCP server...")
    mcp.run()


if __name__ == "__main__":
    main()
