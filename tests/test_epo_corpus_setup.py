"""EPO/PCT corpus wiring into setup (issue #49) and honest downloads.

The old EPC URL served a WIPO HTML page; _download_file saved it as
epc_convention.pdf and reported success, so a fresh install carried a
28 KB HTML file where the Convention should be and the index build would
feed HTML to PyMuPDF. Downloads that claim a .pdf must BE a PDF, presence
checks must not be fooled by the corrupt artifact, and setup must actually
fetch the corpus (nothing ever called the downloaders — issue #49).
"""

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


