"""Non-patent literature search: parsing, merging, and honest failure reporting.

The parser tests read real responses recorded from OpenAlex and arXiv on
2026-11-09 (tests/fixtures/literature/). The live behavior of all three
sources is checked by scripts/test_literature_search.py, which needs network
but no key.
"""

import json
import urllib.error
from pathlib import Path

import pytest

from mcp_server import literature_search as ls
from mcp_server.validation import SearchLiteratureInput, validate_input

FIX = Path(__file__).parent / "fixtures" / "literature"


def _openalex():
    return json.loads((FIX / "openalex_attention.json").read_text(encoding="utf-8"))


def _arxiv(name="arxiv_attention.xml"):
    return (FIX / name).read_text(encoding="utf-8")


# --- parsers on recorded responses -----------------------------------------


def test_arxiv_parse_empty_feed_is_zero_results():
    rows, total = ls.parse_arxiv(_arxiv("arxiv_empty.xml"))
    assert rows == [] and total == 0


def test_arxiv_parser_refuses_entity_expansion():
    bomb = (
        '<?xml version="1.0"?><!DOCTYPE f [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;">]>'
        '<feed xmlns="http://www.w3.org/2005/Atom"><title>&b;</title></feed>'
    )
    from defusedxml import EntitiesForbidden

    with pytest.raises(EntitiesForbidden):
        ls.parse_arxiv(bomb)


# --- merging ---------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_s2_waiting(monkeypatch):
    """Semantic Scholar pacing sleeps for real; tests record waits instead."""
    waits = []
    monkeypatch.setattr(ls, "_s2_sleep", waits.append)
    monkeypatch.setattr(ls, "_s2_last", [0.0])
    monkeypatch.setattr(ls, "_s2_jitter", lambda: 0.0)
    return waits


# --- search(): one failing source never reads as "no prior art" -------------


def _fake_get(responses):
    def _get(self, source, url, headers=None):
        r = responses[source]
        if isinstance(r, Exception):
            raise r
        return r

    return _get


def test_failed_source_is_reported_not_silent(monkeypatch):
    monkeypatch.setattr(
        ls.LiteratureSearch,
        "_get",
        _fake_get({
            "openalex": json.dumps(_openalex()),
            "arxiv": ls.SourceError("failed", "arxiv could not be reached: timeout"),
            "semantic_scholar": ls.SourceError("rate_limited", "busy"),
        }),
    )
    out = ls.LiteratureSearch().search("attention transduction", limit=5)
    assert out["sources"]["openalex"]["status"] == "ok"
    assert out["sources"]["arxiv"]["status"] == "failed"
    assert out["sources"]["semantic_scholar"]["status"] == "rate_limited"
    assert out["results"]


def test_all_sources_down_says_nothing_about_prior_art(monkeypatch):
    err = ls.SourceError("failed", "down")
    monkeypatch.setattr(ls.LiteratureSearch, "_get", _fake_get(dict.fromkeys(ls.SOURCES, err)))
    out = ls.LiteratureSearch().search("anything")
    assert out["results"] == []
    assert out["note"].startswith("No source could be searched")


def test_empty_answer_is_not_called_proof(monkeypatch):
    monkeypatch.setattr(
        ls.LiteratureSearch,
        "_get",
        _fake_get({"openalex": json.dumps({"meta": {"count": 0}, "results": []}),
                   "arxiv": _arxiv("arxiv_empty.xml")}),
    )
    out = ls.LiteratureSearch().search("zzq", sources=["openalex", "arxiv"])
    assert "not proof" in out["note"] and out["results"] == []


