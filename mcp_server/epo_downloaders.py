#!/usr/bin/env python3
"""
EPO and WIPO/PCT Legal Document Downloaders

Downloads legal documents for the European Patent Office (EPO) and
Patent Cooperation Treaty (PCT) systems for indexing in the RAG pipeline.
"""

import re
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from logging_config import get_logger

    logger = get_logger()
    LOGGING_AVAILABLE = True
except ImportError:
    logger = None
    LOGGING_AVAILABLE = False


def _log_info(msg: str, **kwargs):
    if LOGGING_AVAILABLE and logger:
        logger.info(msg, extra=kwargs)
    else:
        print(f"[INFO] {msg}", file=sys.stderr)


def _log_error(msg: str, **kwargs):
    if LOGGING_AVAILABLE and logger:
        logger.error(msg, extra=kwargs)
    else:
        print(f"[ERROR] {msg}", file=sys.stderr)


# =============================================================================
# Download URLs (verified March 2026)
# =============================================================================

# EPC: 17th edition (Jul 2020) from WIPO Lex - includes Convention + Implementing Regulations
EPC_DOWNLOAD_URL = "https://www.wipo.int/wipolex/en/text/312166"

# PCT Treaty text (in force April 1, 2002)
PCT_TREATY_URL = "https://www.wipo.int/documents/d/pct-system/docs-en-texts-pct.pdf"

# PCT Regulations (in force January 1, 2026)
PCT_RULES_URL = "https://www.wipo.int/documents/d/pct-system/docs-en-texts-pct-regs.pdf"

# PCT International Search and Preliminary Examination Guidelines
PCT_GUIDELINES_URL = "https://www.wipo.int/documents/d/pct-system/docs-en-texts-ispe.pdf"

# EPO Guidelines for Examination - HTML base URL (no single PDF available since 2023)
EPO_GUIDELINES_BASE_URL = "https://www.epo.org/en/legal/guidelines-epc"

# EPO Guidelines draft PDF (may be available during consultation periods)
EPO_GUIDELINES_DRAFT_PDF_PATTERN = "https://link.epo.org/web/legal/guidelines-epc/en-epc-guidelines-draft-{year}.pdf"

# File names for stored documents
EPC_FILE = "epc_convention.pdf"
PCT_TREATY_FILE = "pct_treaty.pdf"
PCT_RULES_FILE = "pct_regulations.pdf"
PCT_GUIDELINES_FILE = "pct_guidelines.pdf"
EPO_GUIDELINES_FILE = "epo_guidelines.txt"


