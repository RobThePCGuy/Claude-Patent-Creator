#!/usr/bin/env python3
"""
MPEP Search Module - Standalone
Provides semantic search across MPEP, 35 USC, and 37 CFR documents
Extracted from server.py to work as a standalone library
"""

import json
import sys
from pathlib import Path
from typing import Any, Optional

# PDF processing
try:
    import fitz  # PyMuPDF

    PYMUPDF_AVAILABLE = True
except ImportError:
    print(
        "Warning: PyMuPDF not found. Install with: pip install PyMuPDF",
        file=sys.stderr,
    )
    PYMUPDF_AVAILABLE = False
    fitz = None

# Vector search capabilities
try:
    import faiss
    import numpy as np
    import torch
    from sentence_transformers import CrossEncoder, SentenceTransformer

    VECTOR_SEARCH_AVAILABLE = True
except ImportError:
    print(
        "Warning: Required packages not found. Install with: pip install sentence-transformers faiss-cpu numpy torch",
        file=sys.stderr,
    )
    VECTOR_SEARCH_AVAILABLE = False
    faiss = None
    np = None
    torch = None
    CrossEncoder = None
    SentenceTransformer = None

# BM25 for hybrid search
try:
    from rank_bm25 import BM25Okapi

    BM25_AVAILABLE = True
except ImportError:
    print(
        "Warning: rank-bm25 not found. Hybrid search disabled. Install with: pip install rank-bm25",
        file=sys.stderr,
    )
    BM25_AVAILABLE = False
    BM25Okapi = None

# Import device utilities
try:
    from utils.device import get_device
except ImportError:
    # Fallback: simple device detection
    def get_device() -> str:  # type: ignore[misc]
        """Detect device (GPU/CPU) with fallback"""
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"


# Import logging and monitoring with fallback
try:
    from logging_config import get_logger
    from monitoring import log_operation_result, track_performance

    logger = get_logger()
    LOGGING_AVAILABLE = True
except ImportError:
    logger = None
    track_performance = None
    log_operation_result = None
    LOGGING_AVAILABLE = False


# Global variables for the RAG system
MPEP_DIR = Path(__file__).parent.parent / "pdfs"
INDEX_DIR = Path(__file__).parent / "index"

# Ensure directories exist
MPEP_DIR.mkdir(parents=True, exist_ok=True)
INDEX_DIR.mkdir(parents=True, exist_ok=True)

# USPTO file constants
USC_35_FILE = "consolidated_laws.pdf"
CFR_37_FILE = "consolidated_rules.pdf"
SUBSEQUENT_PUBS_FILE = "subsequent_publications.pdf"


# Helper functions for logging (graceful fallback)
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


