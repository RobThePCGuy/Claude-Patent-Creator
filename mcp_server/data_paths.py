"""Where downloaded corpora and the search index live on disk (issue #51).

These used to be derived from ``Path(__file__)``, i.e. inside the installed
package, where a reinstall or venv removal silently destroys ~650 MB of
downloads plus a 5-15 minute index build.

Resolution order for each directory:

1. ``PATENT_DATA_DIR`` environment variable (also settable via
   ``patent-creator config set PATENT_DATA_DIR ...`` — the config layer
   bridges file values into the environment at server startup).
2. The legacy in-tree location, only when it already contains data — so
   installs that predate this module keep using what they downloaded, with
   no migration step.
3. The platform app-data directory, which survives pip upgrades and
   reinstalls.
"""

import os
from pathlib import Path

_PACKAGE_DIR = Path(__file__).parent

# Legacy in-tree locations (pre-#51). Module-level so tests can repoint them.
LEGACY_PDFS_DIR = _PACKAGE_DIR.parent / "pdfs"
LEGACY_INDEX_DIR = _PACKAGE_DIR / "index"
LEGACY_DIAGRAMS_DIR = _PACKAGE_DIR.parent / "diagrams"

_APP_DIR_NAME = "claude-patent-creator"


def _default_base() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / _APP_DIR_NAME / "data"
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / _APP_DIR_NAME / "data"


def _resolve(name: str, legacy: Path, has_data) -> Path:
    override = os.environ.get("PATENT_DATA_DIR")
    if override:
        return Path(override) / name
    try:
        if has_data(legacy):
            return legacy
    except OSError:
        pass
    return _default_base() / name


def mpep_dir() -> Path:
    """Directory holding MPEP/USC/CFR source PDFs and text."""
    return _resolve("pdfs", LEGACY_PDFS_DIR, lambda p: any(p.glob("*.pdf")))


def index_dir() -> Path:
    """Directory holding the FAISS index and chunk store."""
    return _resolve("index", LEGACY_INDEX_DIR, lambda p: (p / "mpep_index.faiss").exists())


def diagrams_dir() -> Path:
    """Default output directory for generated diagrams."""
    return _resolve("diagrams", LEGACY_DIAGRAMS_DIR, lambda p: p.is_dir() and any(p.iterdir()))