def _download_file(url: str, dest_path: Path, description: str, timeout: int = 120) -> bool:
    """Download a file with progress reporting.

    Args:
        url: URL to download from
        dest_path: Destination file path
        description: Human-readable description for logging
        timeout: Download timeout in seconds

    Returns:
        True if download succeeded
    """
    if not REQUESTS_AVAILABLE:
        _log_error(f"Cannot download {description}: requests library not available")
        return False

    if dest_path.exists():
        _log_info(f"{description} already exists at {dest_path}")
        return True

    _log_info(f"Downloading {description}...", url=url)

    try:
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()

        # Ensure parent directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        downloaded = 0

        with dest_path.open("wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)

        size_mb = downloaded / (1024 * 1024)
        _log_info(f"Downloaded {description} ({size_mb:.1f} MB)")
        return True

    except Exception as e:
        _log_error(f"Failed to download {description}: {e}")
        # Clean up partial download
        if dest_path.exists():
            dest_path.unlink()
        return False


def download_epc(dest_dir: Path) -> bool:
    """Download European Patent Convention (includes Convention text + Implementing Regulations).

    The 17th edition PDF from WIPO Lex contains both the EPC articles and
    the Implementing Regulations in a single document. The extractor in
    mpep_search.py splits them by detecting the section boundary.

    Note: This is the 17th edition (Jul 2020) and may not reflect the latest
    Administrative Council amendments. The EPO HTML version is more current.
    """
    return _download_file(
        url=EPC_DOWNLOAD_URL,
        dest_path=dest_dir / EPC_FILE,
        description="European Patent Convention (17th ed.)",
    )


def download_pct_treaty(dest_dir: Path) -> bool:
    """Download PCT Treaty text."""
    return _download_file(
        url=PCT_TREATY_URL,
        dest_path=dest_dir / PCT_TREATY_FILE,
        description="PCT Treaty",
    )


def download_pct_rules(dest_dir: Path) -> bool:
    """Download PCT Regulations."""
    return _download_file(
        url=PCT_RULES_URL,
        dest_path=dest_dir / PCT_RULES_FILE,
        description="PCT Regulations",
    )


def download_pct_guidelines(dest_dir: Path) -> bool:
    """Download PCT International Search and Preliminary Examination Guidelines."""
    return _download_file(
        url=PCT_GUIDELINES_URL,
        dest_path=dest_dir / PCT_GUIDELINES_FILE,
        description="PCT Search & Examination Guidelines",
    )


def scrape_epo_guidelines(dest_dir: Path, year: Optional[int] = None) -> bool:
    """Download or scrape EPO Guidelines for Examination.

    Since March 2023, the EPO publishes the Guidelines as HTML only.
    This function first attempts to download a PDF (available during
    consultation periods), then falls back to scraping the HTML version.

    Args:
        dest_dir: Directory to save the guidelines
        year: Year for draft PDF attempt (defaults to current year)

    Returns:
        True if guidelines were obtained successfully
    """
    dest_path = dest_dir / EPO_GUIDELINES_FILE

    if dest_path.exists():
        _log_info(f"EPO Guidelines already exist at {dest_path}")
        return True

    if not REQUESTS_AVAILABLE:
        _log_error("Cannot download EPO Guidelines: requests library not available")
        return False

    # Try draft PDF first (available during annual consultation)
    if year is None:
        import datetime

        year = datetime.datetime.now().year

    pdf_url = EPO_GUIDELINES_DRAFT_PDF_PATTERN.format(year=year)
    pdf_dest = dest_dir / f"epo_guidelines_{year}.pdf"

    _log_info(f"Attempting EPO Guidelines PDF download for {year}...")
    if _download_file(pdf_url, pdf_dest, f"EPO Guidelines {year} PDF"):
        # If PDF downloaded, we'll use it directly (extractor handles PDF)
        # Create a symlink or copy reference
        _log_info(f"EPO Guidelines PDF obtained for {year}")
        return True

    # Fall back to HTML scraping
    _log_info("PDF not available, scraping HTML version...")
    return _scrape_epo_guidelines_html(dest_path)


def _scrape_epo_guidelines_html(dest_path: Path) -> bool:
    """Scrape EPO Guidelines from HTML pages.

    The Guidelines are organized into 8 parts (A-H), each with multiple
    chapters and sections. We scrape the table of contents to discover
    all pages, then download and extract text from each.

    Args:
        dest_path: Path to save consolidated text file

    Returns:
        True if scraping succeeded
    """
    parts = {
        "A": "Formalities examination",
        "B": "Search",
        "C": "Substantive examination (procedure)",
        "D": "Opposition and limitation/revocation",
        "E": "General procedural matters",
        "F": "The European patent application",
        "G": "Patentability",
        "H": "Amendments and corrections",
    }

    all_text = []
    all_text.append("EPO GUIDELINES FOR EXAMINATION IN THE EUROPEAN PATENT OFFICE")
    all_text.append("=" * 70)
    all_text.append("")

    session = requests.Session()
    session.headers.update({"User-Agent": "Claude-Patent-Creator/1.0 (patent research tool)"})

    total_sections = 0

    for part_letter, part_title in parts.items():
        _log_info(f"Scraping Part {part_letter}: {part_title}...")
        all_text.append(f"\n{'=' * 70}")
        all_text.append(f"PART {part_letter} - {part_title.upper()}")
        all_text.append(f"{'=' * 70}\n")

        # Try to get the part's main page
        part_url = f"{EPO_GUIDELINES_BASE_URL}/2024/part-{part_letter.lower()}"

        try:
            response = session.get(part_url, timeout=30)

            if response.status_code != 200:
                _log_info(f"Could not fetch Part {part_letter} (status {response.status_code}), skipping")
                continue

            # Extract text content (simple approach - strip HTML tags)
            text = _extract_text_from_html(response.text)
            if text:
                all_text.append(text)
                total_sections += 1

            # Be polite to the server
            time.sleep(1)

        except Exception as e:
            _log_error(f"Error scraping Part {part_letter}: {e}")
            continue

    if total_sections == 0:
        _log_error("No EPO Guidelines content could be scraped")
        return False

    # Write consolidated text
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text("\n".join(all_text), encoding="utf-8")

    total_chars = sum(len(t) for t in all_text)
    _log_info(
        f"EPO Guidelines scraped: {total_sections} parts, {total_chars:,} characters",
        sections=total_sections,
        characters=total_chars,
    )
    return True


def _extract_text_from_html(html: str) -> str:
    """Extract readable text from HTML, preserving section structure.

    Args:
        html: Raw HTML content

    Returns:
        Extracted plain text
    """
    # Remove script and style elements
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)

    # Convert headings to text with markers
    html = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n\n## \1\n", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n\n### \1\n", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n\n#### \1\n", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<h[4-6][^>]*>(.*?)</h[4-6]>", r"\n\1\n", html, flags=re.DOTALL | re.IGNORECASE)

    # Convert paragraphs and line breaks
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<p[^>]*>", "\n\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</p>", "", html, flags=re.IGNORECASE)

    # Convert list items
    html = re.sub(r"<li[^>]*>", "\n- ", html, flags=re.IGNORECASE)

    # Remove all remaining HTML tags
    html = re.sub(r"<[^>]+>", "", html)

    # Decode HTML entities
    html = html.replace("&amp;", "&")
    html = html.replace("&lt;", "<")
    html = html.replace("&gt;", ">")
    html = html.replace("&quot;", '"')
    html = html.replace("&#39;", "'")
    html = html.replace("&nbsp;", " ")

    # Clean up whitespace
    lines = []
    for line in html.split("\n"):
        line = line.strip()
        if line:
            lines.append(line)

    return "\n".join(lines)