class MPEPIndex:
    """Manages indexing and retrieval of MPEP documents with advanced RAG techniques"""

    def __init__(self, use_hyde: bool = True):
        # Check dependencies
        if not VECTOR_SEARCH_AVAILABLE:
            raise ImportError(
                "Vector search packages not available. "
                "Install with: pip install sentence-transformers faiss-cpu numpy torch"
            )
        if not PYMUPDF_AVAILABLE:
            raise ImportError("PyMuPDF not available. Install with: pip install PyMuPDF")

        # Detect and use GPU if available
        self.device = get_device()

        _log_info("Loading embedding model (BGE-base)...", device=self.device)
        self.model = SentenceTransformer("BAAI/bge-base-en-v1.5", device=self.device)  # type: ignore[misc]

        _log_info("Loading reranker model...", device=self.device)
        self.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device=self.device)  # type: ignore[misc]

        # Initialize HyDE query expander
        self.use_hyde = use_hyde
        self.hyde_expander = None
        if use_hyde:
            try:
                from hyde import HyDEQueryExpander

                self.hyde_expander = HyDEQueryExpander(backend="auto")
                _log_info("HyDE query expansion enabled")
            except Exception as e:
                _log_warning(
                    f"HyDE initialization failed: {e}. Continuing without HyDE.", error=str(e)
                )
                self.use_hyde = False

        self.chunks = []
        self.metadata = []
        self.index = None
        self.bm25 = None
        self.index_file = INDEX_DIR / "mpep_index.faiss"
        self.metadata_file = INDEX_DIR / "mpep_metadata.json"
        self.bm25_file = INDEX_DIR / "mpep_bm25.json"

    def extract_text_from_pdf(self, pdf_path: Path) -> list[dict[str, Any]]:
        """Extract text from PDF with contextual metadata"""
        chunks = []
        doc = None
        try:
            doc = fitz.open(pdf_path)  # type: ignore[union-attr]
            section = self._extract_section_from_filename(pdf_path.name)

            for page_num, page in enumerate(doc):  # type: ignore[arg-type]
                text = page.get_text()
                if text.strip():
                    # Use common chunking helper
                    page_chunks = self._chunk_text_with_metadata(
                        text=text,
                        section_label=section,
                        base_metadata={
                            "source": "MPEP",
                            "file": pdf_path.name,
                            "page": page_num + 1,
                            "section": section,
                            "is_statute": False,
                            "is_regulation": False,
                            "is_update": False,
                        },
                    )
                    chunks.extend(page_chunks)
        except Exception as e:
            _log_error(f"Error processing {pdf_path}: {e}", exc_info=True, file_path=str(pdf_path))
        finally:
            if doc is not None:
                doc.close()
        return chunks

    def _extract_section_from_filename(self, filename: str) -> str:
        """Extract MPEP section number from filename"""
        # mpep-0100.pdf -> MPEP 100
        # mpep-2100.pdf -> MPEP 2100
        parts = filename.replace(".pdf", "").split("-")
        if len(parts) > 1:
            section = parts[1]
            if section.startswith("0") and len(section) == 4:
                section = section.lstrip("0") or "0"
            return f"MPEP {section}"
        return filename

    def _chunk_text_with_metadata(
        self,
        text: str,
        section_label: str,
        base_metadata: dict[str, Any],
        chunk_size: int = 500,
        overlap: int = 100,
        min_chunk_length: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Common helper to chunk text and attach metadata with cross-reference detection.

        Args:
            text: Raw text to chunk
            section_label: Label to prepend (e.g., "MPEP 100", "35 U.S.C. Section 101")
            base_metadata: Base metadata dict to include in all chunks
            chunk_size: Characters per chunk
            overlap: Overlapping characters between chunks
            min_chunk_length: Minimum chunk length to keep

        Returns:
            List of chunk dictionaries with text and metadata
        """
        import re

        chunks = []
        for i in range(0, len(text), chunk_size - overlap):
            chunk_text = text[i : i + chunk_size]
            if len(chunk_text.strip()) < min_chunk_length:
                continue

            # Prepend section context to chunk
            contextualized_text = f"[{section_label}] {chunk_text}"

            # Detect cross-references in chunk (US + EPO + PCT)
            has_mpep_ref = bool(re.search(r"MPEP\s*Section ?\s*\d+", chunk_text))
            has_usc_ref = bool(re.search(r"35 U\.?S\.?C\.?\s*Section ?\s*\d+", chunk_text))
            has_cfr_ref = bool(re.search(r"37 C\.?F\.?R\.?\s*Section ?\s*\d+", chunk_text))
            has_epc_ref = bool(re.search(r"Art(?:icle)?\.?\s*\d+\s*(?:\(\d+\))?\s*(?:EPC)?", chunk_text))
            has_pct_ref = bool(re.search(r"(?:PCT\s+)?Rule\s+\d+", chunk_text))
            has_epo_guideline_ref = bool(re.search(r"(?:Part\s+[A-H]|Guidelines?\s+[A-H])", chunk_text))

            # Merge base metadata with detected references
            chunk_metadata = {
                "text": contextualized_text,
                **base_metadata,
                "has_mpep_ref": has_mpep_ref,
                "has_usc_ref": has_usc_ref,
                "has_cfr_ref": has_cfr_ref,
                "has_epc_ref": has_epc_ref,
                "has_pct_ref": has_pct_ref,
                "has_epo_guideline_ref": has_epo_guideline_ref,
                "has_statute": has_usc_ref or has_epc_ref,
                "has_rule_ref": has_cfr_ref or has_pct_ref,
            }

            chunks.append(chunk_metadata)

        return chunks

    def extract_text_from_usc(self, pdf_path: Path) -> list[dict[str, Any]]:
        """Extract text from 35 USC PDF with statute section detection"""
        import re

        chunks = []
        doc = None
        try:
            doc = fitz.open(pdf_path)  # type: ignore[union-attr]
            current_section = "35 U.S.C."

            for page_num, page in enumerate(doc):  # type: ignore[arg-type]
                text = page.get_text()
                if not text.strip():
                    continue

                # Detect section headers: "Section  100", "Section  101", etc.
                section_matches = list(re.finditer(r"Section \s*(\d+)\.?\s+([^\n]{1,80})", text))

                # If we found sections on this page, process them
                if section_matches:
                    for match in section_matches:
                        section_num = match.group(1)
                        section_title = match.group(2).strip()
                        current_section = f"35 U.S.C. Section {section_num} - {section_title}"

                # Chunk the text using common helper
                page_chunks = self._chunk_text_with_metadata(
                    text=text,
                    section_label=current_section,
                    base_metadata={
                        "source": "35_USC",
                        "file": pdf_path.name,
                        "section": current_section,
                        "page": page_num + 1,
                        "has_statute": True,  # Override: USC is always statute
                        "is_statute": True,
                        "is_regulation": False,
                        "is_update": False,
                    },
                )
                chunks.extend(page_chunks)
        except Exception as e:
            _log_error(f"Error processing {pdf_path}: {e}", exc_info=True, file_path=str(pdf_path))
        finally:
            if doc is not None:
                doc.close()
        return chunks

    def extract_text_from_cfr(self, pdf_path: Path) -> list[dict[str, Any]]:
        """Extract text from 37 CFR PDF with rule section detection"""
        import re

        chunks = []
        doc = None
        try:
            doc = fitz.open(pdf_path)  # type: ignore[union-attr]
            current_rule = "37 C.F.R."
            current_part = "Part 1"

            for page_num, page in enumerate(doc):  # type: ignore[arg-type]
                text = page.get_text()
                if not text.strip():
                    continue

                # Detect part headers: "PART 1", "PART 5", etc.
                part_match = re.search(r"PART\s+(\d+)", text)
                if part_match:
                    current_part = f"Part {part_match.group(1)}"

                # Detect rule sections: "Section  1.1", "Section  1.16", etc.
                rule_matches = list(re.finditer(r"Section \s*(\d+\.\d+)\s+([^\n]{1,80})", text))

                if rule_matches:
                    for match in rule_matches:
                        rule_num = match.group(1)
                        rule_title = match.group(2).strip()
                        current_rule = f"37 C.F.R. Section {rule_num} - {rule_title}"

                # Chunk the text using common helper
                page_chunks = self._chunk_text_with_metadata(
                    text=text,
                    section_label=current_rule,
                    base_metadata={
                        "source": "37_CFR",
                        "file": pdf_path.name,
                        "part": current_part,
                        "section": current_rule,
                        "page": page_num + 1,
                        "is_statute": False,
                        "is_regulation": True,
                        "is_fee_schedule": "fee" in text.lower() and "$" in text,
                        "is_update": False,
                    },
                )
                chunks.extend(page_chunks)
        except Exception as e:
            _log_error(f"Error processing {pdf_path}: {e}", exc_info=True, file_path=str(pdf_path))
        finally:
            if doc is not None:
                doc.close()
        return chunks

    def extract_text_from_subsequent_pubs(self, pdf_path: Path) -> list[dict[str, Any]]:
        """Extract text from Subsequent Publications PDF with update tracking"""
        import re

        chunks = []
        doc = None
        try:
            doc = fitz.open(pdf_path)  # type: ignore[union-attr]
            current_doc_type = "Update"
            current_doc_title = "Subsequent Publication"
            fr_citation = None
            effective_date = None

            for page_num, page in enumerate(doc):  # type: ignore[arg-type]
                text = page.get_text()
                if not text.strip():
                    continue

                # Detect document type
                if re.search(r"Final\s+[Rr]ule", text):
                    current_doc_type = "Final Rule"
                elif re.search(r"Memorandum", text, re.IGNORECASE):
                    current_doc_type = "Memorandum"
                elif re.search(r"Official\s+Gazette", text, re.IGNORECASE):
                    current_doc_type = "OG Notice"

                # Extract Federal Register citation: "90 FR 3036"
                fr_match = re.search(r"(\d+)\s+FR\s+(\d+)", text)
                if fr_match:
                    fr_citation = f"{fr_match.group(1)} FR {fr_match.group(2)}"
                    current_doc_title = f"{current_doc_type} {fr_citation}"

                # Extract effective date
                date_match = re.search(r"effective\s+(\w+\s+\d+,\s+\d{4})", text, re.IGNORECASE)
                if date_match:
                    effective_date = date_match.group(1)

                # Detect affected MPEP sections
                mpep_sections_affected = list(
                    set(re.findall(r"MPEP\s*Section ?\s*(\d+(?:\.\d+)?)", text))
                )

                # Chunk the text using common helper
                page_chunks = self._chunk_text_with_metadata(
                    text=text,
                    section_label=current_doc_title,
                    base_metadata={
                        "source": "SUBSEQUENT",
                        "file": pdf_path.name,
                        "section": current_doc_title,
                        "doc_type": current_doc_type,
                        "fr_citation": fr_citation,
                        "effective_date": effective_date,
                        "mpep_sections_affected": mpep_sections_affected,
                        "page": page_num + 1,
                        "is_statute": False,
                        "is_regulation": False,
                        "is_update": True,
                        "supersedes_mpep": True,
                    },
                )
                chunks.extend(page_chunks)
        except Exception as e:
            _log_error(f"Error processing {pdf_path}: {e}", exc_info=True, file_path=str(pdf_path))
        finally:
            if doc is not None:
                doc.close()
        return chunks

    # ==========================================================================
    # EPO/WIPO Document Extractors
    # ==========================================================================

    def extract_text_from_epc(self, pdf_path: Path) -> list[dict[str, Any]]:
        """Extract text from European Patent Convention PDF.

        The EPC 17th edition PDF contains both the Convention articles and the
        Implementing Regulations. This method splits them by detecting the
        section boundary and produces chunks with source="EPC" for articles
        and source="EPC_RULES" for rules.
        """
        import re

        epc_chunks = []
        rules_chunks = []
        doc = None
        try:
            doc = fitz.open(pdf_path)  # type: ignore[union-attr]
            current_article = "EPC"
            in_rules_section = False

            for page_num, page in enumerate(doc):  # type: ignore[arg-type]
                text = page.get_text()
                if not text.strip():
                    continue

                # Detect transition to Implementing Regulations
                if re.search(r"IMPLEMENTING\s+REGULATIONS", text, re.IGNORECASE):
                    in_rules_section = True

                if in_rules_section:
                    # Detect rule numbers: "Rule 1", "Rule 42", etc.
                    rule_matches = list(re.finditer(r"Rule\s+(\d+)\s*\n\s*([^\n]{1,100})", text))
                    current_label = current_article

                    if rule_matches:
                        for match in rule_matches:
                            rule_num = match.group(1)
                            rule_title = match.group(2).strip()
                            current_label = f"Rule {rule_num} EPC - {rule_title}"

                    page_chunks = self._chunk_text_with_metadata(
                        text=text,
                        section_label=current_label,
                        base_metadata={
                            "source": "EPC_RULES",
                            "file": pdf_path.name,
                            "section": current_label,
                            "page": page_num + 1,
                            "is_statute": False,
                            "is_regulation": True,
                            "is_update": False,
                        },
                    )
                    rules_chunks.extend(page_chunks)
                else:
                    # Detect article numbers: "Article 52", "Article 84", etc.
                    art_matches = list(re.finditer(r"Article\s+(\d+)\s*\n\s*([^\n]{1,100})", text))

                    if art_matches:
                        for match in art_matches:
                            art_num = match.group(1)
                            art_title = match.group(2).strip()
                            current_article = f"Art. {art_num} EPC - {art_title}"

                    page_chunks = self._chunk_text_with_metadata(
                        text=text,
                        section_label=current_article,
                        base_metadata={
                            "source": "EPC",
                            "file": pdf_path.name,
                            "section": current_article,
                            "page": page_num + 1,
                            "is_statute": True,
                            "is_regulation": False,
                            "is_update": False,
                        },
                    )
                    epc_chunks.extend(page_chunks)

        except Exception as e:
            _log_error(f"Error processing EPC {pdf_path}: {e}", exc_info=True, file_path=str(pdf_path))
        finally:
            if doc is not None:
                doc.close()

        _log_info(
            f"Extracted {len(epc_chunks)} EPC article chunks and {len(rules_chunks)} EPC rules chunks",
            epc_chunks=len(epc_chunks),
            rules_chunks=len(rules_chunks),
        )
        return epc_chunks + rules_chunks

    def extract_text_from_epo_guidelines(self, text_path: Path) -> list[dict[str, Any]]:
        """Extract text from EPO Guidelines for Examination (text file from HTML scrape).

        The Guidelines are organized into 8 parts (A-H), each with chapters and
        sections. This method detects the Part/Chapter/Section structure.
        """
        import re

        chunks = []
        try:
            text = text_path.read_text(encoding="utf-8")
            if not text.strip():
                return chunks

            # Split by part headers
            current_part = "EPO Guidelines"
            current_section = "EPO Guidelines"

            # Process line by line, detecting headers
            lines = text.split("\n")
            buffer = []

            for line in lines:
                # Detect part headers: "PART A - FORMALITIES EXAMINATION"
                part_match = re.match(r"PART\s+([A-H])\s*[-–]\s*(.+)", line, re.IGNORECASE)
                if part_match:
                    # Flush buffer
                    if buffer:
                        buffer_text = "\n".join(buffer)
                        page_chunks = self._chunk_text_with_metadata(
                            text=buffer_text,
                            section_label=current_section,
                            base_metadata={
                                "source": "EPO_GUIDELINES",
                                "file": text_path.name,
                                "section": current_section,
                                "part": current_part,
                                "is_statute": False,
                                "is_regulation": False,
                                "is_update": False,
                            },
                        )
                        chunks.extend(page_chunks)
                        buffer = []

                    current_part = f"Part {part_match.group(1)}"
                    current_section = f"EPO Guidelines {current_part} - {part_match.group(2).strip()}"
                    continue

                # Detect chapter/section headers
                section_match = re.match(r"(?:###+|####)\s*(.+)", line)
                if section_match:
                    # Flush buffer
                    if buffer:
                        buffer_text = "\n".join(buffer)
                        page_chunks = self._chunk_text_with_metadata(
                            text=buffer_text,
                            section_label=current_section,
                            base_metadata={
                                "source": "EPO_GUIDELINES",
                                "file": text_path.name,
                                "section": current_section,
                                "part": current_part,
                                "is_statute": False,
                                "is_regulation": False,
                                "is_update": False,
                            },
                        )
                        chunks.extend(page_chunks)
                        buffer = []

                    current_section = f"EPO Guidelines {current_part} - {section_match.group(1).strip()}"
                    continue

                buffer.append(line)

            # Flush remaining buffer
            if buffer:
                buffer_text = "\n".join(buffer)
                page_chunks = self._chunk_text_with_metadata(
                    text=buffer_text,
                    section_label=current_section,
                    base_metadata={
                        "source": "EPO_GUIDELINES",
                        "file": text_path.name,
                        "section": current_section,
                        "part": current_part,
                        "is_statute": False,
                        "is_regulation": False,
                        "is_update": False,
                    },
                )
                chunks.extend(page_chunks)

        except Exception as e:
            _log_error(f"Error processing EPO Guidelines {text_path}: {e}", exc_info=True)

        _log_info(f"Extracted {len(chunks)} EPO Guidelines chunks", chunk_count=len(chunks))
        return chunks

    def extract_text_from_pct(self, pdf_path: Path) -> list[dict[str, Any]]:
        """Extract text from PCT Treaty PDF with article detection."""
        import re

        chunks = []
        doc = None
        try:
            doc = fitz.open(pdf_path)  # type: ignore[union-attr]
            current_article = "PCT"

            for page_num, page in enumerate(doc):  # type: ignore[arg-type]
                text = page.get_text()
                if not text.strip():
                    continue

                # Detect article headers: "Article 1", "Article 17", etc.
                art_matches = list(re.finditer(r"Article\s+(\d+)\s*\n\s*([^\n]{1,100})", text))

                if art_matches:
                    for match in art_matches:
                        art_num = match.group(1)
                        art_title = match.group(2).strip()
                        current_article = f"PCT Art. {art_num} - {art_title}"

                page_chunks = self._chunk_text_with_metadata(
                    text=text,
                    section_label=current_article,
                    base_metadata={
                        "source": "PCT",
                        "file": pdf_path.name,
                        "section": current_article,
                        "page": page_num + 1,
                        "is_statute": True,
                        "is_regulation": False,
                        "is_update": False,
                    },
                )
                chunks.extend(page_chunks)

        except Exception as e:
            _log_error(f"Error processing PCT {pdf_path}: {e}", exc_info=True, file_path=str(pdf_path))
        finally:
            if doc is not None:
                doc.close()

        _log_info(f"Extracted {len(chunks)} PCT Treaty chunks", chunk_count=len(chunks))
        return chunks

    def extract_text_from_pct_rules(self, pdf_path: Path) -> list[dict[str, Any]]:
        """Extract text from PCT Regulations PDF with rule detection."""
        import re

        chunks = []
        doc = None
        try:
            doc = fitz.open(pdf_path)  # type: ignore[union-attr]
            current_rule = "PCT Regulations"

            for page_num, page in enumerate(doc):  # type: ignore[arg-type]
                text = page.get_text()
                if not text.strip():
                    continue

                # Detect rule headers: "Rule 5", "Rule 11", etc.
                rule_matches = list(re.finditer(r"Rule\s+(\d+(?:\.\d+)?)\s*\n\s*([^\n]{1,100})", text))

                if rule_matches:
                    for match in rule_matches:
                        rule_num = match.group(1)
                        rule_title = match.group(2).strip()
                        current_rule = f"PCT Rule {rule_num} - {rule_title}"

                page_chunks = self._chunk_text_with_metadata(
                    text=text,
                    section_label=current_rule,
                    base_metadata={
                        "source": "PCT_RULES",
                        "file": pdf_path.name,
                        "section": current_rule,
                        "page": page_num + 1,
                        "is_statute": False,
                        "is_regulation": True,
                        "is_update": False,
                    },
                )
                chunks.extend(page_chunks)

        except Exception as e:
            _log_error(f"Error processing PCT Rules {pdf_path}: {e}", exc_info=True, file_path=str(pdf_path))
        finally:
            if doc is not None:
                doc.close()

        _log_info(f"Extracted {len(chunks)} PCT Rules chunks", chunk_count=len(chunks))
        return chunks

    def _offer_pdf_cleanup(self):
        """Ask user if they want to delete PDF files after successful indexing"""

        # Find all PDFs in MPEP_DIR
        pdf_files = list(MPEP_DIR.glob("*.pdf"))

        if not pdf_files:
            return

        # Calculate total size
        total_size_mb = sum(f.stat().st_size for f in pdf_files) / (1024 * 1024)

        print(f"\n{'='*60}", file=sys.stderr)
        print("PDF Cleanup Option", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)
        print(
            f"Found {len(pdf_files)} PDF files ({total_size_mb:.1f} MB)",
            file=sys.stderr,
        )
        print(f"Location: {MPEP_DIR}", file=sys.stderr)
        print("\nThe index has been successfully built from these PDFs.", file=sys.stderr)
        print("You can now delete the PDF files to save disk space.", file=sys.stderr)
        print("The index will continue to work without them.", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)

        try:
            response = input("\nDelete PDF files? (y/n): ").lower().strip()

            if response == "y":
                deleted_count = 0
                for pdf_file in pdf_files:
                    try:
                        pdf_file.unlink()
                        deleted_count += 1
                    except Exception as e:
                        print(f"Failed to delete {pdf_file.name}: {e}", file=sys.stderr)

                print(
                    f"\n[OK] Deleted {deleted_count} PDF files ({total_size_mb:.1f} MB freed)",
                    file=sys.stderr,
                )
            else:
                print(f"\nPDF files kept in {MPEP_DIR}", file=sys.stderr)
                print("You can manually delete them later if needed.", file=sys.stderr)
        except EOFError:
            # Non-interactive mode, skip cleanup
            print(
                "\nRunning in non-interactive mode, skipping PDF cleanup.",
                file=sys.stderr,
            )
            print(f"To manually delete PDFs later: rm {MPEP_DIR}/*.pdf", file=sys.stderr)

    def build_index(self, force_rebuild: bool = False):
        """Build or load the FAISS index with BM25"""
        _log_info("build_index_started", force_rebuild=force_rebuild)
        if not force_rebuild and self.index_file.exists() and self.metadata_file.exists():
            # Load existing index
            self.index = faiss.read_index(str(self.index_file))  # type: ignore[union-attr]
            with self.metadata_file.open(encoding="utf-8") as f:
                data = json.load(f)
                self.chunks = data["chunks"]
                self.metadata = data["metadata"]
            _log_info(
                f"Loaded existing index with {len(self.chunks)} chunks",
                chunk_count=len(self.chunks),
            )

            # Load BM25 tokenized corpus from JSON and rebuild index
            if BM25_AVAILABLE and BM25Okapi and self.bm25_file.exists():
                try:
                    _log_info("Loading BM25 index from disk...")
                    with self.bm25_file.open(encoding="utf-8") as bf:
                        tokenized = json.load(bf)
                    self.bm25 = BM25Okapi(tokenized)
                    _log_info("Hybrid search enabled")
                except Exception as e:
                    _log_warning(f"Failed to load BM25 index: {e}, rebuilding...", error=str(e))
                    tokenized = [chunk.lower().split() for chunk in self.chunks]
                    self.bm25 = BM25Okapi(tokenized)
            return

        # Build new index from all available sources
        _log_info("Building new index from all patent law sources...")
        all_chunks = []

        # 1. Process MPEP PDFs
        mpep_files = sorted(MPEP_DIR.glob("mpep-*.pdf"))
        if mpep_files:
            _log_info(f"Processing {len(mpep_files)} MPEP PDFs...", file_count=len(mpep_files))
            for pdf_file in mpep_files:
                _log_debug(f"Processing {pdf_file.name}...", file_name=pdf_file.name)
                chunks = self.extract_text_from_pdf(pdf_file)
                all_chunks.extend(chunks)
            mpep_chunk_count = len(
                [c for c in all_chunks if c.get("source") not in ("35_USC", "37_CFR", "SUBSEQUENT")]
            )
            _log_info(f"Extracted {mpep_chunk_count} MPEP chunks", chunk_count=mpep_chunk_count)

        # 2. Process 35 USC (Patent Laws)
        usc_file = MPEP_DIR / USC_35_FILE
        if usc_file.exists():
            _log_info("Processing 35 USC (Patent Laws)...")
            usc_chunks = self.extract_text_from_usc(usc_file)
            all_chunks.extend(usc_chunks)
            _log_info(f"Extracted {len(usc_chunks)} statute chunks", chunk_count=len(usc_chunks))
        else:
            _log_warning("35 USC not found (run --download-statutes to add)")

        # 3. Process 37 CFR (Patent Rules)
        cfr_file = MPEP_DIR / CFR_37_FILE
        if cfr_file.exists():
            _log_info("Processing 37 CFR (Patent Rules)...")
            cfr_chunks = self.extract_text_from_cfr(cfr_file)
            all_chunks.extend(cfr_chunks)
            _log_info(f"Extracted {len(cfr_chunks)} regulation chunks", chunk_count=len(cfr_chunks))
        else:
            _log_warning("37 CFR not found (run --download-regulations to add)")

        # 4. Process Subsequent Publications (Updates)
        sub_pubs_file = MPEP_DIR / SUBSEQUENT_PUBS_FILE
        if sub_pubs_file.exists():
            _log_info("Processing Subsequent Publications (post-Jan 2024 updates)...")
            update_chunks = self.extract_text_from_subsequent_pubs(sub_pubs_file)
            all_chunks.extend(update_chunks)
            _log_info(
                f"Extracted {len(update_chunks)} update chunks", chunk_count=len(update_chunks)
            )
        else:
            _log_warning("Subsequent Publications not found (run --download-updates to add)")

        # 5. Process EPC (European Patent Convention + Implementing Regulations)
        from epo_downloaders import (
            EPC_FILE,
            EPO_GUIDELINES_FILE,
            PCT_GUIDELINES_FILE,
            PCT_RULES_FILE,
            PCT_TREATY_FILE,
        )

        epc_file = MPEP_DIR / EPC_FILE
        if epc_file.exists():
            _log_info("Processing EPC (European Patent Convention + Implementing Regulations)...")
            epc_chunks = self.extract_text_from_epc(epc_file)
            all_chunks.extend(epc_chunks)
            _log_info(f"Extracted {len(epc_chunks)} EPC chunks", chunk_count=len(epc_chunks))
        else:
            _log_info("EPC not found (optional: run --download-epo to add EPO sources)")

        # 6. Process EPO Guidelines for Examination
        epo_guidelines_file = MPEP_DIR / EPO_GUIDELINES_FILE
        if epo_guidelines_file.exists():
            _log_info("Processing EPO Guidelines for Examination...")
            epo_guide_chunks = self.extract_text_from_epo_guidelines(epo_guidelines_file)
            all_chunks.extend(epo_guide_chunks)
            _log_info(f"Extracted {len(epo_guide_chunks)} EPO Guidelines chunks", chunk_count=len(epo_guide_chunks))
        else:
            _log_info("EPO Guidelines not found (optional: run --download-epo to add)")

        # 7. Process PCT Treaty
        pct_file = MPEP_DIR / PCT_TREATY_FILE
        if pct_file.exists():
            _log_info("Processing PCT Treaty...")
            pct_chunks = self.extract_text_from_pct(pct_file)
            all_chunks.extend(pct_chunks)
            _log_info(f"Extracted {len(pct_chunks)} PCT Treaty chunks", chunk_count=len(pct_chunks))
        else:
            _log_info("PCT Treaty not found (optional: run --download-pct to add PCT sources)")

        # 8. Process PCT Regulations
        pct_rules_file = MPEP_DIR / PCT_RULES_FILE
        if pct_rules_file.exists():
            _log_info("Processing PCT Regulations...")
            pct_rules_chunks = self.extract_text_from_pct_rules(pct_rules_file)
            all_chunks.extend(pct_rules_chunks)
            _log_info(f"Extracted {len(pct_rules_chunks)} PCT Rules chunks", chunk_count=len(pct_rules_chunks))
        else:
            _log_info("PCT Regulations not found (optional: run --download-pct to add)")

        # 9. Process PCT Search & Examination Guidelines (if present)
        pct_guidelines_file = MPEP_DIR / PCT_GUIDELINES_FILE
        if pct_guidelines_file.exists():
            _log_info("Processing PCT Search & Examination Guidelines...")
            pct_guide_chunks = self.extract_text_from_pct_rules(pct_guidelines_file)  # Same format as rules
            all_chunks.extend(pct_guide_chunks)
            _log_info(f"Extracted {len(pct_guide_chunks)} PCT Guidelines chunks", chunk_count=len(pct_guide_chunks))

        if not all_chunks:
            raise ValueError(
                "No chunks extracted from any sources. Run patent-creator setup to download sources."
            )

        # Create embeddings (no prefix for documents with BGE)
        _log_info(
            f"Creating embeddings for {len(all_chunks)} chunks on {self.device}...",
            chunk_count=len(all_chunks),
            device=self.device,
        )
        texts = [chunk["text"] for chunk in all_chunks]

        # Optimize batch size for GPU/CPU
        if self.device == "cuda":
            batch_size = 256  # Large batch for GPU
            _log_info(f"Using GPU batch size: {batch_size}", batch_size=batch_size)
        else:
            batch_size = 32  # Smaller batch for CPU
            _log_info(f"Using CPU batch size: {batch_size}", batch_size=batch_size)

        embeddings = self.model.encode(
            texts, batch_size=batch_size, show_progress_bar=True, device=self.device
        )
        _log_info(f"Generated {len(embeddings):,} embeddings", embedding_count=len(embeddings))

        # Build FAISS index
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)  # type: ignore[union-attr]
        self.index.add(embeddings.astype("float32"))  # type: ignore[call-arg]

        self.chunks = texts
        # Preserve all metadata from all source types
        self.metadata = []
        for c in all_chunks:
            meta = {
                "source": c.get("source", "MPEP"),
                "file": c["file"],
                "page": c["page"],
                "section": c["section"],
                "has_statute": c.get("has_statute", False),
                "has_mpep_ref": c.get("has_mpep_ref", False),
                "has_rule_ref": c.get("has_rule_ref", False),
                "is_statute": c.get("is_statute", False),
                "is_regulation": c.get("is_regulation", False),
                "is_update": c.get("is_update", False),
            }
            # Add source-specific fields
            if c.get("source") == "37_CFR":
                meta["part"] = c.get("part")
                meta["is_fee_schedule"] = c.get("is_fee_schedule", False)
            elif c.get("source") == "SUBSEQUENT":
                meta["doc_type"] = c.get("doc_type")
                meta["fr_citation"] = c.get("fr_citation")
                meta["effective_date"] = c.get("effective_date")
                meta["mpep_sections_affected"] = c.get("mpep_sections_affected", [])
                meta["supersedes_mpep"] = c.get("supersedes_mpep", False)

            self.metadata.append(meta)

        # Build BM25 index for hybrid search
        if BM25_AVAILABLE and BM25Okapi:
            _log_info("Building BM25 index for hybrid search...")
            tokenized = [chunk.lower().split() for chunk in texts]
            self.bm25 = BM25Okapi(tokenized)
            # Persist tokenized corpus as JSON (avoids insecure pickle deserialization)
            with self.bm25_file.open("w", encoding="utf-8") as bf:
                json.dump(tokenized, bf)
            _log_info("Hybrid search enabled")

        # Save index
        faiss.write_index(self.index, str(self.index_file))  # type: ignore[union-attr]
        with self.metadata_file.open("w", encoding="utf-8") as f:
            json.dump({"chunks": self.chunks, "metadata": self.metadata}, f)

        _log_info(
            f"Index built and saved with {len(self.chunks)} chunks", chunk_count=len(self.chunks)
        )
        if LOGGING_AVAILABLE and log_operation_result:
            log_operation_result("mpep_build_index", total_chunks=len(self.chunks))

        # Offer to clean up PDF files after successful indexing
        self._offer_pdf_cleanup()

    def search(
        self,
        query: str,
        top_k: int = 5,
        retrieve_k: Optional[int] = None,
        source_filter: Optional[str] = None,
        is_statute: Optional[bool] = None,
        is_regulation: Optional[bool] = None,
        is_update: Optional[bool] = None,
    ) -> list[dict[str, Any]]:
        """Advanced hybrid search with HyDE expansion and reranking

        Args:
            query: Search query
            top_k: Number of final results to return after reranking
            retrieve_k: Number of candidates to retrieve before reranking (default: top_k * 4, max 50)
            source_filter: Filter by source ("MPEP", "35_USC", "37_CFR", "SUBSEQUENT", or None for all)
            is_statute: Filter for statute content (True/False/None)
            is_regulation: Filter for regulation content (True/False/None)
            is_update: Filter for recent updates (True/False/None)
        """
        if self.index is None:
            raise ValueError("Index not built. Call build_index() first.")

        _log_info(
            "mpep_search_started", query_length=len(query), top_k=top_k, source_filter=source_filter
        )

        retrieve_k = min(top_k * 4, 50) if retrieve_k is None else min(retrieve_k, 100)
        candidates = {}

        # HyDE Query Expansion (if enabled)
        queries_to_search = [query]
        if self.use_hyde and self.hyde_expander:
            try:
                expanded_queries = self.hyde_expander.expand_query(query, num_expansions=3)
                queries_to_search = expanded_queries
                _log_debug(
                    f"HyDE: Expanded to {len(queries_to_search)} queries",
                    expansion_count=len(queries_to_search),
                )
            except Exception as e:
                _log_warning(f"HyDE expansion failed: {e}, using original query", error=str(e))

        # Search with each query variant (original + hypothetical docs)
        for query_idx, search_query in enumerate(queries_to_search):
            query_weight = 1.0 if query_idx == 0 else 0.5  # Weight original query higher

            # Vector search with BGE query prefix (recommended format)
            query_with_prefix = f"query: {search_query}"
            query_embedding = self.model.encode([query_with_prefix])
            vec_distances, vec_indices = self.index.search(  # type: ignore[union-attr]
                query_embedding.astype("float32"), retrieve_k
            )

            # Add vector search results with RRF scoring
            for rank, (idx, dist) in enumerate(zip(vec_indices[0], vec_distances[0])):
                rrf_contribution = query_weight * (1.0 / (60 + rank + 1))

                if idx in candidates:
                    candidates[idx]["rrf_score"] += rrf_contribution
                    candidates[idx]["vector_score"] = max(
                        candidates[idx].get("vector_score", 0), float(1 / (1 + dist))
                    )
                else:
                    candidates[idx] = {
                        "text": self.chunks[idx],
                        "metadata": self.metadata[idx],
                        "vector_score": float(1 / (1 + dist)),
                        "rrf_score": rrf_contribution,
                    }

            # Hybrid search: add BM25 results if available
            if self.bm25:
                tokenized_query = search_query.lower().split()
                bm25_scores = self.bm25.get_scores(tokenized_query)
                bm25_top_indices = np.argsort(bm25_scores)[::-1][:retrieve_k]  # type: ignore[union-attr]

                for rank, idx in enumerate(bm25_top_indices):
                    rrf_contribution = query_weight * (1.0 / (60 + rank + 1))

                    if idx in candidates:
                        candidates[idx]["rrf_score"] += rrf_contribution
                        candidates[idx]["bm25_score"] = max(
                            candidates[idx].get("bm25_score", 0),
                            float(bm25_scores[idx]),
                        )
                    else:
                        candidates[idx] = {
                            "text": self.chunks[idx],
                            "metadata": self.metadata[idx],
                            "bm25_score": float(bm25_scores[idx]),
                            "rrf_score": rrf_contribution,
                        }

        # Apply metadata filters if specified
        if (
            source_filter
            or is_statute is not None
            or is_regulation is not None
            or is_update is not None
        ):
            filtered_candidates = {}
            for idx, cand_data in candidates.items():
                meta = cand_data["metadata"]

                # Check source filter
                if source_filter and meta.get("source", "MPEP") != source_filter:
                    continue

                # Check statute filter
                if is_statute is not None and meta.get("is_statute", False) != is_statute:
                    continue

                # Check regulation filter
                if is_regulation is not None and meta.get("is_regulation", False) != is_regulation:
                    continue

                # Check update filter
                if is_update is not None and meta.get("is_update", False) != is_update:
                    continue

                filtered_candidates[idx] = cand_data

            candidates = filtered_candidates

        # Sort by RRF score and get top candidates for reranking
        sorted_candidates = sorted(
            candidates.items(), key=lambda x: x[1]["rrf_score"], reverse=True
        )[:retrieve_k]

        # Rerank with cross-encoder using ORIGINAL query only
        rerank_pairs = [[query, cand[1]["text"]] for cand in sorted_candidates]
        rerank_scores = self.reranker.predict(rerank_pairs)

        # Combine rerank scores with candidates
        final_results = []
        for (_idx, cand), rerank_score in zip(sorted_candidates, rerank_scores):
            final_results.append(
                {
                    "text": cand["text"],
                    "metadata": cand["metadata"],
                    "relevance_score": float(rerank_score),
                    "hybrid_rrf_score": cand["rrf_score"],
                }
            )

        # Sort by reranker score and return top_k
        final_results.sort(key=lambda x: x["relevance_score"], reverse=True)
        results = final_results[:top_k]

        _log_info("mpep_search_completed", results_count=len(results), top_k=top_k)
        if LOGGING_AVAILABLE and log_operation_result:
            log_operation_result("mpep_search", results_count=len(results))

        return results
