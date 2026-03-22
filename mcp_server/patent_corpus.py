#!/usr/bin/env python3
"""
Patent Corpus Management using PatentsView Data
Downloads and parses PatentsView TSV files for prior art search
"""

import csv
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# PatentsView S3 base URL
PATENTSVIEW_BASE_URL = "https://s3.amazonaws.com/data.patentsview.org/download/"

# Default storage locations
# __file__ is in mcp_server/, so parent is project root
PROJECT_ROOT = Path(__file__).parent.parent
MCP_SERVER_DIR = Path(__file__).parent
PATENT_CORPUS_DIR = MCP_SERVER_DIR / "patent_corpus"
PATENT_INDEX_DIR = MCP_SERVER_DIR / "patent_index"


@dataclass
class Patent:
    """Represents a patent from PatentsView data"""

    patent_id: str
    title: str
    abstract: str
    claims: List[str]
    description: str
    cpc_codes: List[str]
    filing_date: Optional[str]
    grant_date: Optional[str]
    inventors: List[str]
    assignee: Optional[str]

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "patent_id": self.patent_id,
            "title": self.title,
            "abstract": self.abstract,
            "claims": self.claims,
            "description": self.description,
            "cpc_codes": self.cpc_codes,
            "filing_date": self.filing_date,
            "grant_date": self.grant_date,
            "inventors": self.inventors,
            "assignee": self.assignee,
        }


def _safe_int(value: Any, default: int = 0) -> int:
    """Safely convert a value to int, returning default for empty/None/non-numeric values.

    TSV fields may contain empty strings, None, or non-numeric text, all of which
    would cause int() to raise ValueError or TypeError.
    """
    if value is None:
        return default
    s = str(value).strip()
    if not s:
        return default
    try:
        return int(s)
    except (ValueError, TypeError):
        return default