def download_all_epo_documents(dest_dir: Path) -> dict[str, bool]:
    """Download all EPO-related legal documents.

    Args:
        dest_dir: Directory to save documents

    Returns:
        Dict mapping document name to download success
    """
    return {
        "epc": download_epc(dest_dir),
        "epo_guidelines": scrape_epo_guidelines(dest_dir),
    }


def download_all_pct_documents(dest_dir: Path) -> dict[str, bool]:
    """Download all PCT-related legal documents.

    Args:
        dest_dir: Directory to save documents

    Returns:
        Dict mapping document name to download success
    """
    return {
        "pct_treaty": download_pct_treaty(dest_dir),
        "pct_rules": download_pct_rules(dest_dir),
        "pct_guidelines": download_pct_guidelines(dest_dir),
    }


def check_epo_pct_sources(dest_dir: Path) -> dict[str, bool]:
    """Check which EPO/PCT source documents are available.

    Args:
        dest_dir: Directory to check

    Returns:
        Dict mapping document name to availability
    """
    return {
        "epc": (dest_dir / EPC_FILE).exists(),
        "epo_guidelines": (dest_dir / EPO_GUIDELINES_FILE).exists(),
        "pct_treaty": (dest_dir / PCT_TREATY_FILE).exists(),
        "pct_rules": (dest_dir / PCT_RULES_FILE).exists(),
        "pct_guidelines": (dest_dir / PCT_GUIDELINES_FILE).exists(),
    }