def test_http_errors_map_to_actionable_messages_without_the_key(monkeypatch):
    s = ls.LiteratureSearch(openalex_key="SECRET-KEY-123")

    def boom(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(ls.urllib.request, "urlopen", boom)
    with pytest.raises(ls.SourceError) as e:
        s._get("openalex", "https://api.openalex.org/works?api_key=SECRET-KEY-123")
    assert "SECRET-KEY-123" not in str(e.value) and e.value.__cause__ is None

    def net(req, timeout):
        raise OSError(f"connection reset for {req.full_url}")

    monkeypatch.setattr(ls.urllib.request, "urlopen", net)
    with pytest.raises(ls.SourceError) as e:
        s._get("openalex", "https://api.openalex.org/works?api_key=SECRET-KEY-123")
    assert "SECRET-KEY-123" not in str(e.value)


# --- request building --------------------------------------------------------


def test_input_validation():
    ok = validate_input(SearchLiteratureInput, query=" battery ", published_before="2020-01-01")
    assert ok.query == "battery" and ok.published_before.isoformat() == "2020-01-01"
    for bad in (
        {"query": "   "},
        {"query": "x", "published_before": "2020-13-01"},
        {"query": "x", "published_before": "2010-01-01", "published_after": "2015-01-01"},
        {"query": "x", "sources": ["google"]},
        {"query": "x", "sources": []},
    ):
        with pytest.raises(ValueError):
            validate_input(SearchLiteratureInput, **bad)


# --- review findings: each one was a way to report a false "nothing found" ----




def test_arxiv_error_feed_is_a_failure_not_zero_results():
    # Recorded from arXiv for search_query=all:(( (served with HTTP 400).
    with pytest.raises(ls.SourceError):
        ls.parse_arxiv(_arxiv("arxiv_error.xml"))


@pytest.mark.parametrize("body", ["<html><body>Service unavailable</body></html>",
                                  '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'])
def test_arxiv_non_feed_200_is_a_failure(body):
    with pytest.raises(ls.SourceError):
        ls.parse_arxiv(body)


@pytest.mark.parametrize("body", [{}, {"message": "Internal Server Error"}])
def test_semantic_scholar_bodies_without_total_are_failures(body):
    with pytest.raises(ls.SourceError):
        ls.parse_semantic_scholar(body)


def test_key_echoed_in_a_source_error_is_redacted(monkeypatch):
    monkeypatch.setattr(ls.LiteratureSearch, "_get",
                        _fake_get({"openalex": json.dumps({"error": "Invalid api_key REVIEW-KEY-123"})}))
    out = ls.LiteratureSearch(openalex_key="REVIEW-KEY-123").search("x", sources=["openalex"])
    assert out["sources"]["openalex"]["status"] == "failed"
    assert "REVIEW-KEY-123" not in json.dumps(out)
    # Place the key across the cut point: the prefix is
    # "OpenAlex reported an error: " (28 chars), so the key spans 295-309.
    long_echo = json.dumps({"error": "x" * (ls.MESSAGE_CHARS - 28 - 5) + "REVIEW-KEY-123"})
    monkeypatch.setattr(ls.LiteratureSearch, "_get", _fake_get({"openalex": long_echo}))
    out = ls.LiteratureSearch(openalex_key="REVIEW-KEY-123").search("x", sources=["openalex"])
    assert "REVIE" not in json.dumps(out), "shortened before redacting"


def test_unreadable_body_keeps_no_context(monkeypatch):
    monkeypatch.setattr(ls.LiteratureSearch, "_get", _fake_get({"openalex": '{"error":"fake+key/123="'}))
    with pytest.raises(ls.SourceError) as e:
        ls.LiteratureSearch(openalex_key="fake+key/123=")._openalex("x", 5, None, None)
    assert e.value.__context__ is None


@pytest.mark.parametrize("body", [{"error": "Query failed"}, {"message": "bad", "code": "400"}, []])
def test_error_bodies_with_http_200_are_failures(body):
    for parse in (ls.parse_openalex, ls.parse_semantic_scholar):
        with pytest.raises(ls.SourceError):
            parse(body)


def test_query_with_no_words_left_for_arxiv_is_skipped_not_searched(monkeypatch):
    def never(self, source, url, headers=None):
        raise AssertionError("no request should be sent")

    monkeypatch.setattr(ls.LiteratureSearch, "_get", never)
    out = ls.LiteratureSearch().search('(): ""', sources=["arxiv"])
    assert out["sources"]["arxiv"]["status"] == "skipped"


def test_same_title_different_papers_stay_apart():
    a = ls._record(title="Introduction", doi="10.1000/one", year=2010)
    b = ls._record(title="Introduction", doi="10.1000/two", year=2020, abstract="Bob")
    merged = ls.merge_results({"openalex": [a], "semantic_scholar": [b]}, 10)
    assert len(merged) == 2
    long_a = ls._record(title="A long and specific title about mower wires", doi="10.1/a", year=2010)
    long_b = ls._record(title="A long and specific title about mower wires", doi="10.1/b", year=2010)
    assert len(ls.merge_results({"openalex": [long_a], "arxiv": [long_b]}, 10)) == 2


@pytest.mark.parametrize(
    "rec,flagged",
    [
        ({"publication_date": None, "year": 2017}, True),     # year only, cutoff year
        ({"publication_date": None, "year": 2015}, False),    # year only, earlier year
    ],
)
def test_uncertain_dates_are_flagged(rec, flagged):
    assert bool(ls.date_caution(ls._record(title="t", **rec), "2017-06-13")) is flagged


def test_escaped_and_encoded_keys_are_redacted():
    s = ls.LiteratureSearch(openalex_key="fake+key/123=", semantic_scholar_key="FAKE-SECRET\nbad")
    text = "url api_key=fake%2Bkey%2F123%3D and api_key=fake+key/123= header b'FAKE-SECRET\\nbad'"
    out = s._redact(text)
    assert "FAKE-SECRET" not in out and "%2Bkey" not in out and "key/123" not in out


def test_transport_error_keeps_no_context_holding_the_key(monkeypatch):
    s = ls.LiteratureSearch(openalex_key="SECRET-KEY-123")

    def net(req, timeout):
        raise OSError(f"reset for {req.full_url}")

    monkeypatch.setattr(ls.urllib.request, "urlopen", net)
    with pytest.raises(ls.SourceError) as e:
        s._get("openalex", "https://api.openalex.org/works?api_key=SECRET-KEY-123")
    assert e.value.__context__ is None and e.value.__cause__ is None


# --- Crossref cross-check of listed dates -------------------------------------
# crossref_dates.json was recorded live on 2026-11-09 (full records trimmed to
# their date fields). Three of its DOIs carry wrong dates: a 2026 paper listed
# as 2016-03-16 (DOI registered 2026-04-23), a 2022 Springer chapter listed as
# 2012-02-24 (print 2022), and a 2021 article dated 1970-01-01 (journal issue
# 2021-12-07). The Nature and 1999 Elsevier papers are correctly dated.


def _openalex_work(title, doi, published):
    return {"id": f"https://openalex.org/W{abs(hash(doi))}", "doi": f"https://doi.org/{doi}",
            "title": title, "publication_date": published, "publication_year": int(published[:4])}


def _crossref():
    return (FIX / "crossref_dates.json").read_text(encoding="utf-8")


def test_crossref_parse_reads_registration_and_publisher_dates():
    with pytest.raises(ls.SourceError):
        ls.parse_crossref_dates(json.dumps({"status": "error", "message": "bad filter"}))


def _search_with(monkeypatch, works, crossref, cutoff):
    monkeypatch.setattr(ls.LiteratureSearch, "_get", _fake_get({
        "openalex": json.dumps({"meta": {"count": len(works)}, "results": works}),
        "crossref": crossref,
    }))
    return ls.LiteratureSearch().search("q", sources=["openalex"], published_before=cutoff)


def test_crossref_down_still_returns_results_and_says_dates_are_unchecked(monkeypatch):
    out = _search_with(monkeypatch, [_openalex_work("Deep learning", "10.1038/nature14539", "2015-05-27")],
                       ls.SourceError("failed", "crossref search failed: HTTP 503"), "2017-06-12")
    assert out["results"] and out["date_cross_check"]["status"] == "failed"
    out = _search_with(monkeypatch, [_openalex_work("Deep learning", "10.1038/nature14539", "2015-05-27")],
                       KeyError("unexpected"), "2017-06-12")
    assert out["results"] and out["date_cross_check"]["status"] == "failed"


def test_dates_crossref_does_not_know_are_labeled_unchecked(monkeypatch):
    out = _search_with(monkeypatch, [
        _openalex_work("Deep learning", "10.1038/nature14539", "2015-05-27"),
        _openalex_work("RAG accuracy", "10.5281/zenodo.8430247", "2023-10-11"),
    ], _crossref(), "2024-01-01")
    assert out["date_cross_check"]["unchecked"] == 1


def test_epoch_publisher_date_is_never_trusted_and_issue_date_exposes_it():
    info = {"registered": ls.date(2022, 7, 28),
            "dates": [("online", ls.EPOCH), ("journal issue online", ls.date(2021, 12, 7))]}
    msg = ls.crossref_caution(ls._record(title="t", publication_date="1999-05-01"), info, "2000-01-01")
    assert msg


def test_merged_dates_are_kept_per_source_and_disagreement_is_flagged(monkeypatch):
    work = _openalex_work("Attention is all you need", "10.48550/arxiv.1706.03762", "2016-06-12")
    monkeypatch.setattr(ls.LiteratureSearch, "_get", _fake_get({
        "openalex": json.dumps({"meta": {"count": 1}, "results": [work]}),
        "arxiv": _arxiv(),
    }))
    out = ls.LiteratureSearch().search("attention", sources=["openalex", "arxiv"], published_before="2018-01-01")
    hit = next(r for r in out["results"] if (r.get("arxiv_id") or "").startswith("1706.03762"))
    assert hit["dates_by_source"]["openalex"] == "2016-06-12"


def test_unchecked_count_is_reported_when_crossref_is_down(monkeypatch):
    out = _search_with(monkeypatch, [_openalex_work("Deep learning", "10.1038/nature14539", "2015-05-27")],
                       ls.SourceError("failed", "crossref search failed: HTTP 503"), "2017-06-12")
    assert out["date_cross_check"]["unchecked"] == 1


