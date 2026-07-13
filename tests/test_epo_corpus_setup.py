"""EPO/PCT corpus wiring into setup (issue #49) and honest downloads.

The old EPC URL served a WIPO HTML page; _download_file saved it as
epc_convention.pdf and reported success, so a fresh install carried a
28 KB HTML file where the Convention should be and the index build would
feed HTML to PyMuPDF. Downloads that claim a .pdf must BE a PDF, presence
checks must not be fooled by the corrupt artifact, and setup must actually
fetch the corpus (nothing ever called the downloaders — issue #49).
"""


import pytest

from mcp_server import epo_downloaders as ed


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        yield from (
            self._body[i : i + chunk_size]
            for i in range(0, len(self._body), chunk_size)
        )


def test_download_file_rejects_html_masquerading_as_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ed.requests, "get", lambda url, **kw: _FakeResponse(b"<!DOCTYPE html><html>nope</html>")
    )
    dest = tmp_path / "epc_convention.pdf"

    ok = ed._download_file("https://example.test/x", dest, "EPC test")

    assert ok is False
    assert not dest.exists(), "corrupt download must not be left on disk"


def test_download_file_accepts_real_pdf(tmp_path, monkeypatch):
    monkeypatch.setattr(
        ed.requests, "get", lambda url, **kw: _FakeResponse(b"%PDF-1.7 fake body" * 10)
    )
    dest = tmp_path / "epc_convention.pdf"

    ok = ed._download_file("https://example.test/x", dest, "EPC test")

    assert ok is True
    assert dest.read_bytes().startswith(b"%PDF-")


def test_check_sources_treats_html_pdf_as_missing(tmp_path):
    (tmp_path / "epc_convention.pdf").write_bytes(b"<!DOCTYPE html>oops")
    (tmp_path / "pct_treaty.pdf").write_bytes(b"%PDF-1.6 real")

    status = ed.check_epo_pct_sources(tmp_path)

    assert status["epc"] is False, "HTML saved as .pdf is not a present source"
    assert status["pct_treaty"] is True


def test_epc_url_points_at_a_pdf_endpoint():
    assert ed.EPC_DOWNLOAD_URL.lower().endswith(".pdf"), (
        "the old wipolex page URL served HTML; the EPC source must be a "
        "direct PDF link"
    )


def test_guidelines_pdf_becomes_canonical_text_file(tmp_path):
    """The index build reads epo_guidelines.txt only; a downloaded PDF must
    be extracted into it or it is never indexed and never satisfies the
    presence check (setup would re-download 10+ MB every run)."""
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "epo_guidelines_2026.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "PART A - FORMALITIES EXAMINATION")
    doc.save(str(pdf_path))
    doc.close()
    dest = tmp_path / "epo_guidelines.txt"

    ok = ed._pdf_to_guidelines_text(pdf_path, dest)

    assert ok is True
    assert "FORMALITIES EXAMINATION" in dest.read_text(encoding="utf-8")


def test_setup_helper_downloads_only_missing_sources(tmp_path, monkeypatch):
    from mcp_server import cli

    calls = []
    monkeypatch.setattr(
        cli, "check_epo_pct_sources",
        lambda d: {"epc": False, "epo_guidelines": True, "pct_treaty": False,
                   "pct_rules": True, "pct_guidelines": True},
    )
    monkeypatch.setattr(cli, "download_epc", lambda d: calls.append("epc") or True)
    monkeypatch.setattr(cli, "scrape_epo_guidelines", lambda d: calls.append("guidelines") or True)
    monkeypatch.setattr(cli, "download_pct_treaty", lambda d: calls.append("pct_treaty") or True)
    monkeypatch.setattr(cli, "download_pct_rules", lambda d: calls.append("pct_rules") or True)
    monkeypatch.setattr(cli, "download_pct_guidelines", lambda d: calls.append("pct_guidelines") or True)

    got_new = cli._setup_epo_pct_sources(tmp_path)

    assert got_new is True
    assert calls == ["epc", "pct_treaty"], "only missing sources download"


def test_setup_helper_is_best_effort(tmp_path, monkeypatch):
    """EPO corpus problems must never block US setup."""
    from mcp_server import cli

    def boom(d):
        raise RuntimeError("WIPO is down")

    monkeypatch.setattr(
        cli, "check_epo_pct_sources",
        lambda d: {"epc": False, "epo_guidelines": False, "pct_treaty": False,
                   "pct_rules": False, "pct_guidelines": False},
    )
    for name in ("download_epc", "scrape_epo_guidelines", "download_pct_treaty",
                 "download_pct_rules", "download_pct_guidelines"):
        monkeypatch.setattr(cli, name, boom)

    got_new = cli._setup_epo_pct_sources(tmp_path)

    assert got_new is False


def test_setup_command_wires_epo_sources():
    """setup and download-all must invoke the EPO/PCT corpus step."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    cli_src = (root / "mcp_server" / "cli.py").read_text(encoding="utf-8")
    setup_body = cli_src.split("def setup_command", 1)[1].split("\ndef ", 1)[0]
    download_all_body = cli_src.split("def download_all_command", 1)[1].split("\ndef ", 1)[0]
    assert "_setup_epo_pct_sources" in setup_body
    assert "_setup_epo_pct_sources" in download_all_body
