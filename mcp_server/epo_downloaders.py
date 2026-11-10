#!/usr/bin/env python3
"""
EPO and WIPO/PCT Legal Document Downloaders

Downloads legal documents for the European Patent Office (EPO) and
Patent Cooperation Treaty (PCT) systems for indexing in the RAG pipeline.
"""

import sys
from pathlib import Path
from typing import Optional

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from bs4 import BeautifulSoup

    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

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
# Direct PDF published on the EPO's own EPC legal-texts page — the old
# WIPO wipolex URL served an HTML page that got saved as epc_convention.pdf.
EPC_DOWNLOAD_URL = "https://link.epo.org/web/EPC_17th_edition_2020_en.pdf"

# PCT Treaty text (in force April 1, 2002)
PCT_TREATY_URL = "https://www.wipo.int/documents/d/pct-system/docs-en-texts-pct.pdf"

# PCT Regulations (in force January 1, 2026)
PCT_RULES_URL = "https://www.wipo.int/documents/d/pct-system/docs-en-texts-pct-regs.pdf"

# PCT International Search and Preliminary Examination Guidelines
PCT_GUIDELINES_URL = "https://www.wipo.int/documents/d/pct-system/docs-en-texts-ispe.pdf"

# Official published Guidelines, PDF and HTML (verified November 2026)
EPO_GUIDELINES_BASE_URL = "https://www.epo.org/en/legal/guidelines-epc"

