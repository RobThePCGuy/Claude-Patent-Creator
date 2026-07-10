"""Downloaded corpora and the search index must not live in site-packages.

Issue #51: ~650 MB of PDFs plus a 5-15 minute index build lived at paths
derived from Path(__file__), i.e. inside the installed package, where a
reinstall or venv removal silently destroys them. data_paths resolves each
data directory as: PATENT_DATA_DIR override > legacy in-tree location when
it already holds data (existing installs keep working) > platform app-data.
"""

import pytest

from mcp_server import data_paths


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    monkeypatch.delenv("PATENT_DATA_DIR", raising=False)
    # Point the legacy locations at empty temp dirs so the machine running
    # the tests (which may have a real install) does not leak into them.
    monkeypatch.setattr(data_paths, "LEGACY_PDFS_DIR", tmp_path / "legacy_pdfs")
    monkeypatch.setattr(data_paths, "LEGACY_INDEX_DIR", tmp_path / "legacy_index")
    monkeypatch.setattr(data_paths, "LEGACY_DIAGRAMS_DIR", tmp_path / "legacy_diagrams")


def test_override_wins(monkeypatch, tmp_path):
    override = tmp_path / "mydata"
    monkeypatch.setenv("PATENT_DATA_DIR", str(override))

    assert data_paths.mpep_dir() == override / "pdfs"
    assert data_paths.index_dir() == override / "index"
    assert data_paths.diagrams_dir() == override / "diagrams"


def test_legacy_location_with_data_is_kept(monkeypatch, tmp_path):
    """An install that already downloaded everything keeps using it."""
    legacy_pdfs = tmp_path / "legacy_pdfs"
    legacy_pdfs.mkdir()
    (legacy_pdfs / "mpep-0100.pdf").write_bytes(b"x")
    legacy_index = tmp_path / "legacy_index"
    legacy_index.mkdir()
    (legacy_index / "mpep_index.faiss").write_bytes(b"x")

    assert data_paths.mpep_dir() == legacy_pdfs
    assert data_paths.index_dir() == legacy_index


def test_fresh_install_defaults_outside_site_packages(monkeypatch, tmp_path):
    """No override, no legacy data -> platform app-data, never the package."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

    for resolved in (data_paths.mpep_dir(), data_paths.index_dir()):
        assert data_paths._PACKAGE_DIR not in resolved.parents
        assert resolved != data_paths._PACKAGE_DIR
        assert "claude-patent-creator" in str(resolved)


def test_empty_legacy_dir_does_not_count_as_data(tmp_path):
    """A leftover empty directory must not pin data to site-packages."""
    (tmp_path / "legacy_pdfs").mkdir()

    assert data_paths.mpep_dir() != tmp_path / "legacy_pdfs"