class PatentTSVParser:
    """Parse PatentsView TSV files"""

    def __init__(self, corpus_dir: Path = PATENT_CORPUS_DIR):
        self.corpus_dir = corpus_dir
        self.corpus_dir.mkdir(parents=True, exist_ok=True)

        # Cache for loaded data (to avoid re-reading large files)
        self._abstracts: Dict[str, str] = {}
        self._claims: Dict[str, List[str]] = {}
        self._descriptions: Dict[str, str] = {}
        self._inventors: Dict[str, List[str]] = {}
        self._assignees: Dict[str, str] = {}
        self._cpc_codes: Dict[str, List[str]] = {}
        self._applications: Dict[str, str] = {}

    def load_data_files(self, force_reload: bool = False):
        """
        Load all necessary TSV files into memory for fast lookup

        Args:
            force_reload: Force reload even if already loaded
        """
        if not force_reload and self._abstracts:
            print("Data files already loaded", file=sys.stderr)
            return

        print("Loading PatentsView data files...", file=sys.stderr)

        # Load abstracts
        abstracts_file = self.corpus_dir / "g_patent_abstract.tsv"
        if abstracts_file.exists():
            print("  Loading abstracts...", file=sys.stderr)
            self._abstracts = self._load_key_value_file(
                abstracts_file, key_col="patent_id", value_col="patent_abstract"
            )
            print(f"    Loaded {len(self._abstracts)} abstracts", file=sys.stderr)

        # Load claims
        claims_file = self.corpus_dir / "claim.tsv"
        if claims_file.exists():
            print("  Loading claims...", file=sys.stderr)
            self._claims = self._load_grouped_file(
                claims_file,
                key_col="patent_id",
                value_col="claim_text",
                sort_col="claim_sequence",
            )
            print(f"    Loaded claims for {len(self._claims)} patents", file=sys.stderr)

        # Load descriptions
        desc_file = self.corpus_dir / "detail_desc_text.tsv"
        if desc_file.exists():
            print("  Loading descriptions...", file=sys.stderr)
            self._descriptions = self._load_key_value_file(
                desc_file, key_col="patent_id", value_col="description_text"
            )
            print(f"    Loaded {len(self._descriptions)} descriptions", file=sys.stderr)

        # Load inventors
        inventors_file = self.corpus_dir / "g_inventor_not_disambiguated.tsv"
        if inventors_file.exists():
            print("  Loading inventors...", file=sys.stderr)
            self._inventors = self._load_grouped_names(
                inventors_file,
                key_col="patent_id",
                first_col="raw_inventor_name_first",
                last_col="raw_inventor_name_last",
                sort_col="inventor_sequence",
            )
            print(
                f"    Loaded inventors for {len(self._inventors)} patents",
                file=sys.stderr,
            )

        # Load assignees
        assignees_file = self.corpus_dir / "g_assignee_not_disambiguated.tsv"
        if assignees_file.exists():
            print("  Loading assignees...", file=sys.stderr)
            self._assignees = self._load_first_assignee(assignees_file)
            print(f"    Loaded {len(self._assignees)} assignees", file=sys.stderr)

        # Load CPC codes
        cpc_file = self.corpus_dir / "g_cpc_current.tsv"
        if cpc_file.exists():
            print("  Loading CPC codes...", file=sys.stderr)
            self._cpc_codes = self._load_cpc_codes(cpc_file)
            print(
                f"    Loaded CPC codes for {len(self._cpc_codes)} patents",
                file=sys.stderr,
            )

        # Load application data (for filing dates)
        app_file = self.corpus_dir / "g_application.tsv"
        if app_file.exists():
            print("  Loading application data...", file=sys.stderr)
            self._applications = self._load_key_value_file(
                app_file, key_col="patent_id", value_col="filing_date"
            )
            print(f"    Loaded {len(self._applications)} filing dates", file=sys.stderr)

        print("All data files loaded", file=sys.stderr)

    def _load_key_value_file(self, file_path: Path, key_col: str, value_col: str) -> Dict[str, str]:
        """Load a TSV file into a key-value dictionary"""
        result = {}
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
                for row in reader:
                    key = row.get(key_col, "").strip()
                    value = row.get(value_col, "").strip()
                    if key and value:
                        result[key] = value
        except Exception as e:
            print(f"Error loading {file_path}: {e}", file=sys.stderr)
        return result

    def _load_grouped_file(
        self,
        file_path: Path,
        key_col: str,
        value_col: str,
        sort_col: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        """Load a TSV file with multiple rows per key"""
        result = {}
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_MINIMAL)

                # Collect all rows
                rows = []
                for row in reader:
                    key = row.get(key_col, "").strip()
                    value = row.get(value_col, "").strip()
                    sort_key = _safe_int(row.get(sort_col), 0) if sort_col else 0
                    if key and value:
                        rows.append((key, value, sort_key))

                # Sort if needed
                if sort_col:
                    rows.sort(key=lambda x: (x[0], x[2]))

                # Group by key
                for key, value, _ in rows:
                    if key not in result:
                        result[key] = []
                    result[key].append(value)

        except Exception as e:
            print(f"Error loading {file_path}: {e}", file=sys.stderr)
        return result

    def _load_grouped_names(
        self,
        file_path: Path,
        key_col: str,
        first_col: str,
        last_col: str,
        sort_col: Optional[str] = None,
    ) -> Dict[str, List[str]]:
        """Load names from TSV file (first + last)"""
        result = {}
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_MINIMAL)

                rows = []
                for row in reader:
                    key = row.get(key_col, "").strip()
                    first = row.get(first_col, "").strip()
                    last = row.get(last_col, "").strip()
                    sort_key = _safe_int(row.get(sort_col), 0) if sort_col else 0

                    if key and (first or last):
                        name = f"{first} {last}".strip()
                        rows.append((key, name, sort_key))

                # Sort if needed
                if sort_col:
                    rows.sort(key=lambda x: (x[0], x[2]))

                # Group by key
                for key, name, _ in rows:
                    if key not in result:
                        result[key] = []
                    result[key].append(name)

        except Exception as e:
            print(f"Error loading {file_path}: {e}", file=sys.stderr)
        return result

    def _load_first_assignee(self, file_path: Path) -> Dict[str, str]:
        """Load first assignee for each patent"""
        result = {}
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_MINIMAL)

                for row in reader:
                    key = row.get("patent_id", "").strip()
                    seq = _safe_int(row.get("assignee_sequence"), 999)

                    # Only take first assignee (sequence 0)
                    if key and seq == 0:
                        # Try organization first, then individual name
                        assignee = row.get("raw_assignee_organization", "").strip()
                        if not assignee:
                            first = row.get("raw_assignee_individual_name_first", "").strip()
                            last = row.get("raw_assignee_individual_name_last", "").strip()
                            assignee = f"{first} {last}".strip()

                        if assignee:
                            result[key] = assignee

        except Exception as e:
            print(f"Error loading {file_path}: {e}", file=sys.stderr)
        return result

    def _load_cpc_codes(self, file_path: Path) -> Dict[str, List[str]]:
        """Load CPC codes"""
        result = {}
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_MINIMAL)

                for row in reader:
                    key = row.get("patent_id", "").strip()
                    section = row.get("cpc_section", "").strip()
                    cpc_class = row.get("cpc_class", "").strip()
                    subclass = row.get("cpc_subclass", "").strip()

                    if key and section:
                        # Build CPC code
                        code = section
                        if cpc_class:
                            code = cpc_class  # cpc_class already includes section
                        if subclass:
                            code = subclass  # subclass already includes section+class

                        if key not in result:
                            result[key] = []
                        if code not in result[key]:
                            result[key].append(code)

        except Exception as e:
            print(f"Error loading {file_path}: {e}", file=sys.stderr)
        return result

    def parse_main_file(self, max_patents: Optional[int] = None) -> List[Patent]:
        """
        Parse main patent file (g_patent.tsv) and join with other data

        Args:
            max_patents: Maximum number of patents to parse (None = all)

        Returns:
            List of Patent objects
        """
        patents = []
        main_file = self.corpus_dir / "g_patent.tsv"

        if not main_file.exists():
            print(f"Main patent file not found: {main_file}", file=sys.stderr)
            return patents

        # Load all supporting data first
        self.load_data_files()

        print(f"Parsing main patent file: {main_file}", file=sys.stderr)

        try:
            with open(main_file, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_MINIMAL)

                for i, row in enumerate(reader):
                    if max_patents and i >= max_patents:
                        break

                    patent_id = row.get("patent_id", "").strip()
                    if not patent_id:
                        continue

                    # Get data from main file
                    title = row.get("patent_title", "").strip()
                    grant_date = row.get("patent_date", "").strip()

                    # Get data from supporting files
                    abstract = self._abstracts.get(patent_id, "")
                    claims = self._claims.get(patent_id, [])
                    description = self._descriptions.get(patent_id, "")
                    inventors = self._inventors.get(patent_id, [])
                    assignee = self._assignees.get(patent_id)
                    cpc_codes = self._cpc_codes.get(patent_id, [])
                    filing_date = self._applications.get(patent_id)

                    patent = Patent(
                        patent_id=patent_id,
                        title=title,
                        abstract=abstract,
                        claims=claims,
                        description=description,
                        cpc_codes=cpc_codes,
                        filing_date=filing_date,
                        grant_date=grant_date,
                        inventors=inventors,
                        assignee=assignee,
                    )

                    patents.append(patent)

                    if (i + 1) % 10000 == 0:
                        print(f"  Parsed {i + 1} patents...", file=sys.stderr)

        except Exception as e:
            print(f"Error parsing main file: {e}", file=sys.stderr)

        print(f"Parsed {len(patents)} patents total", file=sys.stderr)
        return patents