# Published edition, not the consultation draft.
EPO_GUIDELINES_PDF_PATTERN = "https://link.epo.org/web/legal/guidelines-epc/en-epc-guidelines-{year}-hyperlinked.pdf"

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
        first_bytes = b""

        with dest_path.open("wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if len(first_bytes) < 5:
                    first_bytes += chunk[: 5 - len(first_bytes)]
                f.write(chunk)
                downloaded += len(chunk)

        # A .pdf destination must actually be a PDF — servers answer moved
        # or blocked documents with HTML error/landing pages, and saving one
        # as .pdf poisons the index build downstream.
        if dest_path.suffix.lower() == ".pdf" and not first_bytes.startswith(b"%PDF-"):
            _log_error(
                f"{description}: server returned non-PDF content "
                f"(starts with {first_bytes!r}); discarding"
            )
            dest_path.unlink()
            return False

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

    Download the published PDF, then fall back to the complete linked HTML
    edition. Incomplete HTML retrieval does not install a canonical corpus.

    Args:
        dest_dir: Directory to save the guidelines
        year: Published edition year (defaults to current year)

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

    # Try the published PDF first
    if year is None:
        import datetime

        year = datetime.datetime.now().year

    pdf_url = EPO_GUIDELINES_PDF_PATTERN.format(year=year)
    pdf_dest = dest_dir / f"epo_guidelines_{year}.pdf"

    _log_info(f"Attempting EPO Guidelines PDF download for {year}...")
    # The official link service can cache an HTML error under the PDF URL.
    # A stable edition query avoids that cached response; validate both attempts.
    for candidate in (pdf_url, f"{pdf_url}?v={year}"):
        if _download_file(candidate, pdf_dest, f"EPO Guidelines {year} PDF"):
            if _pdf_to_guidelines_text(pdf_dest, dest_path):
                _log_info(f"EPO Guidelines published PDF obtained and extracted for {year}")
                return True
            _log_error("Guidelines PDF text extraction failed; trying HTML scrape")
            break

    # Fall back to HTML scraping
    _log_info("PDF not available, scraping HTML version...")
    return _scrape_epo_guidelines_html(dest_path, year=year)


def _pdf_to_guidelines_text(pdf_path: Path, dest_path: Path) -> bool:
    """Extract the Guidelines PDF into the canonical text file."""
    try:
        import pymupdf as fitz  # PyMuPDF ("import fitz" warns on stdout)
    except ImportError:
        _log_error("PyMuPDF not available; cannot extract Guidelines PDF")
        return False
    try:
        doc = fitz.open(pdf_path)
        try:
            pages = [doc[p].get_text() for p in range(len(doc))]
        finally:
            doc.close()
        text = "\n".join(pages)
        if not text.strip():
            return False
        dest_path.write_text(text, encoding="utf-8")
        return True
    except Exception as e:
        _log_error(f"Failed to extract Guidelines PDF: {e}")
        return False


def _scrape_epo_guidelines_html(dest_path: Path, year: Optional[int] = None) -> bool:
    """Follow the official edition's contents tree, failing closed.

    Only the legal-content container is indexed, without deleted prior-edition
    text. Never install a partial crawl as the complete Guidelines source.
    """
    import datetime
    from concurrent.futures import ThreadPoolExecutor
    from urllib.parse import urldefrag, urljoin

    if not BS4_AVAILABLE or not REQUESTS_AVAILABLE:
        _log_error("requests and beautifulsoup4 are required for Guidelines HTML")
        return False
    year = year or datetime.datetime.now().year
    base = f"{EPO_GUIDELINES_BASE_URL}/{year}/"
    pending = {base + "index.html"}
    seen, pages, failures = set(), {}, []

    def fetch(url):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            content = soup.select_one(".epolegal-content")
            if content is None:
                raise ValueError("No Guidelines legal content (possibly an error page)")
            for deleted in content.select(".Del, del, script, style"):
                deleted.decompose()
            links = set()
            # The contents tree defines the corpus. Body cross-references can
            # point at deleted chapters (e.g. e_xiv.html in the 2026 edition).
            selector = ".bottom-list a[href]"
            if url == base + "index.html":
                selector += ", .epolegal-content a[href]"
            for a in soup.select(selector):
                target = urldefrag(urljoin(url, a["href"]))[0]
                if target.startswith(base) and target.endswith(".html"):
                    links.add(target)
            heading = soup.find("h1")
            title = heading.get_text(" ", strip=True) if heading else "Guidelines"
            text = _extract_text_from_html(str(content))
            if not text.strip():
                children = soup.select_one(".bottom-list a[href]")
                if children is None:
                    raise ValueError("Empty Guidelines legal content")
                text = "Contents page; substantive text is in linked sections."
            return url, f"### {title}\nSource: {url}\n{text}", links, None
        except Exception as exc:
            return url, "", set(), str(exc)

    with ThreadPoolExecutor(max_workers=4) as pool:
        while pending:
            batch = sorted(pending - seen)
            if not batch:
                break
            seen.update(batch)
            pending = set()
            for url, text, links, error in pool.map(fetch, batch):
                if error:
                    failures.append(url)
                    _log_error(f"Guidelines HTML failed: {url}: {error}")
                else:
                    pages[url] = text
                    pending.update(links - seen)
            _log_info(f"Guidelines HTML: {len(pages)} pages retrieved; "
                      f"{len(failures)} failed; {len(pending)} pending")
    required = {base + part + "_i.html" for part in "abcdefgh"}
    if failures or not required.issubset(pages) or len(pages) <= 9:
        _log_error(f"Guidelines HTML incomplete: {len(pages)}/{len(seen)} discovered pages. "
                   "Not installed; all Parts A-H and linked sections are required.")
        return False
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    header = (f"EPO GUIDELINES FOR EXAMINATION — {year}\n"
              f"Coverage: {len(pages)}/{len(seen)} discovered HTML pages; "
              "all contents-tree sections in this edition retrieved. Body cross-references and external legal texts "
              "were not downloaded; deleted prior-edition text excluded.\n")
    dest_path.write_text(header + "\n\n".join(pages[url] for url in sorted(pages)), encoding="utf-8")
    return True


def _extract_text_from_html(html: str) -> str:
    """Extract readable text from HTML, preserving section structure.

    Args:
        html: Raw HTML content

    Returns:
        Extracted plain text
    """
    if not BS4_AVAILABLE:
        raise ImportError("beautifulsoup4 is required for HTML text extraction")

    soup = BeautifulSoup(html, "lxml")

    # Drop script/style bodies entirely; a real parser also handles the
    # malformed closers (e.g. "</script >") that defeat regex filters.
    for tag in soup(["script", "style"]):
        tag.decompose()

    # Convert headings to text with markers
    for name, marker in (("h1", "\n\n## "), ("h2", "\n\n### "), ("h3", "\n\n#### ")):
        for tag in soup.find_all(name):
            tag.insert_before(marker)
            tag.insert_after("\n")
    for tag in soup.find_all(["h4", "h5", "h6"]):
        tag.insert_before("\n")
        tag.insert_after("\n")

    # Convert paragraphs, line breaks, and list items
    for tag in soup.find_all("br"):
        tag.replace_with("\n")
    for tag in soup.find_all("p"):
        tag.insert_before("\n\n")
    for tag in soup.find_all("li"):
        tag.insert_before("\n- ")

    # get_text() drops remaining tags and decodes entities

    # Clean up whitespace
    lines = []
    for line in soup.get_text().split("\n"):
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
        "epc": _source_present(dest_dir / EPC_FILE),
        "epo_guidelines": _source_present(dest_dir / EPO_GUIDELINES_FILE),
        "pct_treaty": _source_present(dest_dir / PCT_TREATY_FILE),
        "pct_rules": _source_present(dest_dir / PCT_RULES_FILE),
        "pct_guidelines": _source_present(dest_dir / PCT_GUIDELINES_FILE),
    }


def _source_present(path: Path) -> bool:
    """A source counts as present only if it is what it claims to be.

    The old EPC URL saved a WIPO HTML page as epc_convention.pdf; treating
    that artifact as present would block the corrected download forever.
    """
    if not path.exists():
        return False
    if path.suffix.lower() != ".pdf":
        return True
    try:
        with path.open("rb") as f:
            return f.read(5) == b"%PDF-"
    except OSError:
        return False