class PatentCorpusDownloader:
    """Download PatentsView patent corpus from S3"""

    # Files to download (in order)
    REQUIRED_FILES = [
        "g_patent.tsv.zip",  # Main patent data (217 MB)
        "g_patent_abstract.tsv.zip",  # Abstracts (1.6 GB)
        "g_application.tsv.zip",  # Filing dates (67 MB)
        "g_cpc_current.tsv.zip",  # CPC codes (466 MB)
        "g_inventor_not_disambiguated.tsv.zip",  # Inventors (962 MB)
        "g_assignee_not_disambiguated.tsv.zip",  # Assignees (465 MB)
    ]

    # Optional large text files (downloaded separately)
    # NOTE: Claims and descriptions are split by year at PatentsView
    # and would total ~70GB. Omitting for now - users can manually
    # download specific years from:
    # - https://patentsview.org/download/claims
    # - https://patentsview.org/download/detail_desc_text
    OPTIONAL_FILES = []

    def __init__(self, corpus_dir: Path = PATENT_CORPUS_DIR):
        self.corpus_dir = corpus_dir
        self.corpus_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "PatentsView-Patent-Reviewer/1.0.0 (Educational/Research)"}
        )

    def download_file(self, filename: str) -> Optional[Path]:
        """
        Download a specific TSV file from PatentsView S3

        Args:
            filename: Name of the file to download (e.g., "g_patent.tsv.zip")

        Returns:
            Path to downloaded file, or None if failed
        """
        output_path = self.corpus_dir / filename.replace(".zip", "")
        zip_path = self.corpus_dir / filename

        # Skip if already extracted
        if output_path.exists():
            print(f"Already have {filename} (extracted)", file=sys.stderr)
            return output_path

        # Download if needed
        if not zip_path.exists():
            url = f"{PATENTSVIEW_BASE_URL}{filename}"

            try:
                print(f"Downloading {filename}...", file=sys.stderr)
                response = self.session.get(url, stream=True, timeout=300)
                response.raise_for_status()

                # Get file size for progress
                total_size = int(response.headers.get("content-length", 0))

                # Download with progress
                downloaded = 0
                with open(zip_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                percent = (downloaded / total_size) * 100
                                print(
                                    f"\r  Progress: {percent:.1f}%",
                                    end="",
                                    file=sys.stderr,
                                )

                print(
                    f"\r  Downloaded {filename} ({downloaded / 1024 / 1024:.1f} MB)",
                    file=sys.stderr,
                )

            except Exception as e:
                print(f"Failed to download {filename}: {e}", file=sys.stderr)
                if zip_path.exists():
                    zip_path.unlink()
                return None

        # Extract ZIP (with retry for Windows file locking)
        import time

        max_retries = 3

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    # Wait a bit for Windows to release the file lock
                    time.sleep(1)
                    print(f"  Retry {attempt + 1}/{max_retries}...", file=sys.stderr)

                print(f"Extracting {filename}...", file=sys.stderr)
                with zipfile.ZipFile(zip_path, "r") as zf:
                    # Extract first .tsv file
                    for name in zf.namelist():
                        if name.endswith(".tsv"):
                            print(f"  Extracting {name}...", file=sys.stderr)
                            zf.extract(name, self.corpus_dir)
                            extracted_path = self.corpus_dir / name

                            # Rename to expected name
                            if extracted_path != output_path:
                                extracted_path.rename(output_path)

                # Clean up ZIP after successful extraction (outside context manager)
                try:
                    time.sleep(0.5)  # Give Windows a moment
                    zip_path.unlink()
                except Exception:
                    # On Windows, file might still be locked - that's okay, just warn
                    print(
                        "  Note: Could not delete ZIP (it's safe to manually delete later)",
                        file=sys.stderr,
                    )

                print(f"  Extracted to {output_path}", file=sys.stderr)
                return output_path

            except PermissionError:
                if attempt == max_retries - 1:
                    # Last attempt failed - but file is downloaded, so warn and continue
                    print(
                        "  Warning: ZIP downloaded but extraction delayed (Windows file lock)",
                        file=sys.stderr,
                    )
                    print(f"  You can manually extract: {zip_path}", file=sys.stderr)
                    return None
                # Otherwise, retry
                continue

            except Exception as e:
                print(f"Failed to extract {filename}: {e}", file=sys.stderr)
                return None

    def download_corpus(
        self, include_optional: bool = True, max_size_gb: Optional[float] = None
    ) -> bool:
        """
        Download complete PatentsView corpus

        Args:
            include_optional: Download optional large text files (claims, descriptions)
            max_size_gb: Maximum storage to use (None = unlimited)

        Returns:
            True if successful
        """
        print("\nDownloading PatentsView patent corpus...", file=sys.stderr)
        print(f"Target directory: {self.corpus_dir}", file=sys.stderr)

        total_size_bytes = 0
        max_size_bytes = max_size_gb * 1024 * 1024 * 1024 if max_size_gb else float("inf")

        # Download required files
        print("\nDownloading required files...", file=sys.stderr)
        for filename in self.REQUIRED_FILES:
            if total_size_bytes >= max_size_bytes:
                print(f"\nReached size limit of {max_size_gb:.1f} GB", file=sys.stderr)
                break

            path = self.download_file(filename)
            if path:
                total_size_bytes += path.stat().st_size

        # Download optional files
        if include_optional:
            print("\nDownloading optional large text files...", file=sys.stderr)
            for filename in self.OPTIONAL_FILES:
                if total_size_bytes >= max_size_bytes:
                    print(f"\nReached size limit of {max_size_gb:.1f} GB", file=sys.stderr)
                    break

                path = self.download_file(filename)
                if path:
                    total_size_bytes += path.stat().st_size

        print(
            f"\nDownload complete: {total_size_bytes / 1024 / 1024 / 1024:.2f} GB",
            file=sys.stderr,
        )
        return True

    def get_downloaded_files(self) -> List[Path]:
        """Get list of downloaded TSV files"""
        files = []
        if self.corpus_dir.exists():
            for tsv_file in sorted(self.corpus_dir.glob("*.tsv")):
                files.append(tsv_file)
        return files


def check_patent_corpus_status() -> Dict[str, Any]:
    """Check status of downloaded patent corpus"""
    downloader = PatentCorpusDownloader()
    files = downloader.get_downloaded_files()

    total_size = sum(f.stat().st_size for f in files) if files else 0

    return {
        "files_downloaded": len(files),
        "total_size_gb": total_size / 1024 / 1024 / 1024,
        "data_source": "PatentsView (https://patentsview.org)",
        "corpus_dir": PATENT_CORPUS_DIR,
    }
